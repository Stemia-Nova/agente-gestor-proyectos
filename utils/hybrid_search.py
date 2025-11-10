#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HybridSearch Pro MAX Stable
---------------------------
Versión final sin warnings de Pylance ni errores de tipo.
Incluye:
 - SentenceTransformer para embeddings
 - DistilBERT para intención
 - CrossEncoder para rerank
 - Filtrado automático por sprint y estado
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple, Sequence, Optional, cast
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import chromadb

# Tipos base
DocList = List[str]
MetaList = List[Dict[str, Any]]
QueryResult = Dict[str, Any]


class HybridSearch:
    def __init__(
        self,
        collection_name: str = "clickup_tasks",
        db_path: Optional[str] = None,
    ) -> None:
        self.db_path = db_path or "data/rag/chroma_db"
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(collection_name)

        print(f"✅ Inicializando HybridSearchXL sobre colección '{collection_name}'...")

        # Embeddings (MiniLM)
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")

        # Dispositivo
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Intención (DistilBERT)
        self.int_tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        self.int_model = AutoModelForSequenceClassification.from_pretrained(
            "bhadresh-savani/distilbert-base-uncased-emotion"
        ).to(self.device)

        # Reranker (MiniLM CrossEncoder)
        self.rerank_tokenizer = AutoTokenizer.from_pretrained("cross-encoder/ms-marco-MiniLM-L-12-v2")
        self.rerank_model = AutoModelForSequenceClassification.from_pretrained(
            "cross-encoder/ms-marco-MiniLM-L-12-v2"
        ).to(self.device)

    # ================================================================
    # 🔍 BÚSQUEDA PRINCIPAL
    # ================================================================
    def search(self, query: str, top_k: int = 10) -> Tuple[DocList, MetaList]:
        """Ejecuta búsqueda híbrida (embeddings + rerank + intención)."""
        try:
            q_emb = self._embed_query(query)

            results: QueryResult = self.collection.query(
                query_embeddings=[q_emb],
                n_results=int(top_k),
                include=["documents", "metadatas"],  # type: ignore[arg-type]
            )

            docs = self._safe_get_strings(results, "documents")
            metas = self._safe_get_list(results, "metadatas")

            if not docs or not metas:
                return [], []

            docs, metas = self._rerank(query, docs, metas)
            docs, metas = self._filter_by_intent(query, docs, metas)

            # Reordena priorizando sprint actual y urgentes
            metas_sorted = sorted(
                metas,
                key=lambda m: (
                    0 if str(m.get("sprint_status", "")).lower() == "actual" else 1,
                    -1 if str(m.get("priority", "")).lower() in ("alta", "urgente", "high") else 0,
                    1 if str(m.get("status", "")).lower() in ("completado", "cerrado") else 0,
                ),
            )
            ordered_docs = [docs[metas.index(m)] for m in metas_sorted if m in metas]
            return ordered_docs, metas_sorted

        except Exception as e:
            print(f"⚠️ Error en HybridSearch.search(): {e}")
            return [], []

    # ================================================================
    # 🧠 INTERNAS
    # ================================================================
    def _embed_query(self, text: str) -> List[float]:
        emb = cast(Any, self.embedder.encode(text, convert_to_numpy=True))
        if emb is None:
            return []
        if isinstance(emb, np.ndarray):
            return emb.astype(np.float32).tolist()
        # Handle tensor-like objects with .numpy()
        if hasattr(emb, "numpy"):
            try:
                arr = emb.numpy()
                return np.asarray(arr, dtype=np.float32).tolist()
            except Exception:
                pass
        # General iterable fallback
        if hasattr(emb, "__iter__"):
            return [float(x) for x in emb]
        # Final safe fallback
        return []

    def _safe_get_list(self, results: QueryResult, key: str) -> List[Any]:
        """Devuelve results[key][0] si existe, sino []."""
        raw = results.get(key)
        if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], list):
            return cast(List[Any], raw[0])
        return []

    def _safe_get_strings(self, results: QueryResult, key: str) -> List[str]:
        """Devuelve results[key][0] como lista de strings (normalizando listas internas)."""
        raw = results.get(key)
        if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], list):
            inner = raw[0]
            normalized: List[str] = []
            for item in inner:
                if isinstance(item, str):
                    normalized.append(item)
                elif isinstance(item, (list, tuple)):
                    # unir elementos internos a un solo string
                    normalized.append(" ".join(map(str, item)))
                else:
                    normalized.append(str(item))
            return normalized
        if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], str):
            return cast(List[str], raw)
        return []

    def _detect_intent(self, text: str) -> str:
        """Detecta intención de consulta."""
        try:
            tokens = self.int_tokenizer(text, truncation=True, padding=True, return_tensors="pt").to(self.device)
            with torch.no_grad():
                logits = self.int_model(**tokens).logits
            probs = torch.softmax(logits, dim=1)
            idx = torch.argmax(probs, dim=1).item()
            mapping = {0: "bloqueadas", 1: "pendientes", 2: "progreso", 3: "completadas", 4: "general"}
            return mapping.get(int(idx), "general")
        except Exception:
            return "general"

    def _rerank(
        self, query: str, docs: Sequence[str], metas: Sequence[Dict[str, Any]]
    ) -> Tuple[DocList, MetaList]:
        """Reranking contextual con CrossEncoder."""
        try:
            # Normalize docs to a list of strings to satisfy the declared return types
            docs_list: List[str] = []
            for d in docs:
                if isinstance(d, str):
                    docs_list.append(d)
                elif isinstance(d, (list, tuple)):
                    docs_list.append(" ".join(map(str, d)))
                else:
                    docs_list.append(str(d))

            pairs = [(query, doc) for doc in docs_list]
            enc = self.rerank_tokenizer(
                [p[0] for p in pairs],
                [p[1] for p in pairs],
                padding=True,
                truncation=True,
                return_tensors="pt",
            ).to(self.device)
            with torch.no_grad():
                scores = self.rerank_model(**enc).logits.squeeze(-1)
            idxs = torch.argsort(scores, descending=True).tolist()
            reranked_docs = [docs_list[i] for i in idxs]
            reranked_metas = [metas[i] for i in idxs]
            return reranked_docs, reranked_metas
        except Exception as e:
            print(f"⚠️ Error en rerank: {e}")
            # Fall back to stringified docs if something goes wrong
            fallback_docs = [
                d if isinstance(d, str) else " ".join(map(str, d)) if isinstance(d, (list, tuple)) else str(d)
                for d in docs
            ]
            return fallback_docs, list(metas)

    def _filter_by_intent(
        self, query: str, docs: Sequence[str], metas: Sequence[Dict[str, Any]]
    ) -> Tuple[DocList, MetaList]:
        """Filtrado por intención y contexto (bloqueadas, pendientes, completadas, etc.)."""
        q = query.lower()
        intent = self._detect_intent(query).lower()

        filtered_docs: DocList = []
        filtered_metas: MetaList = []

        for doc, meta in zip(docs, metas):
            status = str(meta.get("status", "")).lower()
            blocked = bool(meta.get("is_blocked", False))
            sprint_status = str(meta.get("sprint_status", "")).lower()

            keep = True
            if intent == "bloqueadas" or "bloquead" in q:
                keep = blocked and sprint_status == "actual"
            elif intent in ["pendientes", "progreso"]:
                keep = any(k in status for k in ["pendiente", "progress", "in progress", "curso"])
            elif intent == "completadas":
                keep = any(k in status for k in ["completado", "finalizado", "cerrado"])
            elif "sprint actual" in q:
                keep = sprint_status == "actual"
            elif "sprint cerrado" in q:
                keep = sprint_status == "cerrado"

            if keep:
                filtered_docs.append(doc)
                filtered_metas.append(meta)

        if not filtered_docs:
            return list(docs), list(metas)
        return filtered_docs, filtered_metas
