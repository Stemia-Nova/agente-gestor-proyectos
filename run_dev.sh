#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Agente Gestor de Proyectos - Inicio de Desarrollo"
echo "====================================================="
echo ""

VENV_DIR=".venv"
PY_CMD="${PY:-python3}"

# Verificar versión de Python
echo "🔍 Verificando Python..."
if ! command -v ${PY_CMD} &> /dev/null; then
    echo "❌ ERROR: Python 3 no encontrado. Instala Python 3.10+ primero."
    exit 1
fi

PY_VERSION=$(${PY_CMD} --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "   ✓ Python ${PY_VERSION} encontrado"

# Crear venv si no existe
if [ ! -d "${VENV_DIR}" ]; then
  echo ""
  echo "📦 Creando entorno virtual..."
  ${PY_CMD} -m venv "${VENV_DIR}"
  echo "   ✓ Entorno ${VENV_DIR} creado"
else
  echo "   ✓ Entorno ${VENV_DIR} existente"
fi

# Activar venv
echo ""
echo "🔧 Activando entorno virtual..."
if [ -f "${VENV_DIR}/bin/activate" ]; then
  source "${VENV_DIR}/bin/activate"
  echo "   ✓ Entorno activado"
else
  echo "❌ ERROR: No se encontró ${VENV_DIR}/bin/activate"
  exit 1
fi

# Configurar .env
echo ""
echo "⚙️  Verificando configuración..."
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "   ⚠️  Creado .env desde .env.example"
    echo "   📝 IMPORTANTE: Edita .env con tus API keys antes de usar el sistema"
  else
    echo "   ⚠️  No existe .env.example, crea .env manualmente"
  fi
else
  echo "   ✓ Archivo .env configurado"
fi

# Validar API keys
if [ -f ".env" ]; then
  source .env
  if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "   ⚠️  WARNING: OPENAI_API_KEY no configurada en .env"
  else
    echo "   ✓ OPENAI_API_KEY encontrada"
  fi
fi

# Instalar dependencias
echo ""
echo "📚 Instalando dependencias..."
if [ -f "requirements.txt" ]; then
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
  echo "   ✓ Dependencias instaladas (11 principales)"
else
  echo "   ❌ ERROR: requirements.txt no encontrado"
  exit 1
fi

# Verificar ChromaDB
echo ""
echo "🗄️  Verificando base de datos RAG..."
if [ -d "data/rag/chroma_db" ]; then
  TASK_COUNT=$(find data/rag/chroma_db -name "*.bin" 2>/dev/null | wc -l)
  if [ $TASK_COUNT -gt 0 ]; then
    echo "   ✓ ChromaDB inicializada con datos"
  else
    echo "   ⚠️  ChromaDB existe pero vacía"
    echo "   💡 Ejecuta: python run_pipeline.py --all"
  fi
else
  echo "   ⚠️  ChromaDB no inicializada"
  echo "   💡 Ejecuta: python run_pipeline.py --all"
fi

# Arrancar Chainlit
echo ""
echo "🌐 Iniciando servidor Chainlit..."
echo "   📍 URL: http://localhost:8000"
echo "   ⌨️  Ctrl+C para detener"
echo ""
exec "${VENV_DIR}/bin/chainlit" run main.py -w
