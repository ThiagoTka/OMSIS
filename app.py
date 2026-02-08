import os
from datetime import datetime
from urllib.parse import quote_plus

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text, inspect

# ------------------------------------------------------------------------------
# APP
# ------------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-secreta-dev")

# DATABASE CONFIG
if os.environ.get("DATABASE_URL"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
elif (
    os.environ.get("DB_USER")
    and os.environ.get("DB_PASS")
    and os.environ.get("DB_NAME")
    and os.environ.get("CLOUD_SQL_CONNECTION_NAME")
):
    db_user = os.environ.get("DB_USER")
    db_pass = quote_plus(os.environ.get("DB_PASS"))  # URL-encode the password
    db_name = os.environ.get("DB_NAME")
    cloud_sql_connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql+psycopg2://{db_user}:{db_pass}@/{db_name}?host=/cloudsql/{cloud_sql_connection_name}"
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///dev.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ------------------------------------------------------------------------------
# EXTENSIONS
# ------------------------------------------------------------------------------
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ------------------------------------------------------------------------------
# MODELS
# ------------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Projeto(db.Model):
    __tablename__ = "projetos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    membros = db.relationship(
        "ProjetoMembro",
        backref="projeto",
        lazy=True,
        cascade="all, delete-orphan",
    )


class ProjetoMembro(db.Model):
    __tablename__ = "projeto_membros"

    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey("projetos.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref=db.backref("projeto_membros", lazy=True))

    __table_args__ = (
        db.UniqueConstraint("projeto_id", "user_id", name="uq_projeto_membro"),
    )


class Fase(db.Model):
    __tablename__ = "fases"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    projeto_id = db.Column(db.Integer, db.ForeignKey("projetos.id"), nullable=False)
    projeto = db.relationship("Projeto", backref=db.backref("fases", lazy=True))


class Atividade(db.Model):
    __tablename__ = "atividades"

    id = db.Column(db.Integer, primary_key=True)
    numero_sequencial = db.Column(db.Integer, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    responsavel = db.Column(db.String(100), nullable=False)
    data_liberacao = db.Column(db.DateTime)
    data_conclusao = db.Column(db.DateTime)
    # Relacionamento com Cenario (opcional)
    cenario_id = db.Column(db.Integer, db.ForeignKey("cenarios.id"), nullable=True)
    cenario = db.relationship("Cenario", backref=db.backref("atividades", lazy=True))


class TesteTabela1(db.Model):
    __tablename__ = "teste_tabela_1"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.Text, nullable=False)


class Cenario(db.Model):
    __tablename__ = "cenarios"

    id = db.Column(db.Integer, primary_key=True)
    cenario = db.Column(db.String(200), nullable=False)
    fase_id = db.Column(db.Integer, db.ForeignKey("fases.id"), nullable=True)
    fase = db.relationship("Fase", backref=db.backref("cenarios", lazy=True))


# ------------------------------------------------------------------------------
# LOGIN
# ------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def is_project_member(projeto_id, user_id=None):
    uid = user_id or current_user.id
    return (
        ProjetoMembro.query.filter_by(projeto_id=projeto_id, user_id=uid).first()
        is not None
    )


def get_fase_for_cenario_or_none(cenario):
    if not cenario or not cenario.fase_id:
        return None
    fase = Fase.query.get_or_404(cenario.fase_id)
    if not is_project_member(fase.projeto_id):
        abort(403)
    return fase


# ------------------------------------------------------------------------------
# DB INIT
# ------------------------------------------------------------------------------
def criar_tabelas_e_dados():
    try:
        db.create_all()

        # Garantir que a coluna cenario_id exista em 'atividades' (adiciona se faltar)
        try:
            inspector = inspect(db.engine)
            if "atividades" in inspector.get_table_names():
                cols = [c["name"] for c in inspector.get_columns("atividades")]
                if "cenario_id" not in cols:
                    if db.engine.dialect.name == "sqlite":
                        db.session.execute(text("ALTER TABLE atividades ADD COLUMN cenario_id INTEGER"))
                    else:
                        db.session.execute(text("ALTER TABLE atividades ADD COLUMN cenario_id INTEGER REFERENCES cenarios(id)"))
                    db.session.commit()
        except Exception:
            # Se algo falhar aqui, ignoramos para não quebrar inicialização em ambientes restritos
            pass

        # Garantir que a coluna fase_id exista em 'cenarios' (adiciona se faltar)
        try:
            inspector = inspect(db.engine)
            if "cenarios" in inspector.get_table_names():
                cols = [c["name"] for c in inspector.get_columns("cenarios")]
                if "fase_id" not in cols:
                    if db.engine.dialect.name == "sqlite":
                        db.session.execute(text("ALTER TABLE cenarios ADD COLUMN fase_id INTEGER"))
                    else:
                        db.session.execute(text("ALTER TABLE cenarios ADD COLUMN fase_id INTEGER REFERENCES fases(id)"))
                    db.session.commit()
        except Exception:
            # Se algo falhar aqui, ignoramos para não quebrar inicialização em ambientes restritos
            pass

        if not User.query.first():
            usuarios = [
                ("Alice", "alice@example.com"),
                ("Bob", "bob@example.com"),
                ("Carlos", "carlos@example.com"),
            ]

            for nome, email in usuarios:
                db.session.add(
                    User(
                        username=nome,
                        email=email,
                        password=generate_password_hash("123"),
                    )
                )

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
                        data_liberacao=datetime.now() if liberado else None,
                    )
                )

            db.session.commit()

        # Popular cenários iniciais
        if not Cenario.query.first():
            cenarios = [
                ("Cenário A",),
                ("Cenário B",),
                ("Cenário C",),
            ]
            for (nome,) in cenarios:
                db.session.add(Cenario(cenario=nome))
            db.session.commit()

    except Exception as e:
        print("ERRO AO INICIALIZAR DB:", e)


