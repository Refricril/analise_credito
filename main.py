import os
import io
import logging
import traceback
from datetime import datetime
from functools import wraps
import pytz
import pandas as pd
import psycopg2
import sentry_sdk
from flask import Flask, render_template, request, jsonify, session, send_file, Response
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from dotenv import load_dotenv
from urllib.parse import quote_plus

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv()

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Configuração do Sentry para monitoramento de erros em produção
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        traces_sample_rate=1.0,
        environment=os.getenv("FLASK_ENV", "production")
    )

app = Flask(__name__)

# Configurações de Segurança
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    logger.error("SECRET_KEY não definida! Gerando chave aleatória...")
    app.secret_key = os.urandom(24)

# Configuração de Sessão
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutos
Session(app)

# Configuração do Talisman (Segurança HTTPS)
csp = {
    'default-src': ["'self'"],
    'script-src': ["'self'", "'unsafe-inline'", 'cdn.jsdelivr.net', 'cdn.tailwindcss.com'],
    'style-src': ["'self'", "'unsafe-inline'", 'fonts.googleapis.com'],
    'font-src': ["'self'", 'fonts.gstatic.com'],
    'img-src': ["'self'", 'data:'],
}
Talisman(app, content_security_policy=csp, force_https=False)  # force_https=True em produção

# Configuração do Rate Limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Timezone
TIMEZONE = pytz.timezone('America/Sao_Paulo')

# Dicionário de usuários com hash de senha em produção
USERS = {
    "financeiro": os.getenv("FINANCEIRO_PASS", "fin123"),
    "admin": os.getenv("ADMIN_PASS", "admin123")
}

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "application_name": "analise_financeira"  # Identificação no banco de dados
}

# Validação de configuração do banco de dados
if not all(DB_CONFIG.values()):
    logger.error("Configurações do banco de dados incompletas!")
    raise ValueError("Configurações do banco de dados incompletas. Verifique o arquivo .env")

QUERY_FILE_PATH = "query.sql"
COLUMN_MAPPING = {
    'id_cliente': 'cod_cliente',
    'nome_cliente': 'cliente',
    'doc_cliente': 'documento_cliente',  # CPF/CNPJ do cliente
    'valor_devido': 'vlr_total_vencidos',
    'total_compras': 'vlr_totalcompras',
    'documento': 'documento',  # Column name from final SELECT
    'data_emissao': 'data_emissao',
    'parcela': 'parcela',  # Column name from final SELECT
    'mes_referencia': 'mes_referencia'
}

def require_login(f):
    """Decorator para verificar se o usuário está logado."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'success': False, 'message': 'Acesso não autorizado.'}), 401
        return f(*args, **kwargs)
    return decorated_function

def validate_date(date_str):
    """Valida e converte string de data."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=TIMEZONE)
    except ValueError as e:
        raise ValueError(f"Data inválida: {date_str}") from e

def format_currency(value):
    """Formata valor monetário."""
    return f"R$ {value:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')

def log_error(e, context=""):
    """Registra erro no log com contexto."""
    logger.error(f"{context}: {str(e)}\n{''.join(traceback.format_tb(e.__traceback__))}")

# --- FUNÇÕES DE BANCO DE DADOS ---
def get_db_connection():
    """Estabelece uma nova conexão com o banco de dados com timeout e retry."""
    retries = 3
    for attempt in range(retries):
        try:
            encoded_pass = quote_plus(DB_CONFIG["password"])
            conn_string = f"postgresql://{DB_CONFIG['user']}:{encoded_pass}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}?application_name={DB_CONFIG['application_name']}"
            conn = psycopg2.connect(
                conn_string,
                connect_timeout=10,
                options='-c statement_timeout=300000'  # 5 minutos timeout
            )
            conn.set_session(readonly=True)  # Modo somente leitura por segurança
            return conn
        except psycopg2.Error as e:
            log_error(e, f"Tentativa {attempt + 1} de {retries} de conexão com o banco")
            if attempt == retries - 1:
                raise
    return None

