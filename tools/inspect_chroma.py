#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspecta la base Chroma de tareas ClickUp."""

import chromadb
import json

def main(limit: int = 10):
    client = chromadb.PersistentClient(path="data/rag/chroma_db")
    col = client.get_collection("clickup_tasks")
    print(f"📂 Colección: {col.name}")
    print(f"🧠 Total de documentos: {col.count()}")

    data = col.peek(limit=limit)
    metas = data.get("metadatas") or []
    docs = data.get("documents") or []

    for i, (m, d) in enumerate(zip(metas, docs), start=1):
        print(f"\n── Documento {i} ─────────────────────────────")
        print(json.dumps(m, indent=2, ensure_ascii=False))
        print(f"\n📝 Texto (primeros 300 caracteres):\n{(d or '')[:300]}…")

if __name__ == "__main__":
    main()
