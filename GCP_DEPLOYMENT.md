# Deploy IMSIS no Google Cloud Platform (GCP)

## Visão Geral

Este guia explica como fazer deploy da aplicação Flask no **Google Cloud Run** com banco de dados persistente via **Cloud SQL (PostgreSQL)**.

---

## Pré-requisitos

1. Conta Google Cloud ativa
2. Google Cloud SDK instalado localmente
3. Projeto GCP criado
4. Docker instalado (para testar builds localmente)

---

## Passo 1: Criar Cloud SQL Instance (PostgreSQL)

### Via Console GCP
1. Acesse [Cloud SQL](https://console.cloud.google.com/sql)
2. Clique em **Create Instance** → **PostgreSQL**
3. Configure:
   - **Instance ID**: `imsis-db`
   - **Password**: gere uma senha segura
   - **Database version**: PostgreSQL 15+
   - **Machine type**: db-f1-micro (gratuito para teste)
   - **Region**: escolha a mais próxima

4. Clique **Create Instance** e aguarde a inicialização

### Via gcloud CLI
```bash
gcloud sql instances create imsis-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --root-password=sua-senha-segura
```

---

## Passo 2: Criar Banco de Dados

### Via Console
1. Na instância criada, clique em **Databases**
2. Clique **Create Database**
3. Nome: `imsis`

### Via gcloud CLI
```bash
gcloud sql databases create imsis \
  --instance=imsis-db
```

---

## Passo 3: Criar Usuário do Banco

### Via Console
1. Na instância, clique em **Users**
2. Clique **Create User**
3. Configure:
   - **Username**: `imsis_user`
   - **Password**: gere uma senha segura

### Via gcloud CLI
```bash
gcloud sql users create imsis_user \
  --instance=imsis-db \
  --password=sua-senha-segura
```

---

## Passo 4: Coletar Informações de Conexão

Execute:
```bash
gcloud sql instances describe imsis-db --format='value(connectionName)'
```

Salve o resultado, será algo como: `seu-projeto:us-central1:imsis-db`

---

## Passo 5: Preparar Aplicação para Cloud Run

### Atualizar requirements.txt
Adicione o driver PostgreSQL:
```bash
pip install psycopg2-binary
echo "psycopg2-binary==2.9.9" >> requirements.txt
```

### Criar arquivo .env.example (referência)
```
SECRET_KEY=sua-chave-secreta-super-segura
DB_USER=imsis_user
DB_PASS=sua-senha-do-banco
DB_NAME=imsis
CLOUD_SQL_CONNECTION_NAME=seu-projeto:us-central1:imsis-db
```

---

## Passo 6: Deploy no Cloud Run

### Opção A: Usar gcloud CLI (Recomendado)

1. Faça login:
```bash
gcloud auth login
gcloud config set project seu-projeto-id
```

2. Configure as variáveis de ambiente:
```bash
gcloud run deploy imsis \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars=\
DB_USER=imsis_user,\
DB_PASS=sua-senha-do-banco,\
DB_NAME=imsis,\
CLOUD_SQL_CONNECTION_NAME=seu-projeto:us-central1:imsis-db,\
SECRET_KEY=sua-chave-secreta-super-segura \
  --add-cloudsql-instances seu-projeto:us-central1:imsis-db
```

3. Aguarde até que apareça a URL pública

---

## Passo 7: Inicializar Banco de Dados (Primeira vez)

Após o deploy, execute:
```python
from app import app, criar_tabelas_e_dados

with app.app_context():
    criar_tabelas_e_dados()
    print("Tabelas criadas com sucesso!")
```

Ou acesse a rota `/reset` uma vez (se habilitada) para criar as tabelas padrão.

---

## Estrutura de Variáveis de Ambiente

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DATABASE_URL` | URL completa do banco | `postgresql://user:pass@host/db` |
| `DB_USER` | Usuário PostgreSQL | `imsis_user` |
| `DB_PASS` | Senha PostgreSQL | `abc123xyz` |
| `DB_NAME` | Nome do banco | `imsis` |
| `CLOUD_SQL_CONNECTION_NAME` | Connection string do Cloud SQL | `projeto:region:instance` |
| `SECRET_KEY` | Chave secreta Flask | `chave-aleatoria-segura` |

---

## Troubleshooting

### Erro: "Cannot connect to database"
- Verifique se a Cloud SQL Instance está rodando
- Confirme que o Cloud Run tem permissão de conectar via `--add-cloudsql-instances`

### Erro: "permission denied for schema public"
- Verifique credenciais do usuário do banco

### Dados desaparecem após redeploy
- Confirme que está usando PostgreSQL/Cloud SQL (não SQLite)
- Verifique `CLOUD_SQL_CONNECTION_NAME` está configurado

---

## Segurança (Importante!)

⚠️ **Nunca** commite senhas no Git:
```bash
# Adicione ao .gitignore
.env
.env.local
```

Use **Google Secret Manager** para credenciais:
```bash
echo "sua-senha" | gcloud secrets create imsis-db-pass --data-file=-

# Depois configure no Cloud Run:
gcloud run deploy imsis \
  --set-secrets DB_PASS=imsis-db-pass:latest \
  ...
```

---

## Monitoramento

Acesse os logs:
```bash
gcloud run logs read imsis --region us-central1 --limit 50
```

---

## Próximos Passos

- [ ] Configurar domínio personalizado
- [ ] Habilitar HTTPS (Cloud Run já fornece)
- [ ] Backup automático do banco via Cloud SQL
- [ ] Implementar validação de e-mail (seu próximo TODO)
