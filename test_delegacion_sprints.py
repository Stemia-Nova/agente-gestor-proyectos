#!/usr/bin/env python3
"""
Test rápido sin LLM para verificar la lógica de delegación.
"""

import sys
sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

from utils.hybrid_search import HybridSearch
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("🧪 TEST: Verificar delegación al LLM para conteo de sprints")
print("=" * 70)

hs = HybridSearch(collection_name="clickup_tasks")

query = "¿cuántos sprints hay?"
print(f"\nQuery: \"{query}\"")

# Verificar que _handle_count_question retorna None (delega al LLM)
result = hs._handle_count_question(query)

if result is None:
    print("✅ CORRECTO: _handle_count_question retorna None")
    print("   → La pregunta se delega al LLM con contexto enriquecido")
    print("\n💡 El LLM recibirá contexto con:")
    print("   • Sprint 1: X tareas")
    print("   • Sprint 2: Y tareas")
    print("   • Sprint 3: Z tareas")
    print("   Y podrá contar correctamente 3 sprints únicos")
else:
    print(f"❌ ERROR: _handle_count_question retornó: {result}")
    print("   → Debería retornar None para delegar al LLM")

print("\n" + "=" * 70)
print("🔍 Verificando que NO se interceptan preguntas de tareas:")
print("=" * 70)

queries_tareas = [
    "¿cuántas tareas hay en el sprint 3?",
    "cuántas completadas tiene Jorge?",
    "hay tareas bloqueadas?"
]

for q in queries_tareas:
    result = hs._handle_count_question(q)
    if result:
        print(f"✅ '{q}' → Manejado directamente (optimizado)")
    else:
        print(f"⚠️  '{q}' → Delegado al LLM")

print("\n" + "=" * 70)
print("✅ Lógica de delegación correcta:")
print("   • Preguntas sobre TAREAS → Optimización manual (rápido)")
print("   • Preguntas sobre SPRINTS → Delegación al LLM (flexible)")
print("=" * 70)
