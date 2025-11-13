# 📊 Análisis del Pipeline RAG y Mejoras Implementadas

## 🔍 Resumen Ejecutivo

He analizado el flujo completo de creación del RAG desde la ingesta de ClickUp hasta la indexación en ChromaDB. Se han identificado y **corregido** varios problemas críticos que afectaban la calidad de los embeddings y la capacidad de búsqueda híbrida.

---

## 📂 Flujo Actual del Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. INGESTA (get_clickup_tasks.py)                                  │
│    ↓ Descarga tareas desde ClickUp API                             │
│    ↓ Output: clickup_tasks_all_YYYY-MM-DD.json                     │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 2. LIMPIEZA (01_clean_clickup_tasks.py)                            │
│    ↓ Normaliza estados, prioridades, asignados                     │
│    ↓ Deriva información de tags                                    │
│    ↓ Output: task_clean.jsonl                                      │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 3. MARKDOWN (02_markdownfy_tasks.py)                               │
│    ↓ HTML → Markdown con markdownify                               │
│    ↓ Genera estructura semántica legible                           │
│    ↓ Output: task_markdown.jsonl                                   │
│    ↓ Formato: {"text": "...", "metadata": {...}}                   │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 4. NATURALIZACIÓN (03_naturalize_tasks_hybrid.py)                  │
│    ↓ OpenAI o modelo local (Mistral/Qwen)                          │
│    ↓ Resúmenes concisos (≤2 frases)                                │
│    ↓ Output: task_natural.jsonl                                    │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 5. CHUNKING (04_chunk_tasks.py)                                    │
│    ↓ MarkdownHeaderTextSplitter (respeta estructura)               │
│    ↓ RecursiveCharacterTextSplitter (fragmentos largos)            │
│    ↓ Output: task_chunks.jsonl                                     │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 6. INDEXACIÓN (05_index_tasks.py)                                  │
│    ↓ ChromaDB con embeddings híbridos                              │
│    ↓ MiniLM-L12-v2 + Jina (opcional)                               │
│    ↓ Output: data/rag/chroma_db/                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ❌ Problemas Identificados y ✅ Soluciones Implementadas

### 1. **Mezcla de Metadata y Content en Chunking**

**❌ Problema:**
El script `04_chunk_tasks.py` enriquecía el texto con metadatos:

```python
enriched_text = f"Tarea asignada a {assignees}. Estado: {status}. ..."
```

Esto contamina el embedding con información redundante que ya está en los metadatos.

**✅ Solución:**

```python
# ANTES: texto enriquecido mezclado
enriched_text = f"Tarea asignada a {assignees}. Estado: {status}..."
chunks = text_splitter.split_text(enriched_text)

# DESPUÉS: contenido puro, metadatos separados
text = task.get("text") or ""
chunks = markdown_splitter.split_text(text)  # Solo contenido
# Los metadatos se mantienen en metadata{} separados
```

**Impacto:** Los embeddings ahora capturan el **contenido semántico real** de las tareas, mientras que los metadatos permiten filtrado preciso (`priority=urgent`, `assignees=Juan`).

---

### 2. **Sin Conversión HTML → Markdown**

**❌ Problema:**
ClickUp puede devolver descripciones en HTML/RichText:

```html
<p>Esta es una <strong>descripción</strong> con formato.</p>
```

El script asumía texto plano, perdiendo estructura.

**✅ Solución:**
Integración de `markdownify`:

```python
from markdownify import markdownify as md

def html_to_markdown(text: str) -> str:
    if "<" in text and ">" in text:
        return md(text, heading_style="ATX", strip=["script", "style"])
    return text
```

**Impacto:** La estructura semántica se preserva:

```markdown
Esta es una **descripción** con formato.
```

---

### 3. **Chunking que No Respeta Estructura Markdown**

**❌ Problema:**
Usaba `RecursiveCharacterTextSplitter` genérico que corta en medio de secciones:

```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    separators=["\n\n", ". ", "; ", ":", "\n", " "]
)
```

**✅ Solución:**
Implementación de `MarkdownHeaderTextSplitter`:

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter

headers_to_split_on = [
    ("###", "Header 3"),
    ("**", "Bold"),
]

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False
)
```

**Impacto:** Los chunks respetan la jerarquía de encabezados (`### Tarea:`, `**Estado:**`), manteniendo coherencia semántica.

---

### 4. **Campo `description` Ausente en Limpieza**

**❌ Problema:**
El archivo `task_clean.jsonl` no incluía la descripción original de ClickUp.

**✅ Solución:**

```python
description = t.get("description") or t.get("text_content") or ""
record = {
    ...
    "description": description,
    ...
}
```

**Impacto:** La descripción se preserva para las fases posteriores.

---

## 🎯 Formato JSONL Optimizado

### Estructura Recomendada (Ya Implementada)

Cada línea en `task_markdown.jsonl` y siguientes tiene:

```json
{
  "text": "### Tarea: Implementar login\n**Estado:** In progress\n**Prioridad:** High\n...",
  "metadata": {
    "task_id": "86c6c2re5",
    "name": "Implementar login",
    "status": "in_progress",
    "priority": "high",
    "sprint": "Sprint 3",
    "assignees": "Juan, María",
    "tags": ["backend", "seguridad"],
    "is_blocked": false,
    "date_created": "2025-11-05T11:03:42Z"
  }
}
```

