#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HybridSearch — versión extendida con GPT-4o-mini
------------------------------------------------
Motor central del agente gestor:
 • Recuperación híbrida (embeddings + rerank)
 • Integración con ChromaDB persistente
 • Generación natural de respuesta usando GPT-4o-mini
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional, Sequence, cast
import numpy as np
import torch
import chromadb
from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import CrossEncoder
from openai import OpenAI


class HybridSearch:
    """Motor principal de búsqueda híbrida + generación conversacional."""

    def __init__(
        self,
        collection_name: str = "clickup_tasks",
        db_path: Optional[str] = None,
    ) -> None:
        self.db_path = db_path or "data/rag/chroma_db"
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(collection_name)
        print(f"✅ HybridSearch inicializado sobre colección '{collection_name}'.")

        # --- Inicialización diferida (lazy loading) ---
        self._embedder: Optional[SentenceTransformer] = None
        self._cross_encoder: Optional[CrossEncoder] = None

        # Cliente OpenAI
        self.llm = OpenAI()  # usa la variable de entorno OPENAI_API_KEY
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # =============================================================
    # Embeddings y búsqueda
    # =============================================================
    def _ensure_embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            print("🧠 Cargando modelo de embeddings MiniLM...")
            self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")
        return self._embedder

    def _ensure_reranker(self) -> CrossEncoder:
        # Backwards-compatible alias for reranker; delegate to the cross-encoder initializer.
        return self._ensure_cross_encoder()

    def _ensure_cross_encoder(self) -> CrossEncoder:
        if self._cross_encoder is None:
            print("🧩 Cargando modelo de reranking (MiniLM CrossEncoder)...")
            # CrossEncoder provides a convenient .predict(...) API for pairwise scoring
            self._cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2", device=str(self.device))
        return self._cross_encoder

    def _embed_query(self, text: str) -> List[float]:
        model = self._ensure_embedder()
        emb = model.encode(text, convert_to_numpy=True)
        return emb.astype(np.float32).tolist()

    def search(self, query: str, top_k: int = 8) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Devuelve documentos relevantes según embeddings + rerank."""
        q_emb = self._embed_query(query)
        res = self.collection.query(
            query_embeddings=[q_emb],
            n_results=top_k,
            include=cast(Any, ["documents", "metadatas"])
        )

        # Safely handle cases where the collection returns None for the lists
        docs_list = res.get("documents") or [[]]
        metas_list = res.get("metadatas") or [[]]

        docs = cast(
            List[str],
            docs_list[0] if isinstance(docs_list, (list, tuple)) and len(docs_list) > 0 and docs_list[0] is not None else []
        )
        metas = cast(
            List[Dict[str, Any]],
            metas_list[0] if isinstance(metas_list, (list, tuple)) and len(metas_list) > 0 and metas_list[0] is not None else []
        )

        if not docs or not metas:
            return [], []

        docs, metas = self._rerank(query, docs, metas)
        return list(docs), list(metas)

    # =============================================================
    # Reranking con CrossEncoder
    # =============================================================
    def _rerank(
        self,
        query: str,
        docs: Sequence[str],
        metas: Sequence[Dict[str, Any]],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        cross = self._ensure_cross_encoder()

        # Prepara pares (query, doc)
        pairs = [(query, d) for d in docs]

        # Predice scores; devuelve np.array de shape (len(docs),)
        scores = cross.predict(pairs, convert_to_numpy=True)
        # Orden descendente por score
        idxs = np.argsort(-scores).tolist()

        docs_sorted = [docs[i] for i in idxs]
        metas_sorted = [metas[i] for i in idxs]
        # Asegurar el tipo esperado por el anotador: List[str], List[Dict[str, Any]]
        return cast(List[str], docs_sorted), cast(List[Dict[str, Any]], metas_sorted)

    # =============================================================
    # Generador con GPT-4o-mini
    # =============================================================
    def answer(self, query: str, top_k: int = 6, temperature: float = 0.4) -> str:
        """Genera respuesta contextualizada con GPT-4o-mini."""
        try:
            docs, metas = self.search(query, top_k=top_k)
            if not docs:
                return "No encontré información relevante para esa consulta."

            # Contexto estructurado
            context = "\n".join(
                [
                    f"- {m.get('name', 'sin nombre')} ({m.get('status', 'sin estado')}, "
                    f"prioridad {m.get('priority', 'sin prioridad')}, sprint {m.get('sprint', 'sin sprint')})"
                    for m in metas[:5]
                ]
            )

            system_prompt = (
                "Eres un asistente experto en gestión de proyectos ágiles. "
                "Tienes acceso a datos de tareas de ClickUp y sprints. "
                "Usa el contexto proporcionado para responder de forma breve, clara y útil."
            )

            user_prompt = f"""
Pregunta del usuario:
{query}

Contexto relevante:
{context}

Responde con tono profesional tipo Scrum Master.
"""

            completion = self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )

            # Safely extract content from the completion object/dict, handling None or unexpected shapes
            content = None
            try:
                # Try attribute-style access first
                choices = getattr(completion, "choices", None)
                if choices is None and isinstance(completion, dict):
                    choices = completion.get("choices")
                if choices:
                    first_choice = choices[0]
                    message = getattr(first_choice, "message", None)
                    if message is None and isinstance(first_choice, dict):
                        message = first_choice.get("message")
                    if message:
                        content = getattr(message, "content", None)
                        if content is None and isinstance(message, dict):
                            content = message.get("content")
            except Exception:
                content = None

            if content:
                return content.strip()
            else:
                return "No se obtuvo contenido del modelo."

        except Exception as e:
            print(f"⚠️ Error en HybridSearch.answer(): {e}")
            return f"❌ No se pudo generar la respuesta: {e}"