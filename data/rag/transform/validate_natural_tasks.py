#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
validate_natural_tasks.py
──────────────────────────
Valida la calidad de las tareas naturalizadas antes de indexarlas en ChromaDB.

Evalúa si los textos generados por FLAN-T5 contienen información clave:
- Estado
- Prioridad
- Asignado o responsable

📊 Genera un informe con métricas de completitud y ejemplos de errores.
"""

import json
from pathlib import Path
from collections import Counter
from tqdm import tqdm

# ============================
# Configuración
# ============================
INPUT_PATH = Path("data/processed/task_natural_mt5.jsonl")
REQUIRED_KEYWORDS = ["estado", "prioridad", "asignad", "sprint"]
MIN_LENGTH = 40  # longitud mínima del texto natural

# ============================
# Funciones principales
# ============================
def read_jsonl(path: Path):
    """Lee un archivo JSONL y devuelve una lista de dicts."""
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def validate_text(text: str) -> dict:
    """Evalúa un texto y devuelve un dict con flags de presencia de keywords."""
    text_lower = text.lower()
    flags = {kw: (kw in text_lower) for kw in REQUIRED_KEYWORDS}
    flags["longitud_ok"] = len(text.strip()) >= MIN_LENGTH
    return flags


def evaluate_dataset(records: list) -> dict:
    """Evalúa el dataset completo y devuelve estadísticas agregadas."""
    totals = Counter()
    failures = []

    for r in tqdm(records, desc="Evaluando tareas"):
        text = r.get("text", "")
        flags = validate_text(text)

        if all(flags.values()):
            totals["completas"] += 1
        else:
            totals["incompletas"] += 1
            failures.append({"text": text, "flags": flags, "meta": r.get("metadata", {})})

    total = len(records)
    score = totals["completas"] / total * 100 if total else 0
    return {"total": total, "score": score, "totals": totals, "failures": failures[:5]}


# ============================
# Main
# ============================
def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"No existe el archivo: {INPUT_PATH}")

    data = read_jsonl(INPUT_PATH)
    print(f"📂 Analizando {len(data)} tareas naturalizadas desde {INPUT_PATH}")

    results = evaluate_dataset(data)

    print("\n📊 RESULTADOS DE VALIDACIÓN")
    print(f"Total de tareas: {results['total']}")
    print(f"Tareas completas: {results['totals']['completas']} ✅")
    print(f"Tareas incompletas: {results['totals']['incompletas']} ⚠️")
    print(f"Porcentaje de completitud: {results['score']:.1f}%\n")

    if results["failures"]:
        print("🧩 Ejemplos de tareas incompletas:")
        for f in results["failures"]:
            meta = f.get("meta", {})
            print(f"\n--- {meta.get('sprint', '-')}, {meta.get('task_id', '-')}")
            print("Texto:", f["text"][:200].replace("\n", " "))
            print("Flags:", f["flags"])


if __name__ == "__main__":
    main()
