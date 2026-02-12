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
            nome="Membro",
            projeto_id=projeto.id,
            pode_criar_atividade=True,
            pode_editar_atividade=True,
            pode_excluir_atividade=False,
            pode_concluir_qualquer_atividade=False,
            pode_editar_projeto=False,
            pode_gerenciar_membros=False,
            is_default=True
        )
        db.session.add(perfil_admin)
        db.session.add(perfil_membro)
        db.session.flush()
        
        # Atribuir perfis aos membros
        membros = ProjetoMembro.query.filter_by(projeto_id=projeto.id).all()
        primeiro_membro = membros[0] if membros else None
        
        for membro in membros:
            # Primeiro membro é admin, outros são membros
            if membro == primeiro_membro:
                db.session.add(MembroPerfil(projeto_membro_id=membro.id, perfil_id=perfil_admin.id))
                print(f"  👤 {membro.user.username} -> Administrador")
            else:
                db.session.add(MembroPerfil(projeto_membro_id=membro.id, perfil_id=perfil_membro.id))
                print(f"  👤 {membro.user.username} -> Membro")
        
        db.session.commit()
        print(f"✅ Projeto '{projeto.nome}' migrado com sucesso\n")
    
    print("🎉 Migração concluída!")
