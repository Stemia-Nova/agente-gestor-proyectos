#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Prueba mixta End-to-End del Agente Gestor de Proyectos.
→ Usa el LLM real (OpenAI GPT) si OPENAI_API_KEY está configurada.
→ Si no, usa un mock local que simula la respuesta del modelo.
"""

import asyncio
import os
from chatbot import handlers


async def simulate_chat(query: str):
    """Simula un turno de chat completo del agente."""
    hs = handlers._ensure_hs()

    print(f"\n🧠 Consulta: {query}")

    try:
        results = await asyncio.get_running_loop().run_in_executor(None, hs.query, query)
    except Exception as e:
        print(f"❌ Error en HybridSearch: {e}")
        return

    if not results:
        print("⚠️ No se encontraron resultados relevantes.")
        return

    context_text = handlers._format_results(results)
    prompt = handlers._build_prompt(context_text, query)

    # Detectar si hay clave real de OpenAI
    use_real_llm = bool(os.environ.get("OPENAI_API_KEY"))

    if use_real_llm:
        print("🌐 Usando LLM real (OpenAI API)...")
        try:
            synthesized = await asyncio.get_running_loop().run_in_executor(
                None, handlers._synthesize_sync_openai, context_text, query
            )
            print(f"\n💬 RESPUESTA:\n{synthesized}\n")
        except Exception as e:
            print(f"❌ Error al generar respuesta con OpenAI: {e}")
    else:
        print("🧩 Simulación local (sin LLM real).")
        fake_summary = f"Simulación → He encontrado {len(results)} fragmentos relevantes sobre: '{query}'."
        fake_actions = [r.get('metadata', {}).get('task_id', '-') for r in results[:3]]
        print(f"📝 {fake_summary}\n📋 Ejemplo de tareas: {', '.join(fake_actions)}\n")

    print(f"📄 PROMPT (recortado):\n{prompt[:400]}...\n")


def test_end_to_end_mixed():
    """Ejecuta varias preguntas representativas con LLM real o mock."""
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
