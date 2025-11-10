#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HybridSearch Pro (versión optimizada)
-------------------------------------
Motor híbrido de búsqueda semántica + simbólica para tareas ClickUp.

Características:
- Compatibilidad con tests antiguos (db_path)
- Uso de SentenceTransformer (MiniLM) para embeddings
- Reranking contextual con TinyBERT
- Filtro de intención (bloqueadas, en curso, completadas, etc.)
- Tipado completo y seguro
"""

from __future__ import annotations
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import chromadb
from chromadb.api.types import Include
from typing import Any, Dict, List, Tuple, Sequence


class HybridSearch:
    """Búsqueda híbrida optimizada sobre tareas ClickUp indexadas en ChromaDB."""

    def __init__(self, collection_name: str = "clickup_tasks", db_path: str | None = None):
        """Inicializa la colección y los modelos de embeddings y reranker."""
        print(f"✅ Inicializando HybridSearch Pro sobre colección '{collection_name}'...")

        self.db_path = db_path or "data/rag/chroma_db"
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(collection_name)

        # Modelo de embeddings
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")

        # Modelo de reranking
        self.tokenizer = AutoTokenizer.from_pretrained("cross-encoder/ms-marco-MiniLM-L-12-v2")
        self.reranker = AutoModelForSequenceClassification.from_pretrained(
            "cross-encoder/ms-marco-MiniLM-L-12-v2"
        )

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.reranker.to(self.device)

    # ===============================================================
    # FUNCIONES PRINCIPALES
    # ===============================================================
    def search(self, query: str, top_k: int = 8) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Realiza una búsqueda semántica híbrida sobre la colección."""
        try:
            query_embedding = self._embed_query(query)

            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=top_k,
                include=[Include.documents, Include.metadatas],
            )

            docs: List[str] = results.get("documents", [[]])[0] or []
            metas: List[Dict[str, Any]] = results.get("metadatas", [[]])[0] or []

            if not docs or not metas:
                return [], []

            reranked_docs, reranked_metas = self._rerank(query, docs, metas)
            intent_filtered = self._filter_by_intent(query, reranked_docs, reranked_metas)
            return intent_filtered

        except Exception as e:
            print(f"⚠️ Error en búsqueda híbrida: {e}")
            return [], []

    # ===============================================================
    # INTERNAS
    # ===============================================================
    def _embed_query(self, text: str) -> List[List[float]]:
        """Crea embeddings para la consulta."""
        emb = self.embedder.encode([text], convert_to_numpy=True)
        return emb.tolist()

    def _rerank(
        self, query: str, docs: Sequence[str], metas: Sequence[Dict[str, Any]]
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Reranking basado en CrossEncoder TinyBERT."""
        pairs = [(query, doc) for doc in docs]
        enc = self.tokenizer(
            [p[0] for p in pairs],
            [p[1] for p in pairs],
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            scores = self.reranker(**enc).logits.squeeze(-1)
        scores = torch.softmax(scores, dim=0)

        idxs = torch.argsort(scores, descending=True).tolist()
        reranked_docs = [docs[i] for i in idxs]
        reranked_metas = [metas[i] for i in idxs]
        return reranked_docs, reranked_metas

    def _filter_by_intent(
        self, query: str, docs: Sequence[str], metas: Sequence[Dict[str, Any]]
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Filtra resultados según la intención de la pregunta."""
        q = query.lower()
        filtered_docs, filtered_metas = [], []

        for doc, meta in zip(docs, metas):
            status = (meta.get("status") or "").lower()
            blocked = meta.get("is_blocked", False)
            sprint_status = (meta.get("sprint_status") or "").lower()

            if "bloquead" in q and not blocked:
                continue
            if any(k in q for k in ["pendient", "curso", "progreso"]) and status not in [
                "pendiente",
                "en curso",
                "in progress",
            ]:
                continue
            if any(k in q for k in ["completad", "cerrad", "finalizad"]) and status not in [
                "completado",
                "cerrado",
                "finalizado",
            ]:
                continue
            if "sprint actual" in q and sprint_status != "actual":
                continue
            if "sprint cerrado" in q and sprint_status != "cerrado":
                continue

            filtered_docs.append(doc)
            filtered_metas.append(meta)

        if not filtered_metas:
            # fallback a todos los resultados
            return list(docs), list(metas)

        return list(filtered_docs), list(filtered_metas)
