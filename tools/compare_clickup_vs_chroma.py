#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compara lo almacenado en Chroma (metadatos) con el JSON RAW de ClickUp.
- Muestra diferencias por task_id en: sprint, project, status, priority, assignees, tags, due_date.
- Útil para auditar qué se perdió/normalizó mal en el pipeline.

Requisitos:
- RAW guardado en: data/rag/ingest/clickup_tasks_all_*.json  (ajusta abajo si tu ruta es otra)
- Colección Chroma: clickup_tasks en data/rag/chroma_db
"""

from pathlib import Path
import json
import glob
from collections import defaultdict

import chromadb
from typing import Any, cast

RAW_GLOB = "data/rag/ingest/clickup_tasks_all_*.json"   # ajusta si tu RAW está en otra ruta
CHROMA_PATH = "data/rag/chroma_db"
COLLECTION = "clickup_tasks"

# ---------- Normalizadores básicos ----------
def norm_status(raw_status: str) -> str:
    s = (raw_status or "").strip().lower()
    mapping = {
        "to do": "to_do", "todo": "to_do", "to-do": "to_do",
        "in progress": "in_progress", "in_progress": "in_progress",
        "complete": "done", "completed": "done", "closed": "done", "done": "done",
    }
    return mapping.get(s, s or "unknown")

def norm_priority(raw_pri) -> str:
    # ClickUp raw puede ser objeto {"priority": "urgent"} o None
    if isinstance(raw_pri, dict):
        p = raw_pri.get("priority")
    else:
        p = raw_pri
    p = (p or "").strip().lower()
    mp = {"urgente": "urgent", "urgent": "urgent", "alta": "high", "high": "high",
          "normal": "normal", "baja": "low", "low": "low"}
    return mp.get(p, p or "unknown")

def ms_to_date(ms_str):
    # Devuelve YYYY-MM-DD o "unknown"
    try:
        if not ms_str:
            return "unknown"
        ms = int(ms_str)
        from datetime import datetime, timezone
        return datetime.fromtimestamp(ms/1000, tz=timezone.utc).date().isoformat()
    except Exception:
        return "unknown"

def list_names_assignees(arr):
    if not arr:
        return []
    names = []
    for a in arr:
        n = a.get("username") or a.get("name") or a.get("email")
        if n:
            names.append(n)
    return names

def list_tag_names(arr):
    if not arr:
        return []
    return [t.get("name") for t in arr if isinstance(t, dict) and t.get("name")]

# ---------- Carga RAW (ClickUp) ----------
def load_raw_tasks() -> dict:
    # Junta todos los archivos raw si hay varios
    raw_files = sorted(glob.glob(RAW_GLOB))
    data_by_id = {}
    for rf in raw_files:
        try:
            obj = json.loads(Path(rf).read_text(encoding="utf-8"))
            for t in obj.get("tasks", []):
                data_by_id[t["id"]] = t
        except Exception as e:
            print(f"⚠️ No pude leer {rf}: {e}")
    return data_by_id

def load_chroma_metas(limit=100000):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    col = client.get_collection(COLLECTION)
    res = col.get(include=cast(Any, ["ids","metadatas"]), limit=limit)
    ids = res.get("ids", []) or []
    metas = res.get("metadatas", []) or []
    # los metadatos en tu pipeline guardan "task_id" por chunk; cogemos el primero visto para cada task_id
    by_task = {}
    for _id, m in zip(ids, metas):
        if not isinstance(m, dict):
            continue
        tid = m.get("task_id")
        if not tid:
            # en caso de chunk sin task_id, ignora
            continue
        if tid not in by_task:
            by_task[tid] = m
    return by_task
    return by_task

# ---------- Comparación ----------
FIELDS = ["sprint", "project", "status", "priority", "assignees", "tags", "due_date", "name"]

def extract_expected_from_raw(rt: dict) -> dict:
    return {
        "task_id": rt.get("id"),
        "name": rt.get("name") or "",
        "sprint": rt.get("sprint_name") or "unknown",
        "project": (rt.get("project") or {}).get("name") or "unknown",
        "status": norm_status((rt.get("status") or {}).get("status", "")),
        "priority": norm_priority(rt.get("priority")),
        "assignees": list_names_assignees(rt.get("assignees")),
        "tags": list_tag_names(rt.get("tags")),
        "due_date": ms_to_date(rt.get("due_date")),
    }

def normalize_meta_for_compare(m: dict) -> dict:
    # en tu Chroma aparecen a veces strings "[]" → conviértelo a lista
    def as_list(x):
        if isinstance(x, list):
            return x
        if isinstance(x, str):
            s = x.strip()
            if s == "[]":
                return []
            # si viene como string con comas, intenta partir
            if s.startswith("[") and s.endswith("]"):
                # intento suave
                try:
                    import ast
                    v = ast.literal_eval(s)
                    if isinstance(v, list):
                        return v
                except Exception:
                    pass
            return [s] if s else []
        return []

    return {
        "task_id": m.get("task_id"),
        "name": m.get("name") or "",
        "sprint": m.get("sprint") or "unknown",
        "project": m.get("project") or "unknown",
        "status": (m.get("status") or "unknown").lower(),
        "priority": (m.get("priority") or "unknown").lower(),
        "assignees": as_list(m.get("assignees")),
        "tags": as_list(m.get("tags")),
        "due_date": m.get("due_date") or "unknown",
    }

def main():
    raw = load_raw_tasks()
    chroma = load_chroma_metas()

    missing_in_chroma = []
    diff_by_field = defaultdict(list)

    for tid, rt in raw.items():
        exp = extract_expected_from_raw(rt)
        meta = chroma.get(tid)
        if not meta:
            missing_in_chroma.append(tid)
            continue
        got = normalize_meta_for_compare(meta)

        for f in FIELDS:
            if got[f] != exp[f]:
                diff_by_field[f].append({
                    "task_id": tid,
                    "expected": exp[f],
                    "got": got[f],
                    "name": exp["name"]
                })

    print("\n=== RESUMEN ===")
    print(f"RAW tasks: {len(raw)} | Chroma tasks (con task_id único): {len(chroma)}")
    print(f"Tareas RAW sin metadatos en Chroma: {len(missing_in_chroma)}")
    if missing_in_chroma:
        print("  ->", ", ".join(missing_in_chroma[:10]), ("..." if len(missing_in_chroma)>10 else ""))

    for f in FIELDS:
        lst = diff_by_field.get(f, [])
        print(f"\n- Diferencias en '{f}': {len(lst)}")
        for d in lst[:8]:
            print(f"  · {d['task_id']} ({d['name']}) | esper: {d['expected']} | got: {d['got']}")
        if len(lst) > 8:
            print(f"  ... (+{len(lst)-8} más)")

if __name__ == "__main__":
    main()