### ¿Por Qué Esta Separación?

1. **`text`** → Se pasa al modelo de embeddings (OpenAI, Cohere, MiniLM)

   - Contiene solo contenido semántico legible
   - Formato Markdown para mejor comprensión del modelo

2. **`metadata`** → Se pasa tal cual a ChromaDB/Pinecone/Weaviate
   - Permite **Hybrid Search**: búsqueda semántica + filtros
   - Ejemplo: `¿Tareas urgentes de Juan en Sprint 3?`
     ```python
     results = collection.query(
         query_texts=["tareas urgentes"],
         where={
             "priority": "urgent",
             "assignees": {"$contains": "Juan"},
             "sprint": "Sprint 3"
         }
     )
     ```

---

## 🔧 Parámetros de Chunking

### Configuración Actual

```python
# Splitter primario (estructura MD)
markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("###", "Header 3"), ("**", "Bold")],
    strip_headers=False
)

# Splitter secundario (fragmentos largos)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,      # Aumentado de 600
    chunk_overlap=100,
    separators=["\n\n", ". ", "; ", ":", "\n", " "]
)
```

### Recomendaciones Según Dataset

| Escenario                                    | `chunk_size` | `chunk_overlap` | Chunks/Tarea |
| -------------------------------------------- | ------------ | --------------- | ------------ |
| **Demo** (resúmenes cortos)                  | 600          | 100             | 1-2          |
| **Producción** (descripciones + comentarios) | 800-1000     | 100-150         | 2-4          |
| **Documentación extensa**                    | 1200         | 200             | 4-8          |

---

## 🚀 Flujo de Ejecución

### Actualizar el Pipeline Completo

```bash
# 1. Descargar tareas de ClickUp
python data/rag/ingest/get_clickup_tasks.py

# 2. Limpiar y normalizar
python data/rag/transform/01_clean_clickup_tasks.py

# 3. Convertir a Markdown (HTML→MD)
python data/rag/transform/02_markdownfy_tasks.py

# 4. Naturalizar (opcional, para resúmenes)
python data/rag/transform/03_naturalize_tasks_hybrid.py

# 5. Chunking con MarkdownSplitter
python data/rag/transform/04_chunk_tasks.py

# 6. Indexar en ChromaDB
python data/rag/transform/05_index_tasks.py --reset
```

### Pipeline Automatizado

```bash
# Ejecutar todo el flujo
make rag-rebuild
```

---

## 📊 Ejemplo de Búsqueda Híbrida

```python
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(path="data/rag/chroma_db")
collection = client.get_collection("clickup_tasks")

# Búsqueda semántica + filtros de metadatos
results = collection.query(
    query_texts=["¿Cómo implementar autenticación OAuth?"],
    where={
        "$and": [
            {"priority": {"$in": ["urgent", "high"]}},
            {"sprint": "Sprint 3"},
            {"status": {"$ne": "done"}}
        ]
    },
    n_results=5
)

for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
    print(f"\n📌 {meta['name']}")
    print(f"   Estado: {meta['status']} | Prioridad: {meta['priority']}")
    print(f"   Asignado: {meta['assignees']}")
    print(f"   {doc[:200]}...")
```

---

## 🎓 Recomendaciones Adicionales

### 1. **Embeddings Híbridos**

Combina diferentes modelos para mejor recall:

- **Semántico**: `all-MiniLM-L12-v2` (general)
- **Denso**: `jina-embeddings-v2` (multilingüe)
- **Sparse**: BM25 (keywords exactos)

### 2. **Enriquecimiento Contextual (Opcional)**

Si las tareas tienen relaciones padre-hijo:

```python
# En metadata, añadir contexto de jerarquía
"parent_context": "Epic: Migración a microservicios > Sprint 3 > Backend"
```

### 3. **Validación de Calidad**

Ejecutar después de cada cambio:

```bash
python data/rag/transform/06_validate_chroma_index.py
```

### 4. **Monitoreo de Drift**

Comparar ClickUp vs ChromaDB periódicamente:

```bash
python tools/compare_clickup_vs_chroma.py
```

---

## ✅ Checklist de Implementación

- [x] Separación clara `metadata` / `content` en todos los JSONL
- [x] Conversión HTML → Markdown con `markdownify`
- [x] `MarkdownHeaderTextSplitter` para respetar estructura
- [x] Eliminación de "enriquecimiento" en chunking
- [x] Campo `description` añadido en limpieza
- [x] Dependencia `markdownify==0.13.1` en `requirements.txt`
- [ ] Ejecutar pipeline completo con datos reales
- [ ] Validar calidad de búsqueda híbrida
- [ ] Ajustar `chunk_size` según resultados

---

## 🔗 Referencias

- **LangChain Text Splitters**: https://python.langchain.com/docs/modules/data_connection/document_transformers/
- **ChromaDB Metadata Filtering**: https://docs.trychroma.com/usage-guide#filtering-by-metadata
- **Markdownify**: https://github.com/matthewwithanm/python-markdownify

---

**Fecha de análisis**: 13 de noviembre de 2025  
**Versión del pipeline**: v2.0 (mejorado)
