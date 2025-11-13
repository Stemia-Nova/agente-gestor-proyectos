#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de informes automáticos con OpenAI gpt-4o-mini.
Optimizado para bajo coste y prompts cortos.
"""

from __future__ import annotations
import os
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam


class ReportGenerator:
    """Genera informes ejecutivos o resúmenes ágiles usando gpt-4o-mini."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("Falta OPENAI_API_KEY en entorno o parámetro.")
        self.client = OpenAI(api_key=self.api_key)

    def generate(self, topic: str, context_text: str, max_tokens: int = 350) -> str:
        """Genera un informe corto con gpt-4o-mini (bajo coste, español)."""

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente experto en gestión de proyectos ágiles. "
                    "Redacta un informe ejecutivo breve, claro y accionable en español. "
                    "Usa únicamente la información del contexto, sin inventar."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Genera un informe sobre '{topic}' a partir del siguiente contexto:\n\n"
                    f"{context_text}"
                ),
            },
        ]

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
        )

        # Evitar error 'strip no es atributo de None'
        content = getattr(response.choices[0].message, "content", "") or ""
        return content.strip()
