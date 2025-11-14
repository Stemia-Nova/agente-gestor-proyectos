#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Descarga automáticamente todas las listas (Sprints) de un Folder de ClickUp
y sus tareas, incluyendo subtareas, generando un JSON y un CSV listos
para la etapa RAG.

Variables de entorno requeridas:
CLICKUP_API_TOKEN=pk_XXXX
CLICKUP_FOLDER_ID=901511269055
"""

import os
import sys
import requests
import traceback
import json
import csv
import time
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from collections.abc import MutableMapping

# =============================================================
# CARGA DE CONFIGURACIÓN CON PYDANTIC
# =============================================================

script_location = Path(__file__).resolve().parent
root_dir = script_location.parent.parent.parent
env_path = root_dir / ".env"

# Agregar utils al path para importar config_models
sys.path.insert(0, str(root_dir))

from utils.config_models import get_config, ClickUpConfig

print(f"🔍 Buscando archivo .env en: {env_path}")
load_dotenv(dotenv_path=env_path)

API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
FOLDER_ID = os.getenv("CLICKUP_FOLDER_ID")

# Cargar configuración validada con Pydantic
_CONFIG: ClickUpConfig = get_config()

if not API_TOKEN or not FOLDER_ID:
    print("❌ Faltan variables CLICKUP_API_TOKEN o CLICKUP_FOLDER_ID en el archivo .env")
    exit(1)

API_TOKEN = API_TOKEN.strip()
headers = {"Authorization": API_TOKEN}

# =============================================================
# FUNCIONES AUXILIARES
# =============================================================

def flatten_json(d: MutableMapping, parent_key: str = '', sep: str = '.') -> dict:
    """Aplana estructuras JSON anidadas (dicts y listas) para exportar a CSV."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_json(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            try:
                items.append((new_key, json.dumps(v, ensure_ascii=False)))
            except Exception:
                items.append((new_key, str(v)))
        else:
            items.append((new_key, v))
    return dict(items)

# =============================================================
# OBTENER TODAS LAS LISTAS (SPRINTS) DEL FOLDER
# =============================================================

print(f"📂 Consultando listas (Sprints) del folder {FOLDER_ID}...")
url_lists = f"https://api.clickup.com/api/v2/folder/{FOLDER_ID}/list"

try:
    response = requests.get(url_lists, headers=headers)
    if response.status_code != 200:
        print(f"❌ Error {response.status_code} al obtener listas: {response.text}")
        exit(1)

    data = response.json()
    lists = data.get("lists", [])
    if not lists:
        print("⚠️ No se encontraron listas en el folder indicado.")
        exit(0)

    print(f"✅ {len(lists)} listas encontradas:")
    for l in lists:
        print(f"   - {l['name']} ({l['id']})")

except requests.exceptions.RequestException as e:
    print(f"❌ Error al consultar listas del folder: {e}")
    print(traceback.format_exc())
    exit(1)

# =============================================================
# FUNCIONES DE ENRIQUECIMIENTO DE TAREAS
# =============================================================

def should_fetch_comments(task: dict) -> bool:
    """
    Determina si una tarea debe tener sus comentarios descargados.
    Criterios (en orden de prioridad):
    1. ClickUp API proporciona comment_count > 0 (más eficiente)
    2. Tiene tags críticas (carga desde data/rag/config/clickup_mappings.json)
    3. Estado bloqueado explícitamente
    
    ✅ Los critical_tags ahora se cargan desde clickup_mappings.json
    Según documentación v2: https://clickup.com/api/clickupreference/operation/GetTasks/
    El campo comment_count debería estar disponible si se incluye en params.
    """
    # Método 1: Usar comment_count si está disponible (más eficiente)
    comment_count = task.get("comment_count", 0)
    if comment_count > 0:
        return True
    
    # Método 2: Verificar tags críticas usando Pydantic helper
    tags = task.get("tags", [])
    if tags:
        tag_names = [tag.get("name", "").lower() for tag in tags]
        
        # ✅ Usar helper de Pydantic para verificar tags
        if _CONFIG.should_download_comments(tag_names):
            return True
    
    # Método 3: Verificar si está bloqueada explícitamente
    # (algunos sistemas marcan bloqueada sin tag)
    if task.get("status", {}).get("status", "").lower() == "blocked":
        return True
    
    return False


