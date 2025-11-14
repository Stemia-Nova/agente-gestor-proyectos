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
- [Instalación](#-instalación)
- [Configuración](#️-configuración)
- [Uso](#-uso)
- [Pipeline RAG](#-pipeline-rag)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Documentación Adicional](#-documentación-adicional)
- [Testing](#-testing)

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

## 🚀 Instalación

### 1. Clonar el Repositorio

```bash
git clone https://github.com/Stemia-Nova/agente-gestor-proyectos.git
cd agente-gestor-proyectos
```

### 2. Configurar Entorno Virtual

```bash
# Crear entorno virtual y instalar dependencias
make setup

# O manualmente:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

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

## 💻 Uso

### Pipeline Completo (Recomendado)

```bash
# Ejecutar pipeline RAG completo
make pipeline

# O paso a paso:
make ingest       # 📥 Descargar de ClickUp
make clean-data   # 🧹 Limpiar y normalizar
make markdown     # 📝 Convertir a markdown
make naturalize   # 🧠 Naturalizar con GPT-4
make chunk        # ✂️  Generar chunks
make index        # 🔍 Indexar en ChromaDB
```

### Iniciar Chatbot

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
├── 📄 README.md                   # Documentación principal
├── 📄 requirements.txt            # Dependencias Python
├── 📄 Makefile                    # Comandos automatizados
├── 📄 main.py                     # Entry point del chatbot
│
├── 🗂️ chatbot/                    # Módulo del chatbot Chainlit
│   ├── config.py                  # Configuración
│   ├── handlers.py                # Manejadores de eventos
│   ├── prompts.py                 # Templates de prompts
│   └── README.md                  # Documentación del chatbot
│
├── 🗂️ utils/                      # Utilidades compartidas
│   ├── hybrid_search.py           # Motor de búsqueda RAG
│   ├── report_generator.py        # Generación de PDFs
│   ├── config_models.py           # Modelos Pydantic
│   └── README.md                  # Documentación de utilidades
│
├── 🗂️ data/                       # Pipeline de datos
│   ├── README.md                  # Guía educativa del pipeline
│   ├── processed/                 # Archivos intermedios (.jsonl)
│   ├── logs/                      # PDFs generados
│   └── rag/
│       ├── config/                # Configuración de mapeos
│       ├── ingest/                # Descarga de ClickUp
│       ├── transform/             # Pipeline de transformación
│       └── chroma_db/             # Base de datos vectorial
│
├── 🗂️ test/                       # Tests automatizados
│   ├── test_hybrid_search.py
│   ├── test_natural_queries.py
│   └── test_chatbot_end2end_mixed.py
│
└── 🗂️ docs/                       # Documentación adicional
    └── INFORMES_PDF_GUIA.md       # Guía de informes PDF
```

---

## 📚 Documentación Adicional

- **[Guía del Pipeline RAG](data/README.md)**: Tutorial paso a paso del flujo de datos
- **[Configuración de Mapeos](data/rag/config/README.md)**: Cómo adaptar a tu proyecto
- **[Módulo Chatbot](chatbot/README.md)**: Arquitectura y personalización
- **[Utilidades RAG](utils/README.md)**: Búsqueda híbrida y generación de reportes
- **[Informes PDF](docs/INFORMES_PDF_GUIA.md)**: Generación y personalización

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
