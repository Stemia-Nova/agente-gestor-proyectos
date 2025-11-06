import chainlit as cl


@cl.on_chat_start
async def start():
    """Mensaje de bienvenida cuando arranca la sesión de chat."""
    await cl.Message(
        content="¡Hola! Soy tu asistente. Escribe algo y te responderé."
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Ejemplo mínimo: hace eco del mensaje recibido."""
    # `message` normalmente tiene el atributo `content`
    text = getattr(message, "content", str(message))
    await cl.Message(content=f"Has dicho: {text}").send()
