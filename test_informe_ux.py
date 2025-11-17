#!/usr/bin/env python3
"""
Test de generación de informes mejorado.
Valida que por defecto genera PDF con mensaje amigable.
"""

import sys
import os
sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

from dotenv import load_dotenv
load_dotenv()

from utils.hybrid_search import HybridSearch

hs = HybridSearch()

print("=" * 80)
print("🧪 TEST: Generación de informes - UX mejorada")
print("=" * 80)

# Test 1: "quiero un informe del sprint 3" → debe generar PDF + mensaje amigable
print("\n1️⃣ TEST: 'quiero un informe del sprint 3'")
print("-" * 80)
response1 = hs.answer("quiero un informe del sprint 3")
print(response1)

# Verificar que es un mensaje amigable (no el texto completo del informe)
if "📄" in response1 and "PDF" in response1 and len(response1) < 500:
    print("\n✅ PASS: Genera PDF y muestra mensaje amigable")
else:
    print("\n❌ FAIL: No genera mensaje amigable o muestra informe completo")

# Test 2: "informe del sprint 3 en texto" → debe mostrar texto completo
print("\n" + "=" * 80)
print("2️⃣ TEST: 'informe del sprint 3 en texto'")
print("-" * 80)
response2 = hs.answer("informe del sprint 3 en texto")
print(response2[:300] + "...")

# Verificar que es el texto completo del informe
if "INFORME DE SPRINT" in response2 and len(response2) > 1000:
    print("\n✅ PASS: Muestra informe completo en texto")
else:
    print("\n❌ FAIL: No muestra informe completo")

# Test 3: "genera informe pdf del sprint 2" → debe generar PDF explícitamente
print("\n" + "=" * 80)
print("3️⃣ TEST: 'genera informe pdf del sprint 2'")
print("-" * 80)
response3 = hs.answer("genera informe pdf del sprint 2")
print(response3)

# Verificar mensaje amigable
if "📄" in response3 and "Sprint 2" in response3:
    print("\n✅ PASS: Genera PDF con mensaje para Sprint 2")
else:
    print("\n❌ FAIL: No genera mensaje correcto")

print("\n" + "=" * 80)
print("✅ Tests completados")
print("=" * 80)
