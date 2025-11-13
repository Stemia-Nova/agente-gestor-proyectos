import json, pathlib

p = pathlib.Path("data/processed/task_natural.jsonl")
n = empty = 0

for line in p.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    n += 1
    obj = json.loads(line)
    meta = obj.get("metadata", {})
    if not meta.get("sprint") or not meta.get("project"):
        empty += 1

print("Total líneas:", n, "| Con sprint/project vacío:", empty)
