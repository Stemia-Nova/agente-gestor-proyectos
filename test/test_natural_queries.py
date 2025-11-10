#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Valida que el agente entienda preguntas naturales y devuelva respuestas con sentido.
"""

import sys
import asyncio
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
from chatbot import handlers


# =============================================================
# 🧠 Batería de consultas naturales
# =============================================================
NATURAL_QUERIES = [
    ("¿Qué tareas tengo pendientes?", ["pendiente", "curso", "en curso", "progreso"]),
    ("¿Cuántas tareas hay completadas?", ["complet", "finaliz", "done"]),
    ("¿Qué tareas están bloqueadas?", ["bloquead", "ninguna", "no hay"]),
    ("¿Cuáles son las tareas urgentes?", ["urgente", "prioridad", "alta"]),
    ("¿Qué tareas pertenecen al sprint 2?", ["sprint", "2", "proyecto", "folder"]),
    ("¿Qué tareas asignadas tiene Jorge?", ["jorge", "aguadero"]),
]


@pytest.mark.asyncio
async def test_natural_queries_semantics():
    print("\n==============================")
    print("🗣️ TEST DE PREGUNTAS NATURALES")
    print("==============================")

    passed = 0

    for q, expected_keywords in NATURAL_QUERIES:
        print(f"\n🧩 Consulta: {q}")
        response = await handlers.handle_query(q)
        lower = response.lower()

        # Criterios de validación
        has_keyword = any(k in lower for k in expected_keywords)
        not_empty = len(response.strip()) > 20
        not_generic = "no hay suficiente contexto" not in lower

        if has_keyword and not_empty and not_generic:
            print(f"✅ Respuesta coherente: contiene {expected_keywords}")
            passed += 1
        else:
            print(f"⚠️ Respuesta no convincente: {response[:120]}...")

    print(f"\n📊 Resultado: {passed}/{len(NATURAL_QUERIES)} coherentes\n")
    assert passed >= len(NATURAL_QUERIES) - 2  # tolera hasta 2 respuestas ambiguas
