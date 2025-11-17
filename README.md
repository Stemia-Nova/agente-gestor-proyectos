# 🤖 Agente Gestor de Proyectos - Sistema RAG para ClickUp

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Chainlit](https://img.shields.io/badge/Chainlit-2.8.4-green)](https://chainlit.io/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5.5-purple)](https://www.trychroma.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Sistema de **Retrieval-Augmented Generation (RAG)** especializado en gestión de proyectos con ClickUp. Combina búsqueda híbrida (semántica + léxica), naturalización de tareas con GPT-4 y generación automática de informes PDF profesionales para Product Managers y Scrum Masters.

---

## 📋 Tabla de Contenidos

- [Características Principales](#-características-principales)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Requisitos](#-requisitos)
- [Instalación Rápida](#-instalación-rápida)
- [Configuración](#️-configuración)
- [Uso](#-uso)
- [Pipeline RAG](#-pipeline-rag)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Testing](#-testing)
- [Documentación Adicional](#-documentación-adicional)

---

## ✨ Características Principales

### 🔍 **Búsqueda Híbrida Inteligente**

- **Semántica**: Embeddings con `sentence-transformers` (MiniLM + Jina)
- **Léxica**: BM25 para búsqueda por palabras clave
- **Re-ranking**: Cross-encoder para resultados más precisos
- **Filtros avanzados**: Por sprint, estado, prioridad, tags, asignado

### 🧠 **Naturalización de Tareas**

- Conversión automática de tareas técnicas a lenguaje natural con GPT-4
- Sistema anti-duplicados con cache inteligente
- Preservación de metadata crítica (tags, comentarios, bloqueadores)
- Progress tracking con reinicio automático en caso de error

### 📊 **Informes Profesionales**

- Generación de reportes de sprint en formato texto y PDF
- Métricas avanzadas: velocidad, completitud, bloqueadores, distribución de prioridades
- Análisis de tareas críticas con comentarios detallados
- Formato A4 profesional con logo y estructura formal

### ⚙️ **Configuración Flexible**

- Sistema de mapeos externo con **Pydantic** para validación
- Adaptable a diferentes proyectos sin modificar código
- Soporte multi-idioma (español/inglés)
- Detección automática de tags críticas para descarga de comentarios

### 💬 **Chatbot Conversacional**

- Interfaz web moderna con **Chainlit**
- Respuestas contextuales basadas en RAG
- Comandos especiales para informes y métricas
- Historial de conversación con memoria contextual

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLICKUP API                              │
│                    (Fuente de Datos)                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ├─ 📥 1. INGEST
                     │  └─ get_clickup_tasks.py
                     │     ├─ Descarga tareas, subtareas, comentarios
                     │     ├─ Detección de tags críticas
                     │     └─ Output: clickup_tasks_all.json
                     │
                     ├─ 🧹 2. CLEAN
                     │  └─ 01_clean_clickup_tasks.py
                     │     ├─ Normalización de estados/prioridades
                     │     ├─ Validación con Pydantic
                     │     └─ Output: task_clean.jsonl
                     │
                     ├─ 📝 3. MARKDOWN
                     │  └─ 02_markdownfy_tasks.py
                     │     ├─ Conversión a formato markdown
                     │     ├─ Inclusión de tags en texto
                     │     └─ Output: task_markdown.jsonl
                     │
                     ├─ 🧠 4. NATURALIZE
                     │  └─ 03_naturalize_tasks_hybrid.py
                     │     ├─ Naturalización con GPT-4o-mini
                     │     ├─ Cache anti-duplicados
                     │     └─ Output: task_natural.jsonl
                     │
                     ├─ ✂️  5. CHUNK
                     │  └─ 04_chunk_tasks.py
                     │     ├─ Splitting inteligente (1 chunk/tarea)
                     │     ├─ Enriquecimiento con metadata
                     │     └─ Output: task_chunks.jsonl
                     │
                     └─ 🔍 6. INDEX
                        └─ 05_index_tasks.py
                           ├─ Embeddings con MiniLM + Jina
                           ├─ Indexación en ChromaDB
                           └─ Output: chroma_db/

┌─────────────────────────────────────────────────────────────────┐
│                      CHROMADB (Vector Store)                     │
│              23 tareas × 2 embeddings = 46 vectores              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ├─ 🔎 HYBRID SEARCH
                     │  └─ utils/hybrid_search.py
                     │     ├─ Búsqueda semántica (MiniLM/Jina)
                     │     ├─ Búsqueda léxica (BM25)
                     │     ├─ Re-ranking con cross-encoder
                     │     └─ Fusión híbrida de resultados
                     │
                     ├─ 📄 REPORT GENERATION
                     │  └─ utils/report_generator.py
                     │     ├─ Templates Jinja2
                     │     ├─ Generación de PDF con ReportLab
                     │     └─ Output: informe_sprint_X.pdf
                     │
                     └─ 💬 CHATBOT
                        └─ main.py + chatbot/handlers.py
                           ├─ Interfaz Chainlit
                           ├─ Procesamiento de queries
                           └─ Generación de respuestas con GPT-4
```

---

## 📦 Requisitos

- **Python**: 3.10 o superior
- **Sistema Operativo**: Linux, macOS, Windows (con WSL recomendado)
- **RAM**: Mínimo 8GB (16GB recomendado para modelos locales)
- **Disco**: ~5GB para modelos pre-entrenados
- **GPU**: Opcional (mejora velocidad de embeddings)

### APIs Requeridas

- **ClickUp API Token**: Para descarga de tareas
- **OpenAI API Key**: Para naturalización y generación de respuestas

---

## 🚀 Instalación Rápida

### Opción 1: Script Automático (Linux/macOS)

```bash
git clone https://github.com/Stemia-Nova/agente-gestor-proyectos.git
cd agente-gestor-proyectos
./run_dev.sh
```

El script automáticamente:
- ✅ Crea el entorno virtual `.venv`
- ✅ Instala todas las dependencias
- ✅ Valida las variables de entorno
- ✅ Inicia el servidor Chainlit

### Opción 2: Manual

```bash
# 1. Clonar repositorio
git clone https://github.com/Stemia-Nova/agente-gestor-proyectos.git
cd agente-gestor-proyectos

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configurar .env (ver sección siguiente)
cp .env.example .env
# Editar .env con tus API keys

# 5. Iniciar chatbot
chainlit run main.py -w
```

### Opción 3: Windows (PowerShell)

```powershell
git clone https://github.com/Stemia-Nova/agente-gestor-proyectos.git
cd agente-gestor-proyectos
.\run_dev.ps1
```

### 🔧 Troubleshooting

**Error: httpx incompatible**
```bash
# Solución: httpx>=0.28 tiene breaking changes
pip install "httpx<0.28"
```

**Error: Torch no encontrado**
```bash
# CPU only (más ligero)
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**Rate Limit de OpenAI**
- Cuenta gratuita: 3 req/min, 100K tokens/min
- Solución: Agregar método de pago o esperar entre consultas

---

## ⚙️ Configuración

### 1. Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# ClickUp API
CLICKUP_API_TOKEN=pk_XXXXXXXXXXXXXXXXX
CLICKUP_FOLDER_ID=901234567890

# OpenAI API
OPENAI_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Opcional: Configuración de modelos
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L12-v2
```

### 2. Configuración de Mapeos

Edita `data/rag/config/clickup_mappings.json` para adaptar a tu proyecto:

```json
{
  "version": "1.0",
  "status_mappings": {
    "to_do": ["to do", "todo", "pendiente"],
    "in_progress": ["in progress", "doing"],
    "done": ["complete", "done", "closed"]
  },
  "priority_mappings": {
    "urgent": ["urgent", "urgente", "1"],
    "high": ["high", "alta", "2"]
  },
  "critical_tags_for_comments": ["bloqueada", "blocked", "data", "duda"]
}
```

📖 **Documentación completa**: [`data/rag/config/README.md`](data/rag/config/README.md)

---

## 🔄 Actualizar Base de Datos RAG

### Opción 1: Pipeline Completo Automático

```bash
# Ejecuta todos los pasos (download → clean → ... → index)
python run_pipeline.py --all
```

### Opción 2: Sin Descarga (usar datos existentes)

```bash
# Omite descarga de ClickUp, procesa datos locales
python run_pipeline.py
```

### Opción 3: Desde un paso específico

```bash
# Continuar desde naturalización en adelante
python run_pipeline.py --from-step naturalize
```

**Pasos disponibles**: `download`, `clean`, `markdown`, `naturalize`, `merge`, `chunk`, `index`

### Ejecución Manual (paso a paso)

```bash
# 1. 📥 Descargar de ClickUp (opcional)
python data/rag/sync/get_clickup_tasks.py

# 2. 🧹 Limpiar y normalizar
python data/rag/transform/01_clean_clickup_tasks.py

# 3. 📝 Convertir a markdown
python data/rag/transform/02_markdownfy_tasks.py

# 4. 🧠 Naturalizar con GPT-4
python data/rag/transform/03_naturalize_tasks_hybrid.py

# 5. 🔗 Combinar metadata
python data/rag/transform/03b_merge_metadata.py

# 6. ✂️  Generar chunks
python data/rag/transform/04_chunk_tasks.py

# 7. 🔍 Indexar en ChromaDB
python data/rag/transform/05_index_tasks.py
```

---

## 💬 Uso del Chatbot

### Iniciar Servidor

```bash
# Modo producción
make run

# Modo desarrollo (con auto-reload)
make dev
```

Abre tu navegador en: `http://localhost:8000`

### Ejemplos de Consultas

```
¿Cuántas tareas tiene el Sprint 3?
→ Métricas detalladas del sprint

¿Qué tareas están bloqueadas?
→ Lista de tareas bloqueadas con detalles

Genera un informe PDF del Sprint 3
→ Crea informe_sprint_3_YYYYMMDD_HHMM.pdf

¿Qué tareas tienen la etiqueta data?
→ Búsqueda por tags

Dame las tareas de alta prioridad pendientes
→ Filtrado por prioridad y estado
```

---

## 🔄 Pipeline RAG

Cada etapa del pipeline genera archivos intermedios en `data/processed/`:

| Etapa             | Script                          | Input          | Output                   | Descripción                   |
| ----------------- | ------------------------------- | -------------- | ------------------------ | ----------------------------- |
| **1. Ingest**     | `get_clickup_tasks.py`          | ClickUp API    | `clickup_tasks_all.json` | Descarga tareas y comentarios |
| **2. Clean**      | `01_clean_clickup_tasks.py`     | JSON crudo     | `task_clean.jsonl`       | Normaliza estados/prioridades |
| **3. Markdown**   | `02_markdownfy_tasks.py`        | Clean JSONL    | `task_markdown.jsonl`    | Convierte a formato markdown  |
| **4. Naturalize** | `03_naturalize_tasks_hybrid.py` | Markdown JSONL | `task_natural.jsonl`     | Naturaliza con GPT-4          |
| **5. Chunk**      | `04_chunk_tasks.py`             | Natural JSONL  | `task_chunks.jsonl`      | Genera chunks (1/tarea)       |
| **6. Index**      | `05_index_tasks.py`             | Chunks JSONL   | `chroma_db/`             | Indexa en ChromaDB            |

📚 **Guía educativa completa**: [`data/README.md`](data/README.md)

---

## 📁 Estructura del Proyecto

```
agente-gestor-proyectos/
├── 📄 README.md                   # Este archivo - Documentación principal
├── 📄 INSTALL.md                  # Guía de instalación detallada
├── 📄 requirements.txt            # Dependencias Python (11 principales)
├── 📄 main.py                     # Entry point del chatbot
├── 📄 run_dev.sh                  # Script de inicio automático (Linux/macOS)
├── 📄 run_dev.ps1                 # Script de inicio automático (Windows)
├── 📄 run_pipeline.py             # Ejecutor del pipeline RAG completo
│
├── 🗂️ chatbot/                    # Módulo del chatbot Chainlit
│   ├── config.py                  # Configuración del chatbot
│   ├── handlers.py                # Manejadores de eventos
│   └── prompts.py                 # Templates de prompts
│
├── 🗂️ utils/                      # Utilidades compartidas
│   ├── hybrid_search.py           # Motor RAG (semántica + BM25 + reranker)
│   ├── report_generator.py        # Generación de informes PDF
│   ├── config_models.py           # Validación con Pydantic
│   └── helpers.py                 # Funciones auxiliares
│
├── 🗂️ test/                       # Suite de pruebas
│   ├── test_hybrid_search.py      # Tests del motor RAG
│   ├── test_rag_without_llm.py    # Validación sin LLM
│   ├── test_edge_cases.py         # Casos límite (30 tests)
│   └── test_*.py                  # Otros tests funcionales
│
├── 🗂️ data/                       # Pipeline de datos y resultados
│   ├── README.md                  # Guía educativa del pipeline RAG
│   ├── processed/                 # Archivos intermedios (.jsonl)
│   ├── logs/                      # Informes PDF generados
│   └── rag/
│       ├── config/                # Mapeos de ClickUp (JSON)
│       ├── sync/                  # Scripts de descarga
│       ├── transform/             # Scripts de transformación (6 pasos)
│       └── chroma_db/             # Base de datos vectorial
│
├── 🗂️ tools/                      # Herramientas de análisis
│   ├── inspect_chroma.py          # Inspección de BD vectorial
│   ├── query_demo.py              # Demo de consultas
│   └── compare_clickup_vs_chroma.py
│
└── 🗂️ docs/                       # Documentación adicional
    └── archive/                   # Documentos históricos
```

---

## 🧪 Testing

### Suite Completa de Tests

```bash
# Ejecutar todos los tests
pytest test/ -v

# Tests específicos
pytest test/test_hybrid_search.py -v        # Motor RAG
pytest test/test_rag_without_llm.py -v      # Validación sin LLM (15 tests)
pytest test/test_edge_cases.py -v           # Casos límite (30 tests)
```

### Tests Sin Dependencia de LLM

Valida el sistema RAG puro (búsqueda híbrida, filtros, métricas):

```bash
python test/test_rag_without_llm.py
```

**Resultados esperados**: 14/15 tests (93.3% éxito)
- ✅ Búsqueda semántica + BM25
- ✅ Reranker con CrossEncoder  
- ✅ Filtros por estado, sprint, persona
- ✅ Métricas de sprint
- ✅ Detección de bloqueos

### Tests de Casos Límite

Prueba 30 consultas complejas y ambiguas:

```bash
python test/test_edge_cases.py
```

Categorías:
1. Consultas de conteo ambiguas
2. Búsquedas con términos ambiguos
3. Preguntas multi-condición
4. Casos límite de formato
5. Preguntas sobre informes
6. Edge cases de lógica

---

## 📚 Documentación Adicional

- **[INSTALL.md](INSTALL.md)**: Instalación detallada y troubleshooting
- **[data/README.md](data/README.md)**: Tutorial completo del pipeline RAG
- **[docs/INFORMES_PDF_GUIA.md](docs/INFORMES_PDF_GUIA.md)**: Generación de informes PDF

---

## 🧪 Testing

```bash
# Ejecutar todos los tests
make test

# Verificar calidad de código
make lint

# Formatear código
make format
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT.

---

## 👥 Autores

**Stemia-Nova** - _Desarrollo inicial_

---

<div align="center">
  <strong>Hecho con ❤️ por Stemia-Nova</strong>
</div>
