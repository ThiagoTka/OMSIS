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

# Variáveis (do .env)
DB_PASS="KHH5&efe%hrb@#"
SECRET_KEY="KHH5&efe%hrb@#"

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
