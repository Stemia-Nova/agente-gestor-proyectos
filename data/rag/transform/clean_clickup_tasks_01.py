#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_clickup_tasks_01.py — Limpieza y normalización completa de tareas ClickUp
-------------------------------------------------------------------------------
✔ Obtiene tareas y subtareas de todas las listas de un Folder
✔ Mantiene sprints cerrados (modo lectura) y actual
✔ Incluye tareas sin asignar o sin prioridad
✔ Añade campos parent_id e is_subtask
"""

import os
import json
import requests
from datetime import datetime
from collections import defaultdict
from typing import Any, Dict, List
from dotenv import load_dotenv
import pathlib

# ======================================================
# 📦 CARGA DE ENTORNO (.env desde raíz del proyecto)
# ======================================================
ROOT_DIR = pathlib.Path(__file__).resolve().parents[3]
env_path = ROOT_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"📁 Archivo .env cargado desde: {env_path}")
else:
    print("⚠️ No se encontró el archivo .env en la raíz del proyecto.")

CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
CLICKUP_FOLDER_ID = os.getenv("CLICKUP_FOLDER_ID")
API_BASE = "https://api.clickup.com/api/v2"

print(f"🔍 CLICKUP_API_TOKEN detectado: {bool(CLICKUP_API_TOKEN)}")
print(f"🔍 CLICKUP_FOLDER_ID detectado: {CLICKUP_FOLDER_ID}")

# ======================================================
# 📡 OBTENER TODAS LAS TAREAS DEL FOLDER
# ======================================================
def get_tasks_from_api() -> List[Dict[str, Any]]:
    """Obtiene todas las tareas (incluidas subtareas) desde el folder."""
    if not CLICKUP_API_TOKEN or not CLICKUP_FOLDER_ID:
        raise ValueError("❌ Falta CLICKUP_API_TOKEN o CLICKUP_FOLDER_ID en el entorno.")

    headers = {"Authorization": CLICKUP_API_TOKEN}
    lists_url = f"{API_BASE}/folder/{CLICKUP_FOLDER_ID}/list"

    print(f"📡 Obteniendo listas del Folder {CLICKUP_FOLDER_ID}...")
    resp = requests.get(lists_url, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"⚠️ Error {resp.status_code} al obtener listas: {resp.text}")

    lists = resp.json().get("lists", [])
    print(f"✅ {len(lists)} listas encontradas en el folder.")
    all_tasks: List[Dict[str, Any]] = []

    for lst in lists:
        list_id = lst["id"]
        list_name = lst.get("name", "Sin nombre")

        print(f"📋 Obteniendo tareas de '{list_name}' ({list_id})...")
        tasks_url = f"{API_BASE}/list/{list_id}/task"
        params = {"archived": "false", "include_subtasks": "true"}

        res = requests.get(tasks_url, headers=headers, params=params, timeout=30)
        if res.status_code != 200:
            print(f"⚠️ Error {res.status_code} al obtener tareas de {list_name}")
            continue

        data = res.json()
        tasks = data.get("tasks", [])
        print(f"   ↳ {len(tasks)} tareas encontradas.")
        for t in tasks:
            t["list_name"] = list_name
        all_tasks.extend(tasks)

    print(f"✅ Total de tareas obtenidas: {len(all_tasks)}")
    return all_tasks

# ======================================================
# 🧹 LIMPIAR Y NORMALIZAR TAREAS
# ======================================================
def clean_tasks(raw_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Limpia, normaliza e incluye todas las tareas y subtareas."""
    cleaned: List[Dict[str, Any]] = []

    for task in raw_tasks:
        fields = task.get("custom_fields", [])
        sprint_name = next((f["value"] for f in fields if "Sprint" in f.get("name", "")), task.get("list_name", "Sin sprint"))
        assignees = [a.get("username") or a.get("email") for a in task.get("assignees", [])]
        assignees_text = ", ".join(assignees) if assignees else "Sin asignar"

        priority = task.get("priority", {}).get("priority", "Sin prioridad")
        status = task.get("status", {}).get("status", "desconocido").lower()

        parent_id = task.get("parent")
        is_subtask = bool(parent_id)

        tags = [t.get("name", "").lower() for t in task.get("tags", [])]
        is_blocked = any("bloquead" in tag for tag in tags)

        cleaned.append({
            "id": task["id"],
            "name": task["name"],
            "status": status,
            "priority": priority,
            "assignees": assignees_text,
            "sprint": sprint_name,
            "parent_id": parent_id,
            "is_subtask": is_subtask,
            "is_blocked": is_blocked,
            "date_created": task.get("date_created"),
            "date_updated": task.get("date_updated"),
            "markdown": (
                f"### {task['name']}\n"
                f"- Estado: {status}\n"
                f"- Prioridad: {priority}\n"
                f"- Asignado a: {assignees_text}\n"
                f"- Sprint: {sprint_name}\n"
                f"- Subtarea: {is_subtask}\n"
                f"- Bloqueada: {is_blocked}\n"
            ),
        })

    cleaned = assign_sprint_status(cleaned)
    print(f"🧩 {len(cleaned)} tareas limpias y listas para indexar (incluidas subtareas).")
    return cleaned

# ======================================================
# 🧮 CALCULAR ESTADO DEL SPRINT
# ======================================================
def assign_sprint_status(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Marca sprints como 'actual' o 'cerrado' según sus tareas."""
    sprint_states = defaultdict(list)
    for t in tasks:
        sprint_states[t.get("sprint", "Sin sprint")].append(t.get("status", "").lower())

    sprint_map = {
        sprint: (
            "cerrado"
            if all(s in {"completado", "finalizado", "cerrado"} for s in states)
            else "actual"
        )
        for sprint, states in sprint_states.items()
    }

    for t in tasks:
        t["sprint_status"] = sprint_map.get(t.get("sprint"), "actual")

    return tasks

# ======================================================
# 🧩 PRUEBA LOCAL
# ======================================================
if __name__ == "__main__":
    print("🧪 Ejecutando prueba de obtención y limpieza de tareas...")
    try:
        raw = get_tasks_from_api()
        clean = clean_tasks(raw)
        tmp_path = "data/rag/tmp/tasks_clean_demo.json"
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, ensure_ascii=False)
        print(f"✅ Tareas procesadas: {len(clean)} (guardadas en {tmp_path})")
    except Exception as e:
        print(f"❌ Error: {e}")
