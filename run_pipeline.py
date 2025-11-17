#!/usr/bin/env python3
"""
Pipeline completo de actualización RAG para ClickUp
Ejecuta todos los pasos desde descarga hasta indexación vectorial
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Colores para output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

ROOT = Path(__file__).resolve().parent

# Definir pasos del pipeline (en orden)
PIPELINE_STEPS = {
    "download": {
        "script": ROOT / "data" / "rag" / "sync" / "get_clickup_tasks.py",
        "desc": "Descarga tareas desde ClickUp API",
        "required": False
    },
    "clean": {
        "script": ROOT / "data" / "rag" / "transform" / "01_clean_clickup_tasks.py",
        "desc": "Normaliza estados y prioridades",
        "required": True
    },
    "markdown": {
        "script": ROOT / "data" / "rag" / "transform" / "02_markdownfy_tasks.py",
        "desc": "Convierte a formato markdown",
        "required": True
    },
    "naturalize": {
        "script": ROOT / "data" / "rag" / "transform" / "03_naturalize_tasks_hybrid.py",
        "desc": "Naturaliza con GPT-4 (con cache)",
        "required": True
    },
    "merge": {
        "script": ROOT / "data" / "rag" / "transform" / "03b_merge_metadata.py",
        "desc": "Combina datos naturalizados con metadata",
        "required": True
    },
    "chunk": {
        "script": ROOT / "data" / "rag" / "transform" / "04_chunk_tasks.py",
        "desc": "Genera chunks para RAG",
        "required": True
    },
    "index": {
        "script": ROOT / "data" / "rag" / "transform" / "05_index_tasks.py",
        "desc": "Indexa en ChromaDB con embeddings",
        "required": True
    }
}

def print_header(text: str):
    """Imprime header formateado"""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{text:^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def run_step(name: str, info: dict, step_num: int, total: int) -> bool:
    """Ejecuta un paso del pipeline"""
    script = info["script"]
    desc = info["desc"]
    
    if not script.exists():
        print(f"{RED}❌ Script no encontrado: {script.relative_to(ROOT)}{RESET}")
        return False
    
    print(f"{YELLOW}[{step_num}/{total}] {name.upper()}: {desc}{RESET}")
    print(f"    📄 {script.relative_to(ROOT)}")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            check=True,
            capture_output=False
        )
        print(f"{GREEN}    ✓ Completado{RESET}\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{RED}    ✗ Error en ejecución (código {e.returncode}){RESET}\n")
        return False
    except KeyboardInterrupt:
        print(f"\n{YELLOW}⚠️  Pipeline interrumpido por usuario{RESET}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline RAG para ClickUp - Actualización completa de la base vectorial"
    )
    parser.add_argument(
        "--all", 
        action="store_true",
        help="Ejecutar pipeline completo (incluyendo descarga de ClickUp)"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Ejecutar sin descargar de ClickUp (usar datos existentes)"
    )
    parser.add_argument(
        "--from-step",
        choices=list(PIPELINE_STEPS.keys()),
        help="Iniciar desde un paso específico"
    )
    
    args = parser.parse_args()
    
    # Determinar qué pasos ejecutar
    if args.all:
        steps_to_run = list(PIPELINE_STEPS.keys())
    elif args.skip_download:
        steps_to_run = [k for k in PIPELINE_STEPS.keys() if k != "download"]
    elif args.from_step:
        # Ejecutar desde el paso especificado en adelante
        start_idx = list(PIPELINE_STEPS.keys()).index(args.from_step)
        steps_to_run = list(PIPELINE_STEPS.keys())[start_idx:]
    else:
        # Por defecto: sin descarga
        steps_to_run = [k for k in PIPELINE_STEPS.keys() if k != "download"]
    
    # Header
    print_header("🚀 PIPELINE RAG - ACTUALIZACIÓN CLICKUP")
    print(f"🐍 Python: {sys.executable}")
    print(f"📁 Directorio: {ROOT}")
    print(f"🕐 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n📋 Pasos a ejecutar: {len(steps_to_run)}")
    for i, step in enumerate(steps_to_run, 1):
        print(f"   {i}. {step}: {PIPELINE_STEPS[step]['desc']}")
    
    input(f"\n{YELLOW}Presiona Enter para continuar o Ctrl+C para cancelar...{RESET}")
    
    # Ejecutar pipeline
    start_time = datetime.now()
    failed_steps = []
    
    for i, step_name in enumerate(steps_to_run, 1):
        step_info = PIPELINE_STEPS[step_name]
        success = run_step(step_name, step_info, i, len(steps_to_run))
        
        if not success:
            failed_steps.append(step_name)
            if step_info["required"]:
                print(f"{RED}❌ Paso requerido falló. Abortando pipeline.{RESET}")
                sys.exit(1)
    
    # Resumen final
    elapsed = (datetime.now() - start_time).total_seconds()
    print_header("✅ PIPELINE COMPLETADO")
    print(f"⏱️  Tiempo total: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"✓ Pasos exitosos: {len(steps_to_run) - len(failed_steps)}/{len(steps_to_run)}")
    
    if failed_steps:
        print(f"\n{YELLOW}⚠️  Pasos con advertencias: {', '.join(failed_steps)}{RESET}")
    
    print(f"\n{GREEN}🎯 Base de datos RAG actualizada en:{RESET}")
    print(f"   {ROOT / 'data' / 'rag' / 'chroma_db'}")
    print(f"\n{BLUE}💡 Siguiente paso:{RESET}")
    print(f"   ./run_dev.sh   # Iniciar chatbot")

if __name__ == "__main__":
    main()
