# 🧠 Flujo de Datos — Agente Planificador (RAG Pipeline)

Este directorio contiene el flujo completo de procesamiento de datos que permite al agente construir su **base de conocimiento vectorial** a partir de las tareas de **ClickUp**.  
El objetivo es que el sistema pueda **responder preguntas contextuales** como:

> - ¿Qué tareas están bloqueadas en el sprint actual?  
> - ¿Cuántas tareas se completaron en el último sprint?  
> - ¿Qué tareas urgentes siguen abiertas?  

---

## ⚙️ 1️⃣ Configuración inicial

Antes de ejecutar cualquier script, asegúrate de tener el entorno configurado correctamente:

### 🔧 Archivo `.env` (en la raíz del proyecto)

```bash
CLICKUP_API_TOKEN=pk_xxxxxxxxxxxxx
CLICKUP_FOLDER_ID=901511269055
CLICKUP_INCLUDE_CLOSED=true
```

- **CLICKUP_API_TOKEN:** tu token personal de ClickUp (nivel admin o workspace).  
- **CLICKUP_FOLDER_ID:** el ID del folder (proyecto) que contiene tus sprints.  
  - Puedes obtenerlo desde la URL de ClickUp:  
    `https://app.clickup.com/<TEAM_ID>/v/o/f/<FOLDER_ID>?pr=<SPACE_ID>`  
- **CLICKUP_INCLUDE_CLOSED=true:** permite incluir tareas completadas en la descarga.

---

## 🚀 Flujo de scripts (paso a paso)

### 🔾 Paso 1 — Descargar tareas desde ClickUp  
**Script:** `data/rag/ingest/get_and_clean_clickup_tasks.py`

Este script conecta con la **API de ClickUp** para descargar todas las tareas de las **listas (sprints)** dentro del Folder configurado.  
Incluye tanto tareas abiertas como completadas.

**Qué hace:**
- Detecta automáticamente todos los sprints (`/folder/{id}/list`).
- Descarga las tareas de cada sprint (`/list/{id}/task?include_closed=true`).
- Guarda un JSON combinado con todas las tareas encontradas.
- Exporta también un CSV aplanado para inspección manual.

**Entrada:** `.env` con token y folder ID  
**Salida:**  
- `data/rag/ingest/clickup_tasks_all_YYYY-MM-DD.json`  
- `data/rag/ingest/clickup_tasks_all_YYYY-MM-DD.csv`

---

### 🔳 Paso 2 — Limpiar y normalizar las tareas  
**Script:** `utils/clean_tasks.py`

Toma el JSON crudo descargado desde ClickUp y genera un archivo limpio (`task_clean.jsonl`) con solo la información útil para el RAG.  
Cada línea del archivo representa una tarea normalizada.

**Qué hace:**
- Extrae campos relevantes: título, descripción, estado, sprint, responsable, prioridad, etiquetas.
- Mapea los estados de ClickUp a categorías comunes:
  - `to_do`, `in_progress`, `in_review`, `done`, `blocked`.
- Detecta etiquetas relevantes:
  - `"bloqueada"` → `is_blocked: true`
  - `"duda"` → `has_doubts: true`
  - `"urgente"` → `is_urgent: true`
- Convierte fechas a formato legible.
- Guarda el resultado en formato JSONL (una tarea por línea).

**Entrada:**  
`data/rag/ingest/clickup_tasks_all_YYYY-MM-DD.json`

**Salida:**  
`data/processed/task_clean.jsonl`

**Ejemplo de salida:**
```json
{
  "task_id": "86c6bbdtv",
  "name": "CREAR RAG",
  "description": "Desarrollar el pipeline de indexación vectorial.",
  "status": "in_progress",
  "date_created": "2025-11-04",
  "date_updated": "2025-11-05",
  "metadata": {
    "project": "Folder",
    "sprint": "Sprint 3",
    "priority": "",
    "assignees": "",
    "tags": "bloqueada",
    "is_blocked": true,
    "has_doubts": false,
    "is_urgent": false
  }
}
```

---

### 🔶 Paso 3 — Naturalizar tareas  
**Script:** `data/rag/transform/01_naturalize_tasks.py`

Convierte las tareas limpias en texto descriptivo, usando un lenguaje natural comprensible por el modelo de lenguaje.  
Este paso transforma datos estructurados en frases completas.

