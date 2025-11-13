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

ROOT = Path(__file__).resolve().parents[3]  # raíz del repo
INPUT_FILE = ROOT / "data" / "rag" / "ingest" / "clickup_tasks_all_2025-11-13.json"
OUTPUT_DIR = ROOT / "data" / "processed"
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

def normalize_status(raw: str | None, status_type: str | None = None) -> str:
    """Normaliza estados de ClickUp a categorías estándar.
    
    ClickUp tiene 3 tipos de estados:
    - open: Estados iniciales (to do, open, etc.)
    - custom: Estados personalizados (in progress, review, etc.)
    - closed: Estados finales (complete, done, closed)
    
    Args:
        raw: Nombre del estado de ClickUp
        status_type: Tipo de estado de ClickUp (open/custom/closed)
    
    Returns:
        Estado normalizado: to_do, in_progress, done, blocked, cancelled, custom
    """
    if not raw:
        return "unknown"
    
    s = raw.strip().lower()
    
    # Mapeo directo de estados conocidos de ClickUp
    CLICKUP_STATUS_MAP = {
        # Estados estándar de ClickUp
        "to do": "to_do",
        "in progress": "in_progress",
        "complete": "done",
        
        # Variantes comunes
        "todo": "to_do",
        "open": "to_do",
        "doing": "in_progress",
        "progress": "in_progress",
        "working": "in_progress",
        "completed": "done",
        "done": "done",
        "closed": "done",
        "finished": "done",
        
        # Estados en español
        "por hacer": "to_do",
        "pendiente": "to_do",
        "en progreso": "in_progress",
        "trabajando": "in_progress",
        "finalizado": "done",
        "completado": "done",
        "cerrado": "done",
        
        # Estados de revisión/testing
        "qa": "qa",
        "testing": "qa",
        "test": "qa",
        "review": "review",
        "revision": "review",
        "revisión": "review",
        
        # Estados especiales
        "blocked": "blocked",
        "bloqueado": "blocked",
        "bloqueada": "blocked",
        "cancelled": "cancelled",
        "cancelado": "cancelled",
        "cancelada": "cancelled",
    }
    
    # Buscar coincidencia exacta
    if s in CLICKUP_STATUS_MAP:
        return CLICKUP_STATUS_MAP[s]
    
    # Usar status_type de ClickUp como pista
    if status_type:
        if status_type == "closed":
            return "done"
        elif status_type == "open":
            return "to_do"
    
    # Búsqueda por patrones (fallback)
    if "qa" in s or "test" in s:
        return "qa"
    if "review" in s or "revis" in s:
        return "review"
    if "progress" in s or "doing" in s or "working" in s:
        return "in_progress"
    if "block" in s or "bloque" in s:
        return "blocked"
    if "cancel" in s:
        return "cancelled"
    if "complete" in s or "done" in s or "finaliz" in s or "finish" in s:
        return "done"
    
    # Estado personalizado no reconocido
    return "custom"

def normalize_priority(p: Dict[str, Any] | None) -> str:
    """Normaliza prioridades de ClickUp a categorías estándar.
    
    ClickUp tiene 4 niveles de prioridad estándar:
    - urgent (1): Máxima prioridad
    - high (2): Alta prioridad
    - normal (3): Prioridad normal
    - low (4): Baja prioridad
    
    Args:
        p: Objeto de prioridad de ClickUp con campo 'priority'
    
    Returns:
        Prioridad normalizada: urgent, high, normal, low, unknown
    """
    if not p:
        return "unknown"
    
    priority_name = (p.get("priority") or p.get("name") or "unknown").lower().strip()
    
    # Mapeo de prioridades de ClickUp
    PRIORITY_MAP = {
        "urgent": "urgent",
        "urgente": "urgent",
        "crítico": "urgent",
        "critical": "urgent",
        "1": "urgent",
        
        "high": "high",
        "alta": "high",
        "alto": "high",
        "2": "high",
        
        "normal": "normal",
        "medium": "normal",
        "media": "normal",
        "medio": "normal",
        "3": "normal",
        
        "low": "low",
        "baja": "low",
        "bajo": "low",
        "4": "low",
    }
    
    return PRIORITY_MAP.get(priority_name, "unknown")

