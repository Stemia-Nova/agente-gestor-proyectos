#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_models.py - Modelos Pydantic para configuración de ClickUp
-----------------------------------------------------------------
Validación de tipos y estructura para clickup_mappings.json

Ventajas:
- Validación automática al cargar
- Type hints para IDE autocomplete
- Errores claros si hay typos o campos faltantes
- Conversión automática de tipos
"""

from typing import Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
import json


class ClickUpConfig(BaseModel):
    """Configuración completa de mapeos de ClickUp.
    
    Esta clase valida la estructura del archivo clickup_mappings.json
    y proporciona acceso type-safe a todos los mapeos.
    """
    
    status_mappings: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Mapeo de estados: 'to_do' → ['to do', 'todo', 'por hacer']"
    )
    
    priority_mappings: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Mapeo de prioridades: 'urgent' → ['urgent', 'urgente', '1']"
    )
    
    critical_tags_for_comments: List[str] = Field(
        default_factory=list,
        description="Tags que requieren descarga de comentarios"
    )
    
    spanish_translations: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Traducciones al español: {'status': {'done': 'Completada'}}"
    )
    
    class Config:
        extra = "allow"  # Permitir campos de metadatos como version/description
        
    @field_validator('status_mappings', 'priority_mappings')
    @classmethod
    def validate_mappings(cls, v: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Validar que los mapeos no estén vacíos y tengan estructura correcta."""
        for key, variants in v.items():
            if not isinstance(variants, list):
                raise ValueError(f"'{key}' debe ser una lista, no {type(variants)}")
            if not variants:
                raise ValueError(f"'{key}' no puede tener una lista vacía")
        return v
    
    @field_validator('critical_tags_for_comments')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validar que los tags sean strings no vacíos."""
        if not all(isinstance(tag, str) and tag.strip() for tag in v):
            raise ValueError("Todos los tags deben ser strings no vacíos")
        return [tag.strip().lower() for tag in v]  # Normalizar a lowercase
    
    def get_normalized_status(self, raw_status: str) -> str:
        """Obtener estado normalizado desde raw status de ClickUp.
        
        Args:
            raw_status: Estado crudo de ClickUp (e.g., "In Progress", "doing")
            
        Returns:
            Estado normalizado (e.g., "in_progress") o "unknown"
        """
        raw_lower = raw_status.strip().lower()
        for normalized, variants in self.status_mappings.items():
            if raw_lower in [v.lower() for v in variants]:
                return normalized
        return "unknown"
    
    def get_normalized_priority(self, raw_priority: str) -> str:
        """Obtener prioridad normalizada desde raw priority de ClickUp.
        
        Args:
            raw_priority: Prioridad cruda (e.g., "urgent", "1", "alta")
            
        Returns:
            Prioridad normalizada (e.g., "urgent") o "unknown"
        """
        raw_lower = str(raw_priority).strip().lower()
        for normalized, variants in self.priority_mappings.items():
            if raw_lower in [str(v).lower() for v in variants]:
                return normalized
        return "unknown"
    
    def get_spanish_translation(self, field: str, value: str) -> str:
        """Obtener traducción al español.
        
        Args:
            field: Campo a traducir ("status" o "priority")
            value: Valor normalizado (e.g., "done", "urgent")
            
        Returns:
            Traducción en español o el valor original si no existe
        """
        translations = self.spanish_translations.get(field, {})
        return translations.get(value, value)
    
    def should_download_comments(self, tags: List[str]) -> bool:
        """Determinar si una tarea necesita descarga de comentarios por sus tags.
        
        Args:
            tags: Lista de tags de la tarea
            
        Returns:
            True si algún tag es crítico y requiere comentarios
        """
        if not tags:
            return False
        
        tags_lower = [tag.lower() for tag in tags]
        return any(
            critical_tag in tag_lower 
            for tag_lower in tags_lower 
            for critical_tag in self.critical_tags_for_comments
        )


def load_config(config_path: Optional[Path] = None) -> ClickUpConfig:
    """Cargar y validar configuración desde JSON.
    
    Args:
        config_path: Ruta al archivo de configuración. Si None, usa ruta por defecto.
        
    Returns:
        ClickUpConfig validado
        
    Raises:
        FileNotFoundError: Si el archivo no existe
        ValidationError: Si la estructura JSON es inválida
    """
    if config_path is None:
        # Ruta por defecto
        root = Path(__file__).resolve().parents[1]
        config_path = root / "data" / "rag" / "config" / "clickup_mappings.json"
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"Archivo de configuración no encontrado: {config_path}\n"
            f"Crea el archivo o usa valores por defecto."
        )
    
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    return ClickUpConfig(**data)


def get_default_config() -> ClickUpConfig:
    """Obtener configuración por defecto con valores hardcoded.
    
    Útil como fallback si el archivo de configuración no existe.
    
    Returns:
        ClickUpConfig con valores por defecto
    """
    return ClickUpConfig(
        status_mappings={
            "to_do": ["to do", "todo", "open", "por hacer", "pendiente"],
            "in_progress": ["in progress", "doing", "progress", "working", "en progreso"],
            "done": ["done", "complete", "completed", "closed", "finalizado", "completado"],
            "qa": ["qa", "testing", "test"],
            "review": ["review", "revision", "revisión"],
            "blocked": ["blocked", "bloqueado", "bloqueada"],
            "cancelled": ["cancelled", "canceled", "cancelado", "cancelada"]
        },
        priority_mappings={
            "urgent": ["urgent", "urgente", "crítico", "critical", "1"],
            "high": ["high", "alta", "alto", "2"],
            "normal": ["normal", "medium", "media", "medio", "3"],
            "low": ["low", "baja", "bajo", "4"]
        },
        critical_tags_for_comments=[
            "bloqueada", "blocked", "bloquer",
            "duda", "pregunta", "question",
            "review", "revisión",
            "data", "datos"
        ],
        spanish_translations={
            "status": {
                "to_do": "Pendiente",
                "in_progress": "En progreso",
                "done": "Completada",
                "qa": "En QA/Testing",
                "review": "En revisión",
                "blocked": "Bloqueada",
                "cancelled": "Cancelada",
                "unknown": "Desconocido"
            },
            "priority": {
                "urgent": "Urgente",
                "high": "Alta",
                "normal": "Normal",
                "low": "Baja",
                "unknown": "Sin prioridad"
            }
        }
    )


# Singleton global para evitar recargar config múltiples veces
_config_cache: Optional[ClickUpConfig] = None


def get_config(reload: bool = False) -> ClickUpConfig:
    """Obtener configuración (con caché).
    
    Args:
        reload: Si True, fuerza recarga desde disco
        
    Returns:
        ClickUpConfig (cacheado o recargado)
    """
    global _config_cache
    
    if _config_cache is None or reload:
        try:
            _config_cache = load_config()
            print("✅ Configuración cargada desde clickup_mappings.json")
        except FileNotFoundError:
            print("⚠️  Usando configuración por defecto (archivo no encontrado)")
            _config_cache = get_default_config()
        except Exception as e:
            print(f"❌ Error cargando configuración: {e}")
            print("⚠️  Usando configuración por defecto")
            _config_cache = get_default_config()
    
    return _config_cache
