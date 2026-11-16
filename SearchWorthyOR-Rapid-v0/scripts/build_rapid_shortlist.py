from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from coptpy import COPT, Envr, quicksum


FAMILIES = (
    "routing_transport",
    "scheduling_workforce",
    "production_capacity",
    "assignment_matching",
    "facility_network",
    "inventory_supply_chain",
    "energy_environment",
    "healthcare_resources",
    "finance_portfolio",
    "telecom_service",
)
PATCH_CLASSES = (
    "eligibility_domain",
    "temporal_coupling",
    "conditional_auxiliary",
    "quota_risk_service_objective",
)
W_D_KEEP = {"W-D-002", "W-D-004", "W-D-005", "W-D-006", "W-D-008"}
PERMANENTLY_QUARANTINED_IDS = {f"SRCV2-{number:04d}" for number in range(294, 304)}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def eligible(row: dict[str, Any]) -> bool:
    atom = row.get("rule_atom")
    rejection_reason = row.get("rejection_reason")
    permanently_rejected = rejection_reason == "independent_support_review_requires_replacement"
    return bool(
        not permanently_rejected
        and row.get("candidate_id") not in PERMANENTLY_QUARANTINED_IDS
        and isinstance(atom, dict)
        and atom.get("not_numeric_only") is True
        and row.get("primary_url")
        and row.get("authority")
        and row.get("jurisdiction")
        and row.get("subject_scope")
        and row.get("effective_period")
        and row.get("support_needles")
        and set(row.get("candidate_families", ())) & set(FAMILIES)
        and set(row.get("candidate_patch_classes", ())) & set(PATCH_CLASSES)
    )


def quality(row: dict[str, Any]) -> int:
    value = 1000 if row["candidate_id"] in W_D_KEEP else 0
    if row.get("status") == "ROUND24_PENDING":
        value += 240
    elif row.get("status") == "DISCOVERED":
        value += 120
    elif row.get("rejection_reason") == "0h_insufficient_distinct_live_supporting_official_paths:1/2":
        value += 100
    elif row.get("status") == "REJECTED" and row.get("rejection_reason") is None:
        value += 50
    elif row.get("status") == "REJECTED":
        value += 20
    if any(r.get("round_pass") is True for r in row.get("probe_rounds", [])):
        value += 120
    if row.get("source_use_status") == "PERMISSIVE":
        value += 50
    if row.get("public_release_status"):
        value += 20
    if row.get("backup_official_urls"):
        value += 10
    numeric = "".join(ch for ch in row["candidate_id"] if ch.isdigit())
    return value * 10000 - int(numeric or 0)


