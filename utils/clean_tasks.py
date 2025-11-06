#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Limpieza y normalización de tareas ClickUp (multi-sprint).
Genera un archivo `data/processed/task_clean.jsonl` listo para la etapa de naturalización.
Mantiene los campos: sprint, proyecto, lista, prioridad, estado y etiquetas.
"""

import json
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

RAW_DIR = Path("data/rag/ingest")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

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

    raw = (status_obj.get("status") or "").lower()
    typ = (status_obj.get("type") or "").lower()

    if "to do" in raw or "pendiente" in raw:
        return "to_do"
    if "in progress" in raw or "progreso" in raw:
        return "in_progress"
    if "review" in raw:
        return "in_review"
    if "done" in raw or "complete" in raw or "finalizada" in raw:
        return "done"
    if "block" in raw:
        return "blocked"

    if typ == "open":
        return "to_do"
    if typ == "custom":
        return "in_progress"
    if typ == "done":
        return "done"

    return raw or "unknown"

# =============================================================
# PROCESAMIENTO PRINCIPAL
# =============================================================

json_files = sorted(RAW_DIR.glob("clickup_tasks_all_*.json"))
if not json_files:
    raise FileNotFoundError("❌ No se encontró ningún archivo JSON en data/rag/ingest/")
latest = json_files[-1]

print(f"📂 Leyendo tareas desde: {latest}")

with open(latest, "r", encoding="utf-8") as f:
    data = json.load(f)

tasks = data.get("tasks", [])
print(f"✅ {len(tasks)} tareas encontradas.")

output = PROCESSED_DIR / "task_clean.jsonl"
with open(output, "w", encoding="utf-8") as fout:
    for t in tqdm(tasks, desc="🧹 Limpiando tareas"):
        status = normalize_status(t.get("status", {}))
        project = t.get("project", {}).get("name", "")
        list_name = t.get("list", {}).get("name", "")
        sprint = t.get("sprint_name", list_name)
        desc = t.get("description") or ""
        assignees = ", ".join(a.get("username", "") for a in t.get("assignees", [])) or ""
        tags = ", ".join(tag.get("name", "") for tag in t.get("tags", [])) or ""

        metadata = {
            "status": status,
            "project": project,
            "list": list_name,
            "sprint": sprint,
            "priority": t.get("priority", {}).get("priority") if t.get("priority") else "",
            "assignees": assignees,
            "tags": tags,
            "is_blocked": "bloque" in tags.lower(),
            "has_doubts": "duda" in tags.lower(),
            "is_urgent": "urgent" in tags.lower() or "urgente" in tags.lower(),
        }

        record = {
            "task_id": t.get("id"),
            "name": t.get("name", "Sin título"),
            "description": desc,
            "status": status,
            "date_created": parse_date(t.get("date_created")),
            "date_updated": parse_date(t.get("date_updated")),
            "metadata": metadata,
        }

        fout.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"💾 Archivo limpio generado en: {output}")
