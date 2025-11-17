#!/usr/bin/env python3
"""
Test de contexto conversacional mejorado.
Simula la secuencia: "hay tareas bloqueadas?" → "me puedes dar más info?"
"""

import sys
import os
sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

from dotenv import load_dotenv
load_dotenv()

from chatbot.handlers import handle_query, conversation_history
import asyncio

async def test_conversational_context():
    print("=" * 80)
    print("🧪 TEST: Contexto conversacional - Solicitud de más información")
    print("=" * 80)
    
    # Limpiar historial previo
    conversation_history.clear()
    
    # Pregunta 1: ¿Hay tareas bloqueadas?
    print("\n1️⃣ Usuario: ¿hay tareas bloqueadas?")
    response1 = await handle_query("hay tareas bloqueadas?")
    print(f"   Bot: {response1[:200]}...")
    
    # Pregunta 2: Dame más info (debe referirse a la tarea bloqueada)
    print("\n2️⃣ Usuario: me puedes dar más info?")
    response2 = await handle_query("me puedes dar más info?")
    print(f"   Bot: {response2[:300]}...")
    
    # Verificar que la respuesta habla de la tarea bloqueada específica
    print("\n" + "=" * 80)
    print("📊 VALIDACIÓN:")
    print("=" * 80)
    
    # Extraer nombre de la tarea bloqueada de la primera respuesta
    import re
    task_names = re.findall(r'"([^"]+)"', response1)
    
    if task_names:
        blocked_task_name = task_names[0]
        print(f"✅ Tarea bloqueada detectada: '{blocked_task_name}'")
        
        # Verificar que la segunda respuesta menciona la misma tarea
        if blocked_task_name.lower() in response2.lower():
            print(f"✅ PASS: La respuesta habla de '{blocked_task_name}'")
        else:
            print(f"❌ FAIL: La respuesta NO menciona '{blocked_task_name}'")
            print(f"   Respuesta completa: {response2}")
        
        # Verificar que incluye información detallada
        has_details = any(word in response2.lower() for word in [
            "subtarea", "comentario", "estado", "sprint", "asignado", "prioridad"
        ])
        
        if has_details:
            print("✅ PASS: La respuesta incluye detalles (subtareas, comentarios, etc.)")
        else:
            print("⚠️  WARNING: La respuesta no incluye detalles suficientes")
    else:
        print("❌ FAIL: No se pudo detectar ninguna tarea bloqueada en la primera respuesta")
    
    print("\n" + "=" * 80)
    print("📝 Respuesta completa a 'más info':")
    print("=" * 80)
    print(response2)
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_conversational_context())
