# build.ps1
# =====================================================
# RAG Project Automation Pipeline (versión PowerShell)
# Ejecuta: limpieza → naturalización → chunk → index
# =====================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot  # asegúrate de estar en la raíz del proyecto

function Run-Step($description, $scriptPath) {
    Write-Host ""
    Write-Host "▶️  $description..."
    python $scriptPath
    if ($LASTEXITCODE -ne 0) {
        throw "❌ Error ejecutando $scriptPath"
    }
    Write-Host "✅  $scriptPath completado."
}

param(
    [ValidateSet("build","clean","clean_tasks","naturalize","chunk","index")]
    [string]$Task = "build"
)

switch ($Task) {
    "clean_tasks" {
        Run-Step "🧹 Ejecutando limpieza de tareas ClickUp" "utils/clean_tasks.py"
    }
    "naturalize" {
        Run-Step "🧠 Naturalizando tareas" "data/rag/transform/01_naturalize_tasks.py"
    }
    "chunk" {
        Run-Step "✂️ Generando chunks de texto" "data/rag/chunk/02_chunk_tasks.py"
    }
    "index" {
        Run-Step "🧠 Indexando en ChromaDB" "data/rag/index/03_index_vector_chroma.py"
    }
    "clean" {
        Write-Host "🗑️ Limpiando archivos generados..."
        Remove-Item -Recurse -Force "data/processed/*.jsonl","data/rag/chroma_db" -ErrorAction SilentlyContinue
        Write-Host "✅ Limpieza completada."
    }
    "build" {
        Run-Step "🧹 Ejecutando limpieza de tareas ClickUp" "utils/clean_tasks.py"
        Run-Step "🧠 Naturalizando tareas" "data/rag/transform/01_naturalize_tasks.py"
        Run-Step "✂️ Generando chunks de texto" "data/rag/chunk/02_chunk_tasks.py"
        Run-Step "🧠 Indexando en ChromaDB" "data/rag/index/03_index_vector_chroma.py"
        Write-Host ""
        Write-Host "✅ Pipeline RAG ejecutado correctamente."
    }
}
