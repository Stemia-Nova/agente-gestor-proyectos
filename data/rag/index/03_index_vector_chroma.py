#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Crea o actualiza una base vectorial persistente (ChromaDB) con las tareas procesadas.
Esta versión garantiza la persistencia física en disco.
"""

import json
import numpy as np
from pathlib import Path
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
import re

# =============================================================
# CONFIG
# =============================================================

INPUT_FILE = Path("data/processed/task_chunks.jsonl")
DB_DIR = Path("data/rag/chroma_db")
COLLECTION_NAME = "clickup_tasks"
MODEL_NAME = "sentence-transformers/all-MiniLM-L12-v2"

# =============================================================
# UTILS
# =============================================================

def load_chunks():
    if not INPUT_FILE.exists():
        raise FileNotFoundError("❌ No se encontró task_chunks.jsonl.")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

_token_re = re.compile(r"\w+", re.UNICODE)
def tokenize(text): return [t.lower() for t in _token_re.findall(text or "")]

# =============================================================
# MAIN LOGIC
# =============================================================

def main():
    chunks = load_chunks()
    print(f"✅ {len(chunks)} chunks cargados.")
    model = SentenceTransformer(MODEL_NAME)

    print(f"🧠 Cargando o creando base vectorial persistente en: {DB_DIR.resolve()}")
    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR.resolve()))
    collection = client.get_or_create_collection(COLLECTION_NAME)

    existing_ids = set(collection.get(limit=100000).get("ids", []))
    new_chunks = [c for c in chunks if c["chunk_id"] not in existing_ids]

    print(f"📊 Ya existen {len(existing_ids)} documentos, nuevos: {len(new_chunks)}")
    for c in tqdm(new_chunks, desc="🆕 Indexando nuevos chunks"):
        emb = model.encode(c["text"], convert_to_numpy=True).tolist()
        metadata = {k: (v if isinstance(v, (str, int, float, bool)) else str(v))
                    for k, v in c.get("metadata", {}).items()}
        collection.add(
            ids=[c["chunk_id"]],
            documents=[c["text"]],
            metadatas=[metadata],
            embeddings=[emb],
        )

    print("💾 Base vectorial persistente actualizada correctamente.")
    print("✅ Ahora puedes ejecutar 04_hybrid_search.py para consultas híbridas.")

if __name__ == "__main__":
    main()
