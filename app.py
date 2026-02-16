import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
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

# Carregar secrets do Google Secret Manager (se em produção no GCP)
try:
    from load_secrets import load_secrets
    load_secrets()
except ImportError:
    pass  # load_secrets.py não disponível (dev local)
except Exception as e:
    print(f"[WARN] Erro ao carregar secrets: {e}")

# Se ainda não houver DB_PASS, tentar ler arquivo de secret do Cloud Run
if not os.environ.get("DB_PASS"):
    try:
        secret_path = "/var/run/secrets/cloud.google.com/secret/db-pass/latest"
        if os.path.exists(secret_path):
            with open(secret_path, "r") as f:
                db_pass_value = f.read().strip()
                if db_pass_value:
                    os.environ["DB_PASS"] = db_pass_value
                    print("[OK] DB_PASS carregado de arquivo de secret")
    except Exception as e:
        print(f"[WARN] Erro ao carregar DB_PASS de arquivo: {e}")

# Se ainda não houver SECRET_KEY, tentar ler arquivo de secret do Cloud Run
if not os.environ.get("SECRET_KEY"):
    try:
        secret_path = "/var/run/secrets/cloud.google.com/secret/secret-key/latest"
        if os.path.exists(secret_path):
            with open(secret_path, "r") as f:
                secret_key_value = f.read().strip()
                if secret_key_value:
                    os.environ["SECRET_KEY"] = secret_key_value
                    print("[OK] SECRET_KEY carregado de arquivo de secret")
    except Exception as e:
        print(f"[WARN] Erro ao carregar SECRET_KEY de arquivo: {e}")

# Criar app Flask ANTES de usar variáveis de ambiente
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-secreta-dev")


def get_secret_or_env(key, default=""):
    """Obtém secret de variável de ambiente, arquivo Cloud Run, ou padrão"""
    # Tentar ambiente
    value = os.environ.get(key)
    if value:
        print(f"[DEBUG get_secret_or_env] {key} carregado de os.environ")
        return value
    
    # Tentar arquivo de secret do Cloud Run (/var/run/secrets/cloud.google.com/secret/{secret_name}/latest)
    secret_path = f"/var/run/secrets/cloud.google.com/secret/{key.lower().replace('_', '-')}/latest"
    print(f"[DEBUG get_secret_or_env] Tentando ler {key} de {secret_path}")
    if os.path.exists(secret_path):
        try:
            with open(secret_path, "r") as f:
                value = f.read().strip()
                print(f"[OK] {key} carregado de arquivo Cloud Run")
                return value
        except Exception as e:
            print(f"[ERROR get_secret_or_env] Erro ao ler secret {key} de arquivo: {e}")
    else:
        print(f"[DEBUG get_secret_or_env] Arquivo nao existe: {secret_path}")
    
    # Tentar format alternativo de Cloud Run secret
    alt_path = f"/var/run/secrets/google.com/secret_{key.lower()}"
    if os.path.exists(alt_path):
        try:
            with open(alt_path, "r") as f:
                value = f.read().strip()
                print(f"[OK] {key} carregado de {alt_path}")
                return value
        except Exception as e:
            print(f"[WARN] Erro ao ler de {alt_path}: {e}")
    
    print(f"[WARN get_secret_or_env] {key} nao encontrado, usando default")
    return default


def env_truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


app.config["APP_BASE_URL"] = get_secret_or_env("APP_BASE_URL", "").rstrip("/")
app.config["SMTP_HOST"] = get_secret_or_env("SMTP_HOST")
app.config["SMTP_PORT"] = get_secret_or_env("SMTP_PORT", "")
app.config["SMTP_USER"] = get_secret_or_env("SMTP_USER")
app.config["SMTP_PASS"] = get_secret_or_env("SMTP_PASS")
app.config["SMTP_FROM"] = get_secret_or_env("SMTP_FROM")
app.config["SMTP_USE_TLS"] = env_truthy(get_secret_or_env("SMTP_USE_TLS", "true"))
app.config["SMTP_USE_SSL"] = env_truthy(get_secret_or_env("SMTP_USE_SSL", "false"))
app.config["EMAIL_CONFIRM_MINUTES"] = int(get_secret_or_env("EMAIL_CONFIRM_MINUTES", "60"))

# Debug: Show SMTP configuration loaded
if app.config.get("SMTP_HOST"):
    print(f"[OK] SMTP_HOST={app.config.get('SMTP_HOST')}")
    print(f"[OK] SMTP_PORT={app.config.get('SMTP_PORT')}")
    print(f"[OK] SMTP_USER={app.config.get('SMTP_USER')}")
    print(f"[OK] SMTP_USE_SSL={app.config.get('SMTP_USE_SSL')}")
else:
    print("[WARN] SMTP_HOST nao configurado em app.config")

# Tentar carregar variáveis de ambiente com valores padrão
db_user = get_secret_or_env("DB_USER", "")
db_pass = get_secret_or_env("DB_PASS", "")
db_name = get_secret_or_env("DB_NAME", "")
cloud_sql_connection_name = get_secret_or_env("CLOUD_SQL_CONNECTION_NAME", "")

# DEBUG: Log das variáveis (remover em produção)
if db_user:
    print(f"[OK] DB_USER={db_user}")
if db_name:
    print(f"[OK] DB_NAME={db_name}")
if cloud_sql_connection_name:
    print(f"[OK] CLOUD_SQL_CONNECTION_NAME={cloud_sql_connection_name}")
if db_pass:
    print(f"[OK] DB_PASS carregado ({len(db_pass)} caracteres)")
else:
    print("[WARN] DB_PASS está vazio!")

# DATABASE CONFIG
if os.environ.get("DATABASE_URL"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    print("[OK] Usando DATABASE_URL")
elif db_user and db_pass and db_name and cloud_sql_connection_name:
    db_pass_encoded = quote_plus(db_pass)  # URL-encode the password
    app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql+psycopg2://{db_user}:{db_pass_encoded}@/{db_name}?host=/cloudsql/{cloud_sql_connection_name}"
    print("[OK] Conectando ao Cloud SQL")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///dev.db"
    print("[OK] Usando SQLite local")

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
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verification_token_hash = db.Column(db.String(255))
    email_verification_expires_at = db.Column(db.DateTime)
    password_reset_token_hash = db.Column(db.String(255))
    password_reset_expires_at = db.Column(db.DateTime)


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


class LicaoAprendida(db.Model):
    __tablename__ = "licoes_aprendidas"

    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey("projetos.id"), nullable=False)
    fase_id = db.Column(db.Integer, db.ForeignKey("fases.id"), nullable=True)
    categoria = db.Column(db.String(100))  # Ex: Técnica, Gestão, Comunicação
    tipo = db.Column(db.String(50))  # Ex: Sucesso, Problema, Oportunidade
    descricao = db.Column(db.Text, nullable=False)
    causa_raiz = db.Column(db.Text)
    impacto = db.Column(db.Text)
    acao_tomada = db.Column(db.Text)
    recomendacao = db.Column(db.Text)
    responsavel = db.Column(db.String(100))
    status = db.Column(db.String(50))  # Ex: Registrada, Em Análise, Aplicada
    aplicavel_futuros = db.Column(db.Boolean, default=True)
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    projeto = db.relationship("Projeto", backref=db.backref("licoes_aprendidas", lazy=True))
    fase = db.relationship("Fase", backref=db.backref("licoes_aprendidas", lazy=True))


class SolicitacaoMudanca(db.Model):
    __tablename__ = "solicitacoes_mudanca"

    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey("projetos.id"), nullable=False)
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    solicitante = db.Column(db.String(100))
    area_solicitante = db.Column(db.String(100))
    descricao = db.Column(db.Text, nullable=False)
    justificativa = db.Column(db.Text)
    tipo_mudanca = db.Column(db.String(50))  # Escopo, Legal, Técnica, Melhoria, Correção, Integração
    impacto_prazo = db.Column(db.String(100))
    impacto_custo = db.Column(db.String(100))
    impacto_escopo = db.Column(db.String(50))  # Baixo, Médio, Alto
    impacto_recursos = db.Column(db.String(200))
    impacto_risco = db.Column(db.String(50))  # Baixo, Médio, Alto
    prioridade = db.Column(db.String(50))  # Baixa, Média, Alta, Crítica
    recomendacao_pm = db.Column(db.String(50))  # Aprovar, Rejeitar, Postergar
    status = db.Column(db.String(50))  # Em análise, Aprovada, Rejeitada, Em implementação, Concluída
    aprovador = db.Column(db.String(100))
    data_decisao = db.Column(db.DateTime)
    data_implementacao = db.Column(db.DateTime)
    observacoes = db.Column(db.Text)
    
    projeto = db.relationship("Projeto", backref=db.backref("solicitacoes_mudanca", lazy=True))


