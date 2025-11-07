import re
import asyncio
import time
import random
import os
import chainlit as cl

from utils.hybrid_search import HybridSearch
from chatbot import prompts
from chatbot import config as chat_config

try:
    import openai
except Exception:
    openai = None


# Instancia de HybridSearch compartida (lazy init).
_HS_INSTANCE = None


def _ensure_hs():
    global _HS_INSTANCE
    if _HS_INSTANCE is None:
        # Inicializar en modo 'basic' por defecto. Cambiar si se desea 'pro'.
        _HS_INSTANCE = HybridSearch(data_path="data/processed/task_chunks.jsonl", mode="basic")
    return _HS_INSTANCE


def _extract_title(text: str) -> str:
    m = re.search(r"La tarea '([^']+)'", text)
    if m:
        return m.group(1)
    return "(sin título)"


def _format_results(results: list) -> str:
    # Formato más legible y con valores por defecto claros
    parts = []
    for i, r in enumerate(results, start=1):
        meta = r.get("metadata", {}) or {}
        task_id = meta.get("task_id") or "-"
        sprint = meta.get("sprint") or "-"
        project = meta.get("project") or "-"
        status = meta.get("status") or "-"
        priority = meta.get("priority") or "sin prioridad"
        assignees = meta.get("assignees") or "sin asignar"
        title = _extract_title(r.get("text", ""))
        snippet = r.get("text", "").strip().replace("\n", " ")
        # Acortar snippet si es muy largo
        if len(snippet) > 300:
            snippet = snippet[:300].rstrip() + "..."

        # Asegurar separación y signos de puntuación
        parts.append(
            f"{i}. [{task_id}] '{title}'\n"
            f"   Proyecto: {project} | Sprint: {sprint}\n"
            f"   Estado: {status} | Prioridad: {priority} | Asignados: {assignees}\n"
            f"   Descripción: {snippet}\n"
        )

    return "\n".join(parts)


async def _run_semantic_search(query: str, top_k: int = 5):
    """Ejecuta semantic_search y rerank en un executor para no bloquear el event loop."""
    hs = _ensure_hs()
    loop = asyncio.get_running_loop()

    results = await loop.run_in_executor(None, hs.semantic_search, query, top_k)
    # Re-rankeamos (también en executor)
    ranked = await loop.run_in_executor(None, hs.rerank, query, results, min(3, len(results)))
    return ranked


from typing import Optional


def _build_prompt(context: str, question: str) -> str:
    """Construye y devuelve el prompt exacto que se envía al modelo."""
    return prompts.RAG_CONTEXT_PROMPT.format(context=context, question=question)


