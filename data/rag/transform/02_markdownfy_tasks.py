#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02_markdownfy_tasks.py (robusto y embeddings-safe)
--------------------------------------------------
Convierte las tareas limpias (task_clean.jsonl) en texto Markdown semánticamente limpio.

✔ Elimina dependencias de claves frágiles (priority_level ausente, etc.)
✔ Mantiene estructura Markdown legible para modelos.
✔ Sustituye iconos por texto natural: Bloqueada, Urgente, Pendiente de revisión, etc.
✔ Incluye comentarios y subtareas en texto plano.
✔ Genera salida lista para la fase de naturalización o embeddings.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from tqdm import tqdm

try:
    from markdownify import markdownify as md
    HAS_MARKDOWNIFY = True
except ImportError:
    HAS_MARKDOWNIFY = False
    print("⚠️ markdownify no instalado. Instala con: pip install markdownify")

INPUT_PATH = Path("data/processed/task_clean.jsonl")
OUTPUT_PATH = Path("data/processed/task_markdown.jsonl")


# -----------------------------
# Helpers de saneamiento/seguridad
# -----------------------------
def safe_str(x: Any, default: str = "") -> str:
    if x is None:
        return default
    if isinstance(x, (dict, list, tuple, set)):
        try:
            return json.dumps(x, ensure_ascii=False)
        except Exception:
            return str(x)
    return str(x)


def safe_cap(x: Any, default: str = "") -> str:
    s = safe_str(x, default=default).strip()
    return s.capitalize() if s else default


