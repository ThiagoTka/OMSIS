"""
Script de migração para adicionar funcionalidade de solicitações de mudança
"""
import sqlite3

# Conectar ao banco de dados
conn = sqlite3.connect('instance/dev.db')
cursor = conn.cursor()

try:
    # Adicionar colunas de permissões de solicitações de mudança na tabela perfis
    print("Adicionando colunas de permissões de solicitações de mudança...")
    
    try:
        cursor.execute("ALTER TABLE perfis ADD COLUMN pode_criar_mudanca BOOLEAN DEFAULT 0")
        print("✓ Coluna pode_criar_mudanca adicionada")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("- Coluna pode_criar_mudanca já existe")
        else:
            raise
    
    try:
        cursor.execute("ALTER TABLE perfis ADD COLUMN pode_editar_mudanca BOOLEAN DEFAULT 0")
        print("✓ Coluna pode_editar_mudanca adicionada")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("- Coluna pode_editar_mudanca já existe")
        else:
            raise
    
    try:
        cursor.execute("ALTER TABLE perfis ADD COLUMN pode_excluir_mudanca BOOLEAN DEFAULT 0")
        print("✓ Coluna pode_excluir_mudanca adicionada")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("- Coluna pode_excluir_mudanca já existe")
        else:
            raise
    
    # Criar tabela de solicitações de mudança
    print("\nCriando tabela de solicitações de mudança...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS solicitacoes_mudanca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            data_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            solicitante VARCHAR(100),
            area_solicitante VARCHAR(100),
            descricao TEXT NOT NULL,
            justificativa TEXT,
            tipo_mudanca VARCHAR(50),
            impacto_prazo VARCHAR(100),
            impacto_custo VARCHAR(100),
            impacto_escopo VARCHAR(50),
            impacto_recursos VARCHAR(200),
            impacto_risco VARCHAR(50),
            prioridade VARCHAR(50),
            recomendacao_pm VARCHAR(50),
            status VARCHAR(50),
            aprovador VARCHAR(100),
            data_decisao DATETIME,
            data_implementacao DATETIME,
            observacoes TEXT,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id)
        )
    """)
    print("✓ Tabela solicitacoes_mudanca criada/verificada")
    
    # Atualizar permissões dos perfis padrão
    print("\nAtualizando permissões dos perfis padrão...")
    
    # Administrador - todas as permissões
    cursor.execute("""
        UPDATE perfis 
        SET pode_criar_mudanca = 1, 
            pode_editar_mudanca = 1, 
            pode_excluir_mudanca = 1
        WHERE nome = 'Administrador' AND is_default = 1
    """)
    print("✓ Permissões do perfil Administrador atualizadas")
    
    # Membro - pode criar e editar, mas não excluir
    cursor.execute("""
        UPDATE perfis 
        SET pode_criar_mudanca = 1, 
            pode_editar_mudanca = 1, 
            pode_excluir_mudanca = 0
        WHERE nome = 'Membro' AND is_default = 1
    """)
    print("✓ Permissões do perfil Membro atualizadas")
    
    # Commit das mudanças
    conn.commit()
    print("\n✅ Migração concluída com sucesso!")
    
except Exception as e:
    print(f"\n❌ Erro durante a migração: {e}")
    conn.rollback()
    raise
finally:
    conn.close()

print("\nVocê pode agora executar 'python app.py' para iniciar a aplicação.")
