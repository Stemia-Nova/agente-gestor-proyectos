#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hybrid_search_optimized.py — Versión optimizada con mejoras profesionales
--------------------------------------------------------------------------
Mejoras implementadas:
 • Caché de embeddings para performance
 • Logging robusto y comprehensivo
 • Métricas avanzadas de sprint
 • Comparación entre sprints
 • Detalles enriquecidos de tareas con subtareas
 • Manejo de errores profesional
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional, Sequence, cast
import re
import hashlib
import logging
from datetime import datetime
from functools import lru_cache

import numpy as np
import torch
import chromadb
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from openai import OpenAI

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HybridSearch:
    """Motor de búsqueda híbrida con optimizaciones profesionales."""

    def __init__(
        self,
        collection_name: str = "clickup_tasks",
        db_path: Optional[str] = None,
        cache_size: int = 100,
    ) -> None:
        self.db_path = db_path or "data/rag/chroma_db"
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(collection_name)
        logger.info(f"✅ HybridSearch inicializado sobre colección '{collection_name}'.")

        # Caché de embeddings
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_size = cache_size

        # Lazy loading
        self._embedder: Optional[SentenceTransformer] = None
        self._rerank_tokenizer: Optional[Any] = None
        self._rerank_model: Optional[AutoModelForSequenceClassification] = None
        self._llm: Optional[OpenAI] = None

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"🖥️  Usando dispositivo: {self.device}")

    # =============================================================
    # Embeddings con caché
    # =============================================================
    def _ensure_embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            logger.info("🧠 Cargando modelo de embeddings MiniLM...")
            self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")
        return self._embedder

    def _ensure_reranker(self):
        if self._rerank_model is None or self._rerank_tokenizer is None:
            logger.info("🧩 Cargando modelo de reranking (MiniLM CrossEncoder)...")
            self._rerank_tokenizer = AutoTokenizer.from_pretrained("cross-encoder/ms-marco-MiniLM-L-12-v2")
            self._rerank_model = AutoModelForSequenceClassification.from_pretrained(
                "cross-encoder/ms-marco-MiniLM-L-12-v2"
            ).to(self.device)

    def _ensure_llm(self) -> OpenAI:
        if self._llm is None:
            self._llm = OpenAI()
        return self._llm

    def _embed_query(self, text: str) -> List[float]:
        """Embed con caché para queries repetidas."""
        # Generar clave de caché
        cache_key = hashlib.md5(text.encode()).hexdigest()
        
        # Verificar caché
        if cache_key in self._embedding_cache:
            logger.debug(f"🎯 Caché hit para query: '{text[:30]}...'")
            return self._embedding_cache[cache_key]
        
        # Generar embedding
        model = self._ensure_embedder()
        emb = model.encode(text, convert_to_numpy=True)
        emb_list = emb.astype(np.float32).tolist()
        
        # Guardar en caché (con límite)
        if len(self._embedding_cache) >= self._cache_size:
            # Eliminar entrada más antigua (FIFO)
            oldest_key = next(iter(self._embedding_cache))
            del self._embedding_cache[oldest_key]
        
        self._embedding_cache[cache_key] = emb_list
        logger.debug(f"💾 Embedding cacheado para: '{text[:30]}...'")
        
        return emb_list

    def search(
        self, 
        query: str, 
        top_k: int = 8,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        use_filters: bool = False
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Búsqueda con logging comprehensivo."""
        try:
            start_time = datetime.now()
            logger.info(f"🔍 Nueva búsqueda: '{query[:50]}...'")
            
            # Extraer filtros
            post_filters = {}
            if use_filters and not where:
                where = self._extract_filters_from_query(query)
                if where and "is_blocked" in str(where):
                    import json
                    where_str = json.dumps(where)
                    if '"is_blocked": true' in where_str.lower():
                        post_filters["is_blocked"] = True
                        where = self._remove_boolean_filters(where)
                if where:
                    logger.info(f"🔍 Filtros ChromaDB: {where}")
                if post_filters:
                    logger.info(f"🔍 Post-filtros (Python): {post_filters}")
            
            q_emb = self._embed_query(query)
            
            n_results = 50 if post_filters and not where else top_k
            search_params: Dict[str, Any] = {
                "query_embeddings": [q_emb],
                "n_results": n_results,
                "include": cast(Any, ["documents", "metadatas"])
            }
            
            if where:
                search_params["where"] = where
            if where_document:
                search_params["where_document"] = where_document
            
            res = self.collection.query(**search_params)

            docs_container = res.get("documents")
            metas_container = res.get("metadatas")

            docs = cast(List[str], docs_container[0] if docs_container and len(docs_container) > 0 else [])
            metas = cast(List[Dict[str, Any]], metas_container[0] if metas_container and len(metas_container) > 0 else [])

            if not docs or not metas:
                logger.warning(f"⚠️  No se encontraron resultados para: '{query[:50]}...'")
                return [], []

            # Post-filtrado
            if post_filters:
                filtered_docs, filtered_metas = [], []
                for doc, meta in zip(docs, metas):
                    matches = all(meta.get(k) == v for k, v in post_filters.items())
                    if matches:
                        filtered_docs.append(doc)
                        filtered_metas.append(meta)
                docs, metas = filtered_docs[:top_k], filtered_metas[:top_k]
                if not docs:
                    logger.warning(f"⚠️  Post-filtrado eliminó todos los resultados")
                    return [], []

            docs, metas = self._rerank(query, docs, metas)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ Búsqueda completada en {elapsed:.2f}s - {len(docs)} resultados")
            
            return docs, metas
            
        except Exception as e:
            logger.error(f"❌ Error en búsqueda: {e}", exc_info=True)
            return [], []
    
    def _remove_boolean_filters(self, where: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Remueve filtros booleanos del dict para ChromaDB."""
        if "$and" in where:
            conditions = [c for c in where["$and"] if "is_blocked" not in c]
            if len(conditions) == 0:
                return None
            elif len(conditions) == 1:
                return conditions[0]
            else:
                return {"$and": conditions}
        else:
            return {k: v for k, v in where.items() if k != "is_blocked"} or None

    def _rerank(self, query: str, docs: List[str], metas: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
        self._ensure_reranker()
        assert self._rerank_tokenizer and self._rerank_model

        pairs = [(query, d) for d in docs]
        enc = self._rerank_tokenizer(
            [p[0] for p in pairs],
            [p[1] for p in pairs],
            padding=True,
            truncation=True,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = cast(Any, self._rerank_model)(**enc)
            scores = outputs.logits.squeeze(-1)

        idxs = torch.argsort(scores, descending=True).tolist()
        return [docs[i] for i in idxs], [metas[i] for i in idxs]

    def _extract_filters_from_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Extrae filtros de metadata desde la query."""
        query_lower = query.lower()
        filters: Dict[str, Any] = {}
        
        if "pendiente" in query_lower or "por hacer" in query_lower:
            filters["status"] = "to_do"
        elif "en progreso" in query_lower or "trabajando" in query_lower:
            filters["status"] = "in_progress"
        elif "qa" in query_lower or "testing" in query_lower or "prueba" in query_lower:
            filters["status"] = "qa"
        elif "review" in query_lower or "revisión" in query_lower or "revision" in query_lower:
            filters["status"] = "review"
        elif "completada" in query_lower or "finalizada" in query_lower or "hecha" in query_lower:
            filters["status"] = "done"
        elif "cancelada" in query_lower:
            filters["status"] = "cancelled"
        
        if "bloqueada" in query_lower or "bloqueado" in query_lower:
            filters["is_blocked"] = True
        
        sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
        if sprint_match:
            filters["sprint"] = f"Sprint {sprint_match.group(1)}"
        
        if "urgente" in query_lower:
            filters["priority"] = "urgent"
        elif "alta prioridad" in query_lower or "prioridad alta" in query_lower:
            filters["priority"] = "high"
        elif "baja prioridad" in query_lower or "prioridad baja" in query_lower:
            filters["priority"] = "low"
        
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
            
            done = sum(1 for m in metadatas if m.get('status') == 'done')
            in_progress = sum(1 for m in metadatas if m.get('status') == 'in_progress')
            to_do = sum(1 for m in metadatas if m.get('status') == 'to_do')
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
    ) -> str:
        """
        Genera un informe profesional del sprint en formato PDF.
        
        Args:
            sprint: Nombre del sprint (ej: "Sprint 2")
            output_path: Ruta donde guardar el PDF
            destinatario: A quién va dirigido el informe
            
        Returns:
            Mensaje de confirmación o error
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
            result_msg = generator.export_to_pdf(
                sprint_name=sprint,
                metrics=metrics,
                tasks=tasks,
                output_path=output_path,
                destinatario=destinatario
            )
            
            logger.info(f"✅ Informe PDF generado para {sprint}")
            return result_msg
            
        except Exception as e:
            logger.error(f"❌ Error generando PDF: {e}", exc_info=True)
            return f"❌ Error al generar PDF: {str(e)}"

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
    
    def _handle_count_question(self, query: str) -> str:
        """Maneja preguntas de conteo."""
        query_lower = query.lower()
        
        sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
        sprint_filter = None
        if sprint_match:
            sprint_num = sprint_match.group(1)
            sprint_filter = {"sprint": f"Sprint {sprint_num}"}
        
        if "actual" in query_lower or "corriente" in query_lower:
            sprint_filter = {"sprint": "Sprint 3"}
        
        state_filter = None
        if "curso" in query_lower or "en progreso" in query_lower or "no completadas" in query_lower:
            state_filter = {"status": {"$ne": "done"}}
        elif "completadas" in query_lower or "finalizadas" in query_lower:
            state_filter = {"status": "done"}
        elif "pendiente" in query_lower or "por hacer" in query_lower:
            state_filter = {"status": "to_do"}
        elif "bloqueada" in query_lower:
            state_filter = {"is_blocked": True}
        elif " qa" in query_lower or "testing" in query_lower or "prueba" in query_lower:
            state_filter = {"status": "qa"}
        elif "review" in query_lower or "revisión" in query_lower:
            state_filter = {"status": "review"}
        
        combined_filter = None
        if sprint_filter and state_filter:
            combined_filter = {"$and": [sprint_filter, state_filter]}
        elif sprint_filter:
            combined_filter = sprint_filter
        elif state_filter:
            combined_filter = state_filter
        
        count = self.count_tasks(where=combined_filter)
        
        task_names = []
        if count > 0 and count <= 5:
            try:
                result = self.collection.get(where=cast(Any, combined_filter), limit=5)
                metadatas = result.get('metadatas') or []
                task_names = [m.get('name', 'Sin nombre') for m in metadatas]
            except Exception:
                pass
        
        if sprint_match:
            sprint_text = f"Sprint {sprint_match.group(1)}"
        elif "actual" in query_lower:
            sprint_text = "el sprint actual (Sprint 3)"
        else:
            sprint_text = "total"
        
        if state_filter:
            if "curso" in query_lower:
                state_text = "en curso (no completadas)"
            elif combined_filter and "$ne" in str(combined_filter):
                state_text = "en curso"
            elif state_filter.get("status") == "done":
                state_text = "completadas"
            elif state_filter.get("status") == "to_do":
                state_text = "pendientes"
            elif state_filter.get("status") == "qa":
                state_text = "en QA/testing"
            elif state_filter.get("status") == "review":
                state_text = "en revisión"
            elif state_filter.get("is_blocked"):
                state_text = "bloqueadas"
            else:
                state_text = ""
        else:
            state_text = ""
        
        plural = count != 1
        if sprint_text != "total" and state_text:
            if plural:
                base_response = f"En {sprint_text} hay {count} tareas {state_text}"
            else:
                state_singular = state_text.rstrip('s') if state_text.endswith('as') or state_text.endswith('es') else state_text
                base_response = f"En {sprint_text} hay {count} tarea {state_singular}"
        elif sprint_text != "total":
            base_response = f"En {sprint_text} hay {count} tarea{'s' if plural else ''}"
        elif state_text:
            if plural:
                base_response = f"Hay {count} tareas {state_text}"
            else:
                state_singular = state_text.rstrip('s') if state_text.endswith('as') or state_text.endswith('es') else state_text
                base_response = f"Hay {count} tarea {state_singular}"
        else:
            base_response = f"Hay un total de {count} tarea{'s' if plural else ''} en el proyecto"
        
        if task_names:
            if count == 1:
                return f"{base_response}: \"{task_names[0]}\"."
            else:
                tasks_list = ", ".join([f"\"{name}\"" for name in task_names[:-1]]) + f" y \"{task_names[-1]}\""
                return f"{base_response}: {tasks_list}."
        else:
            return f"{base_response}."

    # =============================================================
    # Generador con GPT-4o-mini
    # =============================================================
    
    def answer(self, query: str, top_k: int = 6, temperature: float = 0.4, use_filters: bool = True, conversation_context: str = "") -> str:
        """Genera respuesta contextualizada con manejo robusto de errores.
        
        Args:
            query: Pregunta del usuario
            top_k: Número de resultados a recuperar
            temperature: Temperatura para el LLM
            use_filters: Si aplicar filtros automáticos
            conversation_context: Contexto de conversación previa para enriquecer la respuesta
        """
        try:
            # Validar entrada
            if not query or len(query.strip()) < 3:
                return "❓ Por favor, formula una pregunta más específica."
            
            logger.info(f"💬 Generando respuesta para: '{query[:50]}...'")
            query_lower = query.lower()
            
            # Detectar solicitud de informe
            is_report_request = any(word in query_lower for word in [
                'informe', 'reporte', 'report', 'generar informe', 'genera informe'
            ])
            
            # Detectar si quiere PDF
            is_pdf_request = 'pdf' in query_lower
            
            if is_report_request:
                sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
                if sprint_match:
                    sprint = f"Sprint {sprint_match.group(1)}"
                    
                    if is_pdf_request:
                        # Generar PDF con fecha en el nombre
                        from datetime import datetime
                        fecha = datetime.now().strftime("%Y%m%d_%H%M")
                        pdf_path = f"data/logs/informe_{sprint.replace(' ', '_').lower()}_{fecha}.pdf"
                        result = self.generate_report_pdf(sprint, pdf_path)
                        return result
                    else:
                        # Generar informe en texto
                        return self.generate_report(sprint)
                else:
                    return "⚠️ Por favor, especifica el sprint para generar el informe (ej: 'genera informe del Sprint 2' o 'genera informe PDF del Sprint 2')"
            
            # Detectar preguntas de conteo
            is_count_question = any(word in query_lower for word in [
                'cuántas', 'cuantas', 'cantidad', 'número', 'total', 'count'
            ])
            
            if is_count_question:
                return self._handle_count_question(query)
            
            # Detectar comparaciones
            is_comparison = any(word in query_lower for word in [
                'compar', 'vs', 'versus', 'diferencia'
            ])
            
            if is_comparison:
                sprint_matches = re.findall(r"sprint\s*(\d+)", query_lower)
                if len(sprint_matches) >= 2:
                    sprints = [f"Sprint {num}" for num in sprint_matches]
                    return self.compare_sprints(sprints)
                elif "sprint 1" in query_lower and "sprint 2" in query_lower:
                    return self.compare_sprints(["Sprint 1", "Sprint 2", "Sprint 3"])
            
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
                        f"• Completadas: {metrics['completadas']}"
                        )
            
            docs, metas = self.search(query, top_k=top_k, use_filters=use_filters)
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
            
            # Agregar contexto conversacional si existe
            if conversation_context:
                context = f"{conversation_context}\n\n{'='*50}\n\n{context}"

            from chatbot.prompts import SYSTEM_INSTRUCTIONS, RAG_CONTEXT_PROMPT
            
            system_prompt = SYSTEM_INSTRUCTIONS
            user_prompt = RAG_CONTEXT_PROMPT.format(
                system="",
                context=context,
                question=query
            )

            llm = self._ensure_llm()
            completion = llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )

            content = completion.choices[0].message.content
            return content.strip() if content else "No se pudo generar respuesta."

        except ConnectionError as e:
            logger.error(f"❌ Error de conexión con OpenAI: {e}")
            return ("❌ Error de conexión con el servicio de IA. "
                   "Por favor, verifica tu conexión a internet e intenta de nuevo.")
        except Exception as e:
            logger.error(f"❌ Error inesperado en answer(): {e}", exc_info=True)
            return f"❌ Ocurrió un error procesando tu consulta: {str(e)[:100]}"
