#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05_index_tasks.py (versión corregida y optimizada)
--------------------------------------------------
Crea o reconstruye el índice base de tareas (RAG híbrido) en ChromaDB.

Entrada:
    data/processed/task_chunks.jsonl
Salida:
    Base persistente en data/rag/chroma_db

Flujo:
    1️⃣ Carga chunks → 2️⃣ Genera embeddings híbridos (MiniLM + Jina)
    → 3️⃣ Crea colección clickup_tasks → 4️⃣ Inserta datos limpios

Uso:
    python data/rag/transform/05_index_tasks.py --reset
"""

from __future__ import annotations
import json
import importlib
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm
import chromadb

# =============================================================
# 📂 Configuración
# =============================================================
CHUNKS_PATH = Path("data/processed/task_chunks.jsonl")
CHROMA_PATH = Path("data/rag/chroma_db")
COLLECTION_NAME = "clickup_tasks"


# =============================================================
# 🧠 Cargar chunks
# =============================================================
def load_chunks() -> List[Dict[str, Any]]:
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(f"No se encontró {CHUNKS_PATH}")
    rows = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    print(f"📦 Chunks cargados: {len(rows)}")
    return rows


# =============================================================
# ⚙️ Cargar embedding functions
# =============================================================
def load_embedding_functions() -> Dict[str, Any]:
    """Carga las funciones de embeddings: MiniLM + Jina si está disponible."""
    mod = importlib.import_module("chromadb.utils.embedding_functions")
    SentenceTF = getattr(mod, "SentenceTransformerEmbeddingFunction")
    embed_fns = {
        "semantic": SentenceTF(model_name="sentence-transformers/all-MiniLM-L12-v2")
    }

    try:
        JinaEF = getattr(mod, "JinaEmbeddingFunction", None)
        if JinaEF:
            embed_fns["dense"] = JinaEF(api_key=None)
            print("🧠 Embeddings híbridos: MiniLM + Jina")
        else:
            print("🧠 Solo MiniLM (Jina no disponible)")
    except Exception:
        print("🧠 Solo MiniLM (Jina no disponible)")
    return embed_fns


# =============================================================
# 🚀 Indexación completa
# =============================================================
def main(reset: bool = False) -> None:
    t0 = time.time()
    chunks = load_chunks()
    embed_fns = load_embedding_functions()

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    # Reset colección si se indica
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"🗑️ Colección '{COLLECTION_NAME}' eliminada.")
        except Exception:
            pass

    # Crear nueva colección
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fns["semantic"],
        metadata={
            "source": "clickup",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "hybrid_mode": "MiniLM + Jina" if "dense" in embed_fns else "MiniLM",
        },
    )

    print(f"📂 Colección activa: {COLLECTION_NAME}")

    ids, docs, metadatas = [], [], []
    seen_hashes = set()

    for ch in tqdm(chunks, desc="🧩 Indexando chunks"):
        cid = ch.get("chunk_id")
        chash = ch.get("chunk_hash")
        text = ch.get("text", "")
        meta = ch.get("metadata", {})

        if not cid or not text:
            continue
        if chash in seen_hashes:
            continue

        # Agregar embeddings híbridos si existe Jina
        if "dense" in embed_fns:
            try:
                emb_dense = embed_fns["dense"]([text])[0]
                meta["embedding_dense"] = emb_dense
            except Exception:
                pass

        # 🧹 Limpiar metadatos (Chroma no acepta None ni estructuras complejas)
        clean_meta: Dict[str, Any] = {}
        for k, v in (meta or {}).items():
            # Saltar valores None
            if v is None:
                continue
            
            # Caso especial: tags como string searchable (no JSON string)
            # Convertimos ["data", "hotfix"] → "data|hotfix" para búsquedas
            if k == "tags" and isinstance(v, list):
                v = "|".join(str(tag) for tag in v) if v else ""
            # Otros arrays/dicts los guardamos como JSON para preservar estructura
            elif isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            
            # Chroma acepta: str, int, float, bool
            # ⚠️ IMPORTANTE: Preservar tipos bool/int/float, NO convertir todo a string
            if isinstance(v, bool):
                clean_meta[k] = v
            elif isinstance(v, (int, float)):
                clean_meta[k] = v
            else:
                # Solo strings: limpiar whitespace
                clean_meta[k] = str(v).strip()

        ids.append(cid)
        docs.append(text)
        metadatas.append(clean_meta)
        seen_hashes.add(chash)

    if not ids:
        print("⚠️ No hay chunks válidos para indexar.")
        return

    # Upsert en Chroma
    collection.upsert(ids=ids, documents=docs, metadatas=metadatas)
    t1 = time.time()

    print(f"\n✅ Indexación completada en {t1 - t0:.2f} s")
    print(f"📊 Total chunks indexados: {len(ids)}")
    print(f"💾 Colección almacenada en: {CHROMA_PATH}")


# =============================================================
# CLI
# =============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Crea el índice base de ClickUp en ChromaDB.")
    parser.add_argument("--reset", action="store_true", help="Reinicia la colección antes de indexar.")
    args = parser.parse_args()

    main(reset=args.reset)
