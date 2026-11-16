"""Descriptive summaries from the complete independently audited 600-run table."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
with (HERE / "independent_model_equivalence_records.csv").open(encoding="utf-8-sig", newline="") as handle:
    rows = list(csv.DictReader(handle))
assert len(rows) == 600
methods = ["Standard-online", "SWAgent-online"]
paired = defaultdict(dict)
for row in rows:
    key = (row["source_task_id"], row["run_id"])
    assert row["method"] not in paired[key]
    paired[key][row["method"]] = row
assert len(paired) == 300 and all(set(p) == set(methods) for p in paired.values())
out = {"paired_by_source_and_run": {}, "by_repeat": {}, "source_pass_distribution": {}}
for name, predicate in [("full_model", lambda r: r["full_model_status"] == "PASS"),
                        ("answer", lambda r: r["answer_correct_existing"] == "True")]:
    counts = Counter()
    for pair in paired.values():
        standard, swagent = (predicate(pair[m]) for m in methods)
        counts["both" if standard and swagent else "swagent_only" if swagent else "standard_only" if standard else "neither"] += 1
    out["paired_by_source_and_run"][name] = dict(counts)
for run in ["1", "2", "3"]:
    out["by_repeat"][run] = {}
    for method in methods:
        selected = [r for r in rows if r["method"] == method and r["run_id"] == run]
        assert len(selected) == 100
        out["by_repeat"][run][method] = {
            "full_pass": sum(r["full_model_status"] == "PASS" for r in selected),
            "answer_correct": sum(r["answer_correct_existing"] == "True" for r in selected)}
for method in methods:
    sources = defaultdict(int)
    for row in rows:
        if row["method"] == method:
            sources[row["source_task_id"]] += row["full_model_status"] == "PASS"
    assert len(sources) == 100
    out["source_pass_distribution"][method] = dict(sorted(Counter(sources.values()).items()))
group = {m: [r for r in rows if r["method"] == m] for m in methods}
correct = {m: sum(r["answer_correct_existing"] == "True" for r in group[m]) for m in methods}
passed = {m: sum(r["full_model_status"] == "PASS" for r in group[m]) for m in methods}
ratios = {m: sum(r["full_model_status"] == "PASS" and r["answer_correct_existing"] == "True" for r in group[m]) / correct[m] for m in methods}
out["answer_correct_subset_full_pass"] = {"standard": ratios[methods[0]], "swagent": ratios[methods[1]],
    "difference_percentage_points": 100 * (ratios[methods[1]] - ratios[methods[0]])}
out["strict_model_nonpass_relative_reduction"] = (passed[methods[1]] - passed[methods[0]]) / (300 - passed[methods[0]])
out["strict_model_pass_relative_gain"] = (passed[methods[1]] - passed[methods[0]]) / passed[methods[0]]
sw = group[methods[1]]
initial_pass = sum(r["initial_full_model_status"] == "PASS" for r in sw)
out["swagent_initial_full_pass"] = initial_pass
out["swagent_final_full_pass"] = passed[methods[1]]
out["swagent_net_full_pass_increase"] = passed[methods[1]] - initial_pass
out["swagent_initial_fail_to_pass_share"] = sum(r["initial_full_model_status"] == "FAIL" and r["full_model_status"] == "PASS" for r in sw) / sum(r["initial_full_model_status"] == "FAIL" for r in sw)
out["scope"] = "Descriptive statistics of the same 100 sources x 3 runs; no independent 300-task or causal claim."
(HERE / "focused_evidence_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2))
