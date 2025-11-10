#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HybridSearchXL — Motor híbrido con intención (Hugging Face) y tipado Pylance-safe.

• Intención con zero-shot (opcional) + fallback por diccionarios de sinónimos
• Embeddings (MiniLM) + Rerank (TinyBERT)
• Filtros por metadatos: status, sprint_status, priority, is_blocked, assignees, is_subtask
• IncludeEnum correcto, nulos seguros y casts para Pylance
• Agregaciones (conteos por estado/sprint/asignado/prioridad)
• Modo debug: export HYBRID_DEBUG=1
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

import chromadb
from chromadb.api.types import IncludeEnum, QueryResult

import torch
from sentence_transformers import SentenceTransformer
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizerBase,
    pipeline,
)


# ===============================
# Config y utilidades
# ===============================
def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


class Config:
    MODEL_EMBEDDING = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L12-v2")
    MODEL_RERANK = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-TinyBERT-L-6")
    MODEL_INTENT = os.getenv("INTENT_MODEL", "facebook/bart-large-mnli")  # zero-shot
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    DEBUG = _bool_env("HYBRID_DEBUG", False)


# ===============================
# Clasificador de intención
# ===============================
class IntentClassifier:
    """
    Intención con zero-shot. Si no carga, usa fallback por tablas de sinónimos (sin elif).
    Salida (slots posibles):
      - sprint_status: "actual" | "cerrado"
      - status: "pendiente" | "en curso" | "completado"
      - priority: "urgente" | "alta" | "normal" | "baja" | "sin prioridad"
      - is_blocked: True/False
      - assignees: "sin asignar"
      - is_subtask: True/False
      - all_project: True (no restringe sprint)
      - all_closed: True (status=completado sin restringir sprint)
    """

    # Tablas de sinónimos → slot/valor (evitamos elif encadenados)
    SYNONYMS: Dict[str, Dict[str, Any]] = {
        "all_project": {
            "todo el proyecto": True, "todo el backlog": True, "todo el sistema": True, "todo el repositorio": True
        },
        "all_closed": {
            "todas las cerradas": True, "todas las completadas": True, "todas finalizadas": True
        },
        "sprint_status.actual": {
            "sprint actual": "actual", "en este sprint": "actual", "ahora": "actual"
        },
        "sprint_status.cerrado": {
            "anteriores": "cerrado", "previos": "cerrado", "histórico": "cerrado", "cerrados": "cerrado", "anteriores sprints": "cerrado"
        },
        "status.pendiente": {
            "pendiente": "pendiente", "por hacer": "pendiente", "to do": "pendiente"
        },
        "status.en curso": {
            "en curso": "en curso", "progreso": "en curso", "in progress": "en curso"
        },
        "status.completado": {
            "completad": "completado", "finalizad": "completado", "cerrad": "completado"
        },
        "priority.urgente": {"urgente": "urgente"},
        "priority.alta": {"prioridad alta": "alta", "alta prioridad": "alta"},
        "priority.normal": {"prioridad normal": "normal"},
        "priority.baja": {"prioridad baja": "baja"},
        "priority.sin prioridad": {"sin prioridad": "sin prioridad"},
        "is_blocked.true": {"bloquead": True, "bloqueadas": True},
        "is_blocked.false": {"no bloqueadas": False},
        "assignees": {"sin asignar": "sin asignar"},
        "is_subtask.true": {"subtarea": True, "subtareas": True},
        "is_subtask.false": {"solo principales": False, "sin subtareas": False},
    }

    ZERO_SHOT_LABELS: List[str] = [
        # Ámbito
        "todo_proyecto", "sprint_actual", "sprint_cerrado",
        # Estado
        "pendientes", "en_curso", "completadas",
        # Otros
        "urgentes", "sin_asignar", "bloqueadas", "subtareas",
    ]

    def __init__(self) -> None:
        self.pipe = None
        try:
            self.pipe = pipeline(
                "zero-shot-classification",
                model=Config.MODEL_INTENT,
                device=0 if Config.DEVICE == "cuda" else -1,
            )
            if Config.DEBUG:
                print(f"🧠 Modelo de intención cargado: {Config.MODEL_INTENT}")
        except Exception as e:
            if Config.DEBUG:
                print(f"⚠️ Zero-shot no disponible, fallback a sinónimos. Motivo: {e}")

    def _fallback_keywords(self, text: str) -> Dict[str, Any]:
        q = text.lower()
        intent: Dict[str, Any] = {
            "scope": "auto",
            "status": None,
            "priority": None,
            "is_blocked": None,
            "assignees": None,
            "is_subtask": None,
            "sprint_status": None,
            "all_closed": False,
            "all_project": False,
        }

        # Recorremos las tablas de sinónimos (sin elif)
        for key, syns in self.SYNONYMS.items():
            for token, value in syns.items():
                if token in q:
                    if key.startswith("sprint_status."):
                        intent["sprint_status"] = value
                    elif key.startswith("status."):
                        intent["status"] = value
                    elif key.startswith("priority."):
                        intent["priority"] = value
                    elif key.startswith("is_blocked."):
                        intent["is_blocked"] = value
                    elif key == "assignees":
                        intent["assignees"] = value
                    elif key.startswith("is_subtask."):
                        intent["is_subtask"] = value
                    elif key == "all_project":
                        intent["all_project"] = True
                    elif key == "all_closed":
                        intent["all_closed"] = True
                        intent["status"] = "completado"

        return intent

    def predict(self, text: str) -> Dict[str, Any]:
        # Intento con zero-shot si disponible
        if self.pipe is not None:
            try:
                result = cast(Dict[str, Any], self.pipe(text, self.ZERO_SHOT_LABELS))
                labels = cast(List[str], result.get("labels", []))
                scores = cast(List[float], result.get("scores", []))
                if labels and scores and Config.DEBUG:
                    print(f"🧩 Zero-shot top: {labels[0]} ({scores[0]:.2f})")

                intent: Dict[str, Any] = {
                    "scope": "auto",
                    "status": None,
                    "priority": None,
                    "is_blocked": None,
                    "assignees": None,
                    "is_subtask": None,
                    "sprint_status": None,
                    "all_closed": False,
                    "all_project": False,
                }

                # Mapeo etiqueta → slot (sin elif, usando dict)
                label2slot: Dict[str, Dict[str, Any]] = {
                    "todo_proyecto": {"all_project": True},
                    "sprint_actual": {"sprint_status": "actual"},
                    "sprint_cerrado": {"sprint_status": "cerrado"},
                    "pendientes": {"status": "pendiente"},
                    "en_curso": {"status": "en curso"},
                    "completadas": {"status": "completado"},
                    "urgentes": {"priority": "urgente"},
                    "sin_asignar": {"assignees": "sin asignar"},
                    "bloqueadas": {"is_blocked": True},
                    "subtareas": {"is_subtask": True},
                }

                # Aplicamos todas las etiquetas por encima de un umbral (multi-label)
                for lab, sc in zip(labels, scores):
                    if sc >= 0.35 and lab in label2slot:
                        for k, v in label2slot[lab].items():
                            intent[k] = v

                # Regla especial “todas las cerradas” (lo detecta mejor por keywords)
                kw_intent = self._fallback_keywords(text)
                if kw_intent.get("all_closed"):
                    intent["all_closed"] = True
                    intent["status"] = "completado"

                return intent
            except Exception as e:
                if Config.DEBUG:
                    print(f"⚠️ Zero-shot falló en runtime, fallback a sinónimos: {e}")

        # Fallback por sinónimos
        return self._fallback_keywords(text)


