#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batería de pruebas para validar el comportamiento del Agente Gestor de Proyectos (RAG ClickUp).
Ejecuta consultas en lenguaje natural y evalúa la coherencia de los resultados
devueltos por el motor HybridSearch (semántico + proximidad + reranker).
"""

import re
import json
from utils.hybrid_search import HybridSearch

# ==============================================================
# CONFIGURACIÓN
# ==============================================================

search = HybridSearch()  # usa configuración por defecto (colección clickup_tasks)

TEST_QUERIES = [
    # --- Estado de tareas ---
    ("¿Qué tareas están bloqueadas?", ["bloqueada", "blocked"]),
    ("¿Hay alguna tarea con impedimentos?", ["bloqueada", "blocked"]),
    ("¿Qué tareas están en progreso?", ["in_progress", "progreso"]),
    ("¿Cuáles están finalizadas?", ["done", "finalizada", "cerrada"]),
    ("¿Hay tareas sin empezar?", ["to_do", "pendiente", "por hacer"]),
    ("¿Qué tareas están pendientes de revisión?", ["review", "revisión"]),

    # --- Urgentes ---
    ("¿Qué tareas son urgentes?", ["urgent", "urgente"]),

    # --- Por sprint ---
    ("¿Cuántas tareas hay en el Sprint 1?", ["Sprint 1"]),
    ("Muéstrame las tareas del Sprint 2", ["Sprint 2"]),
    ("¿Qué hay en el Sprint actual?", ["Sprint 3"]),  # el más alto se considera el actual
    ("¿Qué tareas tiene el Sprint 3?", ["Sprint 3"]),

    # --- Generales ---
    ("¿Qué tareas están completadas o cerradas?", ["done", "finalizada"]),
    ("¿Cuántas tareas tenemos en total?", ["tarea", "task"]),  # solo debe devolver resultados
    ("¿Qué tareas tiene Jorge Aguadero?", ["Jorge", "Aguadero"]),
    ("¿Qué tareas tiene Laura Pérez?", ["Laura", "Pérez"]),
]

# ==============================================================
# FUNCIONES AUXILIARES
# ==============================================================

def normalize(text: str) -> str:
    """Limpia el texto para comparación robusta."""
    return re.sub(r"[^a-záéíóúñü0-9 ]", "", text.lower())

# ==============================================================
# EJECUCIÓN DE TESTS
# ==============================================================

print("\n==============================")
print("🔍 BATERÍA DE PRUEBAS DEL AGENTE GESTOR DE PROYECTOS")
print("==============================\n")

total = len(TEST_QUERIES)
passed = 0

for query, expected_keywords in TEST_QUERIES:
    print(f"\n🧠 Consulta: {query}")
    results = search.query(query)

    if not results:
        print("❌ Sin resultados devueltos.")
        continue

    # Concatenar textos y metadatos para analizar coincidencias
    all_text = " ".join(
        f"{r.get('text','')} {json.dumps(r.get('metadata', {}))}".lower() for r in results
    )

    match_count = 0
    for keyword in expected_keywords:
        if normalize(keyword) in normalize(all_text):
            match_count += 1

    if expected_keywords and match_count > 0:
        print(f"✅ Resultado coherente: contiene {match_count}/{len(expected_keywords)} keywords esperadas {expected_keywords}")
        passed += 1
    elif not expected_keywords and len(results) > 0:
        print(f"🟡 No había keywords esperadas explícitas, pero devolvió {len(results)} resultados.")
        passed += 1
    else:
        print(f"❌ No se encontraron coincidencias esperadas: {expected_keywords}")
        print("   Ejemplo de resultados obtenidos:")
        for r in results[:2]:
            doc = r.get("text", "")
            print(f" - {doc[:120]}...")

# ==============================================================
# RESUMEN FINAL
# ==============================================================

print("\n==============================")
print("📊 RESULTADO FINAL DE PRUEBAS")
print("==============================")
print(f"✅ {passed}/{total} consultas coherentes ({(passed/total)*100:.1f}%)")
if passed < total:
    print("⚠️ Algunas consultas podrían necesitar mejor contexto o tuning semántico.")
else:
    print("🎯 Todas las consultas fueron respondidas de forma coherente.")
