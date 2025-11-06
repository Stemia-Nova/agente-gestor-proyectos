#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Convierte las tareas limpias (task_clean.jsonl) en texto natural legible por el modelo,
manteniendo la metadata estructurada (proyecto, sprint, prioridad, etc.)
"""

import json
from pathlib import Path
from tqdm import tqdm

INPUT_FILE = Path("data/processed/task_clean.jsonl")
OUTPUT_FILE = Path("data/processed/task_natural.jsonl")

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"No se encontró {INPUT_FILE}. Ejecuta primero clean_tasks.py")

print(f"📂 Leyendo tareas limpias desde {INPUT_FILE}")

def build_natural_text(task):
    """Genera una descripción en lenguaje natural de la tarea."""
    meta = task.get("metadata", {})
    name = task.get("name", "Sin título")
    desc = task.get("description", "")
    project = meta.get("project", "")
    sprint = meta.get("sprint_display", meta.get("sprint", meta.get("list", "")))
    status = meta.get("status", task.get("status", ""))
    priority = meta.get("priority", "")
    assignees = meta.get("assignees", "")
    tags = meta.get("tags", "")
    created = task.get("date_created", "")
    updated = task.get("date_updated", "")

    text = (
        f"La tarea '{name}' pertenece al proyecto '{project}' en el sprint '{sprint}'. "
        f"Actualmente está en estado '{status}' y tiene prioridad '{priority}'. "
        f"{'Está asignada a ' + assignees + '. ' if assignees else 'No tiene responsables asignados. '}"
        f"{'Tiene las etiquetas ' + tags + '. ' if tags else ''}"
        f"Fue creada el {created} y actualizada el {updated}. "
        f"Descripción: {desc if desc else 'sin descripción disponible.'}"
    )

    return text.strip()

# =============================================================
# PROCESAMIENTO PRINCIPAL
# =============================================================

with open(INPUT_FILE, "r", encoding="utf-8") as fin, open(OUTPUT_FILE, "w", encoding="utf-8") as fout:
    for line in tqdm(fin, desc="🧠 Naturalizando tareas"):
        task = json.loads(line)
        text = build_natural_text(task)

        natural_task = {
            "task_id": task.get("task_id"),
            "text": text,
            # ✅ se conserva la metadata estructurada
            "metadata": task.get("metadata", {}),
        }

        fout.write(json.dumps(natural_task, ensure_ascii=False) + "\n")

print(f"💾 Archivo naturalizado generado: {OUTPUT_FILE}")
print("✅ Naturalización completada con éxito.")