def _synthesize_sync_openai(context: str, question: str, model: str = "gpt-4o-mini") -> str:
    """Genera una respuesta usando la API de OpenAI (síncrono, para ejecutar en executor)."""
    if openai is None:
        raise RuntimeError("La librería 'openai' no está instalada")

    api_key = getattr(chat_config, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no configurada en `chatbot.config`")
    # Prefer to provide the API key via environment so modern clients pick it up
    os.environ.setdefault("OPENAI_API_KEY", api_key)

    prompt = _build_prompt(context, question)

    messages = [
        {"role": "system", "content": "Eres un asistente conciso, objetivo y orientado a acciones. Usa únicamente la información del contexto para responder y señala cuando algo no está en el contexto."},
        {"role": "user", "content": prompt},
    ]

    # Compatibilidad con distintas versiones del SDK y reintentos ante 429
    max_retries = 3
    attempt = 0
    base_backoff = 0.5

    openai_dict = getattr(openai, "__dict__", {}) or {}
    OpenAIClient = openai_dict.get("OpenAI")
    ChatCompletion = openai_dict.get("ChatCompletion")

    last_exc = None
    while attempt <= max_retries:
        try:
            # 1) Si existe el cliente moderno, intentar usarlo
            if OpenAIClient:
                # Intentar crear cliente con api_key si acepta
                try:
                    client = OpenAIClient(api_key=api_key)
                except TypeError:
                    client = OpenAIClient()

                # Varias rutas posibles según implementación
                chat_attr = getattr(client, "chat", None)
                if chat_attr is not None:
                    completions = getattr(chat_attr, "completions", None)
                    if completions is not None and hasattr(completions, "create"):
                        resp = completions.create(model=model, messages=messages, max_tokens=400, temperature=0.0)
                    else:
                        # intentar top-level completions
                        completions_top = getattr(client, "completions", None)
                        if completions_top is not None and hasattr(completions_top, "create"):
                            resp = completions_top.create(model=model, messages=messages, max_tokens=400, temperature=0.0)
                        else:
                            raise RuntimeError("No se encontró un método de generación en el cliente OpenAI moderno.")
                else:
                    # Si el cliente moderno no expone .chat, intentar .completions
                    completions_top = getattr(client, "completions", None)
                    if completions_top is not None and hasattr(completions_top, "create"):
                        resp = completions_top.create(model=model, messages=messages, max_tokens=400, temperature=0.0)
                    else:
                        raise RuntimeError("No se encontró un método de generación en el cliente OpenAI moderno.")

            else:
                # 2) Fallback a ChatCompletion clásico si existe
                if ChatCompletion and hasattr(ChatCompletion, "create"):
                    resp = ChatCompletion.create(model=model, messages=messages, max_tokens=400, temperature=0.0)
                else:
                    raise RuntimeError("No se encontró un cliente OpenAI compatible en el paquete 'openai'.")

            # Extraer texto de forma robusta
            # respuesta dict-like
            if isinstance(resp, dict):
                choices = resp.get("choices") or []
                if choices:
                    first = choices[0] or {}
                    if isinstance(first, dict):
                        msg = first.get("message") or {}
                        text = msg.get("content") or first.get("text")
                        if text:
                            return text.strip()
            else:
                # objeto con atributos
                try:
                    choices = getattr(resp, "choices", None)
                    if choices:
                        first = choices[0]
                        msg = getattr(first, "message", None)
                        # msg puede ser dict-like o un objeto con atributo 'content'
                        if isinstance(msg, dict):
                            text = msg.get("content")
                            if text:
                                return text.strip()
                        else:
                            # objeto con .content
                            text = getattr(msg, "content", None)
                            if text:
                                return text.strip()

                        # Intentar también extraer .text de ser aplicable
                        text = getattr(first, "text", None)
                        if text:
                            return text.strip()
                except Exception:
                    pass

            # Fallback: retornar string
            return str(resp)

        except Exception as e:
            last_exc = e
            # Detectar 429 / rate limit por varias señales
            status_code = getattr(e, "http_status", None) or getattr(e, "status_code", None)
            msg = str(e).lower()
            is_rate = False
            if status_code == 429:
                is_rate = True
            if "too many requests" in msg or "rate limit" in msg or "429" in msg:
                is_rate = True

            attempt += 1
            if is_rate and attempt <= max_retries:
                backoff = base_backoff * (2 ** (attempt - 1))
                # jitter
                backoff = backoff + random.uniform(0, 0.3)
                time.sleep(backoff)
                continue
            # No se puede recuperar o excedimos reintentos: propagar
            raise

    # Si salimos del loop sin resultado, mostrar último error
    if last_exc:
        raise last_exc
    raise RuntimeError("No se obtuvo respuesta del servicio OpenAI")


@cl.on_chat_start
async def start():
    """Mensaje de bienvenida (plantilla)."""
    await cl.Message(content=prompts.WELCOME_PROMPT).send()


@cl.on_message
async def on_message(message: cl.Message):
    text = getattr(message, "content", "") or ""
    text = text.strip()

    if not text:
        await cl.Message(content="No he recibido ninguna pregunta. Escribe algo sobre las tareas (por ejemplo: '¿Qué tareas están bloqueadas?')").send()
        return

    # Ejecutar búsqueda RAG
    try:
        ranked = await _run_semantic_search(text, top_k=5)
    except FileNotFoundError:
        await cl.Message(content="No se encontró la fuente de datos RAG (data/processed/task_chunks.jsonl). Ejecuta el pipeline de indexado primero.").send()
        return
    except Exception as e:
        await cl.Message(content=f"Error durante la búsqueda de contexto: {e}").send()
        return

    if not ranked:
        await cl.Message(content=prompts.RAG_NO_RESULTS).send()
        return

    # Si la pregunta menciona bloqueo o 'bloquead', priorizar resultados con metadata is_blocked o tags que contengan 'bloque'
    ql = text.lower()
    try:
        if "bloque" in ql:
            blocked = [r for r in ranked if (r.get("metadata", {}) or {}).get("is_blocked") or ("bloque" in ((r.get("metadata", {}) or {}).get("tags") or ""))]
            if blocked:
                ranked = blocked

        # Priorizar urgentes si la pregunta lo solicita
        if "urg" in ql:  # cubre 'urgente' o 'urgent'
            urgent = [r for r in ranked if ((r.get("metadata", {}) or {}).get("priority") or "").lower().startswith("urg")]
            if urgent:
                ranked = urgent
    except Exception:
        # no bloquear el flujo si la inspección de metadata falla
        pass

    # Formatear contexto y responder
    context_text = _format_results(ranked)

    # Intentar sintetizar automáticamente la respuesta con un modelo Hugging Face
    loop = asyncio.get_running_loop()
    # Detectar petición de debug en la pregunta del usuario
    debug = any(k in text.lower() for k in ("ver respuesta", "ver la respuesta", "mostrar prompt", "mostrar contexto", "debug"))

    # Construir prompt para poder mostrarlo si el usuario lo solicita
    prompt_text = _build_prompt(context_text, text)

    try:
        # Prefer OpenAI when an API key is configured
        use_openai = (openai is not None) and bool(getattr(chat_config, "OPENAI_API_KEY", None))
        if use_openai:
            synthesized = await loop.run_in_executor(None, _synthesize_sync_openai, context_text, text)
        else:
            # No OpenAI: fallback to sending fragments and suggesting configuration
            final = f"He encontrado {len(ranked)} fragmentos relevantes.\n\n{context_text}\n\nPara obtener una respuesta en lenguaje natural y más concisa, configura la variable de entorno OPENAI_API_KEY y reinicia el servicio."
            await cl.Message(content=final).send()
            if debug:
                await cl.Message(content=f"DEBUG - Prompt (would be):\n\n{prompt_text}").send()
                task_ids = ", ".join([(r.get("metadata", {}) or {}).get("task_id", "-") for r in ranked])
                await cl.Message(content=f"DEBUG - Task IDs utilizados: {task_ids}\nFuente: data/processed/task_chunks.jsonl").send()
            return

        # Si la síntesis devuelve algo vacío o demasiado corto, enviar el contexto en bruto
        if not synthesized or len(synthesized.strip()) < 10:
            final = f"He encontrado {len(ranked)} fragmentos relevantes.\n\n{context_text}\n\n(La síntesis devolvió poco contenido.)"
            await cl.Message(content=final).send()
            # Si debug, también mostrar prompt y task ids
            if debug:
                await cl.Message(content=f"DEBUG - Prompt usado:\n\n{prompt_text}").send()
                task_ids = ", ".join([(r.get("metadata", {}) or {}).get("task_id", "-") for r in ranked])
                await cl.Message(content=f"DEBUG - Task IDs utilizados: {task_ids}\nFuente: data/processed/task_chunks.jsonl").send()
            return

        # Enviar la respuesta sintetizada
        await cl.Message(content=synthesized).send()
        # Si el usuario pidió ver la respuesta / prompt, añadir el prompt y fuente
        if debug:
            await cl.Message(content=f"DEBUG - Prompt usado:\n\n{prompt_text}").send()
            task_ids = ", ".join([(r.get("metadata", {}) or {}).get("task_id", "-") for r in ranked])
            await cl.Message(content=f"DEBUG - Task IDs utilizados: {task_ids}\nFuente: data/processed/task_chunks.jsonl").send()
        return
    except Exception as e:
        # Fallback: enviar fragmentos y un aviso de error en la síntesis
        final = f"No ha sido posible sintetizar la respuesta con el modelo local: {e}\n\nEnvío los fragmentos relevantes:\n\n{context_text}"
        await cl.Message(content=final).send()
        return
