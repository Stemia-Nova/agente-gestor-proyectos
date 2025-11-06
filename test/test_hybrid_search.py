from utils.hybrid_search import HybridSearch

hs = HybridSearch()

print("\n🔹 BM25:")
bm25_results = hs.keyword_search("Sprint 3")

print("\n🔹 Semántico:")
sem_results = hs.semantic_search("tareas bloqueadas")

print("\n🔹 Re-rank:")
hs.rerank("tareas bloqueadas", sem_results)
