# 📊 Dashboard Financeiro - Refricril (Streamlit)

## ✨ Funcionalidades Principais

### 🔐 Autenticação
- Login seguro com usuários pré-configurados
- Sessão gerenciada automaticamente pelo Streamlit

### 📊 Dashboard Interativo
- **Resumo Executivo**: Métricas principais em cards informativos
- **Análise de Variações**: Gráficos interativos com Plotly
- **Compradores**: Comparação visual dos maiores compradores
- **Dados Detalhados**: Tabelas completas por período
- **Exportação**: Download em Excel e CSV

### 🎨 Interface Moderna
- Design responsivo e profissional
- Gráficos interativos com Plotly
- Tabelas filtráveis e ordenáveis
- Cache inteligente para melhor performance

## 🚀 Como Executar

### 1. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 2. Executar Aplicação
```bash
streamlit run streamlit_app.py
```

### 3. Acessar Dashboard
Abra seu navegador em: **http://localhost:8501**

## 👤 Credenciais de Acesso

- **Admin**: admin / admin123
- **Financeiro**: financeiro / fin123

## 📋 Funcionalidades por Aba

### 📊 Variações
- Gráfico horizontal das maiores variações
- Tabela detalhada com formatação monetária
- Cálculo automático de percentuais

### 🛒 Compradores
- Gráficos comparativos lado a lado
- Top 10 maiores compradores por período
- Análise visual de tendências

### 📋 Dados Detalhados
- Visualização completa dos dados brutos
- Separação por períodos em sub-abas
- Formatação monetária automática

### 📤 Exportar
- Download direto em Excel (múltiplas planilhas)
- Exportação em CSV formatado
- Nomenclatura automática com datas

## 🔧 Configurações

### Banco de Dados
Configure as variáveis no arquivo `.env`:
- `DB_HOST`: Endereço do servidor
- `DB_PORT`: Porta de conexão
- `DB_NAME`: Nome do banco
- `DB_USER`: Usuário de acesso
- `DB_PASSWORD`: Senha de acesso

### Performance
- Cache automático por 5 minutos
- Conexões otimizadas com timeout
- Processamento assíncrono de dados

## 🆚 Vantagens do Streamlit vs Flask

### ✅ Streamlit
- Interface mais moderna e responsiva
- Gráficos interativos nativos
- Desenvolvimento mais rápido
- Cache inteligente automático
- Componentes pré-construídos
- Melhor experiência mobile

### ⚙️ Flask (Anterior)
- Controle total sobre HTML/CSS
- Arquitetura mais flexível
- APIs REST personalizadas
- Melhor para aplicações complexas

## 📈 Melhorias Implementadas

1. **UI/UX Modernas**: Interface muito mais atrativa
2. **Gráficos Interativos**: Plotly para visualizações avançadas
3. **Performance**: Cache e otimizações
4. **Responsividade**: Funciona bem em mobile
5. **Exportação Melhorada**: Downloads diretos no navegador
6. **Feedback Visual**: Loading spinners e mensagens claras
7. **Validações**: Verificações robustas de dados
8. **Logs Detalhados**: Monitoramento completo

## 🔍 Análises Disponíveis

- **Comparação de Períodos**: Análise temporal de dívidas
- **Top Compradores**: Identificação de clientes-chave
- **Variações de Dívida**: Aumentos e reduções detalhadas
- **Estatísticas Gerais**: Métricas consolidadas
- **Dados Transacionais**: Detalhamento completo

## 🛠️ Tecnologias Utilizadas

- **Streamlit**: Framework principal
- **Plotly**: Gráficos interativos
- **Pandas**: Manipulação de dados
- **PostgreSQL**: Banco de dados
- **Python**: Linguagem base