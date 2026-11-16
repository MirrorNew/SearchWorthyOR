"""Check archived inputs against the frozen inputs used by this retrospective audit."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
old = ROOT / "analysis/rebuttal_dqz1_evidence_20261114/model_full_equivalence_records.jsonl"
public_file = ROOT / "datasets/SearchWorthyOR-v1.6.3/public/cases_zh.jsonl"
records = [json.loads(line) for line in old.read_text(encoding="utf-8-sig").splitlines()]
public = {row["eval_id"]: row for row in map(json.loads, public_file.read_text(encoding="utf-8-sig").splitlines())}
checks = []
for row in records:
    path = (ROOT / row["model_file"]).parent.parent / "input.json"
    saved = json.loads(path.read_text(encoding="utf-8-sig"))
    current = public[row["eval_id"]]
    checks.append({"source_task_id": row["source_task_id"], "run_id": row["run_id"], "method": row["method"],
                   "input_file": path.relative_to(ROOT).as_posix(), "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "id_equal": saved["id"] == current["eval_id"],
                   "prompt_equal": saved["prompt"] == current["prompt_zh"],
                   "output_schema_equal": saved["output_schema"] == current["output_schema"]})
result = {"records": len(checks), "identical": sum(c["id_equal"] and c["prompt_equal"] and c["output_schema_equal"] for c in checks),
          "scope": "saved public input equality; not independent validation of reference semantics", "checks": checks}
(OUT / "input_provenance_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "checks"}))
assert result["identical"] == result["records"] == 600
