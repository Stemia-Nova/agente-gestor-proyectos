#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Actualiza automáticamente la colección del sprint activo en ChromaDB,
sin reindexar todo el proyecto.

Detecta:
 - Nuevas tareas → se añaden
 - Tareas editadas → se actualizan (hash cambiado)
 - Tareas sin cambios → se mantienen

Compatible con ChromaDB >= 0.5.5
"""

import os
import json
import hashlib
import requests
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from chromadb.api.types import IncludeEnum  # ✅ Import oficial
from typing import Dict, Any, Optional, List


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / ".env")

API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
FOLDER_ID = os.getenv("CLICKUP_FOLDER_ID")
DB_DIR = BASE_DIR / "data" / "rag" / "chroma_db"
MODEL_NAME = "sentence-transformers/all-MiniLM-L12-v2"

HEADERS = {"Authorization": API_TOKEN}
BASE_URL = "https://api.clickup.com/api/v2"
client = chromadb.PersistentClient(path=str(DB_DIR))

# =========================================================
# HELPERS
# =========================================================

def compute_hash(text: str) -> str:
    """Devuelve un hash MD5 para detectar cambios de contenido."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def fetch_active_sprint() -> tuple[str, str]:
    """Obtiene el sprint activo (lista no archivada) del folder indicado."""
    url = f"{BASE_URL}/folder/{FOLDER_ID}/list"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        raise RuntimeError(f"Error al obtener listas del folder {FOLDER_ID}: {resp.text}")

    data = resp.json()
    active = next((l for l in data.get("lists", []) if not l.get("archived")), None)
    if not active:
        raise ValueError("❌ No se encontró ningún sprint activo en ClickUp.")
    print(f"🏁 Sprint activo detectado: {active['name']} ({active['id']})")
    return active["name"], active["id"]


def fetch_tasks(list_id: str) -> list[dict[str, Any]]:
    """Descarga todas las tareas del sprint activo."""
    url = f"{BASE_URL}/list/{list_id}/task?archived=false"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        raise RuntimeError(f"Error al obtener tareas: {resp.text}")
    data = resp.json()
    print(f"📦 {len(data.get('tasks', []))} tareas encontradas en el sprint activo.")
    return data.get("tasks", [])


def flatten_task(task: dict[str, Any]) -> dict[str, str]:
    """Simplifica el JSON de la tarea ClickUp."""
    return {
        "id": task.get("id", ""),
        "name": task.get("name", "Sin título"),
        "desc": task.get("description", ""),
        "status": task.get("status", {}).get("status", ""),
        "sprint": task.get("list", {}).get("name", ""),
        "project": task.get("project", {}).get("name", ""),
        "priority": (task.get("priority", {}) or {}).get("priority", ""),
        "assignees": ", ".join(a.get("username", "") for a in task.get("assignees", [])),
        "tags": ", ".join(t.get("name", "") for t in task.get("tags", [])),
    }

# =========================================================
# MAIN UPDATE LOGIC
# =========================================================

def update_active_sprint() -> None:
    """Sincroniza la base vectorial con el sprint activo de ClickUp."""
    sprint_name, sprint_id = fetch_active_sprint()
    tasks = fetch_tasks(sprint_id)
    model = SentenceTransformer(MODEL_NAME)

    collection = client.get_or_create_collection(sprint_name)

    # ✅ Tipado correcto con IncludeEnum (nuevo API)
    existing = collection.get(ids=None, include=IncludeEnum.metadatas)  # type: ignore

    existing_ids = existing.ids if hasattr(existing, "ids") else []
    existing_metas = existing.metadatas if hasattr(existing, "metadatas") else []

    existing_hashes: Dict[str, str] = {}
    for i, meta in zip(existing_ids, existing_metas):
        if meta and isinstance(meta, dict):
            existing_hashes[i] = meta.get("hash", "")

    print(f"📊 Colección '{sprint_name}' contiene {len(existing_hashes)} documentos existentes.")
    to_add, to_update = [], []

    # Analizar cambios
    for t in tqdm(tasks, desc="🔍 Analizando tareas"):
        doc = flatten_task(t)
        text = (
            f"La tarea '{doc['name']}' pertenece al proyecto '{doc['project']}' "
            f"en el sprint '{doc['sprint']}'. Estado: {doc['status']}. "
            f"Prioridad: {doc['priority']}. Asignado a: {doc['assignees']}. "
            f"Etiquetas: {doc['tags']}. Descripción: {doc['desc']}"
        )
        hash_ = compute_hash(text)

        if doc["id"] not in existing_hashes:
            to_add.append((doc, text, hash_))
        elif existing_hashes[doc["id"]] != hash_:
            to_update.append((doc, text, hash_))

    print(f"🆕 Nuevas tareas: {len(to_add)} | ♻️ Actualizadas: {len(to_update)}")

    # Añadir nuevas tareas
    for doc, text, hash_ in to_add:
        emb = model.encode(text, convert_to_numpy=True).tolist()
        metadata = {**doc, "hash": hash_}
        collection.add(ids=[doc["id"]], documents=[text], embeddings=[emb], metadatas=[metadata])

    # Reindexar las modificadas
    for doc, text, hash_ in to_update:
        print(f"♻️ Actualizando tarea modificada: {doc['name']}")
        emb = model.encode(text, convert_to_numpy=True).tolist()
        metadata = {**doc, "hash": hash_}
        collection.delete(ids=[doc["id"]])
        collection.add(ids=[doc["id"]], documents=[text], embeddings=[emb], metadatas=[metadata])

    print("✅ Actualización completada con éxito.")
    print(f"💾 Base vectorial actualizada para el sprint: {sprint_name}")


# =========================================================
# OPTIONAL MODULAR FUNCTION
# =========================================================

def sync_sprint() -> str:
    """
    Función reutilizable para integrarse en el agente o chatbot.
    Devuelve el nombre del sprint actualizado.
    """
    try:
        update_active_sprint()
        return "✅ Sprint activo sincronizado correctamente."
    except Exception as e:
        return f"❌ Error durante la sincronización: {e}"


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    update_active_sprint()
