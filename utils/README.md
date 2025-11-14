# 🛠️ Utils Module - Documentación

Módulo de utilidades compartidas que proporciona la funcionalidad core del sistema RAG: búsqueda híbrida, generación de reportes y validación de configuración.

---

## 📋 Estructura del Módulo

```
utils/
├── __init__.py              # Inicialización del módulo
├── hybrid_search.py         # Motor de búsqueda RAG híbrida
├── report_generator.py      # Generación de informes PDF
├── config_models.py         # Modelos Pydantic de configuración
└── README.md                # Esta documentación
```

---

## 🔍 `hybrid_search.py` - Motor de Búsqueda RAG

### Clase Principal: `HybridSearch`

Sistema de búsqueda que combina:
- 🧠 **Búsqueda semántica**: Similitud de embeddings
- 📝 **Búsqueda léxica**: BM25 (keyword matching)
- ⚖️ **Fusión híbrida**: Combina ambos resultados
- 🎯 **Re-ranking**: Refina resultados con cross-encoder

### Métodos Principales

#### `__init__(db_path, collection_name)`
```python
searcher = HybridSearch(
    db_path="data/rag/chroma_db",
    collection_name="clickup_tasks"
)
```
Inicializa conexión a ChromaDB y carga modelos de embeddings.

#### `search(query, top_k=6, filters=None)`
```python
documents, metadatas = searcher.search(
    query="tareas bloqueadas",
    top_k=10,
    filters={"sprint": "Sprint 3"}
)
```
Ejecuta búsqueda híbrida con filtros opcionales.

**Parámetros**:
- `query`: Consulta en lenguaje natural
- `top_k`: Número de resultados a retornar
- `filters`: Dict con filtros de metadata

**Retorna**: Tuple `(documents: List[str], metadatas: List[Dict])`

#### `answer(query)`
```python
response = searcher.answer("¿Cuántas tareas pendientes hay?")
```
Genera respuesta completa usando GPT-4 con contexto RAG.

**Flujo interno**:
1. Ejecuta `search()` para obtener contexto
2. Construye prompt con contexto + query
3. Llama a GPT-4 para generar respuesta
4. Detecta comandos especiales (PDF, métricas)

#### `get_sprint_metrics(sprint)`
```python
metrics = searcher.get_sprint_metrics("Sprint 3")
# Returns: {
#   "total": 23,
#   "completadas": 15,
#   "en_progreso": 2,
#   "porcentaje_completitud": 65.2,
#   "bloqueadas": 1
# }
```

#### `generate_report_pdf(sprint, destinatario)`
```python
pdf_path = searcher.generate_report_pdf(
    sprint="Sprint 3",
    destinatario="Product Manager"
)
# Returns: "data/logs/informe_sprint_3_20251114_1200.pdf"
```

### Algoritmo de Búsqueda Híbrida

```python
def hybrid_search(query, top_k=6):
    # 1. Búsqueda semántica (embeddings)
    semantic_results = vector_search(query, k=20)
    semantic_scores = [normalize(dist) for dist in results]
    
    # 2. Búsqueda léxica (BM25)
    bm25_results = bm25.get_scores(query)
    bm25_scores = [normalize(score) for score in bm25_results]
    
    # 3. Fusión con pesos
    final_scores = {}
    for doc_id in all_docs:
        semantic = semantic_scores.get(doc_id, 0.0)
        lexical = bm25_scores.get(doc_id, 0.0)
        final_scores[doc_id] = (
            0.7 * semantic +  # Peso semántico
            0.3 * lexical     # Peso léxico
        )
    
    # 4. Re-ranking con cross-encoder
    candidates = sorted(final_scores, key=lambda x: x[1], reverse=True)[:20]
    reranked = cross_encoder.predict([(query, doc) for doc in candidates])
    
    # 5. Retornar top_k
    return sorted(reranked, key=lambda x: x.score, reverse=True)[:top_k]
```

### Configuración Avanzada

```python
# Ajustar pesos de fusión
searcher.semantic_weight = 0.8  # Más peso a semántica
searcher.lexical_weight = 0.2   # Menos peso a keywords

# Cambiar modelos de embeddings
searcher.embedding_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Configurar reranking
searcher.use_reranking = True
searcher.rerank_top_k = 20  # Rerank top 20 candidatos
```

