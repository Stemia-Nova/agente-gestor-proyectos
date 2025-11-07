#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Handlers para el Agente Gestor de Proyectos (Chainlit).

✅ Soporta:
 - Preguntas de conteo: tareas totales, por sprint, completadas, bloqueadas, urgentes, etc.
 - Preguntas sobre sprints: activos, cerrados, listado de sprints, sprint actual.
 - Búsqueda semántica híbrida vía HybridSearch (embeddings + BM25 + reranker).
 - Síntesis con OpenAI (SDK moderno >= 1.0.0).
"""

import re
import asyncio
import os
import json
import chainlit as cl
from typing import Optional, Dict, Any
from pathlib import Path

from utils.hybrid_search import HybridSearch
from chatbot import prompts
from chatbot import config as chat_config

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ================================================================
# Inicialización del motor de búsqueda
# ================================================================

_HS_INSTANCE: Optional[HybridSearch] = None


def _ensure_hs() -> HybridSearch:
    """Devuelve la instancia global de HybridSearch (singleton)."""
    global _HS_INSTANCE
    if _HS_INSTANCE is None:
        _HS_INSTANCE = HybridSearch(chroma_base=Path("data/rag/chroma_db"))
    return _HS_INSTANCE


# ================================================================
# Utilidades de formato
# ================================================================

def _extract_title(text: str) -> str:
    m = re.search(r"La tarea '([^']+)'", text)
    return m.group(1) if m else "(sin título)"


def _format_results(results: list) -> str:
    """Formatea resultados del RAG de forma legible."""
    unique = {}
    for r in results:
        tid = (r.get("metadata", {}) or {}).get("task_id")
        if tid and tid not in unique:
            unique[tid] = r
    results = list(unique.values())

    parts = []
    for i, r in enumerate(results, start=1):
        meta = r.get("metadata", {}) or {}
        task_id = meta.get("task_id", "-")
        sprint = meta.get("sprint", "-")
        project = meta.get("project", "-")
        status = meta.get("status", "-")
        priority = meta.get("priority", "sin prioridad")
        assignees = meta.get("assignees", "sin asignar")
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


# ================================================================
# Detección de intención
# ================================================================

def _detect_count_intent(text: str) -> Optional[Dict[str, Any]]:
    """Detecta intenciones de conteo o consultas estructuradas."""
    q = text.lower()
    q = q.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

    # --- Conteos de tareas ---
    if any(x in q for x in ["cuantos", "cuantas", "numero de", "total de"]):
        if "sprints" in q:
            return {"type": "sprints"}
        if any(k in q for k in ["completadas", "finalizadas", "cerradas", "hechas", "done"]):
            return {"filters": {"status": "finalizada"}, "field": "tareas completadas"}
        if any(k in q for k in ["bloqueadas", "impedidas", "bloqueo"]):
            return {"filters": {"is_blocked": True}, "field": "tareas bloqueadas"}
        if any(k in q for k in ["urgentes", "urgente"]):
            return {"filters": {"priority": "urgente"}, "field": "tareas urgentes"}
        if "tareas" in q:
            return {"filters": None, "field": "tareas"}

    # --- Consultas sobre sprints ---
    if any(k in q for k in ["sprint actual", "sprint activo", "que sprint"]):
        return {"type": "current_sprint"}
    if any(k in q for k in ["sprints cerrados", "finalizados", "terminados"]):
        return {"type": "closed_sprints"}

    # --- Conteo dentro de un sprint específico ---
    sprint_match = re.search(r"sprint\s+(\d+)", q)
    if sprint_match:
        sprint_name = f"Sprint {sprint_match.group(1)}"
        if "completadas" in q or "finalizadas" in q:
            return {"filters": {"status": "finalizada"}, "field": "tareas completadas", "scope": sprint_name}
        if "bloqueadas" in q:
            return {"filters": {"is_blocked": True}, "field": "tareas bloqueadas", "scope": sprint_name}
        if "urgentes" in q:
            return {"filters": {"priority": "urgente"}, "field": "tareas urgentes", "scope": sprint_name}
        if "tareas" in q:
            return {"filters": None, "field": "tareas", "scope": sprint_name}

    return None


def _answer_sprint_query(intent_type: str) -> str:
    """Responde consultas relacionadas con los sprints."""
    reg_path = Path("data/rag/chroma_db/index_registry.json")
    if not reg_path.exists():
        return "❌ No hay registro de sprints aún. Ejecuta el pipeline de indexado."

    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    if not registry:
        return "❌ No hay sprints registrados."

    sprints = list(registry.keys())
    active = [s for s, info in registry.items() if info.get("status") == "active"]
    closed = [s for s, info in registry.items() if info.get("status") != "active"]

    if intent_type == "sprints":
        txt = ", ".join(sprints)
        active_txt = f" El sprint actual es {active[-1]}." if active else ""
        return f"Hay {len(sprints)} sprints ({txt}).{active_txt}"

    if intent_type == "current_sprint":
        return f"El sprint actual es {active[-1]}." if active else "No hay sprint activo registrado."

    if intent_type == "closed_sprints":
        if not closed:
            return "No hay sprints cerrados."
        return f"Los sprints cerrados son: {', '.join(closed)}."

    return "No se pudo interpretar la consulta sobre sprints."


# ================================================================
# OpenAI utilities
# ================================================================

def _build_prompt(context: str, question: str, system: Optional[str] = None) -> str:
    """Construye y devuelve el prompt contextual completo."""
    if system is None:
        system = getattr(prompts, "SYSTEM_INSTRUCTIONS", "")
    return prompts.RAG_CONTEXT_PROMPT.format(system=system, context=context, question=question)


def _synthesize_sync_openai(context: str, question: str, model: str = "gpt-4o-mini") -> str:
    """Genera una respuesta con OpenAI (SDK moderno >=1.0)."""
    if OpenAI is None:
        raise RuntimeError("La librería 'openai' no está instalada.")

    api_key = getattr(chat_config, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no configurada en `chatbot.config`")

    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(context, question)

    messages = [
        {
            "role": "system",
            "content": (
                "Eres un asistente experto en gestión ágil y Scrum. "
                "Responde de forma breve, basada solo en el contexto, sin inventar información."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        max_tokens=400,
        temperature=0.0,
    )

    message_content = getattr(response.choices[0].message, "content", None) or ""
    return message_content.strip()


# ================================================================
# Chainlit Handlers
# ================================================================

@cl.on_chat_start
async def start():
    await cl.Message(content=prompts.WELCOME_PROMPT).send()


@cl.on_message
async def on_message(message: cl.Message):
    text = (getattr(message, "content", "") or "").strip()
    if not text:
        await cl.Message(content="No he recibido ninguna pregunta.").send()
        return

    hs = _ensure_hs()
    ql = text.lower()

    # 1️⃣ Intento de conteo directo o pregunta estructurada
    count_intent = _detect_count_intent(ql)
    if count_intent:
        try:
            # --- sprints ---
            if count_intent.get("type") in ("sprints", "current_sprint", "closed_sprints"):
                msg = _answer_sprint_query(count_intent["type"])
                await cl.Message(content=msg).send()
                return

            # --- tareas ---
            field = count_intent.get("field", "tareas")
            filters = count_intent.get("filters") if isinstance(count_intent.get("filters"), dict) else None
            scope = count_intent.get("scope", "all")

            total = hs.count_tasks(filters=filters, scope=scope)
            sprint_txt = f" en {scope}" if scope not in (None, "all") else ""
            await cl.Message(content=f"Hay {total} {field}{sprint_txt}.").send()
            return

        except Exception as e:
            await cl.Message(content=f"Error al procesar la consulta: {e}").send()
            return

    # 2️⃣ Consulta semántica RAG normal
    try:
        results = await asyncio.get_running_loop().run_in_executor(None, hs.query, text, 5, "all")
    except Exception as e:
        await cl.Message(content=f"Error durante la búsqueda de contexto: {e}").send()
        return

    if not results:
        await cl.Message(content=prompts.RAG_NO_RESULTS).send()
        return

    context_text = _format_results(results)
    prompt_text = _build_prompt(context_text, text)
    debug = any(k in ql for k in ["debug", "mostrar contexto", "mostrar prompt"])

    # 3️⃣ Síntesis con OpenAI
    try:
        use_openai = (OpenAI is not None) and bool(getattr(chat_config, "OPENAI_API_KEY", None))
        if use_openai:
            synthesized = await asyncio.get_running_loop().run_in_executor(
                None, _synthesize_sync_openai, context_text, text
            )
            await cl.Message(content=synthesized).send()
            if debug:
                await cl.Message(content=f"🧩 DEBUG — Prompt usado:\n\n{prompt_text}").send()
        else:
            await cl.Message(content=f"He encontrado {len(results)} fragmentos relevantes:\n\n{context_text}").send()
    except Exception as e:
        await cl.Message(content=f"No fue posible sintetizar respuesta con OpenAI: {e}\n\n{context_text}").send()
