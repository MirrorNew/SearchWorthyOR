"""Offline scoring of delivered objectives; never imported by experiment workers."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch")
    args = parser.parse_args()
    batch = ROOT / "orlm_c3/batches" / args.batch
    manifest = read(batch / "batch_manifest.json")
    references = {r["eval_id"]: r for r in read(ROOT / "orlm_reference/scoring_reference.json")}
    rows = []
    for method in ("standard", "swagent"):
        for eval_id in manifest["selection"]:
            folder = batch / method / eval_id
            case = folder / "case"
            reference = references[eval_id]
            result = read(case / "result.json") if (case / "result.json").exists() else {}
            execution = read(folder / "execution.json") if (folder / "execution.json").exists() else {}
            error = read(case / "worker_error.json") if (case / "worker_error.json").exists() else {}
            decision = result.get("decision") or {}
            obj = decision.get("objective") or {}
            value = obj.get("value")
            matched = decision.get("status") == "OPTIMAL" and obj.get("direction") == reference["direction"] and type(value) in (int, float) and math.isfinite(value) and abs(value - reference["value"]) <= 1e-5
            resources = result.get("resources", error.get("resources", {}))
            row = {"source_id": reference["source_id"], "eval_id": eval_id, "method": method + "-online",
                   "completed": bool(execution), "stop_reason": result.get("stop_reason", error.get("stop_reason", "MISSING_RESULT")),
                   "error": result.get("error", error.get("error")), "solver_status": decision.get("status"),
                   "last_solver_status": (result.get("last_solve") or {}).get("status"),
                   "reference_direction": reference["direction"], "generated_direction": obj.get("direction"),
                   "reference_value": reference["value"], "generated_value": value,
                   "objective_match": bool(matched), "absolute_error": abs(value - reference["value"]) if isinstance(value, (float, int)) else None,
                   "normal_finish": result.get("stop_reason") in {"FINISHED", "FINISHED_AFTER_ACQUISITION_CLOSED"},
                   "model_calls": resources.get("model"), "search_calls": resources.get("search"), "read_calls": resources.get("read"),
                   "solve_calls": resources.get("solve"), "elapsed_seconds": execution.get("seconds"),
                   "output_actions": len(decision.get("actions") or {}), "recorded_usage": result.get("usage")}
            rows.append(row)
    summary = {"batch": args.batch, "condition": "C3-style", "metric": "delivered optimal objective match, not full-model or independently verified business feasibility",
               "absolute_tolerance": 1e-5, "n_per_method": manifest["case_count"], "recorded_monetary_cost": None,
               "complete": all(r["completed"] for r in rows), "methods": {}}
    for method in ("standard-online", "swagent-online"):
        group = [r for r in rows if r["method"] == method]
        summary["methods"][method] = {"matches": sum(r["objective_match"] for r in group), "denominator": len(group),
                    "match_percent": 100 * sum(r["objective_match"] for r in group) / len(group),
                    "completed": sum(r["completed"] for r in group), "normal_finish": sum(r["normal_finish"] for r in group),
                    "stop_reasons": dict(Counter(r["stop_reason"] for r in group)),
                    "model_calls": sum(r["model_calls"] or 0 for r in group),
                    "search_calls": sum(r["search_calls"] or 0 for r in group), "read_calls": sum(r["read_calls"] or 0 for r in group),
                    "known_total_tokens": sum((r["recorded_usage"] or {}).get("known_total_tokens") or 0 for r in group),
                    "runs_with_complete_token_usage": sum((r["recorded_usage"] or {}).get("usage_complete") is True for r in group),
                    "observed_models": sorted({name for r in group for name in (r["recorded_usage"] or {}).get("actual_models", [])})}
    (batch / "objective_scores.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (batch / "objective_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (batch / "objective_scores.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [k for k in rows[0] if k != "recorded_usage"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
