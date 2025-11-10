#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers.py — versión Pro
---------------------------------------------
• Búsqueda híbrida avanzada
• Detección simple de intención
• Contexto persistente
• Sincronización ClickUp desde chat
"""

import asyncio
import traceback
import re
import importlib
from typing import Any, Dict

from utils.hybrid_search import HybridSearch

# Carga dinámica del módulo de sincronización
try:
    update_chroma_from_clickup = importlib.import_module("data.rag.sync.update_chroma_from_clickup")
except Exception as e:
    update_chroma_from_clickup = None
    print(f"⚠️ No se pudo importar update_chroma_from_clickup: {e}")

hybrid_search = HybridSearch()

# Memoria de contexto (simple, por sesión)
context_memory: Dict[str, Any] = {}


async def handle_query(query: str) -> str:
    """Procesa consultas naturales del usuario."""
    try:
        q = query.lower().strip()
        if not q:
            return "Por favor, formula una pregunta relacionada con tareas, sprints o bloqueos."

        # Intento de sincronización
        if any(k in q for k in ["actualiza clickup", "sincroniza clickup", "refresca datos"]):
            return await _sync_clickup()

        # Detección básica de intención
        intent = _detect_intent(q)

        # Búsqueda híbrida
        result, metas = hybrid_search.search(q, top_k=6)
        if not metas:
            return "No encontré resultados relevantes para esa consulta."

        response = _format_response(intent, result, metas)
        context_memory["last_query"] = q
        context_memory["last_response"] = response
        return response

    except Exception as e:
        traceback.print_exc()
        return f"❌ Error procesando la consulta: {e}"


def _detect_intent(q: str) -> str:
    """Clasificación básica de intención por palabras clave."""
    if re.search(r"bloquead", q):
        return "bloqueadas"
    if re.search(r"pendient|curso|progreso", q):
        return "progreso"
    if re.search(r"completad|cerrad|finalizad", q):
        return "completadas"
    if re.search(r"sprint", q):
        return "sprint"
    if re.search(r"asignad|responsable", q):
        return "responsables"
    return "general"


def _format_response(intent: str, result: str, metas: list[dict[str, Any]]) -> str:
    """Crea un formato elegante de respuesta estilo Scrum Master."""
    header = {
        "bloqueadas": "🚧 Tareas bloqueadas detectadas:",
        "progreso": "🏃‍♂️ Tareas en curso:",
        "completadas": "✅ Tareas completadas:",
        "sprint": "📆 Información de sprint:",
        "responsables": "👥 Asignaciones:",
        "general": "📋 Información general:"
    }.get(intent, "📋 Información:")

    lines = [header]
    for m in metas[:5]:
        name = m.get("name", "sin nombre")
        sprint = m.get("sprint", "sin sprint")
        prio = m.get("priority", "sin prioridad")
        status = m.get("status", "sin estado")
        blocked = "🚫" if m.get("is_blocked") else ""
        lines.append(f"- {name} ({sprint}) — {status}, prioridad {prio} {blocked}")

    first = metas[0]
    lines.append("\n💡 Recomendación:")
    lines.append(
        f"Revisa '{first.get('name')}' — responsable: {first.get('assignees', 'sin asignar')}, prioridad: {first.get('priority', 'sin prioridad')}."
    )
    return "\n".join(lines)


async def _sync_clickup() -> str:
    """Ejecuta sincronización ClickUp desde el chatbot."""
    if not update_chroma_from_clickup:
        return "⚠️ No se pudo cargar el módulo de sincronización."

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, update_chroma_from_clickup.main)
        return "✅ Sincronización completada correctamente desde ClickUp."
    except Exception as e:
        traceback.print_exc()
        return f"❌ Error durante la sincronización: {e}"


if __name__ == "__main__":
    async def _test():
        print(await handle_query("cuántas tareas hay en curso"))
        print(await handle_query("actualiza ClickUp"))

    asyncio.run(_test())
