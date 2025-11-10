# tools/test_hybrid_search.py
from utils.hybrid_search import HybridSearch

# Inicializa (usa la colección ya indexada en data/rag/chroma_db)
hs = HybridSearch(collection_name="clickup_tasks", db_path="data/rag/chroma_db")

query = "tareas urgentes bloqueadas en Sprint 2"
docs, metas = hs.search(query, top_k=8)

print(f"\n🔎 Query: {query}\n")
for i, (d, m) in enumerate(zip(docs, metas), start=1):
    sprint = m.get("sprint")
    status = m.get("status")
    priority = m.get("priority")
    project = m.get("project")
    print(f"#{i}. sprint={sprint} | status={status} | priority={priority} | project={project}")
    print((d[:200] + "…") if d and len(d) > 200 else d)
    print()
