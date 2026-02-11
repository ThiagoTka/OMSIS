"""
Script de migração para adicionar colunas de lições aprendidas
"""
import sqlite3

# Conectar ao banco de dados
conn = sqlite3.connect('instance/dev.db')
cursor = conn.cursor()

try:
    # Adicionar colunas de permissões de lições aprendidas na tabela perfis
    print("Adicionando colunas de permissões de lições aprendidas...")
    
    try:
        cursor.execute("ALTER TABLE perfis ADD COLUMN pode_criar_licao BOOLEAN DEFAULT 0")
        print("✓ Coluna pode_criar_licao adicionada")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("- Coluna pode_criar_licao já existe")
        else:
            raise
    
    try:
        cursor.execute("ALTER TABLE perfis ADD COLUMN pode_editar_licao BOOLEAN DEFAULT 0")
        print("✓ Coluna pode_editar_licao adicionada")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("- Coluna pode_editar_licao já existe")
        else:
            raise
    
    try:
        cursor.execute("ALTER TABLE perfis ADD COLUMN pode_excluir_licao BOOLEAN DEFAULT 0")
        print("✓ Coluna pode_excluir_licao adicionada")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("- Coluna pode_excluir_licao já existe")
        else:
            raise
    
    # Criar tabela de lições aprendidas
    print("\nCriando tabela de lições aprendidas...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licoes_aprendidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            fase_id INTEGER,
            categoria VARCHAR(100),
            tipo VARCHAR(50),
            descricao TEXT NOT NULL,
            causa_raiz TEXT,
            impacto TEXT,
            acao_tomada TEXT,
            recomendacao TEXT,
            responsavel VARCHAR(100),
            status VARCHAR(50),
            aplicavel_futuros BOOLEAN DEFAULT 1,
            data_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id),
            FOREIGN KEY (fase_id) REFERENCES fases(id)
        )
    """)
    print("✓ Tabela licoes_aprendidas criada/verificada")
    
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
