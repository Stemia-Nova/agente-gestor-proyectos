#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Divide las tareas naturalizadas en chunks y conserva los metadatos importantes.
Genera `data/processed/task_chunks.jsonl` con textos listos para indexación.
"""

import json
from pathlib import Path
from tqdm import tqdm
from langchain_text_splitters import RecursiveCharacterTextSplitter

INPUT_FILE = Path("data/processed/task_natural.jsonl")
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
    raise FileNotFoundError("❌ No se encontró task_natural.jsonl. Ejecuta 01_naturalize_tasks.py antes.")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)

with open(INPUT_FILE, "r", encoding="utf-8") as fin, open(OUTPUT_FILE, "w", encoding="utf-8") as fout:
    lines = fin.readlines()
    total_chunks = 0

    for line in tqdm(lines, desc="✂️ Generando chunks"):
        task = json.loads(line)
        text = task["text"]
        chunks = splitter.split_text(text)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{task['task_id']}_chunk{i}"
            meta = task["metadata"]

            # Mantener campos clave para el RAG
            metadata = {
                "task_id": task["task_id"],
                "sprint": meta.get("sprint", ""),
                "project": meta.get("project", ""),
                "list": meta.get("list", ""),
                "status": meta.get("status", ""),
                "priority": meta.get("priority", ""),
                "assignees": meta.get("assignees", ""),
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

print(f"💾 Archivo final con {total_chunks} chunks generado en: {OUTPUT_FILE}")
