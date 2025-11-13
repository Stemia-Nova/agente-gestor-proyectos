import chainlit as cl
from chatbot import handlers
from chatbot.prompts import WELCOME_PROMPT

@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content=WELCOME_PROMPT).send()

@cl.on_message
async def on_message(message: cl.Message):
    response = await handlers.handle_query(message.content)
    await cl.Message(content=response).send()
