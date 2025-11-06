import os
import requests
import traceback
import json
import csv
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from collections.abc import MutableMapping

# --- Carga de .env robusta ---
script_location = Path(__file__).resolve().parent
root_dir = script_location.parent
env_path = root_dir / ".env"

print(f"Buscando el archivo .env en: {env_path}")
load_dotenv(dotenv_path=env_path)

# --- Configuración ---
API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
CLICKUP_LIST_ID = os.getenv("CLICKUP_LIST_ID")

if not API_TOKEN or not CLICKUP_LIST_ID:
    print("❌ Faltan variables CLICKUP_API_TOKEN o CLICKUP_LIST_ID en el archivo .env")
    exit(1)

API_TOKEN = API_TOKEN.strip()

# --- Función para aplanar JSON anidado ---
def flatten_json(d: MutableMapping, parent_key: str = '', sep: str = '.') -> dict:
    """Aplana estructuras JSON anidadas (dicts y listas) para exportar a CSV."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_json(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convertir listas a texto JSON
            try:
                items.append((new_key, json.dumps(v, ensure_ascii=False)))
            except Exception:
                items.append((new_key, str(v)))
        else:
            items.append((new_key, v))
    return dict(items)

# --- Llamada a la API ---
url = f"https://api.clickup.com/api/v2/list/{CLICKUP_LIST_ID}/task"
headers = {"Authorization": API_TOKEN}

print(f"📡 Consultando tareas de la lista ID: {CLICKUP_LIST_ID}...")

try:
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("✅ Conexión exitosa (200)")
        data = response.json()
        tasks = data.get("tasks", [])
        print(f"Se encontraron {len(tasks)} tareas.")

        # --- Preparar nombres de archivo con fecha ---
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_json = script_location / f"clickup_tasks_{CLICKUP_LIST_ID}_{date_str}.json"
        output_csv = script_location / f"clickup_tasks_{CLICKUP_LIST_ID}_{date_str}.csv"

        # --- Guardar JSON completo ---
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Datos guardados en JSON: {output_json}")

        # --- Aplanar y guardar CSV ---
        print("🧩 Aplanando tareas para exportar a CSV...")
        flattened = [flatten_json(task) for task in tasks]
        if not flattened:
            print("⚠️ No hay tareas para exportar.")
        else:
            # Obtener todas las claves posibles para las columnas del CSV
            fieldnames = sorted({k for t in flattened for k in t.keys()})
            with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for task in flattened:
                    writer.writerow(task)
            print(f"💾 CSV completo guardado en: {output_csv}")

        # --- Mostrar ejemplo ---
        if tasks:
            print(f"\nEjemplo de tarea:\n- {tasks[0]['name']} [{tasks[0]['status']['status']}]")

    elif response.status_code == 401:
        print("❌ Error 401: No autorizado. Revisa tu token en .env.")
    elif response.status_code == 404:
        print("❌ Error 404: Lista no encontrada. Revisa tu CLICKUP_LIST_ID.")
    else:
        print(f"⚠️ Error inesperado ({response.status_code})")
        try:
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except Exception:
            print(response.text)

except requests.exceptions.RequestException as e:
    print(f"❌ Error de conexión: {e}")
    print(traceback.format_exc())
except Exception as e:
    print(f"❌ Error inesperado: {e}")
    print(traceback.format_exc())
