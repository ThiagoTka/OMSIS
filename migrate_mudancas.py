"""
⚠️  DEPRECATED - NÃO é MAIS NECESSÁRIO

Todos os scripts de migração antigos são obsoletos!

A criação de tabelas do banco de dados agora é AUTOMÁTICA quando a aplicação inicia.

Veja app.py:
    with app.app_context():
        criar_tabelas()  # Executa db.create_all()

✅ Isto substitui completamente os antigos scripts de migração:
- create_db.py ❌
- init_db.py ❌
- migrate_licoes.py ❌
- migrate_mudancas.py ❌
- migrate_perfis.py ❌

Por que não precisa mais?
1. SQLAlchemy ORM agora gerencia todas as tabelas automaticamente
2. db.create_all() cria TODAS as tabelas necessárias em uma única chamada
3. A inicialização acontece no startup da aplicação (app.py linha ~273)
4. Seguro para rodar múltiplas vezes (idempotent)
5. Funciona em qualquer ambiente (local, GCP, etc)

Para desenvolvimento local:
    python app.py

Para GCP Cloud Run:
    As tabelas serão criadas automaticamente na primeira requisição

Não execute este script manualmente. Ele será ignorado.
"""

print(__doc__)
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