# 🔥 Executa sempre que o container sobe
with app.app_context():
    criar_tabelas_e_dados()


# ------------------------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------------------------

@app.route("/db-check")
def db_check():
    result = db.session.execute(text("SELECT current_database(), current_user"))
    row = result.fetchone()
    return f"DB={row[0]} | USER={row[1]}"


@app.route("/where-db")
def where_db():
    return app.config["SQLALCHEMY_DATABASE_URI"]

@app.route("/test-db")
def test_db():
    try:
        registro = TesteTabela1(nome="Cloud Run OK")
        db.session.add(registro)
        db.session.commit()
        return "INSERT OK - gravou no Cloud SQL"
    except Exception as e:
        return f"ERRO DB: {e}", 500


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if User.query.filter_by(email=email).first():
            flash("E-mail já cadastrado")
            return redirect(url_for("register"))

        user = User(
            username=email.split("@")[0],
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("projetos"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash("Usuário ou senha inválidos")
            return redirect(url_for("login"))

        login_user(user)
        return redirect(url_for("projetos"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    atividades = Atividade.query.order_by(Atividade.numero_sequencial).all()
    return render_template(
        "index.html",
        atividades=atividades,
        usuario_atual=current_user.username,
    )


@app.route("/projetos", methods=["GET", "POST"])
@login_required
def projetos():
    if request.method == "POST":
        nome = request.form.get("nome")
        membros_ids = request.form.getlist("membros")
        if nome:
            projeto = Projeto(nome=nome)
            db.session.add(projeto)
            db.session.flush()
            membros = {int(mid) for mid in membros_ids if mid.isdigit()}
            membros.add(current_user.id)
            for uid in membros:
                db.session.add(ProjetoMembro(projeto_id=projeto.id, user_id=uid))
            db.session.commit()
            flash("Projeto criado com sucesso")
        return redirect(url_for("projetos"))

    projetos = (
        Projeto.query
        .join(ProjetoMembro)
        .filter(ProjetoMembro.user_id == current_user.id)
        .order_by(Projeto.id)
        .all()
    )
    usuarios = User.query.order_by(User.username).all()
    return render_template(
        "projetos.html",
        projetos=projetos,
        usuarios=usuarios,
        usuario_atual=current_user.username,
    )


@app.route("/projetos/<int:projeto_id>/membros", methods=["POST"])
@login_required
def adicionar_membro_projeto(projeto_id):
    Projeto.query.get_or_404(projeto_id)
    if not is_project_member(projeto_id):
        abort(403)

    user_id = request.form.get("user_id")
    if user_id and user_id.isdigit():
        uid = int(user_id)
        if User.query.get(uid) and not ProjetoMembro.query.filter_by(projeto_id=projeto_id, user_id=uid).first():
            db.session.add(ProjetoMembro(projeto_id=projeto_id, user_id=uid))
            db.session.commit()
            flash("Membro adicionado com sucesso")
    return redirect(url_for("projetos"))


@app.route("/projetos/<int:projeto_id>/membros/remover", methods=["POST"])
@login_required
def remover_membro_projeto(projeto_id):
    Projeto.query.get_or_404(projeto_id)
    if not is_project_member(projeto_id):
        abort(403)

    user_id = request.form.get("user_id")
    if not user_id or not user_id.isdigit():
        return redirect(url_for("projetos"))

    uid = int(user_id)
    membro = ProjetoMembro.query.filter_by(projeto_id=projeto_id, user_id=uid).first()
    if not membro:
        return redirect(url_for("projetos"))

    total_membros = ProjetoMembro.query.filter_by(projeto_id=projeto_id).count()
    if total_membros <= 1:
        flash("O projeto precisa ter pelo menos um membro")
        return redirect(url_for("projetos"))

    db.session.delete(membro)
    db.session.commit()
    flash("Membro removido com sucesso")
    return redirect(url_for("projetos"))


@app.route("/projetos/<int:projeto_id>/fluxo", methods=["GET", "POST"])
@login_required
def fluxo(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    if not is_project_member(projeto_id):
        abort(403)

    # Processar POST (criar fase, cenário ou atividade)
    if request.method == "POST":
        fase_id = request.args.get("fase", type=int)
        cenario_id = request.args.get("cenario", type=int)
        
        if request.form.get("fase"):
            # Criar fase
            nome = request.form.get("fase")
            if nome:
                db.session.add(Fase(nome=nome, projeto_id=projeto_id))
                db.session.commit()
                flash("Fase criada com sucesso", "success")
            return redirect(url_for("fluxo", projeto_id=projeto_id))
        
        elif request.form.get("cenario"):
            # Criar cenário
            nome = request.form.get("cenario")
            if nome and fase_id:
                db.session.add(Cenario(cenario=nome, fase_id=fase_id))
                db.session.commit()
                flash("Cenário criado com sucesso", "success")
            return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id))
        
        elif request.form.get("descricao"):
            # Criar atividade
            try:
                numero = int(request.form.get("numero_sequencial") or 0)
            except ValueError:
                numero = 0
            descricao = request.form.get("descricao")
            responsavel = request.form.get("responsavel")
            
            if descricao and responsavel and cenario_id:
                nova = Atividade(
                    numero_sequencial=numero,
                    descricao=descricao,
                    responsavel=responsavel,
                    cenario_id=cenario_id,
                )
                db.session.add(nova)
                db.session.commit()
                
                # Se não houver nenhuma atividade liberada neste cenário, liberar a primeira (menor seq)
                any_liberada = (
                    Atividade.query
                    .filter_by(cenario_id=cenario_id)
                    .filter(Atividade.data_liberacao != None)
                    .first()
                )
                if not any_liberada:
                    primeira = (
                        Atividade.query
                        .filter_by(cenario_id=cenario_id)
                        .order_by(Atividade.numero_sequencial)
                        .first()
                    )
                    if primeira and not primeira.data_liberacao:
                        primeira.data_liberacao = datetime.now()
                        db.session.commit()
                
                flash("Atividade criada com sucesso", "success")
            return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id, cenario=cenario_id))

    # Carregar todas as fases com seus cenários
    fases = Fase.query.filter_by(projeto_id=projeto_id).order_by(Fase.id).all()
    
    # Para cada fase, carregar seus cenários
    for fase in fases:
        fase.cenarios = Cenario.query.filter_by(fase_id=fase.id).order_by(Cenario.id).all()
        # Para cada cenário, carregar suas atividades
        for cenario in fase.cenarios:
            cenario.atividades = (
                Atividade.query
                .filter_by(cenario_id=cenario.id)
                .order_by(Atividade.numero_sequencial)
                .all()
            )

    # Fase selecionada (da query string)
    fase_id = request.args.get("fase", type=int)
    fase_selecionada = None
    cenarios = []
    
    if fase_id:
        fase_selecionada = Fase.query.filter_by(id=fase_id, projeto_id=projeto_id).first()
        if fase_selecionada:
            cenarios = Cenario.query.filter_by(fase_id=fase_id).order_by(Cenario.id).all()
            # Carregar atividades para cada cenário
            for cenario in cenarios:
                cenario.atividades = (
                    Atividade.query
                    .filter_by(cenario_id=cenario.id)
                    .order_by(Atividade.numero_sequencial)
                    .all()
                )

    # Cenário selecionado (da query string)
    cenario_id = request.args.get("cenario", type=int)
    cenario_selecionado = None
    atividades = []
    usuarios = []
    
    if cenario_id:
        cenario_selecionado = Cenario.query.filter_by(id=cenario_id, fase_id=fase_id).first() if fase_id else None
        if cenario_selecionado:
            atividades = (
                Atividade.query
                .filter_by(cenario_id=cenario_id)
                .order_by(Atividade.numero_sequencial)
                .all()
            )
            # Apenas membros do projeto podem ser responsáveis
            usuarios = (
                User.query
                .join(ProjetoMembro)
                .filter(ProjetoMembro.projeto_id == projeto_id)
                .order_by(User.username)
                .all()
            )

    return render_template(
        "fluxo.html",
        projeto=projeto,
        fases=fases,
        fase_selecionada=fase_selecionada,
        cenarios=cenarios,
        cenario_selecionado=cenario_selecionado,
        atividades=atividades,
        usuario_atual=current_user.username,
        usuarios=usuarios,
    )


@app.route("/projetos/<int:projeto_id>/editar_fase", methods=["POST"])
@login_required
def fluxo_editar_fase(projeto_id):
    if not is_project_member(projeto_id):
        abort(403)
    
    fase_id = request.form.get("fase_id", type=int)
    novo_nome = request.form.get("nome")
    
    if fase_id and novo_nome:
        fase = Fase.query.get_or_404(fase_id)
        if fase.projeto_id == projeto_id:
            fase.nome = novo_nome
            db.session.commit()
            flash("Fase atualizada com sucesso", "success")
    
    return redirect(url_for("fluxo", projeto_id=projeto_id))


@app.route("/projetos/<int:projeto_id>/excluir_fase", methods=["POST"])
@login_required
def fluxo_excluir_fase(projeto_id):
    if not is_project_member(projeto_id):
        abort(403)
    
    fase_id = request.form.get("fase_id", type=int)
    
    if fase_id:
        fase = Fase.query.get_or_404(fase_id)
        if fase.projeto_id == projeto_id:
            # Excluir cenários e atividades relacionados
            cenarios = Cenario.query.filter_by(fase_id=fase_id).all()
            for cenario in cenarios:
                Atividade.query.filter_by(cenario_id=cenario.id).delete()
                db.session.delete(cenario)
            db.session.delete(fase)
            db.session.commit()
            flash("Fase excluída com sucesso", "success")
    
    return redirect(url_for("fluxo", projeto_id=projeto_id))


@app.route("/projetos/<int:projeto_id>/editar_cenario", methods=["POST"])
@login_required
def fluxo_editar_cenario(projeto_id):
    if not is_project_member(projeto_id):
        abort(403)
    
    cenario_id = request.form.get("cenario_id", type=int)
    novo_nome = request.form.get("nome")
    fase_id = request.form.get("fase_id", type=int)
    
    if cenario_id and novo_nome:
        cenario = Cenario.query.get_or_404(cenario_id)
        fase = Fase.query.get_or_404(cenario.fase_id)
        if fase.projeto_id == projeto_id:
            cenario.cenario = novo_nome
            db.session.commit()
            flash("Cenário atualizado com sucesso", "success")
    
    return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id))


