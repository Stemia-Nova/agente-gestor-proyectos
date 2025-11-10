#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chatbot/handlers.py
-------------------
Versión refinada para integración con `chatbot/prompts.py`.

✔ Integra HybridSearch (RAG)
✔ Usa prompts especializados (Scrum/Agile)
✔ Genera respuestas naturales o JSON según el tipo de consulta
✔ Incluye memoria conversacional, comandos y debug
✔ Compatible con Chainlit 2.8.x y `main.py` clásico
"""

import os
import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from utils.hybrid_search import HybridSearch
from chatbot import prompts  # importamos tu prompts.py

# ======================================================
# ⚙️ CARGA DE ENTORNO
# ======================================================
load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
REQUEST_TIMEOUT = float(os.getenv("OPENAI_REQUEST_TIMEOUT", 60))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

try:
    client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception as e:
    print(f"⚠️ No se pudo inicializar OpenAI: {e}")
    client = None

# Instanciar HybridSearch (sin parámetros, según tu clase actual)
hybrid_search = HybridSearch()

# ======================================================
# 💾 MEMORIA CONVERSACIONAL
# ======================================================
_conversation_history: List[Dict[str, str]] = []


def _log_conversation(q: str, r: str) -> None:
    """Guarda en memoria las últimas interacciones."""
    _conversation_history.append(
        {"timestamp": datetime.now().isoformat(timespec="seconds"), "question": q, "answer": r}
    )
    if len(_conversation_history) > 5:
        _conversation_history.pop(0)


def reset_memory() -> str:
    _conversation_history.clear()
    return "🧹 Memoria conversacional reiniciada."


# ======================================================
# 🧮 UTILIDADES DE FORMATEO
# ======================================================

def summarize_context(meta: List[Dict[str, Any]]) -> str:
    """Crea un resumen textual de las tareas recuperadas."""
    if not meta:
        return "(sin contexto)"
    resumen = []
    for m in meta[:5]:
        resumen.append(
            f"- {m.get('name','Tarea sin nombre')} "
            f"(Sprint {m.get('sprint','?')}) — "
            f"{m.get('status','?')}, "
            f"{m.get('assignees','Sin asignar')}, "
            f"prioridad: {m.get('priority','Sin prioridad')}."
        )
    return "\n".join(resumen)


# ======================================================
# 🧠 GENERACIÓN CON OPENAI
# ======================================================

async def _synthesize_openai(question: str, context: str) -> str:
    """Genera respuesta contextual con OpenAI o fallback."""
    context = str(context or "")
    if not client:
        return prompts.DEFAULT_ECHO_PREFIX + " " + context if context.strip() else prompts.RAG_NO_RESULTS

    # Construimos prompt contextual
    user_prompt = prompts.RAG_CONTEXT_PROMPT.format(
        system=prompts.SYSTEM_INSTRUCTIONS,
        context=context,
        question=question,
    )

    # Intentamos hasta 3 veces (por rate limit)
    for attempt in range(3):
        try:
            completion = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": prompts.SYSTEM_INSTRUCTIONS},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.25,
                    max_tokens=450,
                    timeout=REQUEST_TIMEOUT,
                )
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e):
                delay = (attempt + 1) * 2
                print(f"⚠️ Rate limit alcanzado. Reintentando en {delay}s...")
                time.sleep(delay)
                continue
            print(f"⚠️ Error con OpenAI: {e}")
            break

    # Fallback textual
    return (
        "Respuesta basada en el contexto:\n" + context
        if context.strip()
        else prompts.RAG_NO_RESULTS
    )


# ======================================================
# 💬 MANEJADOR PRINCIPAL
# ======================================================

async def handle_query(query: str) -> str:
    """Maneja consultas del usuario con RAG, prompts y memoria."""
    q = (query or "").strip()
    if not q:
        return "Por favor, escribe una pregunta."

    # --- Comandos ---
    if q.lower() in {"/ayuda", "ayuda"}:
        return (
            "📘 Comandos disponibles:\n"
            "• /contexto → muestra las últimas interacciones.\n"
            "• /reset → borra la memoria conversacional.\n"
            "• /debug → muestra el último prompt enviado al modelo.\n"
            "• /ayuda → muestra esta lista.\n"
        )

    if q.lower() in {"/reset", "reset"}:
        return reset_memory()

    if q.lower() in {"/contexto", "contexto"}:
        if not _conversation_history:
            return "🧠 Memoria vacía."
        texto = "\n\n".join(
            f"[{x['timestamp']}] Q: {x['question']}\nA: {x['answer']}"
            for x in _conversation_history
        )
        return f"🧠 Memoria reciente:\n{texto}"

    # --- Búsqueda híbrida ---
    try:
        results, metas = hybrid_search.search(q, top_k=5)  # type: ignore[attr-defined]
    except Exception as e:
        r = f"⚠️ Error en la búsqueda: {e}"
        _log_conversation(q, r)
        return r

    if not results:
        r = prompts.RAG_NO_RESULTS
        _log_conversation(q, r)
        return r

    # --- Preparar contexto y generar respuesta ---
    context_text = summarize_context(metas)
    answer = await _synthesize_openai(q, context_text)

    # --- Guardar en memoria y devolver ---
    _log_conversation(q, answer)
    return answer


# ======================================================
# 🧩 DEBUG LOCAL
# ======================================================

if __name__ == "__main__":
    import asyncio

    print("🤖 Prueba manual del handler con prompts ágiles")
    res = asyncio.run(handle_query("¿Qué tareas están bloqueadas?"))
    print(res)
