from app import app, criar_tabelas_e_dados

with app.app_context():
    criar_tabelas_e_dados()
    print("Tabelas criadas com sucesso!")