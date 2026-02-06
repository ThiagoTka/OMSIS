import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-dev')

# ---------------------------
# CONFIGURAÇÃO DO BANCO
# ---------------------------
if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

elif os.environ.get('DB_USER') and os.environ.get('DB_PASS') and os.environ.get('DB_NAME'):
    db_user = os.environ.get('DB_USER')
    db_pass = os.environ.get('DB_PASS')
    db_name = os.environ.get('DB_NAME')
    cloud_sql_instance = os.environ.get('CLOUD_SQL_CONNECTION_NAME')

    if cloud_sql_instance:
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            f"postgresql+psycopg2://{db_user}:{db_pass}@/"
            f"{db_name}?host=/cloudsql/{cloud_sql_instance}"
        )
    else:
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        )
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tarefas.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------------------
# LOGIN
# ---------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------
# MODELOS
# ---------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Atividade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_sequencial = db.Column(db.Integer, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    responsavel = db.Column(db.String(100), nullable=False)
    data_liberacao = db.Column(db.DateTime)
    data_conclusao = db.Column(db.DateTime)

# ---------------------------
# INIT DB
# ---------------------------
def criar_tabelas_e_dados():
    db.create_all()

    if not User.query.first():
        usuarios = [
            ("Alice", "alice@example.com"),
            ("Bob", "bob@example.com"),
            ("Carlos", "carlos@example.com"),
        ]
        for nome, email in usuarios:
            senha = generate_password_hash("123")
            db.session.add(User(username=nome, email=email, password=senha))
        db.session.commit()

    if not Atividade.query.first():
        atividades = [
            (1, "Levantamento de Requisitos", "Alice", True),
            (2, "Desenvolvimento Backend", "Bob", False),
            (3, "Desenvolvimento Frontend", "Carlos", False),
            (4, "Deploy em Produção", "Alice", False),
        ]

        for seq, desc, resp, liberado in atividades:
            db.session.add(
                Atividade(
                    numero_sequencial=seq,
                    descricao=desc,
                    responsavel=resp,
                    data_liberacao=datetime.now() if liberado else None
                )
            )
        db.session.commit()

# 🚀 ISSO É O QUE RESOLVE NO CLOUD RUN
with app.app_context():
    criar_tabelas_e_dados()

# ---------------------------
# ROTAS
# ---------------------------
@app.route('/')
@login_required
def index():
    atividades = Atividade.query.order_by(Atividade.numero_sequencial).all()
    return render_template('index.html', atividades=atividades, usuario_atual=current_user.username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash('Usuário ou senha inválidos')
            return redirect(url_for('login'))

        login_user(user)
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/concluir/<int:id>', methods=['POST'])
@login_required
def concluir_atividade(id):
    atividade = Atividade.query.get_or_404(id)

    if atividade.responsavel != current_user.username:
        flash('Você não pode concluir esta tarefa.')
        return redirect(url_for('index'))

    if not atividade.data_liberacao:
        flash('Atividade ainda não liberada.')
        return redirect(url_for('index'))

    atividade.data_conclusao = datetime.now()
    proxima = Atividade.query.filter_by(numero_sequencial=atividade.numero_sequencial + 1).first()
    if proxima:
        proxima.data_liberacao = datetime.now()

    db.session.commit()
    return redirect(url_for('index'))