def get_data_for_period(position_date):
    """Executa a query para uma data de posição e retorna um DataFrame."""
    start_time = datetime.now()
    logger.info(f"Iniciando consulta para data: {position_date}")
    
    try:
        validate_date(position_date)
        conn = get_db_connection()
        
        with open(QUERY_FILE_PATH, 'r', encoding='utf-8') as f:
            query = f.read()
        
        num_placeholders = query.count('%s')
        params = (position_date,) * num_placeholders
        
        df = pd.read_sql(query, conn, params=params)
        
        # Validações dos dados
        if df.empty:
            logger.warning(f"Nenhum dado encontrado para a data: {position_date}")
            return pd.DataFrame(columns=COLUMN_MAPPING.values())
            
        # Conversão de tipos e limpeza
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].str.strip()
        
        # Validação de valores monetários
        for col in [COLUMN_MAPPING['valor_devido'], COLUMN_MAPPING['total_compras']]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            invalid_values = df[col].isna().sum()
            if invalid_values > 0:
                logger.warning(f"Encontrados {invalid_values} valores inválidos na coluna {col}")
        
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Consulta concluída em {execution_time:.2f} segundos. Registros: {len(df)}")
        
        return df
        
    except (psycopg2.Error, pd.io.sql.DatabaseError) as e:
        log_error(e, "Erro na consulta SQL")
        raise
    except Exception as e:
        log_error(e, "Erro inesperado ao buscar dados")
        raise
    finally:
        if 'conn' in locals() and conn:
            conn.close()

# --- ROTAS DA APLICAÇÃO ---
@app.route('/favicon.ico')
def favicon():
    """Serve o favicon ou retorna 204 se não existir."""
    return '', 204