def choose_primary(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    env = Envr()
    model = env.createModel("rapid_v0_primary_shortlist")
    model.setParam(COPT.Param.Logging, 0)
    choices: dict[tuple[int, int, str, str], Any] = {}
    for i, row in enumerate(pool):
        for batch in range(1, 6):
            for family in row["candidate_families"]:
                if family not in FAMILIES:
                    continue
                for patch in row["candidate_patch_classes"]:
                    if patch in PATCH_CLASSES:
                        choices[i, batch, family, patch] = model.addVar(
                            vtype=COPT.BINARY,
                            name=f"pick_{i}_{batch}_{family}_{patch}",
                        )
    for i in range(len(pool)):
        model.addConstr(
            quicksum(v for (j, _b, _f, _p), v in choices.items() if j == i) <= 1
        )
    for batch in range(1, 6):
        batch_vars = [v for (_i, b, _f, _p), v in choices.items() if b == batch]
        model.addConstr(quicksum(batch_vars) == 20)
        for family in FAMILIES:
            model.addConstr(
                quicksum(v for (_i, b, f, _p), v in choices.items() if b == batch and f == family)
                == 2
            )
        for patch in PATCH_CLASSES:
            model.addConstr(
                quicksum(v for (_i, b, _f, p), v in choices.items() if b == batch and p == patch)
                == 5
            )
    documents = sorted({row["source_document_key"] for row in pool})
    for document in documents:
        model.addConstr(
            quicksum(
                v
                for (i, _b, _f, _p), v in choices.items()
                if pool[i]["source_document_key"] == document
            )
            <= 3
        )
    for candidate_id in W_D_KEEP:
        indices = [i for i, row in enumerate(pool) if row["candidate_id"] == candidate_id]
        if indices:
            i = indices[0]
            model.addConstr(
                quicksum(v for (j, _b, _f, _p), v in choices.items() if j == i) == 1
            )
    w_d_008 = next(i for i, row in enumerate(pool) if row["candidate_id"] == "W-D-008")
    model.addConstr(
        choices[w_d_008, 1, "energy_environment", "quota_risk_service_objective"] == 1
    )
    model.setObjective(
        quicksum(quality(pool[i]) * v for (i, _b, _f, _p), v in choices.items()),
        COPT.MAXIMIZE,
    )
    model.solve()
    if model.status != COPT.OPTIMAL:
        raise RuntimeError(f"primary shortlist model status={model.status}")
    selected = []
    for (i, batch, family, patch), variable in choices.items():
        if variable.x > 0.5:
            selected.append(
                {
                    "row": pool[i],
                    "batch": batch,
                    "assigned_family": family,
                    "assigned_patch_class": patch,
                }
            )
    return selected


def choose_backups(
    pool: list[dict[str, Any]], primary_ids: set[str]
) -> list[dict[str, Any]]:
    remaining = [row for row in pool if row["candidate_id"] not in primary_ids]
    remaining.sort(key=lambda row: (-quality(row), row["candidate_id"]))
    document_counts: dict[str, int] = {}
    backups = []
    for row in remaining:
        document = row["source_document_key"]
        if document_counts.get(document, 0) >= 3:
            continue
        backups.append(row)
        document_counts[document] = document_counts.get(document, 0) + 1
        if len(backups) == 30:
            break
    if len(backups) != 30:
        raise RuntimeError(f"only {len(backups)} backups available")
    return [
        {
            "row": row,
            "batch": index // 6 + 1,
            "assigned_family": None,
            "assigned_patch_class": None,
        }
        for index, row in enumerate(backups)
    ]


def projection(item: dict[str, Any], role: str, task_id: str | None) -> dict[str, Any]:
    row = item["row"]
    return {
        "shortlist_role": role,
        "batch": item["batch"],
        "rapid_task_id": task_id,
        "source_candidate_id": row["candidate_id"],
        "assigned_family": item["assigned_family"],
        "assigned_patch_class": item["assigned_patch_class"],
        "authority": row["authority"],
        "jurisdiction": row["jurisdiction"],
        "source_document_key": row["source_document_key"],
        "regulation_key": row["regulation_key"],
        "primary_url": row["primary_url"],
        "backup_official_urls": row.get("backup_official_urls", []),
        "support_needles": row["support_needles"],
        "rule_atom": row["rule_atom"],
        "subject_scope": row["subject_scope"],
        "exception_scope": row["exception_scope"],
        "effective_period": row["effective_period"],
        "candidate_families": row["candidate_families"],
        "candidate_patch_classes": row["candidate_patch_classes"],
        "quality_score": quality(row),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ledger = read_jsonl(args.v2_root / "private/source_candidates.jsonl")
    staging = read_jsonl(args.v2_root / "staging/source_candidates_batch_w_d.jsonl")
    pool = [row for row in ledger if eligible(row)]
    pool.extend(row for row in staging if row["candidate_id"] in W_D_KEEP and eligible(row))
    ids = [row["candidate_id"] for row in pool]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate candidate ids")
    primary = choose_primary(pool)
    primary.sort(
        key=lambda item: (
            item["batch"],
            0 if item["row"]["candidate_id"] == "W-D-008" else 1,
            item["assigned_family"],
            item["assigned_patch_class"],
            item["row"]["candidate_id"],
        )
    )
    rows = []
    counters = {batch: 0 for batch in range(1, 6)}
    for item in primary:
        batch = item["batch"]
        counters[batch] += 1
        task_number = (batch - 1) * 20 + counters[batch]
        rows.append(projection(item, "PRIMARY", f"SWOR-R{task_number:03d}"))
    primary_ids = {item["row"]["candidate_id"] for item in primary}
    backups = choose_backups(pool, primary_ids)
    rows.extend(projection(item, "BACKUP", None) for item in backups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "eligible_pool": len(pool),
                "primary": len(primary),
                "backups": len(backups),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