def get_task_comments(task_id: str, task_name: str = "", max_comments: int = 50) -> list:
    """Obtiene los comentarios de una tarea específica."""
    url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            comments_data = response.json()
            comments = comments_data.get("comments", [])
            # Limitar a max_comments y extraer info relevante
            return [{
                "id": c.get("id"),
                "comment_text": c.get("comment_text", ""),
                "user": c.get("user", {}).get("username", "unknown"),
                "date": c.get("date"),
                "resolved": c.get("resolved", False)
            } for c in comments[:max_comments]]
        elif response.status_code == 429:
            print(f"      ⚠️ Rate limit alcanzado, esperando...")
            time.sleep(2)
            return []
        return []
    except Exception as e:
        print(f"      ⚠️ Error al obtener comentarios de {task_name[:30]}: {e}")
        return []


def organize_subtasks(all_tasks: list) -> dict:
    """
    Organiza las tareas en una estructura parent-child.
    Retorna un diccionario: parent_id -> [lista de subtareas]
    """
    subtasks_by_parent = {}
    
    for task in all_tasks:
        parent_id = task.get("parent")
        if parent_id:
            if parent_id not in subtasks_by_parent:
                subtasks_by_parent[parent_id] = []
            subtasks_by_parent[parent_id].append({
                "id": task.get("id"),
                "name": task.get("name"),
                "status": task.get("status", {}).get("status"),
                "assignees": [a.get("username") for a in task.get("assignees", [])]
            })
    
    return subtasks_by_parent


# =============================================================
# DESCARGA TODAS LAS TAREAS (Y SUBTAREAS) DE CADA LISTA
# =============================================================

all_tasks = []
tasks_by_id = {}  # Para mapear parent-child relationships

for l in lists:
    lid = l["id"]
    lname = l["name"]
    print(f"\n📡 Descargando tareas (y subtareas) del Sprint '{lname}' (ID: {lid}) ...")

    page = 0
    total_tasks_list = []

    while True:
        # ✅ Añadimos subtasks=true y paginación
        url_tasks = (
            f"https://api.clickup.com/api/v2/list/{lid}/task"
            f"?archived=false&include_closed=true&subtasks=true&page={page}"
        )

        try:
            response = requests.get(url_tasks, headers=headers)
            if response.status_code == 200:
                data = response.json()
                tasks = data.get("tasks", [])

                if not tasks:
                    break  # fin de la paginación

                print(f"   ➕ Página {page + 1}: {len(tasks)} tareas recibidas")
                for t in tasks:
                    t["sprint_name"] = lname
                    t["sprint_id"] = lid
                    tasks_by_id[t["id"]] = t
                total_tasks_list.extend(tasks)
                page += 1
            else:
                print(f"⚠️ Error {response.status_code} al obtener tareas: {response.text}")
                break
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión con la lista {lid}: {e}")
            print(traceback.format_exc())
            break

    print(f"✅ {len(total_tasks_list)} tareas (incluyendo subtareas) encontradas en {lname}.")
    all_tasks.extend(total_tasks_list)

print(f"\n📊 Total de tareas recopiladas (incluyendo subtareas): {len(all_tasks)}")

if not all_tasks:
    print("⚠️ No se encontraron tareas. Fin del proceso.")
    exit(0)

# =============================================================
# ENRIQUECIMIENTO: Organizar subtareas y añadir comentarios
# =============================================================

