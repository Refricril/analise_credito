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
        devido_col: 'sum',
        compras_col: 'sum'
    }).reset_index() if not df_a.empty else pd.DataFrame(columns=[id_col, nome_col, doc_cliente_col, devido_col, compras_col])
    
    df_b_grouped = df_b.groupby(id_col).agg({
        nome_col: 'first',
        doc_cliente_col: 'first',
        devido_col: 'sum',
        compras_col: 'sum'
    }).reset_index() if not df_b.empty else pd.DataFrame(columns=[id_col, nome_col, doc_cliente_col, devido_col, compras_col])
    
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
        for col in [f'{nome_col}_B', f'{doc_cliente_col}_B', f'{devido_col}_B', f'{compras_col}_B']:
            df_comparativo[col] = 0
    elif not df_b_grouped.empty:
        df_comparativo = df_b_grouped.copy()
        df_comparativo = df_comparativo.rename(columns={
            nome_col: f'{nome_col}_B',
            doc_cliente_col: f'{doc_cliente_col}_B',
            devido_col: f'{devido_col}_B',
            compras_col: f'{compras_col}_B'
        })
        for col in [f'{nome_col}_A', f'{doc_cliente_col}_A', f'{devido_col}_A', f'{compras_col}_A']:
            df_comparativo[col] = 0
    else:
        df_comparativo = pd.DataFrame()
    
    if not df_comparativo.empty:
        # Limpeza dos dados
        df_comparativo[nome_col] = df_comparativo.get(f'{nome_col}_A', '').fillna('').astype(str) + df_comparativo.get(f'{nome_col}_B', '').fillna('').astype(str)
        df_comparativo[doc_cliente_col] = df_comparativo.get(f'{doc_cliente_col}_A', '').fillna('').astype(str) + df_comparativo.get(f'{doc_cliente_col}_B', '').fillna('').astype(str)
        
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
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Variações", "🛒 Compradores", "📋 Dados Detalhados", "📤 Exportar"])
    
    with tab1:
        st.markdown("### 🔄 Maiores Variações de Dívida")
        
        if not df_comparativo.empty:
            df_variacao = df_comparativo[df_comparativo['Diferenca_Divida'] != 0].copy()
            df_variacao = df_variacao.sort_values('Diferenca_Divida', ascending=False)
            
            if not df_variacao.empty:
                # Gráfico
                fig = create_comparison_chart(df_variacao)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Tabela das variações
                st.markdown("#### 📋 Detalhes das Variações")
                
                # Preparar dados para exibição
                df_display = df_variacao[[
                    id_col, nome_col, doc_cliente_col,
                    f'{devido_col}_A', f'{devido_col}_B',
                    'Diferenca_Divida', 'Variacao_Percentual'
                ]].copy()
                
                # Formatação
                df_display[f'{devido_col}_A'] = df_display[f'{devido_col}_A'].apply(format_currency)
                df_display[f'{devido_col}_B'] = df_display[f'{devido_col}_B'].apply(format_currency)
                df_display['Diferenca_Divida'] = df_display['Diferenca_Divida'].apply(format_currency)
                df_display['Variacao_Percentual'] = df_display['Variacao_Percentual'].apply(lambda x: f"{x:.1f}%")
                
                # Renomear colunas
                df_display.columns = [
                    'Código', 'Cliente', 'CPF/CNPJ',
                    f'Dívida ({date_a.strftime("%d/%m/%Y")})',
                    f'Dívida ({date_b.strftime("%d/%m/%Y")})',
                    'Diferença', 'Variação %'
                ]
                
                st.dataframe(df_display, use_container_width=True)
            else:
                st.info("Nenhuma variação encontrada entre os períodos.")
        else:
            st.info("Nenhum dado disponível para comparação.")
    
    with tab2:
        st.markdown("### 🛒 Análise dos Maiores Compradores")
        
        if not df_a.empty or not df_b.empty:
            fig = create_top_buyers_chart(df_a, df_b, compras_col)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"#### 📅 Top 10 - {date_a.strftime('%d/%m/%Y')}")
                if not df_a.empty:
                    top_a = df_a.nlargest(10, compras_col)[[nome_col, compras_col]].copy()
                    top_a[compras_col] = top_a[compras_col].apply(format_currency)
                    top_a.columns = ['Cliente', 'Total Compras']
                    st.dataframe(top_a, use_container_width=True)
                else:
                    st.info("Sem dados para este período")
            
            with col2:
                st.markdown(f"#### 📅 Top 10 - {date_b.strftime('%d/%m/%Y')}")
                if not df_b.empty:
                    top_b = df_b.nlargest(10, compras_col)[[nome_col, compras_col]].copy()
                    top_b[compras_col] = top_b[compras_col].apply(format_currency)
                    top_b.columns = ['Cliente', 'Total Compras']
                    st.dataframe(top_b, use_container_width=True)
                else:
                    st.info("Sem dados para este período")
        else:
            st.info("Nenhum dado disponível para análise de compradores.")
    
    with tab3:
        st.markdown("### 📋 Dados Detalhados por Período")
        
        period_tab1, period_tab2 = st.tabs([f"📅 {date_a.strftime('%d/%m/%Y')}", f"📅 {date_b.strftime('%d/%m/%Y')}"])
        
        with period_tab1:
            if not df_a.empty:
                st.markdown(f"**Total de registros:** {len(df_a):,}")
                
                # Preparar dados para exibição
                df_a_display = df_a.copy()
                df_a_display[devido_col] = df_a_display[devido_col].apply(format_currency)
                df_a_display[compras_col] = df_a_display[compras_col].apply(format_currency)
                
                st.dataframe(df_a_display, use_container_width=True)
            else:
                st.info("Nenhum dado disponível para este período.")
        
        with period_tab2:
            if not df_b.empty:
                st.markdown(f"**Total de registros:** {len(df_b):,}")
                
                # Preparar dados para exibição
                df_b_display = df_b.copy()
                df_b_display[devido_col] = df_b_display[devido_col].apply(format_currency)
                df_b_display[compras_col] = df_b_display[compras_col].apply(format_currency)
                
                st.dataframe(df_b_display, use_container_width=True)
            else:
                st.info("Nenhum dado disponível para este período.")
    
    with tab4:
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