#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path

# Muestra qué Python se usa (debe ser .venv\Scripts\python.exe)
print(f"🐍 Python en uso: {sys.executable}")

# Raíz del repo = carpeta donde está este script
ROOT = Path(__file__).resolve().parent
STEPS = [
    ROOT / "utils" / "clean_tasks.py",
    ROOT / "data" / "rag" / "transform" / "01_naturalize_tasks.py",
    ROOT / "data" / "rag" / "chunk" / "02_chunk_tasks.py",  # usa "chunks" si esa es tu carpeta real
    ROOT / "data" / "rag" / "index" / "03_index_vector_chroma.py",
]

print("🚀 Iniciando pipeline completo de actualización de RAG...\n")

for step in STEPS:
    step = Path(step)
    if not step.exists():
        print(f"❌ No encuentro {step}. Revisa la ruta.")
        sys.exit(1)

    print(f"▶️  Ejecutando {step.relative_to(ROOT)} ...")
    # MUY IMPORTANTE: usar SIEMPRE el mismo intérprete (el del venv)
    subprocess.run([sys.executable, str(step)], check=True)
    print(f"✅  {step.name} completado.\n")

print("🎯  Pipeline RAG ejecutado correctamente. Base actualizada en data/rag/chroma_db/")
