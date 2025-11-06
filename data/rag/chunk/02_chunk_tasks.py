#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Divide los textos naturalizados de tareas en fragmentos (chunks) listos para vectorización.
Entrada: data/processed/task_natural.jsonl
Salida:  data/processed/task_chunks.jsonl
"""

import json
from pathlib import Path
from tqdm import tqdm
from langchain_text_splitters import RecursiveCharacterTextSplitter

# =============================================================
# CONFIGURACIÓN
# =============================================================

INPUT_FILE = Path("data/processed/task_natural.jsonl")
OUTPUT_FILE = Path("data/processed/task_chunks.jsonl")

# Ajusta el tamaño del chunk según la longitud media de tus descripciones.
CHUNK_SIZE = 300      # caracteres (equivale aprox. a 200-250 tokens)
CHUNK_OVERLAP = 50    # solape entre chunks

# =============================================================
# FUNCIÓN PRINCIPAL
# =============================================================

def main():
    print(f"📂 Leyendo tareas naturalizadas desde {INPUT_FILE}")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"No se encontró {INPUT_FILE}. Ejecuta antes 01_naturalize_tasks.py.")

    tasks = [json.loads(line) for line in open(INPUT_FILE, "r", encoding="utf-8")]
    print(f"🧩 Procesando {len(tasks)} tareas para generar chunks...")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    chunked_docs = []

    for task in tqdm(tasks, desc="Dividiendo texto en chunks"):
        text = task.get("text", "").strip()
        if not text:
            continue

        chunks = splitter.split_text(text)
        for i, chunk in enumerate(chunks):
            chunked_docs.append({
                "task_id": task["task_id"],
                "chunk_id": f"{task['task_id']}_{i}",
                "text": chunk.strip(),
                "metadata": task.get("metadata", {})
            })

    # Guardar resultado
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for doc in chunked_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"✅ {len(chunked_docs)} chunks guardados en {OUTPUT_FILE}")

    # Mostrar ejemplo
    if chunked_docs:
        print("\n🧠 Ejemplo de chunk generado:\n")
        print(json.dumps(chunked_docs[0], indent=2, ensure_ascii=False))

# =============================================================
# PUNTO DE ENTRADA
# =============================================================
if __name__ == "__main__":
    main()
