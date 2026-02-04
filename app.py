import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-dev')

# Configuração do Banco de Dados
# Prioridade: DATABASE_URL > Cloud SQL Socket > SQLite local
if os.environ.get('DATABASE_URL'):
    # Cloud SQL PostgreSQL via DATABASE_URL (ex: postgresql://user:pass@host/db)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
elif os.environ.get('DB_USER') and os.environ.get('DB_PASS') and os.environ.get('DB_NAME'):
    # Cloud SQL com Cloud SQL Proxy Socket (para Cloud Run/App Engine)
    db_user = os.environ.get('DB_USER')
    db_pass = os.environ.get('DB_PASS')
    db_name = os.environ.get('DB_NAME')
    cloud_sql_instance = os.environ.get('CLOUD_SQL_CONNECTION_NAME')
    if cloud_sql_instance:
        # Cloud Run com unix socket
        app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_pass}@/{db_name}?unix_sock=/cloudsql/{cloud_sql_instance}'
    else:
        # Fallback: assume TCP connection
        db_host = os.environ.get('DB_HOST', 'localhost')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}'
else:
    # SQLite local (desenvolvimento)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tarefas.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redireciona para cá se tentar acessar algo proibido

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Modelos de Dados ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) # Senha criptografada

class Atividade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_sequencial = db.Column(db.Integer, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    responsavel = db.Column(db.String(100), nullable=False)
    data_liberacao = db.Column(db.DateTime, nullable=True)
    data_conclusao = db.Column(db.DateTime, nullable=True)

# --- Inicialização ---
def criar_tabelas_e_dados():
    db.create_all()

    # Se a coluna 'email' não existir (migração leve para bancos antigos), adiciona-a
    try:
        table_name = User.__table__.name
        # Verifica colunas na tabela (SQLite)
        result = db.session.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
        cols = [row[1] for row in result]
        if 'email' not in cols:
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN email VARCHAR(120)"))
            db.session.commit()
            # Atualiza registros existentes para ter um e-mail baseado no username
            users = User.query.all()
            for u in users:
                if not getattr(u, 'email', None):
                    u.email = f"{u.username.lower()}@example.com"
                    db.session.add(u)
            db.session.commit()
    except Exception:
        # Não bloquear inicialização caso a migração falhe; mostraremos erros ao tentar logar
        pass
    
    # 1. Cria os USUÁRIOS automaticamente (Senha padrão: 123)
    if not User.query.first():
        usuarios_padrao = [
            ("Alice", "alice@example.com"),
            ("Bob", "bob@example.com"),
            ("Carlos", "carlos@example.com"),
        ]
        for nome, email in usuarios_padrao:
            # Cria o usuário se ele não existir
            if not User.query.filter_by(email=email).first():
                # Criptografa a senha "123"
                senha_hash = generate_password_hash('123', method='pbkdf2:sha256')
                novo_usuario = User(username=nome, email=email, password=senha_hash)
                db.session.add(novo_usuario)
        db.session.commit()
        print("--- Usuários de teste criados: Alice, Bob, Carlos (Senha: 123) ---")

    # 2. Cria as TAREFAS iniciais
    if not Atividade.query.first():
        dados = [
            (1, "Levantamento de Requisitos", "Alice", True),
            (2, "Desenvolvimento Backend", "Bob", False),
            (3, "Desenvolvimento Frontend", "Carlos", False),
            (4, "Deploy em Produção", "Alice", False)
        ]
        for seq, desc, resp, liberado in dados:
            nova = Atividade(
                numero_sequencial=seq,
                descricao=desc,
                responsavel=resp,
                data_liberacao=datetime.now() if liberado else None
            )
            db.session.add(nova)
        db.session.commit()
        
# --- Rotas de Autenticação ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Verifica se email já existe
        if User.query.filter_by(email=email).first():
            flash('Já existe uma conta com este e-mail.')
            return redirect(url_for('register'))

        # Define um username simples a partir do e-mail (parte antes do @)
        username = email.split('@')[0]

        # Cria novo usuário com senha criptografada (hash)
        new_user = User(username=username, email=email, password=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        
        # Verifica se usuário existe e a senha bate com o hash
        if not user or not check_password_hash(user.password, password):
            flash('Verifique seus dados e tente novamente.')
            return redirect(url_for('login'))
        
        login_user(user)
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- Rotas Principais ---
@app.route('/')
@login_required # Só acessa se estiver logado
def index():
    atividades = Atividade.query.order_by(Atividade.numero_sequencial).all()
    return render_template('index.html', atividades=atividades, usuario_atual=current_user.username)

@app.route('/concluir/<int:id>', methods=['POST'])
@login_required
def concluir_atividade(id):
    atividade = Atividade.query.get_or_404(id)

    # Regra 1: Validação com o usuário logado real
    if atividade.responsavel != current_user.username:
        flash(f'Erro: Apenas {atividade.responsavel} pode concluir esta tarefa.')
        return redirect(url_for('index'))

    # Regra 2: Sequência
    if not atividade.data_liberacao:
        flash('Erro: Esta atividade ainda não foi liberada pela anterior.')
        return redirect(url_for('index'))

    atividade.data_conclusao = datetime.now()
    
    proxima = Atividade.query.filter_by(numero_sequencial=atividade.numero_sequencial + 1).first()
    if proxima:
        proxima.data_liberacao = datetime.now()
    
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/reset')
def reset():
    db.drop_all()
    criar_tabelas_e_dados()
    return redirect(url_for('index'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # Garante que as tabelas e dados iniciais existam ao iniciar localmente
    try:
        criar_tabelas_e_dados()
    except Exception:
        pass

    app.run(host="0.0.0.0", port=port)