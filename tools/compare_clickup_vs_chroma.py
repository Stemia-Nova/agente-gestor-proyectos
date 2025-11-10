#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_clickup_vs_chroma.py — Verifica la sincronización entre ClickUp limpio y ChromaDB
----------------------------------------------------------------------------------------
✔ Carga la base de datos local ChromaDB (colección clickup_tasks)
✔ Compara con el archivo limpio `data/processed/task_clean.json`
✔ Detecta diferencias de IDs y muestra resumen
"""

import os
import json
from pathlib import Path
from typing import Any, cast
from collections import Counter

import chromadb
from chromadb.config import Settings

# ======================================================
# 📁 CONFIGURACIÓN DE RUTAS
# ======================================================

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = ROOT / "data" / "processed" / "task_clean.json"
CHROMA_PATH = ROOT / "data" / "rag" / "chroma_db"
COLLECTION_NAME = "clickup_tasks"

# ======================================================
# 🔍 FUNCIONES AUXILIARES
# ======================================================

def load_clickup_tasks() -> list[dict[str, Any]]:
    """Carga las tareas limpias desde el archivo JSON procesado."""
    if not PROCESSED_PATH.exists():
        raise FileNotFoundError(f"No se encontró {PROCESSED_PATH}")
    data = json.loads(PROCESSED_PATH.read_text(encoding="utf-8"))
    print(f"📥 {len(data)} tareas cargadas desde {PROCESSED_PATH.name}")
    return data


def load_chroma_metas(limit: int | None = None, batch_size: int = 1000) -> dict[str, list[Any]]:
    """Carga los metadatos de la colección Chroma."""
    if not CHROMA_PATH.exists():
        raise FileNotFoundError(f"No se encontró la carpeta de Chroma en {CHROMA_PATH}")

    print(f"🧠 Cargando colección '{COLLECTION_NAME}' desde {CHROMA_PATH} ...")
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    # listar colecciones disponibles
    collections = [c.name for c in client.list_collections()]
    if COLLECTION_NAME not in collections:
        raise ValueError(f"La colección '{COLLECTION_NAME}' no existe. Encontradas: {collections}")

    col = client.get_collection(name=COLLECTION_NAME)

    include = cast(Any, ["metadatas"])
    all_ids, all_metas = [], []
    fetched = 0

    while True:
        res = col.get(include=include, limit=batch_size, offset=fetched)
        ids = res.get("ids", []) or []
        metas = res.get("metadatas")
        # Ensure metas is a non-None iterable before extending
        if metas is None:
            metas = []
        elif not isinstance(metas, list):
            metas = list(metas)

        if not ids:
            break

        all_ids.extend(ids)
        all_metas.extend(metas)
        fetched += len(ids)

        if limit is not None and fetched >= limit:
            break

    print(f"📚 Recuperados {len(all_ids)} documentos de Chroma.")
    return {"ids": all_ids, "metadatas": all_metas}


def extract_task_ids_from_metas(metas: list[dict[str, Any]]) -> set[str]:
    """Extrae los task_id de los metadatos."""
    ids = set()
    for m in metas:
        tid = m.get("task_id") or m.get("id") or m.get("uuid")
        if tid:
            ids.add(str(tid))
    return ids


def compare_sets(clickup_ids: set[str], chroma_ids: set[str]) -> dict[str, set[str]]:
    """Compara los IDs entre ClickUp limpio y Chroma."""
    return {
        "missing_in_chroma": clickup_ids - chroma_ids,
        "missing_in_clickup": chroma_ids - clickup_ids,
        "both": clickup_ids & chroma_ids
    }


def summarize_chroma_fields(metas: list[dict[str, Any]]):
    """Imprime resumen de campos en Chroma."""
    field_counter = Counter()
    for m in metas:
        field_counter.update(m.keys())
    print("\n🧩 Campos más comunes en metadatos:")
    for k, v in field_counter.most_common(10):
        print(f"   • {k}: {v}")


# ======================================================
# 🚀 EJECUCIÓN PRINCIPAL
# ======================================================

def main():
    print("🔍 Comparando datos de ClickUp vs Chroma...\n")

    clickup = load_clickup_tasks()
    clickup_ids = {str(t.get("task_id")) for t in clickup if t.get("task_id")}
    print(f"📊 {len(clickup_ids)} IDs únicos en ClickUp limpio.")

    chroma = load_chroma_metas()
    chroma_ids = extract_task_ids_from_metas(chroma["metadatas"])
    print(f"📊 {len(chroma_ids)} IDs únicos en Chroma.")

    diff = compare_sets(clickup_ids, chroma_ids)

    print("\n📈 RESULTADOS DE COMPARACIÓN")
    print(f"   ✅ Coinciden: {len(diff['both'])}")
    print(f"   ⚠️ En ClickUp pero no en Chroma: {len(diff['missing_in_chroma'])}")
    print(f"   ⚠️ En Chroma pero no en ClickUp: {len(diff['missing_in_clickup'])}")

    if diff["missing_in_chroma"]:
        print("\n❌ Faltan en Chroma:")
        for tid in list(diff["missing_in_chroma"])[:5]:
            print(f"   - {tid}")
        if len(diff["missing_in_chroma"]) > 5:
            print("   ...")

    if diff["missing_in_clickup"]:
        print("\n⚠️ Existen en Chroma pero no en ClickUp:")
        for tid in list(diff["missing_in_clickup"])[:5]:
            print(f"   - {tid}")
        if len(diff["missing_in_clickup"]) > 5:
            print("   ...")

    summarize_chroma_fields(chroma["metadatas"])
    print("\n🏁 Comparación finalizada correctamente.")


if __name__ == "__main__":
    main()