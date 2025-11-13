#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Indexa chunks en ChromaDB con control de cambios por content_hash.
Entrada por defecto:
  - data/processed/task_chunks.jsonl (campos: chunk_id, text, metadata{...})
Colección por defecto:
  - clickup_tasks

Uso:
  python data/rag/index/03_index_vector_chroma.py --input data/processed/task_chunks.jsonl
  python data/rag/index/03_index_vector_chroma.py --input data/processed/task_chunks.jsonl --reset
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

import chromadb
from chromadb.config import Settings
from chromadb.api.types import Include
from sentence_transformers import SentenceTransformer

DEFAULT_DB_DIR = "data/rag/chroma_db"
DEFAULT_INPUT = "data/processed/task_chunks.jsonl"
DEFAULT_COLLECTION = "clickup_tasks"
EMB_MODEL = "sentence-transformers/all-MiniLM-L12-v2"

BATCH_IDS = 512

# Tipos simples para evitar peleas con Pylance
Primitive = str | int | float | bool
Metadata = Dict[str, Primitive]


def sha1_text(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            yield json.loads(s)


def normalize_meta(raw: Dict[str, Any]) -> Metadata:
    """
    Normaliza metadatos a tipos primitivos admitidos por Chroma:
    - None -> "" (str)
    - list/tuple/dict -> JSON string
    - str/int/float/bool -> tal cual
    """
    out: Metadata = {}
    for k, v in raw.items():
        key = str(k)
        if v is None:
            out[key] = ""  # str
        elif isinstance(v, (str, int, float, bool)):
            out[key] = v
        elif isinstance(v, (list, tuple, dict)):
            out[key] = json.dumps(v, ensure_ascii=False, sort_keys=True)
        else:
            out[key] = str(v)
    return out


def fetch_existing_hashes(col, ids: List[str]) -> Dict[str, str | None]:
    existing: Dict[str, str | None] = {}
    for i in range(0, len(ids), BATCH_IDS):
        batch_ids = ids[i : i + BATCH_IDS]
        got = col.get(ids=batch_ids, include=cast(Include, ["metadatas"]))
        got_ids = (got or {}).get("ids") or []
        got_metas = (got or {}).get("metadatas") or []
        for idx in range(min(len(got_ids), len(got_metas))):
            _id = got_ids[idx]
            meta = got_metas[idx] or {}
            # meta probablemente ya es dict[str, Primitive], pero lo tratamos como Any por seguridad
            existing[_id] = cast(Dict[str, Any], meta).get("content_hash")
    return existing


def main():
    ap = argparse.ArgumentParser(description="Indexar chunks en ChromaDB (con upsert por hash)")
    ap.add_argument("--input", default=DEFAULT_INPUT, help="Ruta JSONL de chunks")
    ap.add_argument("--collection", default=DEFAULT_COLLECTION, help="Nombre de la colección")
    ap.add_argument("--db", default=DEFAULT_DB_DIR, help="Directorio de la DB persistente")
    ap.add_argument("--reset", action="store_true", help="Borra la colección antes de indexar")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"❌ No existe {input_path}. Ejecuta 02_chunk_tasks.py antes.")

    print(f"🧠 Cargando modelo de embeddings: {EMB_MODEL}")
    _ = SentenceTransformer(EMB_MODEL)  # warmup/check

    print(f"💾 Cargando base vectorial persistente: {args.db}")
    client = chromadb.PersistentClient(path=args.db, settings=Settings(allow_reset=True))

    if args.reset:
        try:
            client.delete_collection(name=args.collection)
            print(f"🧽 Colección '{args.collection}' borrada (reset).")
        except Exception:
            pass

    try:
        col = client.get_collection(args.collection)
    except Exception:
        col = client.create_collection(args.collection, metadata={"hnsw:space": "cosine"})

    print(f"📂 Leyendo tareas desde {input_path}")
    records = list(read_jsonl(input_path))
    if not records:
        print("ℹ️ No hay registros en el archivo de entrada.")
        return

    candidate_ids: List[str] = [rec["chunk_id"] for rec in records if "chunk_id" in rec]
    existing = fetch_existing_hashes(col, candidate_ids)

    to_add_ids: List[str] = []
    to_add_docs: List[str] = []
    to_add_meta: List[Metadata] = []
    to_upd_ids: List[str] = []
    to_upd_docs: List[str] = []
    to_upd_meta: List[Metadata] = []
    unchanged = 0

    for rec in records:
        chunk_id: str = rec["chunk_id"]
        text: str = rec.get("text", "")
        raw_meta: Dict[str, Any] = rec.get("metadata", {}) or {}

        meta: Metadata = normalize_meta(raw_meta)
        c_hash = sha1_text(text)
        meta["chunk_id"] = chunk_id          # str
        meta["content_hash"] = c_hash        # str

        old_hash = existing.get(chunk_id)
        if old_hash is None:
            to_add_ids.append(chunk_id)
            to_add_docs.append(text)
            to_add_meta.append(meta)
        elif old_hash != c_hash:
            to_upd_ids.append(chunk_id)
            to_upd_docs.append(text)
            to_upd_meta.append(meta)
        else:
            unchanged += 1

    # === Escritura (silenciamos Pylance con cast(Any, ...); en runtime es correcto) ===
    if to_add_ids:
        col.add(
            ids=to_add_ids,
            documents=to_add_docs,
            metadatas=cast(Any, to_add_meta),
        )
    if to_upd_ids:
        col.delete(ids=to_upd_ids)
        col.add(
            ids=to_upd_ids,
            documents=to_upd_docs,
            metadatas=cast(Any, to_upd_meta),
        )

    added = len(to_add_ids)
    updated = len(to_upd_ids)

    if added == 0 and updated == 0:
        print("✅ No hay nuevos documentos que indexar ni cambios detectados.")
    else:
        print(f"✅ Indexación completada: añadidos {added}, actualizados {updated}, sin cambios {unchanged}.")


if __name__ == "__main__":
    main()
