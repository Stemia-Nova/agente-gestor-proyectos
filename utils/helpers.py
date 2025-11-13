#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
helpers.py — utilidades generales y de análisis
-----------------------------------------------
• Lectura/escritura JSON
• Variables de entorno
• Consultas analíticas sobre la base vectorial (Chroma)
"""

import os
import json
from typing import Any, List, Dict, Optional

# ==============================================================
# 🧩 FUNCIONES GENÉRICAS
# ==============================================================

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


# ==============================================================
# 📊 FUNCIONES DE CONSULTA CHROMA (para handlers/chatbot)
# ==============================================================

import chromadb


def _load_collection(collection_name: str = "clickup_tasks", db_path: str = "data/rag/chroma_db"):
    """Abrir la colección persistente de Chroma."""
    client = chromadb.PersistentClient(path=db_path)
    return client.get_collection(collection_name)


def _extract_metadatas(result: Any) -> List[Dict[str, Any]]:
    """
    Extrae metadatos de un GetResult de Chroma de manera segura.
    - En algunas versiones viene como lista plana.
    - En otras, como lista de listas.
    """
    if result is None:
        return []

    metas = None
    if isinstance(result, dict):
        metas = result.get("metadatas", None)
    else:
        # Algunos GetResult se comportan como objetos; intenta acceder como atributo
        try:
            metas = getattr(result, "metadatas", None)
        except Exception:
            metas = None

    if metas is None:
        return []

    # Lista de listas → toma la primera
    if isinstance(metas, list) and metas and isinstance(metas[0], list):
        return [m for m in metas[0] if isinstance(m, dict)]

    # Lista plana
    if isinstance(metas, list):
        return [m for m in metas if isinstance(m, dict)]

    return []


def _fetch_metadatas(limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Intenta peek() y, si es necesario, cae a get(). Siempre devuelve lista de dicts.
    """
    col = _load_collection()

    # 1) peek
    try:
        peek_result: Any = col.peek(limit=limit)
        metas = _extract_metadatas(peek_result)
        if metas:
            return metas
    except Exception:
        pass

    # 2) get (fallback)
    try:
        get_result: Any = col.get(limit=limit)
        metas = _extract_metadatas(get_result)
        return metas
    except Exception:
        return []


def _get_with_where(where: Dict[str, Any], limit: int = 10000) -> List[Dict[str, Any]]:
    """Devuelve metadatos filtrados con 'where' usando col.get (hasta 'limit')."""
    col = _load_collection()
    # Evita pasar una lista de strings a 'include' para no romper la comprobación de tipos;
    # _extract_metadatas maneja de forma segura el resultado aunque no se especifique include.
    res: Any = col.get(where=where, limit=limit)
    return _extract_metadatas(res)


def _sorted_strings(values: List[str]) -> List[str]:
    """Ordena de forma segura una lista de strings."""
    try:
        return sorted(values)
    except Exception:
        return list(values)


def _norm_status(s: Optional[str]) -> str:
    s = (s or "").strip().lower().replace(" ", "_")
    mapping = {
        "to_do": "to_do", "todo": "to_do", "to-do": "to_do", "por_hacer": "to_do",
        "in_progress": "in_progress", "en_curso": "in_progress", "en_progreso": "in_progress",
        "doing": "in_progress", "progreso": "in_progress",
        "done": "done", "completado": "done", "cerrado": "done", "finalizado": "done",
    }
    return mapping.get(s, s or "unknown")


def _norm_priority(p: Optional[str]) -> str:
    p = (p or "").strip().lower()
    mapping = {
        "urgente": "urgent", "urgent": "urgent",
        "alta": "high", "high": "high",
        "normal": "normal",
        "baja": "low", "low": "low",
    }
    return mapping.get(p, p or "unknown")


def _filter_by_sprint(metas: List[Dict[str, Any]], sprint: Optional[str]) -> List[Dict[str, Any]]:
    if not sprint:
        return metas
    return [m for m in metas if str(m.get("sprint")) == sprint]


# ------------------- Conteos públicos -------------------

def count_sprints() -> str:
    """Contar los sprints distintos presentes en la base vectorial."""
    try:
        metadatas = _fetch_metadatas(limit=1000)

        # Construye el set de sprints válidos de forma segura evitando llamadas a .strip() sobre None
        sprints_set = set()
        for m in metadatas:
            s = m.get("sprint")
            if isinstance(s, str) and s.strip() and s != "unknown":
                sprints_set.add(s)

        sprints: List[str] = [str(s) for s in sprints_set]
        if not sprints:
            return "📊 No se encontraron sprints registrados."

        sprints_sorted = _sorted_strings(sprints)
        return f"📊 Hay {len(sprints_sorted)} sprints registrados: {', '.join(sprints_sorted)}."
    except Exception as e:
        return f"⚠️ Error al contar sprints: {e}"


def count_tasks() -> str:
    """Contar el total de tareas almacenadas en la base vectorial."""
    try:
        col = _load_collection()
        total = col.count()
        return f"📋 Hay {total} tareas registradas en la base vectorial."
    except Exception as e:
        return f"⚠️ Error al contar tareas: {e}"


def count_tasks_in_sprint(sprint: str) -> str:
    """Contar tareas (todas) en un sprint concreto."""
    try:
        metas = _get_with_where({"sprint": sprint})
        return f"📆 Tareas en {sprint}: {len(metas)}."
    except Exception as e:
        return f"⚠️ Error al contar tareas en {sprint}: {e}"


def count_tasks_blocked(sprint: Optional[str] = None) -> str:
    """Contar tareas bloqueadas (opcionalmente filtradas por sprint)."""
    try:
        if sprint:
            metas = _get_with_where({"sprint": sprint})
        else:
            metas = _fetch_metadatas(limit=2000)
        n = sum(1 for m in metas if bool(m.get("is_blocked")))
        return f"🚧 Tareas bloqueadas{f' en {sprint}' if sprint else ''}: {n}."
    except Exception as e:
        return f"⚠️ Error al contar tareas bloqueadas: {e}"


def count_tasks_by_status(status: str, sprint: Optional[str] = None) -> str:
    """Contar tareas por estado (to_do, in_progress, done), opcionalmente por sprint."""
    try:
        target = _norm_status(status)
        if sprint:
            metas = _get_with_where({"sprint": sprint})
        else:
            metas = _fetch_metadatas(limit=2000)
        n = sum(1 for m in metas if _norm_status(m.get("status")) == target)
        return f"📌 Tareas con estado {target}{f' en {sprint}' if sprint else ''}: {n}."
    except Exception as e:
        return f"⚠️ Error al contar tareas por estado: {e}"


def count_tasks_by_priority(priority: str, sprint: Optional[str] = None) -> str:
    """Contar tareas por prioridad (urgent, high, normal, low), opcionalmente por sprint."""
    try:
        target = _norm_priority(priority)
        if sprint:
            metas = _get_with_where({"sprint": sprint})
        else:
            metas = _fetch_metadatas(limit=2000)
        n = sum(1 for m in metas if _norm_priority(m.get("priority")) == target)
        return f"⭐ Tareas con prioridad {target}{f' en {sprint}' if sprint else ''}: {n}."
    except Exception as e:
        return f"⚠️ Error al contar tareas por prioridad: {e}"
