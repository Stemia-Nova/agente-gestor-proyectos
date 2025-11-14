# 📊 Pipeline RAG - Guía Educativa Paso a Paso

Esta guía explica el flujo completo de transformación de datos desde ClickUp hasta ChromaDB, diseñada con un enfoque educativo para entender cada etapa del proceso.

---

## 🎯 Objetivo del Pipeline

Convertir tareas técnicas de ClickUp en un sistema RAG (Retrieval-Augmented Generation) que permite:

- 🔍 Búsqueda semántica en lenguaje natural
- 📊 Generación de métricas y reportes
- 💬 Consultas conversacionales con contexto
- 📄 Informes PDF profesionales

---

## 🔄 Etapas del Pipeline

```
ClickUp API → [1.Ingest] → [2.Clean] → [3.Markdown] → [4.Naturalize] → [5.Chunk] → [6.Index] → ChromaDB
```

---

## 1️⃣ INGEST - Descarga de Datos

**Script**: `data/rag/ingest/get_clickup_tasks.py`  
**Entrada**: ClickUp API (CLICKUP_API_TOKEN, CLICKUP_FOLDER_ID)  
**Salida**: `data/rag/ingest/clickup_tasks_all_YYYY-MM-DD.json`

### ¿Qué hace?

1. **Conecta con la API de ClickUp** usando tu token de autenticación
2. **Descarga todas las listas** (sprints) dentro de un folder
3. **Para cada tarea**:
   - Obtiene metadata completa (nombre, descripción, estado, prioridad, tags)
   - Descarga subtareas recursivamente
   - Identifica tags críticas (bloqueada, data, duda, etc.)
   - Descarga comentarios si la tarea tiene tags críticas

### Conceptos clave

- **Tag crítica**: Etiqueta que indica que necesitas contexto adicional (comentarios)
- **Estructura jerárquica**: Tareas → Subtareas (hasta 3 niveles)
- **Rate limiting**: Respeta límites de la API con delays

### Ejemplo de salida

```json
{
  "id": "86d5k8dqp",
  "name": "CREAR RAG",
  "status": { "status": "in progress" },
  "priority": { "priority": "high" },
  "tags": [{ "name": "bloqueada" }],
  "description": "Construir sistema RAG...",
  "comments": [
    { "comment_text": "Bloqueada por falta de API key", "user": "Juan" }
  ]
}
```

---

## 2️⃣ CLEAN - Normalización y Validación

**Script**: `data/rag/transform/01_clean_clickup_tasks.py`  
**Entrada**: `clickup_tasks_all.json`  
**Salida**: `data/processed/task_clean.jsonl`

### ¿Qué hace?

1. **Normaliza estados**: "to do", "TODO", "Pendiente" → `to_do`
2. **Normaliza prioridades**: "urgent", "1", "urgente" → `urgent`
3. **Traduce a español**: `done` → "Completada", `urgent` → "Urgente"
4. **Valida con Pydantic**: Usa `ClickUpConfig` para mapeos configurables
5. **Extrae flags**: Detecta tareas bloqueadas, necesita info, etc.

### Conceptos clave

- **Normalización**: Convertir diferentes variantes a un valor estándar
- **Validación**: Asegurar que los datos cumplen estructura esperada
- **Configuración externa**: `data/rag/config/clickup_mappings.json`

### Ejemplo de transformación

```
ANTES:
  status: "In Progress" → DESPUÉS: status: "in_progress", status_display: "En progreso"
  priority: "1"         → DESPUÉS: priority: "urgent", priority_display: "Urgente"
  tags: ["BLOQUEADA"]   → DESPUÉS: tags: ["bloqueada"], is_blocked: true
```

---

## 3️⃣ MARKDOWN - Formato Estructurado

**Script**: `data/rag/transform/02_markdownfy_tasks.py`  
**Entrada**: `task_clean.jsonl`  
**Salida**: `data/processed/task_markdown.jsonl`

### ¿Qué hace?

