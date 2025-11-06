<#
run_dev.ps1 - Script simple para desarrollo en Windows PowerShell

Qué hace:
  1) Crea un virtualenv `.venv` si no existe
  2) Activa el `.venv` en la sesión actual
  3) Copia `.env.example` a `.env` si no existe
  4) Instala las dependencias de `requirements.txt`
  5) Arranca Chainlit: `chainlit run chainlit_app.py --watch`

Uso:
  1) Abre PowerShell en la carpeta del proyecto
  2) (Opcional) Permite ejecución temporal de scripts:
     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  3) Ejecuta: .\run_dev.ps1
#>

Write-Host "== run_dev: preparar entorno de desarrollo =="

# 1) Crear venv si no existe
if (-not (Test-Path -Path ".\.venv")) {
    Write-Host "Creando entorno virtual .venv..."
    python -m venv .venv
    Write-Host "Entorno .venv creado."
} else {
    Write-Host "Entorno .venv ya existe."
}

# 2) Activar venv
Write-Host "Activando .venv..."
& .\.venv\Scripts\Activate.ps1

# 3) Copiar .env.example a .env si falta
if (-not (Test-Path -Path ".env")) {
    if (Test-Path -Path ".env.example") {
        Copy-Item .env.example .env
        Write-Host "Se ha creado .env desde .env.example. Rellena tus claves si es necesario."
    } else {
        Write-Host "No existe .env.example: crea .env manualmente si hace falta."
    }
} else {
    Write-Host ".env ya existe."
}

# 4) Instalar dependencias
Write-Host "Instalando dependencias..."
pip install -r requirements.txt

# 5) Arrancar Chainlit
Write-Host "Arrancando Chainlit... (Ctrl+C para detener)"
.\.venv\Scripts\python.exe -m chainlit run main.py --watch