@app.route('/')
def index():
    """Renderiza a página principal."""
    if session.get('logged_in'):
        logger.info(f"Acesso à página principal por {session.get('username')}")
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")  # Limite de tentativas de login
def login():
    """Valida as credenciais do usuário."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Usuário e senha são obrigatórios'}), 400
        
        if username in USERS and USERS[username] == password:
            session.clear()  # Limpa qualquer sessão anterior
            session['logged_in'] = True
            session['username'] = username
            session['login_time'] = datetime.now(TIMEZONE).isoformat()
            
            logger.info(f"Login bem-sucedido: {username}")
            return jsonify({'success': True})
        
        logger.warning(f"Tentativa de login mal-sucedida para usuário: {username}")
        return jsonify({'success': False, 'message': 'Usuário ou senha inválida'}), 401
        
    except Exception as e:
        log_error(e, "Erro no processo de login")
        return jsonify({'success': False, 'message': 'Erro interno no servidor'}), 500

@app.route('/api/logout')
@require_login
def logout():
    """Encerra a sessão do usuário."""
    try:
        username = session.get('username')
        session.clear()
        logger.info(f"Logout bem-sucedido: {username}")
        return jsonify({'success': True})
    except Exception as e:
        log_error(e, "Erro no processo de logout")
        return jsonify({'success': False, 'message': 'Erro ao fazer logout'}), 500

@app.route('/api/get-data', methods=['POST'])
@require_login
@limiter.limit("30 per minute")
def get_chart_data():
    """Busca e processa os dados para o dashboard."""
    start_time = datetime.now()
    logger.info(f"Iniciando análise por {session.get('username')}")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400
            
        date_a_str = data.get('date_a')
        date_b_str = data.get('date_b')
        
        if not date_a_str or not date_b_str:
            return jsonify({'success': False, 'message': 'Datas são obrigatórias'}), 400
            
        # Validação das datas
        try:
            date_a = validate_date(date_a_str)
            date_b = validate_date(date_b_str)
            
            if date_a > datetime.now(TIMEZONE) or date_b > datetime.now(TIMEZONE):
                return jsonify({'success': False, 'message': 'Datas não podem ser futuras'}), 400
                
            if abs((date_a - date_b).days) > 365:
                return jsonify({'success': False, 'message': 'Intervalo entre datas não pode ser maior que 1 ano'}), 400
                
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400
            
        # Busca dos dados com medição de performance e filtro de data
        logger.info(f"Buscando dados para as datas: {date_a_str} e {date_b_str}")
        df_a = get_data_for_period(date_a_str)
        df_b = get_data_for_period(date_b_str)
        
        # Log dos dados encontrados antes do filtro
        logger.info(f"Dados encontrados - Período A: {len(df_a)} registros, Período B: {len(df_b)} registros")
        
        # A query já filtra pela data de posição, não precisamos filtrar novamente aqui
        # Apenas vamos converter a coluna de data para facilitar outros processamentos
        data_col = COLUMN_MAPPING['data_emissao']
        df_a[f'{data_col}_dt'] = pd.to_datetime(df_a[data_col], format='%d/%m/%Y', errors='coerce')
        df_b[f'{data_col}_dt'] = pd.to_datetime(df_b[data_col], format='%d/%m/%Y', errors='coerce')
        
        logger.info(f"Dados para análise: {len(df_a)} registros no período A e {len(df_b)} registros no período B")
        
        # Verificar se temos dados para análise
        if df_a.empty and df_b.empty:
            return jsonify({
                'success': True,
                'message': 'Nenhum dado encontrado para as datas selecionadas',
                'date_a_display': pd.to_datetime(date_a_str).strftime('%d/%m/%Y'),
                'date_b_display': pd.to_datetime(date_b_str).strftime('%d/%m/%Y'),
                'stats': {'total_clientes': 0, 'clientes_com_aumento': 0, 'clientes_com_reducao': 0, 'variacao_total': 0},
                'variacao_divida': [],
                'compradores_a': [],
                'compradores_b': [],
                'docs_por_periodo_a': [],
                'docs_por_periodo_b': [],
                'detalhes_a': [],
                'detalhes_b': [],
                'execution_time': (datetime.now() - start_time).total_seconds()
            })
        
        # --- ANÁLISE COMPARATIVA ---
        id_col = COLUMN_MAPPING['id_cliente']
        nome_col = COLUMN_MAPPING['nome_cliente']
        doc_cliente_col = COLUMN_MAPPING['doc_cliente']
        devido_col = COLUMN_MAPPING['valor_devido']
        compras_col = COLUMN_MAPPING['total_compras']
        doc_col = COLUMN_MAPPING['documento']
        data_col = COLUMN_MAPPING['data_emissao']
        parcela_col = COLUMN_MAPPING['parcela']
        mes_col = COLUMN_MAPPING['mes_referencia']
        
        # Preparação dos dados para comparação
        colunas_merge = [id_col, nome_col, doc_cliente_col, devido_col, doc_col, data_col, parcela_col, mes_col]
        
        # Verificar e mostrar as colunas disponíveis em caso de erro
        logger.info(f"Colunas disponíveis em df_a: {df_a.columns.tolist()}")
        logger.info(f"Colunas disponíveis em df_b: {df_b.columns.tolist()}")
        logger.info(f"Colunas que estamos tentando usar: {colunas_merge}")
        
        # Preparar dados para merge - agregando por cliente primeiro
        if not df_a.empty:
            df_a_grouped = df_a.groupby(id_col).agg({
                nome_col: 'first',
                doc_cliente_col: 'first', 
                devido_col: 'sum',
                compras_col: 'sum'
            }).reset_index()
        else:
            df_a_grouped = pd.DataFrame(columns=[id_col, nome_col, doc_cliente_col, devido_col, compras_col])
            
        if not df_b.empty:
            df_b_grouped = df_b.groupby(id_col).agg({
                nome_col: 'first',
                doc_cliente_col: 'first',
                devido_col: 'sum', 
                compras_col: 'sum'
            }).reset_index()
        else:
            df_b_grouped = pd.DataFrame(columns=[id_col, nome_col, doc_cliente_col, devido_col, compras_col])
        
        # Merge com validação de dados
        df_comparativo = pd.merge(
            df_a_grouped,
            df_b_grouped,
            on=[id_col],
            how='outer',
            suffixes=('_A', '_B')
        )
        
        # Limpeza e preparação dos dados
        df_comparativo[nome_col] = df_comparativo[f'{nome_col}_A'].fillna(df_comparativo[f'{nome_col}_B'])
        df_comparativo[doc_cliente_col] = df_comparativo[f'{doc_cliente_col}_A'].fillna(df_comparativo[f'{doc_cliente_col}_B'])
        
        # Remover colunas duplicadas
        colunas_para_remover = [col for col in [f'{nome_col}_B', f'{doc_cliente_col}_B'] if col in df_comparativo.columns]
        df_comparativo.drop(columns=colunas_para_remover, inplace=True)
        
        # Preencher valores nulos com 0 para cálculos
        df_comparativo.fillna(0, inplace=True)
        
        # Cálculo das variações
        df_comparativo['Diferenca_Divida'] = df_comparativo[f'{devido_col}_A'] - df_comparativo[f'{devido_col}_B']
        df_comparativo['Variacao_Percentual'] = (
            (df_comparativo[f'{devido_col}_A'] - df_comparativo[f'{devido_col}_B']) /
            df_comparativo[f'{devido_col}_B'].replace(0, float('nan')) * 100
        ).fillna(0)
        
        # Filtragem e ordenação
        df_variacao = df_comparativo[df_comparativo['Diferenca_Divida'] != 0].copy()
        maiores_aumentos = df_variacao.nlargest(5, 'Diferenca_Divida')
        maiores_reducoes = df_variacao.nsmallest(5, 'Diferenca_Divida')
        df_variacao_final = pd.concat([maiores_aumentos, maiores_reducoes]).sort_values('Diferenca_Divida', ascending=False)
        
        # Análise de compradores
        compradores_a = df_a.nlargest(min(10, len(df_a)), compras_col) if not df_a.empty else pd.DataFrame()
        compradores_b = df_b.nlargest(min(10, len(df_b)), compras_col) if not df_b.empty else pd.DataFrame()
        
        # Estatísticas adicionais
        stats = {
            'total_clientes': len(df_comparativo),
            'clientes_com_aumento': len(df_variacao[df_variacao['Diferenca_Divida'] > 0]),
            'clientes_com_reducao': len(df_variacao[df_variacao['Diferenca_Divida'] < 0]),
            'variacao_total': float(df_variacao['Diferenca_Divida'].sum())
        }
        
        # Formatação das datas
        date_a_display = date_a.strftime('%d/%m/%Y')
        date_b_display = date_b.strftime('%d/%m/%Y')

        # Formatação dos valores monetários para exibição
        df_variacao_final['Diferenca_Divida_Fmt'] = df_variacao_final['Diferenca_Divida'].apply(format_currency)
        df_variacao_final['Variacao_Percentual_Fmt'] = df_variacao_final['Variacao_Percentual'].apply(lambda x: f"{x:.1f}%")
        
        for df in [compradores_a, compradores_b]:
            df[f'{devido_col}_fmt'] = df[devido_col].apply(format_currency)
            df[f'{compras_col}_fmt'] = df[compras_col].apply(format_currency)
        
        # Log de performance
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Análise concluída em {execution_time:.2f} segundos")
        
        # Preparar grupos de documentos por período
        doc_col = COLUMN_MAPPING['documento']
        data_col = COLUMN_MAPPING['data_emissao']
        parcela_col = COLUMN_MAPPING['parcela']
        
        docs_por_periodo_a = df_a[[doc_col, data_col, parcela_col]].to_dict('records') if not df_a.empty else []
        docs_por_periodo_b = df_b[[doc_col, data_col, parcela_col]].to_dict('records') if not df_b.empty else []
        
        # Retorno dos dados
        return jsonify({
            'success': True,
            'date_a_display': date_a_display,
            'date_b_display': date_b_display,
            'stats': stats,
            'variacao_divida': df_variacao_final.to_dict('records'),
            'compradores_a': compradores_a.to_dict('records'),
            'compradores_b': compradores_b.to_dict('records'),
            'docs_por_periodo_a': docs_por_periodo_a,
            'docs_por_periodo_b': docs_por_periodo_b,
            'detalhes_a': df_a.to_dict('records'),
            'detalhes_b': df_b.to_dict('records'),
            'execution_time': execution_time
        })
        
    except Exception as e:
        log_error(e, "Erro ao processar dados para o dashboard")
        return jsonify({
            'success': False,
            'message': 'Erro ao processar os dados',
            'error': str(e) if app.debug else 'Erro interno do servidor'
        }), 500

@app.route('/api/export', methods=['POST'])
@require_login
@limiter.limit("10 per minute")
def export_data():
    """Exporta os dados completos para XLSX ou CSV."""
    start_time = datetime.now()
    logger.info(f"Iniciando exportação por {session.get('username')}")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400
            
        date_a_str = data.get('date_a')
        date_b_str = data.get('date_b')
        export_format = data.get('format')
        
        if not all([date_a_str, date_b_str, export_format]):
            return jsonify({'success': False, 'message': 'Parâmetros incompletos'}), 400
            
        if export_format not in ['xlsx', 'csv']:
            return jsonify({'success': False, 'message': 'Formato de exportação inválido'}), 400
        
        # Busca e validação dos dados
        df_a = get_data_for_period(date_a_str)
        df_b = get_data_for_period(date_b_str)

        # Debug: Verificar estrutura dos dados iniciais
        logger.info(f"Colunas disponíveis em df_a: {df_a.columns.tolist()}")
        logger.info(f"Colunas disponíveis em df_b: {df_b.columns.tolist()}")
        logger.info(f"Amostra de df_a:\n{df_a.head(1).to_dict('records')}")
        
        # Preparação dos dados
        id_col = COLUMN_MAPPING['id_cliente']
        nome_col = COLUMN_MAPPING['nome_cliente']
        devido_col = COLUMN_MAPPING['valor_devido']
        compras_col = COLUMN_MAPPING['total_compras']
        doc_col = COLUMN_MAPPING['documento']
        data_col = COLUMN_MAPPING['data_emissao']
        parcela_col = COLUMN_MAPPING['parcela']
        
        # Primeiro agregar os dados por cliente
        doc_cliente_col = COLUMN_MAPPING['doc_cliente']
        logger.info(f"Iniciando agregação para {len(df_a)} registros do período A e {len(df_b)} registros do período B")
        
        try:
            df_a_agg = df_a.groupby([id_col, nome_col, doc_cliente_col]).agg({
                devido_col: 'sum',
                compras_col: 'sum',
                doc_col: lambda x: ', '.join(sorted(x)),
                data_col: lambda x: ', '.join(sorted(x))  # data_col já está formatada como string
            }).reset_index()
            logger.info(f"Agregação do período A concluída. Resultados: {len(df_a_agg)} registros")
            logger.info(f"Colunas após agregação A: {df_a_agg.columns.tolist()}")
        except Exception as e:
            log_error(e, "Erro na agregação do período A")
            raise
        
        try:
            df_b_agg = df_b.groupby([id_col, nome_col, doc_cliente_col]).agg({
                devido_col: 'sum',
                compras_col: 'sum',
                doc_col: lambda x: ', '.join(sorted(x)),
                data_col: lambda x: ', '.join(sorted(x))  # data_col já está formatada como string
            }).reset_index()
            logger.info(f"Agregação do período B concluída. Resultados: {len(df_b_agg)} registros")
            logger.info(f"Colunas após agregação B: {df_b_agg.columns.tolist()}")
        except Exception as e:
            log_error(e, "Erro na agregação do período B")
            raise
        
        # Agora podemos fazer o merge com os dados agregados
        logger.info("Iniciando merge dos dados agregados")
        try:
            df_comparativo = pd.merge(
                df_a_agg,
                df_b_agg,
                on=[id_col],  # Merge apenas no ID do cliente para evitar problemas com duplicatas
                how='outer',
                suffixes=('_A', '_B')
            )
            logger.info(f"Merge concluído. Resultados: {len(df_comparativo)} registros")
            logger.info(f"Colunas após merge: {df_comparativo.columns.tolist()}")
        except Exception as e:
            log_error(e, "Erro durante o merge dos dados")
            raise
        
        # Limpeza e cálculos
        df_comparativo[f'{nome_col}_A'].fillna(df_comparativo[f'{nome_col}_B'], inplace=True)
        df_comparativo[f'{doc_cliente_col}_A'].fillna(df_comparativo[f'{doc_cliente_col}_B'], inplace=True)
        df_comparativo.drop(columns=[f'{nome_col}_B', f'{doc_cliente_col}_B'], inplace=True, errors='ignore')
        df_comparativo.fillna(0, inplace=True)
        
        df_comparativo['Diferenca_Divida'] = df_comparativo[f'{devido_col}_A'] - df_comparativo[f'{devido_col}_B']
        df_comparativo['Diferenca_Compras'] = df_comparativo[f'{compras_col}_A'] - df_comparativo[f'{compras_col}_B']
        df_comparativo['Variacao_Percentual_Divida'] = (
            (df_comparativo[f'{devido_col}_A'] - df_comparativo[f'{devido_col}_B']) /
            df_comparativo[f'{devido_col}_B'].replace(0, float('nan')) * 100
        ).fillna(0)
        
        # Preparação do DataFrame final
        logger.info("Iniciando preparação do DataFrame final")
        try:
            date_a_display = pd.to_datetime(date_a_str).strftime('%d/%m/%Y')
            date_b_display = pd.to_datetime(date_b_str).strftime('%d/%m/%Y')
            
            df_final = df_comparativo[ [
                id_col, f'{nome_col}_A', f'{doc_cliente_col}_A',
                f'{devido_col}_A', f'{devido_col}_B',
                'Diferenca_Divida', 'Variacao_Percentual_Divida',
                f'{compras_col}_A', f'{compras_col}_B', 'Diferenca_Compras',
                f'{doc_col}_A', f'{data_col}_A',
                f'{doc_col}_B', f'{data_col}_B'
            ]].rename(columns={
                id_col: 'Código Cliente',
                f'{nome_col}_A': 'Nome Cliente',
                f'{doc_cliente_col}_A': 'CPF/CNPJ',
                f'{devido_col}_A': f'Dívida Vencida ({date_a_display})',
                f'{devido_col}_B': f'Dívida Vencida ({date_b_display})',
                'Diferenca_Divida': 'Diferença Dívida',
                'Variacao_Percentual_Divida': 'Variação Percentual',
                f'{compras_col}_A': f'Total Compras ({date_a_display})',
                f'{compras_col}_B': f'Total Compras ({date_b_display})',
                'Diferenca_Compras': 'Diferença Compras',
                f'{doc_col}_A': f'Documentos ({date_a_display})',
                f'{data_col}_A': f'Data Emissão ({date_a_display})',
                f'{doc_col}_B': f'Documentos ({date_b_display})',
                f'{data_col}_B': f'Data Emissão ({date_b_display})'
            })
            logger.info(f"DataFrame final preparado com {len(df_final)} registros")
            logger.info(f"Colunas finais: {df_final.columns.tolist()}")
        except Exception as e:
            log_error(e, "Erro na preparação do DataFrame final")
            raise
        
        # Exportação
        output = io.BytesIO()
        filename = f"relatorio_comparativo_{date_a_str}_vs_{date_b_str}"
        
        try:
            if export_format == 'xlsx':
                logger.info("Iniciando exportação para Excel")
                try:
                    writer = pd.ExcelWriter(output, engine='openpyxl')
                    df_final.to_excel(writer, sheet_name='Comparativo_Periodos', index=False)
                    
                    # Ajuste automático das colunas
                    workbook = writer.book
                    worksheet = writer.sheets['Comparativo_Periodos']
                    for i, col in enumerate(df_final.columns):
                        max_length = max(
                            df_final[col].astype(str).apply(len).max(),
                            len(str(col))
                        ) + 2
                        worksheet.column_dimensions[chr(65 + i)].width = min(max_length, 50)
                    
                    writer.close()
                    logger.info("Arquivo Excel gerado com sucesso")
                    mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    filename += '.xlsx'
                except Exception as e:
                    log_error(e, "Erro na geração do arquivo Excel")
                    raise
            
            else:  # csv
                logger.info("Iniciando exportação para CSV")
                try:
                    df_final.to_csv(
                        output,
                        index=False,
                        sep=';',
                        encoding='utf-8-sig',
                        float_format='%.2f'
                    )
                    logger.info("Arquivo CSV gerado com sucesso")
                    mimetype = 'text/csv'
                    filename += '.csv'
                except Exception as e:
                    log_error(e, "Erro na geração do arquivo CSV")
                    raise
            
        except Exception as e:
            log_error(e, "Erro na geração do arquivo de exportação")
            return jsonify({'success': False, 'message': 'Erro ao gerar arquivo'}), 500
        
        output.seek(0)
        
        # Log de performance
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Exportação concluída em {execution_time:.2f} segundos. Formato: {export_format}")
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        log_error(e, "Erro no processo de exportação")
        return jsonify({
            'success': False,
            'message': 'Erro ao exportar dados',
            'error': str(e) if app.debug else 'Erro interno do servidor'
        }), 500

# --- Handlers de Erro ---
@app.errorhandler(429)
def ratelimit_handler(e):
    """Handler para limite de requisições excedido."""
    return jsonify({
        'success': False,
        'message': 'Limite de requisições excedido. Tente novamente em alguns minutos.'
    }), 429

@app.errorhandler(500)
def internal_error(e):
    """Handler para erros internos do servidor."""
    log_error(e, "Erro interno do servidor")
    return jsonify({
        'success': False,
        'message': str(e) if app.debug else 'Erro interno do servidor'
    }), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Handler global para exceções não tratadas."""
    log_error(e, "Exceção não tratada")
    return jsonify({
        'success': False,
        'message': 'Erro inesperado no servidor',
        'error': str(e) if app.debug else 'Erro interno'
    }), 500

# --- Configurações de Produção ---
def configure_app_for_production():
    """Configura a aplicação para ambiente de produção."""
    if os.getenv('FLASK_ENV') == 'production':
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=1800,  # 30 minutos
        )
        
        # Configurações adicionais de segurança do Talisman
        Talisman(app,
            force_https=True,
            strict_transport_security=True,
            session_cookie_secure=True,
            content_security_policy=csp
        )

if __name__ == '__main__':
    if os.getenv('FLASK_ENV') == 'production':
        configure_app_for_production()
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5503)), debug=False)
    else:
        app.run(host='0.0.0.0', port=5503, debug=True)