1. **Convierte cada tarea a markdown** con estructura consistente
2. **Incluye todas las secciones**: nombre, estado, prioridad, asignado, descripción, tags, comentarios
3. **Prepara para embeddings**: Texto limpio y bien formateado

### Conceptos clave

- **Markdown**: Formato de texto plano legible que mantiene estructura
- **Consistencia**: Todas las tareas siguen el mismo template
- **Inclusión de tags**: Tags en el texto para búsqueda semántica

### Ejemplo de salida

```markdown
# CREAR RAG

**Estado:** En progreso  
**Prioridad:** Alta  
**Sprint:** Sprint 3  
**Asignado a:** Juan Pérez  
**Fecha de vencimiento:** 2025-11-20  
**Etiquetas:** bloqueada, data

## Descripción

Construir sistema RAG para gestión de proyectos con ClickUp...

## Comentarios

- **Juan** (2025-11-10): Bloqueada por falta de API key
```

---

## 4️⃣ NATURALIZE - Lenguaje Natural con GPT-4

**Script**: `data/rag/transform/03_naturalize_tasks_hybrid.py`  
**Entrada**: `task_markdown.jsonl`  
**Salida**: `data/processed/task_natural.jsonl`

### ¿Qué hace?

1. **Envía markdown a GPT-4o-mini** con prompt especializado
2. **Genera resumen en lenguaje natural** como si fuera un PM explicando la tarea
3. **Preserva metadata crítica**: Tags, comentarios, bloqueadores
4. **Cache anti-duplicados**: Evita re-procesar tareas idénticas
5. **Manejo de errores**: Reinicio automático desde última tarea procesada

### Conceptos clave

- **Naturalización**: Convertir texto técnico a lenguaje conversacional
- **Prompt engineering**: Instrucciones específicas para el LLM
- **Idempotencia**: Puede ejecutarse múltiples veces sin duplicar
- **Rate limiting**: Manejo de límites de OpenAI API

### Ejemplo de transformación

```
ANTES (Markdown):
# CREAR RAG
**Estado:** En progreso
**Descripción:** Construir sistema RAG para gestión...

DESPUÉS (Natural):
Estamos trabajando en crear un sistema RAG para gestionar proyectos.
Esta tarea está actualmente en progreso, asignada a Juan, y tiene
prioridad alta. Es importante porque permitirá hacer consultas
inteligentes sobre las tareas. La tarea está bloqueada esperando la
API key de OpenAI. Etiquetas: bloqueada, data.
```

---

## 5️⃣ CHUNK - Fragmentación Inteligente

**Script**: `data/rag/transform/04_chunk_tasks.py`  
**Entrada**: `task_natural.jsonl`  
**Salida**: `data/processed/task_chunks.jsonl`

### ¿Qué hace?

1. **Genera 1 chunk por tarea** (óptimo para este caso de uso)
2. **Enriquece con metadata**: Todos los campos necesarios para filtrado
3. **Prepara para indexación**: Formato compatible con ChromaDB

### Conceptos clave

- **Chunking**: Dividir documentos largos en fragmentos pequeños
- **Granularidad**: 1 tarea = 1 chunk (no necesitamos dividir más)
- **Metadata**: Información estructurada que acompaña al texto

### Estructura del chunk

```json
{
  "text": "Estamos trabajando en crear un sistema RAG...",
  "metadata": {
    "task_id": "86d5k8dqp",
    "name": "CREAR RAG",
    "sprint": "Sprint 3",
    "status": "in_progress",
    "priority": "high",
    "tags": "bloqueada|data",
    "is_blocked": true
  }
}
```

---

## 6️⃣ INDEX - Indexación Vectorial

**Script**: `data/rag/transform/05_index_tasks.py`  
**Entrada**: `task_chunks.jsonl`  
**Salida**: `data/rag/chroma_db/`

### ¿Qué hace?

1. **Genera embeddings** con dos modelos:
   - **MiniLM-L12-v2**: Embeddings generales (384 dims)
   - **Jina Embeddings v2**: Embeddings especializados (768 dims)
