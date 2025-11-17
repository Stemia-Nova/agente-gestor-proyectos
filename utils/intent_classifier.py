#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Clasificador de intenciones usando LLM.
Detecta dinámicamente el tipo de consulta sin reglas hardcodeadas.
"""

import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Clasifica la intención de una consulta usando LLM."""
    
    INTENT_PROMPT = """Eres un clasificador de intenciones para un sistema de gestión de tareas.

Analiza la siguiente pregunta y clasifícala en UNA de estas categorías:

1. COUNT_TASKS: Pregunta sobre cantidad de tareas (ej: "¿cuántas tareas hay?", "¿cuántas tiene Jorge?")
2. CHECK_EXISTENCE: Pregunta sobre si existe algo (ej: "¿hay comentarios?", "¿existe alguna tarea bloqueada?")
3. TASK_INFO: Pregunta sobre información de una tarea específica (ej: "dame info de esa tarea", "¿qué prioridad tiene?")
4. SPRINT_REPORT: Solicitud de informe o resumen (ej: "genera informe del sprint 2", "resume el sprint")
5. LIST_TASKS: Solicitud de listar tareas (ej: "lista las tareas de Jorge", "muéstrame las bloqueadas")
6. GENERAL_QUERY: Pregunta general que requiere búsqueda semántica

Además, extrae estos atributos si están presentes:
- entity_type: persona, sprint, estado, etiqueta, comentario, subtarea, prioridad, etc.
- entity_value: el valor específico (ej: "Jorge", "Sprint 3", "bloqueada", "comentarios")
- filter_type: si aplica filtro (sprint, status, person, tags, has_comments, has_subtasks)
- filter_value: valor del filtro

Pregunta: {query}

Responde SOLO con JSON válido:
{{
  "intent": "COUNT_TASKS|CHECK_EXISTENCE|TASK_INFO|SPRINT_REPORT|LIST_TASKS|GENERAL_QUERY",
  "confidence": 0.0-1.0,
  "entity_type": "string o null",
  "entity_value": "string o null",
  "filter_type": "string o null",
  "filter_value": "string o null",
  "requires_context": true|false
}}"""

    def __init__(self):
        """Inicializa el clasificador."""
        self.client = None
        self._ensure_client()
    
    def _ensure_client(self):
        """Asegura que el cliente OpenAI esté inicializado."""
        if self.client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY no está configurada")
            self.client = OpenAI(api_key=api_key)
            logger.info("✅ Cliente OpenAI inicializado para clasificador de intenciones")
    
    def classify(self, query: str) -> Dict[str, Any]:
        """
        Clasifica la intención de una consulta.
        
        Args:
            query: La consulta del usuario
            
        Returns:
            Dict con: intent, confidence, entity_type, entity_value, filter_type, filter_value, requires_context
        """
        try:
            self._ensure_client()
            
            # Verificar que el cliente está inicializado
            if self.client is None:
                raise ValueError("Cliente OpenAI no inicializado")
            
            prompt = self.INTENT_PROMPT.format(query=query)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un clasificador experto de intenciones. Responde SOLO con JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Baja temperatura para respuestas consistentes
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Respuesta vacía del LLM")
            
            # Parsear JSON
            result = json.loads(content.strip())
            
            # Validar campos requeridos
            if "intent" not in result:
                raise ValueError("Falta campo 'intent' en la respuesta")
            
            logger.info(f"🎯 Intención clasificada: {result['intent']} (confianza: {result.get('confidence', 0):.2f})")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando JSON del clasificador: {e}")
            logger.error(f"Respuesta: {content if 'content' in locals() else 'N/A'}")
            return self._fallback_classification(query)
        except Exception as e:
            logger.error(f"❌ Error clasificando intención: {e}")
            return self._fallback_classification(query)
    
    def _fallback_classification(self, query: str) -> Dict[str, Any]:
        """Clasificación por defecto en caso de error."""
        query_lower = query.lower()
        
        # Clasificación básica basada en reglas
        if any(word in query_lower for word in ["cuántas", "cuantas", "cantidad", "número"]):
            intent = "COUNT_TASKS"
        elif any(word in query_lower for word in ["hay ", "existe", "alguna"]):
            intent = "CHECK_EXISTENCE"
        elif any(word in query_lower for word in ["esa tarea", "esa", "dame info", "información de"]):
            intent = "TASK_INFO"
        elif any(word in query_lower for word in ["informe", "reporte", "resumen del sprint"]):
            intent = "SPRINT_REPORT"
        elif any(word in query_lower for word in ["lista", "muestra", "cuáles son"]):
            intent = "LIST_TASKS"
        else:
            intent = "GENERAL_QUERY"
        
        return {
            "intent": intent,
            "confidence": 0.5,  # Baja confianza para fallback
            "entity_type": None,
            "entity_value": None,
            "filter_type": None,
            "filter_value": None,
            "requires_context": True
        }


# Singleton global
_classifier_instance: Optional[IntentClassifier] = None


def get_classifier() -> IntentClassifier:
    """Obtiene la instancia singleton del clasificador."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance
