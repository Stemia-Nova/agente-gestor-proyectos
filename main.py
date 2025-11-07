"""Entrypoint mínimo para Chainlit.

Este archivo ya no define handlers para evitar respuestas duplicadas (echo).
Importamos `chatbot.handlers` para que los handlers definidos en ese paquete
se registren automáticamente con Chainlit.
"""

# Importar los handlers del paquete chatbot (registro de handlers ocurre en ese módulo).
import chatbot.handlers  # noqa: F401
