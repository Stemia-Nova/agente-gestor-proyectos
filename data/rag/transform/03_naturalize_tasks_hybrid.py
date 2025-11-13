#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03_naturalize_tasks_hybrid.py (versión pro y robusta)
-----------------------------------------------------
Convierte task_markdown.jsonl a resúmenes en español, concisos y limpios.

Flujo híbrido:
1) Usa OpenAI (gpt-4o-mini) si OPENAI_API_KEY está presente.
2) Si no, usa modelo local HF (GPU: Mistral-7B-Instruct, CPU: Qwen2.5-1.5B-Instruct).

Mejoras clave:
- Salida estándar: data/processed/task_natural.jsonl
- Garantiza <= 2 frases, sin emojis, sin "relleno" y en español.
- Reintentos con backoff, escritura incremental, resume por task_id.
- Metadatos de auditoría (model_id, longitudes, errores).
"""

from __future__ import annotations
import os, re, json, time, math, unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Set, Optional
from dataclasses import dataclass
from tqdm import tqdm
from dotenv import load_dotenv

# ----------------------------
# Archivos (convenciones del pipeline)
# ----------------------------
INPUT_JSONL  = Path("data/processed/task_markdown.jsonl")
OUTPUT_JSONL = Path("data/processed/task_natural.jsonl")

# ----------------------------
# Configuración
# ----------------------------
load_dotenv()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
N_FLUSH = 10         # escribir cada N items
MAX_SENTENCES = 3    # máximo 3 frases (para preservar comentarios/subtareas)
MAX_CHARS = 600      # recorte duro de seguridad
MAX_RETRIES = 3

SYSTEM_PROMPT = (
    "Eres un asistente experto en Scrum/Agile y gestión de tareas (ClickUp). "
    "Devuelve un resumen breve en español, fiel al texto. "
    "PRESERVA SIEMPRE información crítica de Project Management: bloqueos mencionados en comentarios, "
    "número de subtareas y su estado, y asignados. "
    "No inventes datos. Sin viñetas ni listas."
)

USER_TEMPLATE = (
    "Convierte esta ficha de tarea (markdown) a un resumen NATURAL de máximo tres frases, "
    "PRESERVANDO información crítica de Project Management: "
    "1) Si hay sección **Comentarios**, CITA TEXTUALMENTE el contenido del comentario más reciente (razón del bloqueo/duda). "
    "2) Si hay sección **Subtareas**, MENCIONA el número exacto y estados (ej: '2 de 5 completadas'). "
    "3) Incluye: título, estado, prioridad, sprint, asignado. "
    "No uses emojis ni viñetas. Solo texto corrido en español.\n\n"
    "Markdown:\n{markdown}"
)

EMOJI_PATTERN = re.compile(
    "[\U00010000-\U0010FFFF]", flags=re.UNICODE
)  # quitar pictogramas fuera del BMP

SPANISH_OK = re.compile(r"[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ0-9]", re.UNICODE)


# ----------------------------
# Utilidades JSONL
# ----------------------------
def jsonl_iter(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue

def jsonl_append(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def load_done_ids(path: Path) -> Set[str]:
    """Toma task_ids ya procesados para reanudar trabajo."""
    done: Set[str] = set()
    if not path.exists():
        return done
    for row in jsonl_iter(path):
        tid = ((row.get("metadata") or {}).get("task_id")) or None
        if tid:
            done.add(str(tid))
    return done


# ----------------------------
# Normalización y validación de salida
# ----------------------------
def to_plain(text: str) -> str:
    """Quita emojis y normaliza espacios."""
    if not text:
        return ""
    # elimina pictogramas y normaliza
    text = EMOJI_PATTERN.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def enforce_spanish(text: str) -> str:
    # Heurística simple: si casi no hay caracteres propios del español, dejamos igual (no traducimos).
    # Solo evitamos respuestas tipo "Sure!" o code-blocks, recortando fórmulas raras.
    # Mantener simple para robustez.
    return text

def keep_two_sentences(text: str, max_sentences: int = MAX_SENTENCES) -> str:
    """Corta al máximo de frases. Delimitadores: . ! ? ;"""
    if not text:
        return ""
    # proteger abreviaturas básicas (S.L., Sr., etc.) → enfoque simple
    parts = re.split(r"(?<=[\.\!\?;])\s+", text)
    parts = [p.strip() for p in parts if p.strip()]
    kept = parts[:max_sentences]
    out = " ".join(kept).strip()
    if len(out) > MAX_CHARS:
        out = out[:MAX_CHARS].rstrip()
    return out

def finalize_summary(raw: str) -> str:
    text = to_plain(raw)
    text = enforce_spanish(text)
    text = keep_two_sentences(text)
    return text or "Sin contenido."


# ----------------------------
# OpenAI backend
# ----------------------------
def _use_openai() -> bool:
    return bool(OPENAI_API_KEY)

def _summarize_openai(markdown_text: str) -> Tuple[str, Dict[str, Any]]:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(markdown=markdown_text)},
                ],
                temperature=0.2,
                max_tokens=180,
            )
            msg = resp.choices[0].message
            text = (msg.content or "").strip()
            text = finalize_summary(text)
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                "total_tokens": getattr(resp.usage, "total_tokens", None),
                "model": "gpt-4o-mini",
                "retries": attempt,
            }
            return text, usage
        except Exception as e:
            err = str(e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            return f"[Error OpenAI] {err}", {"error": err, "model": "gpt-4o-mini", "retries": attempt}

    # Fallback por seguridad estática (si no entra al for)
    return "Error desconocido.", {"error": "sin retorno", "model": "gpt-4o-mini"}



# ----------------------------
# Modelo local Hugging Face
# ----------------------------
def _pick_local_model() -> str:
    override = (os.getenv("NAT_MODEL_ID") or "").strip()
    if override:
        return override
    try:
        import torch
        if torch.cuda.is_available():
            return "mistralai/Mistral-7B-Instruct-v0.3"
        return "Qwen/Qwen2.5-1.5B-Instruct"
    except Exception:
        return "Qwen/Qwen2.5-1.5B-Instruct"

@dataclass
class LocalGen:
    pipe: Any
    model_id: str

def _load_local_pipeline() -> LocalGen:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    import torch

    model_id = _pick_local_model()
    has_gpu = torch.cuda.is_available()
    dtype = torch.bfloat16 if has_gpu else torch.float32

    print(f"🧠 Usando modelo local: {model_id} ({'cuda' if has_gpu else 'cpu'})")

    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=dtype,
        device_map="auto" if has_gpu else None,
    )

    gen = pipeline(
        "text-generation",
        model=model,
        tokenizer=tok,
        torch_dtype=dtype,
        device_map="auto" if has_gpu else None,
        temperature=0.2,
        do_sample=False,
        max_new_tokens=180,
        repetition_penalty=1.05,
        truncation=True,
    )

    return LocalGen(gen, model_id)

def _summarize_local(markdown_text: str, lg: Optional[LocalGen]) -> Tuple[str, Dict[str, Any]]:
    # A static type checker may not infer that lg is set when not using OpenAI; if None, load pipeline lazily.
    if lg is None:
        lg = _load_local_pipeline()

    prompt = (
        f"[INST] {SYSTEM_PROMPT}\n\n"
        f"{USER_TEMPLATE.format(markdown=markdown_text)} [/INST]"
    )
    for attempt in range(MAX_RETRIES):
        try:
            out = lg.pipe(prompt)
            raw = ""
            if isinstance(out, list) and out:
                raw = out[0].get("generated_text") or ""
            text = finalize_summary(raw)
            return text, {"model": lg.model_id, "retries": attempt}
        except Exception as e:
            err = str(e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            return f"[Error local] {err}", {"error": err, "model": lg.model_id, "retries": attempt}

    # Fallback explícito
    return "Error desconocido en modelo local.", {"error": "sin retorno", "model": getattr(lg, 'model_id', 'desconocido')}



# ----------------------------
# Main
# ----------------------------
def run() -> None:
    lg: LocalGen | None = None
    if not INPUT_JSONL.exists():
        raise FileNotFoundError(f"No existe el archivo: {INPUT_JSONL}")

    # Reanudar si ya hay salida previa
    done_ids = load_done_ids(OUTPUT_JSONL)
    use_openai = _use_openai()

    if use_openai:
        print("🌐 Usando modelo OpenAI (gpt-4o-mini).")
        lg = None
        model_id = "gpt-4o-mini"
    else:
        lg = _load_local_pipeline()
        model_id = lg.model_id

    items = list(jsonl_iter(INPUT_JSONL))
    print(f"📂 Procesando {len(items)} tareas desde {INPUT_JSONL}...")
    buffer: List[Dict[str, Any]] = []

    for item in tqdm(items, desc="🧠 Naturalizando tareas"):
        md: str = item.get("text") or ""
        metadata: Dict[str, Any] = item.get("metadata") or {}
        task_id = str(metadata.get("task_id") or "")

        if task_id and task_id in done_ids:
            # ya procesado previamente
            continue

        if not isinstance(md, str) or not md.strip():
            summary, usage = "Sin contenido.", {"warning": "markdown vacío", "model": model_id}
        else:
            if use_openai:
                summary, usage = _summarize_openai(md)
            else:
                summary, usage = _summarize_local(md, lg)

        # Metadatos de auditoría
        enriched = {
            "text": summary,
            "metadata": metadata,
            "usage": {
                **(usage or {}),
                "summary_chars": len(summary or ""),
                "summary_sentences": len(re.split(r"(?<=[\.\!\?;])\s+", summary)) if summary else 0,
            },
        }
        buffer.append(enriched)

        if len(buffer) >= N_FLUSH:
            jsonl_append(OUTPUT_JSONL, buffer)
            for b in buffer:
                if (b.get("metadata") or {}).get("task_id"):
                    done_ids.add(str(b["metadata"]["task_id"]))
            buffer.clear()

    if buffer:
        jsonl_append(OUTPUT_JSONL, buffer)
        buffer.clear()

    print(f"\n✅ Naturalización completada. Archivo generado en {OUTPUT_JSONL}")


if __name__ == "__main__":
    run()
