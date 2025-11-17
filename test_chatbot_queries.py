#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 TEST AUTOMATIZADO - Batería de Queries del Chatbot
=====================================================
Ejecuta las 21 queries de la batería de tests directamente
a través de HybridSearch (sin necesidad de UI Chainlit).

Valida:
- Respuestas correctas
- Tiempos de ejecución
- Detección de errores
- Performance general

Uso:
    python test_chatbot_queries.py
    python test_chatbot_queries.py --verbose
    python test_chatbot_queries.py --query "¿cuántas tareas hay?"
"""

import sys
import os
import time
import argparse
from typing import List, Tuple
from datetime import datetime

sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

from utils.hybrid_search import HybridSearch

# Colores ANSI
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"

class ChatbotTester:
    """Tester automático para queries del chatbot"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.searcher = None
        self.results = []
        
    def initialize(self):
        """Inicializa HybridSearch"""
        print(f"\n{CYAN}🔧 Inicializando HybridSearch...{RESET}")
        start = time.time()
        self.searcher = HybridSearch()
        elapsed = time.time() - start
        print(f"{GREEN}✅ Inicializado en {elapsed:.2f}s{RESET}\n")
        
    def test_query(self, num: int, query: str, expected: str, max_time: float = 10.0) -> Tuple[bool, float, str]:
        """
        Ejecuta una query y valida la respuesta
        
        Args:
            num: Número de test
            query: Query a ejecutar
            expected: String esperado en la respuesta (case-insensitive)
            max_time: Tiempo máximo permitido en segundos
            
        Returns:
            (success, elapsed_time, response)
        """
        print(f"{BLUE}{'='*70}{RESET}")
        print(f"{BOLD}🧪 TEST {num}: {query}{RESET}")
        print(f"{BLUE}{'='*70}{RESET}")
        
        # Ejecutar query
        start = time.time()
        try:
            response = self.searcher.answer(query)
            elapsed = time.time() - start
        except Exception as e:
            elapsed = time.time() - start
            print(f"{RED}❌ ERROR: {str(e)}{RESET}")
            return False, elapsed, str(e)
        
        # Validar respuesta
        success = expected.lower() in response.lower()
        
        # Mostrar resultado
        status_icon = "✅" if success else "❌"
        status_color = GREEN if success else RED
        time_color = GREEN if elapsed < max_time else YELLOW if elapsed < max_time * 1.5 else RED
        
        print(f"\n{status_color}{status_icon} {'PASS' if success else 'FAIL'}{RESET}")
        print(f"⏱️  Tiempo: {time_color}{elapsed:.2f}s{RESET} (límite: {max_time}s)")
        print(f"🎯 Esperado: '{expected}'")
        
        if self.verbose or not success:
            print(f"\n{CYAN}📝 Respuesta completa:{RESET}")
            print(f"{response[:500]}{'...' if len(response) > 500 else ''}\n")
        else:
            print(f"📝 Respuesta: {response[:150]}{'...' if len(response) > 150 else ''}\n")
        
        return success, elapsed, response
    
    def run_test_suite(self):
        """Ejecuta la batería completa de tests"""
        
        print(f"\n{MAGENTA}{'='*70}")
        print(f"🚀 BATERÍA DE PRUEBAS DEL CHATBOT")
        print(f"{'='*70}{RESET}\n")
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Verbose: {self.verbose}\n")
        
        # Batería de tests
        tests = [
            # Básicas (conteo simple)
            (1, "¿Cuántas tareas hay en total?", "24", 3.0),
            (2, "¿Cuántas tareas hay en el Sprint 3?", "8", 3.0),
            (3, "¿Cuántas tareas completadas hay en el Sprint 3?", "1", 5.0),
            (4, "¿Cuántas tareas pendientes hay en el Sprint 3?", "4", 5.0),
            (5, "¿Cuántas tareas tiene Jorge?", "7", 3.0),
            (6, "¿Cuántas tareas tiene Jorge en el Sprint 3?", "5", 5.0),
            
            # Búsquedas específicas
            (7, "¿Hay tareas bloqueadas?", "1", 3.0),
            (8, "¿Hay tareas con comentarios?", "1", 3.0),
            (9, "¿Hay tareas con subtareas?", "3", 3.0),
            (10, "¿Hay tareas con dudas?", "0", 3.0),
            (11, "¿Hay tareas con tag data?", "4", 3.0),
            (12, "¿Hay tareas con tag bloqueada?", "3", 3.0),
            
            # Búsqueda semántica
            (13, "dame tareas sobre base de datos", "tarea", 5.0),
            (14, "información sobre la tarea de machine learning", "tarea", 5.0),
            
            # Informes
            (15, "Quiero un informe del Sprint 3 en texto", "Sprint 3", 7.0),
            (16, "Quiero un informe del Sprint 2", "informe", 7.0),
            
            # Métricas
            (17, "Dame métricas del Sprint 2", "87.5%", 5.0),
            
            # Edge cases
            (18, "", "no entiendo", 2.0),
            (19, "a", "no entiendo", 2.0),
            (20, "¿Cuántas tareas hay en el Sprint 99?", "0", 3.0),
            
            # Híbrido (delegación LLM)
            (21, "¿Cuántos sprints hay?", "3", 7.0),
        ]
        
        # Ejecutar tests
        total_time = 0
        for num, query, expected, max_time in tests:
            success, elapsed, response = self.test_query(num, query, expected, max_time)
            total_time += elapsed
            self.results.append({
                'num': num,
                'query': query,
                'expected': expected,
                'success': success,
                'time': elapsed,
                'response': response
            })
            
            # Pequeña pausa entre tests
            time.sleep(0.5)
        
        # Resumen final
        self.print_summary(total_time)
    
    def print_summary(self, total_time: float):
        """Imprime resumen de resultados"""
        
        passed = sum(1 for r in self.results if r['success'])
        failed = len(self.results) - passed
        success_rate = (passed / len(self.results)) * 100
        
        print(f"\n{MAGENTA}{'='*70}")
        print(f"📊 RESUMEN DE RESULTADOS")
        print(f"{'='*70}{RESET}\n")
        
        print(f"Tests ejecutados: {BOLD}{len(self.results)}{RESET}")
        print(f"Tests pasados:    {GREEN}{BOLD}{passed}{RESET}")
        print(f"Tests fallidos:   {RED if failed > 0 else GREEN}{BOLD}{failed}{RESET}")
        print(f"Tasa de éxito:    {GREEN if success_rate == 100 else YELLOW}{BOLD}{success_rate:.1f}%{RESET}")
        print(f"Tiempo total:     {BOLD}{total_time:.2f}s{RESET}")
        print(f"Tiempo promedio:  {BOLD}{total_time/len(self.results):.2f}s{RESET}/query\n")
        
        # Desglose por performance
        print(f"{CYAN}⏱️  Desglose de Tiempos:{RESET}\n")
        
        fast = [r for r in self.results if r['time'] < 3]
        medium = [r for r in self.results if 3 <= r['time'] < 5]
        slow = [r for r in self.results if r['time'] >= 5]
        
        print(f"  Rápidas (<3s):   {GREEN}{len(fast)}{RESET} queries")
        print(f"  Medias (3-5s):   {YELLOW}{len(medium)}{RESET} queries")
        print(f"  Lentas (>5s):    {RED if len(slow) > 5 else YELLOW}{len(slow)}{RESET} queries\n")
        
        # Tests fallidos (si hay)
        if failed > 0:
            print(f"{RED}❌ Tests Fallidos:{RESET}\n")
            for r in self.results:
                if not r['success']:
                    print(f"  • Test {r['num']}: {r['query']}")
                    print(f"    Esperado: '{r['expected']}'")
                    print(f"    Respuesta: {r['response'][:100]}...\n")
        
        # Tests más lentos
        slowest = sorted(self.results, key=lambda x: x['time'], reverse=True)[:3]
        print(f"{YELLOW}🐌 Top 3 Queries Más Lentas:{RESET}\n")
        for i, r in enumerate(slowest, 1):
            print(f"  {i}. Test {r['num']}: {r['time']:.2f}s - {r['query']}")
        
        print(f"\n{MAGENTA}{'='*70}{RESET}")
        
        # Resultado final
        if success_rate == 100:
            print(f"\n{GREEN}{BOLD}🎉 ¡TODOS LOS TESTS PASARON!{RESET}\n")
        elif success_rate >= 90:
            print(f"\n{YELLOW}{BOLD}⚠️  Casi perfecto, revisar tests fallidos{RESET}\n")
        else:
            print(f"\n{RED}{BOLD}❌ Varios tests fallaron, revisar código{RESET}\n")
    
    def test_single_query(self, query: str):
        """Ejecuta una sola query interactiva"""
        print(f"\n{CYAN}🔍 Ejecutando query individual...{RESET}\n")
        
        start = time.time()
        try:
            response = self.searcher.answer(query)
            elapsed = time.time() - start
            
            print(f"{GREEN}✅ Respuesta generada en {elapsed:.2f}s{RESET}\n")
            print(f"{BOLD}Query:{RESET} {query}")
            print(f"\n{BOLD}Respuesta:{RESET}\n{response}\n")
            
        except Exception as e:
            elapsed = time.time() - start
            print(f"{RED}❌ ERROR después de {elapsed:.2f}s:{RESET}")
            print(f"{str(e)}\n")

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Test automatizado de queries del chatbot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
    python test_chatbot_queries.py                    # Batería completa
    python test_chatbot_queries.py --verbose          # Con respuestas completas
    python test_chatbot_queries.py --query "¿cuántas tareas hay?"  # Query individual
        """
    )
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Mostrar respuestas completas')
    parser.add_argument('-q', '--query', type=str,
                       help='Ejecutar una sola query')
    
    args = parser.parse_args()
    
    # Inicializar tester
    tester = ChatbotTester(verbose=args.verbose)
    tester.initialize()
    
    # Ejecutar tests
    if args.query:
        tester.test_single_query(args.query)
    else:
        tester.run_test_suite()

if __name__ == "__main__":
    main()
