#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Handlers para el Agente Gestor de Proyectos (Chainlit).

Incluye:
- Detección de preguntas de conteo (cuántas tareas, cuántos sprints…)
- Búsqueda semántica híbrida (HybridSearch.query)
- Conteo estructurado directo (HybridSearch.count_tasks)
- Compatibilidad total con OpenAI SDK 0.x y 1.x
"""

import re
import asyncio
import os
import time
import random
import json
import chainlit as cl
from typing import Optional
from pathlib import Path

from utils.hybrid_search import HybridSearch
from chatbot import prompts
from chatbot import config as chat_config

try:
    import openai
except Exception:
    openai = None


# =============================================================
# Inicialización de HybridSearch
# =============================================================
_HS_INSTANCE = None


def _ensure_hs() -> HybridSearch:
    """Inicializa (si no existe) y devuelve la instancia compartida de HybridSearch."""
    global _HS_INSTANCE
    if _HS_INSTANCE is None:
        _HS_INSTANCE = HybridSearch(chroma_base=Path("data/rag/chroma_db"))
    return _HS_INSTANCE


# =============================================================
# Utilidades de formato
# =============================================================
def _extract_title(text: str) -> str:
    m = re.search(r"La tarea '([^']+)'", text)
    return m.group(1) if m else "(sin título)"


def _format_results(results: list) -> str:
    """Formatea los resultados del RAG para mostrarlos en texto legible."""
    unique = {}
    for r in results:
        tid = (r.get("metadata", {}) or {}).get("task_id")
        if tid and tid not in unique:
            unique[tid] = r
    results = list(unique.values())

    parts = []
    for i, r in enumerate(results, start=1):
        meta = r.get("metadata", {}) or {}
        task_id = meta.get("task_id") or "-"
        sprint = meta.get("sprint") or "-"
        project = meta.get("project") or "-"
        status = meta.get("status") or "-"
        priority = meta.get("priority") or "sin prioridad"
        assignees = meta.get("assignees") or "sin asignar"
        title = _extract_title(r.get("text", ""))
        snippet = r.get("text", "").strip().replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:300].rstrip() + "..."
        parts.append(
            f"{i}. [{task_id}] '{title}'\n"
            f"   Proyecto: {project} | Sprint: {sprint}\n"
            f"   Estado: {status} | Prioridad: {priority} | Asignado: {assignees}\n"
            f"   Descripción: {snippet}\n"
        )
    return "\n".join(parts)


# =============================================================
# Detección de intención
# =============================================================
def _detect_count_intent(text: str) -> Optional[dict]:
    """Detecta si la pregunta es de tipo conteo (cuántas tareas, sprints, bloqueadas, etc.)."""
    q = text.lower()
    if "cuántas" in q or "cuantos" in q:
        if any(k in q for k in ["completadas", "finalizadas", "hechas", "cerradas"]):
            return {"filters": {"status": "finalizada"}, "field": "tareas completadas"}
        if any(k in q for k in ["bloqueadas", "impedidas"]):
            return {"filters": {"is_blocked": True}, "field": "tareas bloqueadas"}
        if any(k in q for k in ["urgentes", "urgente"]):
            return {"filters": {"priority": "urgente"}, "field": "tareas urgentes"}
        if "tareas" in q:
            return {"filters": None, "field": "tareas"}
    if "cuántos" in q or "cuantas" in q:
        if "sprints" in q:
            return {"filters": None, "field": "sprints"}
    return None


# =============================================================
# OpenAI utilidades
# =============================================================
def _build_prompt(context: str, question: str) -> str:
    """Construye y devuelve el prompt exacto que se envía al modelo."""
    return prompts.RAG_CONTEXT_PROMPT.format(
        system=prompts.SYSTEM_INSTRUCTIONS,
        context=context,
        question=question
    )
def _synthesize_sync_openai(context: str, question: str, model: str = "gpt-4o-mini") -> str:
    """Genera una respuesta usando el SDK moderno de OpenAI (>=1.0)."""
    if openai is None:
        raise RuntimeError("La librería 'openai' no está instalada.")

    api_key = getattr(chat_config, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no configurada en `chatbot.config`")

    # Configurar cliente (nuevo SDK)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        raise RuntimeError("Instala openai>=1.0.0 correctamente con `pip install openai -U`")

    # Construir prompt contextual
    prompt = _build_prompt(context, question)
    messages = [
        {
            "role": "system",
            "content": "Eres un asistente conciso, experto en gestión ágil y orientado a acciones. Usa únicamente la información del contexto.",
        },
        {"role": "user", "content": prompt},
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=400,
            temperature=0.0,
        )
        text = response.choices[0].message.content.strip()
        return text
    except Exception as e:
        raise RuntimeError(f"Error al generar respuesta con OpenAI: {e}")


# =============================================================
# Chainlit Handlers
# =============================================================
@cl.on_chat_start
async def start():
    """Mensaje de bienvenida."""
    await cl.Message(content=prompts.WELCOME_PROMPT).send()


@cl.on_message
async def on_message(message: cl.Message):
    text = (getattr(message, "content", "") or "").strip()
    if not text:
        await cl.Message(content="No he recibido ninguna pregunta.").send()
        return

    hs = _ensure_hs()
    ql = text.lower()

    # 1️⃣ Intento de conteo directo
    count_intent = _detect_count_intent(ql)
    if count_intent:
        field = count_intent["field"]
        try:
            if field == "sprints":
                reg_path = Path("data/rag/chroma_db/index_registry.json")
                if not reg_path.exists():
                    await cl.Message(content="No hay registro de sprints aún.").send()
                    return
                with open(reg_path, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                total = len(registry)
            else:
                total = hs.count_tasks(filters=count_intent["filters"])
            await cl.Message(content=f"Hay {total} {field}.").send()
            return
        except Exception as e:
            await cl.Message(content=f"Error al contar {field}: {e}").send()
            return

    # 2️⃣ Consulta semántica normal
    try:
        results = await asyncio.get_running_loop().run_in_executor(None, hs.query, text)
    except Exception as e:
        await cl.Message(content=f"Error durante la búsqueda de contexto: {e}").send()
        return

    if not results:
        await cl.Message(content=prompts.RAG_NO_RESULTS).send()
        return

    context_text = _format_results(results)
    prompt_text = _build_prompt(context_text, text)
    debug = any(k in ql for k in ["debug", "mostrar contexto", "mostrar prompt"])

    # 3️⃣ Síntesis de respuesta con OpenAI
    try:
        use_openai = (openai is not None) and bool(getattr(chat_config, "OPENAI_API_KEY", None))
        if use_openai:
            synthesized = await asyncio.get_running_loop().run_in_executor(
                None, _synthesize_sync_openai, context_text, text
            )
            await cl.Message(content=synthesized).send()
            if debug:
                await cl.Message(content=f"DEBUG - Prompt usado:\n\n{prompt_text}").send()
        else:
            await cl.Message(content=f"He encontrado {len(results)} fragmentos relevantes:\n\n{context_text}").send()
    except Exception as e:
        await cl.Message(content=f"No fue posible sintetizar respuesta con OpenAI: {e}\n\n{context_text}").send()
