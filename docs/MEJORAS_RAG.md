# 🔄 Pipeline RAG Mejorado - Guía Rápida

## 📝 Resumen de Mejoras Implementadas

Se han aplicado **las recomendaciones de mejores prácticas para RAG** al pipeline de ClickUp:

### ✅ Cambios Principales

1. **Separación clara Metadata/Content**

   - El `text` contiene solo contenido semántico en Markdown
   - Los `metadata` contienen campos estructurados para filtrado

2. **Conversión HTML → Markdown**

   - Integración de `markdownify` para preservar estructura
   - Fallback a limpieza básica si la librería no está disponible

3. **MarkdownHeaderTextSplitter**

   - Chunking que respeta la jerarquía de encabezados
   - No corta en medio de secciones semánticas

4. **Sin "enriquecimiento" en chunking**
   - El contenido ya no mezcla metadatos dentro del texto
   - Embeddings más puros y precisos

---

## 🚀 Instalación

### Instalar nueva dependencia

```bash
pip install markdownify==0.13.1
# o usar requirements.txt actualizado
pip install -r requirements.txt
```

---

## 📂 Flujo Completo

```bash
# 1. Descargar tareas de ClickUp
python data/rag/ingest/get_clickup_tasks.py

# 2. Pipeline de transformación
python data/rag/transform/01_clean_clickup_tasks.py
python data/rag/transform/02_markdownfy_tasks.py
python data/rag/transform/03_naturalize_tasks_hybrid.py
python data/rag/transform/04_chunk_tasks.py

# 3. Indexar en ChromaDB
python data/rag/transform/05_index_tasks.py --reset

# 4. Validar índice
python data/rag/transform/06_validate_chroma_index.py
```

---

## 🔍 Búsqueda Híbrida: Ejemplos

### Ejemplo 1: Búsqueda Semántica Pura

```python
results = collection.query(
    query_texts=["¿Cómo implementar autenticación?"],
    n_results=5
)
```

### Ejemplo 2: Filtrado por Metadatos

```python
# Tareas urgentes asignadas a Juan en Sprint 3
results = collection.query(
    query_texts=["tareas pendientes"],
    where={
        "$and": [
            {"priority": "urgent"},
            {"assignees": {"$contains": "Juan"}},
            {"sprint": "Sprint 3"},
            {"status": {"$ne": "done"}}
        ]
    },
    n_results=5
)
```

### Ejemplo 3: Búsqueda por Estado y Prioridad

```python
# Tareas bloqueadas de alta prioridad
results = collection.query(
    query_texts=["tareas bloqueadas"],
    where={
        "$and": [
            {"is_blocked": True},
            {"priority": {"$in": ["urgent", "high"]}},
            {"status": {"$in": ["to_do", "in_progress"]}}
        ]
    },
    n_results=10
)
```

---

## 📊 Formato de Datos

### task_clean.jsonl

```json
{"task_id": "86c6c2re5", "name": "Implementar login", "status": "in_progress", "priority": "high", "description": "<p>Descripción HTML</p>", ...}
```

### task_markdown.jsonl

```json
{
  "text": "### Tarea: Implementar login\n**Estado:** In progress\n**Prioridad:** High\n...",
  "metadata": {
    "task_id": "86c6c2re5",
    "status": "in_progress",
    "priority": "high",
    "sprint": "Sprint 3",
    "assignees": "Juan"
  }
}
```

### task_chunks.jsonl

```json
{
  "chunk_id": "86c6c2re5_chunk0",
  "text": "### Tarea: Implementar login\n**Estado:** In progress...",
  "metadata": {
    "task_id": "86c6c2re5",
    "status": "in_progress",
    "priority": "high",
    "chunk_index": 0
  }
}
```

---

## 🎯 Ventajas del Nuevo Formato

### ❌ Antes (formato mixto)

```python
text = "Tarea asignada a Juan. Estado: in_progress. Prioridad: high. Implementar autenticación OAuth..."
# ❌ Embeddings contaminados con metadatos repetitivos
# ❌ No se puede filtrar por assignees eficientemente
```

### ✅ Después (separación clara)

```python
text = "### Tarea: Implementar autenticación OAuth\n**Descripción:**\nCrear endpoint..."
metadata = {"assignees": "Juan", "status": "in_progress", "priority": "high"}
# ✅ Embeddings puros del contenido semántico
# ✅ Filtrado eficiente por metadatos
# ✅ Hybrid Search: semántica + estructurada
```

---

## 🧪 Validación

### Ejecutar ejemplo de búsqueda

```bash
python docs/ejemplo_busqueda_hibrida.py
```

Salida esperada:

```
✅ Conectado a colección: clickup_tasks
📊 Total de documentos: 45

🔍 Ejemplo 1: Búsqueda Semántica Pura
Query: ¿Cómo implementar autenticación?
┌─────────┬──────────────┬────────┬───────────┬──────────┬──────────┐
│ ID      │ Nombre       │ Estado │ Prioridad │ Sprint   │ Distancia│
├─────────┼──────────────┼────────┼───────────┼──────────┼──────────┤
│ 86c6... │ Impl. login  │ prog.. │ high      │ Sprint 3 │ 0.234    │
└─────────┴──────────────┴────────┴───────────┴──────────┴──────────┘
```

---

## 📚 Documentación Completa

Para análisis detallado del pipeline y arquitectura:

```bash
cat docs/analisis_pipeline_rag.md
```

---

## 🛠️ Ajustes Opcionales

### Cambiar tamaño de chunks

Edita `data/rag/transform/04_chunk_tasks.py`:

```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,      # ← Ajustar según longitud promedio
    chunk_overlap=100,
)
```

### Añadir más campos de metadatos

Edita `data/rag/transform/01_clean_clickup_tasks.py`:

```python
record = {
    ...
    "custom_field": t.get("custom_field_value"),
    "due_date_iso": parse_epoch_ms(t.get("due_date")),
}
```

---

## ❓ Troubleshooting

### Error: "No module named 'markdownify'"

```bash
pip install markdownify==0.13.1
```

### Error: "Collection not found"

```bash
python data/rag/transform/05_index_tasks.py --reset
```

### Los chunks están vacíos

Verifica que `task_markdown.jsonl` tenga contenido en el campo `text`:

```bash
head -n 1 data/processed/task_markdown.jsonl | python -m json.tool
```

---

## 📞 Soporte

Para más detalles sobre las mejoras implementadas, consulta:

- `docs/analisis_pipeline_rag.md` - Análisis completo
- `docs/ejemplo_busqueda_hibrida.py` - Ejemplos prácticos
- `data/rag/transform/` - Scripts del pipeline

---

**Versión**: 2.0 (mejorado)  
**Fecha**: Noviembre 2025
