#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sincroniza la base vectorial ChromaDB con los datos de ClickUp.

Solo actualiza el sprint activo (los sprints cerrados permanecen congelados).
Crea una base independiente por sprint bajo: data/rag/chroma_db/{sprint_n}/
y mantiene un registro en data/rag/chroma_db/index_registry.json
"""

import json
import os
from datetime import datetime
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb

# ===========================================================
# CONFIG
# ===========================================================
CHROMA_BASE = Path("data/rag/chroma_db")
REGISTRY_FILE = CHROMA_BASE / "index_registry.json"
EMB_MODEL = "sentence-transformers/all-MiniLM-L12-v2"


def load_registry() -> dict:
    """Carga o crea el registro de indexación."""
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_registry(registry: dict):
    """Guarda el registro actualizado."""
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def reindex_sprint(tasks: list, sprint_name: str, sprint_path: Path):
    """Reindexa las tareas del sprint en su propio subdirectorio."""
    client = chromadb.PersistentClient(path=str(sprint_path))
    model = SentenceTransformer(EMB_MODEL)

    try:
        client.delete_collection("clickup_tasks")
    except Exception:
        pass

    col = client.create_collection("clickup_tasks")

    docs, metas, ids = [], [], []
    for task in tasks:
        meta = task.get("metadata", {})
        docs.append(task["text"])
        metas.append(meta)
        ids.append(meta.get("task_id", f"{sprint_name}_{len(ids)}"))

    print(f"🧠 Generando embeddings para {len(docs)} tareas...")
    embeddings = model.encode(docs, show_progress_bar=True, convert_to_numpy=True)

    col.add(documents=docs, embeddings=embeddings, metadatas=metas, ids=ids)
    print(f"✅ Sprint '{sprint_name}' reindexado con {len(docs)} tareas.")


def sync_chroma_with_clickup(json_path: Path):
    """Actualiza solo el sprint activo en base al JSON exportado desde ClickUp."""
    print(f"📂 Cargando datos desde: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        tasks = [json.loads(line) for line in f if line.strip()]

    registry = load_registry()

    # Detectar sprints únicos en los datos
    sprints = sorted({t["metadata"].get("sprint", "Desconocido") for t in tasks})

    for sprint in sprints:
        sprint_meta = registry.get(sprint, {"status": "active", "last_update": None})
        status = sprint_meta["status"]

        if status == "closed":
            print(f"🧊 {sprint} está cerrado. No se actualiza.")
            continue

        print(f"🔁 Actualizando {sprint}...")
        sprint_tasks = [t for t in tasks if t["metadata"].get("sprint") == sprint]
        sprint_path = CHROMA_BASE / sprint.lower().replace(" ", "_")
        reindex_sprint(sprint_tasks, sprint, sprint_path)

        sprint_meta["last_update"] = datetime.utcnow().isoformat()
        registry[sprint] = sprint_meta

    save_registry(registry)
    print("💾 Registro actualizado correctamente.")


if __name__ == "__main__":
    json_path = Path("data/processed/task_chunks.jsonl")
    if not json_path.exists():
        raise FileNotFoundError("❌ No se encontró el archivo de tareas enriquecidas (task_chunks.jsonl).")
    sync_chroma_with_clickup(json_path)
