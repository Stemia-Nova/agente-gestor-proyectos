#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Actualiza únicamente el sprint ACTIVO desde ClickUp
y genera/actualiza su índice vectorial persistente en ChromaDB.

Flujo:
  1️⃣ Detecta el sprint activo (lista actual en ClickUp)
  2️⃣ Descarga sus tareas (incluso completadas)
  3️⃣ Limpia y naturaliza los datos
  4️⃣ Genera chunks y actualiza la colección Chroma correspondiente
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
import re

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)

CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
FOLDER_ID = os.getenv("CLICKUP_FOLDER_ID")  # debe estar definido en .env

HEADERS = {"Authorization": CLICKUP_API_TOKEN}
BASE_URL = "https://api.clickup.com/api/v2"

DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CHROMA_DIR = DATA_DIR / "rag" / "chroma_db"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "sentence-transformers/all-MiniLM-L12-v2"

# =====================================================
# AUXILIARES
# =====================================================
def get_active_sprint():
    """Devuelve el nombre e ID del sprint actual."""
    url = f"{BASE_URL}/folder/{FOLDER_ID}/list"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    lists = resp.json().get("lists", [])

    # buscamos la lista con 'active' o la última creada
    active = None
    for l in lists:
        if not l.get("archived"):
            active = l
    if not active and lists:
        active = lists[-1]

    if not active:
        raise ValueError("❌ No se encontró ningún sprint activo.")
    print(f"🏁 Sprint activo detectado: {active['name']} (ID: {active['id']})")
    return active["name"], active["id"]

def flatten_json(d, parent_key="", sep="."):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_json(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, json.dumps(v, ensure_ascii=False)))
        else:
            items.append((new_key, v))
    return dict(items)

def tokenize(text):
    return re.findall(r"\w+", text.lower())

# =====================================================
# PIPELINE DE PROCESO
# =====================================================
def fetch_tasks(list_id):
    """Descarga tareas del sprint actual (activas + completadas)."""
    url = f"{BASE_URL}/list/{list_id}/task?include_closed=true"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json().get("tasks", [])
    print(f"📥 {len(data)} tareas descargadas del sprint.")
    return data

def clean_tasks(tasks, sprint_name):
    """Limpia y normaliza tareas básicas."""
    cleaned = []
    for t in tasks:
        status = (t.get("status", {}).get("status") or "").lower()
        desc = t.get("description") or ""
        tags = ", ".join(tag.get("name", "") for tag in t.get("tags", []))
        assignees = ", ".join(a.get("username", "") for a in t.get("assignees", []))

        metadata = {
            "status": status,
            "project": t.get("project", {}).get("name", ""),
            "list": t.get("list", {}).get("name", ""),
            "sprint": sprint_name,
            "priority": (t.get("priority", {}) or {}).get("priority", ""),
            "assignees": assignees,
            "tags": tags,
            "is_blocked": "bloque" in tags.lower(),
            "has_doubts": "duda" in tags.lower(),
            "is_urgent": "urgente" in tags.lower() or "urgent" in tags.lower(),
        }

        cleaned.append({
            "task_id": t.get("id"),
            "name": t.get("name", "Sin título"),
            "description": desc,
            "metadata": metadata,
        })
    return cleaned

def naturalize_task(task):
    """Convierte la tarea en texto narrativo."""
    m = task["metadata"]
    texto = (
        f"La tarea '{task['name']}' pertenece al proyecto '{m.get('project')}' "
        f"en el sprint '{m.get('sprint')}'. "
        f"Actualmente está en estado '{m.get('status')}'. "
        f"Tiene prioridad '{m.get('priority')}'. "
        f"{'Está asignada a ' + m.get('assignees') + '. ' if m.get('assignees') else 'Sin responsables asignados. '}"
        f"Tiene las etiquetas {m.get('tags') or 'ninguna'}. "
        f"Descripción: {task['description'] or 'sin descripción disponible.'}"
    )
    return texto

def chunk_tasks(natural_texts, chunk_size=512):
    """Divide las tareas largas en fragmentos de texto más pequeños."""
    chunks = []
    for i, t in enumerate(natural_texts):
        if len(t["text"]) <= chunk_size:
            chunks.append(t)
        else:
            for idx in range(0, len(t["text"]), chunk_size):
                part = t["text"][idx:idx+chunk_size]
                new = dict(t)
                new["text"] = part
                new["chunk_id"] = f"{t['task_id']}_chunk_{idx//chunk_size}"
                chunks.append(new)
    return chunks

# =====================================================
# INDEXACIÓN EN CHROMA
# =====================================================
def update_chroma(chunks, sprint_name):
    print(f"🧠 Actualizando base vectorial del sprint: {sprint_name}")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(sprint_name)
    model = SentenceTransformer(MODEL_NAME)

    existing_ids = set(collection.get(ids=None, limit=100000).get("ids", []))
    new_chunks = [c for c in chunks if c["chunk_id"] not in existing_ids]

    for c in tqdm(new_chunks):
        emb = model.encode(c["text"], convert_to_numpy=True).tolist()
        meta = c.get("metadata", {})
        collection.add(
            ids=[c["chunk_id"]],
            documents=[c["text"]],
            metadatas=[meta],
            embeddings=[emb],
        )

    print(f"✅ {len(new_chunks)} nuevos chunks indexados en '{sprint_name}'.")

# =====================================================
# PROGRAMA PRINCIPAL
# =====================================================
def main():
    print("🚀 Actualizando sprint activo...")
    sprint_name, list_id = get_active_sprint()
    tasks = fetch_tasks(list_id)
    cleaned = clean_tasks(tasks, sprint_name)
    natural = [{"task_id": t["task_id"], "text": naturalize_task(t), "metadata": t["metadata"], "chunk_id": t["task_id"]} for t in cleaned]
    chunks = chunk_tasks(natural)
    update_chroma(chunks, sprint_name)
    print("✅ Base vectorial actualizada correctamente.")

if __name__ == "__main__":
    main()
