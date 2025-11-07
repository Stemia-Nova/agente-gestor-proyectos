#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
01_markdownify_tasks.py
-----------------------
Convierte tareas limpias en Markdown semántico incluyendo asignados múltiples.

Entrada:  data/processed/task_clean.jsonl
Salida:   data/processed/task_markdown.jsonl
"""

import json
from pathlib import Path
from tqdm import tqdm

INPUT_FILE = Path("data/processed/task_clean.jsonl")
OUTPUT_FILE = Path("data/processed/task_markdown.jsonl")

if not INPUT_FILE.exists():
    raise FileNotFoundError("❌ No se encontró task_clean.jsonl. Ejecuta primero clean_tasks.py")


def format_assignees(value) -> str:
    """Convierte la lista o string de asignados en texto limpio."""
    if not value:
        return "Sin asignar"
    if isinstance(value, list):
        if len(value) == 1:
            return value[0]
        else:
            return ", ".join(value[:-1]) + f" y {value[-1]}"
    return str(value)


def task_to_markdown(task: dict) -> str:
    """Convierte una tarea limpia a Markdown estructurado."""
    meta = task.get("metadata", {})
    name = task.get("name", "Sin título").strip()
    desc = (task.get("description") or "").strip()

    assignees_str = format_assignees(meta.get("assignees"))
    tags = meta.get("tags", "Sin etiquetas")

    md = f"""### Tarea: {name}
**Proyecto:** {meta.get('project', 'Desconocido')}  
**Sprint:** {meta.get('sprint', meta.get('list', 'No definido'))}  
**Estado:** {meta.get('status_verbose', meta.get('status', 'Desconocido'))}  
**Prioridad:** {meta.get('priority', 'No definida')}  
**Asignados:** {assignees_str}  
**Etiquetas:** {tags}  

**Descripción:**  
{desc if desc else 'Sin descripción disponible.'}

Esta tarea está asignada a {assignees_str}.
"""

    return md.strip()


with open(INPUT_FILE, "r", encoding="utf-8") as fin, open(OUTPUT_FILE, "w", encoding="utf-8") as fout:
    count = 0
    for line in tqdm(fin, desc="📝 Generando Markdown estructurado"):
        task = json.loads(line)
        markdown_text = task_to_markdown(task)

        fout.write(json.dumps({
            "chunk_id": f"{task['task_id']}_0",
            "task_id": task["task_id"],
            "text": markdown_text,
            "metadata": task["metadata"]
        }, ensure_ascii=False) + "\n")

        count += 1

print(f"✅ {count} tareas convertidas a Markdown guardadas en {OUTPUT_FILE}")
