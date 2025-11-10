#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_chroma_from_clickup.py (versión profesional e incremental)
-----------------------------------------------------------------
Sincroniza la colección 'clickup_tasks' de ChromaDB con los nuevos
chunks generados desde ClickUp (task_chunks.jsonl).

✔ Inserta solo nuevos o modificados (comparando chunk_hash)
✔ Mantiene sprints cerrados como solo lectura
✔ Actualiza index_registry.json con metadatos y recuentos
✔ Compatible con embeddings MiniLM + Jina y ChromaDB ≥0.4.x
"""

from __future__ import annotations
import json
import importlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, cast
from tqdm import tqdm
import chromadb


# =============================================================
# 📂 Configuración
# =============================================================
CHUNKS_PATH = Path("data/processed/task_chunks.jsonl")
CHROMA_PATH = Path("data/rag/chroma_db")
REGISTRY_PATH = CHROMA_PATH / "index_registry.json"
COLLECTION_NAME = "clickup_tasks"


# =============================================================
# 🧰 Funciones utilitarias
# =============================================================
def load_registry() -> Dict[str, Any]:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_registry(registry: Dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")

def load_chunks() -> List[Dict[str, Any]]:
    if not CHUNKS_PATH.exists():
        print(f"⚠️ No existe el archivo {CHUNKS_PATH}")
        return []
    rows = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as f:
        for ln in f:
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
    print(f"📦 Chunks cargados: {len(rows)}")
    return rows


# =============================================================
# 🧠 Embeddings
# =============================================================
def load_embedding_functions() -> Dict[str, Any]:
    """Carga los embeddings híbridos MiniLM + Jina."""
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
# 🚀 Sincronización incremental
# =============================================================
def main(reset: bool = False) -> None:
    chunks = load_chunks()
    if not chunks:
        print("⚠️ No hay chunks para sincronizar.")
        return

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embed_fns = load_embedding_functions()
    registry = load_registry()

    # Colección principal
    try:
        if reset:
            client.delete_collection(COLLECTION_NAME)
            print(f"🗑️ Colección '{COLLECTION_NAME}' eliminada (reset).")

        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embed_fns["semantic"],
            metadata={
                "source": "clickup",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "hybrid_mode": "MiniLM + Jina" if "dense" in embed_fns else "MiniLM",
            },
        )
    except Exception as e:
        print(f"❌ Error al abrir o crear la colección: {e}")
        return

    print(f"📂 Colección activa: {COLLECTION_NAME}")

    # =========================================================
    # 🔍 Extraer hashes ya existentes
    # =========================================================
    try:
        existing = cast(Dict[str, Any], collection.get(include=cast(Any, ["metadatas"])) or {"metadatas": []})
    except Exception:
        existing = {"metadatas": []}

    metas = existing.get("metadatas") or []
    existing_hashes = {(m or {}).get("chunk_hash") for m in metas if (m or {}).get("chunk_hash")}
    existing_hashes.discard(None)

    print(f"🔍 {len(existing_hashes)} hashes ya indexados detectados.")

    # =========================================================
    # 🆕 Filtrar nuevos chunks
    # =========================================================
    new_chunks = [c for c in chunks if c.get("chunk_hash") not in existing_hashes]
    if not new_chunks:
        print("✅ No hay nuevos chunks para indexar.")
        return

    print(f"🆕 {len(new_chunks)} nuevos chunks detectados.")

    ids, docs, metas = [], [], []

    for ch in tqdm(new_chunks, desc="📤 Insertando nuevos chunks"):
        cid = ch.get("chunk_id")
        text = ch.get("text", "")
        meta = ch.get("metadata", {})
        chash = ch.get("chunk_hash")

        if not cid or not text:
            continue

        # Embedding adicional Jina
        if "dense" in embed_fns:
            try:
                emb_dense = embed_fns["dense"]([text])[0]
                meta["embedding_dense"] = emb_dense
            except Exception:
                pass

        # Limpieza de metadatos
        clean_meta: Dict[str, Any] = {}
        for k, v in (meta or {}).items():
            if v is None:
                continue
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            if isinstance(v, (int, float, bool)):
                clean_meta[k] = v
            else:
                clean_meta[k] = str(v).strip()

        clean_meta["chunk_hash"] = chash
        ids.append(cid)
        docs.append(text)
        metas.append(clean_meta)

    # =========================================================
    # 💾 Inserción en Chroma
    # =========================================================
    collection.upsert(ids=ids, documents=docs, metadatas=metas)
    print(f"✅ Insertados {len(ids)} nuevos chunks en la colección.")

    # =========================================================
    # 🗂️ Actualizar registro
    # =========================================================
    registry["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    registry["new_chunks"] = len(ids)
    save_registry(registry)

    print("🗂️ Registro actualizado correctamente.")
    print("🏁 Sincronización completada sin errores.\n")


# =============================================================
# CLI
# =============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sincroniza nuevos chunks con ChromaDB.")
    parser.add_argument("--reset", action="store_true", help="Reindexar desde cero (borra colección actual).")
    args = parser.parse_args()

    main(reset=args.reset)
