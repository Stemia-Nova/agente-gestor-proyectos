#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HybridSearch: motor híbrido de recuperación semántica para tareas de ClickUp.
- Índices por sprint en ChromaDB (un chroma.sqlite3 por sprint)
- Combina embeddings (SentenceTransformers), BM25 y re-ranking (CrossEncoder)
- Soporta scopes: "active", "all" o "Sprint N"
- Tipado robusto y compatible con chromadb>=0.5 (include como tupla)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, cast

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer
import chromadb
from chromadb.api.models.Collection import Collection

# =============================
# Configuración por defecto
# =============================

EMBED_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

CHROMA_BASE = Path("data/rag/chroma_db")   # carpeta raíz que contiene: index_registry.json y subcarpetas por sprint
COLLECTION_NAME = "clickup_tasks"          # nombre de la colección dentro de cada sprint


class HybridSearch:
    """
    Uso básico:
        hs = HybridSearch()  # intenta usar sprint activo
        hits = hs.query("tareas de Jorge", k=5)            # scope por defecto: "active"
        hits_all = hs.query("bloqueadas", k=10, scope="all")
        n_done = hs.count_tasks(filters={"status": "finalizada"})
    """

    def __init__(self, chroma_base: Path = CHROMA_BASE) -> None:
        self.chroma_base: Path = Path(chroma_base)
        self.embedder: SentenceTransformer = SentenceTransformer(EMBED_MODEL)
        self.reranker: CrossEncoder = CrossEncoder(RERANK_MODEL)
        self.col_active: Optional[Collection] = None

        active = self._get_active_sprint()
        if active:
            self.col_active = self._load_collection(active)
            print(f"✅ Usando colección de sprint activo: {active}")
        else:
            print("⚠️ No hay sprint activo en el registro. Ejecuta el pipeline de sincronización para inicializarlo.")

    # ---------------------------------------------------------------------
    # Registro y carga de colecciones
    # ---------------------------------------------------------------------

    def _get_registry_path(self) -> Path:
        return self.chroma_base / "index_registry.json"

    def _read_registry(self) -> Dict[str, Dict[str, Any]]:
        rp = self._get_registry_path()
        if not rp.exists():
            return {}
        try:
            with rp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _get_active_sprint(self) -> Optional[str]:
        registry = self._read_registry()
        if not registry:
            return None
        # último marcado como active
        active = [s for s, info in registry.items() if (isinstance(info, dict) and info.get("status") == "active")]
        return active[-1] if active else None

    def _load_collection(self, sprint_name: str) -> Collection:
        """Carga (o crea) la colección asociada a un sprint (ruta: {base}/{sprint})."""
        db_path = self.chroma_base / sprint_name
        db_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(db_path))
        return client.get_or_create_collection(name=COLLECTION_NAME)

    def _iter_collections(self, scope: Optional[str]) -> Iterator[Tuple[str, Optional[Collection]]]:
        """
        Itera sobre (sprint, collection) según el scope:
          - None o "active": sólo el sprint activo (si existe).
          - "all": todos los sprints presentes en el registry.
          - "Sprint N": solo ese sprint si existe.
        """
        registry = self._read_registry()
        if not registry:
            # No registry => no hay colecciones todavía
            if scope in (None, "active"):
                yield ("(none)", None)
            return

        if scope in (None, "active"):
            active = self._get_active_sprint()
            if not active:
                yield ("(none)", None)
                return
            yield (active, self._load_collection(active))
            return

        if isinstance(scope, str) and scope.lower() == "all":
            # Iterar todos los sprints conocidos por el registro
            for sprint_name in sorted(registry.keys()):
                yield (sprint_name, self._load_collection(sprint_name))
            return

        # Sprint concreto
        if isinstance(scope, str) and scope in registry:
            yield (scope, self._load_collection(scope))
            return

        # Scope inválido o no presente
        yield ("(none)", None)

    # ---------------------------------------------------------------------
    # Utilidades de obtención de datos
    # ---------------------------------------------------------------------

    def _fetch_docs(self, scope: Optional[str]) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Recupera documentos y metadatos de las colecciones definidas por `scope`.
        Devuelve:
          - documents: List[str]
          - metadatas: List[Dict[str, Any]]
        """
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for sprint_name, col in self._iter_collections(scope):
            if not col:
                continue

            # ⚠️ ChromaDB >=0.5 → include debe ser una secuencia de literales válidos (p.ej. List[str])
            try:
                # chromadb may expect an Include enum; cast to Any to satisfy type checkers
                data = col.get(include=cast(Any, ["documents", "metadatas"]))
            except Exception:
                continue

            # data: {"ids": [...], "documents": List[str] | None, "metadatas": List[Mapping] | None, ...}
            docs = data["documents"] if isinstance(data, dict) and "documents" in data else None
            metas = data["metadatas"] if isinstance(data, dict) and "metadatas" in data else None

            if not docs or not metas:
                continue

            for d, m in zip(docs, metas):
                if not isinstance(d, str):
                    continue
                md: Dict[str, Any] = dict(m) if isinstance(m, dict) else {}
                md.setdefault("sprint", sprint_name)
                documents.append(d)
                metadatas.append(md)

        return documents, metadatas

    # ---------------------------------------------------------------------
    # API pública
    # ---------------------------------------------------------------------

    def count_tasks(self, filters: Optional[Dict[str, Any]] = None, scope: Optional[str] = None) -> int:
        """
        Cuenta tareas opcionalmente filtradas por metadatos en el scope dado.
        - filters: igualdad estricta str/int/bool con conversión a str lower() para comparación robusta
        - scope: None/"active"/"all"/"Sprint N"
        """
        # Si solo queremos contar, podemos pedir sólo metadatas para ahorrar
        documents_dummy: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for sprint_name, col in self._iter_collections(scope):
            if not col:
                continue

            try:
                # chromadb may expect an Include enum; cast to Any to satisfy type checkers
                data = col.get(include=cast(Any, ["metadatas"]))
            except Exception:
                continue

            metas = data["metadatas"] if isinstance(data, dict) and "metadatas" in data else None
            if not metas:
                continue

            for m in metas:
                md: Dict[str, Any] = dict(m) if isinstance(m, dict) else {}
                md.setdefault("sprint", sprint_name)
                metadatas.append(md)

        if not metadatas:
            return 0

        if not filters:
            return len(metadatas)

        def _match(meta: Dict[str, Any], flt: Dict[str, Any]) -> bool:
            for k, v in flt.items():
                av = meta.get(k, "")
                if isinstance(v, bool):
                    if str(bool(av)).lower() != str(v).lower():
                        return False
                else:
                    if str(av).lower() != str(v).lower():
                        return False
            return True

        return sum(1 for m in metadatas if _match(m, filters))

    def query(self, text: str, k: int = 5, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Ejecuta búsqueda híbrida (embeddings + BM25) y re-ranking cruzado.
        - scope: None/"active"/"all"/"Sprint N"
        - Devuelve [{ "text": str, "metadata": dict, "score": float_normalizado_0_1 }, ...]
        """
        docs, metas = self._fetch_docs(scope)

        if not docs or not metas:
            raise ValueError("❌ No hay documentos indexados en ChromaDB para el scope solicitado.")

        # 1) Similaridad semántica (coseno)
        query_vec = self.embedder.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        doc_vecs = self.embedder.encode(docs, convert_to_numpy=True, normalize_embeddings=True)
        scores_sem = np.dot(doc_vecs, query_vec)  # ya normalizados → coseno directo

        top_sem_idx = np.argsort(scores_sem)[::-1][:k]
        sem_hits = [{"text": docs[i], "metadata": metas[i], "score": float(scores_sem[i])} for i in top_sem_idx]

        # 2) BM25
        tokenized_corpus = [d.split() for d in docs]
        bm25 = BM25Okapi(tokenized_corpus)
        scores_bm25 = bm25.get_scores(text.split())
        top_bm_idx = np.argsort(scores_bm25)[::-1][:k]
        prox_hits = [{"text": docs[i], "metadata": metas[i], "score": float(scores_bm25[i])} for i in top_bm_idx]

        # 3) Combinar (únicos por task_id + sprint + título si existiera)
        def _key(h: Dict[str, Any]) -> str:
            md = h.get("metadata", {})
            tid = str(md.get("task_id", ""))
            sp = str(md.get("sprint", ""))
            return f"{tid}::{sp}"

        combined = sem_hits + prox_hits
        unique_map: Dict[str, Dict[str, Any]] = {}
        for h in combined:
            unique_map[_key(h)] = h
        merged_hits = list(unique_map.values())

        # 4) Re-ranking cruzado
        pairs = [(text, h["text"]) for h in merged_hits]
        rerank_scores = self.reranker.predict(pairs)  # np.ndarray
        reranked = [
            {"text": h["text"], "metadata": h["metadata"], "score": float(s)}
            for h, s in zip(merged_hits, list(rerank_scores))
        ]
        reranked.sort(key=lambda x: x["score"], reverse=True)

        # 5) Normalización 0–1
        if reranked:
            arr = np.array([r["score"] for r in reranked], dtype=np.float32)
            mn, mx = float(arr.min()), float(arr.max())
            if mx > mn:
                for r in reranked:
                    r["score"] = (r["score"] - mn) / (mx - mn)
            else:
                # todos iguales → poner 1.0
                for r in reranked:
                    r["score"] = 1.0

        return reranked[:k]

    # ---------------------------------------------------------------------
    # CLI de depuración
    # ---------------------------------------------------------------------

    @staticmethod
    def debug_query() -> None:
        print("\n🔍 *** MODO INTERACTIVO HYBRID SEARCH ***")
        print("Escribe tu consulta (o 'salir' para terminar)\n")

        hs = HybridSearch()
        while True:
            q = input("👉 Introduce tu consulta: ").strip()
            if not q or q.lower() in ("salir", "exit", "quit"):
                break

            scope = input("   Scope [active|all|Sprint N] (ENTER=active): ").strip() or "active"
            try:
                hits = hs.query(q, k=5, scope=scope)
            except Exception as e:
                print(f"\n❌ Error durante la búsqueda: {e}\n")
                continue

            print("\n================================================================================")
            for i, h in enumerate(hits, start=1):
                meta = h.get("metadata", {})
                print(
                    f"{i}. ({h['score']:.3f}) {meta.get('task_id', '-')}"
                    f" ({meta.get('sprint', '-')}"
                    f" • {meta.get('status', '-')}"
                    f" • {meta.get('priority', '-')}) — "
                    f"{h['text'][:120].replace('\\n', ' ')}"
                )
            print("================================================================================")


if __name__ == "__main__":
    HybridSearch.debug_query()
