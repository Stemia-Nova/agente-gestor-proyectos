#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import traceback
from typing import Any, cast
from utils.hybrid_search import HybridSearch

# Inicializa una única instancia del motor IA
hybrid_search = HybridSearch()

# Si quieres mantener sincronización con ClickUp:
try:
    from data.rag.sync import update_chroma_from_clickup
except Exception:
    update_chroma_from_clickup = None


async def handle_query(query: str) -> str:
    """Router principal: delega en HybridSearch."""
    q = query.strip()
    if not q:
        return "Por favor, formula una pregunta sobre tareas, sprints o bloqueos."

    if any(k in q.lower() for k in ["actualiza clickup", "sincroniza clickup"]):
        return await _sync_clickup()
    try:
        return cast(Any, hybrid_search).answer(q)
    except Exception as e:
        traceback.print_exc()
        return f"❌ Error procesando la consulta: {e}"
        return f"❌ Error procesando la consulta: {e}"


async def _sync_clickup() -> str:
    """Ejecuta sincronización con ClickUp desde el chat."""
    if not update_chroma_from_clickup:
        return "⚠️ No se pudo cargar el módulo de sincronización."
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, update_chroma_from_clickup.main)
        return "✅ Sincronización completada correctamente."
    except Exception as e:
        traceback.print_exc()
        return f"❌ Error durante la sincronización: {e}"