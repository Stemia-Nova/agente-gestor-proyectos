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
import requests
import traceback
import json
import csv
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from collections.abc import MutableMapping

# =============================================================
# CARGA DE CONFIGURACIÓN
# =============================================================

script_location = Path(__file__).resolve().parent
root_dir = script_location.parent.parent.parent
env_path = root_dir / ".env"

print(f"🔍 Buscando archivo .env en: {env_path}")
load_dotenv(dotenv_path=env_path)

API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
FOLDER_ID = os.getenv("CLICKUP_FOLDER_ID")

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
# DESCARGA TODAS LAS TAREAS (Y SUBTAREAS) DE CADA LISTA
# =============================================================

all_tasks = []

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