2. **Indexa en ChromaDB**: Base de datos vectorial persistente
3. **Almacena metadata**: Para filtrado eficiente

### Conceptos clave

- **Embedding**: Vector numérico que representa el significado del texto
- **Similitud coseno**: Mide cuán parecidos son dos embeddings
- **Vector database**: Base de datos optimizada para búsqueda por similitud
- **Dual embeddings**: Dos representaciones para mejor recall

### ¿Cómo funcionan los embeddings?

```python
Texto: "Tarea bloqueada por falta de API"
       ↓ [Modelo de embeddings]
Vector: [0.23, -0.15, 0.88, ..., 0.42]  # 384 dimensiones

Búsqueda: "¿Qué tareas están bloqueadas?"
       ↓ [Mismo modelo]
Vector: [0.21, -0.17, 0.85, ..., 0.39]

Similitud: cosine_similarity(v1, v2) = 0.94  # Muy similar!
```

---

## 🎯 Resultado Final

Después de ejecutar el pipeline completo:

```bash
make pipeline
```

Tendrás:

- ✅ **23 tareas** descargadas de ClickUp
- ✅ **46 vectores** en ChromaDB (23 × 2 modelos)
- ✅ **Búsqueda semántica** funcional
- ✅ **Filtros por metadata** (sprint, estado, prioridad, tags)
- ✅ **Sistema listo** para el chatbot

---

## 🔍 Verificación del Pipeline

```bash
# 1. Verificar archivos generados
ls -lh data/processed/
# Deberías ver:
# - task_clean.jsonl (tareas normalizadas)
# - task_markdown.jsonl (formato markdown)
# - task_natural.jsonl (lenguaje natural)
# - task_chunks.jsonl (chunks para indexar)

# 2. Verificar ChromaDB
.venv/bin/python -c "
import chromadb
client = chromadb.PersistentClient(path='data/rag/chroma_db')
collection = client.get_collection('clickup_tasks')
print(f'✅ Total vectores: {collection.count()}')
"

# 3. Probar búsqueda
.venv/bin/python -c "
from utils.hybrid_search import HybridSearch
searcher = HybridSearch()
docs, metas = searcher.search('tareas bloqueadas', top_k=3)
print(f'✅ Encontradas {len(docs)} tareas')
for meta in metas:
    print(f'  - {meta[\"name\"]}')
"
```

---

## 🐛 Troubleshooting

### Error: "OpenAI rate limit"

**Solución**: Espera 30 minutos y ejecuta `make naturalize` de nuevo. El script reanudará desde donde quedó.

### Error: "ChromaDB collection not found"

**Solución**: Ejecuta `make index --reset` para recrear la colección.

### Error: "ClickUp API 401 Unauthorized"

**Solución**: Verifica que `CLICKUP_API_TOKEN` en `.env` sea correcto.

### Tags no se encuentran en búsqueda

**Solución**: Verifica que:

1. Tags estén en `task_markdown.jsonl` (sección **Etiquetas:**)
2. Tags estén en `task_natural.jsonl` (al final del texto)
3. Ejecutaste `make index --reset` después de los cambios

---

## 📚 Recursos Adicionales

- **[Configuración de Mapeos](rag/config/README.md)**: Cómo adaptar a tu proyecto
- **[Ejemplo de Búsqueda](../docs/ejemplo_busqueda_hibrida.py)**: Script demo de búsqueda
- **[Informes PDF](../docs/INFORMES_PDF_GUIA.md)**: Generación de reportes

---

## 💡 Tips para Optimización

1. **Caching**: El paso de naturalización es el más lento. Usa cache para evitar re-procesar.
2. **Batch processing**: Procesa múltiples tareas en paralelo si tienes muchas.
3. **GPU**: Si tienes GPU CUDA, los embeddings serán 10x más rápidos.
4. **Modelos locales**: Considera usar modelos open-source para evitar costos de API.

---

<div align="center">
  <strong>Pipeline RAG diseñado para aprendizaje y escalabilidad</strong>
</div>
