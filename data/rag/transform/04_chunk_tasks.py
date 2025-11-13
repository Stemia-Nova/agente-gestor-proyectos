#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04_chunk_tasks.py (versión adaptable para entorno demo y real)
--------------------------------------------------------------
Divide las tareas naturalizadas en fragmentos ("chunks") para su
indexación semántica posterior en ChromaDB o FAISS.

🎓 Esta versión incluye comentarios didácticos para estudiantes de IA,
explicando cómo ajustar los parámetros según el tamaño de los textos.

Entrada:
    data/processed/task_natural.jsonl
Salida:
    data/processed/task_chunks.jsonl
"""

import json
import uuid
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

# =============================================================
# 📂 Paths
# =============================================================
INPUT_FILE = Path("data/processed/task_natural.jsonl")
OUTPUT_FILE = Path("data/processed/task_chunks.jsonl")

# =============================================================
# ⚙️ Configuración del splitter
# =============================================================
# 🔧 MarkdownHeaderTextSplitter: respeta la jerarquía de encabezados MD
# Divide por secciones (###) preservando el contexto estructural.
# Luego aplica RecursiveCharacterTextSplitter solo si un chunk es muy largo.

headers_to_split_on = [
    ("###", "Header 3"),
    ("**", "Bold"),
]

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False  # Mantener encabezados para contexto
)

# Splitter secundario para fragmentos muy largos
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    length_function=len,
    separators=["\n\n", ". ", "; ", ": ", "\n", " "],
)

# =============================================================
# 🚀 Carga de tareas naturalizadas
# =============================================================
if not INPUT_FILE.exists():
    raise FileNotFoundError(f"No se encontró el archivo {INPUT_FILE}")

tasks = []
with INPUT_FILE.open("r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            try:
                tasks.append(json.loads(line))
            except json.JSONDecodeError:
                continue

print(f"📂 Procesando {len(tasks)} tareas desde {INPUT_FILE} ...")

# =============================================================
# ✂️ Generación de chunks enriquecidos
# =============================================================
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
total_chunks = 0
chunk_order_id = 0  # contador global incremental

with OUTPUT_FILE.open("w", encoding="utf-8") as out:
    for task in tqdm(tasks, desc="✂️ Generando chunks enriquecidos"):
        meta = task.get("metadata", {})
        task_id = meta.get("task_id") or f"task_{uuid.uuid4().hex[:8]}"

        # 🧹 Normalizar texto: quitar espacios y saltos innecesarios
        text = (task.get("text") or "").strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue

        # ✂️ Dividir usando MarkdownSplitter (respeta estructura)
        try:
            # Primero intentar dividir por encabezados Markdown
            md_chunks = markdown_splitter.split_text(text)
            
            # Si algún chunk es muy largo, aplicar splitter secundario
            chunks = []
            for chunk_doc in md_chunks:
                chunk_text = chunk_doc.page_content if hasattr(chunk_doc, 'page_content') else str(chunk_doc)
                if len(chunk_text) > 800:
                    # Dividir chunk largo
                    sub_chunks = text_splitter.split_text(chunk_text)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(chunk_text)
        except Exception as e:
            # Fallback a splitter clásico si falla MD splitter
            chunks = text_splitter.split_text(text)
        chunk_count = len(chunks)
        total_chunks += chunk_count

        for i, chunk in enumerate(chunks):
            chunk_order_id += 1
            chunk_id = f"{task_id}_chunk{i}"
            chunk_hash = hashlib.sha1(chunk.encode("utf-8")).hexdigest()
            indexed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            chunk_record = {
                "chunk_id": chunk_id,
                "task_id": task_id,
                "chunk_index": i,
                "chunk_count": chunk_count,
                "chunk_order_id": chunk_order_id,
                "chunk_hash": chunk_hash,
                "indexed_at": indexed_at,
                "text": chunk.strip(),
                "metadata": {
                    **meta,
                    "chunk_uuid": uuid.uuid4().hex,
                    "chunk_length": len(chunk),
                },
            }
            out.write(json.dumps(chunk_record, ensure_ascii=False) + "\n")

print(f"\n✅ Archivo generado en: {OUTPUT_FILE}")
print(f"📊 Total de chunks creados: {total_chunks}")
print("ℹ️  Consejo: si las tareas reales contienen descripciones largas, "
      "aumenta 'chunk_size' a ~800–1000 para obtener fragmentos más coherentes.\n")
