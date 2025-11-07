#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Actualiza automáticamente la base ChromaDB y el registro de sprints.

Lee data/processed/task_chunks.jsonl, agrupa las tareas por sprint
y crea/actualiza una colección por sprint (sprint_1, sprint_2...).
También genera index_registry.json con el estado y conteo de cada sprint.
"""

import json
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import chromadb
from sentence_transformers import SentenceTransformer

# =============================================================
# Configuración
# =============================================================
INPUT_FILE = Path("data/processed/task_chunks.jsonl")
CHROMA_BASE = Path("data/rag/chroma_db")
COLLECTION_NAME = "clickup_tasks"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
REGISTRY_FILE = CHROMA_BASE / "index_registry.json"

# =============================================================
# Helpers
# =============================================================
def load_chunks() -> list[dict]:
    """Carga las tareas chunkificadas desde el JSONL."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"❌ No se encontró {INPUT_FILE}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def group_by_sprint(tasks: list[dict]) -> dict[str, list[dict]]:
    """Agrupa las tareas por nombre de sprint."""
    grouped: dict[str, list[dict]] = {}
    for t in tasks:
        sprint = (t.get("metadata", {}) or {}).get("sprint") or "Sin Sprint"
        grouped.setdefault(sprint, []).append(t)
    return grouped


# =============================================================
# Proceso principal
# =============================================================
def main():
    print(f"📂 Leyendo tareas desde: {INPUT_FILE}")
    tasks = load_chunks()
    grouped = group_by_sprint(tasks)
    print(f"📊 Detectados {len(grouped)} sprints.")

    embedder = SentenceTransformer(EMBED_MODEL)

    registry = {}

    for i, (sprint_name, sprint_tasks) in enumerate(grouped.items(), start=1):
        sprint_folder = CHROMA_BASE / sprint_name.lower().replace(" ", "_")
        sprint_folder.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(sprint_folder))

        # 🔁 Reset colección si ya existe (Chroma >= 0.5.0)
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

        # Crear colección limpia
        col = client.create_collection(name=COLLECTION_NAME)

        print(f"🧠 Indexando Sprint {sprint_name} ({len(sprint_tasks)} tareas)...")

        ids, docs, metas = [], [], []
        for t in sprint_tasks:
            ids.append(t["chunk_id"])
            docs.append(t["text"])
            metas.append(t["metadata"])

        # Generar embeddings e insertar
        embeddings = embedder.encode(docs, show_progress_bar=False).tolist()
        col.add(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)

        # Registrar metadatos de sprint
        registry[sprint_name] = {
            "status": "active" if i == len(grouped) else "archived",
            "count": len(sprint_tasks),
            "last_update": datetime.now().isoformat(timespec="seconds"),
        }

    # Guardar el registro global
    CHROMA_BASE.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Registro actualizado en: {REGISTRY_FILE}")
    for k, v in registry.items():
        print(f"  - {k}: {v['count']} tareas ({v['status']})")


# =============================================================
# Entry point
# =============================================================
if __name__ == "__main__":
    main()
