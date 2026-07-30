"""Print compact UTF-8 review packets for the frozen reserve2 sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in (
            ROOT / "staging" / "supplemental_reserve2_audit.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for index, row in enumerate(
        rows[args.start : args.start + args.count], args.start + 1
    ):
        directory = (
            ROOT
            / "staging"
            / "certified_sources"
            / "supplemental_reserve2"
            / row["source_id"]
        )
        source = json.loads(
            (directory / "source_snapshot.json").read_text(encoding="utf-8")
        )
        ir = json.loads(
            (directory / "canonical_ir.json").read_text(encoding="utf-8")
        )
        print(
            f"\n===== {index} {row['candidate_id']} {row['source_id']} ====="
        )
        print(source["problem_text"])
        print(
            "VARS",
            [
                (
                    variable["name"],
                    variable["vartype"],
                    variable.get("lb"),
                    variable.get("ub"),
                )
                for variable in ir["variables"]
            ],
        )
        print(
            "OBJ",
            ir["sense"],
            ir["objective"]["terms"],
            ir["objective"].get("constant"),
        )
        print(
            "CONS",
            [
                (
                    constraint["name"],
                    constraint["terms"],
                    constraint["sense"],
                    constraint["rhs"],
                )
                for constraint in ir["constraints"]
            ],
        )
        print("INTERP", ir.get("metadata", {}).get("interpretation"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
