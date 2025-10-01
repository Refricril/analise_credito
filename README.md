# 📊 Sistema de Análise Financeira - Refricril

Sistema completo de análise financeira desenvolvido em **Python** com interfaces **Flask** e **Streamlit** para análise comparativa de dados de crédito e inadimplência.

## 🚀 Funcionalidades Principais

### 📈 **Dashboard Interativo**
- **Análise Comparativa**: Compare dados entre diferentes períodos
- **Visualizações Avançadas**: Gráficos interativos com Plotly
- **Métricas Executivas**: Cards informativos com KPIs principais
- **Exportação**: Download em Excel e CSV

### 🔍 **Análises Disponíveis**
- **Variações de Dívida**: Maiores aumentos e reduções por cliente
- **Top Compradores**: Ranking dos maiores compradores por período  
- **Dados Transacionais**: Detalhamento completo de documentos
- **Estatísticas Consolidadas**: Totais e percentuais de variação

### 🛠️ **Duas Interfaces Disponíveis**

#### 🌐 **Flask** (Versão Web Tradicional)
- Interface web completa com HTML/CSS/JavaScript
- APIs REST para integração
- Sistema de autenticação robusto
- Rate limiting e segurança avançada

#### ⚡ **Streamlit** (Versão Moderna - Recomendada)
- Interface moderna e responsiva
- Desenvolvimento 10x mais rápido
- Gráficos interativos nativos
- Cache automático para performance

## 📋 **Requisitos**

- **Python 3.8+**
- **PostgreSQL**
- **Bibliotecas**: pandas, streamlit, flask, plotly, psycopg2

## 🔧 **Instalação**

### 1. **Clone o Repositório**
```bash
git clone https://github.com/Refricril/analise_credito.git
cd analise_credito
```

### 2. **Instale as Dependências**
```bash
pip install -r requirements.txt
```

### 3. **Configure as Variáveis de Ambiente**
```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite o arquivo .env com suas configurações
```

**Configurações necessárias no `.env`:**
```env
# Banco de Dados
DB_HOST=seu_host
DB_PORT=5432
DB_NAME=seu_banco
DB_USER=seu_usuario
DB_PASSWORD=sua_senha

# Credenciais
ADMIN_PASS=sua_senha_admin
FINANCEIRO_PASS=sua_senha_financeiro

# Segurança
SECRET_KEY=sua_chave_secreta
```

## 🚀 **Execução**

### ⚡ **Streamlit (Recomendado)**
```bash
streamlit run streamlit_app.py
```
**Acesse**: http://localhost:8501

### 🌐 **Flask (Tradicional)**
```bash
python main.py
```
**Acesse**: http://localhost:5503

## 👤 **Credenciais Padrão**

| Usuário | Senha | Permissões |
|---------|-------|------------|
| `admin` | `admin123` | Administrador |
| `financeiro` | `fin123` | Financeiro |

> ⚠️ **Importante**: Altere as senhas padrão em produção!

## 📊 **Estrutura do Projeto**

```
analise_credito/
├── 📁 .streamlit/          # Configurações do Streamlit
├── 📁 flask_session/       # Sessões do Flask (auto-gerado)
├── 📁 static/              # Arquivos estáticos (CSS, JS, imagens)
├── 📁 templates/           # Templates HTML do Flask
├── 📄 main.py              # Aplicação Flask principal
├── 📄 streamlit_app.py     # Aplicação Streamlit (RECOMENDADA)
├── 📄 query.sql            # Query SQL principal
├── 📄 requirements.txt     # Dependências Python
├── 📄 .env.example         # Exemplo de configurações
└── 📄 README.md            # Este arquivo
```

## 🎯 **Como Usar**

### 1. **Login no Sistema**
- Acesse a aplicação no navegador
- Use as credenciais padrão ou configuradas

### 2. **Configurar Análise**
- Selecione as **datas de posição** A e B
- Clique em **"Gerar Análise"**

