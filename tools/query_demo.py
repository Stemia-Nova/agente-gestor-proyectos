# tools/query_demo.py
import sys
import json
from typing import List
import chromadb

def ensure_sentence_transformers():
    try:
        from sentence_transformers import SentenceTransformer  # noqa
        return True
    except Exception as e:
        print("⚠️ Falta 'sentence-transformers'. Instálalo con:\n"
              "   pip install sentence-transformers\n")
        return False

def embed_query(texts: List[str]) -> List[List[float]]:
    # Usamos el mismo modelo que en la indexación (dim=384)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    vecs = model.encode(texts, normalize_embeddings=False)
    # Asegurar que sea lista de listas (no numpy)
    return [v.tolist() for v in (vecs if hasattr(vecs, "__len__") else [vecs])]

def main():
    if not ensure_sentence_transformers():
        sys.exit(1)

    QUERY = " ".join(sys.argv[1:]) or "tareas urgentes bloqueadas en Sprint 2"
    client = chromadb.PersistentClient(path="data/rag/chroma_db")

    try:
        col = client.get_collection("clickup_tasks")
    except Exception as e:
        print("❌ No se pudo abrir la colección 'clickup_tasks'. ¿Indexaste ya con 05_index_tasks.py?")
        print("Detalle:", e)
        sys.exit(2)

    q_emb = embed_query([QUERY])
    # col.query expects a single embedding (Sequence[float]) for one query,
    # so pass the first (and only) embedding from q_emb.
    res = col.query(query_embeddings=q_emb[0], n_results=5)

    docs = res.get("documents") or [[]]
    metas = res.get("metadatas") or [[]]
    ids = res.get("ids") or [[]]

    print(f"\n🔎 Query: {QUERY}\n")

    if not docs[0]:
        print("⚠️ No se obtuvieron resultados. Revisa:")
        print(" - Que la colección tenga documentos (06_validate_chroma_index.py)")
        print(" - Que el modelo de consulta sea el mismo (all-MiniLM-L6-v2, dim=384)")
        sys.exit(0)

    for i, (doc, meta, _id) in enumerate(zip(docs[0], metas[0], ids[0]), start=1):
        sprint = (meta or {}).get("sprint")
        status = (meta or {}).get("status")
        priority = (meta or {}).get("priority")
        project = (meta or {}).get("project")
        snippet = (doc[:200] + "…") if doc and len(doc) > 200 else (doc or "")
        print(f"#{i}  id={_id}")
        print(f"    sprint={sprint} | status={status} | priority={priority} | project={project}")
        print(f"    text={snippet}\n")

if __name__ == "__main__":
    main()
