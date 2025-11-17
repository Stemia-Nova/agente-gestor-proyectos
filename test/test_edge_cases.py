#!/usr/bin/env python3
"""
Batería de pruebas edge-case para validar robustez del sistema RAG
Cubre: consultas ambiguas, casos límite, errores comunes, preguntas complejas
"""
import asyncio
from chatbot.handlers import handle_query

# Colores para output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

async def test_query(num: int, description: str, query: str, delay: int = 2):
    """Ejecuta una prueba con formato bonito"""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{YELLOW}TEST {num}: {description}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")
    print(f"Query: {query}")
    print(f"{BLUE}{'-'*80}{RESET}")
    
    try:
        await asyncio.sleep(delay)  # Rate limit control
        result = await handle_query(query)
        print(f"{GREEN}✓ Respuesta:{RESET}")
        print(result[:600] if len(result) > 600 else result)
        return True
    except Exception as e:
        print(f"{RED}✗ Error: {type(e).__name__}: {str(e)[:200]}{RESET}")
        return False

async def main():
    print(f"{GREEN}{'='*80}")
    print("BATERÍA DE PRUEBAS EDGE-CASE - Sistema RAG")
    print(f"{'='*80}{RESET}\n")
    
    passed = 0
    failed = 0
    
    # ===== CATEGORÍA 1: CONSULTAS DE CONTEO AMBIGUAS =====
    print(f"\n{BLUE}{'#'*80}")
    print("# CATEGORÍA 1: Consultas de Conteo Ambiguas")
    print(f"{'#'*80}{RESET}")
    
    tests = [
        ("Conteo sin especificar estado", 
         "¿Cuántas tareas?"),
        
        ("Conteo con múltiples filtros (persona + estado)",
         "¿Cuántas tareas completadas tiene Jorge?"),
        
        ("Conteo con estado inexistente",
         "¿Cuántas tareas canceladas hay?"),
        
        ("Conteo con nombre parcial",
         "¿Cuántas tiene Jor?"),
        
        ("Conteo negativo (tareas NO completadas)",
         "¿Cuántas tareas no están completadas?"),
    ]
    
    for i, (desc, query) in enumerate(tests, 1):
        if await test_query(i, desc, query):
            passed += 1
        else:
            failed += 1
    
    # ===== CATEGORÍA 2: BÚSQUEDAS CON TÉRMINOS AMBIGUOS =====
    print(f"\n{BLUE}{'#'*80}")
    print("# CATEGORÍA 2: Búsquedas con Términos Ambiguos")
    print(f"{'#'*80}{RESET}")
    
    tests = [
        ("Búsqueda por tema vago",
         "¿Qué tareas hay sobre datos?"),
        
        ("Búsqueda con términos técnicos similares",
         "¿Hay tareas de RAG o embedding?"),
        
        ("Búsqueda con sinónimos",
         "¿Qué tareas están trabadas?"),  # trabadas = bloqueadas
        
        ("Búsqueda con término genérico",
         "¿Qué hay que hacer con el chatbot?"),
        
        ("Búsqueda con contexto temporal vago",
         "¿Qué tareas son urgentes?"),
    ]
    
    for i, (desc, query) in enumerate(tests, 6):
        if await test_query(i, desc, query):
            passed += 1
        else:
            failed += 1
    
    # ===== CATEGORÍA 3: PREGUNTAS COMPLEJAS MULTI-CONDICIÓN =====
    print(f"\n{BLUE}{'#'*80}")
    print("# CATEGORÍA 3: Preguntas Complejas Multi-Condición")
    print(f"{'#'*80}{RESET}")
    
    tests = [
        ("Filtros múltiples (sprint + estado + persona)",
         "¿Qué tareas del Sprint 3 están en progreso y las tiene Jorge?"),
        
        ("Condición negativa compuesta",
         "¿Qué tareas no están completadas ni en revisión?"),
        
        ("Pregunta con comparación implícita",
         "¿Quién tiene más tareas pendientes, Jorge o Laura?"),
        
        ("Pregunta con agregación temporal",
         "¿Cuánto trabajo queda por hacer en el sprint actual?"),
        
        ("Pregunta sobre dependencias",
         "¿Hay tareas bloqueadas con subtareas pendientes?"),
    ]
    
    for i, (desc, query) in enumerate(tests, 11):
        if await test_query(i, desc, query, delay=3):
            passed += 1
        else:
            failed += 1
    
    # ===== CATEGORÍA 4: CASOS LÍMITE DE FORMATO =====
    print(f"\n{BLUE}{'#'*80}")
    print("# CATEGORÍA 4: Casos Límite de Formato")
    print(f"{'#'*80}{RESET}")
    
    tests = [
        ("Pregunta sin signos de interrogación",
         "Dime cuantas tareas completadas hay"),
        
        ("Mayúsculas mezcladas",
         "¿CUÁNTAS TAREAS tiene JORGE?"),
        
        ("Con tildes mal colocadas",
         "¿Cuantas tareas estan en progreso?"),
        
        ("Pregunta muy larga con contexto innecesario",
         "Hola, quería preguntarte si me puedes decir por favor cuántas tareas tenemos completadas hasta el momento, gracias"),
        
        ("Pregunta fragmentada",
         "Jorge... ¿cuántas tareas... que estén completadas?"),
    ]
    
    for i, (desc, query) in enumerate(tests, 16):
        if await test_query(i, desc, query, delay=2):
            passed += 1
        else:
            failed += 1
    
    # ===== CATEGORÍA 5: PREGUNTAS SOBRE INFORMES =====
    print(f"\n{BLUE}{'#'*80}")
    print("# CATEGORÍA 5: Preguntas sobre Informes y Reportes")
    print(f"{'#'*80}{RESET}")
    
    tests = [
        ("Solicitud de informe sin especificar sprint",
         "¿Puedes generar un informe?"),
        
        ("Solicitud de informe de sprint inexistente",
         "Dame el informe del Sprint 99"),
        
        ("Solicitud de informe en PDF",
         "Quiero el informe del Sprint 1 en PDF"),
        
        ("Pregunta sobre progreso general",
         "¿Cómo va el proyecto?"),
        
        ("Pregunta sobre bloqueos críticos",
         "¿Qué me está impidiendo avanzar?"),
    ]
    
    for i, (desc, query) in enumerate(tests, 21):
        if await test_query(i, desc, query, delay=3):
            passed += 1
        else:
            failed += 1
    
    # ===== CATEGORÍA 6: EDGE CASES DE LÓGICA =====
    print(f"\n{BLUE}{'#'*80}")
    print("# CATEGORÍA 6: Edge Cases de Lógica")
    print(f"{'#'*80}{RESET}")
    
    tests = [
        ("Pregunta imposible de responder",
         "¿Cuándo se completará la próxima tarea?"),
        
        ("Pregunta con datos inexistentes",
         "¿Qué tareas tiene Pedro?"),  # Pedro no existe
        
        ("Pregunta sobre comentarios específicos",
         "¿Qué comentarios tiene la tarea de Jorge?"),
        
        ("Pregunta sobre subtareas",
         "¿Cuántas subtareas tiene la tarea bloqueada?"),
        
        ("Pregunta meta sobre el sistema",
         "¿Cuántas tareas tienes indexadas?"),
    ]
    
    for i, (desc, query) in enumerate(tests, 26):
        if await test_query(i, desc, query, delay=2):
            passed += 1
        else:
            failed += 1
    
    # ===== RESUMEN FINAL =====
    print(f"\n{BLUE}{'='*80}")
    print("RESUMEN DE PRUEBAS")
    print(f"{'='*80}{RESET}")
    print(f"{GREEN}✓ Pasadas: {passed}{RESET}")
    print(f"{RED}✗ Fallidas: {failed}{RESET}")
    total = passed + failed
    success_rate = (passed / total * 100) if total > 0 else 0
    print(f"Tasa de éxito: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print(f"\n{GREEN}🎉 EXCELENTE: Sistema muy robusto{RESET}")
    elif success_rate >= 75:
        print(f"\n{YELLOW}⚠️  BUENO: Algunos casos límite por mejorar{RESET}")
    else:
        print(f"\n{RED}❌ REVISAR: Muchos fallos encontrados{RESET}")

if __name__ == "__main__":
    asyncio.run(main())
