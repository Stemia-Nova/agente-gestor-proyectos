import chainlit as cl


@cl.on_chat_start
async def start():
    """Mensaje de bienvenida (plantilla).

    Importa este fichero desde `main.py` o registra sus handlers aquí cuando
    quieras mover la lógica del entrypoint a este paquete.
    """
    await cl.Message(content="¡Hola desde chatbot.handlers! (plantilla)").send()


@cl.on_message
async def on_message(message: cl.Message):
    text = getattr(message, "content", "")
    await cl.Message(content=f"Echo (desde chatbot.handlers): {text}").send()
