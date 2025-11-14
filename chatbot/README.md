# 💬 Chatbot Module - Documentación

Sistema conversacional basado en **Chainlit** que proporciona una interfaz web para interactuar con el sistema RAG de gestión de proyectos.

---

## 📋 Estructura del Módulo

```
chatbot/
├── __init__.py          # Inicialización del módulo
├── config.py            # Configuración del chatbot
├── handlers.py          # Manejadores de eventos de Chainlit
└── prompts.py           # Templates de prompts y mensajes
```

---

## 🎯 Componentes Principales

### 1. `config.py` - Configuración

Centraliza toda la configuración del chatbot:

```python
# Modelos
OPENAI_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L12-v2"

# Parámetros de búsqueda
TOP_K_RESULTS = 6
HYBRID_WEIGHTS = {"semantic": 0.7, "lexical": 0.3}

# UI Settings
CHAINLIT_THEME = "light"
AVATAR_USER = "👤"
AVATAR_ASSISTANT = "🤖"
```

### 2. `handlers.py` - Lógica de Eventos

Maneja los eventos del ciclo de vida de Chainlit:

#### `@cl.on_chat_start`
Se ejecuta cuando un usuario inicia una conversación:
- Inicializa `HybridSearch`
- Muestra mensaje de bienvenida
- Prepara contexto de sesión

#### `@cl.on_message`
Procesa cada mensaje del usuario:
1. **Detección de intención**: Identifica si es búsqueda, informe, métricas, etc.
2. **Búsqueda híbrida**: Recupera contexto relevante con RAG
3. **Generación de respuesta**: Usa GPT-4 con contexto
4. **Comandos especiales**:
   - `pdf` → Genera informe PDF
   - `métricas` / `estadísticas` → Muestra resumen numérico
   - `comparar sprints` → Compara múltiples sprints

### 3. `prompts.py` - Templates de Mensajes

Define todos los prompts y mensajes del sistema:

```python
WELCOME_PROMPT = """
👋 ¡Bienvenido al Agente Gestor de Proyectos!

Puedo ayudarte con:
🔍 Consultar tareas y sprints
📊 Generar métricas y reportes
📄 Crear informes PDF profesionales
...
"""

SYSTEM_PROMPT = """
Eres un asistente experto en gestión de proyectos...
[Instrucciones para el LLM]
"""
```

---

## 🚀 Flujo de una Consulta

```
Usuario: "¿Qué tareas están bloqueadas en Sprint 3?"
   ↓
[1. on_message handler]
   ↓
[2. Detección de intención]
   - Tipo: búsqueda + filtro
   - Filtros: sprint="Sprint 3", is_blocked=true
   ↓
[3. Hybrid Search]
   - Búsqueda semántica: "tareas bloqueadas"
   - Filtro metadata: sprint="Sprint 3"
   - Resultados: 2 tareas encontradas
   ↓
[4. Construcción de contexto]
   - Contexto: Tareas [CREAR RAG, Integrar API]
   - Metadata: Estados, prioridades, comentarios
   ↓
[5. Generación con GPT-4]
   - Prompt: SYSTEM_PROMPT + contexto + pregunta
   - Respuesta: Lista de tareas bloqueadas con detalles
   ↓
[6. Envío a UI]
   - Formato markdown
   - Elementos interactivos (si aplica)
```

---

## ⚙️ Personalización

### Agregar Nuevo Comando

En `handlers.py`:

```python
@cl.on_message
async def handle_message(message: cl.Message):
    query = message.content.lower()
    
    # Agregar detección de nuevo comando
    if "resumen semanal" in query:
        response = await generate_weekly_summary()
        await cl.Message(content=response).send()
        return
    
    # ... resto del código
```

### Modificar Prompt del Sistema

En `prompts.py`:

```python
SYSTEM_PROMPT = """
Eres un asistente especializado en metodologías ágiles.

Características:
- Responde en español con terminología Scrum
- Sé conciso pero completo
- Sugiere mejoras cuando veas oportunidades
- Prioriza tareas críticas y bloqueadores

[Tu personalización aquí]
"""
```

### Cambiar Estilo Visual

En `config.py`:

```python
# Tema oscuro
CHAINLIT_THEME = "dark"

# Avatares personalizados
AVATAR_USER = "assets/user.png"
AVATAR_ASSISTANT = "assets/bot.png"

# Colores personalizados
PRIMARY_COLOR = "#FF6B6B"
SECONDARY_COLOR = "#4ECDC4"
```

---

## 🎨 Características Avanzadas

### 1. Memoria Contextual

El chatbot mantiene contexto de conversación:

```python
# En handlers.py
cl.user_session.set("conversation_history", [])

# Al procesar mensaje
history = cl.user_session.get("conversation_history")
history.append({"role": "user", "content": query})
```

### 2. Elementos Interactivos

```python
# Botones de acción rápida
actions = [
    cl.Action(name="generar_pdf", value="Sprint 3", label="📄 Generar PDF"),
    cl.Action(name="ver_metricas", value="Sprint 3", label="📊 Ver Métricas")
]

await cl.Message(
    content="¿Qué deseas hacer?",
    actions=actions
).send()
```

### 3. Streaming de Respuestas

```python
# Para respuestas largas, usa streaming
async with cl.Step(name="Generando respuesta..."):
    msg = cl.Message(content="")
    await msg.send()
    
    async for chunk in generate_streaming_response(query):
        await msg.stream_token(chunk)
    
    await msg.update()
```

---

## 🧪 Testing del Chatbot

```bash
# Test end-to-end
pytest test/test_chatbot_end2end_mixed.py -v

# Test de búsqueda híbrida
pytest test/test_hybrid_search.py -v

# Test de consultas naturales
pytest test/test_natural_queries.py -v
```

### Ejemplo de Test

```python
# test/test_chatbot_end2end_mixed.py
import pytest
from chatbot.handlers import process_query

@pytest.mark.asyncio
async def test_blocked_tasks_query():
    query = "¿Qué tareas están bloqueadas?"
    response = await process_query(query)
    
    assert "bloqueada" in response.lower()
    assert len(response) > 50  # Respuesta sustantiva
```

---

## 🐛 Troubleshooting

### Error: "OpenAI API key not found"
**Solución**: Verifica que `OPENAI_API_KEY` esté en `.env`

### Error: "ChromaDB collection not found"
**Solución**: Ejecuta `make index` para crear la colección

### Respuestas lentas
**Causas posibles**:
- Primera carga de modelos (normal)
- Embeddings en CPU (considera GPU)
- Rate limiting de OpenAI API

**Solución**: 
- Usa caché para embeddings frecuentes
- Reduce `TOP_K_RESULTS` en config
- Considera modelos locales

---

## 📚 Referencias

- **Chainlit Docs**: https://docs.chainlit.io/
- **OpenAI API**: https://platform.openai.com/docs
- **Hybrid Search**: [`utils/README.md`](../utils/README.md)

---

<div align="center">
  <strong>Chatbot diseñado para productividad y experiencia de usuario</strong>
</div>
