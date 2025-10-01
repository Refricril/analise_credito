import os
import logging
import traceback
from datetime import datetime, date
import pytz
import pandas as pd
import psycopg2
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
from urllib.parse import quote_plus
import io
import folium
from streamlit_folium import st_folium
import json

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv()

# Configuração da página
st.set_page_config(
    page_title="Dashboard Financeiro - Refricril",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    .stDataFrame {
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# Timezone
TIMEZONE = pytz.timezone('America/Sao_Paulo')

# Configurações do banco de dados
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "application_name": "analise_financeira_streamlit"
}

# Validar configurações do banco
if not all(DB_CONFIG.values()):
    st.error("⚠️ Configurações do banco de dados incompletas! Verifique o arquivo .env")
    st.stop()

# Mapeamento de colunas
COLUMN_MAPPING = {
    'id_cliente': 'cod_cliente',
    'nome_cliente': 'cliente',
    'doc_cliente': 'documento_cliente',
    'uf_cliente': 'uf_cliente',
    'cidade_cliente': 'cidade_cliente',
    'valor_devido': 'vlr_total_vencidos',
    'total_compras': 'vlr_totalcompras',
    'documento': 'documento',
    'data_emissao': 'data_emissao',
    'parcela': 'parcela',
    'mes_referencia': 'mes_referencia'
}

def test_db_connection():
    """Testa a conexão com o banco de dados."""
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao testar conexão: {str(e)}")
        return False

def authenticate():
    """Função de autenticação simples."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.markdown('<div class="main-header">🔐 Acesso ao Dashboard Financeiro</div>', unsafe_allow_html=True)
        
        # Testar conexão com banco
        with st.spinner("🔍 Verificando conexão com banco de dados..."):
            if not test_db_connection():
                st.error("❌ **Erro de Conexão**: Não foi possível conectar ao banco de dados. Verifique as configurações.")
                st.info("🔧 **Configurações necessárias no .env:**")
                st.code("""
DB_HOST=seu_host
DB_PORT=5432
DB_NAME=seu_banco
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
                """)
                st.stop()
            else:
                st.success("✅ Conexão com banco de dados OK!")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                username = st.text_input("Usuário", help="Use: admin ou financeiro")
                password = st.text_input("Senha", type="password", help="Senha padrão: admin123 ou fin123")
                login_button = st.form_submit_button("🚪 Entrar", type="primary")
                
                if login_button:
                    # Validação simples
                    valid_users = {
                        "admin": os.getenv("ADMIN_PASS", "admin123"),
                        "financeiro": os.getenv("FINANCEIRO_PASS", "fin123")
                    }
                    
                    if username in valid_users and valid_users[username] == password:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.success("✅ Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Usuário ou senha inválidos!")
        return False
    
    return True

def get_db_connection():
    """Estabelece conexão com o banco de dados."""
    try:
        encoded_pass = quote_plus(DB_CONFIG["password"])
        conn_string = f"postgresql://{DB_CONFIG['user']}:{encoded_pass}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}?application_name={DB_CONFIG['application_name']}"
        conn = psycopg2.connect(
            conn_string,
            connect_timeout=10,
            options='-c statement_timeout=300000'
        )
        conn.set_session(readonly=True)
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        logger.error(f"Erro de conexão: {str(e)}")
        return None

@st.cache_data(ttl=300, show_spinner=False)
def get_data_for_period(position_date):
    """Executa a query para uma data de posição e retorna um DataFrame."""
    start_time = datetime.now()
    
    try:
        conn = get_db_connection()
        if conn is None:
            return pd.DataFrame()
        
        with open("query.sql", 'r', encoding='utf-8') as f:
            query = f.read()
        
        num_placeholders = query.count('%s')
        params = (position_date,) * num_placeholders
        
        df = pd.read_sql(query, conn, params=params)
        
        if df.empty:
            logger.warning(f"Nenhum dado encontrado para a data: {position_date}")
            return pd.DataFrame(columns=list(COLUMN_MAPPING.values()))
            
        # Limpeza dos dados
        for col in df.select_dtypes(include=['object']).columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        # Conversão de valores monetários
        for col in [COLUMN_MAPPING['valor_devido'], COLUMN_MAPPING['total_compras']]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Consulta concluída em {execution_time:.2f}s. Registros: {len(df)}")
        
        conn.close()
        return df
        
    except Exception as e:
        logger.error(f"Erro ao buscar dados: {str(e)}")
        st.error(f"Erro ao buscar dados: {str(e)}")
        return pd.DataFrame()

def format_currency(value):
    """Formata valor monetário."""
    if pd.isna(value):
        return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')

@st.cache_data(ttl=3600)
def load_brasil_estados():
    """Carrega dados dos estados brasileiros."""
    try:
        with open('brasil_estados.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Arquivo brasil_estados.json não encontrado!")
        return {}

@st.cache_data(ttl=3600)
def load_brasil_cidades():
    """Carrega dados das cidades brasileiras."""
    try:
        with open('brasil_cidades.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Arquivo brasil_cidades.json não encontrado!")
        return {}

def create_brasil_map(df_data, uf_col, value_col, cidade_col=None, nivel_visualizacao="Estado", title="Concentração Geográfica"):
    """Cria mapa interativo do Brasil com concentração de dados por estado ou cidade."""
    
    if df_data.empty:
        return None
    
    # Criar mapa centrado no Brasil
    mapa = folium.Map(
        location=[-14.2350, -51.9253],  # Centro do Brasil
        zoom_start=4 if nivel_visualizacao == "Estado" else 5,
        tiles='CartoDB positron'  # Mapa mais limpo
    )
    
    def get_color_intensity(valor, min_val, max_val):
        """Calcula cor baseada no valor: verde (baixo) para vermelho (alto)"""
        if max_val == min_val:
            return 0.5
        return (valor - min_val) / (max_val - min_val)
    
    def value_to_color(intensity):
        """Converte intensidade (0-1) em cor HTML (verde -> amarelo -> vermelho)"""
        if intensity <= 0.5:
            # Verde para amarelo
            r = int(255 * intensity * 2)
            g = 255
            b = 0
        else:
            # Amarelo para vermelho
            r = 255
            g = int(255 * (2 - intensity * 2))
            b = 0
        return f"#{r:02x}{g:02x}{b:02x}"
    
    if nivel_visualizacao == "Estado":
        # Visualização por estado
        estados_info = load_brasil_estados()
        if not estados_info:
            return None
        
        # Agregar dados por UF
        df_map = df_data.groupby(uf_col)[value_col].agg(['sum', 'count', 'mean']).reset_index()
        df_map.columns = ['uf', 'total_valor', 'total_clientes', 'valor_medio']
        
        # Definir escala de cores
        min_valor = df_map['total_valor'].min()
        max_valor = df_map['total_valor'].max()
        
        for _, row in df_map.iterrows():
            uf = row['uf']
            
            if uf in estados_info:
                estado_info = estados_info[uf]
                
                # Calcular intensidade da cor baseada no valor
                intensidade = get_color_intensity(row['total_valor'], min_valor, max_valor)
                cor = value_to_color(intensidade)
                
                # Tooltip com informações
                tooltip_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <b style="font-size: 14px;">{estado_info['nome']} ({uf})</b><br><br>
                    <b>👥 Total de Clientes:</b> {row['total_clientes']:,}<br>
                    <b>💰 Valor Total:</b> {format_currency(row['total_valor'])}<br>
                    <b>📊 Valor Médio:</b> {format_currency(row['valor_medio'])}<br>
                </div>
                """
                
                # Calcular tamanho do marcador
                min_clientes = df_map['total_clientes'].min()
                max_clientes = df_map['total_clientes'].max()
                size_factor = (row['total_clientes'] - min_clientes) / (max_clientes - min_clientes) if max_clientes > min_clientes else 0.5
                radius = 10 + (size_factor * 25)
                
                # Adicionar marcador circular
                folium.CircleMarker(
                    location=[estado_info['lat'], estado_info['lng']],
                    radius=radius,
                    popup=folium.Popup(tooltip_text, max_width=350),
                    tooltip=f"{estado_info['nome']}: {format_currency(row['total_valor'])}",
                    color='#333333',
                    fillColor=cor,
                    fillOpacity=0.8,
                    weight=2
                ).add_to(mapa)
    
    else:  # Visualização por cidade
        if cidade_col is None:
            return None
            
        cidades_info = load_brasil_cidades()
        if not cidades_info:
            return None
        
        # Agregar dados por UF e Cidade
        df_map = df_data.groupby([uf_col, cidade_col])[value_col].agg(['sum', 'count', 'mean']).reset_index()
        df_map.columns = ['uf', 'cidade', 'total_valor', 'total_clientes', 'valor_medio']
        
        # Filtrar apenas cidades com dados válidos
        df_map = df_map[df_map['cidade'].str.strip() != ''].copy()
        
        # Definir escala de cores
        min_valor = df_map['total_valor'].min() if not df_map.empty else 0
        max_valor = df_map['total_valor'].max() if not df_map.empty else 0
        
        def normalize_city_name(name):
            """Normaliza nome da cidade para busca"""
            import unicodedata
            return ''.join(c for c in unicodedata.normalize('NFD', name.upper().strip()) 
                         if unicodedata.category(c) != 'Mn')
        
        for _, row in df_map.iterrows():
            uf = row['uf']
            cidade = row['cidade'].strip().title()
            
            # Procurar coordenadas da cidade
            cidade_coord = None
            if uf in cidades_info:
                # Busca exata primeiro
                if cidade in cidades_info[uf]:
                    cidade_coord = cidades_info[uf][cidade]
                else:
                    # Busca normalizada
                    cidade_norm = normalize_city_name(cidade)
                    for cidade_db, coord in cidades_info[uf].items():
                        if normalize_city_name(cidade_db) == cidade_norm:
                            cidade_coord = coord
                            break
            
            if cidade_coord:
                # Calcular intensidade da cor
                intensidade = get_color_intensity(row['total_valor'], min_valor, max_valor)
                cor = value_to_color(intensidade)
                
                # Tooltip com informações
                tooltip_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <b style="font-size: 14px;">{cidade} - {uf}</b><br><br>
                    <b>👥 Total de Clientes:</b> {row['total_clientes']:,}<br>
                    <b>💰 Valor Total:</b> {format_currency(row['total_valor'])}<br>
                    <b>📊 Valor Médio:</b> {format_currency(row['valor_medio'])}<br>
                </div>
                """
                
                # Calcular tamanho do marcador
                min_clientes = df_map['total_clientes'].min()
                max_clientes = df_map['total_clientes'].max()
                size_factor = (row['total_clientes'] - min_clientes) / (max_clientes - min_clientes) if max_clientes > min_clientes else 0.5
                radius = 5 + (size_factor * 15)  # Menor para cidades
                
                # Adicionar marcador circular
                folium.CircleMarker(
                    location=[cidade_coord['lat'], cidade_coord['lng']],
                    radius=radius,
                    popup=folium.Popup(tooltip_text, max_width=350),
                    tooltip=f"{cidade}: {format_currency(row['total_valor'])}",
                    color='navy',
                    fillColor=cor,
                    fillOpacity=0.9,
                    weight=1
                ).add_to(mapa)
    
    # Criar legenda atualizada
    min_val_display = min_valor if 'min_valor' in locals() else 0
    max_val_display = max_valor if 'max_valor' in locals() else 0
    
    legend_html = f'''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 250px; height: auto; 
                background-color: white; border: 2px solid #333; z-index: 9999; 
                font-size: 12px; padding: 15px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h4 style="margin: 0 0 10px 0; color: #333; font-size: 14px;">{title}</h4>
        <p style="margin: 5px 0; font-weight: bold;">Nível: {nivel_visualizacao}</p>
        
        <div style="margin-bottom: 10px;">
            <b>Escala de Cores:</b><br>
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 15px; background: #00ff00; border: 1px solid #ccc; margin-right: 8px;"></div>
                <span style="font-size: 11px;">Menor valor</span>
            </div>
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 15px; background: #ffff00; border: 1px solid #ccc; margin-right: 8px;"></div>
                <span style="font-size: 11px;">Valor médio</span>
            </div>
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 15px; background: #ff0000; border: 1px solid #ccc; margin-right: 8px;"></div>
                <span style="font-size: 11px;">Maior valor</span>
            </div>
        </div>
        
        <div>
            <b>Tamanho dos Círculos:</b><br>
            <span style="font-size: 11px;">Proporcional ao número de clientes</span>
        </div>
        
        <div style="margin-top: 10px; font-size: 11px; color: #666;">
            <b>Valores:</b><br>
            Mín: {format_currency(min_val_display)}<br>
            Máx: {format_currency(max_val_display)}
        </div>
    </div>
    '''
    mapa.get_root().html.add_child(folium.Element(legend_html))
    
    return mapa

def create_comparison_chart(df_variacao):
    """Cria gráfico de comparação de variações."""
    if df_variacao.empty:
        return None
    
    # Limitar a 15 maiores variações para melhor visualização
    df_plot = df_variacao.head(15)
    
    fig = px.bar(
        df_plot,
        x='Diferenca_Divida',
        y='cliente',
        orientation='h',
        title="Maiores Variações de Dívida",
        labels={'Diferenca_Divida': 'Variação (R$)', 'cliente': 'Cliente'},
        color='Diferenca_Divida',
        color_continuous_scale=['red', 'yellow', 'green']
    )
    
    fig.update_layout(
        height=600,
        showlegend=False,
        yaxis={'categoryorder': 'total ascending'}
    )
    
    return fig

def create_top_buyers_chart(df_a, df_b, compras_col):
    """Cria gráfico comparativo dos maiores compradores."""
    if df_a.empty and df_b.empty:
        return None
    
    top_a = df_a.nlargest(10, compras_col) if not df_a.empty else pd.DataFrame()
    top_b = df_b.nlargest(10, compras_col) if not df_b.empty else pd.DataFrame()
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Período A', 'Período B'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    if not top_a.empty:
        fig.add_trace(
            go.Bar(
                x=top_a[compras_col],
                y=top_a['cliente'],
                orientation='h',
                name='Período A',
                marker_color='lightblue'
            ),
            row=1, col=1
        )
    
    if not top_b.empty:
        fig.add_trace(
            go.Bar(
                x=top_b[compras_col],
                y=top_b['cliente'],
                orientation='h',
                name='Período B',
                marker_color='lightcoral'
            ),
            row=1, col=2
        )
    
    fig.update_layout(height=600, showlegend=False)
    fig.update_xaxes(title_text="Total Compras (R$)")
    fig.update_yaxes(title_text="Cliente")
    
    return fig

def main():
    """Função principal da aplicação."""
    
    # Verificar autenticação
    if not authenticate():
        return
    
    # Header
    st.markdown('<div class="main-header">📊 Dashboard Financeiro - Refricril</div>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("⚙️ Configurações")
    st.sidebar.markdown(f"👤 **Usuário:** {st.session_state.username}")
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Filtros na sidebar
    st.sidebar.markdown("### 📅 Período de Análise")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        date_a = st.date_input(
            "Data Posição A",
            value=date(2025, 10, 1),
            max_value=date.today()
        )
    with col2:
        date_b = st.date_input(
            "Data Posição B",
            value=date(2025, 9, 1),
            max_value=date.today()
        )
    
    # Botão para gerar análise
    if st.sidebar.button("🔍 Gerar Análise", type="primary"):
        st.session_state.analyze = True
    
    # Verificar se deve executar análise
    if 'analyze' not in st.session_state:
        st.info("👈 Configure as datas na barra lateral e clique em 'Gerar Análise' para começar.")
        return
    
    # Validações
    if date_a == date_b:
        st.error("⚠️ As datas devem ser diferentes!")
        return
    
    if abs((date_a - date_b).days) > 365:
        st.error("⚠️ O intervalo entre datas não pode ser maior que 1 ano!")
        return
    
    # Executar análise
    with st.spinner("🔄 Carregando dados..."):
        df_a = get_data_for_period(date_a.strftime('%Y-%m-%d'))
        df_b = get_data_for_period(date_b.strftime('%Y-%m-%d'))
    
    # Verificar se há dados
    if df_a.empty and df_b.empty:
        st.warning("⚠️ Nenhum dado encontrado para as datas selecionadas.")
        st.info("💡 **Dica:** Verifique se as datas estão corretas e se existem dados no sistema para esse período.")
        return
    
    if df_a.empty:
        st.warning(f"⚠️ Nenhum dado encontrado para {date_a.strftime('%d/%m/%Y')}")
    
    if df_b.empty:
        st.warning(f"⚠️ Nenhum dado encontrado para {date_b.strftime('%d/%m/%Y')}")
    
    # Colunas para análise
    id_col = COLUMN_MAPPING['id_cliente']
    nome_col = COLUMN_MAPPING['nome_cliente']
    doc_cliente_col = COLUMN_MAPPING['doc_cliente']
    uf_col = COLUMN_MAPPING['uf_cliente']
    cidade_col = COLUMN_MAPPING['cidade_cliente']
    devido_col = COLUMN_MAPPING['valor_devido']
    compras_col = COLUMN_MAPPING['total_compras']
    
    # Debug: mostrar informações sobre os dados
    with st.expander("🔍 Informações de Debug", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Período A ({date_a.strftime('%d/%m/%Y')})**")
            st.write(f"- Registros encontrados: {len(df_a):,}")
            if not df_a.empty:
                st.write(f"- Colunas: {', '.join(df_a.columns[:5])}...")
                st.write(f"- Total dívidas: {format_currency(df_a[devido_col].sum())}")
        
        with col2:
            st.write(f"**Período B ({date_b.strftime('%d/%m/%Y')})**")
            st.write(f"- Registros encontrados: {len(df_b):,}")
            if not df_b.empty:
                st.write(f"- Colunas: {', '.join(df_b.columns[:5])}...")
                st.write(f"- Total dívidas: {format_currency(df_b[devido_col].sum())}")
    
    # Processar dados
    df_a_grouped = df_a.groupby(id_col).agg({
        nome_col: 'first',
        doc_cliente_col: 'first',
        uf_col: 'first',
        cidade_col: 'first',
        devido_col: 'sum',
        compras_col: 'sum'
    }).reset_index() if not df_a.empty else pd.DataFrame(columns=[id_col, nome_col, doc_cliente_col, uf_col, cidade_col, devido_col, compras_col])
    
    df_b_grouped = df_b.groupby(id_col).agg({
        nome_col: 'first',
        doc_cliente_col: 'first',
        uf_col: 'first',
        cidade_col: 'first',
        devido_col: 'sum',
        compras_col: 'sum'
    }).reset_index() if not df_b.empty else pd.DataFrame(columns=[id_col, nome_col, doc_cliente_col, uf_col, cidade_col, devido_col, compras_col])
    
    # Merge dos dados
    if not df_a_grouped.empty and not df_b_grouped.empty:
        df_comparativo = pd.merge(
            df_a_grouped,
            df_b_grouped,
            on=[id_col],
            how='outer',
            suffixes=('_A', '_B')
        )
    elif not df_a_grouped.empty:
        df_comparativo = df_a_grouped.copy()
        # Para colunas de texto, usar string vazia; para valores numéricos, usar 0
        for col in [f'{nome_col}_B', f'{doc_cliente_col}_B', f'{uf_col}_B', f'{cidade_col}_B']:
            df_comparativo[col] = ''
        for col in [f'{devido_col}_B', f'{compras_col}_B']:
            df_comparativo[col] = 0
    elif not df_b_grouped.empty:
        df_comparativo = df_b_grouped.copy()
        df_comparativo = df_comparativo.rename(columns={
            nome_col: f'{nome_col}_B',
            doc_cliente_col: f'{doc_cliente_col}_B',
            uf_col: f'{uf_col}_B',
            cidade_col: f'{cidade_col}_B',
            devido_col: f'{devido_col}_B',
            compras_col: f'{compras_col}_B'
        })
        # Para colunas de texto, usar string vazia; para valores numéricos, usar 0
        for col in [f'{nome_col}_A', f'{doc_cliente_col}_A', f'{uf_col}_A', f'{cidade_col}_A']:
            df_comparativo[col] = ''
        for col in [f'{devido_col}_A', f'{compras_col}_A']:
            df_comparativo[col] = 0
    else:
        df_comparativo = pd.DataFrame()
    
    if not df_comparativo.empty:
        # Limpeza dos dados - usar coalesce ao invés de concatenação
        df_comparativo[nome_col] = df_comparativo[f'{nome_col}_A'].fillna(df_comparativo[f'{nome_col}_B'])
        df_comparativo[doc_cliente_col] = df_comparativo[f'{doc_cliente_col}_A'].fillna(df_comparativo[f'{doc_cliente_col}_B'])
        df_comparativo[uf_col] = df_comparativo[f'{uf_col}_A'].fillna(df_comparativo[f'{uf_col}_B'])
        df_comparativo[cidade_col] = df_comparativo[f'{cidade_col}_A'].fillna(df_comparativo[f'{cidade_col}_B'])
        
        # Garantir que as colunas existam
        for col in [f'{devido_col}_A', f'{devido_col}_B', f'{compras_col}_A', f'{compras_col}_B']:
            if col not in df_comparativo.columns:
                df_comparativo[col] = 0
        
        df_comparativo.fillna(0, inplace=True)
        
        # Cálculos
        df_comparativo['Diferenca_Divida'] = df_comparativo[f'{devido_col}_A'] - df_comparativo[f'{devido_col}_B']
        df_comparativo['Variacao_Percentual'] = (
            (df_comparativo[f'{devido_col}_A'] - df_comparativo[f'{devido_col}_B']) /
            df_comparativo[f'{devido_col}_B'].replace(0, float('nan')) * 100
        ).fillna(0)
    
    # Estatísticas gerais
    st.markdown("## 📈 Resumo Executivo")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_clientes = len(df_comparativo) if not df_comparativo.empty else 0
        st.metric("👥 Total de Clientes", f"{total_clientes:,}")
    
    with col2:
        if not df_comparativo.empty:
            aumentos = len(df_comparativo[df_comparativo['Diferenca_Divida'] > 0])
        else:
            aumentos = 0
        st.metric("📈 Clientes c/ Aumento", f"{aumentos:,}")
    
    with col3:
        if not df_comparativo.empty:
            reducoes = len(df_comparativo[df_comparativo['Diferenca_Divida'] < 0])
        else:
            reducoes = 0
        st.metric("📉 Clientes c/ Redução", f"{reducoes:,}")
    
    with col4:
        if not df_comparativo.empty:
            variacao_total = df_comparativo['Diferenca_Divida'].sum()
        else:
            variacao_total = 0
        st.metric("💰 Variação Total", format_currency(variacao_total))
    
    # Abas para diferentes análises
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Variações", "🛒 Compradores", "🗺️ Mapa Brasil", "📋 Dados Detalhados", "📤 Exportar"])
    
    with tab1:
        st.markdown("### 🔄 Maiores Variações de Dívida")
        
        if not df_comparativo.empty:
            df_variacao = df_comparativo[df_comparativo['Diferenca_Divida'] != 0].copy()
            df_variacao = df_variacao.sort_values('Diferenca_Divida', ascending=False)
            
            if not df_variacao.empty:
                # Gráfico
                fig = create_comparison_chart(df_variacao)
                if fig:
                    st.plotly_chart(fig, width='stretch')
                
                # Tabela das variações
                st.markdown("#### 📋 Detalhes das Variações")
                
                # Preparar dados para exibição (SEM formatação para manter ordenação numérica)
                df_display = df_variacao[[
                    id_col, uf_col, nome_col, doc_cliente_col,
                    f'{devido_col}_A', f'{devido_col}_B',
                    'Diferenca_Divida', 'Variacao_Percentual'
                ]].copy()
                
                # Renomear colunas (mantendo valores numéricos)
                df_display.columns = [
                    'Código', 'UF', 'Cliente', 'CPF/CNPJ',
                    f'Dívida ({date_a.strftime("%d/%m/%Y")})',
                    f'Dívida ({date_b.strftime("%d/%m/%Y")})',
                    'Diferença', 'Variação %'
                ]
                
                # Aplicar formatação monetária brasileira
                df_display_formatted = df_display.copy()
                df_display_formatted[f'Dívida ({date_a.strftime("%d/%m/%Y")})'] = df_display_formatted[f'Dívida ({date_a.strftime("%d/%m/%Y")})'].apply(format_currency)
                df_display_formatted[f'Dívida ({date_b.strftime("%d/%m/%Y")})'] = df_display_formatted[f'Dívida ({date_b.strftime("%d/%m/%Y")})'].apply(format_currency)
                df_display_formatted['Diferença'] = df_display_formatted['Diferença'].apply(format_currency)
                df_display_formatted['Variação %'] = df_display_formatted['Variação %'].apply(lambda x: f"{x:.1f}%")
                
                st.dataframe(df_display_formatted, width='stretch')
            else:
                st.info("Nenhuma variação encontrada entre os períodos.")
        else:
            st.info("Nenhum dado disponível para comparação.")
    
    with tab2:
        st.markdown("### 🛒 Análise dos Maiores Compradores")
        
        if not df_a.empty or not df_b.empty:
            fig = create_top_buyers_chart(df_a, df_b, compras_col)
            if fig:
                st.plotly_chart(fig, width='stretch')
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"#### 📅 Top 10 - {date_a.strftime('%d/%m/%Y')}")
                if not df_a.empty:
                    top_a = df_a.nlargest(10, compras_col)[[nome_col, compras_col]].copy()
                    top_a.columns = ['Cliente', 'Total Compras']
                    # Formatação brasileira
                    top_a['Total Compras'] = top_a['Total Compras'].apply(format_currency)
                    
                    st.dataframe(top_a, width='stretch')
                else:
                    st.info("Sem dados para este período")
            
            with col2:
                st.markdown(f"#### 📅 Top 10 - {date_b.strftime('%d/%m/%Y')}")
                if not df_b.empty:
                    top_b = df_b.nlargest(10, compras_col)[[nome_col, compras_col]].copy()
                    top_b.columns = ['Cliente', 'Total Compras']
                    # Formatação brasileira
                    top_b['Total Compras'] = top_b['Total Compras'].apply(format_currency)
                    
                    st.dataframe(top_b, width='stretch')
                else:
                    st.info("Sem dados para este período")
        else:
            st.info("Nenhum dado disponível para análise de compradores.")
    
    with tab3:
        st.markdown("### 🗺️ Concentração Geográfica - Brasil")
        
        # Filtros para o mapa
        col1, col2 = st.columns([2, 1])
        
        with col2:
            st.markdown("#### 🎛️ Filtros do Mapa")
            
            # Seletor de nível de visualização
            nivel_mapa = st.radio(
                "🗺️ Nível de Visualização:",
                options=["Estado", "Cidade"],
                key="nivel_mapa",
                horizontal=True
            )
            
            periodo_mapa = st.selectbox(
                "📅 Período:",
                options=[
                    f"Período A ({date_a.strftime('%d/%m/%Y')})",
                    f"Período B ({date_b.strftime('%d/%m/%Y')})",
                    "🔄 Comparativo (Diferença)"
                ],
                key="periodo_mapa"
            )
            
            if periodo_mapa.startswith("🔄"):
                metrica_mapa = st.selectbox(
                    "📊 Métrica:",
                    options=[
                        "💰 Maior Dívida (Diferença)",
                        "📈 Maior Variação (%)",
                        "🛒 Diferença Compras"
                    ],
                    key="metrica_mapa"
                )
            else:
                metrica_mapa = st.selectbox(
                    "📊 Métrica:",
                    options=[
                        "💰 Maior Dívida",
                        "🛒 Total Compras", 
                        "👥 Número de Clientes"
                    ],
                    key="metrica_mapa"
                )
            
            # Filtro adicional por valor
            if not df_comparativo.empty or not df_a.empty or not df_b.empty:
                st.markdown("---")
                
                filtro_valor = st.checkbox("🔍 Filtrar por valor mínimo", key="filtro_valor")
                
                if filtro_valor:
                    if periodo_mapa.startswith("🔄"):
                        min_diferenca = st.number_input(
                            "Diferença mínima (R$):",
                            min_value=0.0,
                            value=1000.0,
                            step=100.0,
                            key="min_diferenca"
                        )
                    else:
                        min_valor = st.number_input(
                            "Valor mínimo (R$):",
                            min_value=0.0,
                            value=5000.0,
                            step=500.0,
                            key="min_valor"
                        )
        
        # Preparar dados para o mapa
        df_mapa = None
        titulo_mapa = "Concentração por Estado"
        valor_col = None
        
        if periodo_mapa.startswith("Período A") and not df_a.empty:
            df_mapa = df_a.copy()
            if "Maior Dívida" in metrica_mapa:
                valor_col = devido_col
                titulo_mapa = f"💰 Maior Dívida por Estado - {date_a.strftime('%d/%m/%Y')}"
            elif "Total Compras" in metrica_mapa:
                valor_col = compras_col
                titulo_mapa = f"🛒 Total Compras por Estado - {date_a.strftime('%d/%m/%Y')}"
            else:  # Número de Clientes
                # Criar coluna auxiliar para contar clientes
                df_mapa['count_clientes'] = 1
                valor_col = 'count_clientes'
                titulo_mapa = f"👥 Número de Clientes por Estado - {date_a.strftime('%d/%m/%Y')}"
                
        elif periodo_mapa.startswith("Período B") and not df_b.empty:
            df_mapa = df_b.copy()
            if "Maior Dívida" in metrica_mapa:
                valor_col = devido_col
                titulo_mapa = f"💰 Maior Dívida por Estado - {date_b.strftime('%d/%m/%Y')}"
            elif "Total Compras" in metrica_mapa:
                valor_col = compras_col
                titulo_mapa = f"🛒 Total Compras por Estado - {date_b.strftime('%d/%m/%Y')}"
            else:  # Número de Clientes
                # Criar coluna auxiliar para contar clientes
                df_mapa['count_clientes'] = 1
                valor_col = 'count_clientes'
                titulo_mapa = f"👥 Número de Clientes por Estado - {date_b.strftime('%d/%m/%Y')}"
                
        elif periodo_mapa.startswith("🔄") and not df_comparativo.empty:
            # Preparar dados comparativos com UF
            df_mapa = df_comparativo.copy()
            
            if "Maior Dívida (Diferença)" in metrica_mapa:
                valor_col = 'Diferenca_Divida'
                titulo_mapa = "💰 Diferença de Dívida por Estado"
            elif "Maior Variação" in metrica_mapa:
                valor_col = 'Variacao_Percentual'
                titulo_mapa = "📈 Variação Percentual por Estado"
            elif "Diferença Compras" in metrica_mapa:
                # Calcular diferença de compras se não existir
                if 'Diferenca_Compras' not in df_mapa.columns:
                    df_mapa['Diferenca_Compras'] = (df_mapa.get(f'{compras_col}_A', 0) - 
                                                   df_mapa.get(f'{compras_col}_B', 0))
                valor_col = 'Diferenca_Compras'
                titulo_mapa = "🛒 Diferença de Compras por Estado"
        
        # Aplicar filtros se especificados
        if df_mapa is not None and not df_mapa.empty and valor_col and 'filtro_valor' in locals():
            if st.session_state.get('filtro_valor', False):
                if periodo_mapa.startswith("🔄"):
                    min_threshold = st.session_state.get('min_diferenca', 1000.0)
                    if valor_col == 'Variacao_Percentual':
                        # Para variação percentual, filtrar por valores absolutos maiores que 10%
                        df_mapa = df_mapa[abs(df_mapa[valor_col]) >= 10]
                    else:
                        # Para diferenças monetárias
                        df_mapa = df_mapa[abs(df_mapa[valor_col]) >= min_threshold]
                else:
                    min_threshold = st.session_state.get('min_valor', 5000.0)
                    df_mapa = df_mapa[df_mapa[valor_col] >= min_threshold]
        
        if df_mapa is not None and not df_mapa.empty and valor_col and uf_col in df_mapa.columns:
            # Remover registros com UF vazio ou inválido
            df_mapa_clean = df_mapa.dropna(subset=[uf_col]).copy()
            df_mapa_clean = df_mapa_clean[df_mapa_clean[uf_col].str.len() == 2]  # UF deve ter 2 caracteres
            
            if not df_mapa_clean.empty:
                # Ajustar título baseado no nível de visualização
                if nivel_mapa == "Cidade":
                    titulo_mapa = titulo_mapa.replace("por Estado", "por Cidade")
                
                # Criar mapa com o nível apropriado
                cidade_col_param = COLUMN_MAPPING['cidade_cliente'] if nivel_mapa == "Cidade" else None
                mapa_brasil = create_brasil_map(
                    df_mapa_clean, 
                    uf_col, 
                    valor_col, 
                    cidade_col_param, 
                    nivel_mapa, 
                    titulo_mapa
                )
                
                if mapa_brasil:
                    with col1:
                        st.markdown(f"### {titulo_mapa}")
                        
                        # Exibir mapa interativo
                        map_data = st_folium(
                            mapa_brasil,
                            width=850,
                            height=550,
                            returned_objects=["last_clicked"]
                        )
                    
                    # Estatísticas por estado
                    st.markdown("#### 📊 Ranking dos Estados")
                    
                    # Agregar dados por UF para mostrar na tabela
                    if valor_col == 'Variacao_Percentual':
                        # Para variação percentual, mostrar média ponderada
                        df_estados = df_mapa_clean.groupby(uf_col).agg({
                            valor_col: ['mean', 'count'],
                            devido_col if f'{devido_col}_A' in df_mapa_clean.columns else f'{devido_col}_A': 'sum'
                        }).reset_index()
                        df_estados.columns = ['UF', 'Variação_Média', 'Quantidade', 'Valor_Total']
                        df_estados = df_estados.sort_values('Variação_Média', key=abs, ascending=False)
                        
                        # Formatação para variação percentual
                        df_estados_display = df_estados.copy()
                        df_estados_display['Variação_Média'] = df_estados_display['Variação_Média'].apply(lambda x: f"{x:.1f}%")
                        df_estados_display['Valor_Total'] = df_estados_display['Valor_Total'].apply(format_currency)
                        df_estados_display['Quantidade'] = df_estados_display['Quantidade'].apply(lambda x: f"{x:,}")
                        df_estados_display.columns = ['🏛️ Estado', '📈 Variação Média', '👥 Clientes', '💰 Valor Total']
                        
                    else:
                        # Para outras métricas
                        df_estados = df_mapa_clean.groupby(uf_col).agg({
                            valor_col: ['sum', 'count', 'mean']
                        }).reset_index()
                        
                        # Flatten column names
                        df_estados.columns = ['UF', 'Total', 'Quantidade', 'Média']
                        
                        # Ordenar por total decrescente
                        df_estados = df_estados.sort_values('Total', ascending=False)
                        
                        # Formatação brasileira
                        df_estados_display = df_estados.copy()
                        if valor_col != 'count_clientes':
                            df_estados_display['Total'] = df_estados_display['Total'].apply(format_currency)
                            df_estados_display['Média'] = df_estados_display['Média'].apply(format_currency)
                        else:
                            df_estados_display['Total'] = df_estados_display['Total'].apply(lambda x: f"{x:,}")
                            df_estados_display['Média'] = df_estados_display['Média'].apply(lambda x: f"{x:.1f}")
                        df_estados_display['Quantidade'] = df_estados_display['Quantidade'].apply(lambda x: f"{x:,}")
                        df_estados_display.columns = ['🏛️ Estado', '💰 Total', '👥 Clientes', '📊 Média']
                    
                    # Mostrar top 10 estados
                    st.dataframe(df_estados_display.head(10), width='stretch', hide_index=True)
                    
                    # Mostrar métricas resumo
                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    
                    with col_m1:
                        total_estados = len(df_estados)
                        st.metric("🏛️ Estados com Dados", total_estados)
                    
                    with col_m2:
                        total_clientes = df_estados['Quantidade'].sum()
                        st.metric("👥 Total de Clientes", f"{total_clientes:,}")
                    
                    with col_m3:
                        if valor_col == 'Variacao_Percentual':
                            media_variacao = df_mapa_clean[valor_col].mean()
                            st.metric("📈 Variação Média", f"{media_variacao:.1f}%")
                        else:
                            valor_total = df_mapa_clean[valor_col].sum()
                            if valor_col != 'count_clientes':
                                st.metric("💰 Valor Total", format_currency(valor_total))
                            else:
                                st.metric("💰 Total Geral", f"{valor_total:,}")
                    
                    with col_m4:
                        # Estado com maior valor
                        estado_top = df_estados.iloc[0]['UF'] if not df_estados.empty else "N/A"
                        st.metric("🏆 Estado Líder", estado_top)
                    
                    # Filtro por estado selecionado
                    if 'df_estados' in locals() and not df_estados.empty:
                        st.markdown("---")
                        st.markdown("#### 🔍 Detalhes por Estado")
                        
                        uf_selecionado = st.selectbox(
                            "Selecione um estado para ver detalhes dos clientes:",
                            options=["Selecione um estado..."] + df_estados['UF'].tolist(),
                            key="uf_filtro"
                        )
                        
                        if uf_selecionado != "Selecione um estado...":
                            st.markdown(f"##### 📋 Detalhes - {uf_selecionado}")
                            
                            # Filtrar dados do período selecionado pelo estado
                            if periodo_mapa.startswith("Período A"):
                                df_filtrado = df_a[df_a[uf_col] == uf_selecionado].copy()
                                colunas_exibir = [nome_col, doc_cliente_col, devido_col, compras_col]
                            elif periodo_mapa.startswith("Período B"):
                                df_filtrado = df_b[df_b[uf_col] == uf_selecionado].copy()
                                colunas_exibir = [nome_col, doc_cliente_col, devido_col, compras_col]
                            else:  # Comparativo
                                df_filtrado = df_comparativo[df_comparativo[uf_col] == uf_selecionado].copy()
                                colunas_exibir = [nome_col, doc_cliente_col, f'{devido_col}_A', f'{devido_col}_B', 
                                                'Diferenca_Divida', 'Variacao_Percentual']
                            
                            if not df_filtrado.empty:
                                # Preparar dados para exibição
                                df_filtrado_display = df_filtrado[colunas_exibir].copy()
                                
                                # Aplicar formatação brasileira
                                for col in df_filtrado_display.columns:
                                    if 'vlr_' in col or 'Diferenca' in col or devido_col in col or compras_col in col:
                                        df_filtrado_display[col] = df_filtrado_display[col].apply(format_currency)
                                    elif 'Variacao' in col:
                                        df_filtrado_display[col] = df_filtrado_display[col].apply(lambda x: f"{x:.1f}%")
                                
                                # Renomear colunas para melhor apresentação
                                if periodo_mapa.startswith("🔄"):
                                    df_filtrado_display.columns = [
                                        '👤 Cliente', '📄 CPF/CNPJ', 
                                        f'💰 Dívida {date_a.strftime("%d/%m")}',
                                        f'💰 Dívida {date_b.strftime("%d/%m")}',
                                        '📈 Diferença', '📊 Variação %'
                                    ]
                                else:
                                    df_filtrado_display.columns = [
                                        '👤 Cliente', '📄 CPF/CNPJ', '💰 Dívida', '🛒 Compras'
                                    ]
                                
                                # Ordenar por valor mais alto
                                if periodo_mapa.startswith("🔄"):
                                    df_filtrado = df_filtrado.reindex(
                                        df_filtrado['Diferenca_Divida'].abs().sort_values(ascending=False).index
                                    )
                                    df_filtrado_display = df_filtrado_display.reindex(df_filtrado.index)
                                else:
                                    col_sort = devido_col if "Maior Dívida" in metrica_mapa else compras_col
                                    df_filtrado = df_filtrado.nlargest(20, col_sort)
                                    df_filtrado_display = df_filtrado_display.reindex(df_filtrado.index)
                                
                                st.dataframe(df_filtrado_display.head(20), width='stretch', hide_index=True)
                                
                                # Estatísticas do estado
                                total_clientes = len(df_filtrado)
                                
                                if periodo_mapa.startswith("🔄"):
                                    total_diferenca = df_filtrado['Diferenca_Divida'].sum()
                                    variacao_media = df_filtrado['Variacao_Percentual'].mean()
                                    
                                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                                    with col_stat1:
                                        st.metric("👥 Total de Clientes", f"{total_clientes:,}")
                                    with col_stat2:
                                        st.metric("💰 Diferença Total", format_currency(total_diferenca))
                                    with col_stat3:
                                        st.metric("📊 Variação Média", f"{variacao_media:.1f}%")
                                        
                                else:
                                    if "Maior Dívida" in metrica_mapa:
                                        total_valor = df_filtrado[devido_col].sum()
                                        media_valor = df_filtrado[devido_col].mean()
                                    else:
                                        total_valor = df_filtrado[compras_col].sum()
                                        media_valor = df_filtrado[compras_col].mean()
                                    
                                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                                    with col_stat1:
                                        st.metric("👥 Total de Clientes", f"{total_clientes:,}")
                                    with col_stat2:
                                        st.metric("� Valor Total", format_currency(total_valor))
                                    with col_stat3:
                                        st.metric("📊 Valor Médio", format_currency(media_valor))
                            else:
                                st.info(f"Nenhum cliente encontrado em {uf_selecionado} para o período selecionado.")
                else:
                    st.error("Erro ao criar o mapa. Verifique se o arquivo brasil_estados.json existe.")
            else:
                st.info("Nenhum dado válido com UF encontrado para o período selecionado.")
        else:
            st.info("Selecione um período com dados disponíveis para visualizar o mapa.")
    
    with tab4:
        st.markdown("### 📋 Dados Detalhados por Período")
        
        period_tab1, period_tab2 = st.tabs([f"📅 {date_a.strftime('%d/%m/%Y')}", f"📅 {date_b.strftime('%d/%m/%Y')}"])
        
        with period_tab1:
            if not df_a.empty:
                st.markdown(f"**Total de registros:** {len(df_a):,}")
                
                # Preparar dados para exibição com formatação brasileira
                df_a_display = df_a.copy()
                df_a_display[devido_col] = df_a_display[devido_col].apply(format_currency)
                df_a_display[compras_col] = df_a_display[compras_col].apply(format_currency)
                
                st.dataframe(df_a_display, width='stretch')
            else:
                st.info("Nenhum dado disponível para este período.")
        
        with period_tab2:
            if not df_b.empty:
                st.markdown(f"**Total de registros:** {len(df_b):,}")
                
                # Preparar dados para exibição com formatação brasileira
                df_b_display = df_b.copy()
                df_b_display[devido_col] = df_b_display[devido_col].apply(format_currency)
                df_b_display[compras_col] = df_b_display[compras_col].apply(format_currency)
                
                st.dataframe(df_b_display, width='stretch')
            else:
                st.info("Nenhum dado disponível para este período.")
    
    with tab5:
        st.markdown("### 📤 Exportar Relatórios")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Exportar para Excel", type="primary"):
                if not df_comparativo.empty:
                    output = io.BytesIO()
                    
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        # Dados comparativos
                        df_export = df_comparativo.copy()
                        df_export.to_excel(writer, sheet_name='Comparativo', index=False)
                        
                        # Dados período A
                        if not df_a.empty:
                            df_a.to_excel(writer, sheet_name=f'Periodo_A_{date_a.strftime("%Y%m%d")}', index=False)
                        
                        # Dados período B
                        if not df_b.empty:
                            df_b.to_excel(writer, sheet_name=f'Periodo_B_{date_b.strftime("%Y%m%d")}', index=False)
                    
                    output.seek(0)
                    
                    st.download_button(
                        label="⬬ Baixar Excel",
                        data=output,
                        file_name=f"relatorio_financeiro_{date_a.strftime('%Y%m%d')}_vs_{date_b.strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.success("✅ Arquivo Excel gerado com sucesso!")
                else:
                    st.warning("⚠️ Nenhum dado disponível para exportação.")
        
        with col2:
            if st.button("📄 Exportar para CSV"):
                if not df_comparativo.empty:
                    csv = df_comparativo.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    
                    st.download_button(
                        label="⬬ Baixar CSV",
                        data=csv,
                        file_name=f"relatorio_financeiro_{date_a.strftime('%Y%m%d')}_vs_{date_b.strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                    st.success("✅ Arquivo CSV gerado com sucesso!")
                else:
                    st.warning("⚠️ Nenhum dado disponível para exportação.")

if __name__ == "__main__":
    main()