# meeting-assistant-agent
Asistente para organizar información en reuniones.

## Inicio rápido (Windows PowerShell)

1) Crear y activar entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Copiar variables de ejemplo y completar claves:

```powershell
copy .env.example .env   # editar .env y añadir claves (p. ej. OPENAI_API_KEY)
```

3) Instalar dependencias:

```powershell
pip install -r requirements.txt
```

4) Ejecutar (desarrollo):

```powershell
.\.venv\Scripts\python.exe -m chainlit run main.py --watch
```

También hay un script `run_dev.ps1` que automatiza estos pasos (crear/activar venv, copiar `.env`, instalar deps y ejecutar). Para usarlo:

```powershell
# Permitir scripts solo para esta sesión (si es necesario)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_dev.ps1
```

Eso es todo: abre http://localhost:8000 en tu navegador para ver la interfaz de Chainlit.

## Uso en WSL / Linux (Bash)

 1) crea un virtualenv `.venv` si no existe,
 2) lo activa en la shell actual,
 3) copia `.env.example` a `.env` si hace falta,
 4) instala dependencias desde `requirements.txt`,
 5) arranca Chainlit con: `python -m chainlit run main.py --watch`.

Pasos (desde la raíz del repo, en WSL):

```bash
chmod +x ./run_dev.sh
./run_dev.sh
```

Notas importantes:
- No mezcles virtualenvs de Windows y WSL. Cada entorno debe crear su propio `.venv`.
- Si prefieres usar comandos separados (setup/start/test) puedes adaptar `run_dev.sh` para añadir subcomandos.
- Si `chainlit` no está instalado en el venv, `run_dev.sh` instalará las dependencias y arrancará si la dependencia aparece en `requirements.txt`.