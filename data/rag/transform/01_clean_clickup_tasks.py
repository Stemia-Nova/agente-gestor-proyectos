#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01_clean_clickup_tasks.py (versión profesional RAG)
---------------------------------------------------
Limpia y normaliza las tareas obtenidas de ClickUp, incluyendo subtareas.

✔ Normaliza estados (Pendiente, En curso, Pendiente de revisión, QA, Completado).
✔ Convierte prioridades (Urgente, Alta, Normal, Baja, Sin prioridad).
✔ Detecta y vincula subtareas con sus tareas padre.
✔ Añade indicadores útiles: is_blocked, has_doubts, is_pending_review, is_overdue, has_comments.
✔ Genera dataset listo para indexación semántica (RAG híbrido).

Salida: data/processed/task_clean.jsonl
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from tqdm import tqdm

# ============================================================
# Configuración de rutas
# ============================================================
INGEST_DIR = Path("data/rag/ingest")
CLEAN_PATH = Path("data/processed/task_clean.jsonl")

raw_files = sorted(INGEST_DIR.glob("clickup_tasks_all_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if not raw_files:
    raise FileNotFoundError(f"No se encontró ningún archivo en {INGEST_DIR}")
RAW_PATH = raw_files[0]

# ============================================================
# Funciones auxiliares
# ============================================================

def normalize_status(raw: str) -> str:
    """Normaliza los estados del tablero actual."""
    if not raw:
        return "desconocido"
    raw = raw.strip().lower()
    status_map = {
        "to do": "pendiente",
        "pending": "pendiente",
        "in progress": "en curso",
        "review": "pendiente de revisión",
        "pending review": "pendiente de revisión",
        "qa": "QA",
        "complete": "completado",
        "done": "completado",
        "closed": "completado",
    }
    return status_map.get(raw, raw)


def normalize_priority(raw: dict | str | None) -> str:
    """Normaliza la prioridad de ClickUp."""
    if not raw:
        return "sin prioridad"
    if isinstance(raw, dict):
        val = (raw.get("priority") or raw.get("label") or "").lower().strip()
    else:
        val = str(raw).lower().strip()
    mapping = {
        "urgent": "urgente",
        "high": "alta",
        "normal": "normal",
        "low": "baja",
    }
    return mapping.get(val, "sin prioridad")


def safe_date(ts: str | int | None) -> str:
    """Convierte timestamps o strings a formato YYYY-MM-DD."""
    if not ts:
        return ""
    try:
        if isinstance(ts, int):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        elif isinstance(ts, str) and ts.isdigit():
            return datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

        elif isinstance(ts, str):
            return ts[:10]
    except Exception:
        return ""
    return ""


def extract_sprint(task: dict) -> str:
    """Detecta el sprint de una tarea."""
    if task.get("sprint_name"):
        return task["sprint_name"]
    for tag in task.get("tags", []):
        if "sprint" in tag.get("name", "").lower():
            return tag["name"].title()
    for n in [
        (task.get("list") or {}).get("name", ""),
        (task.get("folder") or {}).get("name", ""),
    ]:
        if "sprint" in n.lower():
            return n.strip().title()
    return "Desconocido"


def detect_flags(task: dict, status: str, due_date: str) -> dict:
    """Detecta indicadores booleanos de interés."""
    now = datetime.now(timezone.utc)
    comments = task.get("comments", [])
    comments_text = " ".join(c.get("text", "").lower() for c in comments)
    tags_text = " ".join(t.get("name", "").lower() for t in task.get("tags", []))
    text_blob = f"{task.get('name','')} {task.get('description','')} {comments_text} {tags_text}".lower()

    is_blocked = any(k in text_blob for k in ["bloquead", "impedimento", "bloqueo"])
    has_doubts = any(k in text_blob for k in ["duda", "dudas", "doubt"])
    is_pending_review = status == "pendiente de revisión" or "qa" in text_blob

    is_overdue = False
    if due_date and status != "completado":
        try:
            due = datetime.strptime(due_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            is_overdue = due < now
        except Exception:
            pass

    return {
        "is_blocked": is_blocked,
        "has_doubts": has_doubts,
        "is_pending_review": is_pending_review,
        "is_overdue": is_overdue,
        "has_comments": len(comments) > 0,
        "comments_count": len(comments),
        "last_comment_author": comments[-1]["author"] if comments else "",
    }


# ============================================================
# Proceso principal
# ============================================================

def main() -> None:
    print(f"📂 Leyendo tareas desde: {RAW_PATH}")
    data = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    print(f"📦 Tareas detectadas: {len(tasks)}")

    # ------------------------------------------------------------
    # Crear índice por ID para relacionar subtareas con padres
    # ------------------------------------------------------------
    task_index = {t.get("id"): t for t in tasks}

    # Vincular subtareas a sus tareas padre
    for t in tasks:
        parent_id = t.get("parent")
        if parent_id and parent_id in task_index:
            parent = task_index[parent_id]
            if "subtasks" not in parent:
                parent["subtasks"] = []
            parent["subtasks"].append({
                "id": t.get("id"),
                "name": t.get("name"),
                "status": normalize_status((t.get("status") or {}).get("status", "")),
                "priority_level": normalize_priority(t.get("priority")),
            })

    # ------------------------------------------------------------
    # Generar dataset limpio
    # ------------------------------------------------------------
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CLEAN_PATH.open("w", encoding="utf-8") as fout:
        for t in tqdm(tasks, desc="🧹 Limpiando tareas"):

            status = normalize_status((t.get("status") or {}).get("status", ""))
            priority_level = normalize_priority(t.get("priority"))
            sprint = extract_sprint(t)

            assignees = [a.get("username") for a in t.get("assignees", [])]
            assignees_text = ", ".join(a for a in assignees if a) or "sin asignar"
            creator = (t.get("creator") or {}).get("username", "desconocido")

            date_created = safe_date(t.get("date_created"))
            date_updated = safe_date(t.get("date_updated"))
            date_closed = safe_date(t.get("date_closed"))
            due_date = safe_date(t.get("due_date"))

            parent_id = t.get("parent")
            is_subtask = bool(parent_id)

            flags = detect_flags(t, status, due_date)

            comments_text = "\n".join(
                [f"- {c.get('author', 'anon')}: {c.get('text', '').strip()}" for c in t.get("comments", [])]
            )

            subtasks_simplified = t.get("subtasks", [])

            clean_item = {
                "task_id": t.get("id"),
                "name": t.get("name") or "Sin título",
                "description": t.get("description") or "",
                "status": status,
                "priority_level": priority_level,
                "assignees": assignees_text,
                "creator": creator,
                "project": (t.get("project") or {}).get("name", "Sin proyecto"),
                "sprint": sprint,
                "date_created": date_created,
                "date_updated": date_updated,
                "date_closed": date_closed,
                "due_date": due_date,
                "tags": [tg.get("name") for tg in t.get("tags", [])],
                "comments": comments_text,
                "is_subtask": is_subtask,
                "parent_task_id": parent_id,
                "subtasks": subtasks_simplified,
                **flags,
            }

            fout.write(json.dumps(clean_item, ensure_ascii=False) + "\n")

    print(f"✅ Archivo limpio con jerarquía generado en: {CLEAN_PATH}")


# ============================================================
# Entry point
# ============================================================
if __name__ == "__main__":
    main()
