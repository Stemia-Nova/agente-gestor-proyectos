# 📄 Guía de Generación de Informes PDF

## 🎯 Funcionalidades Implementadas

El sistema ahora soporta la generación de **informes profesionales** para Project Managers y Scrum Masters en dos formatos:

- **Texto plano**: Para visualización rápida en el chat
- **PDF**: Para compartir con stakeholders, enviar por email, o archivar

---

## 📊 Características del Informe

### Secciones Incluidas

1. **📊 Resumen Ejecutivo**

   - Total de tareas
   - Completadas con porcentaje
   - En progreso, pendientes, QA/Review
   - Bloqueadas (con alerta si hay)
   - Tareas de alta prioridad

2. **⚠️ Bloqueos Críticos** (si existen)

   - Lista detallada de tareas bloqueadas
   - Asignado, prioridad, motivo del bloqueo
   - Acciones recomendadas específicas
   - Detecta si no hay motivo documentado

3. **📋 Detalle de Tareas**

   - ✅ Tareas completadas
   - 🔄 En progreso
   - ⏳ Pendientes

4. **🔥 Tareas de Alta Prioridad**

   - Lista de tareas urgentes/high priority
   - Estado actual de cada una

5. **💡 Recomendaciones**
   - Análisis automático del avance del sprint
   - Acciones requeridas según el estado
   - Sugerencias para reuniones con cliente

---

## 🚀 Cómo Usar

### Desde el Chatbot

#### Informe en texto

```
Usuario: Genera informe del Sprint 2
Usuario: Dame el reporte del Sprint 3
Usuario: Necesito un informe del Sprint 1
```

#### Informe en PDF

```
Usuario: Genera informe PDF del Sprint 2
Usuario: Dame el reporte en PDF del Sprint 3
Usuario: Exporta informe PDF del Sprint 1
```

### Desde Código Python

```python
from utils.hybrid_search import HybridSearch

search = HybridSearch()

# Informe en texto
report_text = search.generate_report("Sprint 2", "Scrum Master")
print(report_text)

# Informe en PDF
result = search.generate_report_pdf(
    sprint="Sprint 2",
    output_path="data/logs/informe_sprint2.pdf",
    destinatario="Project Manager"
)
print(result)
```

---

## 📁 Ubicación de Archivos

Los PDFs se generan automáticamente en:

```
data/logs/informe_sprint_1.pdf
data/logs/informe_sprint_2.pdf
data/logs/informe_sprint_3.pdf
```

---

## 🎨 Formato del PDF

- **Tamaño**: A4
- **Fuente**: Helvetica
- **Colores**:
  - Encabezados: Azul (#2c5aa0)
  - Tablas: Fondo beige con bordes negros
  - Títulos: Negro (#1a1a1a)
- **Estructura**: Profesional con espaciado adecuado

---

## 📊 Análisis Automático

El sistema analiza automáticamente:

### Avance del Sprint

- **< 50%**: "Sprint con avance bajo" → Recomienda revisar capacidad
- **≥ 80%**: "Sprint en buen ritmo" → Recomienda mantener momentum

### Bloqueos

- Detecta tareas bloqueadas
- Identifica si falta documentar el motivo
- Recomienda reuniones urgentes
- Sugiere escalación para prioridades urgent

### Prioridades

- Destaca tareas de alta prioridad pendientes
- Recomienda foco específico

---

## 🔧 Dependencias

```bash
pip install reportlab  # Ya instalado
```

---

## 📝 Ejemplo de Salida

### Comando

```
Usuario: Genera informe PDF del Sprint 3
```

### Respuesta

```
✅ Informe exportado exitosamente a: data/logs/informe_sprint_3.pdf
```

### Contenido del PDF

```
═══════════════════════════════════════════════════════════
                   INFORME DE SPRINT - Sprint 3
═══════════════════════════════════════════════════════════
Fecha: 14/11/2025 09:13
Preparado para: Scrum Master

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RESUMEN EJECUTIVO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Tabla con métricas]

⚠️ BLOQUEOS CRÍTICOS - REQUIERE ACCIÓN INMEDIATA
[Detalles de bloqueos con acciones recomendadas]

💡 RECOMENDACIONES
⚠️ PRIORIDAD ALTA: Resolver 1 bloqueo(s)
→ Programar reunión urgente para desbloqueo
...
```

---

## ✅ Ventajas del PDF

1. **Profesional**: Formato adecuado para stakeholders
2. **Compartible**: Fácil de enviar por email
3. **Archivable**: Registro histórico de sprints
4. **Portable**: No requiere software especial para ver
5. **Estructurado**: Información clara y organizada

---

## 🎯 Casos de Uso

1. **Daily Standup**: Informe rápido en texto
2. **Sprint Review**: PDF para compartir con cliente
3. **Reportes mensuales**: PDFs archivados de todos los sprints
4. **Escalaciones**: PDF con bloqueos para management
5. **Documentación**: Registro histórico del proyecto

---

## 🔄 Integración con Chainlit

Los comandos funcionan directamente desde la interfaz web:

```bash
# Iniciar el chatbot
source ./run_dev.sh

# En el chat:
"Genera informe PDF del Sprint 2"
```

El bot responderá con la confirmación y ruta del archivo generado.

---

## 📞 Soporte

Para problemas o sugerencias, revisar:

- `utils/report_generator.py` - Lógica de generación
- `utils/hybrid_search.py` - Método `generate_report_pdf()`
- Logs en consola para debugging