class Incidente(db.Model):
    __tablename__ = "incidentes"

    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey("projetos.id"), nullable=False)
    atividade_id = db.Column(db.Integer, db.ForeignKey("atividades.id"), nullable=True)
    descricao = db.Column(db.Text, nullable=False)
    acompanhamento = db.Column(db.Text)
    responsavel = db.Column(db.String(100))
    prioridade = db.Column(db.String(50))  # 1 - Muito Alto, 2 - Alto, 3 - Médio, 4 - Baixo, 5 - Muito Baixo
    status = db.Column(db.String(50))  # Criado, Em andamento, Aguardando Solicitante, Aguardando Externo, Encaminhado Responsavel, Proposta de solução, Concluído
    previsao_original = db.Column(db.DateTime)
    previsao_revisada = db.Column(db.DateTime)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_ultima_modificacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    conclusao = db.Column(db.DateTime)
    
    projeto = db.relationship("Projeto", backref=db.backref("incidentes", lazy=True))
    atividade = db.relationship("Atividade", backref=db.backref("incidentes", lazy=True))


class Risco(db.Model):
    __tablename__ = "riscos"

    id = db.Column(db.Integer, primary_key=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey("projetos.id"), nullable=False)
    area = db.Column(db.String(100))
    tipo_risco = db.Column(db.String(50))  # Ameaca, Oportunidade
    risco = db.Column(db.Text, nullable=False)
    criado_por = db.Column(db.String(100))
    responsavel = db.Column(db.String(100))
    gatilho = db.Column(db.Text)
    impacto_projeto = db.Column(db.Text)
    consequencia = db.Column(db.Text)
    impacto = db.Column(db.String(10))  # 1-5
    probabilidade = db.Column(db.String(10))  # 1-5
    nivel_risco = db.Column(db.String(50))  # 1 - Muito Alto, 2 - Alto, 3 - Medio, 4 - Baixo, 5 - Muito Baixo
    estrategia = db.Column(db.String(50))
    prevencao = db.Column(db.Text)
    contingencia = db.Column(db.Text)
    acompanhamento = db.Column(db.Text)
    status = db.Column(db.String(50))  # Concluido, Planejado, Iniciado, Parado
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_proxima_acao = db.Column(db.DateTime)
    data_conclusao = db.Column(db.DateTime)

    projeto = db.relationship("Projeto", backref=db.backref("riscos", lazy=True))


class Perfil(db.Model):
    __tablename__ = "perfis"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    projeto_id = db.Column(db.Integer, db.ForeignKey("projetos.id"), nullable=False)
    projeto = db.relationship("Projeto", backref=db.backref("perfis", lazy=True))
    
    # Permissões
    pode_criar_atividade = db.Column(db.Boolean, default=True)
    pode_editar_atividade = db.Column(db.Boolean, default=True)
    pode_excluir_atividade = db.Column(db.Boolean, default=False)
    pode_concluir_qualquer_atividade = db.Column(db.Boolean, default=False)
    pode_editar_projeto = db.Column(db.Boolean, default=False)
    pode_gerenciar_membros = db.Column(db.Boolean, default=False)
    
    # Permissões de Lições Aprendidas
    pode_criar_licao = db.Column(db.Boolean, default=False)
    pode_editar_licao = db.Column(db.Boolean, default=False)
    pode_excluir_licao = db.Column(db.Boolean, default=False)
    
    # Permissões de Solicitações de Mudança
    pode_criar_mudanca = db.Column(db.Boolean, default=False)
    pode_editar_mudanca = db.Column(db.Boolean, default=False)
    pode_excluir_mudanca = db.Column(db.Boolean, default=False)
    
    # Permissões de Incidentes
    pode_criar_incidente = db.Column(db.Boolean, default=False)
    pode_editar_incidente = db.Column(db.Boolean, default=False)
    pode_excluir_incidente = db.Column(db.Boolean, default=False)

    # Permissões de Riscos
    pode_criar_risco = db.Column(db.Boolean, default=False)
    pode_editar_risco = db.Column(db.Boolean, default=False)
    pode_excluir_risco = db.Column(db.Boolean, default=False)
    
    is_default = db.Column(db.Boolean, default=False)  # Para perfis padrão


class MembroPerfil(db.Model):
    __tablename__ = "membro_perfis"

    id = db.Column(db.Integer, primary_key=True)
    projeto_membro_id = db.Column(db.Integer, db.ForeignKey("projeto_membros.id"), nullable=False)
    perfil_id = db.Column(db.Integer, db.ForeignKey("perfis.id"), nullable=False)
    
    projeto_membro = db.relationship("ProjetoMembro", backref=db.backref("perfil_associacao", lazy=True))
    perfil = db.relationship("Perfil", backref=db.backref("membros", lazy=True))


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


def get_user_permissions(projeto_id, user_id=None):
    """Retorna as permissões do usuário no projeto"""
    uid = user_id or current_user.id
    membro = ProjetoMembro.query.filter_by(projeto_id=projeto_id, user_id=uid).first()
    
    if not membro:
        return None
    
    # Buscar perfil do membro
    perfil_associacao = MembroPerfil.query.filter_by(projeto_membro_id=membro.id).first()
    
    if perfil_associacao and perfil_associacao.perfil:
        return perfil_associacao.perfil
    
    return None


def has_permission(projeto_id, permission_name, user_id=None):
    """Verifica se o usuário tem uma permissão específica no projeto"""
    perfil = get_user_permissions(projeto_id, user_id)
    
    if not perfil:
        return False

    if perfil.nome == "Administrador":
        return True
    
    return getattr(perfil, permission_name, False)


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
def criar_tabelas():
    """
    Cria todas as tabelas do banco de dados automaticamente.
    Safe para executar múltiplas vezes (é idempotente).
    Executado no startup da aplicação.
    """
    try:
        db.create_all()
        print("[OK] Banco de dados inicializado com sucesso")
        
        # Verificar e adicionar colunas faltando na tabela perfis (para backward compatibility)
        adicionar_colunas_faltando()
        
    except Exception as e:
        print(f"[WARN] Aviso ao inicializar DB: {e}")
        # Não quebra a aplicação se falhar


