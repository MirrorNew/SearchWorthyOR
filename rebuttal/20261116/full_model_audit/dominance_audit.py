"""Check explicit same-primary-choice dominance witnesses for service pruning."""
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
old = ROOT / "analysis/rebuttal_dqz1_evidence_20261114"
spec = importlib.util.spec_from_file_location("frozen_enum", old / "model_equivalence.py")
enum = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enum)
gold = {}
for line in (ROOT / "datasets/SearchWorthyOR-v1.6.3/private/gold.jsonl").read_text(encoding="utf-8-sig").splitlines():
    g = json.loads(line)
    gold[g.get("id", g.get("source_task_id"))] = g
records = [json.loads(line) for line in (old / "model_full_equivalence_records.jsonl").read_text(encoding="utf-8-sig").splitlines()]
selected = [r for r in records if r["method"] == "SWAgent-online" and r["answer_correct_existing"] and r["full_model_status"] == "FAIL"
            and r["source_task_id"] in {"SWOR-R025", "SWOR-R103", "SWOR-R105"}]
results = []
for row in selected:
    g = gold[row["source_task_id"]]
    mapping = g["public_to_private_action_map"]
    public = sorted(mapping)
    reference = enum.normalize(enum.read(ROOT / row["reference_file"]), mapping)
    generated = enum.normalize(enum.read(ROOT / row["model_file"])["model"])
    ref, _ = enum.enumerate_model(reference, public)
    gen, _ = enum.enumerate_model(generated, public)
    assert reference["objective"]["direction"] == generated["objective"]["direction"] == "max"
    assert set(gen).issubset(ref)
    assert all(gen[a] == ref[a] for a in gen)
    primary_indices = [i for i, name in enumerate(public) if int(name.rsplit("a", 1)[-1]) <= 4]
    witnesses = []
    for action in sorted(set(ref) - set(gen)):
        candidates = [a for a in gen if all(a[i] == action[i] for i in primary_indices) and gen[a] > ref[action]]
        assert candidates, (row["source_task_id"], row["run_id"], action)
        better = max(candidates, key=lambda a: gen[a])
        witnesses.append({"removed_action": dict(zip(public, action)), "reference_value": str(ref[action]),
                          "retained_action": dict(zip(public, better)), "retained_value": str(gen[better]),
                          "strict_improvement": str(gen[better] - ref[action]),
                          "changed_services": [public[i] for i in range(len(public)) if action[i] != better[i]]})
    results.append({"source_task_id": row["source_task_id"], "run_id": row["run_id"],
                    "generated_subset_of_reference": True, "same_primary_choice_in_every_witness": True,
                    "every_removed_action_strictly_dominated": True, "removed_actions": len(witnesses), "witnesses": witnesses})
summary = {"scope": "given task constraints and service costs; mathematical safe pruning, not preservation of the entire feasible set or proof the agent intentionally used dominance",
           "runs": len(results), "source_tasks": len(set(r["source_task_id"] for r in results)),
           "removed_actions_with_dominance_witness": sum(r["removed_actions"] for r in results), "results": results}
(OUT / "dominance_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k != "results"}))
