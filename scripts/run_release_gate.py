"""Run every non-optional SearchWorthyOR-100 release gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from audit_duplicates_and_leakage import audit_dataset
from audit_evidence_patch_binding import audit_evidence_patch_binding
from audit_structure_and_provenance import audit_structure_and_provenance
from validate_dataset_schema import validate_dataset


def run_release_gate(root: Path) -> dict[str, Any]:
    schema = validate_dataset(root)
    duplicate_leakage = audit_dataset(root)
    structure_provenance = audit_structure_and_provenance(root)
    evidence_patch_binding = audit_evidence_patch_binding(root)
    return {
        "ok": (
            schema.ok
            and duplicate_leakage.ok
            and structure_provenance.ok
            and evidence_patch_binding.ok
        ),
        "gates": {
            "schema_and_semantics": schema.as_dict(),
            "duplicates_and_leakage": duplicate_leakage.as_dict(),
            "structure_and_provenance": structure_provenance.as_dict(),
            "evidence_and_patch_binding": evidence_patch_binding.as_dict(),
        },
        "summary": {
            "error_count": (
                len(schema.errors)
                + len(duplicate_leakage.errors)
                + len(structure_provenance.errors)
                + len(evidence_patch_binding.errors)
            ),
            "warning_count": (
                len(schema.warnings)
                + len(duplicate_leakage.warnings)
                + len(structure_provenance.warnings)
                + len(evidence_patch_binding.warnings)
            ),
        },
    }


def _format_human(result: dict[str, Any]) -> str:
    lines = [
        f"SearchWorthyOR-100 release gate: {'PASS' if result['ok'] else 'FAIL'}",
        (
            f"errors={result['summary']['error_count']} "
            f"warnings={result['summary']['warning_count']}"
        ),
    ]
    for gate_name, gate in result["gates"].items():
        lines.append(
            f"{gate_name}: {'PASS' if gate['ok'] else 'FAIL'} "
            f"({len(gate['errors'])} errors)"
        )
        for entry in gate["errors"]:
            lines.append(
                f"  ERROR [{entry['code']}] {entry['path']}: {entry['message']}"
            )
        for entry in gate["warnings"]:
            lines.append(
                f"  WARN  [{entry['code']}] {entry['path']}: {entry['message']}"
            )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="dataset root (default: parent of scripts/)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument(
        "--output",
        type=Path,
        help="optionally write the complete JSON result as UTF-8",
    )
    args = parser.parse_args(argv)
    result = run_release_gate(args.root.resolve())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_format_human(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