def assignees_to_text(assignees: List[Dict[str, Any]] | None) -> str:
    if not assignees:
        return "Sin asignar"
    names = [a.get("username") or a.get("email") for a in assignees if a]
    return ", ".join([n for n in names if n]) or "Sin asignar"

def is_blocked_from_tags(tags: List[Dict[str, Any]] | None) -> bool:
    if not tags:
        return False
    return any(re.search(r"bloquead|blocked|blocker", (t.get("name") or "").lower()) for t in tags)


def get_flags_from_tags(tags: List[Dict[str, Any]] | None) -> Dict[str, bool]:
    """Extrae flags adicionales de las tags (blocked, needs_info).
    
    Estos flags NO reemplazan el estado de ClickUp, son información adicional.
    
    Returns:
        Dict con flags: {'is_blocked': bool, 'needs_info': bool}
    """
    flags = {'is_blocked': False, 'needs_info': False}
    
    if not tags:
        return flags
    
    names = [(t.get("name") or "").lower() for t in tags if t]
    
    # Detectar bloqueo
    for n in names:
        if "bloque" in n or "blocked" in n or "blocker" in n or n == "bloqueada":
            flags['is_blocked'] = True
            break
    
    # Detectar necesidad de información
    for n in names:
        if n in ("data", "datos") or "duda" in n or "pregunta" in n:
            flags['needs_info'] = True
            break
    
    return flags


# ============================================================
# 🌍 MAPEOS A LENGUAJE NATURAL (Para PM/Scrum Master)
# ============================================================

# Mapeo de estados normalizados a etiquetas naturales en español
STATUS_TO_SPANISH = {
    "to_do": "Pendiente",
    "in_progress": "En progreso",
    "qa": "En QA/Testing",
    "review": "En revisión",
    "done": "Completada",
    "blocked": "Bloqueada",
    "cancelled": "Cancelada",
    "needs_info": "Requiere información",
    "custom": "Estado personalizado",
    "unknown": "Estado desconocido",
}

# Mapeo de prioridades a etiquetas naturales en español
PRIORITY_TO_SPANISH = {
    "urgent": "Urgente",
    "high": "Alta",
    "normal": "Normal",
    "low": "Baja",
    "unknown": "Sin prioridad",
}

# Emojis opcionales para enriquecer visualización (opcional)
STATUS_EMOJI = {
    "to_do": "📝",
    "in_progress": "🔄",
    "qa": "🧪",
    "review": "👀",
    "done": "✅",
    "blocked": "🚫",
    "cancelled": "❌",
    "needs_info": "❓",
    "custom": "⚙️",
    "unknown": "❔",
}

PRIORITY_EMOJI = {
    "urgent": "🔥",
    "high": "⚡",
    "normal": "📌",
    "low": "💤",
    "unknown": "⚪",
}

def derive_sprint(t: Dict[str, Any]) -> str:
    # Preferimos sprint_name que ya añadiste al descargar.
    return t.get("sprint_name") or t.get("list", {}).get("name") or t.get("list_name") or "Sin sprint"

# ============================================================
# 🧹 LIMPIEZA PRINCIPAL
# ============================================================

