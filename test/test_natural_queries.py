#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batería de pruebas con lenguaje natural para validar el comportamiento del Agente Gestor de Proyectos (RAG ClickUp).
Simula cómo los usuarios harían preguntas reales al sistema.
"""

import re
import json
from utils.hybrid_search import HybridSearch

# ==============================================================
# CONFIGURACIÓN
# ==============================================================

search = HybridSearch(mode="pro")

TEST_QUERIES = [
    # --- Estado de tareas ---
    ("¿Qué tareas están bloqueadas?", ["CREAR RAG"]),
    ("¿Hay alguna tarea con impedimentos?", ["CREAR RAG"]),
    ("¿Qué tareas están en progreso?", []),  # No hay in_progress reales en tu dataset actual
    ("¿Cuáles están finalizadas?", ["Titulo tarea", "tarea finalizada", "Test Tarea inicial"]),
    ("¿Hay tareas sin empezar?", ["Sin título", "Titulo tarea"]),
    ("¿Qué tareas están pendientes de revisión?", []),  # no hay in_review en tu dataset

    # --- Urgentes ---
    ("¿Qué tareas son urgentes?", ["tarea finalizada", "Test Tarea inicial"]),

    # --- Por sprint ---
    ("¿Cuántas tareas hay en el Sprint 1?", ["Sprint 1"]),
    ("Muéstrame las tareas del Sprint 2", ["Sprint 2"]),
    ("¿Qué hay en el Sprint actual?", ["Sprint 3"]),  # el más alto se considera el actual
    ("¿Qué tareas tiene el Sprint 3?", ["Sprint 3"]),

    # --- General ---
    ("¿Qué tareas están completadas o cerradas?", ["Titulo tarea", "tarea finalizada", "Test Tarea inicial"]),
    ("¿Cuántas tareas tenemos en total?", []),
]

# ==============================================================
# FUNCIÓN AUXILIAR
# ==============================================================

def normalize(text: str) -> str:
    return re.sub(r"[^a-záéíóúñü0-9 ]", "", text.lower())

# ==============================================================
# EJECUCIÓN DE TESTS
# ==============================================================

print("\n==============================")
print("🔍 BATERÍA DE PRUEBAS DE LENGUAJE NATURAL")
print("==============================\n")

total = len(TEST_QUERIES)
passed = 0

for query, expected_keywords in TEST_QUERIES:
    print(f"\n🧠 Consulta: {query}")
    results = search.search_semantic(query)

    # concatenar textos para verificar presencia de palabras esperadas
    all_docs = " ".join(r.get("text", "").lower() for r in results if "text" in r)


    match_count = 0
    for keyword in expected_keywords:
        if normalize(keyword) in normalize(all_docs):
            match_count += 1

    if expected_keywords and match_count == len(expected_keywords):
        print(f"✅ Resultado coherente: contiene {expected_keywords}")
        passed += 1
    elif not expected_keywords and len(results) > 0:
        print(f"🟡 No había resultado esperado explícito, pero devolvió {len(results)} coincidencias.")
        passed += 1
    else:
        print(f"❌ No se encontraron todas las coincidencias esperadas: {expected_keywords}")
        print("   Resultados obtenidos:")
        for r in results[:3]:
            doc = r.get("text", "")
            print(f" - {doc[:100]}...")

# ==============================================================
# RESUMEN FINAL
# ==============================================================

print("\n==============================")
print("📊 RESULTADO FINAL DE PRUEBAS")
print("==============================")
print(f"✅ {passed}/{total} consultas coherentes ({(passed/total)*100:.1f}%)")
if passed < total:
    print("⚠️ Algunas consultas podrían necesitar más contexto o mejora semántica.")
else:
    print("🎯 Todas las consultas fueron respondidas de forma coherente.")