**Qué hace:**
- Lee `task_clean.jsonl`.
- Genera una versión narrativa de cada tarea, por ejemplo:

  > La tarea 'CREAR RAG' pertenece al proyecto 'Folder' en el sprint 'Sprint 3'.  
  > Actualmente está en progreso y tiene una prioridad normal.  
  > No tiene responsables asignados.  
  > Descripción: Desarrollar el pipeline de indexación vectorial para ClickUp.

**Entrada:**  
`data/processed/task_clean.jsonl`

**Salida:**  
`data/processed/task_natural.jsonl`

---

### 🔵 Paso 4 — Crear fragmentos (chunks)  
**Script:** `data/rag/chunk/02_chunk_tasks.py`

Divide los textos naturalizados en fragmentos más pequeños (“chunks”) que se pueden vectorizar de forma óptima.  
Esto mejora la precisión y el rendimiento del modelo.

**Qué hace:**
- Lee los textos generados en `task_natural.jsonl`.
- Divide el contenido según longitud y semántica (usando LangChain o NLTK).
- Cada chunk mantiene su contexto (proyecto, sprint, estado).

**Entrada:**  
`data/processed/task_natural.jsonl`

**Salida:**  
`data/processed/task_chunks.jsonl`

---

### 🔴 Paso 5 — Indexar en base vectorial persistente  
**Script:** `data/rag/index/03_index_vector_chroma.py`

Crea la base vectorial del RAG combinando embeddings semánticos con búsqueda lexical.  
Usa **ChromaDB** para almacenar los vectores de manera persistente.

**Qué hace:**
- Carga los `task_chunks.jsonl`.
- Genera embeddings usando el modelo `sentence-transformers/all-MiniLM-L12-v2`.
- Crea un índice híbrido:
  - Vectorial (semántico).
  - BM25 (por coincidencia de texto).
- Almacena los vectores en `data/rag/chroma_db/` (persistente).
- Permite consultas interactivas, por ejemplo:

  ```
  ¿Qué tareas están bloqueadas?
  ¿Cuántas tareas se completaron este sprint?
  ¿Qué tareas con prioridad urgente siguen abiertas?
  ```

**Entrada:**  
`data/processed/task_chunks.jsonl`

**Salida:**  
Base vectorial persistente en  
`data/rag/chroma_db/`

---

## 📊 Estructura del flujo completo

```
┌──────────────────────────────────────────┐
│ get_and_clean_clickup_tasks.py           │
│ ↓ Descarga todas las tareas de ClickUp   │
└──────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│ utils/clean_tasks.py                     │
│ ↓ Limpia y normaliza los datos           │
└──────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│ 01_naturalize_tasks.py                   │
│ ↓ Convierte tareas a texto natural       │
└──────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│ 02_chunk_tasks.py                        │
│ ↓ Divide los textos en fragmentos        │
└──────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│ 03_index_vector_chroma.py                │
│ ↓ Crea embeddings y los guarda en Chroma │
└──────────────────────────────────────────┘
```

---

## 📘 Comandos de ejecución rápida

```bash
# 1. Descargar tareas desde ClickUp
python data/rag/ingest/get_and_clean_clickup_tasks.py

# 2. Limpiar y normalizar
a python utils/clean_tasks.py

# 3. Generar texto natural
python data/rag/transform/01_naturalize_tasks.py

# 4. Crear chunks
python data/rag/chunk/02_chunk_tasks.py

# 5. Indexar en base vectorial persistente
python data/rag/index/03_index_vector_chroma.py
```

---

## 📦 Directorios importantes

| Carpeta | Contenido |
|----------|------------|
| `data/rag/ingest/` | Datos descargados de ClickUp (JSON y CSV). |
| `data/processed/` | Archivos intermedios: tareas limpias, naturalizadas y chunkificadas. |
| `data/rag/chroma_db/` | Base vectorial persistente (ChromaDB). |

---

## 🧠 Resultado final

Después del paso 5 tendrás una base vectorial enriquecida con todas las tareas (activas y completadas),  
lista para alimentar tu **agente de preguntas y respuestas** basado en RAG.

El modelo podrá entender contexto de proyectos, sprints, estados, bloqueos y responsables,  
y responder con precisión a consultas como:

- “¿Qué tareas están bloqueadas actualmente?”  
- “¿Cuántas tareas se completaron en el Sprint 3?”  
- “¿Qué tareas de Jorge Aguadero tienen prioridad alta?”  
- “¿Qué tareas tienen dudas pendientes?”