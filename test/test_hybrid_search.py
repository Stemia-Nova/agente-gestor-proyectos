#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
from utils.hybrid_search import HybridSearch

CHROMA_PATH = "data/rag/chroma_db"

def test_hybrid_search_query_and_counts():
    print("\n==============================")
    print("🔍 PRUEBAS HYBRID SEARCH (v2)")
    print("==============================\n")

    hs = HybridSearch(db_path=CHROMA_PATH)

    queries = [
        ("¿Qué tareas están bloqueadas?", "bloquead"),
        ("¿Qué tareas están en progreso?", "progreso"),
        ("¿Cuáles están finalizadas?", "complet"),
        ("¿Qué tareas son urgentes?", "urgente"),
    ]

    passed = 0
    for q, keyword in queries:
        print(f"\n🧠 Consulta: {q}")
        docs, metadata = hs.search(q, top_k=5)
        joined = " ".join(docs).lower()
        if keyword in joined:
            print(f"✅ Coherente con keyword '{keyword}'")
            passed += 1
        else:
            print(f"⚠️ No se encontró la palabra '{keyword}' en resultados")

    # Obtener estadísticas básicas
    total = hs.count_tasks()
    stats_by_status = hs.aggregate_by_field("status")
    print(f"\n📊 Total de tareas: {total}")
    print(f"📊 Por estado: {stats_by_status}")
    print(f"📈 RESULTADO FINAL: {passed}/{len(queries)} coherentes\n")
    assert passed >= 2
