#!/usr/bin/env python3
"""Search private-task label swaps that reduce registered metadata leakage.

This is a construction tool, not a release gate. Every emitted candidate must
still pass ``verify_frozen_assignment.py`` before it can be frozen.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

from audit_duplicates_and_leakage import (
    _augment_population_metadata_features,
    _fold,
    _metadata_features,
)
from build_dataset import PATCH_CLASSES, public_task_id


ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def metadata_rows(
    tasks: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, str]]]:
    rows: list[tuple[str, str, dict[str, str]]] = []
    for row_index, task in enumerate(tasks, start=1):
        features = _metadata_features(task)
        for modulus in range(2, 17):
            features[f"release_row_mod_{modulus}"] = str(row_index % modulus)
        features["release_row_quartile"] = str(
            min(3, ((row_index - 1) * 4) // len(tasks))
        )
        features["release_row_decile"] = str(
            min(9, ((row_index - 1) * 10) // len(tasks))
        )
        rows.append((str(task["id"]), "placeholder", features))
    _augment_population_metadata_features(tasks, rows)
    return [row[0] for row in rows], [row[2] for row in rows]


def equality_matrix(
    features: list[dict[str, str]], names: tuple[str, ...]
) -> np.ndarray:
    keys = [tuple(row[name] for name in names) for row in features]
    values = np.asarray(keys, dtype=object)
    if values.ndim == 1:
        values = values[:, None]
    return np.all(values[:, None, :] == values[None, :, :], axis=2)


def tie_ranks() -> np.ndarray:
    lexical = {label: rank for rank, label in enumerate(sorted(PATCH_CLASSES))}
    return np.asarray([lexical[label] for label in PATCH_CLASSES], dtype=np.int16)


def predictions_from_counts(counts: np.ndarray) -> np.ndarray:
    return np.argmax(counts * 8 + tie_ranks(), axis=-1)


class TargetAudit:
    def __init__(
        self,
        task_ids: list[str],
        features: list[dict[str, str]],
        stress_features: list[str],
        interactions: list[tuple[str, ...]],
    ) -> None:
        self.task_ids = task_ids
        self.stress_weights: dict[str, np.ndarray] = {}
        folds = np.asarray(
            [
                [_fold(task_id, str(seed)) for task_id in task_ids]
                for seed in range(200)
            ],
            dtype=np.int8,
        )
        different_fold = folds[:, :, None] != folds[:, None, :]
        for name in stress_features:
            same_value = equality_matrix(features, (name,))
            self.stress_weights[name] = (
                different_fold & same_value[None, :, :]
            ).astype(np.int8)
        not_self = ~np.eye(len(task_ids), dtype=bool)
        self.loo_weights: dict[tuple[str, ...], np.ndarray] = {}
        for names in interactions:
            weights = equality_matrix(features, names) & not_self
            empty = ~weights.any(axis=1)
            weights[empty] = not_self[empty]
            self.loo_weights[names] = weights.astype(np.int8)

    def evaluate(self, labels: np.ndarray) -> dict[str, Any]:
        one_hot = np.eye(4, dtype=np.int8)[labels]
        stress: dict[str, int] = {}
        for name, weights in self.stress_weights.items():
            counts = np.einsum("sij,jc->sic", weights, one_hot, optimize=True)
            predicted = predictions_from_counts(counts)
            accuracies = np.sum(predicted == labels[None, :], axis=1)
            stress[name] = int(np.sort(accuracies)[math.ceil(0.95 * 200) - 1])
        interactions: dict[str, int] = {}
        for names, weights in self.loo_weights.items():
            counts = weights @ one_hot
            predicted = predictions_from_counts(counts)
            interactions["+".join(names)] = int(np.sum(predicted == labels))
        values = list(stress.values()) + list(interactions.values())
        return {
            "objective": (
                max(values, default=0),
                sum(max(0, value - 32) for value in values),
                sum(values),
            ),
            "stress_p95_correct": stress,
            "interaction_correct": interactions,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--extra-audit", type=Path, action="append", default=[])
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--stress-floor", type=float, default=0.35)
    parser.add_argument("--loo-floor", type=float, default=0.35)
    parser.add_argument("--interaction-floor", type=float, default=0.35)
    parser.add_argument("--exhaustive-single-swap", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if len(args.start) != 100 or any(value not in "0123" for value in args.start):
        raise ValueError("--start must contain exactly 100 ordinals in 0..3")

    stress_features: list[str] = []
    loo_features: list[str] = []
    interactions: list[tuple[str, ...]] = []
    for audit_path in [args.audit, *args.extra_audit]:
        prior = json.loads(audit_path.read_text(encoding="utf-8"))[
            "metadata_decoder"
        ]["robustness"]
        stress_features.extend(
            name
            for name, result in prior["hash_fold_stress"]["features"].items()
            if float(result["p95_accuracy"]) >= args.stress_floor
        )
        loo_features.extend(
            name
            for name, accuracy in prior[
                "leave_one_out_majority"
            ]["attacks"].items()
            if float(accuracy) >= args.loo_floor
        )
        for result in prior[
            "leave_one_out_majority"
        ]["interaction_attacks"].values():
            interactions.extend(
                tuple(str(name) for name in row["features"])
                for row in result["top_interactions"]
                if float(row["accuracy"]) >= args.interaction_floor
            )
    stress_features = list(dict.fromkeys(stress_features))
    loo_features = list(dict.fromkeys(loo_features))
    interactions.extend((name,) for name in loo_features)
    interactions = list(dict.fromkeys(interactions))

    tasks = load_jsonl(ROOT / "public" / "tasks_zh.jsonl")
    task_ids, features = metadata_rows(tasks)
    row_by_task_id = {task_id: index for index, task_id in enumerate(task_ids)}
    internal_to_row = np.asarray(
        [row_by_task_id[public_task_id(index)] for index in range(100)],
        dtype=np.int16,
    )
    labels_internal = np.asarray([int(value) for value in args.start], dtype=np.int8)
    fixed = {index for index in range(100) if index % 10 >= 8}
    movable = [index for index in range(100) if index not in fixed]
    auditor = TargetAudit(task_ids, features, stress_features, interactions)

    def row_labels(values: np.ndarray) -> np.ndarray:
        result = np.empty(100, dtype=np.int8)
        result[internal_to_row] = values
        return result

    current = labels_internal.copy()
    current_result = auditor.evaluate(row_labels(current))
    best = current.copy()
    best_result = current_result
    accepted = 0
    candidate_count = 0
    if args.exhaustive_single_swap:
        for offset, left in enumerate(movable):
            for right in movable[offset + 1 :]:
                if current[left] == current[right]:
                    continue
                candidate = current.copy()
                candidate[left], candidate[right] = candidate[right], candidate[left]
                result = auditor.evaluate(row_labels(candidate))
                candidate_count += 1
                if result["objective"] < best_result["objective"]:
                    best = candidate
                    best_result = result
    else:
        rng = random.Random(args.seed)
        for iteration in range(args.iterations):
            left, right = rng.sample(movable, 2)
            if current[left] == current[right]:
                continue
            current[left], current[right] = current[right], current[left]
            result = auditor.evaluate(row_labels(current))
            temperature = max(0.001, 1.0 - iteration / args.iterations)
            improve = result["objective"] < current_result["objective"]
            plateau = (
                result["objective"][0] <= current_result["objective"][0]
                and rng.random() < 0.02 * temperature
            )
            if improve or plateau:
                current_result = result
                accepted += 1
                if result["objective"] < best_result["objective"]:
                    best = current.copy()
                    best_result = result
            else:
                current[left], current[right] = current[right], current[left]
            if best_result["objective"][0] <= 33 and iteration >= 2000:
                break

    result = {
        "seed": args.seed,
        "iterations_requested": args.iterations,
        "exhaustive_single_swap": args.exhaustive_single_swap,
        "single_swap_candidates_evaluated": candidate_count,
        "accepted_swaps": accepted,
        "stress_features": stress_features,
        "leave_one_out_features": loo_features,
        "interactions": [list(names) for names in interactions],
        "start_objective": auditor.evaluate(row_labels(labels_internal))["objective"],
        "best_objective": best_result["objective"],
        "best_assignment": "".join(str(int(value)) for value in best),
        "best_target_audit": best_result,
        "requires_full_verification": True,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
