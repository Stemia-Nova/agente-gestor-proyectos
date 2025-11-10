#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers.py — versión Pro++ (conteos ampliados)
---------------------------------------------
• Búsqueda híbrida avanzada (HybridSearch)
• Detección de intención
• Consultas analíticas: conteos por estado/bloqueo/prioridad/sprint
• Contexto persistente
• Sincronización ClickUp desde el chat
"""

import asyncio
import traceback
import re
import importlib
import unicodedata
from typing import Any, Dict, Optional, Tuple

from utils.hybrid_search import HybridSearch

# ==============================================================
# 🔧 Carga dinámica del módulo de sincronización (opcional)
# ==============================================================
try:
    update_chroma_from_clickup = importlib.import_module("data.rag.sync.update_chroma_from_clickup")
except Exception as e:
    update_chroma_from_clickup = None
    print(f"⚠️ No se pudo importar update_chroma_from_clickup: {e}")

# ==============================================================
# 🧠 Inicialización global
# ==============================================================
hybrid_search = HybridSearch()
context_memory: Dict[str, Any] = {}  # memoria simple por sesión


# ========================= Utilidades =========================
def _strip_accents(s: str) -> str:
    """Quita tildes/diacríticos para matching robusto ('cuantos' ~ 'cuántos')."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _detect_intent(q_nf: str) -> str:
    """Clasificación básica de intención por palabras clave (sin tildes)."""
    if re.search(r"\bbloquead", q_nf):
        return "bloqueadas"
    if re.search(r"\bpendient|\ben\s+curso|\bprogreso", q_nf):
        return "progreso"
    if re.search(r"\bcompletad|\bcerrad|\bfinalizad|\bdone\b", q_nf):
        return "completadas"
    if re.search(r"\bsprint\b", q_nf):
        return "sprint"
    if re.search(r"\basignad|\bresponsable", q_nf):
        return "responsables"
    return "general"

def _extract_sprint(q_nf: str) -> Optional[str]:
    """Extrae 'Sprint X' si aparece 'sprint 1', 'del sprint 2', 'en sprint 3', etc."""
    m = re.search(r"sprint\s*(\d+)", q_nf)
    if m:
        return f"Sprint {m.group(1)}"
    return None

def _parse_count_query(q_nf: str) -> Optional[Tuple[str, Dict[str, str]]]:
    """
    Detecta consultas de CONTEO y devuelve (accion, params)
      - count_sprints
      - count_tasks
      - count_tasks_in_sprint [sprint]
      - count_tasks_blocked [sprint?]
      - count_tasks_by_status [status, sprint?]
      - count_tasks_by_priority [priority, sprint?]
    """
    # sprints
    if re.search(r"\bcuant[ao]s?\s+sprints?\b", q_nf) or re.search(r"\bnumer[oa]\s+de\s+sprints?\b", q_nf):
        return ("count_sprints", {})

    # sprint contextual detectado (opcional)
    sprint = _extract_sprint(q_nf)

    # tareas totales (solo si NO hay calificadores)
    # incluye 'progreso' como calificador para NO caer aquí por error
    if re.search(r"\bcuant[ao]s?\s+tareas?\b", q_nf) or re.search(r"\bnumer[oa]\s+de\s+tareas?\b", q_nf):
        if not re.search(r"\b(bloquead|urgent|urgentes?|alta|high|normal|low|baja|to[_ ]?do|in[_ ]?progress|en\s+curso|progreso|pendient|done|completad)\b", q_nf):
            if sprint:
                return ("count_tasks_in_sprint", {"sprint": sprint})
            return ("count_tasks", {})

    # bloqueadas
    if re.search(r"\bcuant[ao]s?\s+tareas?\s+bloquead", q_nf):
        return ("count_tasks_blocked", {"sprint": sprint} if sprint else {})

    # prioridad
    if re.search(r"\bcuant[ao]s?\s+tareas?\s+urgentes?\b", q_nf) or re.search(r"\bprioridad\s+urgente\b", q_nf):
        return ("count_tasks_by_priority", {"priority": "urgent", **({"sprint": sprint} if sprint else {})})
    if re.search(r"\bprioridad\s+alta\b|\bhigh\b", q_nf):
        return ("count_tasks_by_priority", {"priority": "high", **({"sprint": sprint} if sprint else {})})
    if re.search(r"\bprioridad\s+normal\b", q_nf):
        return ("count_tasks_by_priority", {"priority": "normal", **({"sprint": sprint} if sprint else {})})
    if re.search(r"\bprioridad\s+baja\b|\blow\b", q_nf):
        return ("count_tasks_by_priority", {"priority": "low", **({"sprint": sprint} if sprint else {})})

    # estado
    if re.search(r"\b(to[_ ]?do|pendient)\b", q_nf):
        return ("count_tasks_by_status", {"status": "to_do", **({"sprint": sprint} if sprint else {})})
    if re.search(r"\b(in[_ ]?progress|en\s+curso|progreso)\b", q_nf):
        return ("count_tasks_by_status", {"status": "in_progress", **({"sprint": sprint} if sprint else {})})
    if re.search(r"\b(done|completad|cerrad|finalizad)\b", q_nf):
        return ("count_tasks_by_status", {"status": "done", **({"sprint": sprint} if sprint else {})})

    return None


