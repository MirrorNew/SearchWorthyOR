from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from review_artifact_fingerprint import compute_fingerprint
from review_contract import reviewer_assignment_errors


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rapid-root", type=Path, required=True)
    parser.add_argument("--batch", type=int, required=True, choices=range(1, 6))
    args = parser.parse_args()
    root = args.rapid_root.resolve()
    batch_dir = root / "batches" / f"batch_{args.batch:02d}"
    audit_path = batch_dir / "private" / "rapid_audit.jsonl"
    review_path = batch_dir / "private" / "independent_review.jsonl"
    audits = read_jsonl(audit_path)
    reviews = read_jsonl(review_path)
    schema = json.loads((root / "schemas" / "independent_review.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    contract = json.loads((root / "config" / "rapid_contract.json").read_text(encoding="utf-8"))
    errors = []
    if [row.get("id") for row in audits] != [row.get("id") for row in reviews]:
        errors.append("review_ids_do_not_match_audits")
    review_by_id = {row.get("id"): row for row in reviews}
    boolean_fields = [key for key, value in schema["properties"].items() if value == {"type": "boolean"}]
    for audit in audits:
        review = review_by_id.get(audit.get("id"), {})
        for issue in validator.iter_errors(review):
            errors.append(f"{audit.get('id')}:schema:{'/'.join(map(str, issue.path))}:{issue.message}")
        if review.get("reviewer_id") == audit.get("generator_id"):
            errors.append(f"{audit.get('id')}:reviewer_is_generator")
        errors.extend(
            f"{audit.get('id')}:{error}"
            for error in reviewer_assignment_errors(contract, args.batch, review.get("reviewer_id"))
        )
        expected_fingerprint = compute_fingerprint(root, args.batch, audit.get("id"))
        if review.get("artifact_fingerprint") != expected_fingerprint:
            errors.append(f"{audit.get('id')}:stale_review_artifact_fingerprint")
        if review.get("status") != "PASS" or any(review.get(field) is not True for field in boolean_fields):
            errors.append(f"{audit.get('id')}:review_not_unanimous_pass")
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    for audit in audits:
        audit["independent_review"] = "PASS"
        audit["status"] = "RAPID_V0_PASS"
    write_jsonl(audit_path, audits)
    print(json.dumps({"status": "PASS", "batch": args.batch, "updated": len(audits)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
