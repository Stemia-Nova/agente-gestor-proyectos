# tools/fix_priority_unknown.py
import json
from pathlib import Path

IN = Path("data/processed/task_natural.jsonl")
OUT = Path("data/processed/task_natural.fixed.jsonl")

def main():
    lines = IN.read_text(encoding="utf-8").splitlines()
    fixed = 0
    with OUT.open("w", encoding="utf-8") as f:
        for line in lines:
            if not line.strip():
                continue
            obj = json.loads(line)
            m = dict(obj.get("metadata", {}) or {})
            # Si priority está ausente o vacía -> "unknown"
            if not m.get("priority"):
                m["priority"] = "unknown"
                fixed += 1
            obj["metadata"] = m
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"✅ Escrito: {OUT}")
    print(f"🔧 Prioridades fijadas a 'unknown': {fixed}")

if __name__ == "__main__":
    main()
