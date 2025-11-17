#!/usr/bin/env python3
"""
Test mejorado: Verificar que _handle_count_question responde correctamente.
"""

import sys
sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

from utils.hybrid_search import HybridSearch

# Crear instancia
hs = HybridSearch()

print("=" * 80)
print("🔍 TEST: Función _handle_count_question mejorada")
print("=" * 80)

# Test 1: Total Sprint 3
print("\n1️⃣ Test: ¿cuántas tareas hay en el sprint 3?")
result1 = hs._handle_count_question("¿cuántas tareas hay en el sprint 3?")
print(f"   Respuesta: {result1}")

# Test 2: Completadas Sprint 3 (EL CASO PROBLEMÁTICO)
print("\n2️⃣ Test: ¿cuántas tareas completadas hay en el sprint 3?")
result2 = hs._handle_count_question("¿cuántas tareas completadas hay en el sprint 3?")
print(f"   Respuesta: {result2}")
print(f"   Esperado: Hay 1 tarea...")

# Test 3: Pendientes Sprint 3
print("\n3️⃣ Test: ¿cuántas tareas pendientes hay en el sprint 3?")
result3 = hs._handle_count_question("¿cuántas tareas pendientes hay en el sprint 3?")
print(f"   Respuesta: {result3}")
print(f"   Esperado: Hay 4 tareas...")

# Test 4: Jorge en Sprint 3
print("\n4️⃣ Test: ¿cuántas tareas tiene jorge en el sprint 3?")
result4 = hs._handle_count_question("¿cuántas tareas tiene jorge en el sprint 3?")
print(f"   Respuesta: {result4}")

# Test 5: Completadas Jorge Sprint 3 (FILTRO COMBINADO)
print("\n5️⃣ Test: ¿cuántas tareas completadas tiene jorge en el sprint 3?")
result5 = hs._handle_count_question("¿cuántas tareas completadas tiene jorge en el sprint 3?")
print(f"   Respuesta: {result5}")

print("\n" + "=" * 80)
print("✅ Tests completados")
print("=" * 80)