def clean_tasks(raw_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Limpia y normaliza tareas de ClickUp con mapeos optimizados para RAG.
    
    Optimizaciones de ingeniería de IA:
    1. Normalización basada en estados reales de ClickUp
    2. Preservación de contexto PM crítico (comentarios, subtareas)
    3. Etiquetas naturales en español para mejor comprensión del LLM
    4. Metadata estructurada para búsqueda híbrida
    5. Derivación inteligente de estados desde tags
    """
    cleaned = []
    for t in raw_tasks:
        # Obtener objeto de estado completo de ClickUp
        status_obj = t.get("status") or {}
        status_name = status_obj.get("status")
        status_type = status_obj.get("type")  # open, custom, closed
        
        # Normalizar con contexto de tipo de estado
        status = normalize_status(status_name, status_type)
        prio = normalize_priority(t.get("priority"))
        sprint = derive_sprint(t)
        parent_id = t.get("parent")
        is_subtask = bool(parent_id)
        tags = t.get("tags") or []
        # tags_list: nombres de etiquetas (limpios)
        tags_list = [ (x.get("name") or "").strip() for x in tags if x ]

        # Extraer FLAGS adicionales de tags (NO reemplazar el estado de ClickUp)
        # REGLA DE NEGOCIO: Si la tarea está completada, los flags históricos no aplican
        if status == "done":
            # Tarea completada: bloqueos/dudas fueron resueltos
            blocked = False
            needs_info = False
        else:
            # Tarea activa: aplicar flags de tags
            tag_flags = get_flags_from_tags(tags)
            blocked = tag_flags['is_blocked']
            needs_info = tag_flags['needs_info']

        created = parse_epoch_ms(t.get("date_created"))
        updated = parse_epoch_ms(t.get("date_updated"))
        due = parse_epoch_ms(t.get("due_date"))

        assignees_text = assignees_to_text(t.get("assignees"))

        # Extraer descripción (puede ser HTML o texto plano)
        description = t.get("description") or t.get("text_content") or ""
        
        # Procesar comentarios (relevantes para PM: bloqueos, dudas)
        comments = t.get("comments", [])
        has_comments = t.get("has_comments", False) or len(comments) > 0
        comments_count = t.get("comments_count", len(comments))
        
        # Procesar subtareas (importante para jerarquía de trabajo)
        subtasks = t.get("subtasks", [])
        has_subtasks = t.get("has_subtasks", False) or len(subtasks) > 0
        subtasks_count = t.get("subtasks_count", len(subtasks))
        
        # Información de proyecto/folder (para multi-proyecto)
        project_name = t.get("project_name") or (t.get("project") or {}).get("name") or "unknown"
        folder_name = t.get("folder_name") or (t.get("folder") or {}).get("name")
        
        record = {
            "task_id": t.get("id"),
            "name": t.get("name") or "Sin título",
            
            # Estados: valor normalizado + etiqueta natural en español
            "status": status,  # Para lógica y filtros (to_do, in_progress, done, etc.)
            "status_display": STATUS_TO_SPANISH.get(status, STATUS_TO_SPANISH["unknown"]),  # Para LLM
            "status_raw": status_name,  # Estado original de ClickUp (para debugging)
            
            # Prioridades: valor normalizado + etiqueta natural
            "priority": prio,  # Para lógica (urgent, high, normal, low)
            "priority_display": PRIORITY_TO_SPANISH.get(prio, PRIORITY_TO_SPANISH["unknown"]),  # Para LLM
            
            "assignees": assignees_text,
            "sprint": sprint,
            "parent_task_id": parent_id,
            "is_subtask": is_subtask,
            "is_blocked": blocked,
            "needs_info": needs_info,
            "tags": tags_list,
            "description": description,
            # Comentarios (críticos para entender bloqueos/dudas)
            "comments": comments,
            "has_comments": has_comments,
            "comments_count": comments_count,
            # Subtareas (importante para jerarquía)
            "subtasks": subtasks,
            "has_subtasks": has_subtasks,
            "subtasks_count": subtasks_count,
            # Fechas
            "date_created": created,
            "date_updated": updated,
            "due_date": due,
            # Contexto de proyecto (para multi-proyecto)
            "project": project_name,
            "folder": folder_name if folder_name else project_name,
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
    qa = sum(1 for t in cleaned if t["status"] == "qa")
    review = sum(1 for t in cleaned if t["status"] == "review")
    todo = sum(1 for t in cleaned if t["status"] == "to_do")
    blocked = sum(1 for t in cleaned if t["is_blocked"])

    print("\n📊 Resumen:")
    print(f"   • Sprints detectados: {', '.join(sprints)}")
    print(f"   • Done: {done}, In progress: {inprog}, QA: {qa}, Review: {review}, To do: {todo}, Bloqueadas: {blocked}")
    print(f"💾 Guardados:\n   - {OUT_JSONL}\n   - {OUT_JSON}")
    print("🏁 Limpieza completada correctamente.")
