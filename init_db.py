"""
⚠️  DEPRECATED - NÃO é MAIS NECESSÁRIO

A criação de tabelas do banco de dados agora é AUTOMÁTICA quando a aplicação inicia.

Veja app.py:
    with app.app_context():
        criar_tabelas()  # Executa db.create_all()

Estes scripts antigos (.py) não precisam mais ser executados:
- create_db.py ❌
- init_db.py ❌
- migrate_licoes.py ❌
- migrate_mudancas.py ❌
- migrate_perfis.py ❌

A criação de tabelas acontece automaticamente no startup da aplicação.
"""

from app import app, db

print(__doc__)

with app.app_context():
    print("✅ Se você rodar isso manualmente, as tabelas serão criadas:")
    db.create_all()
    print("✅ Tabelas criadas/verificadas com sucesso")
