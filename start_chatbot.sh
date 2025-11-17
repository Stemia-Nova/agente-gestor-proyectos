#!/bin/bash
# Script para iniciar Chainlit con el chatbot

echo "========================================="
echo "🚀 INICIANDO CHATBOT CHAINLIT"
echo "========================================="
echo ""

# Activar entorno virtual
source .venv/bin/activate

# Iniciar Chainlit
echo "🌐 Abriendo interfaz en http://localhost:8000"
echo ""
echo "📝 Queries sugeridas para probar:"
echo "   • ¿Cuántas tareas hay en total?"
echo "   • ¿Y en el Sprint 3?"
echo "   • ¿Cuántas están completadas?"
echo "   • ¿Hay alguna bloqueada?"
echo "   • Dame más info"
echo ""
echo "🛑 Presiona Ctrl+C para detener"
echo ""
echo "========================================="
echo ""

chainlit run main.py --port 8000
