#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03b_merge_metadata.py
--------------------
Combina los metadatos completos de task_markdown.jsonl con el texto
naturalizado de task_natural.jsonl, preservando subtareas y comentarios.
"""

import json
from pathlib import Path

MARKDOWN_FILE = Path("data/processed/task_markdown.jsonl")
NATURAL_FILE = Path("data/processed/task_natural.jsonl")
OUTPUT_FILE = Path("data/processed/task_natural_merged.jsonl")

# Cargar metadatos de markdown
markdown_meta = {}
with MARKDOWN_FILE.open("r", encoding="utf-8") as f:
    for line in f:
        task = json.loads(line)
        meta = task.get("metadata", {})
        task_id = meta.get("task_id")
        if task_id:
            markdown_meta[task_id] = meta

# Mergear con natural
merged_count = 0
with NATURAL_FILE.open("r", encoding="utf-8") as fin, OUTPUT_FILE.open("w", encoding="utf-8") as fout:
    for line in fin:
        task = json.loads(line)
        meta = task.get("metadata", {})
        task_id = meta.get("task_id")
        
        if task_id and task_id in markdown_meta:
            # Usar metadatos completos de markdown
            task["metadata"] = markdown_meta[task_id]
            merged_count += 1
        
        fout.write(json.dumps(task, ensure_ascii=False) + "\n")

print(f"✅ Merged {merged_count} tareas")
print(f"📄 Archivo generado: {OUTPUT_FILE}")
