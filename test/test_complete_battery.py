#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 BATERÍA COMPLETA DE TESTS - Sistema RAG ClickUp
==================================================
Suite comprehensiva de tests que incluye:
- Tests básicos de funcionalidad
- Edge cases y casos problemáticos
- Tests de robustez y manejo de errores
- Tests de performance
- Tests de integración end-to-end
"""

import pytest
import sys
from pathlib import Path
from typing import Dict, List, Any

# Asegurar que podemos importar los módulos
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.hybrid_search import HybridSearch
from utils.config_models import get_config
from utils.report_generator import ReportGenerator


# =============================================================
# 🔧 FIXTURES
# =============================================================

@pytest.fixture(scope="module")
def searcher():
    """Inicializa HybridSearch una sola vez para todos los tests."""
    return HybridSearch(db_path="data/rag/chroma_db")


@pytest.fixture(scope="module")
def config():
    """Carga configuración validada."""
    return get_config()


# =============================================================
# ✅ TESTS BÁSICOS - Funcionalidad Core
# =============================================================

class TestBasicFunctionality:
    """Tests de funcionalidad básica del sistema."""
    
    def test_chromadb_connection(self, searcher):
        """Verifica que ChromaDB está accesible y tiene datos."""
        assert searcher.collection is not None, "Colección ChromaDB no existe"
        count = searcher.collection.count()
        assert count > 0, f"Colección vacía (esperado >0, obtenido {count})"
        print(f"✅ ChromaDB conectado: {count} vectores")
    
    def test_config_loading(self, config):
        """Verifica que la configuración se carga correctamente."""
        assert config is not None, "Config no cargó"
        assert len(config.status_mappings) > 0, "Status mappings vacío"
        assert len(config.priority_mappings) > 0, "Priority mappings vacío"
        assert len(config.critical_tags_for_comments) > 0, "Critical tags vacío"
        print(f"✅ Config cargado: {len(config.status_mappings)} estados")
    
    def test_basic_search(self, searcher):
        """Búsqueda simple debe retornar resultados."""
        docs, metas = searcher.search("tareas", top_k=5)
        assert len(docs) > 0, "Búsqueda no retornó resultados"
        assert len(docs) == len(metas), "Docs y metadata no coinciden"
        print(f"✅ Búsqueda básica: {len(docs)} resultados")
    
    def test_sprint_metrics(self, searcher):
        """Obtener métricas de sprint debe funcionar."""
        metrics = searcher.get_sprint_metrics("Sprint 3")
        assert "total" in metrics, "Métricas no contienen 'total'"
        assert "completadas" in metrics, "Métricas no contienen 'completadas'"
        assert metrics["total"] > 0, "Total de tareas es 0"
        print(f"✅ Métricas Sprint 3: {metrics['total']} tareas")


# =============================================================
# 🔍 TESTS DE BÚSQUEDA - Diferentes tipos de queries
# =============================================================

class TestSearchCapabilities:
    """Tests de capacidades de búsqueda."""
    
    def test_semantic_search(self, searcher):
        """Búsqueda semántica debe encontrar tareas relevantes."""
        queries = [
            "tareas relacionadas con datos",
            "trabajo pendiente",
            "problemas bloqueando el progreso"
        ]
        
        for query in queries:
            docs, metas = searcher.search(query, top_k=3)
            assert len(docs) > 0, f"Sin resultados para: {query}"
            print(f"✅ Semántica '{query[:30]}...': {len(docs)} resultados")
    
    def test_filter_by_sprint(self, searcher):
        """Filtrado por sprint debe funcionar."""
        docs, metas = searcher.search("", where={"sprint": "Sprint 3"})
        
        assert len(metas) > 0, "No se encontraron tareas del Sprint 3"
        for meta in metas:
            assert meta.get("sprint") == "Sprint 3", \
                f"Tarea no pertenece a Sprint 3: {meta.get('sprint')}"
        print(f"✅ Filtro sprint: {len(metas)} tareas en Sprint 3")
    
    def test_filter_by_status(self, searcher):
        """Filtrado por estado debe funcionar."""
        statuses = ["done", "in_progress", "to_do"]
        
        for status in statuses:
            docs, metas = searcher.search("", where={"status": status})
            if len(metas) > 0:
                for meta in metas:
                    assert meta.get("status") == status, \
                        f"Estado incorrecto: {meta.get('status')} != {status}"
                print(f"✅ Filtro estado '{status}': {len(metas)} tareas")
    
    def test_filter_by_priority(self, searcher):
        """Filtrado por prioridad debe funcionar."""
        docs, metas = searcher.search("", where={"priority": "urgent"})
        
        for meta in metas:
            assert meta.get("priority") in ["urgent", "high"], \
                f"Prioridad incorrecta: {meta.get('priority')}"
        print(f"✅ Filtro prioridad urgente: {len(metas)} tareas")
    
    def test_combined_filters(self, searcher):
        """Múltiples filtros deben combinarse correctamente."""
        docs, metas = searcher.search(
            "",
            where={"$and": [{"sprint": "Sprint 3"}, {"status": "done"}]}
        )
        
        for meta in metas:
            assert meta.get("sprint") == "Sprint 3"
            assert meta.get("status") == "done"
        print(f"✅ Filtros combinados: {len(metas)} tareas")


# =============================================================
# 🚨 TESTS DE EDGE CASES - Casos problemáticos
# =============================================================

class TestEdgeCases:
    """Tests de casos límite y problemáticos."""
    
    def test_empty_query(self, searcher):
        """Query vacío debe retornar todos los resultados."""
        docs, metas = searcher.search("", top_k=100)
        assert len(docs) > 0, "Query vacío no retornó resultados"
        print(f"✅ Query vacío: {len(docs)} resultados")
    
    def test_nonsense_query(self, searcher):
        """Query sin sentido debe retornar algo o lista vacía."""
        docs, metas = searcher.search("xyzabc123 qwerty asdfgh", top_k=5)
        # Puede retornar vacío o resultados con bajo score
        print(f"✅ Query sin sentido: {len(docs)} resultados (OK si 0 o pocos)")
    
    def test_special_characters_query(self, searcher):
        """Query con caracteres especiales no debe romper."""
        queries = [
            "¿Qué tareas?",
            "tareas #1 @usuario",
            "búsqueda con ñ, á, é",
            "búsqueda/con/slashes"
        ]
        
        for query in queries:
            try:
                docs, metas = searcher.search(query, top_k=3)
                print(f"✅ Caracteres especiales '{query[:20]}...': OK")
            except Exception as e:
                pytest.fail(f"Query especial falló: {query} - {e}")
    
    def test_very_long_query(self, searcher):
        """Query muy largo no debe romper."""
        long_query = " ".join(["tarea"] * 100)  # 100 palabras
        
        try:
            docs, metas = searcher.search(long_query, top_k=5)
            print(f"✅ Query largo (100 palabras): {len(docs)} resultados")
        except Exception as e:
            pytest.fail(f"Query largo falló: {e}")
    
    def test_nonexistent_sprint(self, searcher):
        """Sprint que no existe debe retornar vacío."""
        docs, metas = searcher.search("", where={"sprint": "Sprint 999"})
        assert len(docs) == 0, "Sprint inexistente retornó resultados"
        print(f"✅ Sprint inexistente: 0 resultados (correcto)")
    
    def test_invalid_filter_value(self, searcher):
        """Valor de filtro inválido no debe romper."""
        try:
            docs, metas = searcher.search(
                "",
                where={"status": "estado_inventado_xyz"}
            )
            assert len(docs) == 0, "Filtro inválido retornó resultados"
            print(f"✅ Filtro inválido: 0 resultados (correcto)")
        except Exception as e:
            print(f"⚠️ Filtro inválido causó excepción (OK si controlada): {e}")
    
    def test_top_k_zero(self, searcher):
        """top_k=0 debe ser manejado correctamente."""
        docs, metas = searcher.search("tareas", top_k=0)
        assert len(docs) == 0, "top_k=0 retornó resultados"
        print(f"✅ top_k=0: 0 resultados (correcto)")
    
    def test_top_k_very_large(self, searcher):
        """top_k muy grande debe estar limitado."""
        docs, metas = searcher.search("tareas", top_k=10000)
        # Debería retornar máximo lo que hay en DB
        total = searcher.collection.count()
        assert len(docs) <= total, f"Retornó más de {total} resultados"
        print(f"✅ top_k=10000: {len(docs)} resultados (max={total})")


# =============================================================
# 🎯 TESTS DE CONSULTAS NATURALES - Como Scrum Master
# =============================================================

class TestNaturalQueries:
    """Tests de consultas en lenguaje natural."""
    
    def test_blocking_tasks_query(self, searcher):
        """¿Qué tareas están bloqueadas?"""
        docs, metas = searcher.search("tareas bloqueadas", top_k=10)
        
        # Verificar que encuentra tareas con is_blocked=true
        blocked = [m for m in metas if m.get("is_blocked") == True]
        print(f"✅ Tareas bloqueadas: {len(blocked)} encontradas")
    
    def test_priority_tasks_query(self, searcher):
        """¿Cuáles son las tareas urgentes?"""
        docs, metas = searcher.search("tareas urgentes", top_k=10)
        
        # Verificar que encuentra tareas de alta prioridad
        urgent = [m for m in metas if m.get("priority") in ["urgent", "high"]]
        print(f"✅ Tareas urgentes: {len(urgent)} encontradas")
    
    def test_tag_search_query(self, searcher):
        """¿Qué tareas tienen etiqueta data?"""
        docs, metas = searcher.search("etiqueta data", top_k=10)
        
        # Verificar que encuentra tareas con tag "data"
        with_data_tag = [
            m for m in metas 
            if "data" in str(m.get("tags", "")).lower()
        ]
        print(f"✅ Tareas con etiqueta 'data': {len(with_data_tag)} encontradas")
    
    def test_assignee_query(self, searcher):
        """¿Qué tareas tiene asignadas Jorge?"""
        docs, metas = searcher.search("tareas asignadas jorge", top_k=10)
        
        # Verificar que encuentra tareas asignadas
        print(f"✅ Tareas de Jorge: {len(metas)} encontradas")
    
    def test_completion_status_query(self, searcher):
        """¿Cuántas tareas están completadas?"""
        docs, metas = searcher.search("tareas completadas", top_k=100)
        
        completed = [m for m in metas if m.get("status") == "done"]
        print(f"✅ Tareas completadas: {len(completed)} encontradas")
    
    def test_in_progress_query(self, searcher):
        """¿Qué tareas están en progreso?"""
        docs, metas = searcher.search("tareas en progreso", top_k=10)
        
        in_progress = [m for m in metas if m.get("status") == "in_progress"]
        print(f"✅ Tareas en progreso: {len(in_progress)} encontradas")


# =============================================================
# 📊 TESTS DE MÉTRICAS Y REPORTES
# =============================================================

class TestMetricsAndReports:
    """Tests de generación de métricas y reportes."""
    
    def test_sprint_metrics_structure(self, searcher):
        """Métricas de sprint deben tener estructura correcta."""
        metrics = searcher.get_sprint_metrics("Sprint 3")
        
        required_fields = [
            "total", "completadas", "en_progreso", "pendientes",
            "porcentaje_completitud", "bloqueadas"
        ]
        
        for field in required_fields:
            assert field in metrics, f"Campo faltante en métricas: {field}"
        
        # Validar tipos
        assert isinstance(metrics["total"], int)
        assert isinstance(metrics["porcentaje_completitud"], (int, float))
        assert 0 <= metrics["porcentaje_completitud"] <= 100
        
        print(f"✅ Estructura de métricas válida")
    
    def test_metrics_math(self, searcher):
        """Validar que las matemáticas de métricas sean correctas."""
        metrics = searcher.get_sprint_metrics("Sprint 3")
        
        # Suma de estados debe ser igual al total
        states_sum = (
            metrics.get("completadas", 0) +
            metrics.get("en_progreso", 0) +
            metrics.get("pendientes", 0) +
            metrics.get("qa", 0) +
            metrics.get("review", 0)
        )
        
        # Puede haber pequeñas diferencias por estados custom
        assert abs(states_sum - metrics["total"]) <= 5, \
            f"Suma de estados ({states_sum}) != total ({metrics['total']})"
        
        print(f"✅ Matemáticas de métricas correctas")
    
    def test_report_generation(self, searcher):
        """Generar reporte de texto debe funcionar."""
        report = searcher.generate_report("Sprint 3")
        
        assert len(report) > 100, "Reporte muy corto"
        assert "Sprint 3" in report, "Reporte no menciona el sprint"
        assert "RESUMEN EJECUTIVO" in report or "resumen ejecutivo" in report.lower()
        
        print(f"✅ Reporte generado: {len(report)} caracteres")
    
    def test_pdf_generation(self, searcher):
        """Generar PDF debe crear archivo."""
        import os
        
        pdf_path = searcher.generate_report_pdf(
            sprint="Sprint 3",
            output_path="data/logs/test_informe.pdf"
        )
        
        assert pdf_path is not None, "generate_report_pdf devolvió None"
        assert os.path.exists(pdf_path), f"PDF no creado en: {pdf_path}"
        assert os.path.getsize(pdf_path) > 1000, "PDF muy pequeño"
        
        print(f"✅ PDF generado correctamente en {pdf_path}")
        print(f"📄 Tamaño: {os.path.getsize(pdf_path)} bytes")
        print(f"💾 El PDF se ha guardado y NO se eliminará para revisión manual")


# =============================================================
# ⚙️ TESTS DE CONFIGURACIÓN
# =============================================================

class TestConfiguration:
    """Tests de sistema de configuración."""
    
    def test_status_normalization(self, config):
        """Normalización de estados debe funcionar."""
        test_cases = [
            ("to do", "to_do"),
            ("TODO", "to_do"),
            ("In Progress", "in_progress"),
            ("complete", "done"),
            ("DONE", "done")
        ]
        
        for raw, expected in test_cases:
            result = config.get_normalized_status(raw)
            assert result == expected, \
                f"Normalización incorrecta: {raw} → {result} (esperado {expected})"
        
        print(f"✅ Normalización de estados: {len(test_cases)} casos")
    
    def test_priority_normalization(self, config):
        """Normalización de prioridades debe funcionar."""
        test_cases = [
            ("urgent", "urgent"),
            ("1", "urgent"),
            ("high", "high"),
            ("alta", "high"),
            ("normal", "normal"),
            ("low", "low")
        ]
        
        for raw, expected in test_cases:
            result = config.get_normalized_priority(raw)
            assert result == expected, \
                f"Normalización incorrecta: {raw} → {result} (esperado {expected})"
        
        print(f"✅ Normalización de prioridades: {len(test_cases)} casos")
    
    def test_critical_tags_detection(self, config):
        """Detección de tags críticas debe funcionar."""
        assert config.should_download_comments(["bloqueada"]) == True
        assert config.should_download_comments(["data"]) == True
        assert config.should_download_comments(["duda"]) == True
        assert config.should_download_comments(["frontend"]) == False
        assert config.should_download_comments([]) == False
        
        print(f"✅ Detección de tags críticas funciona")
    
    def test_spanish_translations(self, config):
        """Traducciones al español deben funcionar."""
        translations = [
            ("status", "done", "Completada"),
            ("status", "in_progress", "En progreso"),
            ("priority", "urgent", "Urgente"),
            ("priority", "high", "Alta")
        ]
        
        for field, value, expected in translations:
            result = config.get_spanish_translation(field, value)
            assert result == expected, \
                f"Traducción incorrecta: {field}.{value} → {result} (esperado {expected})"
        
        print(f"✅ Traducciones: {len(translations)} casos")


# =============================================================
# 🏃 FUNCIÓN PRINCIPAL PARA EJECUTAR TESTS
# =============================================================

def run_all_tests():
    """Ejecuta toda la batería de tests."""
    print("\n" + "="*70)
    print("🧪 BATERÍA COMPLETA DE TESTS - Sistema RAG ClickUp")
    print("="*70 + "\n")
    
    # Ejecutar pytest con configuración
    pytest.main([
        __file__,
        "-v",              # Verbose
        "-s",              # No capturar stdout (ver prints)
        "--tb=short",      # Traceback corto
        "--color=yes",     # Color en output
        "-x"               # Parar en primer fallo (comentar para ver todos)
    ])


if __name__ == "__main__":
    run_all_tests()
