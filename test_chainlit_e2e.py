#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎭 TEST AUTOMATIZADO CON INTERFAZ WEB CHAINLIT
==============================================
Test end-to-end que inicia Chainlit, abre el navegador,
y ejecuta automáticamente un escenario de conversación
interactuando con la UI real.

Requiere: playwright
Instalación: pip install playwright && playwright install chromium

Uso:
    python test_chainlit_e2e.py
    python test_chainlit_e2e.py --scenario sprint_review
    python test_chainlit_e2e.py --scenario pm_daily --headless
"""

import sys
import os
import subprocess
import time
import asyncio
import argparse
from datetime import datetime

sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Colores
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"

SCENARIOS = {
    'basic': {
        'title': 'Consulta Básica con Contexto',
        'queries': [
            "¿Cuántas tareas hay en total?",
            "¿Y en el Sprint 3?",
            "¿Cuántas están completadas?",
            "¿Hay alguna bloqueada?",
            "Dame más info"
        ]
    },
    'sprint_review': {
        'title': 'Sprint Review Completo',
        'queries': [
            "¿Cuántos sprints hay en el proyecto?",
            "Dame métricas del Sprint 2",
            "¿Y del Sprint 3?",
            "¿Hay tareas bloqueadas en el Sprint 3?",
            "Quiero un informe del Sprint 3 en texto"
        ]
    },
    'pm_daily': {
        'title': 'Daily Standup PM',
        'queries': [
            "¿Cuántas tareas tiene Jorge?",
            "¿Cuántas en el Sprint 3?",
            "¿Hay alguna bloqueada?",
            "Dame más información",
            "¿Tiene tareas con comentarios?"
        ]
    }
}

class ChainlitE2ETest:
    """Test end-to-end con Playwright"""
    
    def __init__(self, scenario: str = 'basic', headless: bool = False, delay: float = 3.0):
        self.scenario = scenario
        self.headless = headless
        self.delay = delay
        self.process = None
        self.results = []
        
    def start_chainlit_server(self):
        """Inicia el servidor Chainlit"""
        print(f"\n{CYAN}🚀 Iniciando servidor Chainlit...{RESET}")
        
        # Comando para iniciar Chainlit
        cmd = [
            '.venv/bin/chainlit',
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
        print(f"{YELLOW}⏳ Esperando servidor (10s)...{RESET}")
        time.sleep(10)
        
        # Verificar que está corriendo
        if self.process.poll() is None:
            print(f"{GREEN}✅ Servidor Chainlit activo en http://localhost:8000{RESET}\n")
            return True
        else:
            print(f"{RED}❌ Error iniciando servidor{RESET}")
            return False
    
    async def run_test(self):
        """Ejecuta el test con Playwright"""
        if self.scenario not in SCENARIOS:
            print(f"{RED}❌ Escenario '{self.scenario}' no existe{RESET}")
            return
        
        scenario_data = SCENARIOS[self.scenario]
        queries = scenario_data['queries']
        
        print(f"{MAGENTA}{'='*70}")
        print(f"🎬 TEST E2E: {scenario_data['title']}")
        print(f"{'='*70}{RESET}\n")
        
        async with async_playwright() as p:
            # Lanzar navegador
            print(f"{CYAN}🌐 Iniciando navegador Chromium...{RESET}")
            browser = await p.chromium.launch(headless=self.headless)
            
            # Crear contexto y página
            context = await browser.new_context(viewport={'width': 1280, 'height': 900})
            page = await context.new_page()
            
            try:
                # Navegar a Chainlit
                print(f"{CYAN}📍 Navegando a http://localhost:8000{RESET}")
                await page.goto('http://localhost:8000', wait_until='networkidle')
                print(f"{GREEN}✅ Página cargada{RESET}\n")
                
                # Esperar a que cargue completamente
                await asyncio.sleep(3)
                
                # Tomar screenshot inicial
                await page.screenshot(path='data/logs/chainlit_test_inicio.png')
                print(f"{CYAN}📸 Screenshot guardado: data/logs/chainlit_test_inicio.png{RESET}\n")
                
                # Ejecutar queries
                for i, query in enumerate(queries, 1):
                    print(f"{BOLD}{'─'*70}{RESET}")
                    print(f"{CYAN}[{i}/{len(queries)}] 💬 Query: {query}{RESET}")
                    
                    start_time = time.time()
                    
                    try:
                        # Buscar el campo de entrada (múltiples selectores)
                        input_selector = None
                        possible_selectors = [
                            'textarea[placeholder*="mensaje"]',
                            'textarea[placeholder*="Mensaje"]',
                            'textarea',
                            'input[type="text"]',
                            '.message-input textarea',
                            '#chat-input'
                        ]
                        
                        for selector in possible_selectors:
                            try:
                                await page.wait_for_selector(selector, timeout=2000)
                                input_selector = selector
                                break
                            except PlaywrightTimeout:
                                continue
                        
                        if not input_selector:
                            print(f"{RED}❌ No se encontró campo de entrada{RESET}")
                            print(f"{YELLOW}💡 Elementos en página:{RESET}")
                            # Listar elementos para debug
                            textareas = await page.query_selector_all('textarea')
                            inputs = await page.query_selector_all('input')
                            print(f"   Textareas: {len(textareas)}")
                            print(f"   Inputs: {len(inputs)}")
                            continue
                        
                        # Escribir query
                        await page.fill(input_selector, query)
                        print(f"{GREEN}✅ Query escrita{RESET}")
                        await asyncio.sleep(0.5)
                        
                        # Enviar (buscar botón de envío o usar Enter)
                        # Intentar botón primero
                        try:
                            send_button = await page.query_selector('button[type="submit"]')
                            if send_button:
                                await send_button.click()
                            else:
                                # Usar Enter
                                await page.press(input_selector, 'Enter')
                        except:
                            await page.press(input_selector, 'Enter')
                        
                        print(f"{GREEN}✅ Query enviada{RESET}")
                        
                        # Esperar respuesta del bot
                        print(f"{YELLOW}⏳ Esperando respuesta...{RESET}")
                        
                        # Esperar a que aparezca nuevo mensaje (con timeout)
                        try:
                            # Buscar mensajes del bot
                            await page.wait_for_selector('.message', timeout=self.delay * 1000)
                            await asyncio.sleep(self.delay)
                            
                            # Obtener último mensaje
                            messages = await page.query_selector_all('.message')
                            if messages:
                                last_message = messages[-1]
                                response_text = await last_message.inner_text()
                                
                                elapsed = time.time() - start_time
                                
                                print(f"{GREEN}✅ Respuesta recibida ({elapsed:.1f}s){RESET}")
                                print(f"{CYAN}📝 Respuesta:{RESET} {response_text[:150]}...")
                                
                                self.results.append({
                                    'query': query,
                                    'response': response_text,
                                    'time': elapsed,
                                    'success': True
                                })
                            else:
                                print(f"{YELLOW}⚠️  No se detectó respuesta{RESET}")
                                self.results.append({
                                    'query': query,
                                    'response': None,
                                    'time': time.time() - start_time,
                                    'success': False
                                })
                        
                        except PlaywrightTimeout:
                            elapsed = time.time() - start_time
                            print(f"{YELLOW}⚠️  Timeout esperando respuesta ({elapsed:.1f}s){RESET}")
                            self.results.append({
                                'query': query,
                                'response': None,
                                'time': elapsed,
                                'success': False
                            })
                        
                        # Screenshot después de cada query
                        screenshot_path = f'data/logs/chainlit_test_query_{i}.png'
                        await page.screenshot(path=screenshot_path)
                        print(f"{CYAN}📸 Screenshot: {screenshot_path}{RESET}\n")
                        
                    except Exception as e:
                        elapsed = time.time() - start_time
                        print(f"{RED}❌ Error: {str(e)}{RESET}\n")
                        self.results.append({
                            'query': query,
                            'response': None,
                            'time': elapsed,
                            'success': False,
                            'error': str(e)
                        })
                
                # Screenshot final
                await page.screenshot(path='data/logs/chainlit_test_final.png')
                print(f"\n{CYAN}📸 Screenshot final: data/logs/chainlit_test_final.png{RESET}")
                
            finally:
                await browser.close()
        
        # Mostrar resumen
        self.print_summary()
    
    def print_summary(self):
        """Imprime resumen de resultados"""
        print(f"\n{MAGENTA}{'='*70}")
        print(f"📊 RESUMEN DEL TEST E2E")
        print(f"{'='*70}{RESET}\n")
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        failed = total - successful
        
        print(f"Total queries:        {BOLD}{total}{RESET}")
        print(f"Exitosas:            {GREEN}{BOLD}{successful}{RESET}")
        print(f"Fallidas:            {RED if failed > 0 else GREEN}{BOLD}{failed}{RESET}")
        print(f"Tasa de éxito:       {GREEN if failed == 0 else YELLOW}{BOLD}{(successful/total)*100:.1f}%{RESET}")
        
        if successful > 0:
            avg_time = sum(r['time'] for r in self.results if r['success']) / successful
            print(f"Tiempo promedio:     {BOLD}{avg_time:.2f}s{RESET}")
        
        print(f"\n{CYAN}📸 Screenshots guardados en: data/logs/{RESET}")
        print(f"   • chainlit_test_inicio.png")
        for i in range(1, total + 1):
            print(f"   • chainlit_test_query_{i}.png")
        print(f"   • chainlit_test_final.png")
        
        if failed > 0:
            print(f"\n{YELLOW}⚠️  Queries fallidas:{RESET}")
            for r in self.results:
                if not r['success']:
                    print(f"   • {r['query']}")
                    if 'error' in r:
                        print(f"     Error: {r['error']}")
        
        print(f"\n{MAGENTA}{'='*70}{RESET}\n")
        
        if failed == 0:
            print(f"{GREEN}{BOLD}✅ TODOS LOS TESTS PASARON{RESET}\n")
        else:
            print(f"{YELLOW}{BOLD}⚠️  ALGUNOS TESTS FALLARON{RESET}\n")
    
    def cleanup(self):
        """Limpia recursos"""
        if self.process:
            print(f"\n{CYAN}🛑 Deteniendo servidor Chainlit...{RESET}")
            self.process.terminate()
            self.process.wait(timeout=5)
            print(f"{GREEN}✅ Servidor detenido{RESET}\n")

def check_playwright():
    """Verifica si Playwright está instalado"""
    if not PLAYWRIGHT_AVAILABLE:
        print(f"{RED}❌ Playwright no está instalado{RESET}\n")
        print(f"{YELLOW}Instalación:{RESET}")
        print(f"  pip install playwright")
        print(f"  playwright install chromium\n")
        return False
    
    print(f"{GREEN}✅ Playwright disponible{RESET}")
    return True

async def main():
    parser = argparse.ArgumentParser(
        description='Test end-to-end con interfaz web real de Chainlit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Escenarios disponibles:
    basic         - Consulta básica con contexto
    sprint_review - Review completo de sprint
    pm_daily      - Daily standup de PM

Ejemplo:
    python test_chainlit_e2e.py --scenario basic
    python test_chainlit_e2e.py --scenario sprint_review --headless
        """
    )
    parser.add_argument('-s', '--scenario', type=str, default='basic',
                       choices=list(SCENARIOS.keys()),
                       help='Escenario a ejecutar')
    parser.add_argument('--headless', action='store_true',
                       help='Ejecutar navegador sin interfaz visual')
    parser.add_argument('-d', '--delay', type=float, default=5.0,
                       help='Delay para esperar respuestas (segundos)')
    
    args = parser.parse_args()
    
    print(f"\n{BOLD}{'='*70}")
    print(f"🎭 TEST END-TO-END CON CHAINLIT")
    print(f"{'='*70}{RESET}\n")
    
    # Verificar Playwright
    if not check_playwright():
        return
    
    # Crear instancia de test
    test = ChainlitE2ETest(
        scenario=args.scenario,
        headless=args.headless,
        delay=args.delay
    )
    
    try:
        # Iniciar servidor
        if not test.start_chainlit_server():
            return
        
        # Ejecutar test
        await test.run_test()
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}🛑 Test interrumpido por usuario{RESET}")
    except Exception as e:
        print(f"\n{RED}❌ Error durante test: {e}{RESET}")
        import traceback
        traceback.print_exc()
    finally:
        test.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
