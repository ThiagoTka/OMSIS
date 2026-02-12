# IMSIS - Sistema de Gestão de Projetos

Sistema web para gerenciamento de projetos, com suporte a cenários de teste, lições aprendidas e solicitações de mudança.

## Deployment no GCP

### Deploy automático via GitHub → GCP

1. **Push para GitHub** dispara automaticamente Cloud Build
2. **Cloud Build** executa `cloudbuild.yaml`:
   - Faz build da Docker image
   - Envia para Container Registry
   - Deploy no Cloud Run

### Inicialização automática do banco de dados

⚠️ **Importante**: As tabelas do banco de dados são criadas **automaticamente** quando a aplicação inicia.

Isso acontece em `app.py` com:
```python
with app.app_context():
    criar_tabelas()  # Executa db.create_all()
```

**Vantagens**:
- ✅ Funciona em qualquer ambiente (local, GCP, etc)
- ✅ Idempotente (seguro rodar múltiplas vezes)
- ✅ Não requer passos manuais
- ✅ Detecta automaticamente quando novas tabelas/colunas são necessárias

### Conexão com Cloud SQL

Configure as variáveis de ambiente:
- `DB_USER`: Usuário do PostgreSQL
- `DB_PASS`: Senha do PostgreSQL
- `DB_NAME`: Nome do banco de dados
- `CLOUD_SQL_CONNECTION_NAME`: `projeto:regiao:instancia`

Exemplo em `cloudbuild.yaml`:
```yaml
- --set-env-vars=CLOUD_SQL_CONNECTION_NAME=imsis-486003:us-central1:imsis-db
```

## Desenvolvimento Local

```bash
# Criar venv
python -m venv .venv
.venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Rodar
python app.py
```

Database local: `sqlite:///dev.db`

## Estrutura do Projeto

```
app.py                  # Aplicação principal (models + rotas)
templates/              # Templates HTML (Jinja2)
static/                 # CSS e JavaScript
cloudbuild.yaml         # Configuração do CI/CD (GCP)
Dockerfile              # Container image
requirements.txt        # Dependências Python
```

## Modelos de Dados

- **User**: Usuários do sistema
- **Projeto**: Projetos principais
- **ProjetoMembro**: Associação entre usuários e projetos
- **Perfil**: Perfis de acesso (permissões por projeto)
- **Fase/Cenario/Atividade**: Estrutura de testes
- **LicaoAprendida**: Registro de lições do projeto
- **SolicitacaoMudanca**: Solicitações de mudança

## Permissões por Perfil

Cada perfil pode ter permissões customizadas para:
- Atividades (criar, editar, excluir, concluir)
- Lições Aprendidas (criar, editar, excluir)
- Solicitações de Mudança (criar, editar, excluir)
- Gerenciar membros e perfis do projeto

---

## Deployment Manual (se necessário)

```bash
# Deploy direto no Cloud Run
gcloud run deploy imsis --source .
```

Cores do tema (CSS):
- Primary: #1F4E79 (azul)
- Success: #16A34A (verde)
- Warning: #F59E0B (amarelo)
- Danger: #DC2626 (vermelho)