def adicionar_colunas_faltando():
    """
    Verifica se as colunas de permissões existem na tabela perfis.
    Se não existirem, as cria (para compatibilidade com bancos antigos).
    """
    try:
        inspector = inspect(db.engine)
        colunas_existentes = [c["name"] for c in inspector.get_columns("perfis")]
        
        # Colunas que deveriam existir
        colunas_necessarias = {
            "pode_criar_licao": "ALTER TABLE perfis ADD COLUMN pode_criar_licao BOOLEAN DEFAULT false",
            "pode_editar_licao": "ALTER TABLE perfis ADD COLUMN pode_editar_licao BOOLEAN DEFAULT false",
            "pode_excluir_licao": "ALTER TABLE perfis ADD COLUMN pode_excluir_licao BOOLEAN DEFAULT false",
            "pode_criar_mudanca": "ALTER TABLE perfis ADD COLUMN pode_criar_mudanca BOOLEAN DEFAULT false",
            "pode_editar_mudanca": "ALTER TABLE perfis ADD COLUMN pode_editar_mudanca BOOLEAN DEFAULT false",
            "pode_excluir_mudanca": "ALTER TABLE perfis ADD COLUMN pode_excluir_mudanca BOOLEAN DEFAULT false",
            "pode_criar_incidente": "ALTER TABLE perfis ADD COLUMN pode_criar_incidente BOOLEAN DEFAULT false",
            "pode_editar_incidente": "ALTER TABLE perfis ADD COLUMN pode_editar_incidente BOOLEAN DEFAULT false",
            "pode_excluir_incidente": "ALTER TABLE perfis ADD COLUMN pode_excluir_incidente BOOLEAN DEFAULT false",
            "pode_criar_risco": "ALTER TABLE perfis ADD COLUMN pode_criar_risco BOOLEAN DEFAULT false",
            "pode_editar_risco": "ALTER TABLE perfis ADD COLUMN pode_editar_risco BOOLEAN DEFAULT false",
            "pode_excluir_risco": "ALTER TABLE perfis ADD COLUMN pode_excluir_risco BOOLEAN DEFAULT false",
        }
        
        # Adicionar colunas que faltam
        for coluna, sql in colunas_necessarias.items():
            if coluna not in colunas_existentes:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                    print(f"[OK] Coluna {coluna} adicionada com sucesso")
                except Exception as e:
                    db.session.rollback()
                    # Coluna pode já existir ou houve outro erro, continua
                    if "duplicate column" not in str(e).lower():
                        print(f"[WARN] Erro ao adicionar {coluna}: {e}")

        # Colunas de users para confirmacao de e-mail
        colunas_users_existentes = [c["name"] for c in inspector.get_columns("users")]
        colunas_users_necessarias = {
            "email_verified": ("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT false", "ALTER TABLE users ADD COLUMN email_verified SMALLINT DEFAULT 0"),
            "email_verification_token_hash": ("ALTER TABLE users ADD COLUMN email_verification_token_hash TEXT", "ALTER TABLE users ADD COLUMN email_verification_token_hash VARCHAR(255)"),
            "email_verification_expires_at": ("ALTER TABLE users ADD COLUMN email_verification_expires_at TIMESTAMP", "ALTER TABLE users ADD COLUMN email_verification_expires_at TIMESTAMP"),
            "password_reset_token_hash": ("ALTER TABLE users ADD COLUMN password_reset_token_hash TEXT", "ALTER TABLE users ADD COLUMN password_reset_token_hash VARCHAR(255)"),
            "password_reset_expires_at": ("ALTER TABLE users ADD COLUMN password_reset_expires_at TIMESTAMP", "ALTER TABLE users ADD COLUMN password_reset_expires_at TIMESTAMP"),
        }
        adicionou_email_verified = False
        for coluna, sqls in colunas_users_necessarias.items():
            if coluna not in colunas_users_existentes:
                sql = sqls[0]  # SQLite syntax
                sql_pg = sqls[1]  # PostgreSQL syntax
                try:
                    try:
                        db.session.execute(text(sql))
                        db.session.commit()
                    except Exception as e1:
                        # Tenta sintaxe PostgreSQL se SQLite falhar
                        if "postgresql" in str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).lower():
                            db.session.rollback()
                            db.session.execute(text(sql_pg))
                            db.session.commit()
                        else:
                            raise e1
                    
                    if coluna == "email_verified":
                        adicionou_email_verified = True
                    print(f"[OK] Coluna users.{coluna} adicionada com sucesso")
                except Exception as e:
                    db.session.rollback()
                    if "duplicate column" not in str(e).lower() and "already exists" not in str(e).lower():
                        print(f"[WARN] Erro ao adicionar users.{coluna}: {e}")
                    else:
                        print(f"[OK] Coluna users.{coluna} ja existe")

        if adicionou_email_verified:
            try:
                db.session.execute(text("UPDATE users SET email_verified = true"))
                db.session.commit()
                print("[OK] Usuarios existentes marcados como verificados")
            except Exception as e:
                db.session.rollback()
                print(f"[WARN] Erro ao atualizar email_verified: {e}")
    except Exception as e:
        print(f"[WARN] Erro ao verificar colunas: {e}")
        # Não quebra a aplicação


def build_external_url(path):
    base_url = app.config.get("APP_BASE_URL") or request.url_root.rstrip("/")
    return f"{base_url}{path}"


def send_email(to_email, subject, body):
    host = app.config.get("SMTP_HOST")
    port_value = app.config.get("SMTP_PORT")
    use_ssl = app.config.get("SMTP_USE_SSL")
    use_tls = app.config.get("SMTP_USE_TLS")
    smtp_user = app.config.get("SMTP_USER")
    smtp_pass = app.config.get("SMTP_PASS")
    smtp_from = app.config.get("SMTP_FROM")
    
    print(f"[DEBUG send_email] HOST={host}, PORT={port_value}, USER={smtp_user}, SSL={use_ssl}, TLS={use_tls}")
    
    if not host:
        raise RuntimeError("SMTP_HOST nao configurado")

    if port_value:
        try:
            port = int(port_value)
        except ValueError as e:
            print(f"[ERROR] SMTP_PORT invalido: {port_value} - {e}")
            raise RuntimeError(f"SMTP_PORT nao e inteiro: {port_value}")
    else:
        port = 465 if use_ssl else 587

    smtp_user = app.config.get("SMTP_USER")
    smtp_pass = app.config.get("SMTP_PASS")
    smtp_from = app.config.get("SMTP_FROM") or smtp_user

    if not smtp_from:
        raise RuntimeError("SMTP_FROM nao configurado")

    if not smtp_user:
        raise RuntimeError("SMTP_USER nao configurado")
    
    if not smtp_pass:
        raise RuntimeError("SMTP_PASS nao configurado")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = to_email
    message.set_content(body)

    try:
        if use_ssl:
            print(f"[DEBUG] Conectando com SMTP_SSL a {host}:{port}")
            with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
                print(f"[DEBUG] Conectado, fazendo login como {smtp_user}")
                if smtp_user and smtp_pass:
                    smtp.login(smtp_user, smtp_pass)
                print(f"[DEBUG] Login bem-sucedido, enviando mensagem")
                smtp.send_message(message)
            print(f"[DEBUG] Email enviado com sucesso para {to_email}")
            return

        print(f"[DEBUG] Conectand com SMTP a {host}:{port}")
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            if use_tls:
                print(f"[DEBUG] Iniciando STARTTLS")
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if smtp_user and smtp_pass:
                print(f"[DEBUG] Fazendo login como {smtp_user}")
                smtp.login(smtp_user, smtp_pass)
            print(f"[DEBUG] Enviando mensagem para {to_email}")
            smtp.send_message(message)
        print(f"[DEBUG] Email enviado com sucesso para {to_email}")
    except Exception as e:
        print(f"[ERROR] Erro ao enviar email: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise


def generate_email_confirmation(user):
    token = secrets.token_urlsafe(32)
    user.email_verification_token_hash = generate_password_hash(token)
    user.email_verification_expires_at = datetime.utcnow() + timedelta(
        minutes=app.config.get("EMAIL_CONFIRM_MINUTES", 60)
    )
    return token


def send_confirmation_email(user, token):
    confirm_path = url_for("confirm_email", uid=user.id, token=token)
    confirm_link = build_external_url(confirm_path)
    body = (
        "Ola,\n\n"
        "Confirme seu e-mail para ativar sua conta IMSIS:\n"
        f"{confirm_link}\n\n"
        "Se voce nao solicitou, ignore este e-mail.\n"
    )
    send_email(user.email, "Confirmacao de e-mail - IMSIS", body)


def generate_password_reset(user):
    token = secrets.token_urlsafe(32)
    user.password_reset_token_hash = generate_password_hash(token)
    user.password_reset_expires_at = datetime.utcnow() + timedelta(
        minutes=app.config.get("EMAIL_CONFIRM_MINUTES", 60)
    )
    return token


def send_password_reset_email(user, token):
    reset_path = url_for("reset_password", uid=user.id, token=token)
    reset_link = build_external_url(reset_path)
    body = (
        "Ola,\n\n"
        "Clique no link abaixo para redefinir sua senha:\n"
        f"{reset_link}\n\n"
        "Se voce nao solicitou, ignore este e-mail.\n"
        "Este link expira em 60 minutos.\n"
    )
    send_email(user.email, "Recuperacao de senha - IMSIS", body)


# 🔥 Inicializa o banco de dados automaticamente quando a app inicia
with app.app_context():
    criar_tabelas()


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


@app.route("/check-columns")
def check_columns():
    """Debug endpoint para verificar colunas do banco"""
    try:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        
        if "users" not in inspector.get_table_names():
            return "ERRO: Tabela 'users' nao existe", 500
        
        colunas = [c["name"] for c in inspector.get_columns("users")]
        
        necessarias = [
            "id", "username", "email", "password",
            "email_verified", "email_verification_token_hash", "email_verification_expires_at",
            "password_reset_token_hash", "password_reset_expires_at"
        ]
        
        faltam = [c for c in necessarias if c not in colunas]
        
        if faltam:
            return f"ERRO: Faltam colunas: {faltam}. Ejecute: python migrate.py", 500
        
        return f"OK: Todas as colunas existem. Total: {len(colunas)} colunas. {colunas}"
    except Exception as e:
        return f"ERRO ao verificar colunas: {e}", 500



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
            email_verified=False,
        )
        db.session.add(user)
        db.session.flush()

        token = generate_email_confirmation(user)
        db.session.commit()

        try:
            send_confirmation_email(user, token)
            flash("Cadastro criado. Verifique seu e-mail para confirmar a conta.")
        except Exception as e:
            print(f"[WARN] Erro ao enviar e-mail de confirmacao: {e}")
            flash(
                "Cadastro criado, mas nao foi possivel enviar o e-mail de confirmacao. "
                "Use 'Reenviar confirmacao' no login."
            )

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            email = request.form.get("email")
            password = request.form.get("password")

            user = User.query.filter_by(email=email).first()

            if not user or not check_password_hash(user.password, password):
                flash("Usuário ou senha inválidos")
                return redirect(url_for("login"))

            if not user.email_verified:
                flash("Confirme seu e-mail antes de entrar.")
                return redirect(url_for("resend_confirmation", email=email))

            login_user(user)
            return redirect(url_for("projetos"))
        except Exception as e:
            print(f"[ERROR] Erro no login: {e}")
            import traceback
            traceback.print_exc()
            flash("Erro ao fazer login. Tente novamente.")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/confirm-email")
