#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_validate_chroma_index.py
---------------------------
Valida la integridad de la colección 'clickup_tasks' en ChromaDB.

Comprueba:
- Número de documentos y duplicados
- Campos metadata principales
- Longitud de embeddings
- Distribución por sprint, estado y prioridad
"""

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
import chromadb

# =============================================================
# 📂 Configuración
# =============================================================
CHROMA_PATH = Path("data/rag/chroma_db")
COLLECTION_NAME = "clickup_tasks"

# =============================================================
# 🚀 Cargar colección
# =============================================================
def load_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        col = client.get_collection(COLLECTION_NAME)
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar la colección '{COLLECTION_NAME}': {e}")
    return col

# =============================================================
# 🧩 Validación general
# =============================================================
def validate_collection(col):
    print(f"\n📂 Validando colección: {COLLECTION_NAME}")
    results = col.get(include=["metadatas", "embeddings", "documents"])
    ids = results["ids"]
    metas = results["metadatas"]
    embeds = results["embeddings"]
    docs = results["documents"]

    total = len(ids)
    print(f"📊 Documentos totales: {total}")

    # ---------------------------------------
    # Detectar duplicados
    # ---------------------------------------
    dup_ids = [x for x, c in Counter(ids).items() if c > 1]
    if dup_ids:
        print(f"⚠️ {len(dup_ids)} IDs duplicados detectados.")
    else:
        print("✅ Sin duplicados de ID.")

    # Duplicados por hash
    hashes = [m.get("chunk_hash") for m in metas if m.get("chunk_hash")]
    dup_hashes = [h for h, c in Counter(hashes).items() if c > 1]
    if dup_hashes:
        print(f"⚠️ {len(dup_hashes)} chunks duplicados por hash.")
    else:
        print("✅ Sin duplicados por hash.")

    # ---------------------------------------
    # Metadatos clave
    # ---------------------------------------
    fields = ["status", "priority", "sprint", "project"]
    summary = defaultdict(Counter)
    for m in metas:
        for f in fields:
            summary[f][m.get(f, "Desconocido")] += 1

    print("\n📈 Distribución de campos:")
    for f in fields:
        dist = ", ".join([f"{k}: {v}" for k, v in summary[f].most_common()])
        print(f"  - {f}: {dist}")

    # ---------------------------------------
    # Embeddings
    # ---------------------------------------
    dims = [len(e) for e in embeds if isinstance(e, list)]
    print(f"\n🧠 Dimensiones de embeddings: {set(dims)}")
    if dims:
        print(f"   • Media de longitud: {mean(dims):.1f}")

    # ---------------------------------------
    # Validar contenido textual
    # ---------------------------------------
    empty_docs = [i for i, d in zip(ids, docs) if not d or len(d.strip()) < 20]
    if empty_docs:
        print(f"⚠️ {len(empty_docs)} documentos vacíos o muy cortos.")
    else:
        print("✅ Todos los documentos tienen contenido útil.")

    # ---------------------------------------
    # Campos nulos o vacíos
    # ---------------------------------------
    null_fields = defaultdict(int)
    for m in metas:
        for k, v in m.items():
            if v in ("", None, "null", "None"):
                null_fields[k] += 1

    if null_fields:
        print("\n⚠️ Campos con valores vacíos:")
        for k, v in null_fields.items():
            print(f"   - {k}: {v}")
    else:
        print("\n✅ Sin valores nulos en metadatos.")

    print("\n✅ Validación completada correctamente.\n")


# =============================================================
# CLI
# =============================================================
if __name__ == "__main__":
    print("🔍 Validando base de datos Chroma...")
    col = load_collection()
    validate_collection(col)
