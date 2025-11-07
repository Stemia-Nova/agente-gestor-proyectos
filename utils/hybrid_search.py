#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HybridSearch sin recalcular embeddings.

Usa la base vectorial persistente creada en:
  data/rag/chroma_db  → colección: clickup_tasks

Componentes:
 - SemanticSearch  → consulta vectorial con MiniLM (SentenceTransformers) sobre ChromaDB
 - ProximitySearch → embeddings alternativos (MiniLM también, para compatibilidad)
 - Reranker        → Cross-Encoder TinyBERT para reordenar resultados

Muestra:
 - Top 10 semánticos
 - Top 10 proximidad
 - Top 5 rerankeados
"""

from typing import Any, Dict, List, Mapping, Sequence, cast
import numpy as np
import numpy.typing as npt
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import chromadb
from chromadb.api.types import QueryResult


# ==============================
# Helpers de tipado/seguridad
# ==============================
def _ensure_ndarray(x: Any) -> npt.NDArray[np.float32]:
    """Convierte a np.ndarray float32 (para Chroma)."""
    arr = np.asarray(x, dtype=np.float32)
    return cast(npt.NDArray[np.float32], arr)

def _get_first(results: QueryResult, key: str) -> List[Any]:
    """Extrae primer bloque de 'documents' o 'metadatas' de resultados de Chroma."""
    val = results.get(key)
    if val is None or not isinstance(val, list) or len(val) == 0:
        return []
    first = val[0]
    if first is None:
        return []
    if not isinstance(first, list):
        return [first]
    return first

def _metas_as_dicts(metas: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Convierte Sequence[Mapping] a List[Dict] de forma segura para tipado estático."""
    return [dict(m) for m in metas]


# ==============================
# 1) SEMANTIC SEARCH (MiniLM)
# ==============================
class SemanticSearch:
    """Consulta la colección principal clickup_tasks en ChromaDB."""
    def __init__(
        self,
        db_path: str = "data/rag/chroma_db",
        collection_name: str = "clickup_tasks",
        model_name: str = "sentence-transformers/all-MiniLM-L12-v2",
    ) -> None:
        print("🧠 Inicializando SemanticSearch...")
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(collection_name)

    def query(self, query_text: str, n_results: int = 10) -> QueryResult:
        query_emb = _ensure_ndarray(self.model.encode(query_text))
        return self.collection.query(query_embeddings=[query_emb.tolist()], n_results=n_results)


# ==============================
# 2) PROXIMITY SEARCH (MiniLM)
# ==============================
class ProximitySearch:
    """Consulta alternativa (usando el mismo modelo MiniLM para compatibilidad)."""
    def __init__(
        self,
        db_path: str = "data/rag/chroma_db",
        collection_name: str = "clickup_tasks",
        model_name: str = "sentence-transformers/all-MiniLM-L12-v2",
    ) -> None:
        print("📍 Inicializando ProximitySearch...")
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(collection_name)

    def query(self, query_text: str, n_results: int = 10) -> QueryResult:
        query_emb = _ensure_ndarray(self.model.encode(query_text))
        return self.collection.query(query_embeddings=[query_emb.tolist()], n_results=n_results)


# ==============================
# 3) RERANKER (Cross-Encoder)
# ==============================
class Reranker:
    """Modelo CrossEncoder TinyBERT para reordenar resultados combinados."""
    def __init__(self, model_name: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2") -> None:
        print("⚖️ Inicializando Reranker (TinyBERT)...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def rerank_documents(
        self,
        query: str,
        documents: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        if not documents:
            return []

        inputs = [f"{query} [SEP] {doc}" for doc in documents]
        encodings = self.tokenizer(inputs, truncation=True, padding=True, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**encodings)
        scores = outputs.logits.squeeze().tolist()
        if isinstance(scores, float):
            scores = [scores]

        metas_list: List[Dict[str, Any]] = _metas_as_dicts(metadatas)

        items: List[Dict[str, Any]] = [
            {"text": doc, "metadata": meta, "score": float(score)}
            for doc, meta, score in zip(documents, metas_list, scores)
        ]
        items_sorted = sorted(items, key=lambda x: x["score"], reverse=True)
        return items_sorted[:top_k]


# ==============================
# 4) HYBRID SEARCH (pipeline)
# ==============================
class HybridSearch:
    """Híbrido final sin embeddings locales, sobre ChromaDB persistente."""
    def __init__(self, db_path: str = "data/rag/chroma_db", collection_name: str = "clickup_tasks") -> None:
        print(f"🚀 Inicializando HybridSearch (colección '{collection_name}' en {db_path})")
        self.semantic = SemanticSearch(db_path=db_path, collection_name=collection_name)
        self.proximity = ProximitySearch(db_path=db_path, collection_name=collection_name)
        self.reranker = Reranker()

    def run_query(self, query: str) -> Dict[str, Any]:
        print(f"\n🔎 Ejecutando búsqueda híbrida para: '{query}'")

        # 1) Semántica (top 10)
        sem_res: QueryResult = self.semantic.query(query, n_results=10)
        sem_docs: List[str] = cast(List[str], _get_first(sem_res, "documents"))
        sem_metas: List[Mapping[str, Any]] = cast(List[Mapping[str, Any]], _get_first(sem_res, "metadatas"))

        print("\n🧠 Top 10 resultados SEMÁNTICOS:")
        for i, doc in enumerate(sem_docs):
            print(f"{i+1:2d}. {doc[:120]}...")

        # 2) Proximidad (top 10)
        prox_res: QueryResult = self.proximity.query(query, n_results=10)
        prox_docs: List[str] = cast(List[str], _get_first(prox_res, "documents"))
        prox_metas: List[Mapping[str, Any]] = cast(List[Mapping[str, Any]], _get_first(prox_res, "metadatas"))

        print("\n📍 Top 10 resultados PROXIMIDAD:")
        for i, doc in enumerate(prox_docs):
            print(f"{i+1:2d}. {doc[:120]}...")

        # 3) Combinar para rerank
        combined_docs: List[str] = sem_docs + prox_docs
        combined_metas: List[Mapping[str, Any]] = sem_metas + prox_metas

        # 4) Rerank (top 5)
        reranked: List[Dict[str, Any]] = self.reranker.rerank_documents(
            query,
            combined_docs,
            combined_metas,
            top_k=5
        )

        print("\n⚖️ Top 5 resultados RERANKEADOS:")
        for i, r in enumerate(reranked):
            print(f"{i+1:2d}. ({r['score']:.3f}) {r['text'][:120]}...")

        return {
            "semantic_top10": sem_res,
            "proximity_top10": prox_res,
            "reranked_top5": reranked,
        }


# =========================================================
# BLOQUE INTERACTIVO
# =========================================================
if __name__ == "__main__":
    print("\n🔍 *** MODO INTERACTIVO HYBRID SEARCH ***")
    print("Escribe tu consulta (o 'salir' para terminar)\n")

    hs = HybridSearch()

    while True:
        query_text = input("👉 Introduce tu consulta: ").strip()
        if not query_text or query_text.lower() in {"salir", "exit", "q"}:
            print("\n👋 Saliendo de HybridSearch.")
            break

        print("\n" + "=" * 80)
        hs.run_query(query_text)
        print("=" * 80 + "\n")
