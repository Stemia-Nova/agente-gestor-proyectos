"""Helpers genéricos para el proyecto (sin dependencias a Chainlit)."""
import json
import os
from typing import Any


def get_env(key: str, default: Any = None) -> Any:
    """Leer una variable de entorno y devolver un valor por defecto si no existe."""
    return os.getenv(key, default)


def load_json(path: str) -> Any:
    """Cargar y devolver el contenido JSON de un fichero. Devuelve None si no existe."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    """Guardar datos en formato JSON (crea directorios si hace falta)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