# ========================= Handler principal =========================
async def handle_query(query: str) -> str:
    """Procesa consultas naturales del usuario."""
    try:
        q_raw = query.strip()
        if not q_raw:
            return "Por favor, formula una pregunta relacionada con tareas, sprints o bloqueos."

        q = q_raw.lower()
        q_nf = _strip_accents(q)  # versión sin tildes para regex robusto

        # --- Sincronización manual con ClickUp ---
        if any(k in q_nf for k in ["actualiza clickup", "sincroniza clickup", "refresca datos"]):
            return await _sync_clickup()

        # --- Ruteo de CONTEOS (ampliado) ---
        count_parse = _parse_count_query(q_nf)
        if count_parse:
            accion, params = count_parse
            from utils.helpers import (
                count_sprints, count_tasks,
                count_tasks_in_sprint, count_tasks_blocked,
                count_tasks_by_status, count_tasks_by_priority
            )
            if accion == "count_sprints":
                return count_sprints()
            if accion == "count_tasks":
                return count_tasks()
            if accion == "count_tasks_in_sprint":
                return count_tasks_in_sprint(params["sprint"])
            if accion == "count_tasks_blocked":
                return count_tasks_blocked(params.get("sprint"))
            if accion == "count_tasks_by_status":
                return count_tasks_by_status(params["status"], params.get("sprint"))
            if accion == "count_tasks_by_priority":
                return count_tasks_by_priority(params["priority"], params.get("sprint"))

        # --- Detección básica de intención (para vía semántica) ---
        intent = _detect_intent(q_nf)

        # --- Búsqueda híbrida (embeddings + rerank + intención) ---
        result, metas = hybrid_search.search(q, top_k=6)  # usamos el texto original (con tildes) para semántica
        if not metas:
            return "No encontré resultados relevantes para esa consulta."

        response = _format_response(intent, result, metas)
        context_memory["last_query"] = q_raw
        context_memory["last_response"] = response
        return response

    except Exception as e:
        traceback.print_exc()
        return f"❌ Error procesando la consulta: {e}"


# ========================= Formato de respuesta =========================
def _format_response(intent: str, results: list[str], metas: list[dict[str, Any]]) -> str:
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

    if metas:
        first = metas[0]
        lines.append("\n💡 Recomendación:")
        lines.append(
            f"Revisa '{first.get('name')}' — responsable: {first.get('assignees', 'sin asignar')}, prioridad: {first.get('priority', 'sin prioridad')}."
        )
    else:
        lines.append("\n💡 Recomendación:")
        lines.append("No hay recomendaciones disponibles.")

    return "\n".join(lines)


# ========================= Sincronización ClickUp =========================
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


# ========================= Modo prueba =========================
if __name__ == "__main__":
    async def _test():
        print(await handle_query("cuantos sprints hay?"))
        print(await handle_query("cuantas tareas hay?"))
        print(await handle_query("cuantas tareas bloqueadas hay?"))
        print(await handle_query("cuantas tareas urgentes hay en sprint 2?"))
        print(await handle_query("cuantas tareas en progreso del sprint 1?"))
        print(await handle_query("cuantas tareas tiene el sprint 3?"))
        print(await handle_query("actualiza ClickUp"))

    asyncio.run(_test())