def confirm_email():
    uid = request.args.get("uid", type=int)
    token = request.args.get("token", "")

    if not uid or not token:
        flash("Link de confirmacao invalido")
        return redirect(url_for("login"))

    user = User.query.get(uid)
    if not user:
        flash("Link de confirmacao invalido")
        return redirect(url_for("login"))

    if user.email_verified:
        flash("E-mail ja confirmado")
        return redirect(url_for("login"))

    if not user.email_verification_token_hash:
        flash("Link de confirmacao invalido")
        return redirect(url_for("login"))

    if not user.email_verification_expires_at or user.email_verification_expires_at < datetime.utcnow():
        flash("Link expirou. Reenvie a confirmacao.")
        return redirect(url_for("resend_confirmation", email=user.email))

    if not check_password_hash(user.email_verification_token_hash, token):
        flash("Link de confirmacao invalido")
        return redirect(url_for("login"))

    user.email_verified = True
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    db.session.commit()

    flash("E-mail confirmado com sucesso. Voce ja pode entrar.")
    return redirect(url_for("login"))


@app.route("/resend-confirmation", methods=["GET", "POST"])
def resend_confirmation():
    if request.method == "POST":
        email = request.form.get("email")
        if not email:
            flash("Informe seu e-mail")
            return redirect(url_for("resend_confirmation"))

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Se o e-mail existir, enviaremos um novo link.")
            return redirect(url_for("login"))

        if user.email_verified:
            flash("E-mail ja confirmado. Voce pode entrar.")
            return redirect(url_for("login"))

        token = generate_email_confirmation(user)
        db.session.commit()

        try:
            send_confirmation_email(user, token)
            flash("Enviamos um novo link de confirmacao para o seu e-mail.")
        except Exception as e:
            print(f"[WARN] Erro ao reenviar e-mail de confirmacao: {e}")
            flash("Nao foi possivel enviar o e-mail de confirmacao. Tente novamente.")

        return redirect(url_for("login"))

    prefill_email = request.args.get("email", "")
    return render_template("resend_confirmation.html", email=prefill_email)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        if not email:
            flash("Informe seu e-mail")
            return redirect(url_for("forgot_password"))

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Se o e-mail existir, enviaremos um link de recuperacao.")
            return redirect(url_for("login"))

        token = generate_password_reset(user)
        db.session.commit()

        try:
            send_password_reset_email(user, token)
            flash("Enviamos um link de recuperacao para o seu e-mail.")
        except Exception as e:
            print(f"[WARN] Erro ao enviar e-mail de recuperacao de senha: {e}")
            flash("Nao foi possivel enviar o e-mail. Tente novamente.")

        return redirect(url_for("login"))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    uid = request.args.get("uid", type=int)
    token = request.args.get("token", "")

    if request.method == "GET":
        if not uid or not token:
            flash("Link de recuperacao invalido")
            return redirect(url_for("login"))

        user = User.query.get(uid)
        if not user:
            flash("Link de recuperacao invalido")
            return redirect(url_for("login"))

        if not user.password_reset_token_hash:
            flash("Link de recuperacao invalido")
            return redirect(url_for("login"))

        if not user.password_reset_expires_at or user.password_reset_expires_at < datetime.utcnow():
            flash("Link expirou. Solicite um novo.")
            return redirect(url_for("forgot_password"))

        if not check_password_hash(user.password_reset_token_hash, token):
            flash("Link de recuperacao invalido")
            return redirect(url_for("login"))

        return render_template("reset_password.html", uid=uid, token=token)

    # POST request
    new_password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    if not uid or not token:
        flash("Link de recuperacao invalido")
        return redirect(url_for("login"))

    if not new_password or not confirm_password:
        flash("Informe a nova senha")
        return redirect(url_for("reset_password", uid=uid, token=token))

    if new_password != confirm_password:
        flash("As senhas nao conferem")
        return redirect(url_for("reset_password", uid=uid, token=token))

    if len(new_password) < 6:
        flash("A senha deve ter pelo menos 6 caracteres")
        return redirect(url_for("reset_password", uid=uid, token=token))

    user = User.query.get(uid)
    if not user or not check_password_hash(user.password_reset_token_hash, token):
        flash("Link de recuperacao invalido")
        return redirect(url_for("login"))

    user.password = generate_password_hash(new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    db.session.commit()

    flash("Senha alterada com sucesso. Voce pode entrar.")
    return redirect(url_for("login"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/health")
def health():
    """Health check endpoint - sem autenticação"""
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}, 200
    except Exception as e:
        return {"status": "error", "db": str(e)}, 500


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
            
            # Criar perfis padrão
            perfil_admin = Perfil(
                nome="Administrador",
                projeto_id=projeto.id,
                pode_criar_atividade=True,
                pode_editar_atividade=True,
                pode_excluir_atividade=True,
                pode_concluir_qualquer_atividade=True,
                pode_editar_projeto=True,
                pode_gerenciar_membros=True,
                pode_criar_licao=True,
                pode_editar_licao=True,
                pode_excluir_licao=True,
                pode_criar_mudanca=True,
                pode_editar_mudanca=True,
                pode_excluir_mudanca=True,
                pode_criar_incidente=True,
                pode_editar_incidente=True,
                pode_excluir_incidente=True,
                pode_criar_risco=True,
                pode_editar_risco=True,
                pode_excluir_risco=True,
                is_default=True
            )
            perfil_membro = Perfil(
                nome="Membro",
                projeto_id=projeto.id,
                pode_criar_atividade=True,
                pode_editar_atividade=True,
                pode_excluir_atividade=False,
                pode_concluir_qualquer_atividade=False,
                pode_editar_projeto=False,
                pode_gerenciar_membros=False,
                pode_criar_licao=True,
                pode_editar_licao=True,
                pode_excluir_licao=False,
                pode_criar_mudanca=True,
                pode_editar_mudanca=True,
                pode_excluir_mudanca=False,
                pode_criar_incidente=True,
                pode_editar_incidente=True,
                pode_excluir_incidente=True,
                pode_criar_risco=True,
                pode_editar_risco=True,
                pode_excluir_risco=True,
                is_default=True
            )
            db.session.add(perfil_admin)
            db.session.add(perfil_membro)
            db.session.flush()
            
            # Adicionar membros
            membros = {int(mid) for mid in membros_ids if mid.isdigit()}
            membros.add(current_user.id)
            
            for uid in membros:
                membro = ProjetoMembro(projeto_id=projeto.id, user_id=uid)
                db.session.add(membro)
                db.session.flush()
                
                # Criador é admin, outros são membros
                if uid == current_user.id:
                    db.session.add(MembroPerfil(projeto_membro_id=membro.id, perfil_id=perfil_admin.id))
                else:
                    db.session.add(MembroPerfil(projeto_membro_id=membro.id, perfil_id=perfil_membro.id))
            
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

    if not has_permission(projeto_id, "pode_gerenciar_membros"):
        abort(403)

    user_id = request.form.get("user_id")
    if user_id and user_id.isdigit():
        uid = int(user_id)
        if User.query.get(uid) and not ProjetoMembro.query.filter_by(projeto_id=projeto_id, user_id=uid).first():
            membro = ProjetoMembro(projeto_id=projeto_id, user_id=uid)
            db.session.add(membro)
            db.session.flush()
            
            # Atribuir perfil padrão de Membro
            perfil_membro = Perfil.query.filter_by(projeto_id=projeto_id, nome="Membro", is_default=True).first()
            if perfil_membro:
                db.session.add(MembroPerfil(projeto_membro_id=membro.id, perfil_id=perfil_membro.id))
            
            db.session.commit()
            flash("Membro adicionado com sucesso")
    return redirect(url_for("projetos"))


@app.route("/projetos/<int:projeto_id>/membros/remover", methods=["POST"])
@login_required
def remover_membro_projeto(projeto_id):
    Projeto.query.get_or_404(projeto_id)
    if not is_project_member(projeto_id):
        abort(403)

    if not has_permission(projeto_id, "pode_gerenciar_membros"):
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
        pode_concluir_qualquer=has_permission(projeto_id, 'pode_concluir_qualquer_atividade'),
        pode_editar_atividade=has_permission(projeto_id, 'pode_editar_atividade'),
        pode_excluir_atividade=has_permission(projeto_id, 'pode_excluir_atividade'),
        pode_gerenciar_membros=has_permission(projeto_id, 'pode_gerenciar_membros'),
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

    if not has_permission(projeto_id, "pode_editar_atividade"):
        flash("Você não tem permissão para editar atividades", "error")
        return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id, cenario=cenario_id))
    
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

    if not has_permission(projeto_id, "pode_excluir_atividade"):
        flash("Você não tem permissão para excluir atividades", "error")
        return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id, cenario=cenario_id))
    
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
    
    # Verificar se tem permissão para concluir qualquer atividade
    pode_concluir_qualquer = has_permission(projeto_id, 'pode_concluir_qualquer_atividade')
    
    if atividade_id:
        atividade = Atividade.query.get_or_404(atividade_id)
        cenario = Cenario.query.get_or_404(atividade.cenario_id)
        fase = Fase.query.get_or_404(cenario.fase_id)
        if fase.projeto_id == projeto_id:
            # Verificar permissões apenas se não for admin
            if not pode_concluir_qualquer:
                # Verificar se é o responsável
                if atividade.responsavel != current_user.username:
                    flash("Apenas o responsável pode concluir esta atividade", "error")
                    return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id, cenario=cenario_id))
                # Verificar se está liberada
                if not atividade.data_liberacao:
                    flash("Atividade ainda não está liberada", "error")
                    return redirect(url_for("fluxo", projeto_id=projeto_id, fase=fase_id, cenario=cenario_id))
            
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


