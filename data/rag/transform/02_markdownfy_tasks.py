#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02_markdownfy_tasks.py (versión embeddings-safe)
-------------------------------------------------
Convierte las tareas limpias (task_clean.jsonl) en texto Markdown semánticamente limpio.

✔ Elimina emojis y símbolos no semánticos.
✔ Mantiene estructura Markdown legible para modelos.
✔ Sustituye iconos por texto natural: Bloqueada, Urgente, Pendiente de revisión, etc.
✔ Incluye comentarios y subtareas en texto plano.
✔ Genera salida lista para la fase de naturalización o embeddings.
"""

import json
from pathlib import Path
from tqdm import tqdm

INPUT_PATH = Path("data/processed/task_clean.jsonl")
OUTPUT_PATH = Path("data/processed/task_markdown.jsonl")


def load_tasks(path: Path):
    """Carga las tareas limpias desde JSONL."""
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def generate_markdown(task: dict) -> dict:
    """Convierte una tarea limpia en texto markdown sin símbolos ni emojis."""
    flags = []
    if task.get("is_blocked"):
        flags.append("Tarea BLOQUEADA por un impedimento o dependencia.")
    if task.get("has_doubts"):
        flags.append("El responsable tiene dudas o necesita aclaración.")
    if task.get("is_pending_review"):
        flags.append("Pendiente de revisión o QA.")
    if task.get("is_overdue"):
        flags.append("La tarea está vencida respecto a su fecha límite.")
    if task.get("priority_level") == "urgente":
        flags.append("Marcada como URGENTE.")
    if not flags:
        flags.append("Sin incidencias registradas.")

    flag_text = "\n".join(f"- {f}" for f in flags)

    # Comentarios
    comments = task.get("comments", "").strip()
    comments_section = f"\n**Comentarios:**\n{comments}" if comments else ""

    # Subtareas (si existen)
    subtasks = task.get("subtasks", [])
    subtasks_text = ""
    if subtasks:
        subtasks_text = "\n**Subtareas:**\n" + "\n".join(
            [f"- [{st.get('status','pendiente').capitalize()}] {st.get('name','')}" for st in subtasks]
        )

    # Construcción del texto markdown limpio
    text_md = f"""### Tarea: {task['name']}
**Estado:** {task['status'].capitalize()}
**Prioridad:** {task['priority_level'].capitalize()}
**Sprint:** {task['sprint']}
**Proyecto:** {task['project']}
**Asignado a:** {task['assignees']}
**Creador:** {task['creator']}
**Fecha de creación:** {task.get('date_created','')}
**Fecha de vencimiento:** {task.get('due_date','')}

**Descripción:**
{task['description'] or 'Sin descripción disponible.'}

**Indicadores:**
{flag_text}
{subtasks_text}
{comments_section}
"""

    # Metadatos para filtrado o indexación
    metadata = {
        "task_id": task["task_id"],
        "name": task["name"],
        "status": task["status"],
        "priority": task["priority_level"],
        "sprint": task["sprint"],
        "project": task["project"],
        "assignees": task["assignees"],
        "is_subtask": task.get("is_subtask", False),
        "parent_task_id": task.get("parent_task_id"),
        "is_blocked": task.get("is_blocked", False),
        "has_doubts": task.get("has_doubts", False),
        "is_pending_review": task.get("is_pending_review", False),
        "is_overdue": task.get("is_overdue", False),
        "has_comments": task.get("has_comments", False),
        "comments_count": task.get("comments_count", 0),
    }

    return {"text": text_md.strip(), "metadata": metadata}


def main():
    print(f"📂 Leyendo tareas limpias desde: {INPUT_PATH}")
    tasks = load_tasks(INPUT_PATH)

    markdown_tasks = [generate_markdown(t) for t in tqdm(tasks, desc="🧩 Generando markdown limpio")]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for t in markdown_tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    print(f"✅ Archivo de tareas markdown limpio generado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