# ===============================
# HybridSearch (core)
# ===============================
class HybridSearch:
    def __init__(self, collection_name: str = "clickup_tasks") -> None:
        print(f"✅ Inicializando HybridSearchXL sobre colección '{collection_name}'...")

        # Chroma persistente
        self.client = chromadb.PersistentClient(path="data/rag/chroma_db")
        self.collection = self.client.get_or_create_collection(collection_name)

        # Dispositivo
        self.device = Config.DEVICE
        if Config.DEBUG:
            print(f"🖥️ Torch device: {self.device}")

        # Embeddings
        self.encoder = SentenceTransformer(Config.MODEL_EMBEDDING, device=self.device)

        # Reranker (con tipos explícitos para Pylance)
        self.reranker_tok: Optional[PreTrainedTokenizerBase] = None
        self.reranker_model: Optional[PreTrainedModel] = None
        try:
            self.reranker_tok = AutoTokenizer.from_pretrained(Config.MODEL_RERANK)
            self.reranker_model = AutoModelForSequenceClassification.from_pretrained(
                Config.MODEL_RERANK
            ).to(self.device)
            if Config.DEBUG:
                print(f"🧪 Reranker cargado: {Config.MODEL_RERANK}")
        except Exception as e:
            if Config.DEBUG:
                print(f"⚠️ Reranker no disponible, seguimos sin él: {e}")
            self.reranker_tok = None
            self.reranker_model = None

        # Clasificador de intención
        self.intent_model = IntentClassifier()

    # ---------------------------
    # where a partir de intención
    # ---------------------------
    def _build_where(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        where: Dict[str, Any] = {}

        # “todo el proyecto”: no se restringe por sprint
        # “todas las cerradas”: tampoco restringe sprint (solo status)
        sprint_status = intent.get("sprint_status")
        if sprint_status in {"actual", "cerrado"} and not intent.get("all_project") and not intent.get("all_closed"):
            where["sprint_status"] = sprint_status

        for key in ("status", "priority", "assignees", "is_blocked", "is_subtask"):
            v = intent.get(key, None)
            if v is not None and v != "":
                where[key] = v

        return where

    # ---------------------------
    # Rerank (type-safe)
    # ---------------------------
    def _rerank(
        self,
        query: str,
        docs: Sequence[str],
        metas: Sequence[Dict[str, Any]],
        top_k: int,
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        if not docs:
            return [], []

        if self.reranker_tok is None or self.reranker_model is None:
            return list(docs)[:top_k], list(metas)[:top_k]

        tokenizer = cast(Any, self.reranker_tok)
        model = cast(Any, self.reranker_model)

        pairs = [(query, d) for d in docs]
        inputs = tokenizer(
            pairs, padding=True, truncation=True, return_tensors="pt", max_length=256
        ).to(self.device)

        with torch.no_grad():
            logits = model(**inputs).logits.squeeze(-1)  # shape: [N]

        order: List[int] = torch.argsort(logits, descending=True).tolist()
        ranked_docs = [docs[i] for i in order[:top_k]]
        ranked_metas = [metas[i] for i in order[:top_k]]
        return ranked_docs, ranked_metas

    # ---------------------------
    # Query principal
    # ---------------------------
    def query(self, text: str, top_k: int = 5) -> Tuple[List[str], List[Dict[str, Any]]]:
        # 1) Intención
        intent = self.intent_model.predict(text)
        where = self._build_where(intent)

        if Config.DEBUG:
            print(f"🔎 Intent: {intent}")
            print(f"🔎 Where:  {where}")

        # 2) Embedding (lista de floats para Chroma)
        q_vec: List[float] = self.encoder.encode(text, convert_to_numpy=True).tolist()

        # 3) Búsqueda inicial amplia
        results: QueryResult = self.collection.query(
            query_embeddings=[q_vec],
            n_results=max(20, top_k * 6),
            include=[IncludeEnum.documents, IncludeEnum.metadatas],
            where=where if where else None,
        ) or {}

        raw_docs = cast(Sequence[Sequence[str]], results.get("documents") or [[]])
        raw_metas = cast(Sequence[Sequence[Dict[str, Any]]], results.get("metadatas") or [[]])

        docs: List[str] = list(raw_docs[0]) if raw_docs and len(raw_docs) > 0 and raw_docs[0] else []
        # Convertimos Metadata→dict normal para operar con Any sin que Pylance se queje
        metas: List[Dict[str, Any]] = [dict(m) for m in (raw_metas[0] if raw_metas and len(raw_metas) > 0 else [])]

        if not docs or not metas:
            return [], []

        # 4) Rerank
        docs, metas = self._rerank(text, docs, metas, top_k=top_k)

        if Config.DEBUG:
            print(f"📊 Resultados tras rerank: {len(docs)}")

        return docs, metas

    # ---------------------------
    # API amigable para handlers
    # ---------------------------
    def search(self, query: str, top_k: int = 5) -> Tuple[str, List[Dict[str, Any]]]:
        docs, metas = self.query(query, top_k=top_k)
        if not docs:
            return "⚠️ No se encontraron tareas relevantes.", []

        lines = [f"📋 Resultados para “{query}”:"]
        for i, meta in enumerate(metas, 1):
            lines.append(
                f"{i}. **{meta.get('name', 'Tarea sin nombre')}** "
                f"({meta.get('sprint', 'sin sprint')}, {meta.get('sprint_status', '?')}) — "
                f"{meta.get('status', 'sin estado')}, "
                f"{meta.get('assignees', 'sin asignar')}, "
                f"prioridad: {meta.get('priority', 'sin prioridad')}, "
                f"bloqueada: {meta.get('is_blocked', False)}"
            )
        return "\n".join(lines), metas

    # ---------------------------
    # Agregaciones estilo PM
    # ---------------------------
    def aggregate_counts(self, where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Devuelve:
          - total
          - by_status
          - by_sprint
          - by_assignee
          - by_priority
        """
        res: QueryResult = self.collection.query(
            query_texts=["*"],
            n_results=5000,
            include=[IncludeEnum.metadatas],
            where=where if where else None,
        ) or {}

        raw_metas = cast(Sequence[Sequence[Dict[str, Any]]], res.get("metadatas") or [[]])
        metas: List[Dict[str, Any]] = [dict(m) for m in (raw_metas[0] if raw_metas and len(raw_metas) > 0 else [])]

        total = len(metas)
        by_status: Dict[str, int] = defaultdict(int)
        by_sprint: Dict[str, int] = defaultdict(int)
        by_assignee: Dict[str, int] = defaultdict(int)
        by_priority: Dict[str, int] = defaultdict(int)

        for m in metas:
            by_status[str(m.get("status", "sin estado"))] += 1
            by_sprint[str(m.get("sprint", "sin sprint"))] += 1
            by_assignee[str(m.get("assignees", "sin asignar"))] += 1
            by_priority[str(m.get("priority", "sin prioridad"))] += 1

        return {
            "total": total,
            "by_status": dict(by_status),
            "by_sprint": dict(by_sprint),
            "by_assignee": dict(by_assignee),
            "by_priority": dict(by_priority),
        }
