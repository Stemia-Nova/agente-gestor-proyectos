#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HybridSearch mejorado con:
- Recuperación semántica y proximidad (Chroma)
- Reranking (MiniLM o TinyBERT)
- Normalización (0..1)
- Deducción automática de "Sprint actual"
"""

from __future__ import annotations
import os, re, json
import numpy as np
from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

# ==============================
# Configuración
# ==============================
CHROMA_DIR = "data/rag/chroma_db"
SEM_COLLECTION = "clickup_tasks"
PROX_COLLECTION = "clickup_tasks_proximity"

EMB_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

TOPK_SEM = 10
TOPK_PROX = 10
TOPK_FINAL = 5

# ==============================
# Helpers
# ==============================
def _safe_meta_get(meta: Dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        if k in meta and meta[k] is not None:
            return str(meta[k])
    return default

def _get_task_id(meta: Dict[str, Any], fallback: str) -> str:
    return _safe_meta_get(meta, "task_id", "id", default=fallback)

def _dedup_by_task_id(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for h in hits:
        tid = _get_task_id(h.get("metadata", {}) or {}, fallback=h.get("id", ""))
        if tid and tid not in seen:
            seen.add(tid)
            out.append(h)
    return out

def _pretty_hit(i: int, h: Dict[str, Any]) -> str:
    meta = h.get("metadata", {}) or {}
    title = _safe_meta_get(meta, "title", "task_name", "name", "task_id", default="Tarea")
    sprint = _safe_meta_get(meta, "sprint", "sprint_name", default="-")
    status = _safe_meta_get(meta, "status", default="-")
    prio = _safe_meta_get(meta, "priority", default="-")
    text = (h.get("text") or h.get("document") or "").strip().replace("\n", " ")
    snippet = text[:140] + ("…" if len(text) > 140 else "")
    prob = h.get("score_prob")
    prob_str = f"{prob:.3f}" if isinstance(prob, float) else "--"
    return f" {i}. ({prob_str}) {title} ({sprint} • {status} • {prio}) — {snippet}"

# ==============================
# Reranker
# ==============================
class CrossEncoderReranker:
    def __init__(self, model_name: str = RERANK_MODEL):
        print(f"⚖️  Inicializando Reranker ({model_name})...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()

    @torch.no_grad()
    def score(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not candidates:
            return candidates
        for c in candidates:
            if "text" not in c:
                c["text"] = c.get("document", "") or ""
        pairs = [(query, c["text"]) for c in candidates]
        batch = self.tokenizer.batch_encode_plus(
            pairs, padding=True, truncation=True, return_tensors="pt"
        )
        logits = self.model(**{k: v for k, v in batch.items()}).logits
        if logits.size(-1) == 1:
            probs = torch.sigmoid(logits.squeeze(-1))
        elif logits.size(-1) == 2:
            probs = F.softmax(logits, dim=-1)[:, 1]
        else:
            probs = F.softmax(logits, dim=-1).max(dim=-1).values
        probs_np = probs.detach().cpu().numpy()
        # Normalización por consulta
        pmin, pmax = float(probs_np.min()), float(probs_np.max())
        probs_scaled = (probs_np - pmin) / (pmax - pmin) if pmax > pmin else np.zeros_like(probs_np)
        for c, p in zip(candidates, probs_scaled):
            c["score_prob"] = float(p)
        return sorted(candidates, key=lambda x: x["score_prob"], reverse=True)

# ==============================
# HybridSearch
# ==============================
class HybridSearch:
    def __init__(self, chroma_path=CHROMA_DIR, collection_sem=SEM_COLLECTION,
                 collection_prox=PROX_COLLECTION, emb_model_name=EMB_MODEL):
        print(f"🚀 Inicializando HybridSearch (colección '{collection_sem}' en {chroma_path})")
        print("🧠 Inicializando SemanticSearch...")
        self.emb_model = SentenceTransformer(emb_model_name)
        self.client = chromadb.PersistentClient(path=chroma_path, settings=Settings(allow_reset=False))
        self.col_sem = self.client.get_collection(collection_sem)
        try:
            self.col_prox = self.client.get_collection(collection_prox)
        except Exception:
            self.col_prox = self.col_sem
        self.reranker = CrossEncoderReranker()

    def _query_collection(self, col, query, n_results):
        try:
            res = col.query(query_texts=[query], n_results=n_results, include=["documents", "metadatas"])
        except TypeError:
            res = col.query(query_texts=[query], n_results=n_results,
                            include={"documents": True, "metadatas": True})
        docs = res.get("documents", [[]])[0] if res else []
        metas = res.get("metadatas", [[]])[0] if res else []
        return [{"document": d, "text": d, "metadata": m or {}} for d, m in zip(docs, metas)]

    def query(self, user_query: str):
        # Interpretar "Sprint actual" → sprint con número más alto
        if "actual" in user_query.lower():
            all_meta = self.col_sem.get(include=["metadatas"])
            sprints = []
            for meta in all_meta.get("metadatas", []):
                s = meta.get("sprint", "")
                match = re.search(r"(\d+)", s)
                if match:
                    sprints.append(int(match.group(1)))
            if sprints:
                current_sprint = f"Sprint {max(sprints)}"
                user_query = user_query.replace("actual", current_sprint)
                print(f"🔁 Interpretado 'Sprint actual' como '{current_sprint}'")

        sem_hits = self._query_collection(self.col_sem, user_query, TOPK_SEM)
        prox_hits = self._query_collection(self.col_prox, user_query, TOPK_PROX)
        merged = _dedup_by_task_id(sem_hits + prox_hits)
        reranked = self.reranker.score(user_query, merged)
        return reranked[:TOPK_FINAL]

# ==============================
# CLI interactiva
# ==============================
def main():
    print("\n🔍 *** MODO INTERACTIVO HYBRID SEARCH ***\n")
    hs = HybridSearch()
    while True:
        try:
            q = input("👉 Introduce tu consulta: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q or q.lower() in {"salir", "exit", "quit"}:
            break
        print("\n" + "="*80 + f"\n🔎 Ejecutando búsqueda híbrida para: '{q}'\n")
        hits = hs.query(q)
        if not hits:
            print("ℹ️ Sin resultados.\n")
            continue
        for i, h in enumerate(hits, 1):
            print(_pretty_hit(i, h))
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
