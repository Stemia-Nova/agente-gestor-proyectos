#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Valida la memoria conversacional y coherencia de contexto.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
import asyncio
from chatbot import handlers

@pytest.fixture(scope="module")
def agent():
    if hasattr(handlers, "_conversation_history"):
        handlers._conversation_history.clear()
    return handlers

@pytest.mark.asyncio
async def test_memory_and_followups(agent):
    print("\n==============================")
    print("🧠 TEST MEMORIA CONTEXTUAL")
    print("==============================")

    q1 = "¿Qué tareas están en progreso?"
    r1 = await agent.handle_query(q1)
    lower = r1.lower()

    # aceptar "progreso", "en curso" o "completado" como válidos
    assert any(k in lower for k in ["progreso", "en curso", "completado"]), \
        f"Respuesta inesperada: {r1[:120]}..."

    # verificar que devuelve formato tipo lista de tareas
    assert "-" in r1 or "tarea" in r1.lower()

    q2 = "¿Y cuáles están bloqueadas?"
    r2 = await agent.handle_query(q2)
    lower2 = r2.lower()
    assert any(k in lower2 for k in ["bloquead", "no hay tareas"]), \
        f"Respuesta inesperada: {r2[:120]}..."

    mem = agent.get_memory()
    assert isinstance(mem, list) and len(mem) >= 2
    print(f"🧾 Memoria: {len(mem)} entradas.\n")
