#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Versión Pro-ready del módulo de búsqueda híbrida.

Permite dos modos:
 - 'basic' → BM25 + MiniLM + CrossEncoder
 - 'pro'   → SPLADE + E5-base + CrossEncoder

Modo de uso:
    from utils.hybrid_search import HybridSearch

    hs = HybridSearch(mode="pro")
    results = hs.semantic_search("tareas bloqueadas")
    hs.rerank("tareas bloqueadas", results)
"""

from typing import List, Dict, Any
from pathlib import Path
import numpy as np
import json
import re
import torch
from tqdm import tqdm

from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder
from sklearn.metrics.pairwise import cosine_similarity

# SPLADE (solo si modo pro)
from transformers import AutoTokenizer, AutoModel


class HybridSearch:
    def __init__(
        self,
        data_path: str = "data/processed/task_chunks.jsonl",
        mode: str = "basic",  # 'basic' o 'pro'
        embedding_model_basic: str = "sentence-transformers/all-MiniLM-L12-v2",
        embedding_model_pro: str = "intfloat/e5-base-v2",
        splade_model: str = "naver/efficient-splade-V-large-doc",
        rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        self.mode = mode
        self.data_path = Path(data_path)
        self.device = device
        self._token_re = re.compile(r"\w+", re.UNICODE)

        print(f"🚀 Inicializando HybridSearch en modo '{mode}' ({device})")

        # --- Cargar datos ---
        self.chunks = self._load_chunks()
        self.docs = [c["text"] for c in self.chunks]
        self.metadatas = [c["metadata"] for c in self.chunks]

        # --- Modelos ---
        if self.mode == "pro":
            print("🧠 Cargando modelo de embeddings (E5-base)...")
            self.embedding_model = SentenceTransformer(embedding_model_pro, device=device)
            print("🧩 Cargando modelo SPLADE para búsqueda lexical...")
            self.splade_tokenizer = AutoTokenizer.from_pretrained(splade_model)
            self.splade_model = AutoModel.from_pretrained(splade_model).to(device)
        else:
            print("🧠 Cargando modelo de embeddings (MiniLM)...")
            self.embedding_model = SentenceTransformer(embedding_model_basic, device=device)
            print("🔤 Construyendo índice BM25...")
            tokenized_docs = [self._tokenize(d) for d in self.docs]
            self.bm25 = BM25Okapi(tokenized_docs)

        print("⚖️ Cargando modelo de re-ranking...")
        self.rerank_model = CrossEncoder(rerank_model, device=device)

        # --- Generar embeddings semánticos ---
        print("🧬 Generando embeddings de documentos...")
        self.embeddings = self.embedding_model.encode(
            self.docs, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True
        )

    # =========================================================
    # UTILIDADES INTERNAS
    # =========================================================
    def _load_chunks(self) -> List[Dict[str, Any]]:
        if not self.data_path.exists():
            raise FileNotFoundError(f"No se encontró {self.data_path}")
        with open(self.data_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def _tokenize(self, text: str) -> List[str]:
        return [t.lower() for t in self._token_re.findall(text or "")]

    # =========================================================
    # BÚSQUEDA LEXICAL (BM25 o SPLADE)
    # =========================================================
    def keyword_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Búsqueda lexical según el modo."""
        print(f"\n🔤 Búsqueda lexical para: '{query}'")

        if self.mode == "pro":
            return self._splade_search(query, top_k)
        else:
            return self._bm25_search(query, top_k)

    def _bm25_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [{"text": self.docs[i], "score": float(scores[i]), "metadata": self.metadatas[i]} for i in top_idx]

    def _splade_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Búsqueda lexical con modelo SPLADE (sparse retriever)."""
        self.splade_model.eval()
        with torch.no_grad():
            inputs = self.splade_tokenizer(self.docs, padding=True, truncation=True, return_tensors="pt").to(self.device)
            doc_embs = self.splade_model(**inputs).last_hidden_state.mean(dim=1)
            q_inputs = self.splade_tokenizer(query, return_tensors="pt").to(self.device)
            q_emb = self.splade_model(**q_inputs).last_hidden_state.mean(dim=1)
            sim = torch.nn.functional.cosine_similarity(q_emb, doc_embs)
            top_idx = torch.topk(sim, k=min(top_k, len(self.docs))).indices.cpu().numpy()

        return [{"text": self.docs[i], "score": float(sim[i]), "metadata": self.metadatas[i]} for i in top_idx]

    # =========================================================
    # BÚSQUEDA SEMÁNTICA (EMBEDDINGS)
    # =========================================================
    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Búsqueda semántica basada en embeddings (MiniLM o E5-base)."""
        query_emb = self.embedding_model.encode([query], normalize_embeddings=True)
        sim = cosine_similarity(query_emb, self.embeddings)[0]
        top_idx = np.argsort(sim)[::-1][:top_k]
        results = [{"text": self.docs[i], "score": float(sim[i]), "metadata": self.metadatas[i]} for i in top_idx]
        print(f"\n🧠 Resultados semánticos para: '{query}'")
        for r in results:
            print(f" - ({r['score']:.3f}) {r['text'][:100]}...")
        return results

    # =========================================================
    # RERANKING (CROSS-ENCODER)
    # =========================================================
    def rerank(self, query: str, results: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """Reordena resultados con CrossEncoder."""
        if not results:
            print("⚠️ No hay resultados para re-rankear.")
            return []

        pairs = [[query, r["text"]] for r in results]
        scores = self.rerank_model.predict(pairs)
        for i, s in enumerate(scores):
            results[i]["rerank_score"] = float(s)
        ranked = sorted(results, key=lambda x: x["rerank_score"], reverse=True)[:top_k]

        print(f"\n⚖️ Resultados re-rankeados para: '{query}'")
        for r in ranked:
            print(f" - ({r['rerank_score']:.3f}) {r['text'][:100]}...")
        return ranked

    # =========================================================
    # ALIAS DE COMPATIBILIDAD
    # =========================================================
    def search_semantic(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Alias para semantic_search(), pensado para compatibilidad con tests o integraciones
        donde se espera un método 'search_semantic'.
        """
        return self.semantic_search(query, top_k)
