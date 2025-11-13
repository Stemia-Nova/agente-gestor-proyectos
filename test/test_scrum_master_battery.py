#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_scrum_master_battery.py
-----------------------------
Batería completa de preguntas de Scrum Master para validar
las capacidades del sistema RAG.

Categorías:
- Sprint Planning & Progress
- Bloqueos y Riesgos
- Recursos y Asignaciones
- Dependencias y Subtareas
- Métricas y Reporting
- Priorización
- QA y Review
"""

import asyncio
from utils.hybrid_search import HybridSearch
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

class ScrumMasterTestSuite:
    """Suite de tests para validar respuestas tipo Scrum Master."""
    
    def __init__(self):
        self.hs = HybridSearch(collection_name="clickup_tasks", db_path="data/rag/chroma_db")
        self.results = []
    
    def _print_result(self, category: str, question: str, answer: str):
        """Imprime resultado con formato bonito."""
        console.print(f"\n[bold cyan]📋 Categoría:[/bold cyan] {category}")
        console.print(f"[bold yellow]❓ Pregunta:[/bold yellow] {question}")
        console.print(f"[bold green]💬 Respuesta:[/bold green]")
        console.print(Panel(answer, border_style="green", box=box.ROUNDED))
        
        self.results.append({
            "category": category,
            "question": question,
            "answer": answer
        })
    
    # =========================================================================
    # CATEGORÍA 1: Sprint Planning & Progress
    # =========================================================================
    
    def test_sprint_planning(self):
        """Tests sobre planificación de sprints."""
        console.print("\n[bold magenta]═══════════════════════════════════════════[/bold magenta]")
        console.print("[bold magenta]  📊 CATEGORÍA 1: Sprint Planning & Progress[/bold magenta]")
        console.print("[bold magenta]═══════════════════════════════════════════[/bold magenta]")
        
        questions = [
            "¿Cuántas tareas hay en el Sprint 3?",
            "¿Cuál es el progreso del Sprint 2? ¿Cuántas tareas completadas vs pendientes?",
            "¿Qué tareas están actualmente en progreso en el sprint actual?",
            "Dame un resumen del Sprint 1: tareas completadas y pendientes",
            "¿Cuántas tareas hay en total en el proyecto?",
            "¿Qué sprints tienen más carga de trabajo?",
        ]
        
        for q in questions:
            answer = self.hs.answer(q)
            self._print_result("Sprint Planning & Progress", q, answer)
    
    # =========================================================================
    # CATEGORÍA 2: Bloqueos y Riesgos
    # =========================================================================
    
    def test_blockers_and_risks(self):
        """Tests sobre bloqueos y riesgos."""
        console.print("\n[bold red]═══════════════════════════════════════════[/bold red]")
        console.print("[bold red]  ⚠️ CATEGORÍA 2: Bloqueos y Riesgos[/bold red]")
        console.print("[bold red]═══════════════════════════════════════════[/bold red]")
        
        questions = [
            "¿Hay tareas bloqueadas? ¿Cuáles son?",
            "¿Cuántas tareas bloqueadas hay en total?",
            "¿Qué tareas están bloqueadas en el Sprint 3?",
            "Muéstrame todas las tareas con estado bloqueado",
            "¿Por qué está bloqueada la tarea del ChatBot?",
        ]
        
        for q in questions:
            answer = self.hs.answer(q)
            self._print_result("Bloqueos y Riesgos", q, answer)
    
    # =========================================================================
    # CATEGORÍA 3: Recursos y Asignaciones
    # =========================================================================
    
    def test_resources_and_assignments(self):
        """Tests sobre recursos y asignaciones."""
        console.print("\n[bold blue]═══════════════════════════════════════════[/bold blue]")
        console.print("[bold blue]  👥 CATEGORÍA 3: Recursos y Asignaciones[/bold blue]")
        console.print("[bold blue]═══════════════════════════════════════════[/bold blue]")
        
        questions = [
            "¿Qué tareas están asignadas a usuarios específicos?",
            "¿Cuántas tareas no tienen asignado ningún responsable?",
            "¿Qué personas tienen más carga de trabajo en el Sprint 3?",
            "Muéstrame tareas sin asignar en el sprint actual",
        ]
        
        for q in questions:
            answer = self.hs.answer(q)
            self._print_result("Recursos y Asignaciones", q, answer)
    
    # =========================================================================
    # CATEGORÍA 4: Dependencias y Subtareas
    # =========================================================================
    
    def test_dependencies_and_subtasks(self):
        """Tests sobre dependencias y subtareas."""
        console.print("\n[bold yellow]═══════════════════════════════════════════[/bold yellow]")
        console.print("[bold yellow]  🔗 CATEGORÍA 4: Dependencias y Subtareas[/bold yellow]")
        console.print("[bold yellow]═══════════════════════════════════════════[/bold yellow]")
        
        questions = [
            "¿Qué tareas tienen subtareas?",
            "Dame detalles de la tarea 'Implementación de ChatBot' y sus subtareas",
            "¿Hay tareas con dependencias? ¿Cuáles?",
            "Muéstrame todas las tareas que tienen subtareas pendientes",
            "¿Qué subtareas están completadas vs pendientes?",
        ]
        
        for q in questions:
            answer = self.hs.answer(q)
            self._print_result("Dependencias y Subtareas", q, answer)
    
    # =========================================================================
    # CATEGORÍA 5: Métricas y Reporting
    # =========================================================================
    
    def test_metrics_and_reporting(self):
        """Tests sobre métricas y reporting."""
        console.print("\n[bold green]═══════════════════════════════════════════[/bold green]")
        console.print("[bold green]  📈 CATEGORÍA 5: Métricas y Reporting[/bold green]")
        console.print("[bold green]═══════════════════════════════════════════[/bold green]")
        
        questions = [
            "¿Cuántas tareas están completadas vs en curso?",
            "Dame el porcentaje de completitud del Sprint 3",
            "¿Cuál es la velocidad del equipo? (tareas completadas por sprint)",
            "¿Cuántas tareas se completaron en el Sprint 1 vs Sprint 2?",
            "¿Qué sprint tiene más tareas completadas?",
        ]
        
        for q in questions:
            answer = self.hs.answer(q)
            self._print_result("Métricas y Reporting", q, answer)
    
    # =========================================================================
    # CATEGORÍA 6: Priorización
    # =========================================================================
    
    def test_prioritization(self):
        """Tests sobre priorización."""
        console.print("\n[bold red]═══════════════════════════════════════════[/bold red]")
        console.print("[bold red]  🎯 CATEGORÍA 6: Priorización[/bold red]")
        console.print("[bold red]═══════════════════════════════════════════[/bold red]")
        
        questions = [
            "¿Cuáles son las tareas de alta prioridad en el Sprint 3?",
            "¿Hay tareas urgentes sin completar?",
            "Muéstrame todas las tareas de prioridad alta que están bloqueadas",
            "¿Qué tareas prioritarias están pendientes en el sprint actual?",
            "Dame un ranking de tareas por prioridad en el proyecto",
        ]
        
        for q in questions:
            answer = self.hs.answer(q)
            self._print_result("Priorización", q, answer)
    
    # =========================================================================
    # CATEGORÍA 7: QA y Review
    # =========================================================================
    
    def test_qa_and_review(self):
        """Tests sobre QA y revisión."""
        console.print("\n[bold cyan]═══════════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]  ✅ CATEGORÍA 7: QA y Review[/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════[/bold cyan]")
        
        questions = [
            "¿Cuántas tareas están en QA actualmente?",
            "¿Hay tareas en revisión (review)?",
            "Muéstrame tareas que están en testing",
            "¿Qué tareas están pendientes de aprobación?",
            "Dame el estado de todas las tareas en QA/testing",
        ]
        
        for q in questions:
            answer = self.hs.answer(q)
            self._print_result("QA y Review", q, answer)
    
    # =========================================================================
    # CATEGORÍA 8: Consultas Complejas y Edge Cases
    # =========================================================================
    
    def test_complex_queries(self):
        """Tests de consultas complejas y edge cases."""
        console.print("\n[bold magenta]═══════════════════════════════════════════[/bold magenta]")
        console.print("[bold magenta]  🧩 CATEGORÍA 8: Consultas Complejas[/bold magenta]")
        console.print("[bold magenta]═══════════════════════════════════════════[/bold magenta]")
        
        questions = [
            "¿Qué tareas de alta prioridad están bloqueadas en el Sprint 3?",
            "Dame un resumen completo del sprint actual: progreso, bloqueos, prioridades",
            "¿Hay tareas sin asignar que sean prioritarias y estén bloqueadas?",
            "Compara el progreso del Sprint 1 vs Sprint 2 vs Sprint 3",
            "¿Qué debería priorizar en el daily standup de hoy?",
            "Identifica riesgos: tareas bloqueadas, sin asignar o de alta prioridad sin avance",
        ]
        
        for q in questions:
            answer = self.hs.answer(q)
            self._print_result("Consultas Complejas", q, answer)
    
    # =========================================================================
    # Ejecutar todos los tests
    # =========================================================================
    
    def run_all_tests(self):
        """Ejecuta toda la batería de tests."""
        console.print("\n[bold white on blue]" + "=" * 80 + "[/bold white on blue]")
        console.print("[bold white on blue]  🚀 BATERÍA COMPLETA DE TESTS - SCRUM MASTER  [/bold white on blue]")
        console.print("[bold white on blue]" + "=" * 80 + "[/bold white on blue]")
        
        self.test_sprint_planning()
        self.test_blockers_and_risks()
        self.test_resources_and_assignments()
        self.test_dependencies_and_subtasks()
        self.test_metrics_and_reporting()
        self.test_prioritization()
        self.test_qa_and_review()
        self.test_complex_queries()
        
        self._print_summary()
    
    def _print_summary(self):
        """Imprime resumen de resultados."""
        console.print("\n[bold white on green]" + "=" * 80 + "[/bold white on green]")
        console.print("[bold white on green]  📊 RESUMEN DE RESULTADOS  [/bold white on green]")
        console.print("[bold white on green]" + "=" * 80 + "[/bold white on green]")
        
        table = Table(title="Resumen por Categoría", box=box.ROUNDED)
        table.add_column("Categoría", style="cyan", no_wrap=True)
        table.add_column("Preguntas", style="magenta", justify="center")
        
        categories = {}
        for result in self.results:
            cat = result["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        for cat, count in categories.items():
            table.add_row(cat, str(count))
        
        console.print(table)
        console.print(f"\n[bold green]✅ Total de preguntas probadas: {len(self.results)}[/bold green]")


def main():
    """Función principal."""
    suite = ScrumMasterTestSuite()
    suite.run_all_tests()


if __name__ == "__main__":
    main()
