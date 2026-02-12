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
