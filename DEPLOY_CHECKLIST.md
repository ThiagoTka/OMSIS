# 🚀 Checklist de Deploy GCP - IMSIS

## Antes de Fazer o Deploy

### 1. ⚠️ CRÍTICO: Secrets e Segurança
```bash
# Crie o arquivo .env LOCAL (nunca commitar!)
cat > .env << EOF
DB_PASS=sua_senha_forte_aqui
SECRET_KEY=sua_chave_secreta_aqui
APP_BASE_URL=https://imsis.com.br
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=465
SMTP_USER=accounts@imsis.com.br
SMTP_PASS=sua_senha_smtp_aqui
SMTP_FROM=accounts@imsis.com.br
SMTP_USE_SSL=true
SMTP_USE_TLS=false
EOF

# Execute o script de setup
# Linux/macOS (bash)
bash setup_gcp_secrets.sh

# Windows (PowerShell)
./setup_gcp_secrets.ps1
```
- [ ] Arquivo `.env` criado localmente
- [ ] Script `setup_gcp_secrets.sh` executado com sucesso
- [ ] Secrets verificados no GCP Console
- [ ] SMTP configurado (host, porta, user, pass, from)

### 2. 🗄️ Cloud SQL
```bash
# Verificar se existe
gcloud sql instances describe imsis-db --project=imsis-486003
```
- [ ] Instância Cloud SQL criada
- [ ] Banco de dados `imsis` criado
- [ ] Usuário `imsis_user` criado

### 3. 🔐 Permissões IAM
```bash
# Copie e execute os comandos do GCP_READINESS_REPORT.md seção "Configurar Permissões IAM"
```
- [ ] Service account tem acesso aos secrets
- [ ] Service account tem acesso ao Cloud SQL

### 4. 📝 Verificações Finais
- [ ] `.env` NÃO está no git (`git status` para confirmar)
- [ ] `cloudbuild.yaml` revisado
- [ ] Cloud Build trigger ativo (se usando CI/CD)

## Deploy

### Método 1: Automático via Git
```bash
git add .
git commit -m "deploy: Deploy no GCP"
git push origin main
```
- [ ] Push realizado
- [ ] Cloud Build iniciado
- [ ] Build concluído com sucesso

### Método 2: Manual
```bash
gcloud builds submit --tag gcr.io/imsis-486003/imsis
gcloud run deploy imsis --image gcr.io/imsis-486003/imsis ...
```
- [ ] Build manual concluído
- [ ] Deploy no Cloud Run concluído

## Pós-Deploy

### 1. 🔍 Verificar URL
```bash
gcloud run services describe imsis --region us-central1 --format='value(status.url)'
```
- [ ] URL obtida
- [ ] URL acessível no navegador

### 2. ✅ Testar Endpoints
```bash
# Health check
curl https://[URL]/health

# DB check
curl https://[URL]/db-check
```
- [ ] `/health` retorna 200
- [ ] `/db-check` retorna informações do banco
- [ ] Login funcionando
- [ ] Criação de projeto funcionando

### 3. 📊 Verificar Logs
```bash
gcloud run services logs tail imsis --region us-central1
```
- [ ] Logs mostram: "✅ Banco de dados inicializado com sucesso"
- [ ] Sem erros de conexão
- [ ] Tabelas criadas automaticamente

### 4. 🗄️ Verificar Banco de Dados
- [ ] Tabelas criadas (verificar logs)
- [ ] Perfis padrão criados (Administrador, Membro)
- [ ] Permissões configuradas corretamente

## Troubleshooting

### Erro de conexão ao banco?
1. Verificar nome da instância Cloud SQL no `cloudbuild.yaml`
2. Verificar que o secret `db-pass` está correto
3. Verificar permissões IAM

### Secrets não carregados?
1. Verificar que secrets existem no Secret Manager
2. Verificar IAM policy bindings
3. Verificar sintaxe no `cloudbuild.yaml`: `--set-secrets`

### Tabelas não criadas?
- Verificar logs: `gcloud run services logs read imsis --region us-central1`
- Deve aparecer mensagem "✅ Banco de dados inicializado com sucesso"

## 📚 Documentação de Referência

- [GCP_READINESS_REPORT.md](GCP_READINESS_REPORT.md) - Relatório completo de prontidão
- [GCP_SETUP.md](GCP_SETUP.md) - Guia detalhado de configuração
- [SECURITY.md](SECURITY.md) - Diretrizes de segurança
- [README.md](README.md) - Documentação geral do projeto

---

**Última atualização**: 15 de fevereiro de 2026