@app.route("/projetos/<int:projeto_id>/excluir_cenario", methods=["POST"])
@login_required
def fluxo_excluir_cenario(projeto_id):
    if not is_project_member(projeto_id):
        abort(403)
    
    cenario_id = request.form.get("cenario_id", type=int)
    fase_id = request.form.get("fase_id", type=int)
    
    if cenario_id:
        cenario = Cenario.query.get_or_404(cenario_id)
        fase = Fase.query.get_or_404(cenario.fase_id)
        if fase.projeto_id == projeto_id:
            # Excluir atividades relacionadas
            Atividade.query.filter_by(cenario_id=cenario_id).delete()
            db.session.delete(cenario)
            db.session.commit()
            flash("Cenário excluído com sucesso", "success")
    
    return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id))


@app.route("/projetos/<int:projeto_id>/editar_atividade", methods=["POST"])
@login_required
def fluxo_editar_atividade(projeto_id):
    if not is_project_member(projeto_id):
        abort(403)
    
    atividade_id = request.form.get("atividade_id", type=int)
    numero_sequencial = request.form.get("numero_sequencial", type=int)
    descricao = request.form.get("descricao")
    responsavel = request.form.get("responsavel")
    fase_id = request.form.get("fase_id", type=int)
    cenario_id = request.form.get("cenario_id", type=int)
    
    if atividade_id and descricao and responsavel:
        atividade = Atividade.query.get_or_404(atividade_id)
        cenario = Cenario.query.get_or_404(atividade.cenario_id)
        fase = Fase.query.get_or_404(cenario.fase_id)
        if fase.projeto_id == projeto_id:
            atividade.numero_sequencial = numero_sequencial
            atividade.descricao = descricao
            atividade.responsavel = responsavel
            db.session.commit()
            flash("Atividade atualizada com sucesso", "success")
    
    return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id, cenario=cenario_id))


