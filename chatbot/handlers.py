#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import traceback
from typing import Any, cast, List, Dict
from utils.hybrid_search import HybridSearch

# Inicializa una única instancia del motor IA
hybrid_search = HybridSearch()

# Memoria contextual de conversación (últimas 5 interacciones)
conversation_history: List[Dict[str, str]] = []

# Si quieres mantener sincronización con ClickUp:
try:
    from data.rag.sync import update_chroma_from_clickup
except Exception:
    update_chroma_from_clickup = None


async def handle_query(query: str) -> str:
    """Router principal: delega en HybridSearch con memoria contextual."""
    global conversation_history
    
    q = query.strip()
    if not q:
        return "Por favor, formula una pregunta sobre tareas, sprints o bloqueos."

    if any(k in q.lower() for k in ["actualiza clickup", "sincroniza clickup"]):
        return await _sync_clickup()
    
    try:
        # Enriquecer query con contexto si contiene referencias
        enriched_query = _enrich_query_with_context(q)
        
        # Preparar contexto conversacional para el LLM
        conv_context = ""
        if conversation_history:
            last = conversation_history[-1]
            conv_context = (
                f"[CONTEXTO DE CONVERSACIÓN PREVIA]\n"
                f"Pregunta anterior: {last['query']}\n"
                f"Respuesta anterior: {last['response'][:150]}{'...' if len(last['response']) > 150 else ''}\n"
                f"[FIN CONTEXTO]"
            )
        
        # Obtener respuesta con contexto conversacional
        response = cast(Any, hybrid_search).answer(enriched_query, conversation_context=conv_context)
        
        # Guardar en historial (máximo 5 interacciones)
        conversation_history.append({"query": q, "response": response})
        if len(conversation_history) > 5:
            conversation_history.pop(0)
        
        return response

    except Exception as e:
        traceback.print_exc()
        return f"❌ Error procesando la consulta: {e}"


def _enrich_query_with_context(query: str) -> str:
    """Enriquece la query con contexto de conversación previa."""
    # Palabras que indican referencias contextuales
    contextual_refs = ["esas", "esos", "estas", "estos", "la anterior", "las anteriores", 
                       "el anterior", "los anteriores", "dicha", "dichas", "dicho", "dichos"]
    
    # Conectores que sugieren continuidad (al inicio de pregunta)
    continuity_markers = ["¿y ", "y ", "también ", "además ", "¿también "]
    
    query_lower = query.lower()
    has_contextual_ref = any(ref in query_lower for ref in contextual_refs)
    starts_with_continuity = any(query_lower.startswith(marker) for marker in continuity_markers)
    
    if (has_contextual_ref or starts_with_continuity) and conversation_history:
        # Obtener última interacción
        last_interaction = conversation_history[-1]
        last_query = last_interaction["query"]
        
        # Enriquecer con contexto
        enriched = f"Contexto previo: '{last_query}'. Nueva pregunta: {query}"
        return enriched
    
    return query


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