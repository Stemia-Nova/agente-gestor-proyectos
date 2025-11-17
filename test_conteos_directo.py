#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 TEST DIRECTO DE CONTEOS - Sin OpenAI
========================================
Prueba directamente la función _handle_count_question
que no requiere OpenAI y funciona solo con ChromaDB.
"""

import sys
sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

from utils.hybrid_search import HybridSearch

# Colores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_test(num, query, expected):
    print(f"\n{BLUE}═══════════════════════════════════════════════════════════{RESET}")
    print(f"{BLUE}🧪 TEST {num}: {query}{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════════════════════{RESET}")
    return expected

def check_result(expected, actual, test_name):
    if actual and str(expected) in actual:
        print(f"{GREEN}✅ PASS{RESET} - {test_name}")
        print(f"   Respuesta: {actual}")
        return True
    else:
        print(f"{RED}❌ FAIL{RESET} - {test_name}")
        print(f"   Esperado: contiene '{expected}'")
        print(f"   Obtenido: {actual}")
        return False

def main():
    print(f"\n{YELLOW}{'=' * 80}{RESET}")
    print(f"{YELLOW}🚀 TEST DIRECTO DE CONTEOS (Sin OpenAI){RESET}")
    print(f"{YELLOW}{'=' * 80}{RESET}\n")
    
    # Inicializar HybridSearch
    print("🔧 Inicializando HybridSearch...")
    searcher = HybridSearch(db_path="data/rag/chroma_db")
    print("✅ HybridSearch inicializado correctamente\n")
    
    results = []
    
    # TESTS CRÍTICOS DE CONTEO
    tests = [
        ("¿cuántas tareas hay en total?", "24"),
        ("¿cuántas tareas hay en el sprint 3?", "8"),
        ("¿cuántas tareas completadas hay en el sprint 3?", "1"),  # EL MÁS CRÍTICO
        ("¿cuántas tareas pendientes hay en el sprint 3?", "4"),
        ("¿cuántas tareas tiene Jorge?", "7"),
        ("¿cuántas tareas tiene Jorge en el sprint 3?", "5"),
        ("¿cuántas tareas tiene Laura?", "17"),
        ("¿hay tareas bloqueadas?", "bloqueada"),
        ("¿hay tareas con comentarios?", "1"),  # Solo activas
        ("¿hay tareas con subtareas?", "3"),
        ("¿hay tareas con dudas?", "no hay"),  # No existen dudas
        ("¿hay tareas con la etiqueta data?", "4"),
        ("¿hay tareas con la etiqueta bloqueada?", "3"),
    ]
    
    for i, (query, expected) in enumerate(tests, 1):
        expected_val = print_test(i, query, expected)
        
        # Llamar directamente a _handle_count_question
        response = searcher._handle_count_question(query)
        
        if response:
            results.append(check_result(expected_val, response, f"Test {i}"))
        else:
            print(f"{YELLOW}⚠️  SKIP{RESET} - La función retornó None (delegaría al LLM)")
            print(f"   Query: {query}")
            results.append(False)
    
    # RESUMEN
    print(f"\n{YELLOW}{'=' * 80}{RESET}")
    print(f"{YELLOW}📊 RESUMEN DE RESULTADOS{RESET}")
    print(f"{YELLOW}{'=' * 80}{RESET}\n")
    
    passed = sum(results)
    total = len(results)
    percentage = (passed / total) * 100 if total > 0 else 0
    
    print(f"Tests ejecutados: {total}")
    print(f"Tests pasados: {GREEN}{passed}{RESET}")
    print(f"Tests fallidos: {RED}{total - passed}{RESET}")
    print(f"Porcentaje de éxito: {GREEN if percentage >= 80 else RED}{percentage:.1f}%{RESET}\n")
    
    if percentage == 100:
        print(f"{GREEN}🎉 ¡TODOS LOS TESTS PASARON!{RESET}")
    elif percentage >= 80:
        print(f"{YELLOW}⚠️  Algunos tests fallaron.{RESET}")
    else:
        print(f"{RED}❌ Muchos tests fallaron.{RESET}")
    
    print(f"\n{YELLOW}{'=' * 80}{RESET}\n")
    
    return percentage >= 80

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
