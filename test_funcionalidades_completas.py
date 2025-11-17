#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 TEST COMPLETO - Validación de todas las funcionalidades del chatbot
======================================================================
Prueba todas las correcciones implementadas:
1. Conteo de tareas (sprint + estado + persona)
2. Búsqueda por comentarios (solo activas)
3. Búsqueda por subtareas
4. Búsqueda por tags
5. Búsqueda por dudas
6. Tareas bloqueadas
7. Generación de reportes (texto y PDF)
"""

import sys
import os
sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv()

from utils.hybrid_search import HybridSearch
from datetime import datetime

# Colores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_test(num, description):
    print(f"\n{BLUE}═══════════════════════════════════════════════════════════{RESET}")
    print(f"{BLUE}🧪 TEST {num}: {description}{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════════════════════{RESET}")

def print_result(expected, actual, test_name):
    if expected.lower() in actual.lower():
        print(f"{GREEN}✅ PASS{RESET} - {test_name}")
        print(f"   Esperado: contiene '{expected}'")
        print(f"   Obtenido: {actual[:100]}...")
        return True
    else:
        print(f"{RED}❌ FAIL{RESET} - {test_name}")
        print(f"   Esperado: contiene '{expected}'")
        print(f"   Obtenido: {actual}")
        return False

def main():
    print(f"\n{YELLOW}{'=' * 80}{RESET}")
    print(f"{YELLOW}🚀 INICIANDO BATERÍA COMPLETA DE TESTS{RESET}")
    print(f"{YELLOW}{'=' * 80}{RESET}\n")
    
    # Inicializar HybridSearch
    print("🔧 Inicializando HybridSearch...")
    searcher = HybridSearch(db_path="data/rag/chroma_db")
    print("✅ HybridSearch inicializado correctamente\n")
    
    results = []
    
    # =================================================================
    # TESTS DE CONTEO (LOS MÁS CRÍTICOS)
    # =================================================================
    
    print_test(1, "Conteo total de tareas")
    response = searcher.answer("¿cuántas tareas hay en total?")
    results.append(print_result("24", response, "Total de tareas"))
    
    print_test(2, "Conteo de tareas en Sprint 3")
    response = searcher.answer("¿cuántas tareas hay en el sprint 3?")
    results.append(print_result("8", response, "Tareas en Sprint 3"))
    
    print_test(3, "Conteo de tareas COMPLETADAS en Sprint 3 (CRÍTICO)")
    response = searcher.answer("¿cuántas tareas completadas hay en el sprint 3?")
    results.append(print_result("1", response, "Completadas Sprint 3"))
    
    print_test(4, "Conteo de tareas PENDIENTES en Sprint 3")
    response = searcher.answer("¿cuántas tareas pendientes hay en el sprint 3?")
    results.append(print_result("4", response, "Pendientes Sprint 3"))
    
    print_test(5, "Conteo de tareas de Jorge en total")
    response = searcher.answer("¿cuántas tareas tiene Jorge?")
    results.append(print_result("7", response, "Tareas de Jorge"))
    
    print_test(6, "Conteo de tareas de Jorge en Sprint 3")
    response = searcher.answer("¿cuántas tareas tiene Jorge en el sprint 3?")
    results.append(print_result("5", response, "Jorge en Sprint 3"))
    
    # =================================================================
    # TESTS DE BÚSQUEDA POR ATRIBUTOS ESPECIALES
    # =================================================================
    
    print_test(7, "Búsqueda de tareas bloqueadas")
    response = searcher.answer("¿hay tareas bloqueadas?")
    results.append(print_result("bloqueada", response, "Tareas bloqueadas"))
    
    print_test(8, "Búsqueda de tareas con COMENTARIOS (solo activas)")
    response = searcher.answer("¿hay tareas con comentarios?")
    # Debe encontrar 1 (solo activas, excluye completadas)
    results.append(print_result("1", response, "Tareas con comentarios activas"))
    
    print_test(9, "Búsqueda de tareas con SUBTAREAS")
    response = searcher.answer("¿hay tareas con subtareas?")
    results.append(print_result("3", response, "Tareas con subtareas"))
    
    print_test(10, "Búsqueda de tareas con DUDAS")
    response = searcher.answer("¿hay tareas con dudas?")
    # Verificar que responde correctamente (debería decir que no hay o encontrar 0)
    results.append(print_result("no hay", response, "Tareas con dudas"))
    
    print_test(11, "Búsqueda por TAG 'data'")
    response = searcher.answer("¿hay tareas con la etiqueta data?")
    results.append(print_result("4", response, "Tareas con tag 'data'"))
    
    print_test(12, "Búsqueda por TAG 'bloqueada'")
    response = searcher.answer("¿hay tareas con la etiqueta bloqueada?")
    results.append(print_result("3", response, "Tareas con tag 'bloqueada'"))
    
    # =================================================================
    # TESTS DE BÚSQUEDA SEMÁNTICA
    # =================================================================
    
    print_test(13, "Búsqueda semántica por nombre de tarea")
    response = searcher.answer("¿qué tareas hay sobre RAG?")
    results.append(print_result("RAG", response, "Búsqueda por 'RAG'"))
    
    print_test(14, "Información detallada de tarea específica")
    response = searcher.answer("Dame información sobre la tarea 'Conseguir ChatBot'")
    results.append(print_result("ChatBot", response, "Info tarea 'Conseguir ChatBot'"))
    
    # =================================================================
    # TESTS DE REPORTES
    # =================================================================
    
    print_test(15, "Generación de reporte en TEXTO (Sprint 3)")
    response = searcher.answer("genera informe del sprint 3")
    results.append(print_result("Sprint 3", response, "Reporte texto Sprint 3"))
    
    print_test(16, "Generación de reporte en PDF (Sprint 2)")
    response = searcher.answer("genera informe pdf del sprint 2")
    if "pdf" in response.lower() or "generado" in response.lower():
        print(f"{GREEN}✅ PASS{RESET} - Reporte PDF Sprint 2")
        print(f"   Respuesta: {response}")
        results.append(True)
    else:
        print(f"{RED}❌ FAIL{RESET} - Reporte PDF Sprint 2")
        print(f"   Respuesta: {response}")
        results.append(False)
    
    # =================================================================
    # TESTS DE MÉTRICAS
    # =================================================================
    
    print_test(17, "Métricas de Sprint 2")
    response = searcher.answer("dame las métricas del sprint 2")
    results.append(print_result("completado", response, "Métricas Sprint 2"))
    
    # =================================================================
    # TESTS DE EDGE CASES
    # =================================================================
    
    print_test(18, "Query vacía")
    response = searcher.answer("")
    results.append(print_result("específica", response, "Query vacía"))
    
    print_test(19, "Query muy corta")
    response = searcher.answer("ab")
    results.append(print_result("específica", response, "Query muy corta"))
    
    print_test(20, "Sprint inexistente")
    response = searcher.answer("¿cuántas tareas hay en el sprint 99?")
    # Debe manejar correctamente (0 tareas o mensaje apropiado)
    results.append(True)  # Solo verificamos que no crashea
    print(f"{GREEN}✅ PASS{RESET} - No crashea con sprint inexistente")
    print(f"   Respuesta: {response}")
    
    # =================================================================
    # TESTS DE CONTEO DE ENTIDADES (ENFOQUE HÍBRIDO - LLM)
    # =================================================================
    
    print_test(21, "Conteo de SPRINTS (delegación al LLM)")
    response = searcher.answer("¿cuántos sprints hay?")
    # Debe contar sprints únicos (3), no tareas (24)
    if "3" in response and ("sprint" in response.lower() or "tres" in response.lower()):
        print(f"{GREEN}✅ PASS{RESET} - Conteo de sprints (enfoque híbrido)")
        print(f"   Esperado: 3 sprints")
        print(f"   Obtenido: {response[:150]}...")
        results.append(True)
    elif "24" in response:
        print(f"{RED}❌ FAIL{RESET} - Está contando tareas (24) en vez de sprints")
        print(f"   Obtenido: {response}")
        results.append(False)
    else:
        print(f"{YELLOW}⚠️  PARCIAL{RESET} - Respuesta inesperada (revisar manualmente)")
        print(f"   Obtenido: {response}")
        results.append(False)
    
    # =================================================================
    # RESUMEN FINAL
    # =================================================================
    
    print(f"\n{YELLOW}{'=' * 80}{RESET}")
    print(f"{YELLOW}📊 RESUMEN DE RESULTADOS{RESET}")
    print(f"{YELLOW}{'=' * 80}{RESET}\n")
    
    passed = sum(results)
    total = len(results)
    percentage = (passed / total) * 100
    
    print(f"Tests ejecutados: {total}")
    print(f"Tests pasados: {GREEN}{passed}{RESET}")
    print(f"Tests fallidos: {RED}{total - passed}{RESET}")
    print(f"Porcentaje de éxito: {GREEN if percentage >= 80 else RED}{percentage:.1f}%{RESET}\n")
    
    if percentage == 100:
        print(f"{GREEN}🎉 ¡TODOS LOS TESTS PASARON! Sistema funcionando correctamente.{RESET}")
    elif percentage >= 80:
        print(f"{YELLOW}⚠️  Algunos tests fallaron. Revisar implementación.{RESET}")
    else:
        print(f"{RED}❌ Muchos tests fallaron. Se requieren correcciones importantes.{RESET}")
    
    print(f"\n{YELLOW}{'=' * 80}{RESET}\n")
    
    # Verificar si se generó el PDF
    print(f"{BLUE}📄 VERIFICANDO ARCHIVOS PDF GENERADOS:{RESET}")
    import os
    pdf_files = [f for f in os.listdir("data/logs") if f.endswith(".pdf") and "sprint" in f.lower()]
    if pdf_files:
        print(f"{GREEN}✅ PDFs encontrados:{RESET}")
        for pdf in pdf_files:
            print(f"   • data/logs/{pdf}")
    else:
        print(f"{YELLOW}⚠️  No se encontraron PDFs generados{RESET}")
    
    return percentage >= 80

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
