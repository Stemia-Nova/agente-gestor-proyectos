# tools/fix_natural_metadata.py
import json
from pathlib import Path

IN = Path("data/processed/task_natural.jsonl")
OUT = Path("data/processed/task_natural.fixed.jsonl")

def fix_meta(m):
    # Defaults claros en vez de vacío
    m = dict(m or {})
    m.setdefault("status", "unknown")
    m.setdefault("priority", "unknown")
    m["sprint"]  = m.get("sprint")  or "unknown"
    m["project"] = m.get("project") or "unknown"
    m["creator"] = m.get("creator") or "unknown"
    m["date_created"] = m.get("date_created") or "unknown"
    m["due_date"] = m.get("due_date") or "unknown"
    if "assignees" not in m or m["assignees"] is None:
        m["assignees"] = []
    return m

def main():
    lines = IN.read_text(encoding="utf-8").splitlines()
    with OUT.open("w", encoding="utf-8") as f:
        for line in lines:
            if not line.strip():
                continue
            obj = json.loads(line)
            obj["metadata"] = fix_meta(obj.get("metadata"))
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"✅ Escrito: {OUT}")

if __name__ == "__main__":
    main()
