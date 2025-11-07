#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Naturaliza tareas (markdown estructurado → texto natural breve y útil para RAG)
Usa mT5 y limpia sentinel tokens (<extra_id_#>).
Entradas:
  - data/processed/task_markdown.jsonl  (campos esperados: task_id, text, metadata)
Salidas:
  - data/processed/task_natural_mt5.jsonl  (campos: task_id, text, metadata)

Recomendación: El 'text' generado es breve (título + bullets). La descripción larga queda en el JSON original si se quiere.
"""

from pathlib import Path
import json
import re
from tqdm import tqdm

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

INPUT_FILE = Path("data/processed/task_markdown.jsonl")
OUTPUT_FILE = Path("data/processed/task_natural_mt5.jsonl")

MODEL_NAME = "google/mt5-base"

PROMPT_PREFIX = (
    "paraphrase:\n"
    "Convierte el siguiente markdown de una tarea de ClickUp a un resumen breve en español, con:\n"
    "- Título claro\n"
    "- 3 viñetas con: objetivo, estado/bloqueos y próximo paso\n"
    "- Si hay responsables, menciónalos\n"
    "Texto:\n"
)

MAX_NEW_TOKENS = 256


def clean_mt5(text: str) -> str:
    # Quita sentinel tokens <extra_id_#>
    text = re.sub(r"<extra_id_\d+>", "", text)
    # Colapsa espacios raros
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def load_lines(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            yield json.loads(s)


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"❌ No se encontró {INPUT_FILE}. Ejecuta 01_markdownfy_tasks.py antes."
        )

    print(f"🧠 Cargando modelo {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    device = "cpu"
    model.to(device)
    print(f"✅ Modelo cargado en dispositivo: {device}")

    n, ok = 0, 0
    with OUTPUT_FILE.open("w", encoding="utf-8") as fout:
        for rec in tqdm(list(load_lines(INPUT_FILE)), desc="🧬 Naturalizando con mT5"):
            n += 1
            task_id = rec.get("task_id") or rec.get("id") or f"task_{n}"
            src_text = rec.get("text") or rec.get("markdown") or ""

            prompt = PROMPT_PREFIX + src_text

            tok_inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
            tok_inputs = {k: v.to(device) for k, v in tok_inputs.items()}

            # Generación estable, sin sampling, sin repeticiones triviales
            gen = model.generate(
                **tok_inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                num_beams=4,
                no_repeat_ngram_size=3,
                early_stopping=True,
                length_penalty=1.0,
            )
            out = tokenizer.decode(gen[0], skip_special_tokens=True)
            out = clean_mt5(out)

            # Si queda vacío por algún motivo raro, fallback mínimo
            if not out:
                out = clean_mt5(src_text[:800])

            natural = {
                "task_id": task_id,
                "text": out,
                "metadata": rec.get("metadata", {}),
            }
            fout.write(json.dumps(natural, ensure_ascii=False) + "\n")
            ok += 1

    print(f"✅ {ok} tareas naturalizadas guardadas en {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
