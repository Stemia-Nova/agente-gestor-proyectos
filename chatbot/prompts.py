"""Plantilla de prompts y textos reutilizables para el chatbot."""

WELCOME_PROMPT = "¡Hola! Soy tu asistente. ¿En qué puedo ayudarte?"

DEFAULT_ECHO_PREFIX = "Has dicho:"


# Plantilla para incluir contexto RAG en la conversación.
# `context` será un texto con los fragmentos de tarea más relevantes.
RAG_CONTEXT_PROMPT = (
	"He encontrado información relevante en las tareas del proyecto. "
	"Úsala para responder la siguiente pregunta de forma concisa y orientada a acciones:\n\n"
	"Contexto:\n{context}\n\nPregunta: {question}\n\nRespuesta:")


# Plantilla de respuesta cuando no se encuentran resultados.
RAG_NO_RESULTS = "No he encontrado tareas relevantes para esa consulta. ¿Quieres que busque en todo el proyecto o en otro sprint?"
