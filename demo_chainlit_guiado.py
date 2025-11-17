#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎬 SCRIPT DE DEMO GUIADO PARA CHAINLIT
======================================
Inicia Chainlit y muestra las queries del escenario
para que las ejecutes manualmente en la interfaz web.

Uso:
    python demo_chainlit_guiado.py
    python demo_chainlit_guiado.py --scenario sprint_review
"""

import subprocess
import time
import sys
import argparse
import signal

# Colores
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

SCENARIOS = {
    'basic': {
        'title': '📋 Consulta Básica con Contexto',
        'queries': [
            "¿Cuántas tareas hay en total?",
            "¿Y en el Sprint 3?",
            "¿Cuántas están completadas?",
            "¿Hay alguna bloqueada?",
            "Dame más info"
        ],
        'description': 'Demuestra el contexto conversacional con queries simples.'
    },
    'sprint_review': {
        'title': '📊 Sprint Review Completo',
        'queries': [
            "¿Cuántos sprints hay en el proyecto?",
            "Dame métricas del Sprint 2",
            "¿Y del Sprint 3?",
            "¿Hay tareas bloqueadas en el Sprint 3?",
            "Quiero un informe del Sprint 3 en texto"
        ],
        'description': 'Review completo de sprint con métricas e informes.'
    },
    'pm_daily': {
        'title': '👥 Daily Standup - PM Review',
        'queries': [
            "¿Cuántas tareas tiene Jorge?",
            "¿Cuántas en el Sprint 3?",
            "¿Hay alguna bloqueada?",
            "Dame más información",
            "¿Tiene tareas con comentarios?"
        ],
        'description': 'Daily standup enfocado en un desarrollador específico.'
    },
    'hybrid_demo': {
        'title': '🔄 Demostración Arquitectura Híbrida',
        'queries': [
            "¿Cuántas tareas hay?",
            "¿Cuántos sprints hay?",
            "¿Cuántas tareas en Sprint 3?",
            "Dame métricas del Sprint 2",
            "¿Hay tareas bloqueadas?",
            "Quiero un informe del Sprint 3"
        ],
        'description': 'Muestra optimización manual vs delegación LLM.'
    }
}

def print_header():
    """Imprime header del script"""
    print(f"\n{MAGENTA}{'='*70}")
    print(f"{BOLD}🎬 DEMO GUIADO DE CHAINLIT{RESET}")
    print(f"{MAGENTA}{'='*70}{RESET}\n")

def print_scenario_info(scenario_name):
    """Imprime información del escenario"""
    scenario = SCENARIOS[scenario_name]
    
    print(f"{BOLD}{scenario['title']}{RESET}")
    print(f"{scenario['description']}\n")
    
    print(f"{CYAN}📝 Queries a ejecutar ({len(scenario['queries'])} pasos):{RESET}\n")
    
    for i, query in enumerate(scenario['queries'], 1):
        print(f"{BOLD}{i}.{RESET} {query}")
    
    print(f"\n{YELLOW}💡 Copia y pega cada query en la interfaz web{RESET}")
    print(f"{YELLOW}   Observa el contexto conversacional en acción{RESET}\n")

def start_chainlit():
    """Inicia servidor Chainlit"""
    print(f"{CYAN}🚀 Iniciando servidor Chainlit...{RESET}")
    print(f"{YELLOW}⏳ Espera 5-10 segundos...{RESET}\n")
    
    process = subprocess.Popen(
        ['.venv/bin/chainlit', 'run', 'main.py', '--port', '8000'],
        cwd='/home/st12/agente-gestor-proyectos/agente-gestor-proyectos',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    time.sleep(8)
    
    print(f"{GREEN}✅ Servidor iniciado{RESET}")
    print(f"{BOLD}🌐 Abre: http://localhost:8000{RESET}\n")
    
    return process

def main():
    parser = argparse.ArgumentParser(
        description='Demo guiado de Chainlit con queries preparadas'
    )
    parser.add_argument('-s', '--scenario', type=str, default='basic',
                       choices=list(SCENARIOS.keys()),
                       help='Escenario a demostrar')
    parser.add_argument('-l', '--list', action='store_true',
                       help='Listar escenarios disponibles')
    
    args = parser.parse_args()
    
    if args.list:
        print(f"\n{BOLD}Escenarios disponibles:{RESET}\n")
        for name, data in SCENARIOS.items():
            print(f"{CYAN}{name:15}{RESET} - {data['title']}")
            print(f"                  {data['description']}")
            print(f"                  {len(data['queries'])} queries\n")
        return
    
    print_header()
    print_scenario_info(args.scenario)
    
    print(f"{MAGENTA}{'─'*70}{RESET}\n")
    input(f"{BOLD}Presiona ENTER para iniciar Chainlit...{RESET}")
    
    process = start_chainlit()
    
    try:
        print(f"{GREEN}{'─'*70}{RESET}")
        print(f"{BOLD}🎯 INSTRUCCIONES:{RESET}")
        print(f"{GREEN}{'─'*70}{RESET}\n")
        
        print(f"1. Abre http://localhost:8000 en tu navegador")
        print(f"2. Copia y pega cada query (en orden)")
        print(f"3. Observa las respuestas y el contexto conversacional")
        print(f"4. Presiona Ctrl+C aquí cuando termines\n")
        
        print(f"{CYAN}📋 QUERIES PARA COPIAR:{RESET}\n")
        
        for i, query in enumerate(SCENARIOS[args.scenario]['queries'], 1):
            print(f"{i}. {query}")
        
        print(f"\n{YELLOW}🛑 Presiona Ctrl+C para detener el servidor{RESET}\n")
        
        # Mantener ejecutándose
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n\n{CYAN}🛑 Deteniendo servidor...{RESET}")
        process.terminate()
        process.wait()
        print(f"{GREEN}✅ Servidor detenido{RESET}\n")

if __name__ == "__main__":
    main()
