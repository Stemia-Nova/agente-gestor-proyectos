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
                import json
                where_str = json.dumps(where)
                if '"is_blocked": true' in where_str.lower():
                    post_filters["is_blocked"] = True
                    # Remover del where de ChromaDB
                    where = self._remove_boolean_filters(where)
            if where:
                print(f"🔍 Filtros ChromaDB: {where}")
            if post_filters:
                print(f"🔍 Post-filtros (Python): {post_filters}")
        
        q_emb = self._embed_query(query)
        
        # Preparar parámetros de búsqueda
        # Si solo hay post-filtros, necesitamos buscar TODOS los documentos relevantes
        # para luego filtrar en Python
        n_results = 50 if post_filters and not where else top_k
        search_params: Dict[str, Any] = {
            "query_embeddings": [q_emb],
            "n_results": n_results,
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
                matches = all(meta.get(k) == v for k, v in post_filters.items())
                if matches:
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
            return {k: v for k, v in where.items() if k != "is_blocked"} or None

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
            # Call the model directly (cast to Any to avoid type checker issues)
            outputs = cast(Any, self._rerank_model)(**enc)
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
        
        # Si hay múltiples filtros, usar sintaxis $and de ChromaDB
        if len(filters) > 1:
            conditions = [{k: v} for k, v in filters.items()]
            return {"$and": conditions}
        
        return filters if filters else None

    # =============================================================
    # Agregaciones y conteo
    # =============================================================
    def count_tasks(self, where: Optional[Dict[str, Any]] = None) -> int:
        """Cuenta tareas que coinciden con los filtros."""
        try:
            result = self.collection.get(where=where, limit=1000)
            return len(result['ids'])
        except Exception as e:
            print(f"⚠️ Error contando tareas: {e}")
            return 0
    
    def aggregate_by_field(self, field: str, where: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """Agrega tareas por un campo específico (sprint, status, priority, etc)."""
        try:
            result = self.collection.get(where=where, limit=1000)
            aggregation: Dict[str, int] = {}
            metadatas = result.get('metadatas') or []
            for meta in metadatas:
                value = str(meta.get(field, "Sin especificar"))
                aggregation[value] = aggregation.get(value, 0) + 1
            return aggregation
        except Exception as e:
            print(f"⚠️ Error agregando por {field}: {e}")
            return {}
    
    def _handle_count_question(self, query: str) -> str:
        """Maneja preguntas de conteo como '¿cuántas tareas hay en el sprint 2?'"""
        query_lower = query.lower()
        
        # Detectar sprint
        sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
        sprint_filter = None
        if sprint_match:
            sprint_num = sprint_match.group(1)
            sprint_filter = {"sprint": f"Sprint {sprint_num}"}
        
        # Detectar "sprint actual" (asumimos Sprint 3 como actual)
        if "actual" in query_lower or "corriente" in query_lower:
            sprint_filter = {"sprint": "Sprint 3"}
        
        # Detectar estado
        state_filter = None
        if "curso" in query_lower or "en progreso" in query_lower or "no completadas" in query_lower:
            # Tareas en curso: todas menos "done"
            # Nota: ChromaDB usa $ne para "not equal"
            state_filter = {"status": {"$ne": "done"}}
        elif "completadas" in query_lower or "finalizadas" in query_lower:
            state_filter = {"status": "done"}
        elif "pendiente" in query_lower or "por hacer" in query_lower:
            state_filter = {"status": "to_do"}
        elif "bloqueada" in query_lower:
            state_filter = {"is_blocked": True}
        elif " qa" in query_lower or "testing" in query_lower or "prueba" in query_lower:
            state_filter = {"status": "qa"}
        elif "review" in query_lower or "revisión" in query_lower:
            state_filter = {"status": "review"}
        
        # Combinar filtros
        combined_filter = None
        if sprint_filter and state_filter:
            combined_filter = {"$and": [sprint_filter, state_filter]}
        elif sprint_filter:
            combined_filter = sprint_filter
        elif state_filter:
            combined_filter = state_filter
        
        # Contar
        count = self.count_tasks(where=combined_filter)
        
        # Obtener tareas si el conteo es bajo (para dar más contexto)
        task_names = []
        if count > 0 and count <= 5:
            try:
                result = self.collection.get(where=cast(Any, combined_filter), limit=5)
                metadatas = result.get('metadatas') or []
                task_names = [m.get('name', 'Sin nombre') for m in metadatas]
            except Exception:
                pass
        
        # Generar respuesta
        if sprint_match:
            sprint_text = f"Sprint {sprint_match.group(1)}"
        elif "actual" in query_lower:
            sprint_text = "el sprint actual (Sprint 3)"
        else:
            sprint_text = "total"
        
        if state_filter:
            if "curso" in query_lower:
                state_text = "en curso (no completadas)"
            elif combined_filter and "$ne" in str(combined_filter):
                state_text = "en curso"
            elif state_filter.get("status") == "done":
                state_text = "completadas"
            elif state_filter.get("status") == "to_do":
                state_text = "pendientes"
            elif state_filter.get("status") == "qa":
                state_text = "en QA/testing"
            elif state_filter.get("status") == "review":
                state_text = "en revisión"
            elif state_filter.get("is_blocked"):
                state_text = "bloqueadas"
            else:
                state_text = ""
        else:
            state_text = ""
        
        # Construir respuesta base (con concordancia de número)
        plural = count != 1
        if sprint_text != "total" and state_text:
            # Ajustar género/número del estado según la cantidad
            if plural:
                base_response = f"En {sprint_text} hay {count} tareas {state_text}"
            else:
                # Singular: ajustar terminación del estado
                state_singular = state_text.rstrip('s') if state_text.endswith('as') or state_text.endswith('es') else state_text
                base_response = f"En {sprint_text} hay {count} tarea {state_singular}"
        elif sprint_text != "total":
            base_response = f"En {sprint_text} hay {count} tarea{'s' if plural else ''}"
        elif state_text:
            if plural:
                base_response = f"Hay {count} tareas {state_text}"
            else:
                state_singular = state_text.rstrip('s') if state_text.endswith('as') or state_text.endswith('es') else state_text
                base_response = f"Hay {count} tarea {state_singular}"
        else:
            base_response = f"Hay un total de {count} tarea{'s' if plural else ''} en el proyecto"
        
        # Añadir lista de tareas si hay pocas
        if task_names:
            if count == 1:
                return f"{base_response}: \"{task_names[0]}\"."
            else:
                tasks_list = ", ".join([f"\"{name}\"" for name in task_names[:-1]]) + f" y \"{task_names[-1]}\""
                return f"{base_response}: {tasks_list}."
        else:
            return f"{base_response}."

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
            query_lower = query.lower()
            
            # Detectar preguntas de conteo
            is_count_question = any(word in query_lower for word in [
                'cuántas', 'cuantas', 'cantidad', 'número', 'total', 'count'
            ])
            
            if is_count_question:
                return self._handle_count_question(query)
            
            docs, metas = self.search(query, top_k=top_k, use_filters=use_filters)
            if not docs:
                from chatbot.prompts import RAG_NO_RESULTS
                return RAG_NO_RESULTS

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

            # Usar prompts profesionales del archivo prompts.py
            from chatbot.prompts import SYSTEM_INSTRUCTIONS, RAG_CONTEXT_PROMPT
            
            system_prompt = SYSTEM_INSTRUCTIONS
            user_prompt = RAG_CONTEXT_PROMPT.format(
                system="",  # Ya está en el mensaje de sistema
                context=context,
                question=query
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