print(f"\n🔗 Organizando relaciones parent-child...")
subtasks_map = organize_subtasks(all_tasks)
print(f"✅ {len(subtasks_map)} tareas padre con subtareas identificadas")

# Añadir lista de subtareas a cada tarea padre
for task in all_tasks:
    task_id = task.get("id")
    if task_id in subtasks_map:
        task["subtasks"] = subtasks_map[task_id]
        task["has_subtasks"] = True
        task["subtasks_count"] = len(subtasks_map[task_id])
    else:
        task["has_subtasks"] = False
        task["subtasks_count"] = 0

print(f"\n💬 Enriqueciendo tareas relevantes con comentarios...")
tasks_to_enrich = [t for t in all_tasks if should_fetch_comments(t)]
print(f"   📋 {len(tasks_to_enrich)} tareas necesitan comentarios (tienen tags relevantes)")

tasks_with_comments = 0
total_comments = 0

for i, task in enumerate(tasks_to_enrich):
    task_id = task.get("id")
    task_name = task.get("name", "Sin nombre")
    
    # Obtener comentarios solo de tareas relevantes
    comments = get_task_comments(task_id, task_name)
    if comments:
        task["comments"] = comments
        task["has_comments"] = True
        task["comments_count"] = len(comments)
        tasks_with_comments += 1
        total_comments += len(comments)
        print(f"   📝 [{i+1}/{len(tasks_to_enrich)}] {task_name[:40]}: {len(comments)} comentarios")
    else:
        task["has_comments"] = False
        task["comments_count"] = 0
    
    # Rate limiting: pequeña pausa entre requests
    if i > 0 and i % 5 == 0:
        time.sleep(0.5)

# Añadir campos has_comments y comments_count a todas las tareas sin comentarios
for task in all_tasks:
    if "has_comments" not in task:
        task["has_comments"] = False
        task["comments_count"] = 0

print(f"\n✅ {tasks_with_comments} tareas con comentarios ({total_comments} comentarios totales)")

# Añadir info del proyecto/folder para contexto multi-proyecto
print(f"\n📁 Añadiendo contexto de proyecto/folder...")
for task in all_tasks:
    if task.get("folder"):
        task["folder_name"] = task["folder"].get("name")
        task["folder_id"] = task["folder"].get("id")
    if task.get("project"):
        task["project_name"] = task["project"].get("name")
        task["project_id"] = task["project"].get("id")

# =============================================================
# GUARDADO LOCAL (JSON + CSV)
# =============================================================

date_str = datetime.now().strftime("%Y-%m-%d")
output_dir = script_location
output_json = output_dir / f"clickup_tasks_all_{date_str}.json"
output_csv = output_dir / f"clickup_tasks_all_{date_str}.csv"

# Guardar JSON completo
with open(output_json, "w", encoding="utf-8") as f:
    json.dump({"tasks": all_tasks}, f, indent=2, ensure_ascii=False)
print(f"💾 JSON combinado guardado en: {output_json}")

# Aplanar y guardar CSV
print("🧩 Aplanando tareas para exportar a CSV...")
flattened = [flatten_json(task) for task in all_tasks]

if flattened:
    fieldnames = sorted({k for t in flattened for k in t.keys()})
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for task in flattened:
            writer.writerow(task)
    print(f"💾 CSV combinado guardado en: {output_csv}")
else:
    print("⚠️ No se generaron datos aplanados para CSV.")

# Mostrar un ejemplo
print("\n🔍 Ejemplo de tarea descargada:")
if all_tasks:
    sample = all_tasks[0]
    print(json.dumps({
        "id": sample.get("id"),
        "name": sample.get("name"),
        "status": sample.get("status", {}).get("status"),
        "project": sample.get("project", {}).get("name"),
        "list": sample.get("list", {}).get("name"),
        "sprint": sample.get("sprint_name"),
        "parent": sample.get("parent")
    }, indent=2, ensure_ascii=False))

print("\n✅ Proceso completado correctamente.")
