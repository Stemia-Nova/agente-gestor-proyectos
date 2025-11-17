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
import hashlib
import logging
import time
from datetime import datetime
from functools import lru_cache

import numpy as np
import torch
import torch.nn as nn
import chromadb
from chromadb.api.types import GetResult

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers.tokenization_utils_base import PreTrainedTokenizerBase
from openai import OpenAI
from openai import OpenAI, RateLimitError

# Logger
logger = logging.getLogger(__name__)


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
    # LLM Helper
    # -------------------------
    def _ensure_llm(self) -> OpenAI:
        """Asegura que hay un cliente OpenAI disponible."""
        if not self.llm:
            raise ValueError("OpenAI no está configurado. Verifica OPENAI_API_KEY.")
        return self.llm

    # -------------------------
    # Búsqueda
    # -------------------------
    def _call_llm_with_retry(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "gpt-4o-mini",
        temperature: float = 0.4,
        max_retries: int = 3
    ) -> str:
        """Llama al LLM con reintentos exponenciales en caso de rate limit.
        
        Args:
            messages: Lista de mensajes para el chat
            model: Modelo a usar
            temperature: Temperatura del modelo
            max_retries: Número máximo de reintentos
            
        Returns:
            Respuesta del modelo o mensaje de error
        """
        llm = self._ensure_llm()
        
        for attempt in range(max_retries):
            try:
                completion = llm.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore
                    temperature=temperature,
                )
                content = completion.choices[0].message.content
                return content.strip() if content else "No se pudo generar respuesta."
                
            except RateLimitError as e:
                wait_time = (2 ** attempt) * 1  # Espera exponencial: 1s, 2s, 4s
                if attempt < max_retries - 1:
                    logger.warning(f"⏳ Rate limit alcanzado. Reintentando en {wait_time}s... (intento {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Rate limit después de {max_retries} intentos")
                    return "⏳ El servicio está temporalmente saturado. Por favor, intenta de nuevo en unos segundos."
                    
            except Exception as e:
                logger.error(f"❌ Error en llamada al LLM: {e}")
                return f"❌ Error al generar respuesta: {str(e)[:100]}"
        
        return "❌ No se pudo completar la solicitud."

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
    def _extract_filters_from_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Extrae filtros de metadata desde la query en español."""
        query_lower = query.lower()
        filters: Dict[str, Any] = {}
        
        # Filtros de estado (ahora en español)
        if "pendiente" in query_lower or "por hacer" in query_lower:
            filters["status"] = "Pendiente"
        elif "en progreso" in query_lower or "trabajando" in query_lower or "progreso" in query_lower:
            filters["status"] = "En progreso"
        elif "qa" in query_lower or "testing" in query_lower or "prueba" in query_lower:
            filters["status"] = "En QA"
        elif "review" in query_lower or "revisión" in query_lower or "revision" in query_lower:
            filters["status"] = "En revisión"
        elif "completada" in query_lower or "finalizada" in query_lower or "hecha" in query_lower or "terminada" in query_lower:
            filters["status"] = "Completada"
        elif "cancelada" in query_lower:
            filters["status"] = "Cancelada"
        
        if "bloqueada" in query_lower or "bloqueado" in query_lower:
            filters["is_blocked"] = True
        
        sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
        if sprint_match:
            filters["sprint"] = f"Sprint {sprint_match.group(1)}"
        
        # Filtros de prioridad (ahora en español)
        if "urgente" in query_lower:
            filters["priority"] = "Urgente"
        elif "alta prioridad" in query_lower or "prioridad alta" in query_lower:
            filters["priority"] = "Alta"
        elif "baja prioridad" in query_lower or "prioridad baja" in query_lower:
            filters["priority"] = "Baja"
        
        if len(filters) > 1:
            conditions = [{k: v} for k, v in filters.items()]
            return {"$and": conditions}
        
        return filters if filters else None

    # =============================================================
    # Nuevas funciones: Métricas avanzadas
    # =============================================================
    
    def get_sprint_metrics(self, sprint: str) -> Dict[str, Any]:
        """Obtiene métricas completas de un sprint."""
        try:
            sprint_filter = cast(Any, {"sprint": sprint})
            result = self.collection.get(where=sprint_filter, limit=1000)
            metadatas = result.get('metadatas') or []
            
            total = len(metadatas)
            if total == 0:
                return {"error": f"No hay tareas en {sprint}"}
            
            done = sum(1 for m in metadatas if m.get('status') == 'Completada')
            in_progress = sum(1 for m in metadatas if m.get('status') == 'En progreso')
            to_do = sum(1 for m in metadatas if m.get('status') == 'Pendiente')
            qa = sum(1 for m in metadatas if m.get('status') == 'qa')
            review = sum(1 for m in metadatas if m.get('status') == 'review')
            blocked = sum(1 for m in metadatas if m.get('is_blocked', False))
            high_priority = sum(1 for m in metadatas if m.get('priority') in ['high', 'urgent'])
            
            return {
                "sprint": sprint,
                "total": total,
                "completadas": done,
                "en_progreso": in_progress,
                "pendientes": to_do,
                "qa": qa,
                "review": review,
                "bloqueadas": blocked,
                "porcentaje_completitud": round((done / total) * 100, 1) if total > 0 else 0,
                "alta_prioridad": high_priority,
                "completadas": done
            }
        except Exception as e:
            logger.error(f"❌ Error obteniendo métricas de {sprint}: {e}")
            return {"error": str(e)}
    
    def compare_sprints(self, sprints: List[str]) -> str:
        """Compara múltiples sprints."""
        try:
            logger.info(f"📊 Comparando sprints: {sprints}")
            metrics = [self.get_sprint_metrics(s) for s in sprints]
            
            response = "📊 **Comparación de Sprints**\n\n"
            for m in metrics:
                if "error" in m:
                    response += f"⚠️ {m['sprint']}: {m['error']}\n\n"
                    continue
                
                response += f"**{m['sprint']}**:\n"
                response += f"  • Completado: {m['porcentaje_completitud']}% ({m['completadas']}/{m['total']} tareas)\n"
                response += f"  • En progreso: {m['en_progreso']}\n"
                response += f"  • Pendientes: {m['pendientes']}\n"
                response += f"  • QA/Review: {m['qa']}/{m['review']}\n"
                response += f"  • Bloqueadas: {m['bloqueadas']}\n"
                response += f"  • Alta prioridad: {m['alta_prioridad']}\n"
                response += f"  • Completadas: {m['completadas']}\n\n"
            
            return response.strip()
        except Exception as e:
            logger.error(f"❌ Error comparando sprints: {e}")
            return f"❌ Error al comparar sprints: {e}"

    def generate_report(self, sprint: str, destinatario: str = "Project Manager / Scrum Master") -> str:
        """
        Genera un informe profesional del sprint para PMs y Scrum Masters.
        
        Args:
            sprint: Nombre del sprint (ej: "Sprint 2")
            destinatario: A quién va dirigido el informe
            
        Returns:
            Informe profesional formateado
        """
        try:
            logger.info(f"📄 Generando informe profesional para {sprint}...")
            
            # Obtener métricas
            metrics = self.get_sprint_metrics(sprint)
            if "error" in metrics:
                return f"❌ Error al generar informe: {metrics['error']}"
            
            # Obtener todas las tareas del sprint
            sprint_filter = {"sprint": sprint}
            result = self.collection.get(
                where=cast(Any, sprint_filter),
                limit=1000,
                include=cast(Any, ['metadatas'])
            )
            
            tasks = cast(List[Dict[str, Any]], result.get('metadatas') or [])
            
            if not tasks:
                return f"⚠️ No se encontraron tareas para {sprint}"
            
            # Importar generador de informes
            from utils.report_generator import ReportGenerator
            
            generator = ReportGenerator()
            report = generator.generate_sprint_report(
                sprint_name=sprint,
                metrics=metrics,
                tasks=tasks,
                destinatario=destinatario
            )
            
            logger.info(f"✅ Informe generado exitosamente para {sprint}")
            return report
            
        except Exception as e:
            logger.error(f"❌ Error generando informe: {e}", exc_info=True)
            return f"❌ Error al generar informe: {str(e)}"

    def generate_report_pdf(
        self, 
        sprint: str, 
        output_path: str,
        destinatario: str = "Project Manager / Scrum Master"
    ) -> Optional[str]:
        """
        Genera un informe profesional del sprint en formato PDF.
        
        Args:
            sprint: Nombre del sprint (ej: "Sprint 2")
            output_path: Ruta donde guardar el PDF
            destinatario: A quién va dirigido el informe
            
        Returns:
            Ruta del archivo PDF generado, o None si hubo error
        """
        try:
            logger.info(f"📄 Generando informe PDF para {sprint}...")
            
            # Obtener métricas
            metrics = self.get_sprint_metrics(sprint)
            if "error" in metrics:
                return f"❌ Error al generar informe: {metrics['error']}"
            
            # Obtener todas las tareas del sprint
            sprint_filter = {"sprint": sprint}
            result = self.collection.get(
                where=cast(Any, sprint_filter),
                limit=1000,
                include=cast(Any, ['metadatas'])
            )
            
            tasks = cast(List[Dict[str, Any]], result.get('metadatas') or [])
            
            if not tasks:
                return f"⚠️ No se encontraron tareas para {sprint}"
            
            # Importar generador de informes
            from utils.report_generator import ReportGenerator
            
            generator = ReportGenerator()
            pdf_path = generator.export_to_pdf(
                sprint_name=sprint,
                metrics=metrics,
                tasks=tasks,
                output_path=output_path,
                destinatario=destinatario
            )
            
            if pdf_path:
                logger.info(f"✅ Informe PDF generado para {sprint}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"❌ Error generando PDF: {e}", exc_info=True)
            return None

    # =============================================================
    # Conteo y agregaciones
    # =============================================================
    
    def count_tasks(self, where: Optional[Dict[str, Any]] = None) -> int:
        """Cuenta tareas que coinciden con los filtros."""
        try:
            result = self.collection.get(where=cast(Any, where), limit=1000)
            return len(result['ids'])
        except Exception as e:
            logger.error(f"⚠️ Error contando tareas: {e}")
            return 0
    
    def aggregate_by_field(self, field: str, where: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """Agrega tareas por un campo específico."""
        try:
            result = self.collection.get(where=cast(Any, where), limit=1000)
            aggregation: Dict[str, int] = {}
            metadatas = result.get('metadatas') or []
            for meta in metadatas:
                value = str(meta.get(field, "Sin especificar"))
                aggregation[value] = aggregation.get(value, 0) + 1
            return aggregation
        except Exception as e:
            logger.error(f"⚠️ Error agregando por {field}: {e}")
            return {}
    
    def _handle_count_question(self, query: str) -> Optional[Dict[str, Any]]:
        """Extrae datos de conteo para que el LLM genere la respuesta.
        
        Retorna un dict con:
        - count: número de tareas
        - tasks: lista de metadatos de las tareas encontradas
        - context: descripción del filtro aplicado
        
        O None si no es una pregunta de conteo manejable.
        """
        query_lower = query.lower()
        
        try:
            # Obtener todas las tareas una sola vez
            all_tasks = self.collection.get(limit=10000, include=cast(Any, ['metadatas']))
            metadatas = all_tasks.get('metadatas') or []
            
            if not metadatas:
                return {"count": 0, "tasks": [], "context": "No hay tareas en el sistema"}
            
            # Determinar filtros
            filtered_tasks = metadatas
            filter_desc = []
            
            # Filtro por persona
            if "jorge" in query_lower:
                filtered_tasks = [m for m in filtered_tasks if m.get('assignees') and 'Jorge' in str(m.get('assignees', ''))]
                filter_desc.append("asignadas a Jorge")
            elif "laura" in query_lower:
                filtered_tasks = [m for m in filtered_tasks if m.get('assignees') and 'Laura' in str(m.get('assignees', ''))]
                filter_desc.append("asignadas a Laura")
            
            # Filtro por sprint
            sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
            if sprint_match:
                sprint_name = f"Sprint {sprint_match.group(1)}"
                filtered_tasks = [m for m in filtered_tasks if m.get('sprint') == sprint_name]
                filter_desc.append(f"del {sprint_name}")
            
            # Filtro por estado
            if "completada" in query_lower or "hecha" in query_lower:
                filtered_tasks = [m for m in filtered_tasks if m.get('status') == 'Completada']
                filter_desc.append("completadas")
            elif "pendiente" in query_lower:
                filtered_tasks = [m for m in filtered_tasks if m.get('status') == 'Pendiente']
                filter_desc.append("pendientes")
            elif "progreso" in query_lower or "curso" in query_lower:
                filtered_tasks = [m for m in filtered_tasks if m.get('status') == 'En progreso']
                filter_desc.append("en progreso")
            elif "bloquead" in query_lower:
                filtered_tasks = [m for m in filtered_tasks if m.get('is_blocked')]
                filter_desc.append("bloqueadas")
            
            context = "tareas " + " ".join(filter_desc) if filter_desc else "todas las tareas"
            
            return {
                "count": len(filtered_tasks),
                "tasks": filtered_tasks,
                "context": context
            }
            
        except Exception as e:
            logger.error(f"Error en _handle_count_question: {e}")
            return None

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
        """Genera respuesta usando OpenAI."""
        if not self._openai_enabled or not self.llm:
            return "ℹ️ Generación deshabilitada (no se encontró OPENAI_API_KEY)."
        
        try:
            resp = self.llm.chat.completions.create(
                model=self.cfg.openai_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                temperature=self.cfg.temperature,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error(f"Error en _gen: {e}")
            return "No se obtuvo contenido del modelo."

    # -------------------------
    # Router de intents principal
    # -------------------------
    def answer(
        self, 
        query: str, 
        top_k: int = 6, 
        temperature: float = 0.4, 
        conversation_context: str = ""
    ) -> str:
        """Genera respuesta contextualizada con manejo robusto de errores."""
        try:
            if not query or len(query.strip()) < 3:
                return "❓ Por favor, formula una pregunta más específica."
            
            logger.info(f"💬 Generando respuesta para: '{query[:50]}...'")
            query_lower = query.lower()
            
            # Detectar solicitud de informe
            is_report_request = any(word in query_lower for word in [
                'informe', 'reporte', 'report', 'generar informe', 'genera informe'
            ])
            
            is_pdf_request = 'pdf' in query_lower
            
            if is_report_request:
                sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
                if sprint_match:
                    sprint = f"Sprint {sprint_match.group(1)}"
                    
                    if is_pdf_request:
                        from datetime import datetime as dt
                        fecha = dt.now().strftime("%Y%m%d_%H%M")
                        pdf_path = f"data/logs/informe_{sprint.replace(' ', '_').lower()}_{fecha}.pdf"
                        result = self.generate_report_pdf(sprint, pdf_path)
                        return result if result else f"❌ Error al generar PDF para {sprint}"
                    else:
                        return self.generate_report(sprint)
                else:
                    return "⚠️ Por favor, especifica el sprint para generar el informe (ej: 'genera informe del Sprint 2' o 'genera informe PDF del Sprint 2')"
            
            # Detectar preguntas de conteo
            is_count_question = any(word in query_lower for word in [
                'cuántas', 'cuantas', 'cantidad', 'número', 'total', 'count'
            ])
            
            if is_count_question:
                count_data = self._handle_count_question(query)
                if count_data:
                    context_parts = []
                    for m in count_data['tasks'][:15]:
                        status_spanish = m.get('status_spanish', m.get('status', 'sin estado'))
                        blocked = "⚠️ BLOQUEADA" if m.get('is_blocked') else ""
                        context_parts.append(
                            f"• {m.get('name', 'sin nombre')} - {status_spanish} {blocked}\n"
                            f"  Asignado a: {m.get('assignees', 'sin asignar')} | Sprint: {m.get('sprint', 'N/A')} | "
                            f"Prioridad: {m.get('priority', 'sin prioridad')}"
                        )
                    
                    count_summary = (
                        f"RESULTADO DEL CONTEO:\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"TOTAL ENCONTRADO: {count_data['count']} tareas\n"
                        f"FILTROS APLICADOS: {count_data['context']}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    )
                    
                    if count_data['count'] == 0:
                        context = count_summary + "No se encontraron tareas que cumplan estos criterios."
                    else:
                        context = count_summary + "\n\n".join(context_parts) if context_parts else count_summary
                    
                    system_prompt = (
                        "Eres un asistente de gestión de proyectos. "
                        "Responde preguntas de conteo de forma directa y precisa. "
                        "Usa EXACTAMENTE el número que aparece en 'TOTAL ENCONTRADO' del contexto. "
                        "No inventes números ni hagas cálculos adicionales."
                    )
                    
                    user_prompt = (
                        f"Contexto:\n{context}\n\n"
                        f"Pregunta: {query}\n\n"
                        f"Responde de forma natural y conversacional, usando el número exacto del TOTAL ENCONTRADO. "
                        f"Si hay 0 tareas, di que no hay ninguna. Si hay 1, usa singular. Si hay más, usa plural."
                    )
                    
                    return self._call_llm_with_retry(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.3
                    )
            
            # Detectar comparaciones
            is_comparison = any(word in query_lower for word in [
                'compar', 'vs', 'versus', 'diferencia'
            ])
            
            if is_comparison:
                sprint_matches = re.findall(r"sprint\s*(\d+)", query_lower)
                if len(sprint_matches) >= 2:
                    sprints = [f"Sprint {num}" for num in sprint_matches]
                    return self.compare_sprints(sprints)
            
            # Detectar solicitud de métricas
            if "progreso" in query_lower or "métrica" in query_lower or "resumen" in query_lower:
                sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
                if sprint_match:
                    sprint = f"Sprint {sprint_match.group(1)}"
                    metrics = self.get_sprint_metrics(sprint)
                    if "error" not in metrics:
                        return (
                            f"📊 **Métricas de {metrics['sprint']}**\n\n"
                            f"• Completado: {metrics['porcentaje_completitud']}% ({metrics['completadas']}/{metrics['total']} tareas)\n"
                            f"• En progreso: {metrics['en_progreso']}\n"
                            f"• Pendientes: {metrics['pendientes']}\n"
                            f"• QA/Review: {metrics['qa']}/{metrics['review']}\n"
                            f"• Bloqueadas: {metrics['bloqueadas']}\n"
                            f"• Alta prioridad: {metrics['alta_prioridad']}\n"
                        )
            
            # Búsqueda normal con RAG
            docs, metas = self.search(query, top_k=top_k)
            if not docs:
                from chatbot.prompts import RAG_NO_RESULTS
                return RAG_NO_RESULTS

            context_parts = []
            for m in metas[:top_k]:
                status_spanish = m.get('status_spanish', m.get('status', 'sin estado'))
                blocked = "⚠️ BLOQUEADA" if m.get('is_blocked') else ""
                context_parts.append(
                    f"• {m.get('name', 'sin nombre')} - {status_spanish} {blocked}\n"
                    f"  Sprint: {m.get('sprint', 'N/A')} | Prioridad: {m.get('priority', 'sin prioridad')}\n"
                    f"  Asignado: {m.get('assignees', 'sin asignar')}"
                )
            
            context = "\n\n".join(context_parts)
            
            if conversation_context:
                context = f"{conversation_context}\n\n{'='*50}\n\n{context}"

            from chatbot.prompts import SYSTEM_INSTRUCTIONS, RAG_CONTEXT_PROMPT
            
            system_prompt = SYSTEM_INSTRUCTIONS
            user_prompt = RAG_CONTEXT_PROMPT.format(
                system="",
                context=context,
                question=query
            )

            return self._call_llm_with_retry(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature
            )

        except ConnectionError as e:
            logger.error(f"❌ Error de conexión con OpenAI: {e}")
            return ("❌ Error de conexión con el servicio de IA. "
                   "Por favor, verifica tu conexión a internet e intenta de nuevo.")
        except Exception as e:
            logger.error(f"❌ Error inesperado en answer(): {e}", exc_info=True)
            return f"❌ Ocurrió un error procesando tu consulta: {str(e)[:100]}"

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
