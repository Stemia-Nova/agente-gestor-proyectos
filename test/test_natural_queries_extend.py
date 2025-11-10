#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST EXTENDIDO DE PREGUNTAS NATURALES — v3
--------------------------------------------------
Evalúa la comprensión y coherencia del agente gestor de proyectos.
"""

import sys
import asyncio
from pathlib import Path
import re
import pytest
from chatbot import handlers

sys.path.append(str(Path(__file__).resolve().parents[1]))

# =============================================================
# 🔍 Batería ampliada de consultas naturales
# =============================================================
NATURAL_QUERIES = [
    ("¿Qué tareas están bloqueadas ahora mismo?", ["bloquead"]),
    ("¿Hay alguna tarea pendiente?", ["pendient", "curso", "in progress"]),
    ("¿Cuántas tareas hay completadas?", ["complet", "finaliz"]),
    ("¿Cuántas tareas tiene asignadas Laura?", ["laura"]),
    ("¿Qué tareas tiene Jorge en curso?", ["jorge", "curso"]),
    ("¿Cuántos sprint hemos tenido hasta ahora?", ["sprint"]),
    ("¿Qué tareas pertenecen al Sprint 2?", ["sprint", "2"]),
    ("¿Qué tareas son urgentes?", ["urgente", "alta"]),
    ("Muéstrame las tareas sin prioridad", ["sin prioridad", "normal"]),
    ("¿Qué tareas están esperando revisión?", ["revisión", "review"]),
    ("¿Hay alguna tarea asignada pero sin empezar?", ["asignad", "pendient"]),
    ("¿Qué tareas son de Laura pero están bloqueadas?", ["laura", "bloquead"]),
    ("¿Cuántas tareas están en curso en el Sprint 3?", ["curso", "sprint", "3"]),
    ("¿Qué tareas están completadas y a quién se asignaron?", ["complet", "asign"]),
    ("¿Cuáles son las tareas críticas del proyecto?", ["urgente", "alta", "prioridad"]),
    ("¿Qué tareas faltan por terminar?", ["pendient", "curso", "todo"]),
    ("¿Quién tiene más tareas asignadas?", ["jorge", "laura", "asign"]),
    ("¿Cuántas tareas bloqueadas hay por sprint?", ["bloquead", "sprint"]),
    ("¿Qué tareas pertenecen al Sprint actual?", ["sprint"]),
    ("¿Cuántas tareas hay en total en el proyecto?", ["total", "tarea"]),
]

# =============================================================
# 🧩 Funciones auxiliares
# =============================================================
def _has_keywords(text: str, expected_keywords: list[str]) -> bool:
    lower = text.lower()
    return any(k in lower for k in expected_keywords)

def _is_meaningful(text: str) -> bool:
    """Descarta respuestas vacías o genéricas."""
    lower = text.lower()
    if not text.strip():
        return False
    if "no hay suficiente contexto" in lower or "respuesta basada en el contexto" in lower:
        return False
    return len(text.strip()) > 30

# =============================================================
# 🧠 Test principal
# =============================================================
@pytest.mark.asyncio
async def test_natural_queries_extended_v3():
    print("\n==============================")
    print("🧠 TEST AMPLIADO DE PREGUNTAS NATURALES (Gestor de proyectos)")
    print("==============================")

    passed = 0
    for q, expected_keywords in NATURAL_QUERIES:
        print(f"\n🧩 Consulta: {q}")
        response = await handlers.handle_query(q)
        lower = response.lower()

        meaningful = _is_meaningful(response)
        has_keyword = _has_keywords(lower, expected_keywords)

        if meaningful and has_keyword:
            print(f"✅ Respuesta válida ({expected_keywords})")
            passed += 1
        else:
            print(f"⚠️ Respuesta débil o fuera de contexto: {response[:160]}...")

    ratio = passed / len(NATURAL_QUERIES)
    print(f"\n📊 Resultado: {passed}/{len(NATURAL_QUERIES)} ({ratio:.0%}) válidas.\n")
    assert ratio >= 0.7  # al menos 70% deben ser coherentes
