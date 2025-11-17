#!/usr/bin/env python3
"""
Script de prueba para verificar el conteo mejorado de tareas.
Verifica: "¿cuantas tareas completadas hay en el sprint 3?"
"""

import sys
sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

import chromadb
from typing import cast, Any

# Conectar a ChromaDB
client = chromadb.PersistentClient(path="data/rag/chroma_db")
collection = client.get_or_create_collection("clickup_tasks")

print("=" * 80)
print("🔍 TEST: Conteo de tareas completadas en Sprint 3")
print("=" * 80)

# Paso 1: Obtener TODAS las tareas del Sprint 3
sprint_filter = {"sprint": "Sprint 3"}
result = collection.get(
    where=cast(Any, sprint_filter),
    limit=10000,
    include=cast(Any, ['metadatas'])
)

all_sprint_3_metas = result.get('metadatas') or []
print(f"\n📦 Total de tareas en Sprint 3: {len(all_sprint_3_metas)}")

# Listar estados disponibles
estados = {}
for m in all_sprint_3_metas:
    status = m.get('status', 'Sin estado')
    estados[status] = estados.get(status, 0) + 1
    
print(f"\n📊 Distribución de estados:")
for estado, count in estados.items():
    print(f"   - {estado}: {count}")

# Paso 2: Filtrar solo las completadas EN PYTHON
completadas = [m for m in all_sprint_3_metas if m.get('status') == 'Completada']

print(f"\n✅ Tareas COMPLETADAS en Sprint 3: {len(completadas)}")

if completadas:
    print("\n📝 Detalles:")
    for m in completadas:
        name = m.get('name', 'Sin nombre')
        assignees = m.get('assignees', 'Sin asignar')
        print(f"   - {name} (Asignado: {assignees})")
else:
    print("   (No hay tareas completadas)")

print("\n" + "=" * 80)
print(f"🎯 RESPUESTA CORRECTA: Hay {len(completadas)} tareas completadas en el Sprint 3")
print("=" * 80)
