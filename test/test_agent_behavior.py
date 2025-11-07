#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batería de pruebas funcionales para el Agente Gestor de Proyectos.

✅ Objetivos:
 - Validar búsquedas híbridas y conteos coherentes.
 - Confirmar que las consultas comunes (estado, sprints, bloqueos)
   se responden correctamente usando HybridSearch + Reranker.
 - Asegurar que los filtros y el registro de sprints funcionan.

Ejecutar con:
    pytest -v test/test_agent_behavior.py
"""

import json
from pathlib import Path
from utils.hybrid_search import HybridSearch


# ================================================================
# CONFIGURACIÓN
# ================================================================

CHROMA_PATH = Path("data/rag/chroma_db")
RESULTS_DIR = Path("data/debug")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ================================================================
# ESCENARIOS DE PRUEBA
# ================================================================

TEST_QUERIES = [
    # 🔹 Estado de tareas
    ("¿Qué tareas están bloqueadas?", ["bloqueada", "blocked"]),
    ("¿Hay alguna tarea con impedimentos?", ["bloqueada", "blocked"]),
    ("¿Qué tareas están en progreso?", ["in_progress", "progreso"]),
    ("¿Cuáles están finalizadas?", ["done", "finalizada", "cerrada"]),
    ("¿Hay tareas sin empezar?", ["to_do", "pendiente", "por hacer"]),
    ("¿Qué tareas están pendientes de revisión?", ["review", "revisión"]),

    # 🔹 Priorización y urgencia
    ("¿Qué tareas son urgentes?", ["urgent", "urgente"]),

    # 🔹 Sprints
    ("¿Cuántas tareas hay en el Sprint 1?", ["Sprint 1"]),
    ("Muéstrame las tareas del Sprint 2", ["Sprint 2"]),
    ("¿Qué hay en el Sprint actual?", ["Sprint 3"]),
    ("¿Qué tareas tiene el Sprint 3?", ["Sprint 3"]),

    # 🔹 Conteo y responsables
    ("¿Qué tareas están completadas o cerradas?", ["done", "finalizada"]),
    ("¿Cuántas tareas tenemos en total?", ["tarea", "task"]),
    ("¿Qué tareas tiene Jorge Aguadero?", ["Jorge", "Aguadero"]),
    ("¿Qué tareas tiene Laura Pérez?", ["Laura", "Pérez"]),
]


# ================================================================
# TEST PRINCIPAL
# ================================================================

def test_hybrid_behavior():
    print("\n==============================")
    print("🔍 BATERÍA DE PRUEBAS DEL AGENTE GESTOR DE PROYECTOS")
    print("==============================\n")

    hs = HybridSearch(chroma_base=CHROMA_PATH)
    coherent_count = 0

    for query, expected_keywords in TEST_QUERIES:
        print(f"\n🧠 Consulta: {query}")
        try:
            results = hs.query(query, k=5, scope="all")
            if not results:
                print("❌ Sin resultados.\n")
                continue

            # Guardar resultados para inspección manual
            with open(RESULTS_DIR / "last_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            # Evaluar coherencia: si contiene palabras esperadas
            joined_texts = " ".join([r["text"].lower() for r in results])
            hits = sum(1 for kw in expected_keywords if kw.lower() in joined_texts)

            if hits > 0:
                coherent_count += 1
                print(f"✅ Resultado coherente: contiene {hits}/{len(expected_keywords)} keywords esperadas {expected_keywords}")
            else:
                print(f"❌ No se encontraron coincidencias esperadas: {expected_keywords}")
                print("   Ejemplo de resultados obtenidos:")
                for r in results[:2]:
                    meta = r.get("metadata", {})
                    print(f" - {meta.get('task_id', '-')}: {meta.get('status', '?')} ({meta.get('sprint', '-')}) — {r.get('text', '')[:80]}...")

        except Exception as e:
            print(f"❌ Error durante la búsqueda: {e}")

    total = len(TEST_QUERIES)
    print("\n==============================")
    print("📊 RESULTADO FINAL DE PRUEBAS")
    print("==============================")
    print(f"✅ {coherent_count}/{total} consultas coherentes ({coherent_count/total*100:.1f}%)\n")

    assert coherent_count >= total * 0.8, "Menos del 80% de consultas coherentes — revisar embeddings o pipeline."
