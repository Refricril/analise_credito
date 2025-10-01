# 🚀 Guia de Deploy - Sistema de Análise Financeira

## 📋 **Opções de Deploy**

### ⚡ **1. Streamlit Cloud (Recomendado)**

#### **Vantagens**
- ✅ Deploy gratuito e automático
- ✅ Integração direta com GitHub
- ✅ HTTPS automático
- ✅ Escalabilidade automática

#### **Passo a Passo**
1. **Acesse**: https://streamlit.io/cloud
2. **Conecte sua conta GitHub**
3. **Selecione o repositório**: `Refricril/analise_credito`
4. **Configure**:
   - **Main file path**: `streamlit_app.py`
   - **Python version**: 3.9
5. **Adicione secrets** em `Settings > Secrets`:
```toml
[secrets]
DB_HOST = "seu_host"
DB_PORT = "5432"
DB_NAME = "seu_banco"
DB_USER = "seu_usuario"
DB_PASSWORD = "sua_senha"
ADMIN_PASS = "admin123"
FINANCEIRO_PASS = "fin123"
```
6. **Deploy automático** ✅

### 🐳 **2. Docker**

#### **Dockerfile**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicação
COPY . .

# Expor porta
EXPOSE 8501

# Comando de inicialização
CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0"]
```

#### **docker-compose.yml**
```yaml
version: '3.8'
services:
  analise-financeira:
    build: .
    ports:
      - "8501:8501"
    environment:
      - DB_HOST=${DB_HOST}
      - DB_PORT=${DB_PORT}
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - ADMIN_PASS=${ADMIN_PASS}
      - FINANCEIRO_PASS=${FINANCEIRO_PASS}
    volumes:
      - ./.env:/app/.env
```

#### **Comandos**
```bash
# Build
docker build -t analise-financeira .

# Run
docker run -p 8501:8501 --env-file .env analise-financeira

# Docker Compose
docker-compose up -d
```

### ☁️ **3. Heroku**

#### **Procfile**
```
web: streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
```

#### **runtime.txt**
```
python-3.9.20
```

#### **Comandos**
```bash
# Instalar Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# Login
heroku login

# Criar app
heroku create sua-app-name

# Configurar variáveis
heroku config:set DB_HOST=seu_host
heroku config:set DB_PORT=5432
heroku config:set DB_NAME=seu_banco
heroku config:set DB_USER=seu_usuario
heroku config:set DB_PASSWORD=sua_senha
heroku config:set ADMIN_PASS=admin123
heroku config:set FINANCEIRO_PASS=fin123

# Deploy
git push heroku main
```

### 🌐 **4. VPS/Servidor Próprio**

#### **Nginx + Gunicorn (Para Flask)**
```nginx
server {
    listen 80;
    server_name seu-dominio.com;

    location / {
        proxy_pass http://127.0.0.1:5503;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### **Systemd Service**
```ini
[Unit]
Description=Analise Financeira Flask App
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/analise_credito
Environment=PATH=/var/www/analise_credito/venv/bin
ExecStart=/var/www/analise_credito/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

#### **Para Streamlit**
```bash
# Screen/tmux
screen -S analise_financeira
streamlit run streamlit_app.py --server.port 8501

# PM2
npm install -g pm2
pm2 start "streamlit run streamlit_app.py" --name analise_financeira
pm2 startup
pm2 save
```

## 🔒 **Configurações de Segurança**

### **Variáveis de Ambiente Obrigatórias**
```bash
# Banco de dados
DB_HOST=
DB_PORT=5432
DB_NAME=
DB_USER=
DB_PASSWORD=

# Autenticação (ALTERAR EM PRODUÇÃO!)
ADMIN_PASS=
FINANCEIRO_PASS=

# Segurança
SECRET_KEY=  # Para Flask apenas
```

### **Firewall**
```bash
# Streamlit
ufw allow 8501

# Flask
ufw allow 5503
```

### **HTTPS**
```bash
# Certbot (Let's Encrypt)
sudo apt install certbot
sudo certbot --nginx -d seu-dominio.com
```

## 📊 **Monitoramento**

### **Logs**
```bash
# Streamlit Cloud
# Logs automáticos no dashboard

# Docker
docker logs -f container_name

# PM2
pm2 logs analise_financeira

# Systemd
journalctl -u analise_financeira -f
```

### **Métricas**
- **CPU**: Monitorar uso durante análises
- **Memória**: Especialmente com grandes datasets
- **Conexões DB**: Pool de conexões PostgreSQL
- **Response Time**: Tempo de resposta das queries

## 🔧 **Troubleshooting**

### **Erro de Conexão com Banco**
```bash
# Testar conexão
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME

# Verificar firewall
telnet $DB_HOST $DB_PORT
```

### **Erro de Memória**
```bash
# Aumentar limite Docker
docker run --memory=2g analise-financeira

# Otimizar queries
# Adicionar LIMIT nas queries de teste
```

### **Erro de Dependências**
```bash
# Atualizar pip
pip install --upgrade pip

# Reinstalar requirements
pip install -r requirements.txt --force-reinstall
```

## 📈 **Escalabilidade**

### **Horizontal**
- Load Balancer (nginx)
- Múltiplas instâncias
- Cache Redis compartilhado

### **Vertical**
- Mais CPU para processamento
- Mais RAM para datasets grandes
- SSD para velocidade de I/O

### **Database**
- Read replicas PostgreSQL
- Connection pooling
- Query optimization

## 🎯 **Recomendações de Deploy**

### **Desenvolvimento**
```bash
# Local
streamlit run streamlit_app.py
```

### **Teste**
```bash
# Streamlit Cloud (branch develop)
# Deploy automático em commits
```

### **Produção**
```bash
# Streamlit Cloud (branch main)
# OU Docker em VPS
# OU Heroku para simplicidade
```

---

**💡 Dica**: Para deploy corporativo, recomendamos **Streamlit Cloud** pela simplicidade e **Docker** para controle total.