@app.route("/projetos/<int:projeto_id>/excluir_atividade", methods=["POST"])
@login_required
def fluxo_excluir_atividade(projeto_id):
    if not is_project_member(projeto_id):
        abort(403)
    
    atividade_id = request.form.get("atividade_id", type=int)
    fase_id = request.form.get("fase_id", type=int)
    cenario_id = request.form.get("cenario_id", type=int)
    
    if atividade_id:
        atividade = Atividade.query.get_or_404(atividade_id)
        cenario = Cenario.query.get_or_404(atividade.cenario_id)
        fase = Fase.query.get_or_404(cenario.fase_id)
        if fase.projeto_id == projeto_id:
            db.session.delete(atividade)
            db.session.commit()
            flash("Atividade excluída com sucesso", "success")
    
    return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id, cenario=cenario_id))


@app.route("/projetos/<int:projeto_id>/concluir_atividade", methods=["POST"])
@login_required
def fluxo_concluir_atividade(projeto_id):
    if not is_project_member(projeto_id):
        abort(403)
    
    atividade_id = request.form.get("atividade_id", type=int)
    fase_id = request.form.get("fase_id", type=int)
    cenario_id = request.form.get("cenario_id", type=int)
    
    if atividade_id:
        atividade = Atividade.query.get_or_404(atividade_id)
        cenario = Cenario.query.get_or_404(atividade.cenario_id)
        fase = Fase.query.get_or_404(cenario.fase_id)
        if fase.projeto_id == projeto_id:
            atividade.data_conclusao = datetime.now()
            db.session.commit()
            
            # Liberar próxima atividade na sequência
            proxima = (
                Atividade.query
                .filter_by(cenario_id=cenario_id)
                .filter(Atividade.numero_sequencial > atividade.numero_sequencial)
                .filter(Atividade.data_liberacao == None)
                .order_by(Atividade.numero_sequencial)
                .first()
            )
            if proxima:
                proxima.data_liberacao = datetime.now()
                db.session.commit()
            
            flash("Atividade concluída com sucesso", "success")
    
    return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id, cenario=cenario_id))


