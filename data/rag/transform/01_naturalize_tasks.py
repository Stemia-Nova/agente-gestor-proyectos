#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Convierte tareas limpias en descripciones narrativas ricas en contexto.
Incluye información de estado, prioridad, etiquetas, y responsables.
Genera `data/processed/task_natural.jsonl`.
"""

import json
from pathlib import Path
from tqdm import tqdm

INPUT_FILE = Path("data/processed/task_clean.jsonl")
OUTPUT_FILE = Path("data/processed/task_natural.jsonl")

if not INPUT_FILE.exists():
    raise FileNotFoundError("❌ No se encontró task_clean.jsonl. Ejecuta primero clean_tasks.py")

def estado_descriptivo(status: str, meta: dict) -> str:
    """Devuelve una frase descriptiva según el estado y etiquetas."""
    s = status.lower().strip()

    if s in ["to_do", "todo", "pendiente", "por hacer"]:
        return "todavía no se ha comenzado."
    elif s in ["in_progress", "en progreso", "en curso"]:
        return "está actualmente en curso o desarrollo."
    elif s in ["in_review", "pendiente de revisión", "en revisión"]:
        return "se encuentra pendiente de revisión o validación final."
    elif s in ["done", "completada", "finalizada"]:
        return "esta tarea ya ha sido completada con éxito."
    elif s in ["blocked", "bloqueada"]:
        return "está bloqueada o tiene algún impedimento pendiente de resolver."
    else:
        # Detección semántica por etiquetas
        if meta.get("is_blocked"):
            return "está bloqueada o detenida por algún problema."
        if meta.get("has_doubts"):
            return "está en pausa hasta resolver algunas dudas o dependencias."
        return f"se encuentra en estado '{s}'."

def construir_texto(task: dict) -> str:
    """Construye la descripción natural completa de la tarea."""
    meta = task["metadata"]
    name = task.get("name", "Sin título")
    desc = (task.get("description") or "").strip()
    project = meta.get("project", "")
    sprint = meta.get("sprint", meta.get("list", ""))
    estado = estado_descriptivo(task.get("status", ""), meta)
    priority = meta.get("priority", "") or "sin prioridad"
    assignees = meta.get("assignees", "") or "sin responsables asignados"
    tags = meta.get("tags", "")

    extra = []
    if meta.get("is_urgent"): extra.append("Es una tarea urgente.")
    if meta.get("has_doubts"): extra.append("Tiene dudas o dependencias por resolver.")
    if meta.get("is_blocked"): extra.append("Actualmente está bloqueada o detenida.")
    if tags:
        extra.append(f"Tiene las etiquetas: {tags}.")

    text = (
        f"La tarea '{name}' pertenece al proyecto '{project}' en el sprint '{sprint}'. "
        f"Actualmente {estado} Tiene una prioridad '{priority}' y {assignees}. "
        f"{' '.join(extra)} "
        f"Descripción: {desc if desc else 'Sin descripción adicional.'}"
    )

    return text.strip()

with open(INPUT_FILE, "r", encoding="utf-8") as fin, open(OUTPUT_FILE, "w", encoding="utf-8") as fout:
    count = 0
    for line in tqdm(fin, desc="🧠 Naturalizando tareas"):
        task = json.loads(line)
        task_text = construir_texto(task)
        fout.write(json.dumps({
            "task_id": task["task_id"],
            "text": task_text,
            "metadata": task["metadata"]
        }, ensure_ascii=False) + "\n")
        count += 1

print(f"✅ {count} tareas naturalizadas guardadas en {OUTPUT_FILE}")
