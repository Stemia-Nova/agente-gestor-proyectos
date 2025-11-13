#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HybridSearch — RAG “listo para producción”
------------------------------------------
• Recuperación híbrida (embeddings → ChromaDB → rerank CrossEncoder)
• Agregaciones deterministas (conteos por sprint, proyecto, asignatario, bloqueadas)
• Normalización y tolerancia a typos
• Generación de respuesta con GPT-4o-mini (opcional)

Requisitos (pip):
    sentence-transformers
    chromadb
    torch
    transformers
    openai>=1.0.0

Variables de entorno:
    OPENAI_API_KEY
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional, Sequence, cast
import os
import re
import difflib
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import chromadb
from chromadb.api.types import GetResult

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers.tokenization_utils_base import PreTrainedTokenizerBase
from openai import OpenAI


# =========================
# Config
# =========================
@dataclass
class HybridConfig:
    collection_name: str = "clickup_tasks"
    db_path: str = "data/rag/chroma_db"
    embedder_model: str = "sentence-transformers/all-MiniLM-L12-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    chroma_get_limit: int = 100_000
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.4


class HybridSearch:
    """Motor de búsqueda híbrida + agregaciones deterministas + generación LLM."""

    def __init__(self, cfg: Optional[HybridConfig] = None) -> None:
        self.cfg = cfg or HybridConfig()

        # Chroma persistente
        self.client = chromadb.PersistentClient(path=self.cfg.db_path)
        self.collection = self.client.get_or_create_collection(self.cfg.collection_name)
        print(f"✅ HybridSearch conectado a '{self.cfg.collection_name}' en '{self.cfg.db_path}'")

        # Lazy loading de modelos
        self._embedder: Optional[SentenceTransformer] = None
        self._rerank_tok: Optional[PreTrainedTokenizerBase] = None
        self._rerank_model: Optional[nn.Module] = None  # nn.Module expone .eval()

        # OpenAI (opcional)
        self._openai_enabled = bool(os.getenv("OPENAI_API_KEY"))
        self.llm = OpenAI() if self._openai_enabled else None

        # Device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # -------------------------
    # Helpers
    # -------------------------
    @staticmethod
    def _norm(s: Optional[str]) -> str:
        # Seguro frente a None
        if s is None:
            return ""
        return s.strip().lower()

    @staticmethod
    def _split_assignees(s: Optional[str]) -> List[str]:
        if not s:
            return []
        return [p.strip() for p in s.split(",") if p.strip()]

    @staticmethod
    def _closest(candidate: str, options: List[str], cutoff: float = 0.8) -> str:
        if not candidate or not options:
            return candidate
        matches = difflib.get_close_matches(candidate, options, n=1, cutoff=cutoff)
        return matches[0] if matches else candidate

    # -------------------------
    # Modelos
    # -------------------------
    def _ensure_embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            print("🧠 Cargando modelo de embeddings…")
            self._embedder = SentenceTransformer(self.cfg.embedder_model)
        return self._embedder

    def _ensure_reranker(self) -> Tuple[PreTrainedTokenizerBase, nn.Module]:
        if self._rerank_tok is None or self._rerank_model is None:
            print("🧩 Cargando modelo de reranking…")
            # Tipos concretos, pero anotados con base classes para Pylance
            tok: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(self.cfg.reranker_model)  # type: ignore[assignment]
            model: nn.Module = AutoModelForSequenceClassification.from_pretrained(
                self.cfg.reranker_model
            ).to(self.device)  # type: ignore[assignment]
            model.eval()  # nn.Module expone eval() para Pylance
            self._rerank_tok = tok
            self._rerank_model = model
        return self._rerank_tok, self._rerank_model  # type: ignore[return-value]

    # -------------------------
    # Búsqueda
    # -------------------------
    def _embed_query(self, text: str) -> List[float]:
        emb = self._ensure_embedder().encode(text, convert_to_numpy=True)
        return emb.astype(np.float32).tolist()

    def search(self, query: str, top_k: int = 8) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Embeddings → Chroma → rerank CrossEncoder."""
        q_emb = self._embed_query(query)
        res = self.collection.query(
            query_embeddings=[q_emb],
            n_results=top_k,
            include=cast(Any, ["documents", "metadatas"]),  # stubs estrictos en Chroma
        )

        raw_docs = res.get("documents")
        raw_metas = res.get("metadatas")

        # Defaults seguros para evitar “Object of type None is not subscriptable”
        docs_list: List[List[str]] = cast(List[List[str]], raw_docs or [[]])
        metas_list: List[List[Dict[str, Any]]] = cast(List[List[Dict[str, Any]]], raw_metas or [[]])

        docs: List[str] = docs_list[0] if docs_list else []
        metas: List[Dict[str, Any]] = metas_list[0] if metas_list else []

        if not docs or not metas:
            return [], []

        return self._rerank(query, docs, metas)

    def _rerank(
        self,
        query: str,
        docs: Sequence[str],
        metas: Sequence[Dict[str, Any]],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        tok, model = self._ensure_reranker()

        pairs = [(query, d) for d in docs]
        enc = tok(
            [p[0] for p in pairs],
            [p[1] for p in pairs],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = model(**enc)  # nn.Module es “callable”
            # logits: [batch, 1] → squeeze para [batch]
            scores = cast(torch.Tensor, outputs.logits).squeeze(-1)

        idxs = torch.argsort(scores, descending=True).tolist()
        # Ensure types match the declared return type: List[str], List[Dict[str, Any]]
        reranked_docs = [str(docs[i]) for i in idxs]
        reranked_metas = [cast(Dict[str, Any], metas[i]) for i in idxs]
        return reranked_docs, reranked_metas

    # -------------------------
    # Metadatos globales
    # -------------------------
    def _get_all_metas(self) -> List[Dict[str, Any]]:
        res: GetResult = self.collection.get(
            include=cast(Any, ["metadatas"]),
            limit=self.cfg.chroma_get_limit,
        )
        metas = cast(List[Dict[str, Any]], res.get("metadatas") or [])
        return metas

    # -------------------------
    # Agregaciones deterministas
    # -------------------------
    def count_total(self) -> int:
        return len(self._get_all_metas())

    def list_projects(self) -> List[str]:
        projects = sorted({(m.get("project") or "unknown") for m in self._get_all_metas()})
        return projects

    def list_sprints(self) -> List[str]:
        sprints = sorted({(m.get("sprint") or "Sin sprint") for m in self._get_all_metas()})
        return sprints

    def count_by_project(self, project_query: str) -> int:
        metas = self._get_all_metas()
        projects_norm = [self._norm(p) for p in self.list_projects()]
        canonical = self._closest(self._norm(project_query), projects_norm)
        return sum(1 for m in metas if self._norm(m.get("project")) == canonical)

    def count_by_sprint(self, sprint_query: str) -> int:
        metas = self._get_all_metas()
        sprints_norm = [self._norm(s) for s in self.list_sprints()]
        canonical = self._closest(self._norm(sprint_query), sprints_norm)
        return sum(1 for m in metas if self._norm(m.get("sprint")) == canonical)

    def count_assigned_to(self, person_query: str) -> int:
        metas = self._get_all_metas()
        target = self._norm(person_query)

        def has_person(val: Optional[str]) -> bool:
            names = [self._norm(x) for x in self._split_assignees(val)]
            return any(target and (target in n) for n in names)

        return sum(1 for m in metas if has_person(m.get("assignees")))

    def count_blocked(self) -> int:
        return sum(1 for m in self._get_all_metas() if bool(m.get("is_blocked")))

    def stats_by_project(self, project_query: Optional[str] = None) -> Dict[str, int]:
        metas = self._get_all_metas()
        if project_query:
            projects_norm = [self._norm(p) for p in self.list_projects()]
            canonical = self._closest(self._norm(project_query), projects_norm)
            metas = [m for m in metas if self._norm(m.get("project")) == canonical]

        agg = {"done": 0, "in_progress": 0, "to_do": 0, "blocked": 0, "cancelled": 0, "unknown": 0, "custom": 0}
        for m in metas:
            s = self._norm(m.get("status"))
            agg[s if s in agg else "custom"] += 1
        agg["total"] = len(metas)
        return agg

    # -------------------------
    # Generación (opcional)
    # -------------------------
    def _gen(self, system_msg: str, user_msg: str) -> str:
        if not self._openai_enabled or not self.llm:
            return "ℹ️ Generación deshabilitada (no se encontró OPENAI_API_KEY)."
        resp = self.llm.chat.completions.create(
            model=self.cfg.openai_model,
            messages=[{"role": "system", "content": system_msg},
                      {"role": "user", "content": user_msg}],
            temperature=self.cfg.temperature,
        )
        try:
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            return "No se obtuvo contenido del modelo."

    # -------------------------
    # Router de intents
    # -------------------------
    def answer(self, query: str, top_k: int = 8) -> str:
        ql = self._norm(query)

        # Preguntas de conteo
        if any(w in ql for w in ["cuántas", "cuantas", "número", "numero", "total", "cuenta", "cuente", "cuántos", "cuantos"]):
            try:
                if "bloquead" in ql:
                    return f"Hay {self.count_blocked()} tareas bloqueadas."

                m = re.search(r"sprint\s+(\d+)", ql)
                if m:
                    sprint_name = f"sprint {m.group(1)}".lower()
                    return f"En Sprint {m.group(1)} hay {self.count_by_sprint(sprint_name)} tareas."

                if "jorge" in ql:
                    return f"Jorge tiene {self.count_assigned_to('Jorge Aguadero')} tareas asignadas."
                if "laura" in ql:
                    return f"Laura tiene {self.count_assigned_to('Laura Pérez Lopez')} tareas asignadas."

                if "proyecto" in ql or any(self._norm(p) in ql for p in self.list_projects()):
                    candidates = self.list_projects()
                    chosen: Optional[str] = None
                    for p in candidates:
                        if self._norm(p) in ql:
                            chosen = p
                            break
                    if not chosen:
                        words = [w for w in re.split(r"\W+", ql) if w]
                        rev = {self._norm(x): x for x in candidates}
                        if words:
                            chosen_norm = self._closest(self._norm(words[-1]), list(rev.keys()))
                            chosen = rev.get(chosen_norm, "Folder")
                        else:
                            chosen = "Folder"
                    count = self.count_by_project(chosen)
                    return f"En el proyecto {chosen} hay {count} tareas."

                return f"En total hay {self.count_total()} tareas."
            except Exception as e:
                return f"❌ No pude calcular el conteo: {e}"

        # RAG clásico
        docs, metas = self.search(query, top_k=top_k)
        if not metas:
            return "No encontré información relevante para esa consulta."

        context = "\n".join([
            f"- {m.get('name','(sin nombre)')} "
            f"(estado: {m.get('status','?')}, prioridad: {m.get('priority','?')}, "
            f"sprint: {m.get('sprint','?')}, asignado: {m.get('assignees','Sin asignar')})"
            for m in metas[:6]
        ])

        system_prompt = (
            "Eres un asistente experto en gestión ágil (Scrum/Kanban). "
            "Usa el contexto de tareas de ClickUp y responde breve, claro y accionable."
        )
        user_prompt = f"Pregunta: {query}\n\nContexto:\n{context}\n\nResponde como Scrum Master."

        return self._gen(system_prompt, user_prompt)

    # -------------------------
    # Debug
    # -------------------------
    def debug_sample(self, k: int = 5) -> List[Dict[str, Any]]:
        return self._get_all_metas()[:k]


if __name__ == "__main__":
    cfg = HybridConfig(
        collection_name=os.getenv("CHROMA_COLLECTION", "clickup_tasks"),
        db_path=os.getenv("CHROMA_DB_PATH", "data/rag/chroma_db"),
    )
    hs = HybridSearch(cfg)
    print(hs.answer("¿Cuántas tareas hay en total?"))
    print(hs.answer("¿Cuántas tareas hay en el proyecto Flder?"))
    print(hs.answer("¿Cuántas tareas hay en el Sprint 3?"))
    print(hs.answer("¿Cuántas tareas tiene Jorge?"))
    print(hs.answer("¿Qué tareas urgentes tengo este sprint?"))
