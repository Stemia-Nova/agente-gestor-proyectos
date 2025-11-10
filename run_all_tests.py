#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all_tests.py
----------------
Runner de validación para toda la batería de tests del Agente Gestor de Proyectos.

Ejecuta Pytest programáticamente y muestra un resumen visual con emojis y colores.
"""

import pytest
import time
import sys
from pathlib import Path

# =============================================================
# 🎨 Colores para salida en terminal
# =============================================================
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


# =============================================================
# 🧪 Tests que se ejecutarán
# =============================================================
TESTS = [
    "test/test_hybrid_search.py",
    "test/test_contextual_memory.py",
    "test/test_chatbot_end2end_mixed.py",
    "test/test_natural_queries.py",
    "test/test_natural_queries_extend.py",
]

# =============================================================
# 🚀 Ejecutar batería completa
# =============================================================
def main() -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}🧪 Ejecutando batería completa de tests RAG...{Colors.RESET}\n")

    t0 = time.time()
    results_summary = []
    total_passed, total_failed = 0, 0

    for test_path in TESTS:
        path = Path(test_path)
        if not path.exists():
            print(f"{Colors.YELLOW}⚠️  {test_path} no encontrado, omitido.{Colors.RESET}")
            continue

        print(f"{Colors.BOLD}▶️ Ejecutando: {path.name}{Colors.RESET}")
        start = time.time()

        # Ejecutar pytest silenciosamente, capturando resultado
        result = pytest.main([str(path), "-q", "--disable-warnings"])
        end = time.time()
        elapsed = end - start

        if result == 0:
            print(f"{Colors.GREEN}✅ {path.name} — OK ({elapsed:.2f}s){Colors.RESET}\n")
            total_passed += 1
            results_summary.append((path.name, True, elapsed))
        else:
            print(f"{Colors.RED}❌ {path.name} — FALLÓ ({elapsed:.2f}s){Colors.RESET}\n")
            total_failed += 1
            results_summary.append((path.name, False, elapsed))

    # =========================================================
    # 🧾 Resumen final
    # =========================================================
    total = total_passed + total_failed
    duration = time.time() - t0

    print(f"\n{Colors.BOLD}{Colors.CYAN}📊 RESUMEN GLOBAL{Colors.RESET}")
    print(f"{'-'*50}")
    for name, passed, t in results_summary:
        emoji = "✅" if passed else "❌"
        color = Colors.GREEN if passed else Colors.RED
        print(f"{emoji} {color}{name:<35}{Colors.RESET} ({t:.2f}s)")
    print(f"{'-'*50}")

    print(
        f"\n{Colors.BOLD}🏁 Total: {total} tests — "
        f"{Colors.GREEN}{total_passed} OK{Colors.RESET}, "
        f"{Colors.RED}{total_failed} fallidos{Colors.RESET} "
        f"⏱️  Tiempo total: {duration:.2f}s{Colors.RESET}\n"
    )

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
