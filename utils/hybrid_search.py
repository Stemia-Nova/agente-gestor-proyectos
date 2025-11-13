#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HybridSearch — versión extendida con GPT-4o-mini
------------------------------------------------
Motor central del agente gestor:
 • Recuperación híbrida (embeddings + rerank)
 • Integración con ChromaDB persistente
 • Generación natural de respuesta usando GPT-4o-mini
 • Filtros inteligentes con sintaxis $and de ChromaDB
 • Post-filtrado para campos booleanos
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional, cast
import re
import numpy as np
import torch
import chromadb
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
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
        self._rerank_tokenizer: Optional[Any] = None
        self._rerank_model: Optional[AutoModelForSequenceClassification] = None
        self._llm: Optional[OpenAI] = None

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # =============================================================
    # Embeddings y búsqueda
    # =============================================================
    def _ensure_embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            print("🧠 Cargando modelo de embeddings MiniLM...")
            self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")
        return self._embedder

    def _ensure_reranker(self):
        if self._rerank_model is None or self._rerank_tokenizer is None:
            print("🧩 Cargando modelo de reranking (MiniLM CrossEncoder)...")
            self._rerank_tokenizer = AutoTokenizer.from_pretrained("cross-encoder/ms-marco-MiniLM-L-12-v2")
            self._rerank_model = AutoModelForSequenceClassification.from_pretrained(
                "cross-encoder/ms-marco-MiniLM-L-12-v2"
            ).to(self.device)

    def _ensure_llm(self) -> OpenAI:
        if self._llm is None:
            self._llm = OpenAI()  # usa la variable de entorno OPENAI_API_KEY
        return self._llm

    def _embed_query(self, text: str) -> List[float]:
        model = self._ensure_embedder()
        emb = model.encode(text, convert_to_numpy=True)
        return emb.astype(np.float32).tolist()

    def search(
        self, 
        query: str, 
        top_k: int = 8,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        use_filters: bool = False
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Devuelve documentos relevantes según embeddings + rerank + filtros.
        
        Args:
            query: Texto de búsqueda
            top_k: Número de resultados
            where: Filtros de metadata (ej: {"status": "to_do", "sprint": "Sprint 1"})
            where_document: Filtros en el contenido del documento
            use_filters: Si True, extrae filtros automáticamente desde la query
            
        Returns:
            Tupla de (documentos, metadatas)
        """
        # Extraer filtros automáticamente si está habilitado
        post_filters = {}
        if use_filters and not where:
            where = self._extract_filters_from_query(query)
            # Extraer filtros booleanos para post-procesamiento
            if where and "is_blocked" in str(where):
                post_filters["is_blocked"] = True
                # Remover del where de ChromaDB
                where = self._remove_boolean_filters(where)
            if where:
                print(f"🔍 Filtros ChromaDB: {where}")
            elif post_filters:
                print(f"🔍 Solo post-filtros: {post_filters}")
        
        q_emb = self._embed_query(query)
        
        # Preparar parámetros de búsqueda
        search_params: Dict[str, Any] = {
            "query_embeddings": [q_emb],
            "n_results": top_k * 2 if post_filters else top_k,  # Pedir más si hay post-filtrado
            "include": cast(Any, ["documents", "metadatas"])
        }
        
        # Agregar filtros si existen
        if where:
            search_params["where"] = where
        if where_document:
            search_params["where_document"] = where_document
        
        res = self.collection.query(**search_params)

        docs_container = res.get("documents")
        metas_container = res.get("metadatas")

        docs = cast(List[str], docs_container[0] if docs_container and len(docs_container) > 0 else [])
        metas = cast(List[Dict[str, Any]], metas_container[0] if metas_container and len(metas_container) > 0 else [])

        if not docs or not metas:
            return [], []

        # Post-filtrado para campos booleanos
        if post_filters:
            filtered_docs, filtered_metas = [], []
            for doc, meta in zip(docs, metas):
                if all(meta.get(k) == v for k, v in post_filters.items()):
                    filtered_docs.append(doc)
                    filtered_metas.append(meta)
            docs, metas = filtered_docs[:top_k], filtered_metas[:top_k]
            if not docs:
                return [], []

        docs, metas = self._rerank(query, docs, metas)
        return docs, metas
    
    def _remove_boolean_filters(self, where: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Remueve filtros booleanos del dict para ChromaDB."""
        if "$and" in where:
            conditions = [c for c in where["$and"] if "is_blocked" not in c]
            if len(conditions) == 0:
                return None
            elif len(conditions) == 1:
                return conditions[0]
            else:
                return {"$and": conditions}
        else:
            filtered = {k: v for k, v in where.items() if k != "is_blocked"}
            return filtered if filtered else None

    # =============================================================
    # Reranking con CrossEncoder
    # =============================================================
    def _rerank(self, query: str, docs: List[str], metas: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
        self._ensure_reranker()
        assert self._rerank_tokenizer and self._rerank_model

        pairs = [(query, d) for d in docs]
        enc = self._rerank_tokenizer(
            [p[0] for p in pairs],
            [p[1] for p in pairs],
            padding=True,
            truncation=True,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self._rerank_model(**enc)
            scores = outputs.logits.squeeze(-1)

        idxs = torch.argsort(scores, descending=True).tolist()
        return [docs[i] for i in idxs], [metas[i] for i in idxs]

    # =============================================================
    # Detección inteligente de filtros desde query
    # =============================================================
    def _extract_filters_from_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Extrae filtros de metadata desde la query en lenguaje natural.
        
        Ejemplos:
        - "tareas pendientes" → {"status": "to_do"}
        - "tareas bloqueadas" → {"is_blocked": True}
        - "tareas del Sprint 1" → {"sprint": "Sprint 1"}
        - "tareas urgentes" → {"priority": "urgent"}
        - "tareas completadas Sprint 1" → {"$and": [{"status": "done"}, {"sprint": "Sprint 1"}]}
        """
        query_lower = query.lower()
        filters: Dict[str, Any] = {}
        
        # Detectar estados
        if "pendiente" in query_lower or "por hacer" in query_lower:
            filters["status"] = "to_do"
        elif "en progreso" in query_lower or "trabajando" in query_lower:
            filters["status"] = "in_progress"
        elif "qa" in query_lower or "testing" in query_lower or "prueba" in query_lower:
            filters["status"] = "qa"
        elif "review" in query_lower or "revisión" in query_lower or "revision" in query_lower:
            filters["status"] = "review"
        elif "completada" in query_lower or "finalizada" in query_lower or "hecha" in query_lower:
            filters["status"] = "done"
        elif "cancelada" in query_lower:
            filters["status"] = "cancelled"
        
        # Detectar flags (se manejarán con post-filtrado)
        if "bloqueada" in query_lower or "bloqueado" in query_lower:
            filters["is_blocked"] = True
        
        # Detectar sprint
        sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
        if sprint_match:
            filters["sprint"] = f"Sprint {sprint_match.group(1)}"
        
        # Detectar prioridad
        if "urgente" in query_lower:
            filters["priority"] = "urgent"
        elif "alta prioridad" in query_lower or "prioridad alta" in query_lower:
            filters["priority"] = "high"
        elif "baja prioridad" in query_lower or "prioridad baja" in query_lower:
            filters["priority"] = "low"
        
        # Si hay múltiples filtros NO BOOLEANOS, usar sintaxis $and de ChromaDB
        non_boolean_filters = {k: v for k, v in filters.items() if k != "is_blocked"}
        if len(non_boolean_filters) > 1:
            conditions = [{k: v} for k, v in non_boolean_filters.items()]
            result = {"$and": conditions}
            # Agregar is_blocked si estaba
            if "is_blocked" in filters:
                result["is_blocked"] = filters["is_blocked"]
            return result
        
        return filters if filters else None

    # =============================================================
    # Generador con GPT-4o-mini
    # =============================================================
    def answer(self, query: str, top_k: int = 6, temperature: float = 0.4, use_filters: bool = True) -> str:
        """Genera respuesta contextualizada con GPT-4o-mini usando prompts profesionales.
        
        Args:
            query: Pregunta del usuario
            top_k: Número de documentos a recuperar
            temperature: Temperatura del LLM (0-1)
            use_filters: Si True, extrae filtros de la query automáticamente
        """
        try:
            docs, metas = self.search(query, top_k=top_k, use_filters=use_filters)
            if not docs:
                return (
                    "No he encontrado tareas relevantes para esa consulta en el índice. "
                    "Puedes pedir que busque en todo el proyecto, en otro sprint, "
                    "o ejecutar el pipeline de indexado si los datos están desactualizados."
                )

            # Contexto enriquecido con todos los campos relevantes
            context_parts = []
            for m in metas[:top_k]:
                status_spanish = m.get('status_spanish', m.get('status', 'sin estado'))
                blocked = "⚠️ BLOQUEADA" if m.get('is_blocked') else ""
                context_parts.append(
                    f"• {m.get('name', 'sin nombre')} - {status_spanish} {blocked}\n"
                    f"  Sprint: {m.get('sprint', 'N/A')} | Prioridad: {m.get('priority', 'sin prioridad')}\n"
                    f"  Asignado: {m.get('assignees', 'sin asignar')}"
                )
            
            context = "\n\n".join(context_parts)

            # Usar prompts profesionales (basados en prompts.py)
            system_prompt = (
                "Eres un asistente experto en Scrum/Agile y en la gestión de tareas (ClickUp). "
                "Responde de forma concisa, evita la jerga innecesaria y no inventes información "
                "que no esté en el contexto proporcionado. "
                "Cuando la información sea incompleta, indícalo claramente y sugiere pasos para obtenerla. "
                "Prioriza acciones prácticas y asignables (quién debe hacer qué)."
            )

            user_prompt = (
                f"He identificado fragmentos relevantes en las tareas del proyecto. "
                f"Usa sólo la información dentro del contexto para responder la pregunta.\n\n"
                f"Contexto:\n{context}\n\n"
                f"Pregunta: {query}\n\n"
                f"Proporciona una única respuesta clara y directa en un solo párrafo (sin encabezados ni numeración).\n\n"
                f"Si hay acciones recomendadas, precede la lista con la línea exacta 'Acciones recomendadas:' "
                f"(sin comillas) y usa viñetas '- '. Para cada acción incluye: responsable (owner) "
                f"y prioridad (alta/media/baja). No uses numeración.\n\n"
                f"Si NO hay acciones recomendadas, no añadas ese encabezado.\n\n"
                f"Si alguna información no está disponible en el contexto, indícalo explícitamente y evita adivinar."
            )

            llm = self._ensure_llm()
            completion = llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )

            content = completion.choices[0].message.content
            return content.strip() if content else "No se pudo generar respuesta."

        except Exception as e:
            print(f"⚠️ Error en HybridSearch.answer(): {e}")
            return f"❌ No se pudo generar la respuesta: {e}"
