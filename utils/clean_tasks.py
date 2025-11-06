#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Limpia y normaliza las tareas descargadas desde ClickUp (varios Sprints)
para generar un archivo `task_clean.jsonl` listo para la etapa de naturalización.
"""

import json
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

RAW_DIR = Path("data/rag/ingest")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================
# LOCALIZAR ÚLTIMO ARCHIVO DE INGESTA
# =============================================================

json_files = sorted(RAW_DIR.glob("clickup_tasks_all_*.json"))
if not json_files:
    raise FileNotFoundError("❌ No se encontró ningún archivo JSON crudo en data/rag/ingest/")
latest_file = json_files[-1]

print(f"📂 Leyendo tareas desde: {latest_file}")

# =============================================================
# FUNCIONES AUXILIARES
# =============================================================

def parse_date(ts):
    """Convierte timestamps de ClickUp a fecha legible."""
    try:
        return datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d")
    except Exception:
        return ""

def normalize_status(status_obj):
    """Mapea los estados de ClickUp a categorías uniformes."""
    if not status_obj or not isinstance(status_obj, dict):
        return "unknown"

    raw_status = (status_obj.get("status") or "").lower().strip()
    status_type = (status_obj.get("type") or "").lower().strip()

    # Mapeo principal
    if raw_status in ["to do", "por hacer", "pendiente"]:
        return "to_do"
    if raw_status in ["in progress", "en progreso", "working on it"]:
        return "in_progress"
    if raw_status in ["in review", "pendiente de revisión", "review"]:
        return "in_review"
    if raw_status in ["done", "complete", "completada", "finalizada", "terminada"]:
        return "done"
    if "block" in raw_status:
        return "blocked"

    # Basado en tipo genérico
    if status_type == "open":
        return "to_do"
    if status_type == "custom":
        return "in_progress"
    if status_type == "done":
        return "done"

    return raw_status or "unknown"

# =============================================================
# PROCESAMIENTO PRINCIPAL
# =============================================================

with open(latest_file, "r", encoding="utf-8") as f:
    data = json.load(f)

tasks = data.get("tasks", [])
print(f"✅ {len(tasks)} tareas encontradas.")

output_path = PROCESSED_DIR / "task_clean.jsonl"

with open(output_path, "w", encoding="utf-8") as fout:
    for t in tqdm(tasks, desc="🧹 Limpiando tareas"):
        status = normalize_status(t.get("status", {})).lower()
        project = t.get("project", {}).get("name", "")
        list_name = t.get("list", {}).get("name", "")
        sprint = list_name  # ClickUp usa listas como sprints
        desc = t.get("description") or ""
        assignees = ", ".join(a.get("username", "") for a in t.get("assignees", [])) or ""
        tags = ", ".join(tag.get("name", "").lower() for tag in t.get("tags", [])) or ""

        metadata = {
            "status": status,
            "project": project,
            "project_id": t.get("project", {}).get("id", ""),
            "list": list_name,
            "sprint": sprint,
            "sprint_id": t.get("list", {}).get("id", ""),
            "priority": t.get("priority", {}).get("priority") if t.get("priority") else "",
            "assignees": assignees,
            "tags": tags,
            "is_blocked": "bloque" in tags,
            "has_doubts": "duda" in tags,
            "is_urgent": "urgent" in tags or "urgente" in tags,
        }

        clean_task = {
            "task_id": t.get("id"),
            "name": t.get("name", "Sin título"),
            "description": desc,
            "status": status,
            "date_created": parse_date(t.get("date_created")),
            "date_updated": parse_date(t.get("date_updated")),
            "metadata": metadata,
        }

        fout.write(json.dumps(clean_task, ensure_ascii=False) + "\n")

print(f"💾 Archivo limpio generado: {output_path}")
print("✅ Limpieza completada con éxito.")
