#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Prueba End-to-End del Agente Gestor de Proyectos con LLM real (OpenAI).
Reproduce la misma ruta que Chainlit:
HybridSearch → contexto → _build_prompt → _synthesize_sync_openai
"""

import asyncio
from chatbot import handlers


async def simulate_chat(message: str):
    """Simula un turno de chat completo como si se hiciera desde Chainlit."""
    hs = handlers._ensure_hs()

    print(f"\n🧠 Consulta del usuario: {message}")

    # 1️⃣ Ejecutar búsqueda híbrida (igual que en handlers.on_message)
    try:
        results = await asyncio.get_running_loop().run_in_executor(None, hs.query, message)
    except Exception as e:
        print(f"❌ Error en HybridSearch: {e}")
        return

    if not results:
        print("⚠️ No se encontraron resultados relevantes.")
        return

    # 2️⃣ Construir contexto textual
    context_text = handlers._format_results(results)
    prompt = handlers._build_prompt(context_text, message)

    # 3️⃣ Generar respuesta real con OpenAI (usa tu OPENAI_API_KEY)
    try:
        synthesized = await asyncio.get_running_loop().run_in_executor(
            None, handlers._synthesize_sync_openai, context_text, message
        )
        print(f"\n🧩 PROMPT:\n{prompt[:600]}...\n")
        print(f"💬 RESPUESTA:\n{synthesized}\n")
    except Exception as e:
        print(f"❌ Error al generar respuesta con OpenAI: {e}")


def test_end_to_end_openai():
    """Ejecuta varias preguntas clave usando el pipeline real."""
    queries = [
        "¿Cuántos sprints hay?",
        "¿Cuántas tareas completadas hay en total?",
        "¿Qué tareas tiene Laura?",
        "¿Qué tareas están bloqueadas?",
        "¿Qué tareas tiene Jorge Aguadero?",
        "¿Qué sprint está activo ahora?"
    ]

    loop = asyncio.get_event_loop()
    for q in queries:
        loop.run_until_complete(simulate_chat(q))
