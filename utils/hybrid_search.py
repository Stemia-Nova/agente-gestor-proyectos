#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HybridSearch: motor híbrido de recuperación semántica para tareas de ClickUp.
Usa ChromaDB persistente por sprint y combina:
 - Embeddings semánticos (SentenceTransformers)
 - Proximidad léxica (BM25)
 - Re-ranker cruzado (CrossEncoder)
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union, cast
import numpy as np
from tqdm import tqdm
import chromadb
from chromadb.api.models.Collection import Collection
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

# =============================================================
# CONFIGURACIÓN
# =============================================================
EMBED_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CHROMA_BASE = Path("data/rag/chroma_db")
COLLECTION_NAME = "clickup_tasks"

# =============================================================
# CLASE PRINCIPAL
# =============================================================
class HybridSearch:
    def __init__(self, chroma_base: Path = CHROMA_BASE):
        self.chroma_base = chroma_base
        self.embedder = SentenceTransformer(EMBED_MODEL)
        self.reranker = CrossEncoder(RERANK_MODEL)
        self._client = chromadb.PersistentClient(path=str(self.chroma_base))
        self.col: Optional[Collection] = None

        active_sprint = self._get_active_sprint()
        if active_sprint:
            self.col = self._load_collection(active_sprint)
            print(f"✅ Usando colección de sprint activo: {active_sprint}")
        else:
            print("⚠️ No hay sprint activo en el registro. Usa update_chroma_from_clickup.py para inicializarlo.")

    # ---------------------------------------------------------
    # Utilidades internas
    # ---------------------------------------------------------
    def _get_registry_path(self) -> Path:
        return self.chroma_base / "index_registry.json"

    def _get_active_sprint(self) -> Optional[str]:
        reg_path = self._get_registry_path()
        if not reg_path.exists():
            return None
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
            for sprint, info in registry.items():
                if info.get("status") == "active":
                    return sprint
        except Exception:
            return None
        return None

    def _load_collection(self, sprint_name: str) -> Collection:
        db_path = self.chroma_base / sprint_name.lower().replace(" ", "_")
        db_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(db_path))
        return client.get_or_create_collection(name=COLLECTION_NAME)

    # ---------------------------------------------------------
    # Funciones públicas
    # ---------------------------------------------------------
    def count_tasks(self, filters: Optional[Dict[str, Any]] = None) -> int:
        if not self.col:
            raise ValueError("❌ No hay sprint activo en el registro.")

        # Chroma acepta include como Sequence[Literal["metadatas"]]
        data = self.col.get(include=cast(Sequence[str], ["metadatas"]))
        metas = cast(List[Dict[str, Any]], data.get("metadatas") or [])

        if not metas:
            return 0

        if not filters:
            return len(metas)

        count = 0
        for m in metas:
            if all(str(m.get(k, "")).lower() == str(v).lower() for k, v in filters.items()):
                count += 1
        return count

    def query(self, text: str, k: int = 5) -> List[Dict[str, Any]]:
        if not self.col:
            raise ValueError("❌ No hay sprint activo en el registro.")

        raw = self.col.get(include=cast(Sequence[str], ["documents", "metadatas"]))
        docs = cast(List[str], raw.get("documents") or [])
        metas = cast(List[Dict[str, Any]], raw.get("metadatas") or [])

        if not docs:
            raise ValueError("❌ No hay documentos indexados en ChromaDB.")

        # =========================
        # 1️⃣ Embeddings semánticos
        # =========================
        query_vec = self.embedder.encode([text], convert_to_numpy=True)[0]
        doc_vecs = self.embedder.encode(docs, convert_to_numpy=True)

        scores_sem = np.dot(doc_vecs, query_vec) / (
            np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(query_vec)
        )
        top_sem_idx = np.argsort(scores_sem)[::-1][:k]
        sem_hits = [
            {"text": docs[i], "metadata": metas[i], "score": float(scores_sem[i])}
            for i in top_sem_idx
        ]

        # =========================
        # 2️⃣ BM25 (proximidad léxica)
        # =========================
        tokenized_corpus = [d.split() for d in docs]
        bm25 = BM25Okapi(tokenized_corpus)
        scores_bm25 = bm25.get_scores(text.split())
        top_bm_idx = np.argsort(scores_bm25)[::-1][:k]
        prox_hits = [
            {"text": docs[i], "metadata": metas[i], "score": float(scores_bm25[i])}
            for i in top_bm_idx
        ]

        # =========================
        # 3️⃣ Combinar y re-rankear
        # =========================
        combined = sem_hits + prox_hits
        unique = {json.dumps(h["metadata"], sort_keys=True): h for h in combined}
        merged_hits = list(unique.values())

        pairs = [(text, h["text"]) for h in merged_hits]
        rerank_scores = self.reranker.predict(pairs)
        reranked = sorted(
            [
                {"text": h["text"], "metadata": h["metadata"], "score": float(s)}
                for h, s in zip(merged_hits, rerank_scores)
            ],
            key=lambda x: x["score"],
            reverse=True,
        )

        if reranked:
            scores = np.array([r["score"] for r in reranked])
            min_s, max_s = scores.min(), scores.max()
            if max_s - min_s > 0:
                for r in reranked:
                    r["score"] = (r["score"] - min_s) / (max_s - min_s)

        return reranked[:k]

    # ---------------------------------------------------------
    # CLI (modo debug)
    # ---------------------------------------------------------
    @staticmethod
    def debug_query():
        print("\n🔍 *** MODO INTERACTIVO HYBRID SEARCH ***")
        print("Escribe tu consulta (o 'salir' para terminar)\n")

        hs = HybridSearch()
        while True:
            q = input("👉 Introduce tu consulta: ").strip()
            if not q or q.lower() in ("salir", "exit", "quit"):
                break

            try:
                hits = hs.query(q, k=5)
            except Exception as e:
                print(f"\n❌ Error durante la búsqueda: {e}\n")
                continue

            print("\n================================================================================")
            for i, h in enumerate(hits, start=1):
                meta = h.get("metadata", {})
                print(
                    f"{i}. ({h['score']:.3f}) {meta.get('task_id')} "
                    f"({meta.get('sprint')} • {meta.get('status')} • {meta.get('priority')}) — "
                    f"{h['text'][:100]}"
                )
            print("================================================================================")


# =============================================================
# PUNTO DE ENTRADA CLI
# =============================================================
if __name__ == "__main__":
    HybridSearch.debug_query()