### 3. **Explorar Resultados**
- **📊 Variações**: Gráfico das maiores mudanças
- **🛒 Compradores**: Comparação de top compradores  
- **📋 Dados Detalhados**: Tabelas completas
- **📤 Exportar**: Download dos relatórios

## 📈 **Análises Disponíveis**

### **Variações de Dívida**
- Maiores aumentos e reduções de dívida por cliente
- Cálculo automático de percentuais de variação
- Visualização em gráfico horizontal interativo

### **Top Compradores**
- Ranking dos 10 maiores compradores por período
- Comparação visual lado a lado
- Identificação de tendências de compra

### **Métricas Executivas**
- Total de clientes analisados
- Quantidade de aumentos vs reduções
- Variação total consolidada

## 🔒 **Segurança**

### **Autenticação**
- Sistema de login com sessões
- Validação de credenciais
- Timeout automático de sessão

### **Banco de Dados**
- Conexões em modo somente-leitura
- Timeout de conexão configurável
- Validação de parâmetros SQL

### **Rate Limiting**
- Limite de tentativas de login
- Proteção contra ataques DDoS
- Logs de segurança detalhados

## ⚡ **Performance**

### **Cache Inteligente**
- Cache automático de consultas (5 min)
- Conexões otimizadas com pool
- Processamento assíncrono

### **Otimizações**
- Agregação de dados por cliente
- Processamento vetorizado com pandas
- Compressão de dados para export

## 🆚 **Comparação: Streamlit vs Flask**

| Aspecto | Flask | Streamlit |
|---------|-------|-----------|
| **Desenvolvimento** | ⏱️ Semanas | ⚡ Horas |
| **Interface** | 🔧 HTML/CSS Manual | 🎨 Automática |
| **Gráficos** | 📊 Plotly + JavaScript | 📈 Plotly Nativo |
| **Responsividade** | 📱 CSS Customizado | 📲 Automática |
| **Cache** | 🔄 Manual | 🚀 Automático |
| **Deploy** | 🛠️ Complexo | ☁️ Simples |
| **Manutenção** | 🔧 Alta | ✅ Baixa |

## 📤 **Exportação de Dados**

### **Formatos Suportados**
- **Excel (.xlsx)**: Múltiplas planilhas com formatação
- **CSV**: Separado por ponto-e-vírgula, UTF-8

### **Conteúdo dos Relatórios**
- Dados comparativos entre períodos
- Variações calculadas automaticamente
- Documentos e datas de emissão
- Formatação monetária brasileira

## 🚀 **Deploy em Produção**

### **Streamlit Cloud**
```bash
# Configure secrets no Streamlit Cloud
# Upload do projeto via GitHub
# Deploy automático
```

### **Docker**
```dockerfile
FROM python:3.9
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["streamlit", "run", "streamlit_app.py"]
```

### **Heroku**
```bash
# Configure buildpack Python
# Adicione Procfile: web: streamlit run streamlit_app.py
# Configure variáveis de ambiente
```

## 🔧 **Troubleshooting**

### **Erro de Conexão com Banco**
- Verifique as configurações no `.env`
- Confirme se o PostgreSQL está acessível
- Teste a conexão manualmente

### **Dados Não Aparecem**
- Verifique se existem dados nas datas selecionadas
- Confirme a query SQL no arquivo `query.sql`
- Use o modo debug para mais informações

### **Performance Lenta**
- Verifique índices no banco de dados
- Ajuste o timeout de conexão
- Use períodos menores de análise

## 📞 **Suporte**

- **Repositório**: https://github.com/Refricril/analise_credito
- **Issues**: Para reportar bugs ou solicitar features
- **Docs**: Documentação completa no README

## 📄 **Licença**

Este projeto é propriedade da **Refricril** e destinado ao uso interno da empresa.

---

**Desenvolvido com ❤️ pela equipe Refricril**