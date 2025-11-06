#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de prueba comparativa entre los modos BASIC y PRO del buscador híbrido.
"""

import time
from utils.hybrid_search import HybridSearch

def run_test(mode: str, query: str):
    print(f"\n==============================")
    print(f"🔍 Ejecutando HybridSearch en modo: {mode.upper()}")
    print("==============================")

    start = time.time()
    hs = HybridSearch(mode=mode)

    # 1️⃣ Prueba lexical
    print("\n--- Keyword Search ---")
    lex = hs.keyword_search(query)

    # 2️⃣ Prueba semántica
    print("\n--- Semantic Search ---")
    sem = hs.semantic_search(query)

    # 3️⃣ Re-ranking
    print("\n--- Re-Ranking ---")
    reranked = hs.rerank(query, sem)
    end = time.time()

    print(f"\n🕒 Tiempo total ({mode}): {end - start:.2f} s")
    print(f"📊 Resultados finales (Top 3):")
    for i, r in enumerate(reranked[:3], start=1):
        print(f"{i}. ({r['rerank_score']:.3f}) {r['text'][:120]}...\n")


if __name__ == "__main__":
    QUERY = "tareas bloqueadas o impedidas"
    run_test("basic", QUERY)
    run_test("pro", QUERY)