---

## 📄 `report_generator.py` - Generación de PDFs

### Clase Principal: `ReportGenerator`

Genera informes profesionales en formato PDF con ReportLab.

### Métodos Principales

#### `generate_report(sprint, metrics, tasks)`
```python
generator = ReportGenerator()
report_text = generator.generate_report(
    sprint="Sprint 3",
    metrics={
        "total": 23,
        "completadas": 15,
        "bloqueadas": 1
    },
    tasks=[...]  # Lista de tareas
)
```
Genera informe en formato texto (markdown).

#### `export_to_pdf(sprint, output_path, destinatario)`
```python
pdf_path = generator.export_to_pdf(
    sprint="Sprint 3",
    output_path="data/logs/informe_sprint_3.pdf",
    destinatario="Product Manager"
)
```
Genera PDF profesional con:
- 📋 Portada con logo y fecha
- 📊 Métricas resumidas en tabla
- 📝 Listado detallado de tareas
- 🚫 Sección de tareas bloqueadas
- 💬 Comentarios críticos

### Template de Informe

```python
SPRINT_REPORT_TEMPLATE = """
# Informe de {{ sprint }}

## 📊 Métricas Generales
- **Total de tareas**: {{ metrics.total }}
- **Completadas**: {{ metrics.completadas }} ({{ metrics.porcentaje_completitud }}%)
- **En progreso**: {{ metrics.en_progreso }}
- **Pendientes**: {{ metrics.pendientes }}
- **Bloqueadas**: {{ metrics.bloqueadas }}

## 📝 Tareas por Estado
{% for estado, tareas in tareas_por_estado.items() %}
### {{ estado }}
{% for tarea in tareas %}
- **{{ tarea.name }}** (Prioridad: {{ tarea.priority }})
  Asignado a: {{ tarea.assignees }}
{% endfor %}
{% endfor %}
"""
```

### Personalización de PDFs

```python
# Colores corporativos
PRIMARY_COLOR = colors.HexColor("#1E40AF")
SECONDARY_COLOR = colors.HexColor("#3B82F6")

# Estilos de texto
title_style = ParagraphStyle(
    'CustomTitle',
    fontSize=24,
    textColor=PRIMARY_COLOR,
    alignment=TA_CENTER
)

# Logo personalizado
logo_path = "assets/company_logo.png"
```

---

## ⚙️ `config_models.py` - Validación con Pydantic

### Clase Principal: `ClickUpConfig`

Modelo Pydantic para validación type-safe de configuración.

```python
from utils.config_models import get_config

# Cargar y validar configuración
config = get_config()

# Acceso type-safe
status = config.get_normalized_status("to do")     # → "to_do"
priority = config.get_normalized_priority("alta")  # → "high"
spanish = config.get_spanish_translation("status", "done")  # → "Completada"

# Verificar tags críticas
if config.should_download_comments(["bloqueada", "data"]):
    download_comments(task)
```

### Estructura del Modelo

```python
class ClickUpConfig(BaseModel):
    status_mappings: Dict[str, List[str]]
    priority_mappings: Dict[str, List[str]]
    critical_tags_for_comments: List[str]
    spanish_translations: Dict[str, Dict[str, str]]
    
    class Config:
        extra = "allow"  # Permite campos adicionales (version, description)
```

### Métodos Helper

#### `get_normalized_status(raw_status: str) -> str`
Normaliza estado de ClickUp a valor estándar.

```python
config.get_normalized_status("In Progress")  # → "in_progress"
config.get_normalized_status("TODO")         # → "to_do"
config.get_normalized_status("Complete")     # → "done"
```

#### `get_normalized_priority(raw_priority: str) -> str`
Normaliza prioridad de ClickUp a valor estándar.

```python
config.get_normalized_priority("1")          # → "urgent"
config.get_normalized_priority("Alta")       # → "high"
config.get_normalized_priority("normal")     # → "normal"
```

#### `should_download_comments(tags: List[str]) -> bool`
Determina si debe descargar comentarios según tags.

```python
config.should_download_comments(["bloqueada", "data"])  # → True
config.should_download_comments(["frontend"])           # → False
```

### Validación Automática

