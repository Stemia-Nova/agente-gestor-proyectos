#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_mejoras_rag.py
------------------
Script de validación para las mejoras implementadas en el pipeline RAG.
"""

import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()


def test_markdownify_import():
    """Verifica que markdownify esté instalado."""
    console.print("\n[bold cyan]1. Test: Importación de markdownify[/bold cyan]")
    try:
        from markdownify import markdownify as md
        console.print("[green]✅ markdownify instalado correctamente[/green]")
        
        # Test de conversión
        html = "<p>Esta es una <strong>prueba</strong> con <em>formato</em>.</p>"
        markdown = md(html)
        expected = "Esta es una **prueba** con *formato*."
        
        console.print(f"   HTML: {html}")
        console.print(f"   MD:   {markdown.strip()}")
        
        if "**prueba**" in markdown and "*formato*" in markdown:
            console.print("[green]✅ Conversión HTML→MD funciona correctamente[/green]")
            return True
        else:
            console.print("[yellow]⚠️ La conversión no produjo el resultado esperado[/yellow]")
            return False
    except ImportError:
        console.print("[red]❌ markdownify NO está instalado[/red]")
        console.print("[yellow]💡 Instala con: pip install markdownify==0.13.1[/yellow]")
        return False


def test_langchain_markdown_splitter():
    """Verifica que MarkdownHeaderTextSplitter esté disponible."""
    console.print("\n[bold cyan]2. Test: MarkdownHeaderTextSplitter[/bold cyan]")
    try:
        from langchain_text_splitters import MarkdownHeaderTextSplitter
        console.print("[green]✅ MarkdownHeaderTextSplitter importado correctamente[/green]")
        
        # Test de splitting
        text = """### Tarea: Implementar login
**Estado:** In progress
**Prioridad:** High

Esta es la descripción de la tarea con varios detalles importantes.

