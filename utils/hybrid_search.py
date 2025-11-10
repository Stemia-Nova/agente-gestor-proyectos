#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HybridSearch — versión optimizada y tipada para base única (clickup_tasks)
---------------------------------------------------------------------------
Motor de búsqueda híbrido sobre la base Chroma del Agente Gestor de Proyectos.

✔ Compatible con Chroma ≥0.5.x
✔ Integración directa con la colección 'clickup_tasks'
✔ Combina búsqueda semántica (MiniLM) + reranker CrossEncoder
✔ Manejo seguro de tipos y datos opcionales
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import chromadb

# =============================================================
# 📂 Configuración general
# =============================================================
CHROMA_PATH = Path("data/rag/chroma_db")
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class HybridSearch:
    """Búsqueda híbrida (semántica + reranker) sobre colección única de Chroma."""

    def __init__(self, db_path: str | Path = CHROMA_PATH) -> None:
        self.db_path = str(db_path)
        self.chroma = chromadb.PersistentClient(path=self.db_path)
        self.embedder = SentenceTransformer(DEFAULT_MODEL, device=DEVICE)
        self.collection_name = "clickup_tasks"

        try:
            self.collection = self.chroma.get_collection(self.collection_name)
        except Exception:
            raise RuntimeError(f"❌ No se encontró la colección '{self.collection_name}' en {db_path}")

        print(f"✅ HybridSearch inicializado sobre colección '{self.collection_name}'.")

        # Reranker CrossEncoder (reordenamiento semántico fino)
        self.reranker_tokenizer = AutoTokenizer.from_pretrained("cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.reranker_model = AutoModelForSequenceClassification.from_pretrained(
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ).to(DEVICE)

    # =============================================================
    # 📥 Recolectar documentos
    # =============================================================
    def _collect_documents(self) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Obtiene todos los documentos y metadatos de la colección Chroma."""
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []

        try:
            data = self.collection.get(include=cast(Any, ["documents", "metadatas"])) or {}
            raw_docs = data.get("documents") or []
            raw_metas = data.get("metadatas") or []

            # Garantizar tipos válidos
            docs = list(raw_docs) if isinstance(raw_docs, list) else []
            metas = [dict(m) for m in raw_metas if isinstance(m, dict)]
        except Exception as e:
            print(f"⚠️ Error al recolectar documentos: {e}")

        return docs, metas

    # =============================================================
    # 🔁 Reranking
    # =============================================================
    def _rerank(self, query: str, docs: List[str]) -> List[Tuple[str, float]]:
        """Reordena los documentos según similitud contextual con CrossEncoder."""
        if not docs:
            return []

        pairs = [(query, d) for d in docs]
        inputs = self.reranker_tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=256,
        ).to(DEVICE)

        with torch.no_grad():
            scores = self.reranker_model(**inputs).logits.squeeze().cpu().numpy()

        if isinstance(scores, float):
            scores = np.array([scores])
        sorted_idx = np.argsort(scores)[::-1]
        return [(docs[i], float(scores[i])) for i in sorted_idx]

    # =============================================================
    # 🔍 Consulta semántica principal
    # =============================================================
    def query(self, text: str, k: int = 5) -> List[Dict[str, Any]]:
        """Ejecuta búsqueda semántica + reranking sobre la colección."""
        query_emb = self.embedder.encode([text], convert_to_numpy=True)
        results: List[Dict[str, Any]] = []

        try:
            q = self.collection.query(
                query_embeddings=query_emb,
                n_results=k,
                include=cast(Any, ["documents", "metadatas"]),
            ) or {}

            raw_docs = (q.get("documents") or [[]])[0] or []
            raw_metas = (q.get("metadatas") or [[]])[0] or []

            # Validar estructura
            docs = list(raw_docs) if isinstance(raw_docs, list) else []
            metas = [dict(m) for m in raw_metas if isinstance(m, dict)]

            results.extend({"text": d, "metadata": m} for d, m in zip(docs, metas))
        except Exception as e:
            print(f"⚠️ Error en query: {e}")

        if not results:
            return []

        reranked = self._rerank(text, [r["text"] for r in results])
        top_docs = {r[0] for r in reranked[:k]}
        return [r for r in results if r["text"] in top_docs]

    # =============================================================
    # 📊 Agregaciones globales
    # =============================================================
    def aggregate_counts(self) -> Dict[str, Any]:
        """Devuelve un resumen de estados de tareas."""
        docs, metas = self._collect_documents()
        agg = {"total": len(docs), "done": 0, "in_progress": 0, "todo": 0, "blocked": 0}

        for m in metas:
            st = str(m.get("status", "")).lower()
            if "finaliz" in st or "done" in st or "complet" in st:
                agg["done"] += 1
            elif "curso" in st or "progress" in st:
                agg["in_progress"] += 1
            elif "pend" in st or "todo" in st:
                agg["todo"] += 1
            if m.get("is_blocked"):
                agg["blocked"] += 1

        return agg

    # =============================================================
    # 🚫 Listar tareas bloqueadas
    # =============================================================
    def list_blocked(self) -> List[Dict[str, Any]]:
        """Devuelve todas las tareas marcadas como bloqueadas."""
        docs, metas = self._collect_documents()
        blocked = []
        for d, m in zip(docs, metas):
            if m.get("is_blocked"):
                blocked.append({"text": d, "metadata": m})
        return blocked


# =============================================================
# 🧪 Ejemplo de uso directo
# =============================================================
if __name__ == "__main__":
    hs = HybridSearch()
    print("\n🔎 Consulta de ejemplo:")
    query = "tareas pendientes del sprint 3"
    results = hs.query(query)
    for r in results:
        print("-", r["metadata"].get("name"), "→", r["metadata"].get("status"))
