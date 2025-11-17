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
            # Verificar que la respuesta anterior existe y no es None
            if last.get('response'):
                conv_context = (
                    f"[CONTEXTO DE CONVERSACIÓN PREVIA]\n"
                    f"Pregunta anterior: {last['query']}\n"
                    f"Respuesta anterior: {last['response'][:150]}{'...' if len(last['response']) > 150 else ''}\n"
                    f"[FIN CONTEXTO]"
                )
        
        # Obtener respuesta con contexto conversacional
        response = cast(Any, hybrid_search).answer(enriched_query, conversation_context=conv_context)
        
        # Verificar que la respuesta no es None o vacía
        if not response:
            response = "❌ No se pudo generar una respuesta. Por favor, intenta reformular tu pregunta."
        
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
    if not conversation_history:
        return query
    
    query_lower = query.lower()
    
    # Palabras que indican referencias contextuales
    contextual_refs = [
        "esa tarea", "ese", "esa", "esos", "esas", 
        "esta tarea", "este", "esta", "estos", "estas",
        "la anterior", "las anteriores", "el anterior", "los anteriores",
        "dicha", "dichas", "dicho", "dichos",
        "la tarea", "las tareas", "la bloqueada"
    ]
    
    # Conectores que sugieren continuidad (al inicio de pregunta)
    continuity_markers = ["¿y ", "y ", "también ", "además ", "¿también ", "¿tiene ", "tiene ", "qué ", "¿qué "]
    
    # Solicitudes explícitas de más información
    more_info_requests = [
        "más info", "mas info", "más información", "mas información",
        "dame más", "dame mas", "cuéntame más", "cuentame mas",
        "dime más", "dime mas", "detalle", "detalles"
    ]
    
    has_contextual_ref = any(ref in query_lower for ref in contextual_refs)
    starts_with_continuity = any(query_lower.startswith(marker) for marker in continuity_markers)
    is_more_info_request = any(req in query_lower for req in more_info_requests)
    
    # Detectar preguntas sobre características de la tarea anterior (comentarios, subtareas, etc.)
    is_feature_question = any(word in query_lower for word in ["comentario", "subtarea", "prioridad", "asignado", "estado", "sprint"])
    is_short_question = len(query.split()) <= 6  # Preguntas cortas como "¿Tiene comentarios?"
    
    # Si hay referencia contextual, solicitud de más info, o pregunta sobre características
    should_enrich = (
        has_contextual_ref or 
        starts_with_continuity or 
        is_more_info_request or
        (is_feature_question and is_short_question)
    )
    
    if should_enrich:
        # Obtener última interacción
        last_interaction = conversation_history[-1]
        last_query = last_interaction["query"]
        last_response = last_interaction.get("response", "")[:400]  # Primeros 400 chars
        
        # Intentar extraer nombre de tarea del contexto previo
        # Buscar patrones como: '"Nombre de la tarea"' o 'tarea "Nombre"'
        import re
        task_names = re.findall(r'"([^"]+)"', last_response)
        
        if task_names:
            # Si hay nombres de tareas en la respuesta anterior, incluirlos
            # Para solicitudes de "más info", ser más explícito
            if is_more_info_request:
                context_info = (
                    f"IMPORTANTE: El usuario solicita MÁS INFORMACIÓN sobre la tarea: '{task_names[0]}'\n"
                    f"Proporciona TODOS los detalles disponibles: estado, sprint, prioridad, asignados, "
                    f"comentarios (cuántos y su contenido si es posible), subtareas (cantidad y estados), "
                    f"tags, fechas, y cualquier otra información relevante."
                )
            else:
                context_info = f"Tarea del contexto: '{task_names[0]}'"
            
            enriched = (
                f"[CONTEXTO DE CONVERSACIÓN PREVIA]\n"
                f"Pregunta anterior: {last_query}\n"
                f"Respuesta anterior: {last_response}\n"
                f"{context_info}\n"
                f"[NUEVA PREGUNTA]: {query}"
            )
        else:
            enriched = (
                f"[CONTEXTO DE CONVERSACIÓN PREVIA]\n"
                f"Pregunta anterior: {last_query}\n"
                f"Respuesta anterior: {last_response}\n"
                f"[NUEVA PREGUNTA]: {query}"
            )
        
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