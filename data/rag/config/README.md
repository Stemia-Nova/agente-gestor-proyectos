# 🔧 Configuración de Mapeos de ClickUp

Este directorio contiene archivos de configuración para adaptar el sistema a diferentes proyectos y configuraciones de ClickUp.

## 📄 Archivos

### `clickup_mappings.json`

Archivo centralizado con todos los mapeos configurables:

#### **Estados (status_mappings)**

Define cómo se normalizan los estados de ClickUp a categorías estándar del sistema.

```json
{
  "to_do": ["to do", "todo", "open", "por hacer", "pendiente"],
  "in_progress": ["in progress", "doing", "en progreso"],
  ...
}
```

**Categorías estándar:**

- `to_do`: Tareas por iniciar
- `in_progress`: Tareas en desarrollo
- `done`: Tareas completadas
- `qa`: En proceso de testing
- `review`: En revisión de código/calidad
- `blocked`: Bloqueadas
- `cancelled`: Canceladas
- `needs_info`: Esperando información

#### **Prioridades (priority_mappings)**

Define cómo se normalizan las prioridades.

```json
{
  "urgent": ["urgent", "urgente", "crítico", "1"],
  "high": ["high", "alta", "2"],
  ...
}
```

**Niveles estándar:**

- `urgent`: Máxima prioridad
- `high`: Alta prioridad
- `normal`: Prioridad normal
- `low`: Baja prioridad

#### **Tags Críticas (critical_tags_for_comments)**

Lista de tags que indican que una tarea debería tener sus comentarios descargados.

```json
[
  "bloqueada",
  "data",
  "duda",
  "review",
  ...
]
```

#### **Traducciones al Español (spanish_translations)**

Traducciones para mostrar en informes y respuestas del chatbot.

---

## 🚀 Cómo Usar

### Opción 1: Usar configuración actual (recomendado)

El sistema actualmente usa mapeos hardcodeados en el código. Los archivos de configuración están preparados para migración futura.

### Opción 2: Migrar a configuración externa (TODO)

**Pasos para implementar:**

1. **Modificar `01_clean_clickup_tasks.py`:**

```python
import json
from pathlib import Path

# Cargar configuración
config_path = Path(__file__).parent.parent / "config" / "clickup_mappings.json"
with open(config_path, 'r', encoding='utf-8') as f:
    MAPPINGS = json.load(f)

def normalize_status(raw: str, status_type: str = None) -> str:
    if not raw:
        return "unknown"

    raw_lower = raw.lower().strip()

    # Buscar en mapeos
    for standard_status, variants in MAPPINGS["status_mappings"].items():
        if raw_lower in variants:
            return standard_status

    return "custom"
```

2. **Modificar `get_clickup_tasks.py`:**

```python
# Cargar tags críticas desde config
CRITICAL_TAGS = MAPPINGS["critical_tags_for_comments"]

def should_fetch_comments(task: dict) -> bool:
    tags = task.get("tags", [])
    tag_names = [tag.get("name", "").lower() for tag in tags]
    return any(critical in tag for tag in tag_names for critical in CRITICAL_TAGS)
```

3. **Modificar `report_generator.py`:**

```python
# Usar traducciones desde config
PRIORITY_TO_SPANISH = MAPPINGS["spanish_translations"]["priority"]
STATUS_TO_SPANISH = MAPPINGS["spanish_translations"]["status"]
```

---

## 🔄 Adaptación a Nuevos Proyectos

Para adaptar a un nuevo proyecto con diferentes configuraciones de ClickUp:

1. **Copia el archivo de configuración:**

```bash
cp clickup_mappings.json clickup_mappings_proyecto_nuevo.json
```

2. **Edita los mapeos según tu proyecto:**

   - Revisa los estados personalizados en tu espacio de ClickUp
   - Ajusta los nombres en español si usas otro idioma
   - Agrega/modifica tags críticas según tus necesidades

3. **Actualiza el código para usar el nuevo archivo:**

```python
CONFIG_FILE = os.getenv("CLICKUP_CONFIG", "clickup_mappings.json")
config_path = Path(__file__).parent.parent / "config" / CONFIG_FILE
```

---

## 📋 Verificación de Mapeos

Para verificar que tus mapeos cubren todos los estados de tu proyecto:

```python
# Script para listar estados únicos en tus datos
import json

with open('data/rag/ingest/clickup_tasks_all_FECHA.json', 'r') as f:
    tasks = json.load(f)

estados_unicos = set()
for task in tasks:
    estado = task.get('status', {}).get('status', '')
    if estado:
        estados_unicos.add(estado.lower())

print("Estados encontrados en tus tareas:")
for estado in sorted(estados_unicos):
    print(f"  - {estado}")
```

---

## 🐛 Troubleshooting

### Problema: Tareas con estado "custom" o "unknown"

**Solución:** Revisa el log de transformación y agrega los estados faltantes a `status_mappings`.

### Problema: Prioridades no traducidas

**Solución:** Verifica que todos los valores de prioridad de ClickUp estén en `priority_mappings`.

### Problema: Comentarios no se descargan

**Solución:** Revisa que las tags estén en `critical_tags_for_comments` o verifica que `comment_count > 0`.

---

## 📚 Referencias

- [ClickUp API - Get Tasks](https://clickup.com/api/clickupreference/operation/GetTasks/)
- [ClickUp API - Task Comments](https://clickup.com/api/clickupreference/operation/GetTaskComments/)
- [ClickUp Custom Statuses](https://help.clickup.com/hc/en-us/articles/6310449699095-Custom-Statuses)

---

## ⚠️ TODOs

- [ ] Implementar carga automática de configuración en `01_clean_clickup_tasks.py`
- [ ] Implementar carga automática de configuración en `get_clickup_tasks.py`
- [ ] Implementar carga automática de configuración en `report_generator.py`
- [ ] Agregar validación de schema para archivo de configuración
- [ ] Crear tests unitarios para verificar mapeos
- [ ] Agregar comando CLI para validar configuración
- [ ] Documentar cómo verificar `comment_count` en API de ClickUp
