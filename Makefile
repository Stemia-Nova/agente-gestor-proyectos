.PHONY: help setup install test lint format clean pipeline ingest clean-data markdown naturalize chunk index run dev

# ============================================================================
# 🤖 Agente Gestor de Proyectos - Sistema RAG para ClickUp
# ============================================================================

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PROJECT_DIR := $(CURDIR)

# Default target
.DEFAULT_GOAL := help

# -----------------------------------------------------------------------------
# 📚 Help - Muestra todos los comandos disponibles
# -----------------------------------------------------------------------------
help:
	@echo "🤖 Agente Gestor de Proyectos - Comandos disponibles:"
	@echo ""
	@echo "  📦 SETUP Y CONFIGURACIÓN"
	@echo "  make setup        - Crea entorno virtual y configura proyecto"
	@echo "  make install      - Instala dependencias desde requirements.txt"
	@echo ""
	@echo "  🔄 PIPELINE RAG COMPLETO"
	@echo "  make pipeline     - Ejecuta pipeline completo (ingest → index)"
	@echo "  make ingest       - Descarga tareas de ClickUp"
	@echo "  make clean-data   - Limpia y normaliza tareas"
	@echo "  make markdown     - Convierte a markdown"
	@echo "  make naturalize   - Naturaliza con OpenAI"
	@echo "  make chunk        - Genera chunks de texto"
	@echo "  make index        - Indexa en ChromaDB"
	@echo ""
	@echo "  🚀 EJECUCIÓN"
	@echo "  make run          - Ejecuta chatbot Chainlit (producción)"
	@echo "  make dev          - Ejecuta chatbot en modo desarrollo"
	@echo ""
	@echo "  🧪 TESTING Y CALIDAD"
	@echo "  make test         - Ejecuta todos los tests"
	@echo "  make lint         - Verifica código con pylint"
	@echo "  make format       - Formatea código con black"
	@echo ""
	@echo "  🗑️  LIMPIEZA"
	@echo "  make clean        - Limpia archivos generados y cache"

# -----------------------------------------------------------------------------
# 📦 Setup y Configuración
# -----------------------------------------------------------------------------
setup:
	@echo "📦 Creando entorno virtual..."
	python3 -m venv .venv
	@echo "📥 Instalando dependencias..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "✅ Setup completado. Activa el entorno con: source .venv/bin/activate"

install:
	@echo "📥 Instalando dependencias..."
	$(PIP) install -r requirements.txt
	@echo "✅ Dependencias instaladas correctamente."

# -----------------------------------------------------------------------------
# 🔄 Pipeline RAG (ClickUp → ChromaDB)
# -----------------------------------------------------------------------------
pipeline: ingest clean-data markdown naturalize chunk index
	@echo "✅ Pipeline RAG ejecutado correctamente."

ingest:
	@echo "📥 Descargando tareas de ClickUp..."
	$(PYTHON) data/rag/ingest/get_clickup_tasks.py

clean-data:
	@echo "🧹 Limpiando y normalizando tareas..."
	$(PYTHON) data/rag/transform/01_clean_clickup_tasks.py

markdown:
	@echo "📝 Convirtiendo a markdown..."
	$(PYTHON) data/rag/transform/02_markdownfy_tasks.py

naturalize:
	@echo "🧠 Naturalizando tareas con OpenAI..."
	$(PYTHON) data/rag/transform/03_naturalize_tasks_hybrid.py

chunk:
	@echo "✂️  Generando chunks de texto..."
	$(PYTHON) data/rag/transform/04_chunk_tasks.py

index:
	@echo "🔍 Indexando en ChromaDB..."
	$(PYTHON) data/rag/transform/05_index_tasks.py --reset

# -----------------------------------------------------------------------------
# 🚀 Ejecución del Chatbot
# -----------------------------------------------------------------------------
run:
	@echo "🚀 Iniciando chatbot Chainlit..."
	$(PYTHON) -m chainlit run main.py --host 0.0.0.0 --port 8000

dev:
	@echo "🔧 Iniciando chatbot en modo desarrollo..."
	$(PYTHON) -m chainlit run main.py --host localhost --port 8000 -w

# -----------------------------------------------------------------------------
# 🧪 Testing y Calidad de Código
# -----------------------------------------------------------------------------
test:
	@echo "🧪 Ejecutando tests..."
	$(PYTHON) -m pytest test/ -v

lint:
	@echo "🔍 Verificando código con pylint..."
	$(PYTHON) -m pylint utils/ chatbot/ --disable=C0114,C0115,C0116

format:
	@echo "✨ Formateando código con black..."
	$(PYTHON) -m black utils/ chatbot/ data/ test/

# -----------------------------------------------------------------------------
# 🗑️  Limpieza
# -----------------------------------------------------------------------------
clean:
	@echo "🗑️  Limpiando archivos generados..."
	rm -rf data/processed/*.jsonl
	rm -rf data/rag/chroma_db
	rm -rf data/logs/*.pdf
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Limpieza completada."
