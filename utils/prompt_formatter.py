#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convierte datos estructurados del RAG en texto legible para prompts del LLM.
Uso:
    from utils.prompt_formatter import PromptFormatter
"""

from typing import Any, Dict, List


class PromptFormatter:
    """Formateador de datos agregados y listas de tareas para informes o contexto LLM."""

    @staticmethod
    def aggregates_to_text(agg: Dict[str, Any]) -> str:
        """Convierte métricas agregadas en texto legible."""
        return (
            f"- Total tareas: {agg.get('total', 0)}\n"
            f"- Finalizadas: {agg.get('done', 0)}\n"
            f"- En progreso: {agg.get('in_progress', 0)}\n"
            f"- Pendientes: {agg.get('todo', 0)}\n"
            f"- Bloqueadas: {agg.get('blocked', 0)}\n"
            f"- Por sprint: "
            + ", ".join(f"{s} ({n})" for s, n in agg.get("by_sprint", {}).items())
            + "\n- Por persona: "
            + ", ".join(f"{a} ({n})" for a, n in agg.get("by_assignee", {}).items())
        )

    @staticmethod
    def tasks_to_text(tasks: List[Dict[str, Any]]) -> str:
        """Convierte lista de tareas en texto legible para contexto de prompt."""
        if not tasks:
            return "No hay tareas registradas en este conjunto."

        lines = []
        for t in tasks:
            lines.append(
                f"- [{t.get('task_id', '?')}] {t.get('status', 'sin estado')}, "
                f"prioridad {t.get('priority', 'N/A')}, asignado a {t.get('assignees', 'sin asignar')} "
                f"(Sprint {t.get('sprint', '-')})"
            )
        return "\n".join(lines)
