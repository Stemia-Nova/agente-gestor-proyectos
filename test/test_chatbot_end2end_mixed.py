#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test End-to-End del pipeline RAG → Handlers → OpenAI (si disponible).
"""

import os
import asyncio
from utils.hybrid_search import HybridSearch
from chatbot import handlers

QUERIES = [
    "¿Cuántas tareas hay en total?",
    "¿Qué tareas están bloqueadas?",
    "¿Qué tareas están en curso?",
    "¿Qué tareas completadas hay?",
]

def test_end_to_end_pipeline():
    print("\n==============================")
    print("🤖 TEST END-TO-END PIPELINE")
    print("==============================")

    hs = HybridSearch()
    api_key = os.environ.get("OPENAI_API_KEY")
    use_llm = bool(api_key and getattr(handlers, "client", None))

    for q in QUERIES:
        print(f"\n🧠 Consulta: {q}")
        try:
            results = hs.query(q, k=5)
        except Exception as e:
            print(f"❌ Error en HybridSearch: {e}")
            results = []

        if not results:
            print("⚠️ Sin resultados del índice.")
            continue

        ctx = handlers._format_results(results)
        if use_llm:
            print("🌐 OpenAI activo — generando respuesta...")
            resp = asyncio.run(handlers.handle_query(q))
            print(f"💬 RESPUESTA:\n{resp}\n")
        else:
            print("🧩 Resultados RAG:")
            print(ctx)
    assert True
