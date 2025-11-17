import chainlit as cl
from chatbot import handlers
from chatbot.prompts import WELCOME_PROMPT

@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content=WELCOME_PROMPT).send()

@cl.on_message
async def on_message(message: cl.Message):
    response, pdf_path = await handlers.handle_query(message.content)
    
    # Si hay PDF, enviarlo como archivo
    if pdf_path:
        await cl.Message(
            content=response,
            elements=[cl.File(name="informe_sprint.pdf", path=pdf_path, display="inline")]
        ).send()
    else:
        await cl.Message(content=response).send()
