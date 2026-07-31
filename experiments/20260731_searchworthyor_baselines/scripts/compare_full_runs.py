from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any


CORE_METRICS = (
    "base_model_success",
    "generated_code_ir_consistent",
    "evidence_selected",
    "model_structurally_changed",
    "decision_model_equivalent",
    "decision_e2e",
    "semantic_e2e",
    "strict_e2e",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires at least one value")
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return (
        sorted_values[lower] * (1.0 - weight)
        + sorted_values[upper] * weight
    )


def bootstrap_rate(
    values: list[int],
    rng: random.Random,
    samples: int,
) -> dict[str, float]:
    n = len(values)
    draws = []
    for _ in range(samples):
        draws.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    draws.sort()
    return {
        "rate": sum(values) / n,
        "ci95_low": quantile(draws, 0.025),
        "ci95_high": quantile(draws, 0.975),
    }


def bootstrap_paired_difference(
    left: list[int],
    right: list[int],
    rng: random.Random,
    samples: int,
) -> dict[str, float]:
    n = len(left)
    differences = []
    for _ in range(samples):
        sampled = [rng.randrange(n) for _ in range(n)]
        differences.append(
            sum(left[index] - right[index] for index in sampled) / n
        )
    differences.sort()
    return {
        "difference": (sum(left) - sum(right)) / n,
        "ci95_low": quantile(differences, 0.025),
        "ci95_high": quantile(differences, 0.975),
    }


def mcnemar_exact(left: list[int], right: list[int]) -> dict[str, Any]:
    left_only = sum(a == 1 and b == 0 for a, b in zip(left, right))
    right_only = sum(a == 0 and b == 1 for a, b in zip(left, right))
    discordant = left_only + right_only
    if discordant == 0:
        p_value = 1.0
    else:
        smaller = min(left_only, right_only)
        lower_tail = sum(
            math.comb(discordant, k) for k in range(smaller + 1)
        ) / (2**discordant)
        p_value = min(1.0, 2.0 * lower_tail)
    return {
        "left_only": left_only,
        "right_only": right_only,
        "discordant": discordant,
        "two_sided_exact_p": p_value,
    }


def parse_run(specification: str) -> tuple[str, Path]:
    if "=" not in specification:
        raise ValueError("--run must have the form LABEL=PATH")
    label, raw_path = specification.split("=", 1)
    if not label.strip() or not raw_path.strip():
        raise ValueError("--run must have a non-empty label and path")
    return label.strip(), Path(raw_path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument(
        "--scope",
        choices=["all", "public_web"],
        default="all",
    )
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--metric", action="append")
    parser.add_argument("--bootstrap-samples", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()

    tasks = read_jsonl(args.tasks.resolve())
    all_task_ids = [task["id"] for task in tasks]
    task_ids = [
        task["id"]
        for task in tasks
        if args.scope == "all" or "HTTPS" in task["problem_zh"]
    ]
    if len(all_task_ids) != len(set(all_task_ids)):
        raise ValueError("task file contains duplicate ids")
    all_task_id_set = set(all_task_ids)
    task_id_set = set(task_ids)
    metrics = tuple(args.metric or CORE_METRICS)
    runs: dict[str, dict[str, Any]] = {}
    vectors: dict[str, dict[str, list[int]]] = {}

    for specification in args.run:
        label, path = parse_run(specification)
        if label in runs:
            raise ValueError(f"duplicate run label: {label}")
        summary = json.loads(path.read_text(encoding="utf-8-sig"))
        row_by_id = {row["task_id"]: row for row in summary["rows"]}
        if len(row_by_id) != len(summary["rows"]):
            raise ValueError(f"{label} contains duplicate task rows")
        unexpected = sorted(set(row_by_id) - all_task_id_set)
        if unexpected:
            raise ValueError(f"{label} has unexpected tasks: {unexpected}")
        row_by_id = {
            task_id: row
            for task_id, row in row_by_id.items()
            if task_id in task_id_set
        }
        active_failures = [
            failure
            for failure in summary.get("active_failures", [])
            if failure.get("task_id") in task_id_set
        ]
        summary_scope = summary.get("scope", "all")
        scoped_usage = (
            summary.get("usage", {})
            if summary_scope == args.scope
            else {}
        )
        vectors[label] = {
            metric: [
                int(bool(row_by_id.get(task_id, {}).get(metric, False)))
                for task_id in task_ids
            ]
            for metric in metrics
        }
        runs[label] = {
            "summary_path": str(path),
            "submitted": len(row_by_id),
            "expected": len(task_ids),
            "active_failure_count": len(active_failures),
            "summary_scope": summary_scope,
            "usage": scoped_usage,
            "metrics": {},
        }

    rng = random.Random(args.seed)
    for label in runs:
        for metric in metrics:
            runs[label]["metrics"][metric] = bootstrap_rate(
                vectors[label][metric],
                rng,
                args.bootstrap_samples,
            )

    comparisons = []
    labels = list(runs)
    for left_index, left_label in enumerate(labels):
        for right_label in labels[left_index + 1 :]:
            for metric in metrics:
                left = vectors[left_label][metric]
                right = vectors[right_label][metric]
                comparisons.append(
                    {
                        "left": left_label,
                        "right": right_label,
                        "metric": metric,
                        **bootstrap_paired_difference(
                            left,
                            right,
                            rng,
                            args.bootstrap_samples,
                        ),
                        "mcnemar": mcnemar_exact(left, right),
                    }
                )

    output = {
        "task_count": len(task_ids),
        "bootstrap_samples": args.bootstrap_samples,
        "seed": args.seed,
        "missing_or_failed_tasks_count_as_false": True,
        "runs": runs,
        "paired_comparisons": comparisons,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Full-run paired comparison",
        "",
        (
            f"Tasks: {len(task_ids)}; bootstrap samples: "
            f"{args.bootstrap_samples}; seed: {args.seed}. "
            "Missing or failed tasks count as false."
        ),
        "",
        (
            "Statistical pairing does not make differently defined metrics "
            "semantically comparable. In particular, frozen-corpus exact "
            "document ID and live-web exact Gold URL measure identity, not "
            "authoritative-source semantic equivalence."
        ),
        "",
        "## Coverage",
        "",
        "| Run | Submitted | Expected | Active failures |",
        "|---|---:|---:|---:|",
    ]
    for label, record in runs.items():
        lines.append(
            f"| {label} | {record['submitted']} | {record['expected']} | "
            f"{record['active_failure_count']} |"
        )
    lines.extend(
        [
            "",
            "## End-to-end model usage",
            "",
            (
                "Means are computed over submissions with recorded usage; "
                "the parenthesized value is that usage count. Accuracy "
                "denominators remain the preregistered task count above."
            ),
            "",
            (
                "| Run | Input tokens | Output tokens | Reasoning tokens | "
                "Model calls | Search calls | Model wall seconds |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    def usage_cell(record: dict[str, Any], name: str) -> str:
        statistic = record["usage"].get(name)
        if not statistic or not statistic.get("count"):
            return "—"
        return f"{statistic['mean']:.2f} ({statistic['count']})"

    for label, record in runs.items():
        lines.append(
            f"| {label} | "
            f"{usage_cell(record, 'e2e_input_tokens')} | "
            f"{usage_cell(record, 'e2e_output_tokens')} | "
            f"{usage_cell(record, 'e2e_reasoning_output_tokens')} | "
            f"{usage_cell(record, 'model_call_count')} | "
            f"{usage_cell(record, 'search_call_count')} | "
            f"{usage_cell(record, 'e2e_model_wall_seconds')} |"
        )
    lines.extend(
        [
        "",
        "## Per-run rates and task-bootstrap 95% CI",
        "",
        "| Run | Metric | Success | Rate | 95% CI |",
        "|---|---|---:|---:|---:|",
        ]
    )
    for label, record in runs.items():
        for metric, result in record["metrics"].items():
            success = sum(vectors[label][metric])
            lines.append(
                f"| {label} | {metric} | {success}/{len(task_ids)} | "
                f"{result['rate']:.3f} | "
                f"[{result['ci95_low']:.3f}, "
                f"{result['ci95_high']:.3f}] |"
            )
    lines.extend(
        [
            "",
            "## Paired comparisons",
            "",
            (
                "`Difference` is left minus right. McNemar uses an exact "
                "two-sided binomial test over discordant tasks."
            ),
            "",
            (
                "| Left | Right | Metric | Difference | 95% CI | "
                "Left only | Right only | Exact p |"
            ),
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for comparison in comparisons:
        test = comparison["mcnemar"]
        lines.append(
            f"| {comparison['left']} | {comparison['right']} | "
            f"{comparison['metric']} | {comparison['difference']:.3f} | "
            f"[{comparison['ci95_low']:.3f}, "
            f"{comparison['ci95_high']:.3f}] | "
            f"{test['left_only']} | {test['right_only']} | "
            f"{test['two_sided_exact_p']:.4g} |"
        )
    args.markdown_out.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
