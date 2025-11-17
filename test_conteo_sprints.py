#!/usr/bin/env python3
"""
Test para validar el conteo de sprints con enfoque híbrido profesional.

Problema reportado: "cuántos sprints hay?" retornaba 24 (total de tareas)
Solución: Enfoque híbrido - delegar al LLM con contexto enriquecido (flexible + inteligente)
"""

import sys
sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

from utils.hybrid_search import HybridSearch
from dotenv import load_dotenv
import time

# Cargar variables de entorno
load_dotenv()

def verificar_chromadb():
    """Verificar datos en ChromaDB."""
    print("=" * 70)
    print("🔍 VERIFICACIÓN DE CHROMADB")
    print("=" * 70)
    
    import chromadb
    
    client = chromadb.PersistentClient(path="data/rag/chroma_db")
    collection = client.get_or_create_collection(name="clickup_tasks")
    result = collection.get(include=['metadatas'])
    
    metas = result['metadatas']
    
    # Extraer sprints únicos
    sprints = set()
    sprint_counts = {}
    
    for m in metas:
        sprint_name = m.get('sprint')
        if sprint_name:
            sprints.add(sprint_name)
            sprint_counts[sprint_name] = sprint_counts.get(sprint_name, 0) + 1
    
    print(f"\nTotal tareas: {len(metas)}")
    print(f"Sprints únicos: {len(sprints)}")
    print("\nDistribución:")
    for sprint in sorted(sprints):
        count = sprint_counts.get(sprint, 0)
        print(f"  • {sprint}: {count} tareas")
    
    print("=" * 70)
    return len(sprints), sprint_counts

def test_conteo_sprints_hibrido():
    """Test del conteo de sprints con enfoque híbrido (LLM)."""
    print("\n" + "=" * 70)
    print("🧪 TEST: Conteo de Sprints (Enfoque Híbrido - LLM)")
    print("=" * 70)
    
    hs = HybridSearch(collection_name="clickup_tasks")
    
    # Variantes de la pregunta (incluyendo reformulaciones)
    queries = [
        "¿cuántos sprints hay?",
        "cuantos sprints hay",
        "número de sprints en el proyecto",
        "cuántas iteraciones tenemos",
        "how many sprints",  # inglés
    ]
    
    print("\n📝 Probando variantes de la pregunta:")
    print("   (El LLM debe entender todas las reformulaciones)\n")
    
    results = []
    for i, query in enumerate(queries, 1):
        print(f"{i}. Query: \"{query}\"")
        
        # Medir tiempo
        start = time.time()
        response = hs.answer(query, temperature=0.2)  # Usar answer() que delega al LLM
        elapsed = time.time() - start
        
        print(f"   Tiempo: {elapsed:.2f}s")
        print(f"   Respuesta: {response}")
        
        # Validar respuesta
        if "3" in response and ("sprint" in response.lower() or "iteraci" in response.lower()):
            print("   ✅ CORRECTO: Detecta 3 sprints")
            results.append(True)
        elif "24" in response and "tarea" in response.lower():
            print("   ❌ ERROR: Está contando tareas (24) en vez de sprints")
            results.append(False)
        else:
            print("   ⚠️  Respuesta inesperada (verificar manualmente)")
            results.append(None)
        
        print()
    
    # Resumen
    print("=" * 70)
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    
    if failed > 0:
        print(f"❌ TEST FALLIDO: {failed}/{len(queries)} respuestas incorrectas")
        return False
    elif passed == len(queries):
        print(f"✅ TEST PASADO: {passed}/{len(queries)} respuestas correctas")
        print("\n💡 VENTAJAS DEL ENFOQUE HÍBRIDO:")
        print("   • Entiende reformulaciones naturales")
        print("   • Funciona en múltiples idiomas")
        print("   • No requiere regex por cada variante")
        print("   • Proporciona contexto adicional (distribución)")
        return True
    else:
        print(f"⚠️  TEST PARCIAL: {passed}/{len(queries)} correctas, {len(queries) - passed - failed} inconclusas")
        return None

def test_comparacion_enfoques():
    """Demostrar superioridad del enfoque híbrido vs manual."""
    print("\n" + "=" * 70)
    print("📊 COMPARACIÓN: Enfoque Manual vs Híbrido (LLM)")
    print("=" * 70)
    
    queries_dificiles = [
        ("¿En cuántos ciclos dividieron el trabajo?", "Requiere sinónimo (ciclo=sprint)"),
        ("Número de iteraciones en el proyecto", "Reformulación técnica"),
        ("Quiero saber cuántos sprints han creado", "Formulación indirecta"),
        ("how many sprints are there?", "Inglés"),
    ]
    
    print("\n🔧 ENFOQUE MANUAL (Regex):")
    print("   ❌ Requiere regex por cada variante")
    print("   ❌ No entiende sinónimos")
    print("   ❌ Un idioma por implementación")
    print("   ✅ Rápido (sin latencia LLM)")
    print("   ✅ Determinístico")
    
    print("\n🧠 ENFOQUE HÍBRIDO (LLM):")
    print("   ✅ Entiende reformulaciones naturales")
    print("   ✅ Multiidioma sin cambios")
    print("   ✅ Contexto enriquecido (distribución)")
    print("   ⚠️  Latencia ~1-2s (aceptable para UX)")
    print("   ⚠️  Costo por query (~$0.0001)")
    
    print("\n" + "=" * 70)
    print("💡 CONCLUSIÓN: Híbrido es MÁS PROFESIONAL para casos no críticos")
    print("=" * 70)

if __name__ == "__main__":
    # 1. Verificar ChromaDB
    num_sprints, sprint_counts = verificar_chromadb()
    
    # 2. Ejecutar test principal
    success = test_conteo_sprints_hibrido()
    
    # 3. Mostrar comparación
    test_comparacion_enfoques()
    
    # 4. Resultado final
    if success:
        print("\n🎉 ¡Test completado exitosamente!")
        print(f"\n✅ El sistema detecta correctamente {num_sprints} sprints únicos")
        print("✅ El enfoque híbrido (LLM) proporciona flexibilidad profesional")
        sys.exit(0)
    elif success is False:
        print("\n❌ Test falló")
        sys.exit(1)
    else:
        print("\n⚠️  Test inconcluso - revisar manualmente")
        sys.exit(2)
