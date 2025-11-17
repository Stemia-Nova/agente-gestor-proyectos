#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de informes profesionales para Project Managers y Scrum Masters.
Utiliza Jinja2 para plantillas y estructura profesional con análisis de bloqueos.
Soporta exportación a PDF con reportlab.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Any, Optional
from jinja2 import Template
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

# Mapeo de prioridades a español
PRIORITY_TO_SPANISH = {
    "urgent": "Urgente",
    "high": "Alta",
    "normal": "Normal",
    "low": "Baja",
    "unknown": "Sin prioridad",
}

# Mapeo de estados a español
STATUS_TO_SPANISH = {
    "to_do": "Pendiente",
    "in_progress": "En Progreso",
    "done": "Completada",
    "qa": "En QA",
    "review": "En Revisión",
    "blocked": "Bloqueada",
    "cancelled": "Cancelada",
    "unknown": "Sin estado",
}

def translate_priority(priority: str) -> str:
    """Traduce prioridad de inglés a español."""
    return PRIORITY_TO_SPANISH.get(priority.lower() if priority else "", "Sin prioridad")

def translate_status(status: str) -> str:
    """Traduce estado de inglés a español."""
    return STATUS_TO_SPANISH.get(status.lower() if status else "", "Sin estado")


SPRINT_REPORT_TEMPLATE = """# 📊 Informe de Sprint: **{{ sprint_name }}**

**Fecha:** {{ fecha }}  
**Preparado para:** {{ destinatario }}

---

## 📈 Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Total de Tareas** | {{ total_tareas }} |
| **✅ Completadas** | {{ completadas }} (**{{ porcentaje_completitud }}%**) |
| **🔄 En Progreso** | {{ en_progreso }} |
| **⏳ Pendientes** | {{ pendientes }} |
| **🔍 En QA/Review** | {{ qa }}/{{ review }} |
| **⚠️ Bloqueadas** | {{ bloqueadas }}{% if bloqueadas > 0 %} 🚨 **REQUIERE ATENCIÓN**{% endif %} |
| **🔥 Alta Prioridad** | {{ alta_prioridad }} |

---

## 📋 Detalle de Tareas

{% if tareas_completadas %}
### ✅ Tareas Completadas ({{ tareas_completadas|length }})

{% for tarea in tareas_completadas %}
{{ loop.index }}. **{{ tarea.name }}**
   - 👤 Asignado: {{ tarea.assignees }}
   - 🎯 Prioridad: {{ tarea.priority_spanish }}
   {% if tarea.subtasks_count and tarea.subtasks_count|int > 0 %}- 📎 Subtareas: {{ tarea.subtasks_count }}
   {% endif %}{% if tarea.comments_count and tarea.comments_count|int > 0 %}- 💬 Comentarios: {{ tarea.comments_count }}
   {% endif %}
{% endfor %}

{% endif %}
{% if tareas_en_progreso %}
### 🔄 En Progreso ({{ tareas_en_progreso|length }})

{% for tarea in tareas_en_progreso %}
{{ loop.index }}. **{{ tarea.name }}**
   - 👤 Asignado: {{ tarea.assignees }}
   - 🎯 Prioridad: {{ tarea.priority_spanish }}
   {% if tarea.subtasks_count and tarea.subtasks_count|int > 0 %}- 📎 Subtareas: {{ tarea.subtasks_count }}
   {% endif %}{% if tarea.comments_count and tarea.comments_count|int > 0 %}- 💬 Comentarios: {{ tarea.comments_count }}
   {% endif %}
{% endfor %}

{% endif %}
{% if tareas_pendientes %}
### ⏳ Pendientes ({{ tareas_pendientes|length }})

{% for tarea in tareas_pendientes %}
{{ loop.index }}. **{{ tarea.name }}**
   - 👤 Asignado: {{ tarea.assignees }}
   - 🎯 Prioridad: {{ tarea.priority_spanish }}
   {% if tarea.subtasks_count and tarea.subtasks_count|int > 0 %}- 📎 Subtareas: {{ tarea.subtasks_count }}
   {% endif %}{% if tarea.comments_count and tarea.comments_count|int > 0 %}- 💬 Comentarios: {{ tarea.comments_count }}
   {% endif %}
{% endfor %}

{% endif %}
{% if tareas_bloqueadas %}
---

## 🚨 Bloqueos Críticos - Acción Inmediata Requerida

{% for tarea in tareas_bloqueadas %}
### {{ loop.index }}. {{ tarea.name }}

- **Estado:** {{ tarea.status_spanish }}
- **Asignado:** {{ tarea.assignees }}
- **Prioridad:** {{ tarea.priority_spanish }}
{% if tarea.subtasks_count and tarea.subtasks_count|int > 0 %}- **Subtareas:** 📎 {{ tarea.subtasks_count }}
{% endif %}{% if tarea.comments_count and tarea.comments_count|int > 0 %}- **Comentarios:** 💬 {{ tarea.comments_count }}
{% endif %}{% if tarea.blocked_reason %}- **Motivo del bloqueo:** {{ tarea.blocked_reason }}
{% else %}- **Motivo:** ⚠️ NO ESPECIFICADO (requiere investigación)
{% endif %}- **Acción recomendada:** {% if tarea.priority == 'urgent' %}🔥 ESCALACIÓN INMEDIATA AL CLIENTE{% else %}Reunión con el equipo para desbloquear{% endif %}

{% endfor %}

### 🔴 Acciones Requeridas

{% for tarea in tareas_bloqueadas %}
- Desbloquear **"{{ tarea.name }}"** ({{ tarea.assignees }})
  {% if not tarea.blocked_reason %}- → Prioridad: Documentar motivo del bloqueo{% endif %}
  {% if tarea.priority in ['urgent', 'high'] %}- → Requiere reunión con cliente{% endif %}
{% endfor %}

{% endif %}
{% if tareas_alta_prioridad %}
---

## 🔥 Tareas de Alta Prioridad

{% for tarea in tareas_alta_prioridad %}
{{ loop.index }}. **{{ tarea.name }}**
   - **Estado:** {{ tarea.status_spanish }}
   - **Asignado:** {{ tarea.assignees }}
   - **Prioridad:** {{ tarea.priority_spanish }}
   {% if tarea.subtasks_count and tarea.subtasks_count|int > 0 %}- 📎 Subtareas: {{ tarea.subtasks_count }}
   {% endif %}{% if tarea.comments_count and tarea.comments_count|int > 0 %}- 💬 Comentarios: {{ tarea.comments_count }}
   {% endif %}
{% endfor %}
{% endif %}

---

## 💡 Recomendaciones

{% if bloqueadas > 0 %}
> **⚠️ PRIORIDAD ALTA:** Resolver **{{ bloqueadas }} bloqueo(s)** antes de continuar
> - Programar reunión urgente para desbloqueo
> - Documentar causas raíz de bloqueos

{% endif %}
{% if porcentaje_completitud < 50 %}
> **📌 Sprint con avance bajo ({{ porcentaje_completitud }}%)**
> - Revisar capacidad del equipo
> - Identificar impedimentos
> - Considerar replanificación

{% elif porcentaje_completitud >= 80 %}
> **✅ Sprint en buen ritmo ({{ porcentaje_completitud }}%)**
> - Mantener momentum
> - Preparar siguiente sprint

{% endif %}
{% if alta_prioridad > 0 %}
> **🎯 Foco:** {{ alta_prioridad }} tarea(s) de alta prioridad pendientes

{% endif %}

---

*Informe generado automáticamente por el Agente Gestor de Proyectos*
"""


