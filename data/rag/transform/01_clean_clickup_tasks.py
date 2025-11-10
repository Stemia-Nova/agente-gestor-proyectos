#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_clickup_tasks_01.py — Limpieza y normalización (rutas fijas)
------------------------------------------------------------------
Lee el JSON crudo descargado de ClickUp:
  data/rag/ingest/clickup_tasks_all_2025-11-10.json
y genera en data/processed/:
  - task_clean.jsonl
  - task_clean.json
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List
from collections import defaultdict

# ============================================================
# 📂 RUTAS FIJAS (ajústalas si lo necesitas)
# ============================================================

ROOT = Path(__file__).resolve().parents[2]  # raíz del repo
INPUT_FILE = ROOT / "rag" / "ingest" / "clickup_tasks_all_2025-11-10.json"
OUTPUT_DIR = ROOT / "processed"
OUT_JSONL = OUTPUT_DIR / "task_clean.jsonl"
OUT_JSON = OUTPUT_DIR / "task_clean.json"

# ============================================================
# 🔧 FUNCIONES AUXILIARES
# ============================================================

def parse_epoch_ms(value: Any) -> str | None:
    """Convierte epoch en ms (str/int) a ISO UTC."""
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return None

def normalize_status(raw: str | None) -> str:
    if not raw:
        return "unknown"
    s = raw.strip().lower()
    mapping = {
        "to do": "to_do",
        "todo": "to_do",
        "open": "to_do",
        "in progress": "in_progress",
        "doing": "in_progress",
        "progress": "in_progress",
        "complete": "done",
        "completed": "done",
        "done": "done",
        "closed": "done",
        "finalizado": "done",
        "completado": "done",
        "blocked": "blocked",
        "bloqueado": "blocked",
        "cancelled": "cancelled",
    }
    if s in mapping:
        return mapping[s]
    if "progress" in s: return "in_progress"
    if "block" in s or "bloque" in s: return "blocked"
    if "cancel" in s: return "cancelled"
    if "complete" in s or "done" in s or "finaliz" in s: return "done"
    return "custom"

def normalize_priority(p: Dict[str, Any] | None) -> str:
    if not p:
        return "unknown"
    return (p.get("priority") or p.get("name") or "unknown").lower()

def assignees_to_text(assignees: List[Dict[str, Any]] | None) -> str:
    if not assignees:
        return "Sin asignar"
    names = [a.get("username") or a.get("email") for a in assignees if a]
    return ", ".join([n for n in names if n]) or "Sin asignar"

def is_blocked_from_tags(tags: List[Dict[str, Any]] | None) -> bool:
    if not tags:
        return False
    return any(re.search(r"bloquead|blocked|blocker", (t.get("name") or "").lower()) for t in tags)

def derive_sprint(t: Dict[str, Any]) -> str:
    # Preferimos sprint_name que ya añadiste al descargar.
    return t.get("sprint_name") or t.get("list", {}).get("name") or t.get("list_name") or "Sin sprint"

# ============================================================
# 🧹 LIMPIEZA PRINCIPAL
# ============================================================

def clean_tasks(raw_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for t in raw_tasks:
        status = normalize_status((t.get("status") or {}).get("status"))
        prio = normalize_priority(t.get("priority"))
        sprint = derive_sprint(t)
        parent_id = t.get("parent")
        is_subtask = bool(parent_id)
        blocked = is_blocked_from_tags(t.get("tags"))

        created = parse_epoch_ms(t.get("date_created"))
        updated = parse_epoch_ms(t.get("date_updated"))
        due = parse_epoch_ms(t.get("due_date"))

        assignees_text = assignees_to_text(t.get("assignees"))

        record = {
            "task_id": t.get("id"),
            "name": t.get("name") or "Sin título",
            "status": status,
            "priority": prio,
            "assignees": assignees_text,
            "sprint": sprint,
            "parent_task_id": parent_id,
            "is_subtask": is_subtask,
            "is_blocked": blocked,
            "date_created": created,
            "date_updated": updated,
            "due_date": due,
            "project": (t.get("project") or {}).get("name") or (t.get("folder") or {}).get("name") or "unknown",
            "url": t.get("url"),
        }
        cleaned.append(record)

    cleaned = assign_sprint_status(cleaned)
    return cleaned

def assign_sprint_status(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Marca sprints como actual/cerrado según los estados."""
    sprints: dict[str, list[str]] = defaultdict(list)
    for t in tasks:
        sprint_key = str(t.get("sprint") or "Sin sprint")
        status_val = str(t.get("status") or "unknown")
        sprints[sprint_key].append(status_val)
    sprint_map = {
        s: "cerrado" if all(st in {"done", "cancelled"} for st in sts) else "actual"
        for s, sts in sprints.items()
    }
    for t in tasks:
        t_sprint = str(t.get("sprint") or "Sin sprint")
        t["sprint_status"] = sprint_map.get(t_sprint, "actual")
    return tasks

# ============================================================
# 💾 GUARDADO
# ============================================================

def write_jsonl(tasks: List[Dict[str, Any]], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

def write_json(tasks: List[Dict[str, Any]], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")

# ============================================================
# 🚀 EJECUCIÓN PRINCIPAL
# ============================================================

if __name__ == "__main__":
    print("🧹 Iniciando limpieza de ClickUp (rutas fijas)...")

    if not INPUT_FILE.exists():
        raise SystemExit(f"❌ No existe el archivo de entrada: {INPUT_FILE}")

    print(f"📥 Leyendo: {INPUT_FILE}")
    raw = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    tasks_raw = raw.get("tasks", [])
    print(f"🧩 {len(tasks_raw)} tareas crudas encontradas")

    cleaned = clean_tasks(tasks_raw)
    print(f"✅ {len(cleaned)} tareas limpias procesadas")

    write_jsonl(cleaned, OUT_JSONL)
    write_json(cleaned, OUT_JSON)

    sprints = sorted({t.get("sprint", 'Sin sprint') for t in cleaned})
    done = sum(1 for t in cleaned if t["status"] == "done")
    inprog = sum(1 for t in cleaned if t["status"] == "in_progress")
    todo = sum(1 for t in cleaned if t["status"] == "to_do")
    blocked = sum(1 for t in cleaned if t["is_blocked"])

    print("\n📊 Resumen:")
    print(f"   • Sprints detectados: {', '.join(sprints)}")
    print(f"   • Done: {done}, In progress: {inprog}, To do: {todo}, Bloqueadas: {blocked}")
    print(f"💾 Guardados:\n   - {OUT_JSONL}\n   - {OUT_JSON}")
    print("🏁 Limpieza completada correctamente.")
