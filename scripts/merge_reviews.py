"""Merge two independently written blind-review files into private gold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_dataset import read_jsonl, refresh_manifest, write_json, write_jsonl


REQUIRED_REVIEW_CHECKS = {
    "base_semantics",
    "source_applicability",
    "patch_semantics",
    "solver_dual",
    "certificate_complete",
    "anti_fogging",
    "metadata_leakage",
}

REQUIRED_REVIEW_FIELDS = {
    "id",
    "label",
    "reviewer_id",
    "blind_packet",
    "issues",
    "checks",
}


def validate_review(review: dict, *, expected_id: str, packet: str) -> None:
    if set(review) != REQUIRED_REVIEW_FIELDS:
        raise ValueError(
            f"{packet}:{expected_id}: review fields must exactly match the frozen contract."
        )
    if review.get("id") != expected_id:
        raise ValueError(f"{packet}: task id mismatch for {expected_id}.")
    if review.get("label") not in {"accept", "reject"}:
        raise ValueError(f"{packet}:{expected_id}: label must be accept or reject.")
    if review.get("blind_packet") is not True:
        raise ValueError(f"{packet}:{expected_id}: blind_packet must be true.")
    reviewer_id = review.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ValueError(f"{packet}:{expected_id}: reviewer_id is required.")
    issues = review.get("issues")
    if not isinstance(issues, list):
        raise ValueError(f"{packet}:{expected_id}: issues must be a list.")
    checks = review.get("checks")
    if not isinstance(checks, dict) or set(checks) != REQUIRED_REVIEW_CHECKS:
        raise ValueError(
            f"{packet}:{expected_id}: checks must exactly match the frozen review contract."
        )
    if any(not isinstance(value, bool) for value in checks.values()):
        raise ValueError(f"{packet}:{expected_id}: every review check must be boolean.")
    if review["label"] == "accept" and (issues or not all(checks.values())):
        raise ValueError(
            f"{packet}:{expected_id}: accept is inconsistent with issues or failed checks."
        )
    if review["label"] == "reject":
        if not issues:
            raise ValueError(
                f"{packet}:{expected_id}: reject must state at least one issue."
            )
        if all(checks.values()):
            raise ValueError(
                f"{packet}:{expected_id}: reject must fail at least one check."
            )


def gwet_ac1(labels_a: list[str], labels_b: list[str]) -> float:
    if len(labels_a) != len(labels_b) or not labels_a:
        raise ValueError("Review vectors must be non-empty and aligned.")
    observed = sum(a == b for a, b in zip(labels_a, labels_b, strict=True)) / len(
        labels_a
    )
    categories = sorted(set(labels_a) | set(labels_b))
    pooled = {
        category: (
            labels_a.count(category) + labels_b.count(category)
        )
        / (2 * len(labels_a))
        for category in categories
    }
    chance = sum(probability * (1 - probability) for probability in pooled.values())
    if abs(1 - chance) < 1e-12:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - chance) / (1 - chance)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    root = args.root.resolve()
    gold = read_jsonl(root / "private" / "gold.jsonl")
    review_a = read_jsonl(root / "audits" / "review_a.jsonl")
    review_b = read_jsonl(root / "audits" / "review_b.jsonl")
    by_a = {row["id"]: row for row in review_a}
    by_b = {row["id"]: row for row in review_b}
    ids = [row["id"] for row in gold]
    if len(review_a) != 100 or len(review_b) != 100:
        raise ValueError("Both review files must contain exactly 100 rows.")
    if set(by_a) != set(ids) or set(by_b) != set(ids):
        raise ValueError("Review task IDs do not exactly match gold.")

    labels_a = []
    labels_b = []
    unresolved = []
    for row in gold:
        task_id = row["id"]
        a = by_a[task_id]
        b = by_b[task_id]
        validate_review(a, expected_id=task_id, packet="review_a")
        validate_review(b, expected_id=task_id, packet="review_b")
        if a["reviewer_id"] == b["reviewer_id"]:
            raise ValueError(f"{task_id}: blind reviewers must be distinct.")
        labels_a.append(a["label"])
        labels_b.append(b["label"])
        row["reviews"] = {"review_a": a, "review_b": b}
        both_pass = a["label"] == "accept" and b["label"] == "accept"
        row["adjudication"] = {
            "status": "resolved" if both_pass else "requires_fix",
            "label": "accept" if both_pass else "reject",
            "unresolved": not both_pass,
            "adjudicator": "root_agent",
            "basis": (
                "two independent blind passes"
                if both_pass
                else "at least one blind reviewer reported an unresolved issue"
            ),
        }
        row["base_audit"]["independent_reviews"] = (
            "complete_pass" if both_pass else "requires_fix"
        )
        row["base_audit"]["status"] = (
            "unchanged_pass" if both_pass else "rejected"
        )
        if not both_pass:
            unresolved.append(
                {
                    "id": task_id,
                    "review_a": a["issues"],
                    "review_b": b["issues"],
                }
            )
    observed = sum(
        a == b for a, b in zip(labels_a, labels_b, strict=True)
    ) / len(labels_a)
    agreement = {
        "review_count_each": 100,
        "observed_agreement": observed,
        "gwet_ac1": gwet_ac1(labels_a, labels_b),
        "threshold": 0.8,
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
        "passed": observed >= 0.8
        and gwet_ac1(labels_a, labels_b) >= 0.8
        and not unresolved,
    }
    write_jsonl(root / "private" / "gold.jsonl", gold)
    write_json(root / "audits" / "review_agreement.json", agreement)
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        summary = dict(manifest.get("build_summary", {}))
    else:
        summary = {}
    summary.update({
        "tasks": len(gold),
        "gold_rows": len(gold),
        "unique_base_ids": len({row["base_id"] for row in gold}),
        "all_decision_certificates_pass": all(
            row["decision_certificate"]["passed"] for row in gold
        ),
        "reviews_pending": bool(unresolved),
        "review_agreement": agreement,
    })
    refresh_manifest(root, summary)
    print(json.dumps(agreement, ensure_ascii=False, indent=2))
    return 0 if agreement["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
