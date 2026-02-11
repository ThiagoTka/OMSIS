"""
Script para atualizar permissões dos perfis padrão
"""
import sqlite3

# Conectar ao banco de dados
conn = sqlite3.connect('instance/dev.db')
cursor = conn.cursor()

try:
    # Atualizar perfil Administrador - todas as permissões de lições
    print("Atualizando permissões do perfil Administrador...")
    cursor.execute("""
        UPDATE perfis 
        SET pode_criar_licao = 1,
            pode_editar_licao = 1,
            pode_excluir_licao = 1
        WHERE nome = 'Administrador' AND is_default = 1
    """)
    admin_updated = cursor.rowcount
    print(f"✓ {admin_updated} perfil(is) Administrador atualizado(s)")
    
    # Atualizar perfil Membro - criar e editar lições
    print("\nAtualizando permissões do perfil Membro...")
    cursor.execute("""
        UPDATE perfis 
        SET pode_criar_licao = 1,
            pode_editar_licao = 1,
            pode_excluir_licao = 0
        WHERE nome = 'Membro' AND is_default = 1
    """)
    membro_updated = cursor.rowcount
    print(f"✓ {membro_updated} perfil(is) Membro atualizado(s)")
    
    # Commit das mudanças
    conn.commit()
    print("\n✅ Permissões atualizadas com sucesso!")
    
    # Mostrar resumo
    print("\n📋 Resumo das permissões:")
    print("\nAdministrador:")
    print("  ✓ Criar lições aprendidas")
    print("  ✓ Editar lições aprendidas")
    print("  ✓ Excluir lições aprendidas")
    
    print("\nMembro:")
    print("  ✓ Criar lições aprendidas")
    print("  ✓ Editar lições aprendidas")
    print("  ✗ Excluir lições aprendidas")
    
except Exception as e:
    print(f"\n❌ Erro durante a atualização: {e}")
    conn.rollback()
    raise
finally:
    conn.close()
