#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RAG híbrido (BM25 + Embeddings) en memoria.
Combina similitud semántica (vectorial) y lexical (BM25),
aplicando boosts según metadatos como 'bloqueada', 'dudas', 'urgente', y estados abiertos.
"""

import json
import re
import numpy as np
from pathlib import Path
from typing import List
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

# =============================================================
# CONFIGURACIÓN
# =============================================================

INPUT_FILE = Path("data/processed/task_chunks.jsonl")
MODEL_NAME = "sentence-transformers/all-MiniLM-L12-v2"
TOP_K = 5

# Pesos de fusión
W_VEC = 0.6       # peso del vectorial
W_BM25 = 0.4      # peso del lexical
BOOST_BLOCKED = 0.15
BOOST_DOUBT = 0.10
BOOST_URGENT = 0.10
BOOST_OPEN = 0.10  # boost para tareas abiertas (to_do, in_progress, in_review)

# =============================================================
# UTILIDADES
# =============================================================

def load_chunks():
    """Carga los chunks vectorizables desde el archivo procesado."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"No se encontró {INPUT_FILE}. Ejecuta antes 02_chunk_tasks.py.")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]
    print(f"✅ {len(chunks)} chunks cargados correctamente.")
    return chunks


_token_re = re.compile(r"\w+", re.UNICODE)

def tokenize(text: str) -> List[str]:
    """Tokeniza el texto para BM25."""
    return [t.lower() for t in _token_re.findall(text or "")]


def expand_query(query: str) -> str:
    """Amplía la consulta con sinónimos relevantes."""
    ql = query.lower()
    extra = []
    if "bloque" in ql or "blocked" in ql or "imped" in ql:
        extra += ["bloqueada", "bloqueado", "bloqueo", "impedimento", "blocked", "blocker"]
    if "duda" in ql or "question" in ql:
        extra += ["pendiente de aclarar", "dudas", "pregunta"]
    if "urgente" in ql or "prioridad" in ql or "alta prioridad" in ql:
        extra += ["urgente", "prioritaria", "alta prioridad"]
    if "abiert" in ql or "pendiente" in ql or "por hacer" in ql or "sin empezar" in ql or "en curso" in ql:
        extra += ["to do", "in progress", "in review", "pendiente", "no terminada", "en progreso"]
    return ql + " " + " ".join(extra)


def minmax_norm(x: np.ndarray) -> np.ndarray:
    """Normaliza un vector de scores entre 0 y 1."""
    if x.size == 0:
        return x
    mn, mx = float(x.min()), float(x.max())
    if mx - mn < 1e-12:
        return np.zeros_like(x)
    return (x - mn) / (mx - mn)

# =============================================================
# ÍNDICES
# =============================================================

def build_vector_index(model, chunks):
    """Crea el índice vectorial."""
    texts = [c["text"] for c in chunks]
    print(f"🧠 Generando embeddings ({len(texts)} documentos)...")
    embs = model.encode(texts, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
    print(f"✅ Embeddings generados (dim={embs.shape[1]})")
    return embs


def build_bm25_index(chunks):
    """Crea el índice BM25 a partir de texto + metadatos."""
    print("🧰 Construyendo índice BM25...")
    docs_tokens = []
    for c in chunks:
        meta = c.get("metadata", {})
        meta_str = " ".join([
            str(meta.get("status", "")),
            str(meta.get("project", "")),
            str(meta.get("list", "")),
            str(meta.get("priority", "")),
            str(meta.get("tags", "")),
        ])
        doc_text = f"{c['text']} {meta_str}"
        docs_tokens.append(tokenize(doc_text))
    return BM25Okapi(docs_tokens), docs_tokens

# =============================================================
# BÚSQUEDA
# =============================================================

def hybrid_search(query: str, model, vec_embs, chunks, bm25: BM25Okapi, bm25_tokens, top_k=TOP_K):
    """Realiza búsqueda híbrida vectorial + BM25 con boosts por etiquetas y estados."""
    q_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
    vec_scores = cosine_similarity(q_emb, vec_embs)[0]
    vec_scores = minmax_norm(vec_scores)

    q_expanded = expand_query(query)
    bm25_scores = np.array(bm25.get_scores(tokenize(q_expanded)))
    bm25_scores = minmax_norm(bm25_scores)

    fused = W_VEC * vec_scores + W_BM25 * bm25_scores

    # Detectar intención en la query
    ask_blocked = any(k in query.lower() for k in ["bloque", "blocked", "impedimento"])
    ask_doubt = any(k in query.lower() for k in ["duda", "question", "aclarar"])
    ask_urgent = any(k in query.lower() for k in ["urgente", "prioridad", "alta prioridad"])
    ask_open = any(k in query.lower() for k in [
        "abiert", "pendiente", "en curso", "por hacer", "sin empezar", "no terminad"
    ])

    # Aplicar boosts según metadatos
    for i, c in enumerate(chunks):
        meta = c.get("metadata", {})
        status = meta.get("status")

        if ask_blocked and meta.get("is_blocked"):
            fused[i] += BOOST_BLOCKED
        if ask_doubt and meta.get("has_doubts"):
            fused[i] += BOOST_DOUBT
        if ask_urgent and meta.get("is_urgent"):
            fused[i] += BOOST_URGENT
        if ask_open and status in ["to_do", "in_progress", "in_review"]:
            fused[i] += BOOST_OPEN

    top_idx = np.argsort(fused)[::-1][:top_k]
    results = [(chunks[i], float(fused[i]), float(vec_scores[i]), float(bm25_scores[i])) for i in top_idx]

    # Mostrar resultados
    print(f"\n🔎 Consulta: {query}")
    for rank, (chunk, fused_score, vscore, bscore) in enumerate(results, start=1):
        meta = chunk.get("metadata", {})
        print(f"\n#{rank} | FUSED={fused_score:.3f} | vec={vscore:.3f} | bm25={bscore:.3f}")
        print(f"Tarea: {chunk['task_id']} | Proyecto: {meta.get('project')} | Estado: {meta.get('status')}")
        print(f"Texto: {chunk['text'][:300]}...")
        print(f"Metadata: {meta}")

    return results

# =============================================================
# PIPELINE PRINCIPAL
# =============================================================

def main():
    chunks = load_chunks()

    print(f"🧠 Cargando modelo de embeddings: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    vec_embs = build_vector_index(model, chunks)
    bm25, bm25_tokens = build_bm25_index(chunks)

    print("\n✅ Índices construidos. Modo consulta interactivo.")
    while True:
        q = input("\n📝 Escribe tu consulta (o 'salir'): ").strip()
        if q.lower() in {"salir", "exit", "quit"}:
            print("👋 Fin del modo interactivo.")
            break
        hybrid_search(q, model, vec_embs, chunks, bm25, bm25_tokens, top_k=TOP_K)

# =============================================================
# ENTRY POINT
# =============================================================

if __name__ == "__main__":
    main()