@app.route("/projetos/<int:projeto_id>/fases", methods=["GET", "POST"])
@login_required
def fases(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    if not is_project_member(projeto_id):
        abort(403)

    if request.method == "POST":
        nome = request.form.get("fase")
        if nome:
            db.session.add(Fase(nome=nome, projeto_id=projeto_id))
            db.session.commit()
            flash("Fase criada com sucesso")
        return redirect(url_for("fases", projeto_id=projeto_id))

    fases = Fase.query.filter_by(projeto_id=projeto_id).order_by(Fase.id).all()
    return render_template(
        "fases.html",
        projeto=projeto,
        fases=fases,
        usuario_atual=current_user.username,
    )


@app.route("/projetos/<int:projeto_id>/fases/<int:fase_id>/cenarios", methods=["GET", "POST"])
@login_required
def cenarios_por_fase(projeto_id, fase_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    if not is_project_member(projeto_id):
        abort(403)

    fase = Fase.query.filter_by(id=fase_id, projeto_id=projeto_id).first_or_404()

    if request.method == "POST":
        nome = request.form.get("cenario")
        if nome:
            db.session.add(Cenario(cenario=nome, fase_id=fase_id))
            db.session.commit()
            flash("Cenário criado com sucesso")
        return redirect(url_for("cenarios_por_fase", projeto_id=projeto_id, fase_id=fase_id))

    cenarios = Cenario.query.filter_by(fase_id=fase_id).order_by(Cenario.id).all()
    return render_template(
        "cenarios.html",
        projeto=projeto,
        fase=fase,
        cenarios=cenarios,
        usuario_atual=current_user.username,
    )


@app.route(
    "/projetos/<int:projeto_id>/fases/<int:fase_id>/cenarios/<int:cenario_id>/atividades",
    methods=["GET", "POST"],
)
@login_required
def atividades_por_cenario(projeto_id, fase_id, cenario_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    if not is_project_member(projeto_id):
        abort(403)

    fase = Fase.query.filter_by(id=fase_id, projeto_id=projeto_id).first_or_404()
    cenario = Cenario.query.filter_by(id=cenario_id, fase_id=fase_id).first_or_404()

    if request.method == "POST":
        try:
            numero = int(request.form.get("numero_sequencial") or 0)
        except ValueError:
            numero = 0
        descricao = request.form.get("descricao")
        responsavel = request.form.get("responsavel")

        if descricao and responsavel:
            nova = Atividade(
                numero_sequencial=numero,
                descricao=descricao,
                responsavel=responsavel,
                cenario_id=cenario_id,
            )
            db.session.add(nova)
            db.session.commit()

            # Se não houver nenhuma atividade liberada neste cenário, liberar a primeira (menor seq)
            any_liberada = (
                Atividade.query
                .filter_by(cenario_id=cenario_id)
                .filter(Atividade.data_liberacao != None)
                .first()
            )
            if not any_liberada:
                primeira = (
                    Atividade.query
                    .filter_by(cenario_id=cenario_id)
                    .order_by(Atividade.numero_sequencial)
                    .first()
                )
                if primeira and not primeira.data_liberacao:
                    primeira.data_liberacao = datetime.now()
                    db.session.commit()

            flash("Atividade criada com sucesso")

        return redirect(
            url_for(
                "atividades_por_cenario",
                projeto_id=projeto_id,
                fase_id=fase_id,
                cenario_id=cenario_id,
            )
        )

    atividades = (
        Atividade.query
        .filter_by(cenario_id=cenario_id)
        .order_by(Atividade.numero_sequencial)
        .all()
    )
    # Apenas membros do projeto podem ser responsáveis
    usuarios = (
        User.query
        .join(ProjetoMembro)
        .filter(ProjetoMembro.projeto_id == projeto_id)
        .order_by(User.username)
        .all()
    )
    return render_template(
        "atividades.html",
        projeto=projeto,
        fase=fase,
        cenario=cenario,
        atividades=atividades,
        usuario_atual=current_user.username,
        usuarios=usuarios,
    )


@app.route("/cenarios")
@login_required
def cenarios_legacy():
    return redirect(url_for("projetos"))


@app.route("/cenarios/<int:cenario_id>/atividades")
@login_required
def atividades_legacy(cenario_id):
    cenario = Cenario.query.get_or_404(cenario_id)
    if not cenario.fase_id:
        return redirect(url_for("projetos"))
    fase = get_fase_for_cenario_or_none(cenario)
    if not fase:
        return redirect(url_for("projetos"))
    return redirect(
        url_for(
            "atividades_por_cenario",
            projeto_id=fase.projeto_id,
            fase_id=fase.id,
            cenario_id=cenario_id,
        )
    )


@app.route("/atividades/<int:atividade_id>/editar", methods=["POST"])
@login_required
def editar_atividade(atividade_id):
    atv = Atividade.query.get_or_404(atividade_id)
    cenario = Cenario.query.get(atv.cenario_id) if atv.cenario_id else None
    fase = get_fase_for_cenario_or_none(cenario) if cenario else None

    if not fase or not is_project_member(fase.projeto_id):
        abort(403)

    try:
        numero = int(request.form.get("numero_sequencial") or atv.numero_sequencial)
    except ValueError:
        numero = atv.numero_sequencial
    
    descricao = request.form.get("descricao")
    responsavel = request.form.get("responsavel")

    if descricao:
        atv.descricao = descricao
    if responsavel:
        atv.responsavel = responsavel
    atv.numero_sequencial = numero
    
    db.session.commit()
    flash("Atividade atualizada com sucesso", "success")

    if cenario and fase:
        return redirect(
            url_for(
                "atividades_por_cenario",
                projeto_id=fase.projeto_id,
                fase_id=fase.id,
                cenario_id=cenario.id,
            )
        )
    return redirect(url_for("projetos"))


@app.route("/atividades/<int:atividade_id>/delete", methods=["POST"])
@login_required
def delete_atividade(atividade_id):
    atv = Atividade.query.get_or_404(atividade_id)
    cenario_id = atv.cenario_id
    cenario = Cenario.query.get(cenario_id) if cenario_id else None
    fase = get_fase_for_cenario_or_none(cenario) if cenario else None
    db.session.delete(atv)
    db.session.commit()
    flash("Atividade excluída")
    if cenario_id and fase:
        return redirect(
            url_for(
                "atividades_por_cenario",
                projeto_id=fase.projeto_id,
                fase_id=fase.id,
                cenario_id=cenario_id,
            )
        )
    return redirect(url_for("projetos"))


@app.route("/atividades/<int:atividade_id>/liberar", methods=["POST"])
@login_required
def liberar_atividade(atividade_id):
    atv = Atividade.query.get_or_404(atividade_id)
    cenario = Cenario.query.get(atv.cenario_id) if atv.cenario_id else None
    fase = get_fase_for_cenario_or_none(cenario) if cenario else None
    if not atv.data_liberacao:
        atv.data_liberacao = datetime.now()
        db.session.commit()
        flash("Atividade liberada")
    else:
        flash("Atividade já está liberada")
    if atv.cenario_id and fase:
        return redirect(
            url_for(
                "atividades_por_cenario",
                projeto_id=fase.projeto_id,
                fase_id=fase.id,
                cenario_id=atv.cenario_id,
            )
        )
    return redirect(url_for("projetos"))


@app.route(
    "/projetos/<int:projeto_id>/fases/<int:fase_id>/cenarios/<int:cenario_id>/delete",
    methods=["POST"],
)
@login_required
def delete_cenario(projeto_id, fase_id, cenario_id):
    if not is_project_member(projeto_id):
        abort(403)
    Fase.query.filter_by(id=fase_id, projeto_id=projeto_id).first_or_404()
    c = Cenario.query.filter_by(id=cenario_id, fase_id=fase_id).first_or_404()
    # remover atividades vinculadas
    Atividade.query.filter_by(cenario_id=cenario_id).delete()
    db.session.delete(c)
    db.session.commit()
    flash("Cenário excluído", "success")
    return redirect(url_for("cenarios_por_fase", projeto_id=projeto_id, fase_id=fase_id))


@app.route("/concluir/<int:atividade_id>", methods=["POST"])
@login_required
def concluir_atividade(atividade_id):
    atv = Atividade.query.get_or_404(atividade_id)
    cenario = Cenario.query.get(atv.cenario_id) if atv.cenario_id else None
    fase = get_fase_for_cenario_or_none(cenario) if cenario else None

    def redirect_cenario():
        if cenario and fase:
            return redirect(
                url_for(
                    "atividades_por_cenario",
                    projeto_id=fase.projeto_id,
                    fase_id=fase.id,
                    cenario_id=cenario.id,
                )
            )
        return redirect(url_for("projetos"))

    # Segurança: apenas o responsável pode concluir
    if atv.responsavel != current_user.username:
        flash("Apenas o responsável pode concluir esta atividade", "error")
        return redirect_cenario()

    # Deve estar liberada
    if not atv.data_liberacao:
        flash("Atividade ainda não está liberada")
        return redirect_cenario()

    atv.data_conclusao = datetime.now()
    db.session.commit()
    flash("Atividade concluída com sucesso")

    # Liberar automaticamente a próxima atividade (mesmo cenário, próximo número sequencial)
    if atv.cenario_id is not None:
        prox = (
            Atividade.query
            .filter(Atividade.cenario_id == atv.cenario_id)
            .filter(Atividade.numero_sequencial > atv.numero_sequencial)
            .order_by(Atividade.numero_sequencial)
            .first()
        )
        if prox and not prox.data_liberacao:
            prox.data_liberacao = datetime.now()
            db.session.commit()
            flash(f"Próxima atividade '{prox.descricao}' liberada")

        return redirect_cenario()

    return redirect(url_for("projetos"))


@app.route("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return "OK"


# ------------------------------------------------------------------------------
# ENTRYPOINT
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
