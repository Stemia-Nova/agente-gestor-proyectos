#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_chroma_from_clickup.py — versión Pro
-------------------------------------------
Sincroniza ClickUp → Chroma con:
• Detección dinámica del sprint actual
• Limpieza incremental de tareas
• Tipado compatible con Pylance
"""

import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, cast
import requests
import chromadb
from dotenv import load_dotenv

# ======================================================
# Configuración base
# ======================================================
load_dotenv()
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
CLICKUP_FOLDER_ID = os.getenv("CLICKUP_FOLDER_ID")
CHROMA_PATH = "data/rag/chroma_db"
COLLECTION_NAME = "clickup_tasks"

if not CLICKUP_API_TOKEN or not CLICKUP_FOLDER_ID:
    raise RuntimeError("❌ Falta CLICKUP_API_TOKEN o CLICKUP_FOLDER_ID en el entorno (.env).")

HEADERS = {"Authorization": CLICKUP_API_TOKEN}


# ======================================================
# Utilidades
# ======================================================
def ts_to_dt(ts: str | int | None):
    """Convierte timestamp (ms) a datetime UTC."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
    except Exception:
        return None


def detect_sprint_status(list_obj: Dict[str, Any]) -> str:
    """Determina si un sprint está activo, cerrado o futuro."""
    now = datetime.now(timezone.utc)
    start_dt = ts_to_dt(list_obj.get("start_date"))
    due_dt = ts_to_dt(list_obj.get("due_date"))
    if start_dt and due_dt and start_dt <= now <= due_dt:
        return "actual"
    elif due_dt and now > due_dt:
        return "cerrado"
    elif start_dt and now < start_dt:
        return "futuro"
    return "sin fecha"


def get_lists_from_folder(folder_id: str) -> List[Dict[str, Any]]:
    """Obtiene listas (sprints) de un folder ClickUp."""
    url = f"https://api.clickup.com/api/v2/folder/{folder_id}/list"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return res.json().get("lists", [])


def get_tasks_from_list(list_id: str) -> List[Dict[str, Any]]:
    """Obtiene todas las tareas de una lista."""
    all_tasks: List[Dict[str, Any]] = []
    page = 0
    while True:
        params = {"page": page, "subtasks": "true", "archived": "true"}
        url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
        res = requests.get(url, headers=HEADERS, params=params)
        res.raise_for_status()
        data = res.json()
        tasks = data.get("tasks", [])
        if not tasks:
            break
        all_tasks.extend(tasks)
        if len(tasks) < 100:
            break
        page += 1
    return all_tasks


def clean_task(task: Dict[str, Any], sprint_name: str, sprint_status: str) -> Dict[str, Any]:
    """Convierte una tarea ClickUp en formato limpio para indexar."""
    return {
        "id": task.get("id"),
        "name": task.get("name", "Tarea sin nombre"),
        "status": (task.get("status") or {}).get("status", "sin estado").lower(),
        "priority": (task.get("priority") or {}).get("priority", "sin prioridad").lower()
        if task.get("priority") else "sin prioridad",
        "assignees": ", ".join([a.get("username", "desconocido") for a in task.get("assignees", [])]) or "sin asignar",
        "is_blocked": any("bloquead" in tag.get("name", "").lower() for tag in task.get("tags", [])),
        "sprint": sprint_name,
        "sprint_status": sprint_status,
        "url": f"https://app.clickup.com/t/{task.get('id')}",
        "last_update": task.get("date_updated"),
        "active": sprint_status == "actual",
    }


# ======================================================
# Ejecución principal
# ======================================================
def main() -> None:
    print(f"📁 Archivo .env cargado desde: {os.getcwd()}/.env")
    print(f"🔍 CLICKUP_API_TOKEN detectado: {bool(CLICKUP_API_TOKEN)}")
    print(f"🔍 CLICKUP_FOLDER_ID detectado: {CLICKUP_FOLDER_ID}")

    # Aseguramos al analizador de tipos que CLICKUP_FOLDER_ID no es None en tiempo de ejecución
    assert CLICKUP_FOLDER_ID is not None, "CLICKUP_FOLDER_ID is required by update_chroma_from_clickup.main"

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    all_cleaned: List[Dict[str, Any]] = []
    lists = get_lists_from_folder(CLICKUP_FOLDER_ID)
    print(f"📂 {len(lists)} listas encontradas en el folder.")

    for l in lists:
        sprint_name = l.get("name", "Sprint sin nombre")
        sprint_status = detect_sprint_status(l)
        print(f"📋 {sprint_name}: {sprint_status.upper()}")

        tasks = get_tasks_from_list(l["id"])
        print(f"   ↳ {len(tasks)} tareas encontradas.")

        for t in tasks:
            clean = clean_task(t, sprint_name, sprint_status)
            all_cleaned.append(clean)

    print(f"✅ Total de tareas limpias: {len(all_cleaned)}")

    if not all_cleaned:
        print("⚠️ No se encontraron tareas nuevas.")
        return

    ids = [t["id"] for t in all_cleaned]
    docs = [json.dumps(t, ensure_ascii=False) for t in all_cleaned]
    metas: List[Dict[str, Any]] = all_cleaned  # ✅ corregido para tipado exacto

    # Normaliza metadatas a valores primitivos (str|int|float|bool) requeridos por chromadb
    def _normalize_metadata(m: Dict[str, Any]) -> Dict[str, str | int | float | bool]:
        normalized: Dict[str, str | int | float | bool] = {}
        for k, v in m.items():
            # Permitir valores primitivos tal cual (None -> empty string)
            if isinstance(v, (str, int, float, bool)):
                normalized[k] = v
            elif v is None:
                normalized[k] = ""
            else:
                # Serializar valores no primitivos a JSON para garantizar tipos válidos
                try:
                    normalized[k] = json.dumps(v, ensure_ascii=False)
                except Exception:
                    normalized[k] = str(v)
        return normalized

    metadatas: List[Mapping[str, str | int | float | bool]] = [_normalize_metadata(m) for m in metas]

    # chromadb typing expects OneOrMany[Metadata]; cast to Any to satisfy the type checker
    collection.upsert(ids=ids, documents=docs, metadatas=cast(Any, metadatas))
    print(f"📤 {len(ids)} tareas insertadas o actualizadas en la colección.")
    print("🏁 Sincronización completada correctamente.\n")


if __name__ == "__main__":
    main()