@app.route("/projetos/<int:projeto_id>/reabrir_atividade", methods=["POST"])
@login_required
def fluxo_reabrir_atividade(projeto_id):
    if not is_project_member(projeto_id):
        abort(403)
    
    # Verificar se tem permissão de administrador
    if not has_permission(projeto_id, 'pode_concluir_qualquer_atividade'):
        flash("Apenas administradores podem reabrir atividades", "error")
        return redirect(url_for("fluxo", projeto_id=projeto_id))
    
    atividade_id = request.form.get("atividade_id", type=int)
    fase_id = request.form.get("fase_id", type=int)
    cenario_id = request.form.get("cenario_id", type=int)
    
    if atividade_id:
        atividade = Atividade.query.get_or_404(atividade_id)
        cenario = Cenario.query.get_or_404(atividade.cenario_id)
        fase = Fase.query.get_or_404(cenario.fase_id)
        
        if fase.projeto_id == projeto_id and atividade.data_conclusao:
            atividade.data_conclusao = None
            db.session.commit()
            flash("Atividade reaberta com sucesso", "success")
    
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
        pode_concluir_qualquer=has_permission(projeto_id, 'pode_concluir_qualquer_atividade'),
        pode_editar_atividade=has_permission(projeto_id, 'pode_editar_atividade'),
        pode_excluir_atividade=has_permission(projeto_id, 'pode_excluir_atividade'),
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

    if not has_permission(fase.projeto_id, "pode_editar_atividade"):
        flash("Você não tem permissão para editar atividades", "error")
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

    if not fase or not is_project_member(fase.projeto_id):
        abort(403)

    if not has_permission(fase.projeto_id, "pode_excluir_atividade"):
        flash("Você não tem permissão para excluir atividades", "error")
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

    # Verificar se tem permissão para concluir qualquer atividade
    pode_concluir_qualquer = has_permission(fase.projeto_id, 'pode_concluir_qualquer_atividade')
    
    if not pode_concluir_qualquer:
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


@app.route("/reabrir/<int:atividade_id>", methods=["POST"])
@login_required
def reabrir_atividade(atividade_id):
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

    # Verificar se tem permissão de administrador
    if not has_permission(fase.projeto_id, 'pode_concluir_qualquer_atividade'):
        flash("Apenas administradores podem reabrir atividades", "error")
        return redirect_cenario()
    
    if atv.data_conclusao:
        atv.data_conclusao = None
        db.session.commit()
        flash("Atividade reaberta com sucesso", "success")
    
    return redirect_cenario()


