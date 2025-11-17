#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/st12/agente-gestor-proyectos/agente-gestor-proyectos')

from utils.hybrid_search import HybridSearch

print("🔍 Generando informe con nuevo formato Markdown...\n")

searcher = HybridSearch()
response = searcher.answer('Quiero un informe del Sprint 3 en texto')

print("="*70)
print(response)
print("="*70)
