#!/usr/bin/env bash
set -euo pipefail

echo "== run_dev.sh: preparar entorno de desarrollo (WSL / Linux) =="

VENV_DIR=".venv"
PY_CMD="${PY:-python3}"

# 1) Crear venv si no existe
if [ ! -d "${VENV_DIR}" ]; then
  echo "Creando virtualenv ${VENV_DIR}..."
  ${PY_CMD} -m venv "${VENV_DIR}"
  echo "Entorno ${VENV_DIR} creado."
else
  echo "Entorno ${VENV_DIR} ya existe."
fi

# 2) Activar venv (en esta shell)
if [ -f "${VENV_DIR}/bin/activate" ]; then
  # shellcheck source=/dev/null
  source "${VENV_DIR}/bin/activate"
  echo "Virtualenv activado."
else
  echo "ERROR: no se encontró ${VENV_DIR}/bin/activate"
  exit 1
fi

# 3) Copiar .env.example a .env si falta
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Se ha creado .env desde .env.example. Rellena tus claves si es necesario."
  else
    echo "No existe .env.example: crea .env manualmente si hace falta."
  fi
else
  echo ".env ya existe."
fi

# 4) Instalar dependencias
if [ -f "requirements.txt" ]; then
  echo "Instalando dependencias..."
  pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "No se encontró requirements.txt, saltando instalación de dependencias."
fi

# 5) Arrancar Chainlit (si está instalado)
echo "Arrancando Chainlit... (Ctrl+C para detener)"
if command -v python >/dev/null 2>&1; then
  # Ejecutar con el python del venv
  "${VENV_DIR}/bin/python" -m chainlit run main.py --watch
else
  echo "ERROR: python no disponible en entorno. Asegúrate de activar el venv o instalar Python." 
  exit 1
fi
