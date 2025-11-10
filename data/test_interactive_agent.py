#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_interactive_agent.py
-------------------------
Interfaz interactiva de consola para hablar con el Agente Gestor de Proyectos.

✅ Usa tu base RAG (clickup_tasks)
✅ Integra el LLM (GPT-4o-mini u otro)
✅ Muestra respuestas naturales y contextuales
"""
import sys
from pathlib import Path

# ✅ añade la raíz del proyecto al path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio
import os
from chatbot import handlers

async def interactive():
    print("\n🤖  AGENTE GESTOR DE PROYECTOS — modo interactivo")
    print("Escribe tus preguntas sobre tareas, sprints, bloqueos o prioridades.")
    print("Escribe 'salir' para terminar.\n")

    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  No se detectó OPENAI_API_KEY. Solo se usarán respuestas basadas en contexto.\n")

    while True:
        try:
            query = input("🧠 Tú: ").strip()
            if not query or query.lower() in {"salir", "exit", "quit"}:
                print("👋 Saliendo del modo interactivo.")
                break

            print("⏳ Procesando...\n")
            response = await handlers.handle_query(query)
            print(f"💬 Agente: {response}\n")

        except KeyboardInterrupt:
            print("\n👋 Saliendo del modo interactivo.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(interactive())
