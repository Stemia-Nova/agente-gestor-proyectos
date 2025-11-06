.PHONY: all clean build clean_tasks naturalize chunk index

# =====================================================
# RAG Project Automation Pipeline
# Ejecuta las etapas del flujo de datos ClickUp → RAG
# =====================================================

# Ruta base del proyecto
PROJECT_DIR := $(CURDIR)

all: build

clean_tasks:
	@echo "🧹 Ejecutando limpieza de tareas ClickUp..."
	python utils/clean_tasks.py

naturalize:
	@echo "🧠 Naturalizando tareas..."
	python data/rag/transform/01_naturalize_tasks.py

chunk:
	@echo "✂️ Generando chunks de texto..."
	python data/rag/chunks/02_chunk_tasks.py

index:
	@echo "🧠 Indexando en ChromaDB..."
	python data/rag/index/03_index_vector_chroma.py

# Ejecuta todo el pipeline
build: clean_tasks naturalize chunk index
	@echo "✅ Pipeline RAG ejecutado correctamente."

# Limpia resultados previos
clean:
	@echo "🗑️ Limpiando archivos generados..."
	rm -rf data/processed/*.jsonl data/rag/chroma_db
	@echo "✅ Limpieza completada."