### Otra Sección
Contenido de otra sección."""
        
        headers_to_split = [("###", "Header 3")]
        splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split)
        chunks = splitter.split_text(text)
        
        console.print(f"   Texto dividido en {len(chunks)} chunks")
        if len(chunks) >= 2:
            console.print("[green]✅ Splitting por encabezados funciona[/green]")
            return True
        else:
            console.print("[yellow]⚠️ El splitting no produjo múltiples chunks[/yellow]")
            return False
    except ImportError as e:
        console.print(f"[red]❌ Error al importar MarkdownHeaderTextSplitter: {e}[/red]")
        return False


def test_formato_task_markdown():
    """Verifica que task_markdown.jsonl tenga el formato correcto."""
    console.print("\n[bold cyan]3. Test: Formato de task_markdown.jsonl[/bold cyan]")
    
    file_path = Path("data/processed/task_markdown.jsonl")
    if not file_path.exists():
        console.print(f"[yellow]⚠️ Archivo no encontrado: {file_path}[/yellow]")
        console.print("[dim]   Ejecuta: python data/rag/transform/02_markdownfy_tasks.py[/dim]")
        return False
    
    try:
        with file_path.open("r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if not first_line:
                console.print("[yellow]⚠️ El archivo está vacío[/yellow]")
                return False
            
            task = json.loads(first_line)
            
            # Verificar estructura
            has_text = "text" in task
            has_metadata = "metadata" in task
            
            if has_text and has_metadata:
                console.print("[green]✅ Estructura correcta: 'text' y 'metadata' presentes[/green]")
                
                # Verificar que text sea Markdown (contiene ###, **)
                text = task.get("text", "")
                is_markdown = ("###" in text or "**" in text)
                
                if is_markdown:
                    console.print("[green]✅ El contenido tiene formato Markdown[/green]")
                else:
                    console.print("[yellow]⚠️ El contenido no parece Markdown[/yellow]")
                
                # Verificar metadatos clave
                metadata = task.get("metadata", {})
                required_fields = ["task_id", "status", "priority", "sprint"]
                missing = [f for f in required_fields if f not in metadata]
                
                if not missing:
                    console.print(f"[green]✅ Metadatos completos: {', '.join(required_fields)}[/green]")
                else:
                    console.print(f"[yellow]⚠️ Metadatos faltantes: {', '.join(missing)}[/yellow]")
                
                # Mostrar ejemplo
                console.print("\n[dim]Ejemplo del primer registro:[/dim]")
                console.print(f"[dim]  text (primeros 100 chars): {text[:100]}...[/dim]")
                console.print(f"[dim]  metadata.task_id: {metadata.get('task_id')}[/dim]")
                console.print(f"[dim]  metadata.status: {metadata.get('status')}[/dim]")
                console.print(f"[dim]  metadata.priority: {metadata.get('priority')}[/dim]")
                
                return True
            else:
                console.print(f"[red]❌ Estructura incorrecta. Tiene: {list(task.keys())}[/red]")
                return False
                
    except json.JSONDecodeError as e:
        console.print(f"[red]❌ Error al parsear JSON: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]❌ Error inesperado: {e}[/red]")
        return False


def test_no_enriquecimiento_chunks():
    """Verifica que los chunks NO tengan texto enriquecido con metadatos."""
    console.print("\n[bold cyan]4. Test: Chunks sin enriquecimiento[/bold cyan]")
    
    file_path = Path("data/processed/task_chunks.jsonl")
    if not file_path.exists():
        console.print(f"[yellow]⚠️ Archivo no encontrado: {file_path}[/yellow]")
        console.print("[dim]   Ejecuta: python data/rag/transform/04_chunk_tasks.py[/dim]")
        return False
    
    try:
        with file_path.open("r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if not first_line:
                console.print("[yellow]⚠️ El archivo está vacío[/yellow]")
                return False
            
            chunk = json.loads(first_line)
            text = chunk.get("text", "")
            
            # Verificar que NO contenga frases de enriquecimiento
            frases_prohibidas = [
                "Tarea asignada a",
                "Estado:",
                "Prioridad:",
                "Sprint:",
                "Proyecto:"
            ]
            
            # Estas frases están OK si vienen del Markdown original (con **Estado:**)
            # Pero no si están como "Estado: in_progress" (texto plano mezclado)
            
            # Buscar patrón de enriquecimiento: "Tarea asignada a X. Estado: Y. Prioridad: Z."
            patron_enriquecido = "Tarea asignada a" in text and ". Estado:" in text and ". Prioridad:" in text
            
            if patron_enriquecido:
                console.print("[red]❌ ENCONTRADO texto enriquecido en chunks[/red]")
                console.print(f"[dim]   Fragmento: {text[:200]}...[/dim]")
                return False
            else:
                console.print("[green]✅ Los chunks NO tienen enriquecimiento de metadatos[/green]")
                console.print(f"[dim]   Fragmento: {text[:150]}...[/dim]")
                return True
                
    except json.JSONDecodeError as e:
        console.print(f"[red]❌ Error al parsear JSON: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]❌ Error inesperado: {e}[/red]")
        return False


def test_field_description_presente():
    """Verifica que task_clean.jsonl incluya el campo 'description'."""
    console.print("\n[bold cyan]5. Test: Campo 'description' en task_clean.jsonl[/bold cyan]")
    
    file_path = Path("data/processed/task_clean.jsonl")
    if not file_path.exists():
        console.print(f"[yellow]⚠️ Archivo no encontrado: {file_path}[/yellow]")
        console.print("[dim]   Ejecuta: python data/rag/transform/01_clean_clickup_tasks.py[/dim]")
        return False
    
    try:
        with file_path.open("r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if not first_line:
                console.print("[yellow]⚠️ El archivo está vacío[/yellow]")
                return False
            
            task = json.loads(first_line)
            
            if "description" in task:
                console.print("[green]✅ Campo 'description' presente[/green]")
                desc = task.get("description", "")
                console.print(f"[dim]   Longitud: {len(desc)} caracteres[/dim]")
                if desc:
                    console.print(f"[dim]   Primeros 100 chars: {desc[:100]}...[/dim]")
                return True
            else:
                console.print("[red]❌ Campo 'description' NO encontrado[/red]")
                console.print(f"[dim]   Campos presentes: {', '.join(task.keys())}[/dim]")
                return False
                
    except json.JSONDecodeError as e:
        console.print(f"[red]❌ Error al parsear JSON: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]❌ Error inesperado: {e}[/red]")
        return False


def main():
    console.print(Panel.fit(
        "[bold white]🧪 Validación de Mejoras del Pipeline RAG[/bold white]\n"
        "[dim]Verifica que todas las mejoras estén correctamente implementadas[/dim]",
        border_style="blue"
    ))
    
    resultados = []
    
    # Ejecutar tests
    resultados.append(("Importación markdownify", test_markdownify_import()))
    resultados.append(("MarkdownHeaderTextSplitter", test_langchain_markdown_splitter()))
    resultados.append(("Formato task_markdown.jsonl", test_formato_task_markdown()))
    resultados.append(("Chunks sin enriquecimiento", test_no_enriquecimiento_chunks()))
    resultados.append(("Campo description presente", test_field_description_presente()))
    
    # Resumen
    console.print("\n" + "="*70)
    console.print("\n[bold cyan]📊 Resumen de Validación[/bold cyan]\n")
    
    passed = sum(1 for _, result in resultados if result)
    total = len(resultados)
    
    for nombre, resultado in resultados:
        icon = "✅" if resultado else "❌"
        color = "green" if resultado else "red"
        console.print(f"  [{color}]{icon} {nombre}[/{color}]")
    
    console.print(f"\n[bold]Tests pasados: {passed}/{total}[/bold]")
    
    if passed == total:
        console.print("\n[bold green]🎉 ¡Todas las mejoras están correctamente implementadas![/bold green]")
    elif passed >= total * 0.7:
        console.print("\n[bold yellow]⚠️ La mayoría de mejoras están implementadas, pero hay algunos pendientes.[/bold yellow]")
    else:
        console.print("\n[bold red]❌ Varias mejoras necesitan atención.[/bold red]")
    
    console.print("\n[dim]💡 Para regenerar el pipeline completo:[/dim]")
    console.print("[dim]   python data/rag/transform/01_clean_clickup_tasks.py[/dim]")
    console.print("[dim]   python data/rag/transform/02_markdownfy_tasks.py[/dim]")
    console.print("[dim]   python data/rag/transform/04_chunk_tasks.py[/dim]")
    console.print("[dim]   python data/rag/transform/05_index_tasks.py --reset[/dim]")


if __name__ == "__main__":
    main()
