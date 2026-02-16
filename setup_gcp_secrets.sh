#!/bin/bash

# 🔐 Script para configurar Google Cloud Secrets para IMSIS

set -e  # Exit se houver erro

echo "🚀 Configurando Google Cloud Secrets para IMSIS..."
echo ""

# Verificar se gcloud está instalado
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI não encontrado. Instale em: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Verificar projeto GCP
PROJECT_ID="imsis-486003"
echo "📋 Verificando projeto: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# ⚠️  IMPORTANTE: Carregue as variáveis do arquivo .env (que NÃO deve estar no git)
if [ ! -f .env ]; then
    echo "❌ Arquivo .env não encontrado!"
    echo "   Crie um arquivo .env com:"
    echo "   DB_PASS=sua_senha_secreta"
    echo "   SECRET_KEY=sua_chave_secreta"
    echo "   SMTP_HOST=smtp.hostinger.com"
    echo "   SMTP_PORT=465"
    echo "   SMTP_USER=accounts@imsis.com.br"
    echo "   SMTP_PASS=sua_senha_smtp"
    echo "   SMTP_FROM=accounts@imsis.com.br"
    exit 1
fi

# Carregar variáveis do .env
export $(grep -v '^#' .env | xargs)

if [ -z "$DB_PASS" ] || [ -z "$SECRET_KEY" ]; then
    echo "❌ DB_PASS ou SECRET_KEY não encontrados no .env"
    exit 1
fi

if [ -z "$SMTP_HOST" ] || [ -z "$SMTP_PORT" ] || [ -z "$SMTP_USER" ] || [ -z "$SMTP_PASS" ] || [ -z "$SMTP_FROM" ]; then
    echo "❌ SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/SMTP_FROM não encontrados no .env"
    exit 1
fi

# Criar secrets
echo ""
echo "🔐 Criando secrets em Secret Manager..."
echo ""

# DB_PASS
echo "  1. Criando db-pass..."
if gcloud secrets describe db-pass --quiet 2>/dev/null; then
    echo "     ✓ db-pass já existe, atualizando..."
    echo -n "$DB_PASS" | gcloud secrets versions add db-pass --data-file=-
else
    echo "     Criando novo secret..."
    echo -n "$DB_PASS" | gcloud secrets create db-pass --data-file=- --replication-policy="automatic" --quiet
fi

# SECRET_KEY
echo "  2. Criando secret-key..."
if gcloud secrets describe secret-key --quiet 2>/dev/null; then
    echo "     ✓ secret-key já existe, atualizando..."
    echo -n "$SECRET_KEY" | gcloud secrets versions add secret-key --data-file=-
else
    echo "     Criando novo secret..."
    echo -n "$SECRET_KEY" | gcloud secrets create secret-key --data-file=- --replication-policy="automatic" --quiet
fi

# SMTP_HOST
echo "  3. Criando smtp-host..."
if gcloud secrets describe smtp-host --quiet 2>/dev/null; then
    echo "     ✓ smtp-host já existe, atualizando..."
    echo -n "$SMTP_HOST" | gcloud secrets versions add smtp-host --data-file=-
else
    echo "     Criando novo secret..."
    echo -n "$SMTP_HOST" | gcloud secrets create smtp-host --data-file=- --replication-policy="automatic" --quiet
fi

# SMTP_PORT
echo "  4. Criando smtp-port..."
if gcloud secrets describe smtp-port --quiet 2>/dev/null; then
    echo "     ✓ smtp-port já existe, atualizando..."
    echo -n "$SMTP_PORT" | gcloud secrets versions add smtp-port --data-file=-
else
    echo "     Criando novo secret..."
    echo -n "$SMTP_PORT" | gcloud secrets create smtp-port --data-file=- --replication-policy="automatic" --quiet
fi

# SMTP_USER
echo "  5. Criando smtp-user..."
if gcloud secrets describe smtp-user --quiet 2>/dev/null; then
    echo "     ✓ smtp-user já existe, atualizando..."
    echo -n "$SMTP_USER" | gcloud secrets versions add smtp-user --data-file=-
else
    echo "     Criando novo secret..."
    echo -n "$SMTP_USER" | gcloud secrets create smtp-user --data-file=- --replication-policy="automatic" --quiet
fi

# SMTP_PASS
echo "  6. Criando smtp-pass..."
if gcloud secrets describe smtp-pass --quiet 2>/dev/null; then
    echo "     ✓ smtp-pass já existe, atualizando..."
    echo -n "$SMTP_PASS" | gcloud secrets versions add smtp-pass --data-file=-
else
    echo "     Criando novo secret..."
    echo -n "$SMTP_PASS" | gcloud secrets create smtp-pass --data-file=- --replication-policy="automatic" --quiet
fi

# SMTP_FROM
echo "  7. Criando smtp-from..."
if gcloud secrets describe smtp-from --quiet 2>/dev/null; then
    echo "     ✓ smtp-from já existe, atualizando..."
    echo -n "$SMTP_FROM" | gcloud secrets versions add smtp-from --data-file=-
else
    echo "     Criando novo secret..."
    echo -n "$SMTP_FROM" | gcloud secrets create smtp-from --data-file=- --replication-policy="automatic" --quiet
fi

echo ""
echo "✅ Secrets criados com sucesso!"
echo ""

# Verificar permissões
echo "📋 Verificando permissões de IAM..."
SERVICE_ACCOUNT=$(gcloud iam service-accounts list --filter="displayName:Cloud Run default" --format='value(email)' 2>/dev/null || echo "cloud-run-sa@$PROJECT_ID.iam.gserviceaccount.com")

echo "  Service Account: $SERVICE_ACCOUNT"
echo ""
echo "  Granting permissions..."
gcloud secrets add-iam-policy-binding db-pass \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet || true

gcloud secrets add-iam-policy-binding secret-key \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet || true

gcloud secrets add-iam-policy-binding smtp-host \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet || true

gcloud secrets add-iam-policy-binding smtp-port \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet || true

gcloud secrets add-iam-policy-binding smtp-user \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet || true

gcloud secrets add-iam-policy-binding smtp-pass \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet || true

gcloud secrets add-iam-policy-binding smtp-from \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet || true

echo ""
echo "✅ Permissões configuradas!"
echo ""
echo "🎯 Próximos passos:"
echo ""
echo "  1. Faça commit das mudanças:"
echo "     git add ."
echo "     git commit -m 'feat: Configure Cloud Run with Cloud SQL and secrets'"
echo ""
echo "  2. Faça push para GitHub:"
echo "     git push"
echo ""
echo "  3. Cloud Build será acionado automaticamente"
echo ""
echo "  4. Verifique o deploy em:"
echo "     gcloud run services describe app --region us-central1 --format='value(status.url)'"
echo ""
echo "✨ Done!"
