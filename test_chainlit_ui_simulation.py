#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🖥️  SIMULADOR DE INTERFAZ CHAINLIT
===================================
Muestra la conversación como aparecería en la UI real de Chainlit,
con formato visual similar a la interfaz web.

Uso:
    python test_chainlit_ui_simulation.py
    python test_chainlit_ui_simulation.py --scenario sprint_review
    python test_chainlit_ui_simulation.py --scenario pm_daily --delay 1
"""

import sys
import os
import asyncio
import time
from datetime import datetime

sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

from dotenv import load_dotenv
load_dotenv()

from chatbot.handlers import handle_query

# Colores y estilos para simular UI de Chainlit
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

# Colores de la UI
BG_USER = "\033[48;5;25m"      # Azul oscuro (mensaje usuario)
BG_BOT = "\033[48;5;236m"       # Gris oscuro (mensaje bot)
BG_HEADER = "\033[48;5;57m"     # Morado (header)
TEXT_USER = "\033[97m"          # Blanco brillante
TEXT_BOT = "\033[97m"           # Blanco brillante
TEXT_TIME = "\033[38;5;245m"    # Gris claro
ICON_USER = "👤"
ICON_BOT = "🤖"

class ChainlitUISimulator:
    """Simula la interfaz visual de Chainlit"""
    
    def __init__(self, delay: float = 0.8):
        self.delay = delay
        self.conversation = []
        
    def clear_screen(self):
        """Limpia la pantalla"""
        os.system('clear' if os.name != 'nt' else 'cls')
        
    def print_header(self):
        """Imprime el header de Chainlit"""
        width = 80
        print(f"\n{BG_HEADER}{' '*width}{RESET}")
        title = "🤖 Agente Gestor de Proyectos - Chainlit"
        padding = (width - len(title)) // 2
        print(f"{BG_HEADER}{' '*padding}{BOLD}{TEXT_USER}{title}{RESET}{BG_HEADER}{' '*(width-padding-len(title))}{RESET}")
        print(f"{BG_HEADER}{' '*width}{RESET}")
        print()
        
    def print_message_user(self, text: str, timestamp: str):
        """Imprime un mensaje del usuario (estilo Chainlit)"""
        print(f"\n{TEXT_TIME}{DIM}{timestamp}{RESET}")
        print(f"{ICON_USER} {BOLD}Tú{RESET}")
        
        # Simular el cuadro de mensaje
        lines = self._wrap_text(text, 70)
        print(f"┌{'─'*72}┐")
        for line in lines:
            print(f"│ {BG_USER}{TEXT_USER} {line:<70} {RESET}│")
        print(f"└{'─'*72}┘")
        
    def print_message_bot(self, text: str, timestamp: str, thinking_time: float):
        """Imprime un mensaje del bot (estilo Chainlit)"""
        # Mostrar indicador de "escribiendo..."
        print(f"\n{TEXT_TIME}{DIM}{timestamp}{RESET}")
        print(f"{ICON_BOT} {BOLD}Agente PM{RESET}")
        print(f"{DIM}⏳ Pensando...{RESET}", end='', flush=True)
        
        # Simular tiempo de pensamiento con puntos animados
        for _ in range(3):
            time.sleep(thinking_time / 4)
            print(".", end='', flush=True)
        print(f" {TEXT_TIME}({thinking_time:.1f}s){RESET}")
        
        # Imprimir respuesta
        lines = self._wrap_text(text, 70)
        print(f"┌{'─'*72}┐")
        for line in lines:
            print(f"│ {BG_BOT}{TEXT_BOT} {line:<70} {RESET}│")
        print(f"└{'─'*72}┘")
        
    def _wrap_text(self, text: str, width: int):
        """Envuelve texto a un ancho específico"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            if current_length + word_length + len(current_line) <= width:
                current_line.append(word)
                current_length += word_length
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
        
        if current_line:
            lines.append(' '.join(current_line))
            
        # Asegurar que hay al menos una línea
        if not lines:
            lines = ['']
            
        return lines
    
    def print_system_message(self, text: str):
        """Imprime un mensaje del sistema"""
        print(f"\n{TEXT_TIME}{DIM}ℹ️  {text}{RESET}")
        
    def print_input_prompt(self):
        """Imprime el prompt de entrada (simulado)"""
        print(f"\n{TEXT_TIME}{DIM}{'─'*80}{RESET}")
        print(f"💬 {DIM}Escribe un mensaje...{RESET}")
        print(f"{TEXT_TIME}{DIM}{'─'*80}{RESET}\n")
        
    async def simulate_conversation(self, scenario: str):
        """Simula una conversación completa con UI de Chainlit"""
        
        scenarios = {
            'basic': {
                'title': 'Consulta Básica con Contexto',
                'messages': [
                    "¿Cuántas tareas hay en total?",
                    "¿Y en el Sprint 3?",
                    "¿Cuántas están completadas?",
                    "¿Hay alguna bloqueada?",
                    "Dame más info"
                ]
            },
            'sprint_review': {
                'title': 'Sprint Review - Análisis Completo',
                'messages': [
                    "¿Cuántos sprints hay en el proyecto?",
                    "Dame métricas del Sprint 2",
                    "¿Y del Sprint 3?",
                    "¿Hay tareas bloqueadas en el Sprint 3?",
                    "Quiero un informe del Sprint 3 en texto"
                ]
            },
            'pm_daily': {
                'title': 'Daily Standup - PM Review',
                'messages': [
                    "¿Cuántas tareas tiene Jorge?",
                    "¿Cuántas en el Sprint 3?",
                    "¿Hay alguna bloqueada?",
                    "Dame más información",
                    "¿Tiene tareas con comentarios?"
                ]
            },
            'search_semantic': {
                'title': 'Búsqueda Semántica Profunda',
                'messages': [
                    "¿Hay tareas sobre base de datos?",
                    "Dame más detalles de esa tarea",
                    "¿Cuántas subtareas tiene?",
                    "¿Hay comentarios?",
                    "¿Está bloqueada?"
                ]
            }
        }
        
        if scenario not in scenarios:
            print(f"❌ Escenario '{scenario}' no existe")
            print(f"Disponibles: {', '.join(scenarios.keys())}")
            return
        
        scenario_data = scenarios[scenario]
        messages = scenario_data['messages']
        
        # Pantalla inicial
        self.clear_screen()
        self.print_header()
        self.print_system_message(f"📋 Escenario: {scenario_data['title']}")
        self.print_system_message(f"🕐 Iniciado: {datetime.now().strftime('%H:%M:%S')}")
        time.sleep(self.delay)
        
        # Simular conversación
        for i, user_msg in enumerate(messages, 1):
            # Mostrar prompt de entrada (simulado)
            await asyncio.sleep(self.delay)
            
            # Usuario escribe mensaje
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.print_message_user(user_msg, timestamp)
            
            # Bot procesa y responde
            await asyncio.sleep(self.delay * 0.5)
            start_time = time.time()
            
            try:
                bot_response = await handle_query(user_msg)
                thinking_time = time.time() - start_time
            except Exception as e:
                bot_response = f"❌ Error: {str(e)}"
                thinking_time = time.time() - start_time
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.print_message_bot(bot_response, timestamp, thinking_time)
            
            # Guardar en historial
            self.conversation.append({
                'user': user_msg,
                'bot': bot_response,
                'time': thinking_time
            })
            
            # Pausa entre mensajes (excepto el último)
            if i < len(messages):
                await asyncio.sleep(self.delay * 1.5)
        
        # Resumen final
        await asyncio.sleep(self.delay)
        self.print_summary()
        
    def print_summary(self):
        """Imprime resumen de la conversación"""
        print(f"\n\n{TEXT_TIME}{DIM}{'='*80}{RESET}")
        print(f"{BOLD}📊 Resumen de Conversación{RESET}")
        print(f"{TEXT_TIME}{DIM}{'='*80}{RESET}\n")
        
        total_time = sum(c['time'] for c in self.conversation)
        avg_time = total_time / len(self.conversation) if self.conversation else 0
        
        print(f"  Mensajes intercambiados: {BOLD}{len(self.conversation) * 2}{RESET} ({len(self.conversation)} turnos)")
        print(f"  Tiempo total:            {BOLD}{total_time:.2f}s{RESET}")
        print(f"  Tiempo promedio:         {BOLD}{avg_time:.2f}s{RESET} por respuesta")
        
        # Queries que usaron contexto
        context_queries = sum(1 for c in self.conversation if any(
            kw in c['user'].lower() 
            for kw in ['más', 'esa', 'ese', 'esta', 'y del', 'y en', 'dame más', 'información']
        ))
        
        print(f"  Uso de contexto:         {BOLD}{context_queries}/{len(self.conversation)}{RESET} queries")
        
        # Respuesta más rápida/lenta
        if self.conversation:
            fastest = min(self.conversation, key=lambda x: x['time'])
            slowest = max(self.conversation, key=lambda x: x['time'])
            
            print(f"\n  ⚡ Más rápida:  {fastest['time']:.2f}s - \"{fastest['user'][:40]}...\"")
            print(f"  🐌 Más lenta:   {slowest['time']:.2f}s - \"{slowest['user'][:40]}...\"")
        
        print(f"\n{TEXT_TIME}{DIM}{'='*80}{RESET}\n")

async def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Simulador visual de la interfaz Chainlit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Escenarios disponibles:
    basic            - Consulta básica con contexto conversacional
    sprint_review    - Sprint review completo con métricas
    pm_daily         - Daily standup de Project Manager
    search_semantic  - Búsqueda semántica profunda

Ejemplos:
    python test_chainlit_ui_simulation.py
    python test_chainlit_ui_simulation.py --scenario sprint_review
    python test_chainlit_ui_simulation.py --scenario pm_daily --delay 0.5
        """
    )
    parser.add_argument('-s', '--scenario', type=str, default='basic',
                       help='Escenario a simular (default: basic)')
    parser.add_argument('-d', '--delay', type=float, default=0.8,
                       help='Delay entre mensajes en segundos (default: 0.8)')
    
    args = parser.parse_args()
    
    # Crear simulador y ejecutar
    simulator = ChainlitUISimulator(delay=args.delay)
    await simulator.simulate_conversation(args.scenario)
    
    print(f"\n{BOLD}✨ Simulación completada{RESET}")
    print(f"{DIM}💡 Para probar en vivo: chainlit run main.py --port 8000{RESET}\n")

if __name__ == "__main__":
    asyncio.run(main())
