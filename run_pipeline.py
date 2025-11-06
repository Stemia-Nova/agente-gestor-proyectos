#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ejecuta todo el flujo RAG (ingesta → limpieza → naturalización → chunking → indexación).
"""

import subprocess
from pathlib import Path

STEPS = [
    "utils/clean_tasks.py",
    "data/rag/transform/01_naturalize_tasks.py",
    "data/rag/chunk/02_chunk_tasks.py",
    "data/rag/index/03_index_vector_chroma.py",
]

print("🚀 Iniciando pipeline completo de actualización de RAG...\n")

for step in STEPS:
    print(f"▶️ Ejecutando {step}...")
    subprocess.run(["python", step], check=True)
    print(f"✅ {step} completado.\n")

print("🎯 Pipeline RAG ejecutado correctamente. Base actualizada en data/rag/chroma_db/")