# ------------------------------------------------------------------------------
# GERENCIAR ACESSOS
# ------------------------------------------------------------------------------
@app.route("/projetos/<int:projeto_id>/acessos", methods=["GET", "POST"])
@login_required
def gerenciar_acessos(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    if not is_project_member(projeto_id):
        abort(403)

    if not has_permission(projeto_id, "pode_gerenciar_membros"):
        abort(403)
    
    # Adicionar membro ao projeto
    if request.method == "POST" and request.form.get("action") == "adicionar_membro":
        user_id = request.form.get("user_id")
        perfil_id = request.form.get("perfil_id")
        
        if user_id and perfil_id:
            # Verificar se o usuário já não é membro
            membro_existente = ProjetoMembro.query.filter_by(projeto_id=projeto_id, user_id=int(user_id)).first()
            if membro_existente:
                flash("Usuário já é membro deste projeto", "error")
            else:
                # Adicionar como membro
                novo_membro = ProjetoMembro(projeto_id=projeto_id, user_id=int(user_id))
                db.session.add(novo_membro)
                db.session.flush()  # Para obter o ID do membro
                
                # Atribuir perfil
                db.session.add(MembroPerfil(projeto_membro_id=novo_membro.id, perfil_id=int(perfil_id)))
                db.session.commit()
                flash("Membro adicionado com sucesso", "success")
        return redirect(url_for("gerenciar_acessos", projeto_id=projeto_id, tab="membros"))
    
    # Remover membro do projeto
    if request.method == "POST" and request.form.get("action") == "remover_membro":
        membro_id = request.form.get("membro_id")
        if membro_id:
            membro = ProjetoMembro.query.get(int(membro_id))
            if membro and membro.projeto_id == projeto_id:
                # Remover associações de perfil
                MembroPerfil.query.filter_by(projeto_membro_id=membro.id).delete()
                # Remover membro
                db.session.delete(membro)
                db.session.commit()
                flash("Membro removido com sucesso", "success")
        return redirect(url_for("gerenciar_acessos", projeto_id=projeto_id, tab="membros"))
    
    # Criar novo perfil
    if request.method == "POST" and request.form.get("action") == "criar_perfil":
        nome_perfil = request.form.get("nome_perfil")
        if nome_perfil:
            novo_perfil = Perfil(
                nome=nome_perfil,
                projeto_id=projeto_id,
                pode_criar_atividade=request.form.get("pode_criar_atividade") == "on",
                pode_editar_atividade=request.form.get("pode_editar_atividade") == "on",
                pode_excluir_atividade=request.form.get("pode_excluir_atividade") == "on",
                pode_concluir_qualquer_atividade=request.form.get("pode_concluir_qualquer_atividade") == "on",
                pode_editar_projeto=request.form.get("pode_editar_projeto") == "on",
                pode_gerenciar_membros=request.form.get("pode_gerenciar_membros") == "on",
                pode_criar_licao=request.form.get("pode_criar_licao") == "on",
                pode_editar_licao=request.form.get("pode_editar_licao") == "on",
                pode_excluir_licao=request.form.get("pode_excluir_licao") == "on",
                pode_criar_mudanca=request.form.get("pode_criar_mudanca") == "on",
                pode_editar_mudanca=request.form.get("pode_editar_mudanca") == "on",
                pode_excluir_mudanca=request.form.get("pode_excluir_mudanca") == "on",
                pode_criar_incidente=request.form.get("pode_criar_incidente") == "on",
                pode_editar_incidente=request.form.get("pode_editar_incidente") == "on",
                pode_excluir_incidente=request.form.get("pode_excluir_incidente") == "on",
                pode_criar_risco=request.form.get("pode_criar_risco") == "on",
                pode_editar_risco=request.form.get("pode_editar_risco") == "on",
                pode_excluir_risco=request.form.get("pode_excluir_risco") == "on",
                is_default=False
            )
            db.session.add(novo_perfil)
            db.session.commit()
            flash("Perfil criado com sucesso", "success")
        return redirect(url_for("gerenciar_acessos", projeto_id=projeto_id))
    
    # Atribuir perfil a membro
    if request.method == "POST" and request.form.get("action") == "atribuir_perfil":
        membro_id = request.form.get("membro_id")
        perfil_id = request.form.get("perfil_id")
        if membro_id and perfil_id:
            # Remover perfil anterior
            MembroPerfil.query.filter_by(projeto_membro_id=int(membro_id)).delete()
            # Adicionar novo perfil
            db.session.add(MembroPerfil(projeto_membro_id=int(membro_id), perfil_id=int(perfil_id)))
            db.session.commit()
            flash("Perfil atribuído com sucesso", "success")
        return redirect(url_for("gerenciar_acessos", projeto_id=projeto_id, tab="membros"))
    
    # Editar perfil
    if request.method == "POST" and request.form.get("action") == "editar_perfil":
        perfil_id = request.form.get("perfil_id")
        perfil = Perfil.query.get(perfil_id)
        if perfil and perfil.projeto_id == projeto_id and not perfil.is_default:
            perfil.pode_criar_atividade = request.form.get("pode_criar_atividade") == "on"
            perfil.pode_editar_atividade = request.form.get("pode_editar_atividade") == "on"
            perfil.pode_excluir_atividade = request.form.get("pode_excluir_atividade") == "on"
            perfil.pode_concluir_qualquer_atividade = request.form.get("pode_concluir_qualquer_atividade") == "on"
            perfil.pode_editar_projeto = request.form.get("pode_editar_projeto") == "on"
            perfil.pode_gerenciar_membros = request.form.get("pode_gerenciar_membros") == "on"
            perfil.pode_criar_licao = request.form.get("pode_criar_licao") == "on"
            perfil.pode_editar_licao = request.form.get("pode_editar_licao") == "on"
            perfil.pode_excluir_licao = request.form.get("pode_excluir_licao") == "on"
            perfil.pode_criar_mudanca = request.form.get("pode_criar_mudanca") == "on"
            perfil.pode_editar_mudanca = request.form.get("pode_editar_mudanca") == "on"
            perfil.pode_excluir_mudanca = request.form.get("pode_excluir_mudanca") == "on"
            perfil.pode_criar_incidente = request.form.get("pode_criar_incidente") == "on"
            perfil.pode_editar_incidente = request.form.get("pode_editar_incidente") == "on"
            perfil.pode_excluir_incidente = request.form.get("pode_excluir_incidente") == "on"
            perfil.pode_criar_risco = request.form.get("pode_criar_risco") == "on"
            perfil.pode_editar_risco = request.form.get("pode_editar_risco") == "on"
            perfil.pode_excluir_risco = request.form.get("pode_excluir_risco") == "on"
            db.session.commit()
            flash("Perfil atualizado com sucesso", "success")
        return redirect(url_for("gerenciar_acessos", projeto_id=projeto_id))
    
    # Excluir perfil customizado
    if request.method == "POST" and request.form.get("action") == "excluir_perfil":
        perfil_id = request.form.get("perfil_id")
        perfil = Perfil.query.get(perfil_id)
        if perfil and perfil.projeto_id == projeto_id and not perfil.is_default:
            # Transferir membros para perfil Membro padrão
            perfil_membro_default = Perfil.query.filter_by(projeto_id=projeto_id, nome="Membro", is_default=True).first()
            if perfil_membro_default:
                for mp in perfil.membros:
                    mp.perfil_id = perfil_membro_default.id
            db.session.delete(perfil)
            db.session.commit()
            flash("Perfil excluído com sucesso", "success")
        return redirect(url_for("gerenciar_acessos", projeto_id=projeto_id))
    
    # Obter dados
    perfis = Perfil.query.filter_by(projeto_id=projeto_id).all()
    membros = ProjetoMembro.query.filter_by(projeto_id=projeto_id).all()
    
    # Criar dicionário de perfis por membro
    membros_com_perfil = []
    for membro in membros:
        perfil_atual = None
        if membro.perfil_associacao:
            perfil_atual = membro.perfil_associacao[0].perfil
        membros_com_perfil.append({
            'membro': membro,
            'user': membro.user,
            'perfil': perfil_atual
        })
    
    # Obter usuários que ainda não são membros do projeto
    membros_ids = [m.user_id for m in membros]
    usuarios_disponiveis = User.query.filter(~User.id.in_(membros_ids)).all() if membros_ids else User.query.all()
    
    # Verificar qual aba deve ser ativa
    tab_ativa = request.args.get('tab', 'perfis')
    
    return render_template(
        "acessos.html",
        projeto=projeto,
        perfis=perfis,
        membros_com_perfil=membros_com_perfil,
        usuarios_disponiveis=usuarios_disponiveis,
        usuario_atual=current_user.username,
        tab_ativa=tab_ativa
    )


@app.route("/projetos/<int:projeto_id>/licoes", methods=["GET", "POST"])
@login_required
def licoes_aprendidas(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    if not is_project_member(projeto_id):
        abort(403)
    
    # Criar nova lição
    if request.method == "POST" and request.form.get("action") == "criar":
        if not has_permission(projeto_id, "pode_criar_licao"):
            abort(403)
        
        nova_licao = LicaoAprendida(
            projeto_id=projeto_id,
            fase_id=request.form.get("fase_id") if request.form.get("fase_id") else None,
            categoria=request.form.get("categoria"),
            tipo=request.form.get("tipo"),
            descricao=request.form.get("descricao"),
            causa_raiz=request.form.get("causa_raiz"),
            impacto=request.form.get("impacto"),
            acao_tomada=request.form.get("acao_tomada"),
            recomendacao=request.form.get("recomendacao"),
            responsavel=request.form.get("responsavel"),
            status=request.form.get("status"),
            aplicavel_futuros=request.form.get("aplicavel_futuros") == "on"
        )
        db.session.add(nova_licao)
        db.session.commit()
        flash("Lição aprendida registrada com sucesso", "success")
        return redirect(url_for("licoes_aprendidas", projeto_id=projeto_id))
    
    # Editar lição
    if request.method == "POST" and request.form.get("action") == "editar":
        if not has_permission(projeto_id, "pode_editar_licao"):
            abort(403)
        
        licao_id = request.form.get("licao_id")
        licao = LicaoAprendida.query.get(licao_id)
        if licao and licao.projeto_id == projeto_id:
            licao.fase_id = request.form.get("fase_id") if request.form.get("fase_id") else None
            licao.categoria = request.form.get("categoria")
            licao.tipo = request.form.get("tipo")
            licao.descricao = request.form.get("descricao")
            licao.causa_raiz = request.form.get("causa_raiz")
            licao.impacto = request.form.get("impacto")
            licao.acao_tomada = request.form.get("acao_tomada")
            licao.recomendacao = request.form.get("recomendacao")
            licao.responsavel = request.form.get("responsavel")
            licao.status = request.form.get("status")
            licao.aplicavel_futuros = request.form.get("aplicavel_futuros") == "on"
            db.session.commit()
            flash("Lição aprendida atualizada com sucesso", "success")
        return redirect(url_for("licoes_aprendidas", projeto_id=projeto_id))
    
    # Excluir lição
    if request.method == "POST" and request.form.get("action") == "excluir":
        if not has_permission(projeto_id, "pode_excluir_licao"):
            abort(403)
        
        licao_id = request.form.get("licao_id")
        licao = LicaoAprendida.query.get(licao_id)
        if licao and licao.projeto_id == projeto_id:
            db.session.delete(licao)
            db.session.commit()
            flash("Lição aprendida excluída com sucesso", "success")
        return redirect(url_for("licoes_aprendidas", projeto_id=projeto_id))
    
    # Obter dados
    licoes = LicaoAprendida.query.filter_by(projeto_id=projeto_id).order_by(LicaoAprendida.data_registro.desc()).all()
    fases = Fase.query.filter_by(projeto_id=projeto_id).all()
    
    pode_criar = has_permission(projeto_id, "pode_criar_licao")
    pode_editar = has_permission(projeto_id, "pode_editar_licao")
    pode_excluir = has_permission(projeto_id, "pode_excluir_licao")
    pode_gerenciar_membros = has_permission(projeto_id, "pode_gerenciar_membros")
    
    return render_template(
        "licoes.html",
        projeto=projeto,
        licoes=licoes,
        fases=fases,
        pode_criar=pode_criar,
        pode_editar=pode_editar,
        pode_excluir=pode_excluir,
        pode_gerenciar_membros=pode_gerenciar_membros,
        usuario_atual=current_user.username
    )


@app.route("/projetos/<int:projeto_id>/mudancas", methods=["GET", "POST"])
@login_required
def solicitacoes_mudanca(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    
    # Verificar se o usuário é membro do projeto
    membro = ProjetoMembro.query.filter_by(projeto_id=projeto_id, user_id=current_user.id).first()
    if not membro:
        abort(403)

    invalid_date = object()

    def parse_date_field(field_name, label):
        value = request.form.get(field_name)
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            flash(f"Data inválida em {label}. Use o formato AAAA-MM-DD.", "danger")
            return invalid_date
    
    # Criar solicitação de mudança
    if request.method == "POST" and request.form.get("action") == "criar":
        if not has_permission(projeto_id, "pode_criar_mudanca"):
            abort(403)

        data_decisao = parse_date_field("data_decisao", "Data da Decisão")
        data_implementacao = parse_date_field("data_implementacao", "Data da Implementação")
        if data_decisao is invalid_date or data_implementacao is invalid_date:
            return redirect(url_for("solicitacoes_mudanca", projeto_id=projeto_id))
        
        solicitacao = SolicitacaoMudanca(
            projeto_id=projeto_id,
            solicitante=request.form.get("solicitante"),
            area_solicitante=request.form.get("area_solicitante"),
            descricao=request.form.get("descricao"),
            justificativa=request.form.get("justificativa"),
            tipo_mudanca=request.form.get("tipo_mudanca"),
            impacto_prazo=request.form.get("impacto_prazo"),
            impacto_custo=request.form.get("impacto_custo"),
            impacto_escopo=request.form.get("impacto_escopo"),
            impacto_recursos=request.form.get("impacto_recursos"),
            impacto_risco=request.form.get("impacto_risco"),
            prioridade=request.form.get("prioridade"),
            recomendacao_pm=request.form.get("recomendacao_pm"),
            status=request.form.get("status", "Em análise"),
            aprovador=request.form.get("aprovador"),
            data_decisao=data_decisao,
            data_implementacao=data_implementacao,
            observacoes=request.form.get("observacoes")
        )
        db.session.add(solicitacao)
        db.session.commit()
        flash("Solicitação de mudança criada com sucesso", "success")
        return redirect(url_for("solicitacoes_mudanca", projeto_id=projeto_id))
    
    # Editar solicitação de mudança
    if request.method == "POST" and request.form.get("action") == "editar":
        if not has_permission(projeto_id, "pode_editar_mudanca"):
            abort(403)

        data_decisao = parse_date_field("data_decisao", "Data da Decisão")
        data_implementacao = parse_date_field("data_implementacao", "Data da Implementação")
        if data_decisao is invalid_date or data_implementacao is invalid_date:
            return redirect(url_for("solicitacoes_mudanca", projeto_id=projeto_id))
        
        mudanca_id = request.form.get("mudanca_id")
        solicitacao = SolicitacaoMudanca.query.get(mudanca_id)
        if solicitacao and solicitacao.projeto_id == projeto_id:
            solicitacao.solicitante = request.form.get("solicitante")
            solicitacao.area_solicitante = request.form.get("area_solicitante")
            solicitacao.descricao = request.form.get("descricao")
            solicitacao.justificativa = request.form.get("justificativa")
            solicitacao.tipo_mudanca = request.form.get("tipo_mudanca")
            solicitacao.impacto_prazo = request.form.get("impacto_prazo")
            solicitacao.impacto_custo = request.form.get("impacto_custo")
            solicitacao.impacto_escopo = request.form.get("impacto_escopo")
            solicitacao.impacto_recursos = request.form.get("impacto_recursos")
            solicitacao.impacto_risco = request.form.get("impacto_risco")
            solicitacao.prioridade = request.form.get("prioridade")
            solicitacao.recomendacao_pm = request.form.get("recomendacao_pm")
            solicitacao.status = request.form.get("status")
            solicitacao.aprovador = request.form.get("aprovador")
            solicitacao.data_decisao = data_decisao
            solicitacao.data_implementacao = data_implementacao
            solicitacao.observacoes = request.form.get("observacoes")
            db.session.commit()
            flash("Solicitação de mudança atualizada com sucesso", "success")
        return redirect(url_for("solicitacoes_mudanca", projeto_id=projeto_id))
    
    # Excluir solicitação de mudança
    if request.method == "POST" and request.form.get("action") == "excluir":
        if not has_permission(projeto_id, "pode_excluir_mudanca"):
            abort(403)
        
        mudanca_id = request.form.get("mudanca_id")
        solicitacao = SolicitacaoMudanca.query.get(mudanca_id)
        if solicitacao and solicitacao.projeto_id == projeto_id:
            db.session.delete(solicitacao)
            db.session.commit()
            flash("Solicitação de mudança excluída com sucesso", "success")
        return redirect(url_for("solicitacoes_mudanca", projeto_id=projeto_id))
    
    # Obter dados
    mudancas = SolicitacaoMudanca.query.filter_by(projeto_id=projeto_id).order_by(SolicitacaoMudanca.data_solicitacao.desc()).all()
    
    pode_criar = has_permission(projeto_id, "pode_criar_mudanca")
    pode_editar = has_permission(projeto_id, "pode_editar_mudanca")
    pode_excluir = has_permission(projeto_id, "pode_excluir_mudanca")
    pode_gerenciar_membros = has_permission(projeto_id, "pode_gerenciar_membros")
    
    return render_template(
        "mudancas.html",
        projeto=projeto,
        mudancas=mudancas,
        pode_criar=pode_criar,
        pode_editar=pode_editar,
        pode_excluir=pode_excluir,
        pode_gerenciar_membros=pode_gerenciar_membros,
        usuario_atual=current_user.username
    )


@app.route("/projetos/<int:projeto_id>/incidentes", methods=["GET", "POST"])
@login_required
def incidentes(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    
    # Verificar se o usuário é membro do projeto
    membro = ProjetoMembro.query.filter_by(projeto_id=projeto_id, user_id=current_user.id).first()
    if not membro:
        abort(403)

    invalid_date = object()

    def parse_date_field(field_name, label):
        value = request.form.get(field_name)
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            flash(f"Data inválida em {label}. Use o formato AAAA-MM-DD.", "danger")
            return invalid_date
    
    # Criar incidente
    if request.method == "POST" and request.form.get("action") == "criar":
        previsao_original = parse_date_field("previsao_original", "Previsão Original")
        previsao_revisada = parse_date_field("previsao_revisada", "Previsão Revisada")
        if previsao_original is invalid_date or previsao_revisada is invalid_date:
            return redirect(url_for("incidentes", projeto_id=projeto_id))
        
        atividade_id = request.form.get("atividade_id")
        incidente = Incidente(
            projeto_id=projeto_id,
            atividade_id=int(atividade_id) if atividade_id else None,
            descricao=request.form.get("descricao"),
            acompanhamento=request.form.get("acompanhamento"),
            responsavel=request.form.get("responsavel"),
            prioridade=request.form.get("prioridade"),
            status=request.form.get("status", "Criado"),
            previsao_original=previsao_original,
            previsao_revisada=previsao_revisada
        )
        db.session.add(incidente)
        db.session.commit()
        flash("Incidente criado com sucesso", "success")
        return redirect(url_for("incidentes", projeto_id=projeto_id))
    
    # Editar incidente
    if request.method == "POST" and request.form.get("action") == "editar":
        previsao_original = parse_date_field("previsao_original", "Previsão Original")
        previsao_revisada = parse_date_field("previsao_revisada", "Previsão Revisada")
        conclusao = parse_date_field("conclusao", "Conclusão")
        
        if previsao_original is invalid_date or previsao_revisada is invalid_date or conclusao is invalid_date:
            return redirect(url_for("incidentes", projeto_id=projeto_id))
        
        incidente_id = request.form.get("incidente_id")
        incidente = Incidente.query.get(incidente_id)
        if incidente and incidente.projeto_id == projeto_id:
            atividade_id = request.form.get("atividade_id")
            incidente.atividade_id = int(atividade_id) if atividade_id else None
            incidente.descricao = request.form.get("descricao")
            incidente.acompanhamento = request.form.get("acompanhamento")
            incidente.responsavel = request.form.get("responsavel")
            incidente.prioridade = request.form.get("prioridade")
            incidente.status = request.form.get("status")
            incidente.previsao_original = previsao_original
            incidente.previsao_revisada = previsao_revisada
            incidente.conclusao = conclusao
            incidente.data_ultima_modificacao = datetime.utcnow()
            db.session.commit()
            flash("Incidente atualizado com sucesso", "success")
        return redirect(url_for("incidentes", projeto_id=projeto_id))
    
    # Excluir incidente
    if request.method == "POST" and request.form.get("action") == "excluir":
        incidente_id = request.form.get("incidente_id")
        incidente = Incidente.query.get(incidente_id)
        if incidente and incidente.projeto_id == projeto_id:
            db.session.delete(incidente)
            db.session.commit()
            flash("Incidente excluído com sucesso", "success")
        return redirect(url_for("incidentes", projeto_id=projeto_id))
    
    # Obter dados
    incidentes_list = Incidente.query.filter_by(projeto_id=projeto_id).order_by(Incidente.data_criacao.desc()).all()
    
    # Obter todas as atividades do projeto para poder fazer link
    atividades = Atividade.query.filter(
        Atividade.cenario_id.in_(
            db.session.query(Cenario.id).filter(
                Cenario.fase_id.in_(
                    db.session.query(Fase.id).filter(Fase.projeto_id == projeto_id)
                )
            )
        )
    ).all()
    
    # Qualquer membro do projeto pode criar/editar/excluir incidentes
    pode_criar = True
    pode_editar = True
    pode_excluir = True
    pode_gerenciar_membros = has_permission(projeto_id, "pode_gerenciar_membros")
    
    return render_template(
        "incidentes.html",
        projeto=projeto,
        incidentes=incidentes_list,
        atividades=atividades,
        pode_criar=pode_criar,
        pode_editar=pode_editar,
        pode_excluir=pode_excluir,
        pode_gerenciar_membros=pode_gerenciar_membros,
        usuario_atual=current_user.username
    )


@app.route("/projetos/<int:projeto_id>/riscos", methods=["GET", "POST"])
@login_required
def riscos(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)

    # Verificar se o usuario e membro do projeto
    membro = ProjetoMembro.query.filter_by(projeto_id=projeto_id, user_id=current_user.id).first()
    if not membro:
        abort(403)

    invalid_date = object()

    def parse_date_field(field_name, label):
        value = request.form.get(field_name)
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            flash(f"Data invalida em {label}. Use o formato AAAA-MM-DD.", "danger")
            return invalid_date

    # Criar risco
    if request.method == "POST" and request.form.get("action") == "criar":
        data_proxima_acao = parse_date_field("data_proxima_acao", "Data Proxima acao")
        data_conclusao = parse_date_field("data_conclusao", "Data Conclusao")
        if data_proxima_acao is invalid_date or data_conclusao is invalid_date:
            return redirect(url_for("riscos", projeto_id=projeto_id))

        risco = Risco(
            projeto_id=projeto_id,
            area=request.form.get("area"),
            tipo_risco=request.form.get("tipo_risco"),
            risco=request.form.get("risco"),
            criado_por=current_user.username,
            responsavel=request.form.get("responsavel"),
            gatilho=request.form.get("gatilho"),
            impacto_projeto=request.form.get("impacto_projeto"),
            consequencia=request.form.get("consequencia"),
            impacto=request.form.get("impacto"),
            probabilidade=request.form.get("probabilidade"),
            nivel_risco=request.form.get("nivel_risco"),
            estrategia=request.form.get("estrategia"),
            prevencao=request.form.get("prevencao"),
            contingencia=request.form.get("contingencia"),
            acompanhamento=request.form.get("acompanhamento"),
            status=request.form.get("status"),
            data_proxima_acao=data_proxima_acao,
            data_conclusao=data_conclusao,
        )
        db.session.add(risco)
        db.session.commit()
        flash("Risco criado com sucesso", "success")
        return redirect(url_for("riscos", projeto_id=projeto_id))

    # Editar risco
    if request.method == "POST" and request.form.get("action") == "editar":
        data_proxima_acao = parse_date_field("data_proxima_acao", "Data Proxima acao")
        data_conclusao = parse_date_field("data_conclusao", "Data Conclusao")
        if data_proxima_acao is invalid_date or data_conclusao is invalid_date:
            return redirect(url_for("riscos", projeto_id=projeto_id))

        risco_id = request.form.get("risco_id")
        risco = Risco.query.get(risco_id)
        if risco and risco.projeto_id == projeto_id:
            risco.area = request.form.get("area")
            risco.tipo_risco = request.form.get("tipo_risco")
            risco.risco = request.form.get("risco")
            risco.responsavel = request.form.get("responsavel")
            risco.gatilho = request.form.get("gatilho")
            risco.impacto_projeto = request.form.get("impacto_projeto")
            risco.consequencia = request.form.get("consequencia")
            risco.impacto = request.form.get("impacto")
            risco.probabilidade = request.form.get("probabilidade")
            risco.nivel_risco = request.form.get("nivel_risco")
            risco.estrategia = request.form.get("estrategia")
            risco.prevencao = request.form.get("prevencao")
            risco.contingencia = request.form.get("contingencia")
            risco.acompanhamento = request.form.get("acompanhamento")
            risco.status = request.form.get("status")
            risco.data_proxima_acao = data_proxima_acao
            risco.data_conclusao = data_conclusao
            db.session.commit()
            flash("Risco atualizado com sucesso", "success")
        return redirect(url_for("riscos", projeto_id=projeto_id))

    # Excluir risco
    if request.method == "POST" and request.form.get("action") == "excluir":
        risco_id = request.form.get("risco_id")
        risco = Risco.query.get(risco_id)
        if risco and risco.projeto_id == projeto_id:
            db.session.delete(risco)
            db.session.commit()
            flash("Risco excluido com sucesso", "success")
        return redirect(url_for("riscos", projeto_id=projeto_id))

    riscos_list = Risco.query.filter_by(projeto_id=projeto_id).order_by(Risco.data_criacao.desc()).all()

    # Qualquer membro do projeto pode criar/editar/excluir riscos
    pode_criar = True
    pode_editar = True
    pode_excluir = True
    pode_gerenciar_membros = has_permission(projeto_id, "pode_gerenciar_membros")

    return render_template(
        "riscos.html",
        projeto=projeto,
        riscos=riscos_list,
        pode_criar=pode_criar,
        pode_editar=pode_editar,
        pode_excluir=pode_excluir,
        pode_gerenciar_membros=pode_gerenciar_membros,
        usuario_atual=current_user.username,
    )


# Listas constantes para status e prioridade
LISTA_STATUS_INCIDENTE = [
    "Criado",
    "Em andamento",
    "Aguardando Solicitante",
    "Aguardando Externo",
    "Encaminhado Responsavel",
    "Proposta de solução",
    "Concluído"
]

LISTA_PRIORIDADE_INCIDENTE = [
    "1 - Muito Alto",
    "2 - Alto",
    "3 - Médio",
    "4 - Baixo",
    "5 - Muito Baixo"
]


# ------------------------------------------------------------------------------
# ENTRYPOINT
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
