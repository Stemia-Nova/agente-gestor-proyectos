#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Índice vectorial persistente con ChromaDB para tareas ClickUp.
Crea o actualiza la base vectorial a partir de los chunks ya procesados.
Permite búsquedas semánticas e incrementales (solo indexa nuevos documentos).
"""

import json
from pathlib import Path
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import numpy as np
from rank_bm25 import BM25Okapi
import re

# =============================================================
# CONFIGURACIÓN
# =============================================================

INPUT_FILE = Path("data/processed/task_chunks.jsonl")
DB_DIR = Path("data/rag/chroma_db")  # 🧠 Carpeta persistente
MODEL_NAME = "sentence-transformers/all-MiniLM-L12-v2"
COLLECTION_NAME = "clickup_tasks"
TOP_K = 5

# =============================================================
# FUNCIONES AUXILIARES
# =============================================================

def load_chunks():
    """Carga los chunks del archivo procesado."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"No se encontró {INPUT_FILE}. Ejecuta antes 02_chunk_tasks.py.")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]
    print(f"✅ {len(chunks)} chunks cargados.")
    return chunks


_token_re = re.compile(r"\w+", re.UNICODE)
def tokenize(text: str):
    """Tokeniza el texto para BM25."""
    return [t.lower() for t in _token_re.findall(text or "")]

# =============================================================
# CONSTRUCCIÓN O ACTUALIZACIÓN DEL ÍNDICE
# =============================================================

def build_or_update_chroma(chunks, model):
    """Crea o actualiza la base ChromaDB con los nuevos chunks."""
    print(f"🧠 Cargando base vectorial persistente en: {DB_DIR.resolve()}")
    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.Client(Settings(persist_directory=str(DB_DIR.resolve())))
    collection = client.get_or_create_collection(COLLECTION_NAME)

    existing_ids = set(collection.get(ids=None, limit=100000).get("ids", []))
    print(f"📊 Actualmente hay {len(existing_ids)} documentos indexados.")

    new_chunks = [c for c in chunks if c["chunk_id"] not in existing_ids]

    if not new_chunks:
        print("✅ No hay nuevos documentos para indexar.")
    else:
        print(f"🆕 Indexando {len(new_chunks)} nuevos documentos...")
        for c in tqdm(new_chunks):
            emb = model.encode(c["text"], convert_to_numpy=True).tolist()

            # 🔧 Limpiar metadatos (evitar None o tipos no válidos)
            metadata = {
                k: ("" if v is None else str(v))
                for k, v in c.get("metadata", {}).items()
                if isinstance(v, (str, int, float, bool)) or v is None
            }

            collection.add(
                ids=[c["chunk_id"]],
                documents=[c["text"]],
                metadatas=[metadata],
                embeddings=[emb],
            )

        print(f"💾 Base vectorial actualizada con {len(new_chunks)} nuevos documentos.")
        print(f"📦 Total actual en ChromaDB: {collection.count()}")

    return collection, client


def build_bm25_index(chunks):
    """Crea el índice BM25 en memoria para búsqueda híbrida."""
    print("🧰 Construyendo índice BM25 (para búsqueda híbrida)...")
    docs_tokens = []
    for c in chunks:
        meta = c.get("metadata", {})
        meta_str = " ".join([
            str(meta.get("status", "")),
            str(meta.get("project", "")),
            str(meta.get("list", "")),
            str(meta.get("priority", "")),
            str(meta.get("tags", "")),
        ])
        doc_text = f"{c['text']} {meta_str}"
        docs_tokens.append(tokenize(doc_text))
    return BM25Okapi(docs_tokens), docs_tokens


def hybrid_search(query: str, model, collection, chunks, bm25, bm25_tokens, top_k=TOP_K):
    """Realiza búsqueda híbrida con BM25 + embeddings de ChromaDB."""
    q_emb = model.encode([query], convert_to_numpy=True)
    results = collection.query(query_embeddings=q_emb.tolist(), n_results=top_k)

    bm25_scores = np.array(bm25.get_scores(tokenize(query)))
    bm25_scores = (bm25_scores - bm25_scores.min()) / (bm25_scores.max() - bm25_scores.min() + 1e-12)

    hybrid_results = []
    for i, doc_id in enumerate(results["ids"][0]):
        idx = next((j for j, c in enumerate(chunks) if c["chunk_id"] == doc_id), None)
        if idx is None:
            continue

        # 🔹 Asegurar similitud positiva
        vec_score = max(0.0, 1.0 - float(results["distances"][0][i]))
        fused = 0.6 * vec_score + 0.4 * bm25_scores[idx]

        hybrid_results.append((chunks[idx], fused))

    hybrid_results = sorted(hybrid_results, key=lambda x: x[1], reverse=True)

    print(f"\n🔎 Consulta: {query}")
    for rank, (chunk, score) in enumerate(hybrid_results[:top_k], start=1):
        meta = chunk.get("metadata", {})
        print(f"\n#{rank} | SCORE={score:.3f}")
        print(f"Tarea: {chunk['task_id']} | Estado: {meta.get('status', '')} | Proyecto: {meta.get('project', '')}")
        print(f"Texto: {chunk['text'][:250]}...")

    return hybrid_results

# =============================================================
# PROGRAMA PRINCIPAL
# =============================================================

def main():
    chunks = load_chunks()
    model = SentenceTransformer(MODEL_NAME)
    bm25, bm25_tokens = build_bm25_index(chunks)

    collection, client = build_or_update_chroma(chunks, model)

    print("\n✅ Base vectorial lista. Puedes hacer consultas.")
    while True:
        q = input("\n📝 Escribe tu consulta (o 'salir'): ").strip()
        if q.lower() in {"salir", "exit", "quit"}:
            break
        hybrid_search(q, model, collection, chunks, bm25, bm25_tokens, top_k=TOP_K)

    # 💾 Persistir al finalizar (si el cliente lo soporta)
    try:
        pers = getattr(client, "persist", None)
        if callable(pers):
            pers()
            print(f"💾 Base Chroma persistida en: {DB_DIR.resolve()}")
        else:
            # Algunas versiones de chromadb no exponen persist() en la API pública;
            # en esos casos la persistencia puede ser automática o gestionada internamente.
            print("⚠️ El cliente ChromaDB no soporta 'persist()' — omitiendo persistencia explícita.")
    except Exception as e:
        print(f"⚠️ No se pudo persistir la base ChromaDB: {e}")


if __name__ == "__main__":
    main()
