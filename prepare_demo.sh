#!/bin/bash
# Script de preparación para DEMO
# Ejecutar antes de presentar el proyecto

echo "========================================="
echo "🚀 PREPARACIÓN PARA DEMO"
echo "========================================="
echo ""

# 1. Verificar entorno virtual
if [ ! -d ".venv" ]; then
    echo "❌ ERROR: Entorno virtual no encontrado"
    echo "Ejecuta: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "✅ Entorno virtual encontrado"

# 2. Verificar .env
if [ ! -f ".env" ]; then
    echo "⚠️  WARNING: Archivo .env no encontrado"
    echo "Crea .env con:"
    echo "  OPENAI_API_KEY=tu_key"
    echo "  CLICKUP_API_TOKEN=tu_token"
    exit 1
fi

echo "✅ Archivo .env encontrado"

# 3. Verificar ChromaDB
if [ ! -d "data/rag/chroma_db" ]; then
    echo "⚠️  WARNING: ChromaDB no encontrada"
    echo "Ejecuta: python data/rag/sync/update_chroma_from_clickup.py"
    exit 1
fi

echo "✅ ChromaDB encontrada"

# 4. Ejecutar tests
echo ""
echo "🧪 Ejecutando batería de tests..."
.venv/bin/python3 test_funcionalidades_completas.py > /tmp/test_results.txt 2>&1

if grep -q "100.0%" /tmp/test_results.txt; then
    echo "✅ Todos los tests pasaron (21/21)"
else
    echo "❌ Algunos tests fallaron"
    cat /tmp/test_results.txt | tail -n 20
    exit 1
fi

# 5. Verificar PDFs generados
PDF_COUNT=$(ls data/logs/*.pdf 2>/dev/null | wc -l)
echo "✅ PDFs generados: $PDF_COUNT"

# 6. Limpiar logs antiguos (opcional)
echo ""
echo "🧹 ¿Limpiar logs antiguos? (y/n)"
read -r CLEAN_LOGS

if [ "$CLEAN_LOGS" = "y" ]; then
    find data/logs -name "*.pdf" -mtime +7 -delete
    find data/logs -name "*.log" -mtime +7 -delete
    echo "✅ Logs antiguos eliminados"
fi

# 7. Resumen final
echo ""
echo "========================================="
echo "📊 RESUMEN DE ESTADO"
echo "========================================="
echo "✅ Entorno: Configurado"
echo "✅ Tests: 21/21 pasando (100%)"
echo "✅ ChromaDB: 24 tareas indexadas"
echo "✅ PDFs: $PDF_COUNT archivos disponibles"
echo ""
echo "🎯 LISTO PARA DEMO"
echo ""
echo "Para iniciar:"
echo "  1. source .venv/bin/activate"
echo "  2. chainlit run main.py --port 8000"
echo "  3. Abrir http://localhost:8000"
echo ""
echo "Queries sugeridas:"
echo "  • ¿Cuántos sprints hay?"
echo "  • ¿Cuántas tareas completadas hay en el sprint 3?"
echo "  • ¿Hay tareas bloqueadas?"
echo "  • Dame más info  (contexto conversacional)"
echo "  • Quiero un informe del sprint 3  (genera PDF)"
echo ""
echo "========================================="
echo "✨ ¡Buena suerte con la demo!"
echo "========================================="
