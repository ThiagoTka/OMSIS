# 🔧 Configuração GCP Cloud Run com Cloud SQL

## ⚠️ IMPORTANTE: Variáveis de Ambiente

O `cloudbuild.yaml` foi atualizado para passar as variáveis de ambiente corretas. **Mas você precisa configurar as variáveis de ambiente no Cloud Build** usando **Google Cloud Secret Manager**.

## 📋 Pré-requisitos

- Projeto GCP criado: `imsis-486003`
- Cloud SQL Database: `imsis-db` na região `us-central1`
- Cloud Build configurado para este repositório

## 🔐 Passo 1: Criar Secrets no GCP

### No Google Cloud Console, execute estes comandos:

⚠️ **IMPORTANTE**: Substitua `SUA_SENHA_AQUI` e `SUA_CHAVE_SECRETA` pelas suas credenciais reais!

```bash
# Criar secret para DB_PASS
echo -n "SUA_SENHA_AQUI" | gcloud secrets create db-pass --data-file=-

# Criar secret para SECRET_KEY
echo -n "SUA_CHAVE_SECRETA" | gcloud secrets create secret-key --data-file=-

# Criar secrets SMTP
echo -n "smtp.hostinger.com" | gcloud secrets create smtp-host --data-file=-
echo -n "465" | gcloud secrets create smtp-port --data-file=-
echo -n "accounts@imsis.com.br" | gcloud secrets create smtp-user --data-file=-
echo -n "SUA_SENHA_SMTP" | gcloud secrets create smtp-pass --data-file=-
echo -n "accounts@imsis.com.br" | gcloud secrets create smtp-from --data-file=-
```

Ou via Google Cloud Console:
1. Vá para **Security** → **Secret Manager**
2. Clique em **Create Secret**
3. Nome: `db-pass`, Valor: `[sua senha do banco de dados]`
4. Nome: `secret-key`, Valor: `[sua chave secreta da aplicação]`

**Dica**: Use o script `setup_gcp_secrets.sh` (bash) ou `setup_gcp_secrets.ps1` (PowerShell) que carrega automaticamente do arquivo `.env`

## 📝 Passo 2: Atualizar cloudbuild.yaml com Secrets

O arquivo já foi atualizado, mas aqui está o padrão correto:

```yaml
--set-env-vars=DB_USER=imsis_user,DB_NAME=imsis,CLOUD_SQL_CONNECTION_NAME=imsis-486003:us-central1:imsis-db,GCP_PROJECT=imsis-486003,APP_BASE_URL=https://imsis.com.br
--update-secrets=DB_PASS=db-pass:latest,SECRET_KEY=secret-key:latest,SMTP_HOST=smtp-host:latest,SMTP_PORT=smtp-port:latest,SMTP_USER=smtp-user:latest,SMTP_PASS=smtp-pass:latest,SMTP_FROM=smtp-from:latest
```

## 🚀 Passo 3: Deploy

Após criar os secrets, faça o deployment:

```bash
git add .
git commit -m "feat: Update Cloud Run configuration with secrets"
git push
```

Cloud Build será acionado automaticamente.

## ✅ Verificar o Deploy

1. Vá para **Cloud Run** → `app`
2. Verifique as **Variáveis de Ambiente**
3. Verifique as **Conexões de Secrets**
4. Clique na URL para testar

## 🔍 Verificar Logs

Se houver erro, veja os logs:

```bash
gcloud run logs read app --region us-central1
```

## 📌 Variáveis de Ambiente Configuradas

| Variável | Valor | Fonte |
|----------|-------|-------|
| `GCP_PROJECT` | imsis-486003 | plaintext |
| `DB_USER` | imsis_user | plaintext |
| `DB_NAME` | imsis | plaintext |
| `CLOUD_SQL_CONNECTION_NAME` | imsis-486003:us-central1:imsis-db | plaintext |
| `DB_PASS` | (secret) | Secret Manager |
| `SECRET_KEY` | (secret) | Secret Manager |
| `SMTP_HOST` | (secret) | Secret Manager |
| `SMTP_PORT` | (secret) | Secret Manager |
| `SMTP_USER` | (secret) | Secret Manager |
| `SMTP_PASS` | (secret) | Secret Manager |
| `SMTP_FROM` | (secret) | Secret Manager |

## 🔗 Conexão Cloud SQL

O Cloud Run esta configurado com:
- `--cloudsql-instances imsis-486003:us-central1:imsis-db`
- Conecta automaticamente via Unix socket `/cloudsql/`

## 🐍 Como app.py Usa Isso

```python
# app.py detecta automaticamente Cloud SQL:
db_user = os.environ.get("DB_USER")           # imsis_user
db_pass = os.environ.get("DB_PASS")           # [carregado do Secret Manager]
db_name = os.environ.get("DB_NAME")           # imsis
cloud_sql = os.environ.get("CLOUD_SQL_CONNECTION_NAME")  # imsis-486003:us-central1:imsis-db

# Conexão string: postgresql+psycopg2://user:pass@/dbname?host=/cloudsql/CONNECTION_NAME
```

## 🆘 Troubleshooting

### Erro: "Connection refused"
- Certifique-se que Cloud SQL Connector está ativado
- Verifique permissões IAM do Cloud Run service account

### Erro: "Unknown database"
- Verifique se database `imsis` existe em Cloud SQL
- Se não, o app.py criará as tabelas automaticamente

### Erro: "Auth failed for user imsis_user"
- Verifique a senha em Secret Manager
- Certifique-se que o usuário existe em Cloud SQL

## 📚 Referências

- [Cloud Run + Cloud SQL](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-service)
- [Secret Manager](https://cloud.google.com/secret-manager/docs)
- [Cloud Build](https://cloud.google.com/build/docs)
