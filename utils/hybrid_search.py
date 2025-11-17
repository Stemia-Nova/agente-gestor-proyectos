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
import json
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

    def _ensure_llm(self):
        """Inicializa el cliente OpenAI."""
        if self._llm is None:
            logger.info("🤖 Inicializando cliente OpenAI...")
            self._llm = OpenAI()
            logger.info("✅ Cliente OpenAI inicializado correctamente.")
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
    
    def _handle_count_question(self, query: str) -> Optional[str]:
        """Maneja preguntas de conteo con filtros combinados (sprint + estado + persona).
        
        ESTRATEGIA HÍBRIDA PROFESIONAL:
        - Casos FRECUENTES + CRÍTICOS (tareas con filtros) → Optimización manual (rápido, determinístico)
        - Casos RAROS o COMPLEJOS (sprints, personas, agregaciones) → Delegar al LLM (flexible, inteligente)
        
        Retorna:
        - str: Respuesta directa si puede manejar el caso
        - None: Delegar al LLM con contexto enriquecido
        """
        query_lower = query.lower()
        
        # === DELEGAR AL LLM: Preguntas sobre sprints/entidades únicas ===
        # El LLM tiene acceso a aggregate_by_field() y puede razonar mejor
        if any(pattern in query_lower for pattern in [
            "cuántos sprints", "cuantos sprints", "número de sprints",
            "cantidad de sprints", "cuántas iteraciones", "cuantas iteraciones",
            "how many sprints", "number of sprints"
        ]):
            logger.info("🔄 Delegando conteo de sprints al LLM (caso raro, mejor con contexto)")
            return None  # → El LLM usará aggregate_by_field("sprint")
        
        # Detectar negaciones que requieren lógica compleja
        negation_patterns = [
            r'\bno\s+(?:\w+\s+)?(completada|finalizad|terminad)',
            r'\bsin\s+\w+',
            r'except',
            r'\bmenos\b',
            r'\bfuera\s+de\b'
        ]
        has_negation = any(re.search(pattern, query_lower) for pattern in negation_patterns)
        
        # Para negaciones simples sobre estados, podemos manejarlo aquí
        if has_negation and ("completada" in query_lower or "finalizad" in query_lower or "terminad" in query_lower):
            # "¿Cuántas NO completadas?" = total - completadas
            total = self.count_tasks()
            completadas = self.count_tasks(where={"status": "Completada"})
            no_completadas = total - completadas
            return f"Hay {no_completadas} tareas no completadas (de un total de {total} tareas)."
        elif has_negation:
            return None  # Otras negaciones → delegar al LLM
        
        # === PASO 1: Detectar sprint y obtener tareas ===
        sprint_match = re.search(r"(?:del|en el|para el|de|en)?\s*sprint\s*(\d+)", query_lower)
        sprint_filter = None
        sprint_text = None
        
        if sprint_match:
            sprint_num = sprint_match.group(1)
            sprint_filter = {"sprint": f"Sprint {sprint_num}"}
            sprint_text = f"Sprint {sprint_num}"
        elif "actual" in query_lower or "corriente" in query_lower:
            sprint_filter = {"sprint": "Sprint 3"}
            sprint_text = "Sprint 3"
        
        # Obtener todas las metadatas del sprint (o todas si no hay sprint)
        try:
            result = self.collection.get(
                where=cast(Any, sprint_filter) if sprint_filter else None,
                limit=10000,
                include=cast(Any, ['metadatas'])
            )
            all_metas = result.get('metadatas') or []
        except Exception as e:
            logger.error(f"Error obteniendo metadatas: {e}")
            return None
        
        if not all_metas:
            return "No hay tareas que coincidan con los filtros especificados."
        
        # === PASO 2: Aplicar TODOS los filtros en Python ===
        filtered_metas = all_metas
        filter_descriptions = []  # Para describir los filtros aplicados
        
        # Filtro por persona
        person_detected = None
        if "jorge" in query_lower:
            person_detected = "Jorge"
            filtered_metas = [m for m in filtered_metas if "Jorge" in m.get('assignees', '')]
            filter_descriptions.append(f"asignadas a {person_detected}")
        elif "laura" in query_lower:
            person_detected = "Laura"
            filtered_metas = [m for m in filtered_metas if "Laura" in m.get('assignees', '')]
            filter_descriptions.append(f"asignadas a {person_detected}")
        
        # Filtro por estado (ORDEN IMPORTA: más específico primero)
        if "completadas" in query_lower or "finalizadas" in query_lower or "terminad" in query_lower:
            filtered_metas = [m for m in filtered_metas if m.get('status') == "Completada"]
            filter_descriptions.append("completadas")
        elif "curso" in query_lower or "en progreso" in query_lower:
            filtered_metas = [m for m in filtered_metas if m.get('status') == "En progreso"]
            filter_descriptions.append("en progreso")
        elif "pendiente" in query_lower or "por hacer" in query_lower or "quedan" in query_lower or "falta" in query_lower:
            filtered_metas = [m for m in filtered_metas if m.get('status') == "Pendiente"]
            filter_descriptions.append("pendientes")
        elif "bloqueada" in query_lower and "etiqueta" not in query_lower:
            filtered_metas = [m for m in filtered_metas if m.get('is_blocked') == True]
            filter_descriptions.append("bloqueadas")
        elif " qa" in query_lower or "testing" in query_lower:
            filtered_metas = [m for m in filtered_metas if m.get('status') == "qa"]
            filter_descriptions.append("en QA")
        elif "review" in query_lower or "revisión" in query_lower:
            filtered_metas = [m for m in filtered_metas if m.get('status') == "review"]
            filter_descriptions.append("en revisión")
        
        # Filtros especiales (dudas, comentarios, subtareas)
        if "duda" in query_lower:
            filtered_metas = [m for m in filtered_metas if m.get('has_doubts') == True]
            # Si es pregunta genérica sobre existencia de dudas, responder directamente
            if any(word in query_lower for word in ["hay ", "existe", "tiene alguna", "alguna tarea"]):
                count = len(filtered_metas)
                if count > 0:
                    task_details = []
                    for m in filtered_metas[:5]:
                        name = m.get('name', 'Sin nombre')
                        has_comments = m.get('has_comments', False)
                        comments_count = m.get('comments_count', 0)
                        if has_comments:
                            task_details.append(f'"{name}" ({comments_count} comentarios)')
                        else:
                            task_details.append(f'"{name}" (sin comentarios)')
                    
                    if count == 1:
                        return f"Sí, hay {count} tarea con dudas: {task_details[0]}."
                    else:
                        tasks_list = ", ".join(task_details)
                        return f"Sí, hay {count} tareas con dudas: {tasks_list}."
                else:
                    return "No hay tareas con dudas."
        
        if "comentario" in query_lower:
            # Buscar tareas con comentarios (SOLO ACTIVAS, no completadas)
            filtered_metas = [m for m in filtered_metas if m.get('has_comments') == True and m.get('status') != "Completada"]
            # Si es pregunta genérica sobre existencia de comentarios, responder directamente
            if any(word in query_lower for word in ["hay ", "existe", "tiene alguna", "alguna tarea"]):
                count = len(filtered_metas)
                if count > 0:
                    # Construir respuesta con info de estado
                    task_details = []
                    for m in filtered_metas[:5]:
                        name = m.get('name', 'Sin nombre')
                        status = m.get('status', 'sin estado')
                        task_details.append(f'"{name}" ({status})')
                    
                    if count == 1:
                        return f"Sí, hay {count} tarea activa con comentarios: {task_details[0]}."
                    else:
                        tasks_list = ", ".join(task_details)
                        return f"Sí, hay {count} tareas activas con comentarios: {tasks_list}."
                else:
                    return "No hay tareas activas con comentarios (se excluyen las completadas)."
        
        if "subtarea" in query_lower:
            # Buscar tareas con subtareas
            filtered_metas = [m for m in filtered_metas if m.get('has_subtasks') == True]
            # Si es pregunta genérica sobre existencia de subtareas, responder directamente
            if any(word in query_lower for word in ["hay ", "existe", "tiene alguna", "alguna tarea"]):
                count = len(filtered_metas)
                if count > 0:
                    task_names = [m.get('name', 'Sin nombre') for m in filtered_metas[:5]]
                    if count == 1:
                        return f"Sí, hay {count} tarea con subtareas: \"{task_names[0]}\"."
                    else:
                        tasks_list = ", ".join([f"\"{name}\"" for name in task_names])
                        return f"Sí, hay {count} tareas con subtareas: {tasks_list}."
                else:
                    return "No hay tareas con subtareas."
        
        # Filtro por etiquetas/tags (tags es string "data|hotfix")
        if "etiqueta" in query_lower or "tag" in query_lower:
            for tag_name in ["data", "hotfix", "bloqueada", "blocked"]:
                if tag_name in query_lower:
                    filtered_metas = [m for m in filtered_metas if tag_name in m.get('tags', '').lower()]
                    filter_descriptions.append(f'con etiqueta "{tag_name}"')
                    break
        
        # === PASO 3: Contar y construir respuesta ===
        count = len(filtered_metas)
        
        # Obtener nombres de tareas (máximo 5) con info adicional para bloqueadas
        task_names = []
        for m in filtered_metas[:5]:
            name = m.get('name', 'Sin nombre')
            if m.get('is_blocked'):
                details = []
                if m.get('has_comments'):
                    details.append(f"{m.get('comments_count', 0)} comentarios")
                if m.get('has_subtasks'):
                    details.append(f"{m.get('subtasks_count', 0)} subtareas")
                if m.get('has_doubts'):
                    details.append("con dudas")
                
                if details:
                    task_names.append(f'"{name}" ({", ".join(details)})')
                else:
                    task_names.append(f'"{name}"')
            else:
                task_names.append(name)
        
        # Construir descripción del contexto
        context_parts = []
        if sprint_text:
            context_parts.append(f"en el {sprint_text}")
        if filter_descriptions:
            context_parts.append(" ".join(filter_descriptions))
        
        context_str = ", ".join(context_parts) if context_parts else "en total"
        
        # Construir respuesta
        plural = count != 1
        
        if context_str == "en total":
            base_response = f"Hay {count} tarea{'s' if plural else ''} en total"
        else:
            if plural:
                base_response = f"Hay {count} tareas {context_str}"
            else:
                # Ajustar palabras al singular
                context_str_singular = (context_str
                                       .replace("completadas", "completada")
                                       .replace("pendientes", "pendiente")
                                       .replace("bloqueadas", "bloqueada")
                                       .replace("asignadas", "asignada"))
                base_response = f"Hay {count} tarea {context_str_singular}"
        
        # Agregar nombres de tareas si hay pocas
        if task_names and count <= 5:
            if count == 1:
                return f"{base_response}: {task_names[0]}."
            elif count == 2:
                return f"{base_response}: {task_names[0]} y {task_names[1]}."
            else:
                tasks_list = ", ".join(task_names[:-1]) + f" y {task_names[-1]}"
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
                'informe', 'reporte', 'report', 'generar informe', 'genera informe', 'dame un informe', 'quiero un informe'
            ])
            
            # Detectar si quiere explícitamente PDF o texto
            is_pdf_request = 'pdf' in query_lower
            is_text_request = any(word in query_lower for word in ['texto', 'en texto', 'textual', 'pantalla'])
            
            if is_report_request:
                sprint_match = re.search(r"sprint\s*(\d+)", query_lower)
                if sprint_match:
                    sprint = f"Sprint {sprint_match.group(1)}"
                    
                    # Prioridad: 
                    # 1. Si pide explícitamente texto → generar texto
                    # 2. Si pide explícitamente PDF → generar PDF
                    # 3. Por defecto (informe formal) → generar PDF + mensaje amigable
                    
                    if is_text_request and not is_pdf_request:
                        # Usuario quiere ver el informe en pantalla
                        return self.generate_report(sprint)
                    else:
                        # Generar PDF (por defecto o explícito)
                        from datetime import datetime
                        fecha = datetime.now().strftime("%Y%m%d_%H%M")
                        pdf_path = f"data/logs/informe_{sprint.replace(' ', '_').lower()}_{fecha}.pdf"
                        result_path = self.generate_report_pdf(sprint, pdf_path)
                        
                        if result_path:
                            # Mensaje amigable con enlace al PDF
                            return (
                                f"📄 **Informe generado exitosamente**\n\n"
                                f"✅ Sprint: {sprint}\n"
                                f"📁 Archivo: `{result_path}`\n\n"
                                f"💡 **Resumen rápido:**\n"
                                f"• Puedes abrir el PDF para ver el informe completo profesional\n"
                                f"• Si prefieres verlo aquí, pregunta: 'muestra informe del {sprint} en texto'\n\n"
                                f"El PDF incluye: métricas, tareas detalladas, bloqueos críticos y recomendaciones."
                            )
                        else:
                            return f"❌ Error al generar PDF para {sprint}"
                else:
                    return "⚠️ Por favor, especifica el sprint para generar el informe (ej: 'quiero un informe del Sprint 3' o 'genera informe PDF del Sprint 2')"
            
            # Clasificar intención usando LLM (más dinámico que reglas hardcodeadas)
            from utils.intent_classifier import get_classifier
            
            classifier = get_classifier()
            intent_result = classifier.classify(query)
            intent = intent_result.get("intent", "GENERAL_QUERY")
            confidence = intent_result.get("confidence", 0.0)
            
            logger.info(f"🎯 Intención detectada: {intent} (confianza: {confidence:.2f})")
            
            # Si la intención es COUNT_TASKS o CHECK_EXISTENCE, usar el handler optimizado
            if intent in ["COUNT_TASKS", "CHECK_EXISTENCE"]:
                count_result = self._handle_count_question(query)
                # Si retorna None, significa que requiere LLM para filtros complejos o conteos de entidades
                if count_result is not None:
                    return count_result
                
                # === CASO DELEGADO: Conteo de entidades únicas (sprints, personas, estados) ===
                # Detectar si es pregunta sobre sprints/entidades (no tareas)
                is_sprint_count = any(pattern in query_lower for pattern in [
                    "cuántos sprints", "cuantos sprints", "número de sprints",
                    "cantidad de sprints", "how many sprints"
                ])
                
                if is_sprint_count:
                    logger.info("🧠 Delegando conteo de sprints al LLM con contexto completo")
                    try:
                        # Obtener TODAS las metadatas
                        result = self.collection.get(
                            include=cast(Any, ["metadatas"]),
                            limit=10000
                        )
                        all_metas = result.get('metadatas', [])
                        
                        if not all_metas:
                            return "No hay tareas en la base de datos."
                        
                        # Construir contexto con información de sprints
                        sprint_info = {}
                        for m in all_metas:
                            sprint = m.get('sprint', 'Sin Sprint')
                            if sprint not in sprint_info:
                                sprint_info[sprint] = {
                                    'count': 0,
                                    'completadas': 0,
                                    'pendientes': 0,
                                    'en_progreso': 0
                                }
                            sprint_info[sprint]['count'] += 1
                            status = m.get('status', '')
                            if status == 'Completada':
                                sprint_info[sprint]['completadas'] += 1
                            elif status == 'Pendiente':
                                sprint_info[sprint]['pendientes'] += 1
                            elif status == 'En progreso':
                                sprint_info[sprint]['en_progreso'] += 1
                        
                        # Construir contexto enriquecido para el LLM
                        context_parts = []
                        for sprint, info in sorted(sprint_info.items()):
                            context_parts.append(
                                f"• {sprint}: {info['count']} tareas "
                                f"({info['completadas']} completadas, {info['en_progreso']} en progreso, "
                                f"{info['pendientes']} pendientes)"
                            )
                        
                        context = "\n".join(context_parts)
                        
                        # Generar respuesta con LLM
                        from chatbot.prompts import SYSTEM_INSTRUCTIONS, RAG_CONTEXT_PROMPT
                        system_prompt = SYSTEM_INSTRUCTIONS
                        user_prompt = RAG_CONTEXT_PROMPT.format(
                            system="",
                            context=f"Información de sprints en el proyecto:\n\n{context}",
                            question=query
                        )
                        
                        llm = self._ensure_llm()
                        completion = llm.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            temperature=0.2,  # Temperatura baja para respuestas determinísticas en conteos
                        )
                        content = completion.choices[0].message.content
                        return content.strip() if content else "No se pudo generar respuesta."
                    
                    except Exception as e:
                        logger.error(f"Error manejando conteo de sprints con LLM: {e}")
                        return f"⚠️ Error al procesar la consulta: {str(e)}"
                
                # Si es None pero NO es conteo de sprints, continúa con búsqueda normal
                # IMPORTANTE: Aumentar top_k para consultas con personas
                # porque necesitamos más contexto para filtrar correctamente
                person_detected = None
                for name in ["jorge", "laura", "aguadero", "pérez", "lopez"]:
                    if name in query_lower:
                        person_detected = name.capitalize()
                        break
                
                if person_detected:
                    # Buscar TODAS las tareas de esta persona
                    # ChromaDB no soporta $contains, así que obtenemos todas y filtramos
                    try:
                        result = self.collection.get(
                            include=cast(Any, ["metadatas"])
                        )
                        all_metas = result.get('metadatas', [])
                        
                        # Filtrar por persona en Python
                        metas = [m for m in all_metas if person_detected in m.get('assignees', '')]
                        
                        if not metas:
                            return f"No se encontraron tareas asignadas a {person_detected}."
                        
                        # Construir contexto enriquecido con todas las tareas encontradas
                        context_parts = []
                        for m in metas:
                            status_spanish = m.get('status_spanish', m.get('status', 'sin estado'))
                            blocked = "⚠️ BLOQUEADA" if m.get('is_blocked') else ""
                            assignees = m.get('assignees', 'sin asignar')
                            priority = m.get('priority', 'sin prioridad')
                            sprint = m.get('sprint', 'sin sprint')
                            subtasks = m.get('subtasks_count', 0)
                            comments = m.get('comments_count', 0)
                            context_parts.append(
                                f"• {m.get('name', 'sin nombre')} - {status_spanish} {blocked}\n"
                                f"  Asignado a: {assignees} | Sprint: {sprint} | Prioridad: {priority} | "
                                f"Subtareas: {subtasks} | Comentarios: {comments}"
                            )
                        
                        context = "\n\n".join(context_parts)
                        
                        # Generar respuesta con LLM usando la pregunta ORIGINAL
                        # (para que responda correctamente a "¿Cuántas completadas tiene Jorge?")
                        from chatbot.prompts import SYSTEM_INSTRUCTIONS, RAG_CONTEXT_PROMPT
                        system_prompt = SYSTEM_INSTRUCTIONS
                        user_prompt = RAG_CONTEXT_PROMPT.format(
                            system="",
                            context=context,
                            question=query  # Query original, no search_query
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
                    except Exception as e:
                        logger.error(f"Error buscando tareas de {person_detected}: {e}")
                        # Fallback a None para que use búsqueda normal
                        return None
            
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
            
            # Detectar solicitud de métricas (pero NO si pregunta por subtareas)
            is_metrics_request = ("progreso" in query_lower or "métrica" in query_lower or "resumen" in query_lower)
            is_subtask_question = ("subtarea" in query_lower or "sub-tarea" in query_lower)
            
            if is_metrics_request and not is_subtask_question:
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
            
            # Detectar si hay un nombre de tarea específico entre comillas
            task_name_match = re.search(r'"([^"]+)"', query)
            
            if task_name_match:
                # Buscar específicamente esa tarea por nombre
                task_name = task_name_match.group(1)
                logger.info(f"🔍 Búsqueda específica de tarea: {task_name}")
                
                # Obtener todas las tareas y buscar por coincidencia de nombre
                result = self.collection.get(include=cast(Any, ["metadatas"]))
                all_metas = result.get('metadatas', [])
                
                # Buscar coincidencia exacta o parcial
                matching_metas = [m for m in all_metas if task_name.lower() in m.get('name', '').lower()]
                
                if matching_metas:
                    metas = matching_metas[:top_k]
                    docs = [m.get('name', '') for m in metas]
                    logger.info(f"✅ Encontradas {len(metas)} tareas que coinciden")
                else:
                    # Si no hay coincidencia, usar búsqueda semántica normal
                    docs, metas = self.search(query, top_k=top_k, use_filters=use_filters)
            else:
                # Búsqueda semántica normal
                docs, metas = self.search(query, top_k=top_k, use_filters=use_filters)
            
            if not docs:
                from chatbot.prompts import RAG_NO_RESULTS
                return RAG_NO_RESULTS

            context_parts = []
            for m in metas[:top_k]:
                status_spanish = m.get('status_spanish', m.get('status', 'sin estado'))
                
                # Indicadores críticos para PM
                indicators = []
                if m.get('is_blocked'):
                    indicators.append("⚠️ BLOQUEADA")
                if m.get('has_doubts'):
                    indicators.append("🤔 CON DUDAS")
                if m.get('is_overdue'):
                    indicators.append("⏰ VENCIDA")
                if m.get('is_pending_review'):
                    indicators.append("👀 PENDIENTE REVISIÓN")
                
                indicators_str = " ".join(indicators)
                
                # Información básica
                task_info = [
                    f"• {m.get('name', 'sin nombre')} - {status_spanish} {indicators_str}",
                    f"  Sprint: {m.get('sprint', 'N/A')} | Prioridad: {m.get('priority', 'sin prioridad')}",
                    f"  Asignado: {m.get('assignees', 'sin asignar')}"
                ]
                
                # Agregar subtareas si existen (contenido completo con estado)
                if m.get('has_subtasks'):
                    subtasks_count = m.get('subtasks_count', 0)
                    subtasks_raw = m.get('subtasks', '[]')
                    
                    # Parsear y analizar subtareas
                    try:
                        subtasks = json.loads(subtasks_raw) if isinstance(subtasks_raw, str) else subtasks_raw
                        if subtasks:
                            # Contar estados de subtareas
                            completed = sum(1 for st in subtasks if isinstance(st, dict) and st.get('status', {}).get('status', '').lower() == 'completada')
                            blocked = sum(1 for st in subtasks if isinstance(st, dict) and st.get('status', {}).get('status', '').lower() == 'blocked')
                            
                            status_info = f"{completed}/{subtasks_count} completadas"
                            if blocked > 0:
                                status_info += f", {blocked} bloqueadas ⚠️"
                            
                            task_info.append(f"  📋 {subtasks_count} subtarea(s): {status_info}")
                            task_info.append(f"  Subtareas:")
                            for st in subtasks[:5]:  # Máximo 5 subtareas
                                if isinstance(st, dict):
                                    st_name = st.get('name', 'Sin nombre')
                                    st_status = st.get('status', {})
                                    st_status_str = st_status.get('status', 'Pendiente') if isinstance(st_status, dict) else 'Pendiente'
                                    task_info.append(f"    • {st_name} [{st_status_str}]")
                                else:
                                    task_info.append(f"    • {str(st)}")
                    except Exception as e:
                        logger.warning(f"Error parseando subtareas: {e}")
                        task_info.append(f"  📋 {subtasks_count} subtarea(s)")
                
                # Agregar tags si existen
                tags = m.get('tags', '')
                if tags:
                    task_info.append(f"  🏷️ Tags: {tags}")
                
                # CRÍTICO: Siempre mostrar comentarios si existen (pueden contener info importante)
                if m.get('has_comments'):
                    comments_count = m.get('comments_count', 0)
                    task_info.append(f"  💬 {comments_count} comentario(s)")
                
                # CRÍTICO: Siempre mostrar si tiene dudas
                if m.get('has_doubts'):
                    has_comments = m.get('has_comments', False)
                    if has_comments:
                        task_info.append(f"  ❓ Tiene dudas (revisar comentarios para posible resolución)")
                    else:
                        task_info.append(f"  ❓ Tiene dudas SIN comentarios (requiere atención)")
                
                context_parts.append("\n".join(task_info))
            
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