class ReportGenerator:
    """Genera informes profesionales para PMs y Scrum Masters."""

    def __init__(self):
        self.template = Template(SPRINT_REPORT_TEMPLATE)

    def generate_sprint_report(
        self, 
        sprint_name: str, 
        metrics: Dict[str, Any], 
        tasks: List[Dict[str, Any]],
        destinatario: str = "Project Manager / Scrum Master"
    ) -> str:
        """
        Genera un informe profesional de sprint con estructura clara.
        
        Args:
            sprint_name: Nombre del sprint (ej: "Sprint 2")
            metrics: Diccionario con métricas del sprint
            tasks: Lista de tareas con metadata completa
            destinatario: A quién va dirigido el informe
            
        Returns:
            Informe formateado en texto
        """
        # Traducir prioridades y estados a español en todas las tareas
        for task in tasks:
            if 'priority' in task:
                task['priority_spanish'] = translate_priority(task['priority'])
            else:
                task['priority_spanish'] = "Sin prioridad"
            
            if 'status' in task:
                task['status_spanish'] = translate_status(task['status'])
            else:
                task['status_spanish'] = "Sin estado"
        
        # Clasificar tareas por estado (soporte español e inglés)
        tareas_completadas = [t for t in tasks if t.get('status') in ['done', 'Completada']]
        tareas_en_progreso = [t for t in tasks if t.get('status') in ['in_progress', 'En progreso']]
        tareas_pendientes = [t for t in tasks if t.get('status') in ['to_do', 'Pendiente']]
        tareas_bloqueadas = [t for t in tasks if t.get('is_blocked')]
        tareas_alta_prioridad = [t for t in tasks if t.get('priority') in ['urgent', 'high', 'Urgente', 'Alta']]
        
        # Preparar contexto para la plantilla
        context = {
            'sprint_name': sprint_name,
            'fecha': datetime.now().strftime("%d/%m/%Y %H:%M"),
            'destinatario': destinatario,
            'total_tareas': metrics.get('total', len(tasks)),
            'completadas': metrics.get('completadas', len(tareas_completadas)),
            'porcentaje_completitud': metrics.get('porcentaje_completitud', 0),
            'en_progreso': metrics.get('en_progreso', len(tareas_en_progreso)),
            'pendientes': metrics.get('pendientes', len(tareas_pendientes)),
            'qa': metrics.get('qa', 0),
            'review': metrics.get('review', 0),
            'bloqueadas': metrics.get('bloqueadas', len(tareas_bloqueadas)),
            'alta_prioridad': metrics.get('alta_prioridad', len(tareas_alta_prioridad)),
            'tareas_completadas': tareas_completadas,
            'tareas_en_progreso': tareas_en_progreso,
            'tareas_pendientes': tareas_pendientes,
            'tareas_bloqueadas': tareas_bloqueadas,
            'tareas_alta_prioridad': tareas_alta_prioridad,
        }
        
        return self.template.render(**context)

    def export_to_pdf(
        self,
        sprint_name: str,
        metrics: Dict[str, Any],
        tasks: List[Dict[str, Any]],
        output_path: str,
        destinatario: str = "Project Manager / Scrum Master"
    ) -> Optional[str]:
        """
        Exporta el informe de sprint a PDF profesional.
        
        Args:
            sprint_name: Nombre del sprint
            metrics: Métricas del sprint
            tasks: Lista de tareas
            output_path: Ruta donde guardar el PDF
            destinatario: A quién va dirigido
            
        Returns:
            Optional[str]: Ruta del PDF generado o None en caso de error
        """
        try:
            # Traducir prioridades a español en todas las tareas
            for task in tasks:
                if 'priority' in task:
                    task['priority_spanish'] = translate_priority(task['priority'])
                else:
                    task['priority_spanish'] = "Sin prioridad"
                
                if 'status' in task:
                    task['status_spanish'] = translate_status(task['status'])
                else:
                    task['status_spanish'] = "Sin estado"
            
            # Clasificar tareas
            tareas_completadas = [t for t in tasks if t.get('status') == 'done']
            tareas_en_progreso = [t for t in tasks if t.get('status') == 'in_progress']
            tareas_pendientes = [t for t in tasks if t.get('status') == 'to_do']
            tareas_bloqueadas = [t for t in tasks if t.get('is_blocked')]
            tareas_alta_prioridad = [t for t in tasks if t.get('priority') in ['urgent', 'high']]
            
            # Crear documento PDF
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Estilos personalizados
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#2c5aa0'),
                spaceBefore=20,
                spaceAfter=10,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                leading=14
            )
            
            # Título
            story.append(Paragraph(f"INFORME DE SPRINT - {sprint_name}", title_style))
            story.append(Paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style))
            story.append(Paragraph(f"Preparado para: {destinatario}", normal_style))
            story.append(Spacer(1, 0.5*cm))
            
            # Resumen Ejecutivo
            story.append(Paragraph("📊 RESUMEN EJECUTIVO", heading_style))
            
            resumen_data = [
                ['Métrica', 'Valor'],
                ['Total de Tareas', str(metrics.get('total', len(tasks)))],
                ['Completadas', f"{metrics.get('completadas', 0)} ({metrics.get('porcentaje_completitud', 0)}%)"],
                ['En Progreso', str(metrics.get('en_progreso', 0))],
                ['Pendientes', str(metrics.get('pendientes', 0))],
                ['En QA/Review', f"{metrics.get('qa', 0)}/{metrics.get('review', 0)}"],
                ['Bloqueadas ⚠️', str(metrics.get('bloqueadas', 0))],
                ['Alta Prioridad', str(metrics.get('alta_prioridad', 0))],
            ]
            
            resumen_table = Table(resumen_data, colWidths=[8*cm, 8*cm])
            resumen_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
            ]))
            
            story.append(resumen_table)
            story.append(Spacer(1, 0.5*cm))
            
            # Bloqueos Críticos
            if tareas_bloqueadas:
                story.append(Paragraph("⚠️ BLOQUEOS CRÍTICOS - REQUIERE ACCIÓN INMEDIATA", heading_style))
                
                for i, tarea in enumerate(tareas_bloqueadas, 1):
                    story.append(Paragraph(
                        f"<b>{i}. {tarea.get('name', 'Sin nombre')}</b>",
                        normal_style
                    ))
                    story.append(Paragraph(
                        f"• Estado: {tarea.get('status_spanish', 'N/A')}",
                        normal_style
                    ))
                    story.append(Paragraph(
                        f"• Asignado: {tarea.get('assignees', 'Sin asignar')}",
                        normal_style
                    ))
                    story.append(Paragraph(
                        f"• Prioridad: {tarea.get('priority_spanish', 'Sin prioridad')}",
                        normal_style
                    ))
                    
                    # Subtareas y comentarios
                    if tarea.get('subtasks_count') and int(tarea['subtasks_count']) > 0:
                        story.append(Paragraph(
                            f"• Subtareas: {tarea['subtasks_count']}",
                            normal_style
                        ))
                    if tarea.get('comments_count') and int(tarea['comments_count']) > 0:
                        story.append(Paragraph(
                            f"• Comentarios: {tarea['comments_count']}",
                            normal_style
                        ))
                    
                    # Descripción si está disponible
                    if tarea.get('description'):
                        desc = tarea['description'][:200] + ('...' if len(tarea['description']) > 200 else '')
                        story.append(Paragraph(
                            f"• Descripción: {desc}",
                            normal_style
                        ))
                    
                    # URL de ClickUp
                    if tarea.get('url'):
                        story.append(Paragraph(
                            f"• Link: <link href='{tarea['url']}'>{tarea['url']}</link>",
                            normal_style
                        ))
                    
                    if tarea.get('blocked_reason'):
                        story.append(Paragraph(
                            f"• Motivo del bloqueo: {tarea['blocked_reason']}",
                            normal_style
                        ))
                    else:
                        story.append(Paragraph(
                            "• Motivo: <b>NO ESPECIFICADO</b> (requiere investigación)",
                            normal_style
                        ))
                    
                    # Acción recomendada
                    if tarea.get('priority') in ['urgent', 'high']:
                        story.append(Paragraph(
                            "• Acción: <b>🔥 ESCALACIÓN INMEDIATA AL CLIENTE</b>",
                            normal_style
                        ))
                    else:
                        story.append(Paragraph(
                            "• Acción: Reunión con el equipo para desbloquear",
                            normal_style
                        ))
                    
                    story.append(Spacer(1, 0.3*cm))
                
                # Acciones requeridas
                story.append(Paragraph("<b>🔴 ACCIONES REQUERIDAS:</b>", normal_style))
                for tarea in tareas_bloqueadas:
                    story.append(Paragraph(
                        f"→ Desbloquear \"{tarea.get('name', 'Sin nombre')}\" ({tarea.get('assignees', 'Sin asignar')})",
                        normal_style
                    ))
                    if not tarea.get('blocked_reason'):
                        story.append(Paragraph(
                            "  → Prioridad: Documentar motivo del bloqueo",
                            normal_style
                        ))
                
                story.append(Spacer(1, 0.5*cm))
            
            # Tareas de Alta Prioridad
            if tareas_alta_prioridad:
                story.append(Paragraph(f"🔥 TAREAS DE ALTA PRIORIDAD ({len(tareas_alta_prioridad)})", heading_style))
                for i, tarea in enumerate(tareas_alta_prioridad, 1):
                    story.append(Paragraph(
                        f"<b>{i}. {tarea.get('name', 'Sin nombre')}</b>",
                        normal_style
                    ))
                    story.append(Paragraph(
                        f"• Estado: {tarea.get('status_spanish', 'N/A')}",
                        normal_style
                    ))
                    story.append(Paragraph(
                        f"• Asignado: {tarea.get('assignees', 'Sin asignar')}",
                        normal_style
                    ))
                    story.append(Paragraph(
                        f"• Prioridad: {tarea.get('priority_spanish', 'Sin prioridad')}",
                        normal_style
                    ))
                    if tarea.get('subtasks_count') and int(tarea['subtasks_count']) > 0:
                        story.append(Paragraph(f"• Subtareas: {tarea['subtasks_count']}", normal_style))
                    if tarea.get('comments_count') and int(tarea['comments_count']) > 0:
                        story.append(Paragraph(f"• Comentarios: {tarea['comments_count']}", normal_style))
                    story.append(Spacer(1, 0.2*cm))
                story.append(Spacer(1, 0.3*cm))
            
            # Tareas Completadas
            if tareas_completadas:
                story.append(Paragraph(f"✅ TAREAS COMPLETADAS ({len(tareas_completadas)})", heading_style))
                for i, tarea in enumerate(tareas_completadas, 1):
                    details = f"{i}. {tarea.get('name', 'Sin nombre')} - {tarea.get('assignees', 'Sin asignar')}"
                    extras = []
                    if tarea.get('subtasks_count') and int(tarea['subtasks_count']) > 0:
                        extras.append(f"📎 {tarea['subtasks_count']}")
                    if tarea.get('comments_count') and int(tarea['comments_count']) > 0:
                        extras.append(f"💬 {tarea['comments_count']}")
                    if extras:
                        details += f" ({', '.join(extras)})"
                    story.append(Paragraph(details, normal_style))
                story.append(Spacer(1, 0.3*cm))
            
            # Tareas en Progreso
            if tareas_en_progreso:
                story.append(Paragraph(f"🔄 EN PROGRESO ({len(tareas_en_progreso)})", heading_style))
                for i, tarea in enumerate(tareas_en_progreso, 1):
                    details = f"{i}. {tarea.get('name', 'Sin nombre')} - {tarea.get('assignees', 'Sin asignar')}"
                    extras = []
                    if tarea.get('subtasks_count') and int(tarea['subtasks_count']) > 0:
                        extras.append(f"📎 {tarea['subtasks_count']}")
                    if tarea.get('comments_count') and int(tarea['comments_count']) > 0:
                        extras.append(f"💬 {tarea['comments_count']}")
                    if extras:
                        details += f" ({', '.join(extras)})"
                    story.append(Paragraph(details, normal_style))
                story.append(Spacer(1, 0.3*cm))
            
            # Tareas Pendientes
            if tareas_pendientes:
                story.append(Paragraph(f"⏳ PENDIENTES ({len(tareas_pendientes)})", heading_style))
                for i, tarea in enumerate(tareas_pendientes[:10], 1):  # Limitar a 10 para no saturar
                    details = f"{i}. {tarea.get('name', 'Sin nombre')} - {tarea.get('assignees', 'Sin asignar')}"
                    extras = []
                    if tarea.get('subtasks_count') and int(tarea['subtasks_count']) > 0:
                        extras.append(f"📎 {tarea['subtasks_count']}")
                    if tarea.get('comments_count') and int(tarea['comments_count']) > 0:
                        extras.append(f"💬 {tarea['comments_count']}")
                    if extras:
                        details += f" ({', '.join(extras)})"
                    story.append(Paragraph(details, normal_style))
                if len(tareas_pendientes) > 10:
                    story.append(Paragraph(f"... y {len(tareas_pendientes) - 10} más", normal_style))
                story.append(Spacer(1, 0.3*cm))
            
            # Recomendaciones
            story.append(Paragraph("💡 RECOMENDACIONES", heading_style))
            
            recomendaciones = []
            if metrics.get('bloqueadas', 0) > 0:
                recomendaciones.append(f"⚠️ PRIORIDAD ALTA: Resolver {metrics['bloqueadas']} bloqueo(s)")
                recomendaciones.append("→ Programar reunión urgente para desbloqueo")
            
            porcentaje = metrics.get('porcentaje_completitud', 0)
            if porcentaje < 50:
                recomendaciones.append(f"📌 Sprint con avance bajo ({porcentaje}%)")
                recomendaciones.append("→ Revisar capacidad del equipo")
            elif porcentaje >= 80:
                recomendaciones.append(f"✅ Sprint en buen ritmo ({porcentaje}%)")
                recomendaciones.append("→ Mantener momentum")
            
            if metrics.get('alta_prioridad', 0) > 0:
                recomendaciones.append(f"🎯 Foco: {metrics['alta_prioridad']} tarea(s) de alta prioridad")
            
            for rec in recomendaciones:
                story.append(Paragraph(rec, normal_style))
            
            # Construir PDF
            doc.build(story)
            
            print(f"✅ Informe exportado exitosamente a: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error al exportar PDF: {str(e)}")
            return None
