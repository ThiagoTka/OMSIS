# 🔧 Configuração GCP Cloud Run com Cloud SQL

## ⚠️ IMPORTANTE: Variáveis de Ambiente

O `cloudbuild.yaml` foi atualizado para passar as variáveis de ambiente corretas. **Mas você precisa configurar as variáveis de ambiente no Cloud Build** usando **Google Cloud Secret Manager**.

## 📋 Pré-requisitos

- Projeto GCP criado: `imsis-486003`
- Cloud SQL Database: `imsis-db` na região `us-central1`
- Cloud Build configurado para este repositório

## 🔐 Passo 1: Criar Secrets no GCP

### No Google Cloud Console, execute estes comandos:

```bash
# Criar secret para DB_PASS
echo -n "KHH5&efe%hrb@#" | gcloud secrets create db-pass --data-file=-

# Criar secret para SECRET_KEY
echo -n "KHH5&efe%hrb@#" | gcloud secrets create secret-key --data-file=-
```

Ou via Google Cloud Console:
1. Vá para **Security** → **Secret Manager**
2. Clique em **Create Secret**
3. Nome: `db-pass`, Valor: `KHH5&efe%hrb@#`
4. Nome: `secret-key`, Valor: `KHH5&efe%hrb@#`

## 📝 Passo 2: Atualizar cloudbuild.yaml com Secrets

O arquivo já foi atualizado, mas aqui está o padrão correto:

```yaml
--set-env-vars=DB_USER=imsis_user,DB_NAME=imsis,CLOUD_SQL_CONNECTION_NAME=imsis-486003:us-central1:imsis-db,GCP_PROJECT=imsis-486003
--update-secrets=DB_PASS=db-pass:latest,SECRET_KEY=secret-key:latest
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

## 🔗 Conexão Cloud SQL

O Cloud Run esta configurado com:
- `--cloudsql-instances imsis-486003:us-central1:imsis-db`
- Conecta automaticamente via Unix socket `/cloudsql/`

## 🐍 Como app.py Usa Isso

```python
# app.py detecta automaticamente Cloud SQL:
db_user = os.environ.get("DB_USER")           # imsis_user
db_pass = os.environ.get("DB_PASS")           # KHH5&efe%hrb@#
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
