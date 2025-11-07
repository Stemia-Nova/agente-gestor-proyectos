#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Actualiza o crea colecciones ChromaDB por sprint a partir de los chunks procesados.
Cada sprint se almacena en una base independiente:
    data/rag/chroma_db/Sprint N/chroma.sqlite3

También mantiene un índice de control:
    data/rag/chroma_db/index_registry.json

Este script puede ejecutarse periódicamente para mantener sincronizados los datos
de ClickUp ya transformados.
"""

from __future__ import annotations

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import chromadb

# ============================================================
# CONFIGURACIÓN
# ============================================================

EMBED_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
CHROMA_BASE = Path("data/rag/chroma_db")
COLLECTION_NAME = "clickup_tasks"

PROCESSED_INPUT = Path("data/processed/task_chunks.jsonl")  # generado por 02_chunk_tasks.py


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra el archivo {path}")
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_registry() -> Dict[str, Dict[str, Any]]:
    reg_path = CHROMA_BASE / "index_registry.json"
    if not reg_path.exists():
        return {}
    with open(reg_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}


def _save_registry(registry: Dict[str, Dict[str, Any]]) -> None:
    CHROMA_BASE.mkdir(parents=True, exist_ok=True)
    with open(CHROMA_BASE / "index_registry.json", "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def _get_or_create_collection(sprint_name: str):
    """Crea o carga la colección de ChromaDB de un sprint concreto."""
    sprint_dir = CHROMA_BASE / sprint_name
    sprint_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(sprint_dir))
    return client.get_or_create_collection(COLLECTION_NAME)


# ============================================================
# PROCESAMIENTO PRINCIPAL
# ============================================================

def main(reset: bool = False) -> None:
    print(f"📂 Leyendo tareas desde: {PROCESSED_INPUT}")
    data = _read_jsonl(PROCESSED_INPUT)
    if not data:
        print("❌ No hay tareas en el archivo procesado.")
        return

    # --- agrupamos por sprint ---
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in data:
        meta = item.get("metadata", {})
        sprint = meta.get("sprint", "Sprint_Desconocido")
        grouped.setdefault(sprint, []).append(item)

    print(f"📊 Detectados {len(grouped)} sprints: {', '.join(grouped.keys())}")

    # --- cargamos modelo de embeddings ---
    print(f"🧠 Cargando modelo de embeddings: {EMBED_MODEL}")
    embedder = SentenceTransformer(EMBED_MODEL)

    # --- cargamos o inicializamos el registro ---
    registry = _load_registry()

    for sprint, items in grouped.items():
        print(f"\n🔹 Procesando {sprint} ({len(items)} tareas)...")
        col = _get_or_create_collection(sprint)

        # limpiar colección (solo si reset o sprint no existía antes)
        if reset or sprint not in registry:
            try:
                col.delete(where={})
            except Exception:
                pass

        # preparamos datos
        docs = [it.get("text") or it.get("chunk") or "" for it in items]
        metas = [it.get("metadata", {}) for it in items]
        ids = [m.get("task_id", f"{sprint}_{i}") for i, m in enumerate(metas)]

        # deduplicamos por ID
        unique = {}
        for i, tid in enumerate(ids):
            unique[tid] = (docs[i], metas[i])
        ids, docs, metas = zip(*[(tid, d, m) for tid, (d, m) in unique.items()])

        # calculamos embeddings
        embeds = embedder.encode(list(docs), convert_to_numpy=True, normalize_embeddings=True)

        # añadimos o actualizamos
        embeds_list = [e.tolist() if hasattr(e, "tolist") else e for e in embeds]

        col.upsert(
            ids=list(ids),
            embeddings=embeds_list,
            documents=list(docs),
            metadatas=list(metas)
        )

        # actualizamos registro
        registry[sprint] = {
            "status": "active",
            "last_update": datetime.now().isoformat(),
            "total_tasks": len(ids)
        }

        print(f"✅ {len(ids)} tareas indexadas en {sprint}.")

    # marcamos como cerrados los que ya no están presentes
    for sprint in list(registry.keys()):
        if sprint not in grouped:
            registry[sprint]["status"] = "closed"

    _save_registry(registry)
    print(f"\n💾 Registro actualizado en: {CHROMA_BASE / 'index_registry.json'}")
    print("🎯 Sincronización completada con éxito.")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Actualizar ChromaDB por sprint.")
    parser.add_argument("--reset", action="store_true", help="Reinicia las colecciones antes de indexar.")
    args = parser.parse_args()
    main(reset=args.reset)
