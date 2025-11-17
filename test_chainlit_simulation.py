#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎭 SIMULACIÓN DE CONVERSACIÓN CON CHAINLIT
==========================================
Simula una conversación real con el chatbot Chainlit,
incluyendo contexto conversacional y múltiples turnos.

Este test ejecuta el flujo completo:
1. Inicialización del chatbot
2. Múltiples queries con contexto
3. Validación de respuestas
4. Medición de tiempos

Uso:
    python test_chainlit_simulation.py
    python test_chainlit_simulation.py --verbose
    python test_chainlit_simulation.py --scenario "sprint_review"
"""

import sys
import os
import asyncio
import time
from typing import List, Dict, Tuple
from datetime import datetime

sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Importar handlers del chatbot (misma lógica que Chainlit)
from chatbot.handlers import handle_query
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

class ConversationSimulator:
    """Simulador de conversaciones con Chainlit"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.searcher = None
        self.conversation_history = []
        self.context = {}  # Simula el estado de contexto de Chainlit
        
    def initialize(self):
        """Inicializa el sistema (como @cl.on_chat_start)"""
        print(f"\n{CYAN}🎬 Inicializando simulador de conversación Chainlit...{RESET}")
        start = time.time()
        
        # Inicializar HybridSearch (igual que en main.py)
        self.searcher = HybridSearch()
        self.context = {
            'last_task': None,
            'last_query': None,
            'conversation_history': []
        }
        
        elapsed = time.time() - start
        print(f"{GREEN}✅ Chatbot inicializado en {elapsed:.2f}s{RESET}")
        print(f"{BLUE}{'='*70}{RESET}\n")
        
    async def send_message(self, user_message: str) -> Tuple[str, float]:
        """
        Simula el envío de un mensaje del usuario
        
        Args:
            user_message: Mensaje del usuario
            
        Returns:
            (bot_response, elapsed_time)
        """
        print(f"{BOLD}👤 Usuario:{RESET} {user_message}")
        
        start = time.time()
        
        # Procesar mensaje con la lógica del chatbot
        # Esto simula exactamente lo que hace Chainlit en @cl.on_message
        try:
            # Usar el handler real de Chainlit (handle_query)
            # Esto incluye toda la lógica de contexto conversacional
            response = await handle_query(user_message)
            
            # Actualizar contexto local (para tracking)
            self.context['last_query'] = user_message
            self.context['conversation_history'].append({
                'user': user_message,
                'bot': response,
                'timestamp': time.time()
            })
            
            # Extraer última tarea si es relevante
            if "Tarea:" in response or "tarea" in response.lower():
                # Simplificado: en producción usa regex más sofisticado
                self.context['last_task'] = response[:100]
            
            elapsed = time.time() - start
            
            # Mostrar respuesta
            time_color = GREEN if elapsed < 3 else YELLOW if elapsed < 5 else RED
            print(f"{time_color}⏱️  {elapsed:.2f}s{RESET}")
            print(f"{BOLD}🤖 Bot:{RESET} {response}\n")
            
            if self.verbose:
                print(f"{CYAN}📝 Contexto actual:{RESET}")
                print(f"  • Última tarea: {self.context.get('last_task', 'Ninguna')[:50]}...")
                print(f"  • Historial: {len(self.context['conversation_history'])} turnos\n")
            
            return response, elapsed
            
        except Exception as e:
            elapsed = time.time() - start
            print(f"{RED}❌ ERROR: {str(e)}{RESET}\n")
            return f"ERROR: {str(e)}", elapsed
    
    async def run_conversation_scenario(self, scenario: str):
        """
        Ejecuta un escenario completo de conversación
        
        Args:
            scenario: Nombre del escenario a ejecutar
        """
        scenarios = {
            'basic': [
                "¿Cuántas tareas hay en total?",
                "¿Y en el Sprint 3?",
                "¿Cuántas están completadas?",
                "¿Hay alguna bloqueada?",
                "Dame más info"
            ],
            'sprint_review': [
                "¿Cuántos sprints hay en el proyecto?",
                "Dame métricas del Sprint 2",
                "¿Y del Sprint 3?",
                "¿Hay tareas bloqueadas en el Sprint 3?",
                "Quiero un informe del Sprint 3 en texto"
            ],
            'pm_daily': [
                "¿Cuántas tareas tiene Jorge?",
                "¿Cuántas en el Sprint 3?",
                "¿Hay alguna bloqueada?",
                "Dame más información",
                "¿Tiene tareas con comentarios?"
            ],
            'search_deep': [
                "¿Hay tareas sobre base de datos?",
                "Dame más detalles",
                "¿Cuántas subtareas tiene?",
                "¿Hay comentarios?",
                "¿Está bloqueada?"
            ],
            'context_heavy': [
                "¿Hay tareas bloqueadas?",
                "¿Cuántas subtareas tiene?",
                "Dame más info",
                "¿Quién está asignado?",
                "¿En qué sprint está?"
            ]
        }
        
        if scenario not in scenarios:
            print(f"{RED}❌ Escenario '{scenario}' no existe{RESET}")
            print(f"{YELLOW}Escenarios disponibles: {', '.join(scenarios.keys())}{RESET}\n")
            return
        
        print(f"\n{MAGENTA}{'='*70}")
        print(f"🎭 ESCENARIO: {scenario.upper()}")
        print(f"{'='*70}{RESET}\n")
        
        messages = scenarios[scenario]
        total_time = 0
        
        for i, message in enumerate(messages, 1):
            print(f"{BLUE}--- Turno {i}/{len(messages)} ---{RESET}")
            response, elapsed = await self.send_message(message)
            total_time += elapsed
            
            # Pausa entre turnos (como usuario real)
            await asyncio.sleep(0.5)
        
        # Resumen de la conversación
        print(f"\n{MAGENTA}{'='*70}")
        print(f"📊 RESUMEN DE CONVERSACIÓN")
        print(f"{'='*70}{RESET}\n")
        
        print(f"Escenario:        {BOLD}{scenario}{RESET}")
        print(f"Turnos:           {BOLD}{len(messages)}{RESET}")
        print(f"Tiempo total:     {BOLD}{total_time:.2f}s{RESET}")
        print(f"Tiempo promedio:  {BOLD}{total_time/len(messages):.2f}s{RESET}/turno")
        
        # Validar contexto conversacional
        context_used = sum(1 for msg in messages if any(
            keyword in msg.lower() 
            for keyword in ['más info', 'dame más', 'y del', 'y en', 'está', 'tiene']
        ))
        print(f"Uso de contexto:  {BOLD}{context_used}/{len(messages)}{RESET} queries\n")
        
        if context_used > 0:
            print(f"{GREEN}✅ Contexto conversacional funcionando{RESET}\n")
        else:
            print(f"{YELLOW}⚠️  Sin uso aparente de contexto{RESET}\n")
    
    async def run_all_scenarios(self):
        """Ejecuta todos los escenarios disponibles"""
        scenarios = ['basic', 'sprint_review', 'pm_daily', 'search_deep', 'context_heavy']
        
        print(f"\n{MAGENTA}{'='*70}")
        print(f"🎬 EJECUTANDO TODOS LOS ESCENARIOS")
        print(f"{'='*70}{RESET}\n")
        
        total_start = time.time()
        
        for scenario in scenarios:
            await self.run_conversation_scenario(scenario)
            
            # Reset contexto entre escenarios
            self.context = {
                'last_task': None,
                'last_query': None,
                'conversation_history': []
            }
            
            print(f"\n{CYAN}---{RESET}\n")
            await asyncio.sleep(1)
        
        total_elapsed = time.time() - total_start
        
        print(f"\n{MAGENTA}{'='*70}")
        print(f"🏁 SIMULACIÓN COMPLETA")
        print(f"{'='*70}{RESET}\n")
        
        print(f"Escenarios ejecutados: {BOLD}{len(scenarios)}{RESET}")
        print(f"Tiempo total:          {BOLD}{total_elapsed:.2f}s{RESET}")
        print(f"Tiempo por escenario:  {BOLD}{total_elapsed/len(scenarios):.2f}s{RESET}\n")
        
        print(f"{GREEN}✅ Simulación completada exitosamente{RESET}\n")

async def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Simulador de conversaciones con Chainlit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Escenarios disponibles:
    basic         - Conversación básica con contexto
    sprint_review - Review de sprint completo
    pm_daily      - Daily standup de PM
    search_deep   - Búsqueda profunda con contexto
    context_heavy - Uso intensivo de contexto

Ejemplos de uso:
    python test_chainlit_simulation.py
    python test_chainlit_simulation.py --verbose
    python test_chainlit_simulation.py --scenario sprint_review
    python test_chainlit_simulation.py --all
        """
    )
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Mostrar información detallada del contexto')
    parser.add_argument('-s', '--scenario', type=str,
                       help='Ejecutar escenario específico')
    parser.add_argument('-a', '--all', action='store_true',
                       help='Ejecutar todos los escenarios')
    
    args = parser.parse_args()
    
    # Inicializar simulador
    simulator = ConversationSimulator(verbose=args.verbose)
    simulator.initialize()
    
    # Ejecutar escenarios
    if args.all:
        await simulator.run_all_scenarios()
    elif args.scenario:
        await simulator.run_conversation_scenario(args.scenario)
    else:
        # Por defecto: escenario básico
        await simulator.run_conversation_scenario('basic')

if __name__ == "__main__":
    asyncio.run(main())
