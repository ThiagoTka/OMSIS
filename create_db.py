"""
⚠️  DEPRECATED - NÃO é MAIS NECESSÁRIO

A criação de tabelas do banco de dados agora é AUTOMÁTICA quando a aplicação inicia.

Veja app.py:
    with app.app_context():
        criar_tabelas()  # Executa db.create_all()

Isso garante que as tabelas sejam criadas em qualquer ambiente:
- ✅ Local (dev)
- ✅ GCP Cloud Run
- ✅ GCP Cloud SQL
- ✅ Qualquer outro servidor

Se por algum motivo você quiser executar manualmente (não necessário):
    python -c "from app import app, db; app.app_context().push(); db.create_all()"

Ou execute direto no Cloud Run:
    gcloud run jobs create init-db --image YOUR_IMAGE --command "python" --args "-c" "from app import app, db; app.app_context().push(); db.create_all()"
"""

print(__doc__)