```python
# Si el JSON tiene errores, Pydantic los detecta
{
  "status_mappings": "invalid"  # ❌ Debería ser Dict
}

# Raise: ValidationError: 1 validation error
#   status_mappings: Input should be a valid dictionary
```

### Fallbacks Automáticos

```python
# Si no existe clickup_mappings.json
config = get_config()  # ⚠️ Usa valores por defecto
# Log: "⚠️ Archivo de config no encontrado. Usando configuración por defecto."

# Si el JSON es inválido
config = get_config()  # ⚠️ Usa valores por defecto
# Log: "❌ Error cargando configuración: 2 validation errors"
```

---

## 🧪 Testing de Utilidades

### Test de Búsqueda Híbrida

```python
# test/test_hybrid_search.py
def test_semantic_search():
    searcher = HybridSearch()
    docs, metas = searcher.search("tareas urgentes", top_k=5)
    
    assert len(docs) == 5
    assert any("urgent" in meta.get("priority", "") for meta in metas)

def test_filters():
    searcher = HybridSearch()
    docs, metas = searcher.search(
        query="tareas",
        filters={"sprint": "Sprint 3", "status": "done"}
    )
    
    assert all(m["sprint"] == "Sprint 3" for m in metas)
    assert all(m["status"] == "done" for m in metas)
```

### Test de Generación de PDFs

```python
# test/test_report_generator.py
def test_pdf_generation():
    generator = ReportGenerator()
    pdf_path = generator.export_to_pdf(
        sprint="Test Sprint",
        output_path="/tmp/test_report.pdf"
    )
    
    assert os.path.exists(pdf_path)
    assert pdf_path.endswith(".pdf")
```

### Test de Configuración

```python
# test/test_config_models.py
def test_config_validation():
    config = get_config()
    
    assert isinstance(config, ClickUpConfig)
    assert "to_do" in config.status_mappings
    assert "urgent" in config.priority_mappings

def test_normalization():
    config = get_config()
    
    assert config.get_normalized_status("TODO") == "to_do"
    assert config.get_normalized_priority("alta") == "high"
```

---

## 🎯 Casos de Uso

### 1. Búsqueda Simple

```python
from utils.hybrid_search import HybridSearch

searcher = HybridSearch()
docs, metas = searcher.search("tareas de backend")

for doc, meta in zip(docs, metas):
    print(f"- {meta['name']} ({meta['sprint']})")
```

### 2. Búsqueda con Filtros

```python
# Tareas urgentes del Sprint 3
docs, metas = searcher.search(
    query="",  # Sin query, solo filtros
    filters={"sprint": "Sprint 3", "priority": "urgent"}
)
```

### 3. Generar Informe PDF

```python
from utils.hybrid_search import HybridSearch

searcher = HybridSearch()
pdf_path = searcher.generate_report_pdf(
    sprint="Sprint 3",
    destinatario="Product Manager"
)
print(f"PDF generado: {pdf_path}")
```

### 4. Métricas de Sprint

```python
metrics = searcher.get_sprint_metrics("Sprint 3")
print(f"Completitud: {metrics['porcentaje_completitud']}%")
print(f"Bloqueadas: {metrics['bloqueadas']}")
```

### 5. Validar Configuración Personalizada

```python
from utils.config_models import load_config

# Cargar config custom
config = load_config("path/to/custom_mappings.json")

# Validar y usar
status = config.get_normalized_status("my_custom_status")
```

---

## 🐛 Troubleshooting

### Error: "ChromaDB collection not found"
**Causa**: No se ha ejecutado el pipeline de indexación.  
**Solución**: `make index`

### Error: "Model not found"
**Causa**: Modelos de embeddings no descargados.  
**Solución**: Se descargan automáticamente en primer uso. Espera ~2GB.

### Búsquedas lentas
**Causa**: CPU sin optimización.  
**Solución**: Usa GPU o reduce `top_k`

### PDFs vacíos
**Causa**: Sprint no existe en ChromaDB.  
**Solución**: Verifica nombre exacto del sprint.

---

## 📚 Referencias

- **ChromaDB**: https://docs.trychroma.com/
- **Sentence Transformers**: https://www.sbert.net/
- **ReportLab**: https://www.reportlab.com/docs/
- **Pydantic**: https://docs.pydantic.dev/

---

<div align="center">
  <strong>Utilidades diseñadas para performance y escalabilidad</strong>
</div>
