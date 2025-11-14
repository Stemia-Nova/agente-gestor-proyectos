#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ejemplo_busqueda_hibrida.py
---------------------------
Demuestra cómo realizar búsquedas híbridas en ChromaDB
combinando búsqueda semántica con filtros de metadatos.
"""

import chromadb
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()

# =============================================================
# Configuración
# =============================================================
CHROMA_PATH = Path("data/rag/chroma_db")
COLLECTION_NAME = "clickup_tasks"


def conectar_chroma():
    """Conecta a ChromaDB y obtiene la colección."""
    if not CHROMA_PATH.exists():
        console.print("[red]❌ No se encontró la base de datos ChromaDB.[/red]")
        console.print(f"[yellow]💡 Ejecuta primero:[/yellow] python data/rag/transform/05_index_tasks.py")
        return None
    
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        collection = client.get_collection(COLLECTION_NAME)
        console.print(f"[green]✅ Conectado a colección:[/green] {COLLECTION_NAME}")
        console.print(f"[blue]📊 Total de documentos:[/blue] {collection.count()}")
        return collection
    except Exception as e:
        console.print(f"[red]❌ Error al conectar: {e}[/red]")
        return None


def ejemplo_busqueda_semantica(collection):
    """Búsqueda semántica pura (sin filtros)."""
    console.print("\n[bold cyan]🔍 Ejemplo 1: Búsqueda Semántica Pura[/bold cyan]")
    
    query = "¿Cómo implementar autenticación?"
    console.print(f"[yellow]Query:[/yellow] {query}")
    
    results = collection.query(
        query_texts=[query],
        n_results=3
    )
    
    mostrar_resultados(results)


def ejemplo_filtro_metadata(collection):
    """Búsqueda con filtros de metadatos."""
    console.print("\n[bold cyan]🔍 Ejemplo 2: Búsqueda con Filtros de Metadatos[/bold cyan]")
    
    query = "tareas bloqueadas"
    filtro = {
        "$and": [
            {"status": {"$ne": "done"}},
            {"is_blocked": True}
        ]
    }
    
    console.print(f"[yellow]Query:[/yellow] {query}")
    console.print(f"[yellow]Filtros:[/yellow] {filtro}")
    
    results = collection.query(
        query_texts=[query],
        where=filtro,
        n_results=5
    )
    
    mostrar_resultados(results)


def ejemplo_filtro_prioridad_sprint(collection):
    """Búsqueda por prioridad y sprint."""
    console.print("\n[bold cyan]🔍 Ejemplo 3: Tareas Urgentes en Sprint Actual[/bold cyan]")
    
    query = "tareas pendientes"
    filtro = {
        "$and": [
            {"priority": {"$in": ["urgent", "high"]}},
            {"sprint_status": "actual"},
            {"status": {"$in": ["to_do", "in_progress"]}}
        ]
    }
    
    console.print(f"[yellow]Query:[/yellow] {query}")
    console.print(f"[yellow]Filtros:[/yellow] Prioridad alta/urgente + Sprint actual + No finalizadas")
    
    results = collection.query(
        query_texts=[query],
        where=filtro,
        n_results=5
    )
    
    mostrar_resultados(results)


def ejemplo_filtro_asignado(collection):
    """Búsqueda por asignado."""
    console.print("\n[bold cyan]🔍 Ejemplo 4: Tareas Asignadas a Usuario Específico[/bold cyan]")
    
    # Primero, obtener todos los asignados únicos
    all_docs = collection.get()
    assignees_set = set()
    for meta in all_docs.get('metadatas', []):
        asignados = meta.get('assignees', '')
        if asignados and asignados != 'Sin asignar':
            assignees_set.add(asignados)
    
    if not assignees_set:
        console.print("[yellow]⚠️ No hay tareas con asignados específicos en el dataset.[/yellow]")
        return
    
    # Usar el primer asignado encontrado como ejemplo
    asignado_ejemplo = list(assignees_set)[0]
    
    query = "tareas en progreso"
    filtro = {
        "$and": [
            {"assignees": asignado_ejemplo},
            {"status": "in_progress"}
        ]
    }
    
    console.print(f"[yellow]Query:[/yellow] {query}")
    console.print(f"[yellow]Filtros:[/yellow] Asignado a '{asignado_ejemplo}' + En progreso")
    
    results = collection.query(
        query_texts=[query],
        where=filtro,
        n_results=5
    )
    
    mostrar_resultados(results)


def mostrar_resultados(results):
    """Muestra los resultados en una tabla formateada."""
    documentos = results.get('documents', [[]])[0]
    metadatas = results.get('metadatas', [[]])[0]
    distancias = results.get('distances', [[]])[0]
    
    if not documentos:
        console.print("[yellow]⚠️ No se encontraron resultados.[/yellow]")
        return
    
    table = Table(title="Resultados")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Nombre", style="magenta")
    table.add_column("Estado", style="green")
    table.add_column("Prioridad", style="yellow")
    table.add_column("Sprint", style="blue")
    table.add_column("Distancia", style="red")
    
    for doc, meta, dist in zip(documentos[:5], metadatas[:5], distancias[:5]):
        table.add_row(
            meta.get('task_id', 'N/A')[:10],
            meta.get('name', 'Sin nombre')[:40],
            meta.get('status', 'unknown'),
            meta.get('priority', 'unknown'),
            meta.get('sprint', 'Sin sprint')[:20],
            f"{dist:.3f}"
        )
    
    console.print(table)
    
    # Mostrar primer resultado completo
    console.print("\n[bold]📄 Contenido del primer resultado:[/bold]")
    console.print(f"[dim]{documentos[0][:300]}...[/dim]")


def estadisticas_coleccion(collection):
    """Muestra estadísticas de la colección."""
    console.print("\n[bold cyan]📊 Estadísticas de la Colección[/bold cyan]")
    
    all_docs = collection.get()
    metadatas = all_docs.get('metadatas', [])
    
    if not metadatas:
        console.print("[yellow]⚠️ La colección está vacía.[/yellow]")
        return
    
    # Contar por estado
    estados = {}
    prioridades = {}
    sprints = {}
    
    for meta in metadatas:
        status = meta.get('status', 'unknown')
        priority = meta.get('priority', 'unknown')
        sprint = meta.get('sprint', 'Sin sprint')
        
        estados[status] = estados.get(status, 0) + 1
        prioridades[priority] = prioridades.get(priority, 0) + 1
        sprints[sprint] = sprints.get(sprint, 0) + 1
    
    console.print(f"\n[bold]Estados:[/bold]")
    for estado, count in sorted(estados.items(), key=lambda x: -x[1]):
        console.print(f"  • {estado}: {count}")
    
    console.print(f"\n[bold]Prioridades:[/bold]")
    for prioridad, count in sorted(prioridades.items(), key=lambda x: -x[1]):
        console.print(f"  • {prioridad}: {count}")
    
    console.print(f"\n[bold]Top 5 Sprints:[/bold]")
    for sprint, count in sorted(sprints.items(), key=lambda x: -x[1])[:5]:
        console.print(f"  • {sprint}: {count}")


def main():
    console.print("[bold blue]🚀 Ejemplos de Búsqueda Híbrida con ChromaDB[/bold blue]\n")
    
    collection = conectar_chroma()
    if not collection:
        return
    
    # Mostrar estadísticas
    estadisticas_coleccion(collection)
    
    # Ejemplos de búsqueda
    try:
        ejemplo_busqueda_semantica(collection)
        ejemplo_filtro_metadata(collection)
        ejemplo_filtro_prioridad_sprint(collection)
        ejemplo_filtro_asignado(collection)
    except Exception as e:
        console.print(f"\n[red]❌ Error durante las búsquedas: {e}[/red]")
    
    console.print("\n[green]✅ Ejemplos completados.[/green]")
    console.print("\n[dim]💡 Tip: Modifica las queries y filtros en el código para experimentar.[/dim]")


if __name__ == "__main__":
    main()