def html_to_markdown(text: str) -> str:
    """
    Convierte HTML/RichText a Markdown preservando estructura.
    Si no hay markdownify, hace limpieza básica de tags HTML.
    """
    if not text or not text.strip():
        return ""
    
    # Detectar si parece HTML
    if not ("<" in text and ">" in text):
        return text.strip()
    
    if HAS_MARKDOWNIFY:
        try:
            # Convertir HTML a Markdown limpio
            return md(text, heading_style="ATX", strip=["script", "style"]).strip()
        except Exception as e:
            print(f"⚠️ Error en markdownify: {e}")
    
    # Fallback: limpieza básica de tags
    import re
    text = re.sub(r"<br\s*/?>|</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_priority(raw: Optional[str]) -> str:
    """
    Normaliza prioridad a un set pequeño (urgent, high, normal, low, unknown).
    Acepta valores en español/inglés y mayúsculas variadas.
    """
    if not raw:
        return "unknown"
    s = safe_str(raw).strip().lower()

    mapping = {
        "urgente": "urgent",
        "urgent": "urgent",
        "alta": "high",
        "high": "high",
        "normal": "normal",
        "media": "normal",
        "medium": "normal",
        "baja": "low",
        "low": "low",
        "sin definir": "unknown",
        "": "unknown",
        "none": "unknown",
        "null": "unknown",
    }
    return mapping.get(s, s if s in {"urgent", "high", "normal", "low"} else "unknown")


def normalize_status(raw: Optional[str]) -> str:
    if not raw:
        return "unknown"
    s = safe_str(raw).strip().lower()
    # Mapea algunos comunes
    mapping = {
        "to do": "to_do",
        "todo": "to_do",
        "por hacer": "to_do",
        "in progress": "in_progress",
        "doing": "in_progress",
        "en progreso": "in_progress",
        "done": "done",
        "hecho": "done",
        "complete": "done",
        "completed": "done",
    }
    return mapping.get(s, s.replace(" ", "_"))


def render_assignees(asg: Union[List, Dict, str, None]) -> str:
    """
    Devuelve una cadena legible de asignados.
    - Si es lista de dicts: usa 'name' o 'username'.
    - Si es lista de strings: únelas.
    - Si es dict: intenta 'name'/'username'.
    - Si es string: devuélvelo.
    """
    if not asg:
        return "—"
    if isinstance(asg, list):
        names: List[str] = []
        for a in asg:
            if isinstance(a, dict):
                nm = a.get("name") or a.get("username") or a.get("email") or ""
                if nm:
                    names.append(str(nm))
            else:
                names.append(safe_str(a))
        return ", ".join([n for n in (x.strip() for x in names) if n]) or "—"
    if isinstance(asg, dict):
        nm = asg.get("name") or asg.get("username") or asg.get("email") or ""
        return nm or "—"
    return safe_str(asg) or "—"


def render_tags(tags: Union[List[str], List[Dict], str, None]) -> str:
    if not tags:
        return "—"
    if isinstance(tags, list):
        out = []
        for t in tags:
            if isinstance(t, dict):
                out.append(safe_str(t.get("name") or t.get("tag") or t.get("value") or "").strip())
            else:
                out.append(safe_str(t).strip())
        out = [x for x in out if x]
        return ", ".join(out) if out else "—"
    return safe_str(tags) or "—"


def render_comments(comments: Union[str, List, None]) -> str:
    """
    Renderiza comentarios en formato Markdown legible.
    IMPORTANTE para PM: Los comentarios contienen info crítica sobre bloqueos y dudas.
    """
    if not comments:
        return ""
    if isinstance(comments, list):
        lines = []
        for c in comments:
            if isinstance(c, dict):
                author = c.get("author") or c.get("user") or ""
                text = c.get("text") or c.get("comment_text") or c.get("comment") or ""
                date = c.get("date", "")
                resolved = c.get("resolved", False)
                status_marker = "✓" if resolved else "○"
                
                if text:
                    lines.append(f"- [{status_marker}] **{safe_str(author)}**: {safe_str(text)}")
            else:
                lines.append(f"- {safe_str(c)}")
        body = "\n".join(lines)
    else:
        body = safe_str(comments)

    body = body.strip()
    return f"\n\n**Comentarios ({len(lines) if isinstance(comments, list) else '?'}):**\n{body}" if body else ""


def render_subtasks(subtasks: Union[List, None]) -> str:
    """
    Renderiza subtareas en formato Markdown.
    IMPORTANTE para PM: Las subtareas muestran la descomposición del trabajo.
    """
    if not subtasks:
        return ""
    lines = []
    for st in subtasks:
        if not isinstance(st, dict):
            lines.append(f"- {safe_str(st)}")
            continue
        st_status = safe_cap(st.get("status", "pendiente"))
        st_name = safe_str(st.get("name", ""))
        st_assignees = st.get("assignees", [])
        assignees_str = ", ".join(st_assignees) if st_assignees else "sin asignar"
        
        if st_name:
            lines.append(f"- [{st_status}] {st_name} (asignado: {assignees_str})")
    
    return (f"\n\n**Subtareas ({len(lines)}):**\n" + "\n".join(lines)) if lines else ""


# -----------------------------
# Carga de tareas
# -----------------------------
def load_tasks(path: Path) -> List[Dict[str, Any]]:
    """Carga las tareas limpias desde JSONL."""
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {path}")
    tasks: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                tasks.append(json.loads(line))
            except Exception:
                # Ignora líneas corruptas pero continúa
                continue
    return tasks


# -----------------------------
# Transformación a Markdown + metadatos
# -----------------------------
def generate_markdown(task: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte una tarea limpia en texto markdown sin símbolos ni emojis, de forma robusta."""
    # Campos base con tolerancia
    name = safe_str(task.get("name") or task.get("title") or "Sin título")
    
    # Usar campos optimizados del clean script (con fallback a versión antigua)
    status_norm = safe_str(task.get("status") or "unknown")
    status_display = safe_str(task.get("status_display") or task.get("estado") or safe_cap(status_norm, default="Desconocido"))
    
    # Prioridad con campos optimizados
    priority_norm = safe_str(task.get("priority") or task.get("priority_level") or "unknown")
    priority_display = safe_str(task.get("priority_display") or safe_cap(priority_norm, default="Sin definir"))

    sprint = safe_str(task.get("sprint") or task.get("list") or "")
    project = safe_str(task.get("project") or "")
    assignees_disp = render_assignees(task.get("assignees"))
    creator = safe_str(task.get("creator") or "")

    date_created = safe_str(task.get("date_created") or task.get("created_at") or "")
    due_date = safe_str(task.get("due_date") or task.get("deadline") or "")

    # Convertir HTML a Markdown si es necesario
    raw_desc = task.get("description") or "Sin descripción disponible."
    description = html_to_markdown(safe_str(raw_desc)).strip()
    if not description:
        description = "Sin descripción disponible."

    # Flags / indicadores
    flags: List[str] = []
    if bool(task.get("is_blocked", False)):
        flags.append("Tarea BLOQUEADA por un impedimento o dependencia.")
    if bool(task.get("has_doubts", False)):
        flags.append("El responsable tiene dudas o necesita aclaración.")
    if bool(task.get("is_pending_review", False)):
        flags.append("Pendiente de revisión o QA.")
    if bool(task.get("is_overdue", False)):
        flags.append("La tarea está vencida respecto a su fecha límite.")
    # Urgente también como flag textual, aparte de priority
    if priority_norm == "urgent":
        flags.append("Marcada como URGENTE.")
    if not flags:
        flags.append("Sin incidencias registradas.")
    flag_text = "\n".join(f"- {f}" for f in flags)

    # Comentarios y subtareas
    comments_section = render_comments(task.get("comments"))
    subtasks_text = render_subtasks(task.get("subtasks"))
    
    # Etiquetas (tags) - CRÍTICO para búsquedas
    tags_display = render_tags(task.get("tags"))
    tags_section = f"\n**Etiquetas:** {tags_display}" if tags_display != "—" else ""

    # Markdown final con etiquetas naturales
    text_md = f"""### Tarea: {name}
**Estado:** {status_display}
**Prioridad:** {priority_display}
**Sprint:** {sprint}
**Proyecto:** {project}
**Asignado a:** {assignees_disp}
**Creador:** {creator}
**Fecha de creación:** {date_created}
**Fecha de vencimiento:** {due_date}{tags_section}

**Descripción:**
{description}

**Indicadores:**
{flag_text}
{subtasks_text}
{comments_section}
""".strip()

    # Metadatos para filtrado o indexación (si no existen, defaults seguros)
    metadata: Dict[str, Any] = {
        "task_id": task.get("task_id") or task.get("id") or "",
        "name": name,
        "status": status_norm,              # normalizado (done, in_progress, to_do, unknown)
        "priority": priority_norm,          # normalizado (urgent, high, normal, low, unknown)
        "sprint": sprint,
        "project": project,
        "assignees": task.get("assignees") or [],
        "is_subtask": bool(task.get("is_subtask", False)),
        "parent_task_id": task.get("parent_task_id"),
        "is_blocked": bool(task.get("is_blocked", False)),
        "has_doubts": bool(task.get("has_doubts", False)),
        "is_pending_review": bool(task.get("is_pending_review", False)),
        "is_overdue": bool(task.get("is_overdue", False)),
        # Comentarios
        "has_comments": bool(task.get("has_comments", False)),
        "comments_count": int(task.get("comments_count") or 0),
        "comments": task.get("comments") or [],  # Lista completa de comentarios
        # Subtareas
        "has_subtasks": bool(task.get("has_subtasks", False)),
        "subtasks_count": int(task.get("subtasks_count") or 0),
        "subtasks": task.get("subtasks") or [],  # Lista completa de subtareas
        # Extras útiles que a veces están presentes:
        "tags": task.get("tags") or [],
        "creator": creator,
        "date_created": date_created,
        "due_date": due_date,
    }

    return {"text": text_md, "metadata": metadata}


# -----------------------------
# Main
# -----------------------------
def main():
    print(f"📂 Leyendo tareas limpias desde: {INPUT_PATH}")
    tasks = load_tasks(INPUT_PATH)

    markdown_tasks = [generate_markdown(t) for t in tqdm(tasks, desc="🧩 Generando markdown limpio")]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for t in markdown_tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    print(f"✅ Archivo de tareas markdown limpio generado en: {OUTPUT_PATH}")
    print(f"🧮 Total de tareas procesadas: {len(markdown_tasks)}")


if __name__ == "__main__":
    main()
