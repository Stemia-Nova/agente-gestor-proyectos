#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Divide las tareas naturalizadas en chunks y conserva los metadatos importantes.
Genera `data/processed/task_chunks.jsonl` con textos enriquecidos (listos para indexación).
"""

import json
from pathlib import Path
from tqdm import tqdm
from langchain_text_splitters import RecursiveCharacterTextSplitter

INPUT_FILE = Path("data/processed/task_natural_mt5.jsonl")
OUTPUT_FILE = Path("data/processed/task_chunks.jsonl")

# =============================================================
# CONFIGURACIÓN DE SEGMENTACIÓN
# =============================================================
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# =============================================================
# EJECUCIÓN
# =============================================================
if not INPUT_FILE.exists():
    raise FileNotFoundError("❌ No se encontró task_natural_mt5.jsonl. Ejecuta 02_naturalize_tasks_flan.py antes.")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)

with open(INPUT_FILE, "r", encoding="utf-8") as fin, open(OUTPUT_FILE, "w", encoding="utf-8") as fout:
    lines = fin.readlines()
    total_chunks = 0

    for line in tqdm(lines, desc="✂️ Generando chunks enriquecidos"):
        task = json.loads(line)
        meta = task.get("metadata", {})

        # ======== Traducción de estados y prioridades ========
        status_map = {
            "done": "finalizada",
            "in_progress": "en progreso",
            "to_do": "por hacer",
            "blocked": "bloqueada",
            "review": "en revisión",
        }
        raw_status = str(meta.get("status", "")).lower()
        status = status_map.get(raw_status, raw_status or "sin estado")

        priority_map = {
            "urgent": "urgente",
            "high": "alta",
            "normal": "media",
            "low": "baja",
        }
        raw_priority = str(meta.get("priority", "")).lower()
        priority = priority_map.get(raw_priority, raw_priority or "sin prioridad")

        assignees = meta.get("assignees", "sin responsable")
        sprint = meta.get("sprint", "sin sprint")
        project = meta.get("project", "sin proyecto")

        # ======== Añadir sinónimos y contexto ========
        extra_info = []
        if meta.get("is_blocked"):
            extra_info.append("Esta tarea está bloqueada por un impedimento o dependencia.")
        if meta.get("is_urgent") or raw_priority == "urgent":
            extra_info.append("Esta tarea es urgente y requiere atención prioritaria.")

        extra_info_str = " ".join(extra_info)

        # ======== Texto enriquecido ========
        enriched_text = (
            f"Tarea asignada a {assignees}. "
            f"Estado: {status}. Prioridad: {priority}. "
            f"Sprint: {sprint}. Proyecto: {project}. "
            f"{extra_info_str} {task.get('text','')}"
        )

        # ======== Segmentación ========
        chunks = splitter.split_text(enriched_text)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{task['task_id']}_chunk{i}"
            metadata = {
                "task_id": task["task_id"],
                "sprint": sprint,
                "project": project,
                "list": meta.get("list", ""),
                "status": status,
                "priority": priority,
                "assignees": assignees,
                "tags": meta.get("tags", ""),
                "is_blocked": meta.get("is_blocked", False),
                "has_doubts": meta.get("has_doubts", False),
                "is_urgent": meta.get("is_urgent", False),
            }

            fout.write(json.dumps({
                "chunk_id": chunk_id,
                "task_id": task["task_id"],
                "text": chunk,
                "metadata": metadata
            }, ensure_ascii=False) + "\n")

            total_chunks += 1

print(f"💾 Archivo final con {total_chunks} chunks enriquecidos generado en: {OUTPUT_FILE}")
