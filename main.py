import chainlit as cl
from chatbot import handlers

@cl.on_chat_start
async def on_chat_start():
    await cl.Message(
        content="👋 ¡Hola! Soy tu Agente Gestor de Proyectos.\n"
        "Puedes preguntarme sobre tareas, sprints, bloqueos o prioridades."
    ).send()

@cl.on_message
async def on_message(message: cl.Message):
    response = await handlers.handle_query(message.content)
    await cl.Message(content=response).send()
