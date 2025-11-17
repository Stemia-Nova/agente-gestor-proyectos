#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🌐 DEMO AUTOMÁTICO EN CHAINLIT
==============================
Inicia la interfaz web de Chainlit y ejecuta automáticamente
un escenario de conversación.

El usuario verá la interfaz real en http://localhost:8000
y las queries se enviarán automáticamente simulando un usuario.

Uso:
    python demo_chainlit_auto.py
    python demo_chainlit_auto.py --scenario sprint_review
    python demo_chainlit_auto.py --scenario pm_daily --delay 3
"""

import sys
import os
import subprocess
import time
import signal
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Colores
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

SCENARIOS = {
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
    ]
}

class ChainlitAutoDemo:
    def __init__(self, scenario: str = 'basic', delay: float = 3.0):
        self.scenario = scenario
        self.delay = delay
        self.process = None
        self.driver = None
        
    def start_chainlit(self):
        """Inicia el servidor Chainlit"""
        print(f"\n{CYAN}🚀 Iniciando servidor Chainlit...{RESET}")
        
        cmd = [
            sys.executable.replace('python3', 'chainlit'),
            'run', 'main.py',
            '--port', '8000',
            '--headless'
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd='/home/st12/agente-gestor-proyectos/agente-gestor-proyectos'
        )
        
        # Esperar a que el servidor esté listo
        print(f"{YELLOW}⏳ Esperando a que el servidor esté listo...{RESET}")
        time.sleep(8)
        
        print(f"{GREEN}✅ Servidor Chainlit iniciado en http://localhost:8000{RESET}\n")
        
    def setup_browser(self):
        """Configura el navegador Chrome"""
        print(f"{CYAN}🌐 Configurando navegador...{RESET}")
        
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # chrome_options.add_argument('--headless')  # Comentado para ver la UI
        chrome_options.add_argument('--window-size=1200,900')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            print(f"{GREEN}✅ Navegador configurado{RESET}\n")
        except Exception as e:
            print(f"{RED}❌ Error configurando navegador: {e}{RESET}")
            print(f"{YELLOW}💡 Asegúrate de tener Chrome y chromedriver instalados{RESET}")
            raise
    
    def run_demo(self):
        """Ejecuta el demo automático"""
        if self.scenario not in SCENARIOS:
            print(f"{RED}❌ Escenario '{self.scenario}' no existe{RESET}")
            print(f"{YELLOW}Disponibles: {', '.join(SCENARIOS.keys())}{RESET}")
            return
        
        queries = SCENARIOS[self.scenario]
        
        print(f"{BOLD}{'='*70}")
        print(f"🎬 EJECUTANDO DEMO: {self.scenario.upper()}")
        print(f"{'='*70}{RESET}\n")
        
        try:
            # Abrir Chainlit
            self.driver.get('http://localhost:8000')
            time.sleep(3)
            
            print(f"{GREEN}✅ Interfaz Chainlit cargada{RESET}\n")
            
            # Ejecutar queries
            for i, query in enumerate(queries, 1):
                print(f"{CYAN}[{i}/{len(queries)}] Enviando: {query}{RESET}")
                
                # Buscar el input de texto
                try:
                    # Intentar diferentes selectores
                    input_field = None
                    selectors = [
                        "textarea[placeholder*='mensaje']",
                        "textarea",
                        "input[type='text']",
                        ".message-input",
                        "#chat-input"
                    ]
                    
                    for selector in selectors:
                        try:
                            input_field = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            break
                        except TimeoutException:
                            continue
                    
                    if not input_field:
                        print(f"{RED}❌ No se encontró el campo de entrada{RESET}")
                        continue
                    
                    # Escribir query
                    input_field.clear()
                    input_field.send_keys(query)
                    time.sleep(0.5)
                    
                    # Enviar (Enter)
                    input_field.send_keys(Keys.RETURN)
                    
                    print(f"{GREEN}✅ Query enviada{RESET}")
                    
                    # Esperar respuesta
                    print(f"{YELLOW}⏳ Esperando respuesta ({self.delay}s)...{RESET}")
                    time.sleep(self.delay)
                    
                except Exception as e:
                    print(f"{RED}❌ Error: {e}{RESET}")
                    continue
                
                print()
            
            print(f"\n{GREEN}{BOLD}✅ DEMO COMPLETADO{RESET}")
            print(f"\n{CYAN}La interfaz quedará abierta para que explores manualmente.{RESET}")
            print(f"{YELLOW}Presiona Ctrl+C para cerrar cuando termines.{RESET}\n")
            
            # Mantener abierto
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n\n{CYAN}🛑 Cerrando demo...{RESET}")
        except Exception as e:
            print(f"\n{RED}❌ Error durante demo: {e}{RESET}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Limpia recursos"""
        if self.driver:
            self.driver.quit()
        if self.process:
            self.process.terminate()
            self.process.wait()
        print(f"{GREEN}✅ Recursos liberados{RESET}\n")

def check_dependencies():
    """Verifica que las dependencias estén instaladas"""
    try:
        import selenium
        print(f"{GREEN}✅ Selenium instalado{RESET}")
    except ImportError:
        print(f"{RED}❌ Selenium no instalado{RESET}")
        print(f"{YELLOW}Instala con: pip install selenium{RESET}")
        return False
    
    try:
        # Verificar chromedriver
        result = subprocess.run(['chromedriver', '--version'], 
                              capture_output=True, text=True, timeout=2)
        print(f"{GREEN}✅ ChromeDriver disponible: {result.stdout.split()[1]}{RESET}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"{RED}❌ ChromeDriver no encontrado{RESET}")
        print(f"{YELLOW}💡 Opciones de instalación:{RESET}")
        print(f"   - Ubuntu/Debian: sudo apt install chromium-chromedriver")
        print(f"   - O descarga de: https://chromedriver.chromium.org/")
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Demo automático en la interfaz web de Chainlit',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-s', '--scenario', type=str, default='basic',
                       choices=list(SCENARIOS.keys()),
                       help='Escenario a ejecutar')
    parser.add_argument('-d', '--delay', type=float, default=4.0,
                       help='Delay entre queries (segundos)')
    
    args = parser.parse_args()
    
    print(f"\n{BOLD}{'='*70}")
    print(f"🎬 DEMO AUTOMÁTICO DE CHAINLIT")
    print(f"{'='*70}{RESET}\n")
    
    # Verificar dependencias
    if not check_dependencies():
        return
    
    # Ejecutar demo
    demo = ChainlitAutoDemo(scenario=args.scenario, delay=args.delay)
    
    try:
        demo.start_chainlit()
        demo.setup_browser()
        demo.run_demo()
    except KeyboardInterrupt:
        print(f"\n{CYAN}🛑 Demo interrumpido por usuario{RESET}")
        demo.cleanup()
    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        demo.cleanup()

if __name__ == "__main__":
    main()
