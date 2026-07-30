"""Duplicate and private-label leakage audit for SearchWorthyOR-100."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import itertools
import json
import math
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sklearn.feature_extraction import DictVectorizer
from sklearn.tree import DecisionTreeClassifier

from validate_dataset_schema import Issue, canonical_bytes, issue, load_jsonl, sha256_file


PUBLIC_FORBIDDEN_KEYS = {
    "answer",
    "reference_answer",
    "gold",
    "solution",
    "solver_results",
    "decision_certificate",
    "typed_patch",
    "patch_class",
    "evidence_mode",
    "evidence_id",
    "evidence_ids",
    "source_passport",
    "applicability",
    "model_hashes",
    "optimal_actions",
    "optimal_action",
    "acceptable_actions",
    "projected_action",
    "objective_value",
    "before_hash",
    "after_hash",
    "family",
}
PUBLIC_FORBIDDEN_MARKERS = (
    "gurobi",
    "copt",
    "参考答案",
    "标准答案",
    "最优解为",
    "最优值为",
    "objective value",
    "optimal action",
    "source_id",
    "source passport",
    "typed patch",
)
PATCH_LABELS = (
    "eligibility_domain",
    "temporal_coupling",
    "conditional_auxiliary",
    "quota_risk_service_objective",
)
EVIDENCE_ROLE_MARKERS = (
    "distractor",
    "applicable",
    "fresh-private",
    "real-web",
    "old_version",
    "wrong_jurisdiction",
    "wrong_entity",
    "non_authoritative",
    "web-d",
)


@dataclasses.dataclass
class AuditReport:
    errors: list[Issue] = dataclasses.field(default_factory=list)
    warnings: list[Issue] = dataclasses.field(default_factory=list)
    stats: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [entry.as_dict() for entry in self.errors],
            "warnings": [entry.as_dict() for entry in self.warnings],
            "stats": self.stats,
        }


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def normalized_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def _metadata_features(task: Mapping[str, Any]) -> dict[str, str]:
    entity = str(task.get("entity", ""))
    task_id = str(task.get("id", ""))
    id_digits = "".join(character for character in task_id if character.isdigit())
    entity_digits = "".join(character for character in entity if character.isdigit())
    interfaces = task.get("allowed_retrieval_interfaces")
    interface = (
        "|".join(sorted(str(value) for value in interfaces))
        if isinstance(interfaces, list)
        else str(interfaces or "")
    )
    features = {
        "decision_month_day": str(task.get("decision_time", ""))[5:],
        "jurisdiction": normalize_text(str(task.get("jurisdiction", ""))),
        "retrieval_interface": normalize_text(interface),
        "entity_digit_signature": entity_digits,
        "entity_suffix": normalize_text(entity[-8:]),
        "id_last_digit": id_digits[-1:] if id_digits else "",
        "id_last_two_digits": id_digits[-2:] if id_digits else "",
    }
    if id_digits:
        numeric_id = int(id_digits)
        for modulus in range(2, 17):
            features[f"id_mod_{modulus}"] = str(numeric_id % modulus)
    return features


def _entity_prefix(value: str) -> str:
    return re.split(r"[（(]", normalize_text(value), maxsplit=1)[0].strip()


def _dense_ranks(values: Mapping[str, str | int]) -> dict[str, int]:
    ordered = {
        value: rank for rank, value in enumerate(sorted(set(values.values())))
    }
    return {task_id: ordered[value] for task_id, value in values.items()}


def _rank_bucket(rank: int, unique_count: int, buckets: int) -> str:
    return str(min(buckets - 1, rank * buckets // max(1, unique_count)))


def _augment_population_metadata_features(
    tasks: Sequence[Mapping[str, Any]],
    rows: list[tuple[str, str, dict[str, str]]],
) -> None:
    task_by_id = {
        str(task["id"]): task
        for task in tasks
        if isinstance(task.get("id"), str)
    }
    entity_values = {
        task_id: normalize_text(str(task.get("entity", "")))
        for task_id, task in task_by_id.items()
    }
    prefix_values = {
        task_id: _entity_prefix(str(task.get("entity", "")))
        for task_id, task in task_by_id.items()
    }
    date_values = {
        task_id: date.fromisoformat(str(task.get("decision_time"))).toordinal()
        for task_id, task in task_by_id.items()
    }
    entity_ranks = _dense_ranks(entity_values)
    prefix_ranks = _dense_ranks(prefix_values)
    date_ranks = _dense_ranks(date_values)
    physical_positions = {
        task_id: index
        for index, (task_id, _, _) in enumerate(rows)
    }
    decision_physical_order = {
        task_id: rank
        for rank, task_id in enumerate(
            sorted(
                task_by_id,
                key=lambda value: (
                    date_values[value],
                    physical_positions[value],
                    value,
                ),
            )
        )
    }
    min_day = min(date_values.values())
    entity_count = len(set(entity_values.values()))
    prefix_count = len(set(prefix_values.values()))
    date_count = len(set(date_values.values()))
    entity_date_diffs = {
        task_id: entity_ranks[task_id] - date_ranks[task_id]
        for task_id in task_by_id
    }
    prefix_date_diffs = {
        task_id: prefix_ranks[task_id] - date_ranks[task_id]
        for task_id in task_by_id
    }
    entity_diff_min = min(entity_date_diffs.values())
    entity_diff_span = max(entity_date_diffs.values()) - entity_diff_min + 1
    prefix_diff_min = min(prefix_date_diffs.values())
    prefix_diff_span = max(prefix_date_diffs.values()) - prefix_diff_min + 1

    for physical_index, (task_id, _, features) in enumerate(rows):
        entity_rank = entity_ranks[task_id]
        prefix_rank = prefix_ranks[task_id]
        date_rank = date_ranks[task_id]
        day_offset = date_values[task_id] - min_day
        for modulus in range(2, 17):
            features[f"entity_lex_rank_mod_{modulus}"] = str(
                entity_rank % modulus
            )
            features[f"entity_prefix_rank_mod_{modulus}"] = str(
                prefix_rank % modulus
            )
            features[f"decision_rank_mod_{modulus}"] = str(
                date_rank % modulus
            )
            features[f"decision_day_offset_mod_{modulus}"] = str(
                day_offset % modulus
            )
            features[f"entity_minus_decision_rank_mod_{modulus}"] = str(
                (entity_rank - date_rank) % modulus
            )
            features[f"prefix_minus_decision_rank_mod_{modulus}"] = str(
                (prefix_rank - date_rank) % modulus
            )
            features[f"physical_minus_entity_rank_mod_{modulus}"] = str(
                (physical_index - entity_rank) % modulus
            )
        for block_size in range(2, 21):
            features[f"physical_row_block_{block_size}"] = str(
                physical_index // block_size
            )
            features[f"entity_lex_rank_block_{block_size}"] = str(
                entity_rank // block_size
            )
            features[f"entity_prefix_rank_block_{block_size}"] = str(
                prefix_rank // block_size
            )
            features[f"decision_physical_rank_block_{block_size}"] = str(
                decision_physical_order[task_id] // block_size
            )
        for buckets in range(2, 21):
            entity_bucket = _rank_bucket(entity_rank, entity_count, buckets)
            prefix_bucket = _rank_bucket(prefix_rank, prefix_count, buckets)
            date_bucket = _rank_bucket(date_rank, date_count, buckets)
            features[f"entity_rank_bucket_{buckets}"] = entity_bucket
            features[f"entity_prefix_rank_bucket_{buckets}"] = prefix_bucket
            features[f"decision_rank_bucket_{buckets}"] = date_bucket
            features[f"entity_decision_bucket_pair_{buckets}"] = (
                f"{entity_bucket}|{date_bucket}"
            )
            features[f"prefix_decision_bucket_pair_{buckets}"] = (
                f"{prefix_bucket}|{date_bucket}"
            )
            features[f"entity_decision_diff_bucket_{buckets}"] = str(
                min(
                    buckets - 1,
                    (
                        (entity_date_diffs[task_id] - entity_diff_min)
                        * buckets
                    )
                    // max(1, entity_diff_span),
                )
            )
            features[f"prefix_decision_diff_bucket_{buckets}"] = str(
                min(
                    buckets - 1,
                    (
                        (prefix_date_diffs[task_id] - prefix_diff_min)
                        * buckets
                    )
                    // max(1, prefix_diff_span),
                )
            )
        features["entity_prefix"] = prefix_values[task_id]


def _fold(task_id: str, seed: str = "metadata-decoder-v1") -> int:
    return int(
        hashlib.sha256(f"{seed}|{task_id}".encode("utf-8")).hexdigest(),
        16,
    ) % 5


def _cross_validated_categorical_accuracy(
    rows: list[tuple[str, str, dict[str, str]]],
    feature_names: tuple[str, ...],
    *,
    seed: str = "metadata-decoder-v1",
) -> float:
    correct = 0
    total = 0
    labels = sorted({label for _, label, _ in rows})
    for held_out_fold in range(5):
        train = [
            row for row in rows if _fold(row[0], seed) != held_out_fold
        ]
        test = [
            row for row in rows if _fold(row[0], seed) == held_out_fold
        ]
        label_counts = Counter(label for _, label, _ in train)
        feature_counts: dict[tuple[str, str, str], int] = Counter()
        feature_value_counts: dict[str, set[str]] = {
            name: set() for name in feature_names
        }
        for _, label, features in train:
            for name in feature_names:
                value = features[name]
                feature_counts[(label, name, value)] += 1
                feature_value_counts[name].add(value)
        for _, actual, features in test:
            scores: dict[str, float] = {}
            for label in labels:
                scores[label] = math.log(
                    (label_counts[label] + 1) / (len(train) + len(labels))
                )
                for name in feature_names:
                    cardinality = max(1, len(feature_value_counts[name]))
                    scores[label] += math.log(
                        (
                            feature_counts[(label, name, features[name])] + 1
                        )
                        / (label_counts[label] + cardinality)
                    )
            predicted = max(labels, key=lambda label: (scores[label], label))
            correct += predicted == actual
            total += 1
    return correct / total if total else 0.0


def _majority_label(counts: Counter[str]) -> str:
    return max(sorted(counts), key=lambda label: (counts[label], label))


def _leave_one_out_categorical_accuracy(
    rows: list[tuple[str, str, dict[str, str]]],
    feature_names: str | tuple[str, ...],
) -> float:
    if isinstance(feature_names, str):
        feature_names = (feature_names,)
    grouped: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    keys: list[tuple[str, ...]] = []
    prior = Counter(label for _, label, _ in rows)
    for _, label, features in rows:
        key = tuple(features[name] for name in feature_names)
        keys.append(key)
        grouped[key][label] += 1
    correct = 0
    for (_, actual, _), key in zip(rows, keys, strict=True):
        matching = grouped[key].copy()
        matching[actual] -= 1
        if matching[actual] <= 0:
            del matching[actual]
        if not matching:
            matching = prior.copy()
            matching[actual] -= 1
            if matching[actual] <= 0:
                del matching[actual]
        correct += _majority_label(matching) == actual
    return correct / len(rows) if rows else 0.0


def _leave_one_out_interaction_summary(
    rows: list[tuple[str, str, dict[str, str]]],
    feature_names: tuple[str, ...],
    *,
    order: int,
) -> dict[str, Any]:
    scored = [
        {
            "features": list(names),
            "accuracy": _leave_one_out_categorical_accuracy(rows, names),
        }
        for names in itertools.combinations(feature_names, order)
    ]
    scored.sort(
        key=lambda row: (
            float(row["accuracy"]),
            tuple(str(value) for value in row["features"]),
        ),
        reverse=True,
    )
    return {
        "order": order,
        "evaluated_interactions": len(scored),
        "maximum_accuracy": float(scored[0]["accuracy"]) if scored else 0.0,
        "top_interactions": scored[:20],
    }


def _cross_validated_majority_accuracy(
    rows: list[tuple[str, str, dict[str, str]]],
    feature_name: str,
    *,
    seed: str,
) -> float:
    correct = 0
    total = 0
    for held_out_fold in range(5):
        train = [
            row for row in rows if _fold(row[0], seed) != held_out_fold
        ]
        test = [
            row for row in rows if _fold(row[0], seed) == held_out_fold
        ]
        prior = Counter(label for _, label, _ in train)
        by_value: dict[str, Counter[str]] = {}
        for _, label, features in train:
            by_value.setdefault(features[feature_name], Counter())[label] += 1
        for _, actual, features in test:
            counts = by_value.get(features[feature_name], prior)
            correct += _majority_label(counts) == actual
            total += 1
    return correct / total if total else 0.0


def _nearest_rank(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    rank = max(1, math.ceil(quantile * len(values)))
    return sorted(values)[rank - 1]


def _group_quota_completion_accuracy(
    rows: list[tuple[str, str, dict[str, str]]],
    test_splits: Iterable[Sequence[int]],
) -> float:
    labels = sorted({label for _, label, _ in rows})
    group_for_index = [
        (features["retrieval_interface"], features["entity_prefix"])
        for _, _, features in rows
    ]
    group_members: dict[tuple[str, str], set[int]] = defaultdict(set)
    for index, group in enumerate(group_for_index):
        group_members[group].add(index)
    all_indices = set(range(len(rows)))
    correct = 0
    total = 0
    for split in test_splits:
        test_indices = set(split)
        train_indices = all_indices - test_indices
        prior = Counter(rows[index][1] for index in train_indices)
        if not prior:
            prior = Counter({label: 1 for label in labels})
        fallback = _majority_label(prior)
        for index in sorted(test_indices):
            target_group = group_for_index[index]
            target_interface = target_group[0]
            target_size = len(group_members[target_group])
            templates = []
            for group, members in group_members.items():
                if (
                    group != target_group
                    and group[0] == target_interface
                    and len(members) == target_size
                    and members.issubset(train_indices)
                ):
                    templates.append(
                        Counter(rows[member][1] for member in members)
                    )
            if not templates:
                predicted = fallback
            else:
                expected = {
                    label: statistics.median(
                        template.get(label, 0) for template in templates
                    )
                    for label in labels
                }
                observed = Counter(
                    rows[member][1]
                    for member in group_members[target_group]
                    if member in train_indices
                )
                deficits = {
                    label: expected[label] - observed.get(label, 0)
                    for label in labels
                }
                maximum = max(deficits.values())
                winners = [
                    label
                    for label in labels
                    if deficits[label] == maximum
                ]
                predicted = winners[0] if len(winners) == 1 else fallback
            correct += predicted == rows[index][1]
            total += 1
    return correct / total if total else 0.0


def _group_quota_completion_audit(
    rows: list[tuple[str, str, dict[str, str]]],
) -> dict[str, Any]:
    loo = _group_quota_completion_accuracy(
        rows, ([index] for index in range(len(rows)))
    )
    fixed_splits = [
        [
            index
            for index, (task_id, _, _) in enumerate(rows)
            if _fold(task_id) == held_out_fold
        ]
        for held_out_fold in range(5)
    ]
    fixed = _group_quota_completion_accuracy(rows, fixed_splits)
    stress = []
    for seed in range(200):
        splits = [
            [
                index
                for index, (task_id, _, _) in enumerate(rows)
                if _fold(task_id, str(seed)) == held_out_fold
            ]
            for held_out_fold in range(5)
        ]
        stress.append(_group_quota_completion_accuracy(rows, splits))
    return {
        "group_key": "normalized_retrieval_interface+entity_prefix",
        "template": (
            "componentwise_median_counts_from_other_complete_groups_with_"
            "same_interface_and_public_group_size"
        ),
        "target_group_excluded_from_template": True,
        "global_release_quota_used": False,
        "leave_one_out_accuracy": loo,
        "fixed_5_fold_accuracy": fixed,
        "hash_fold_stress": {
            "seeds": len(stress),
            "mean_accuracy": sum(stress) / len(stress),
            "p95_accuracy": _nearest_rank(stress, 0.95),
            "maximum_accuracy": max(stress),
            "runs_at_or_above_threshold": sum(
                accuracy >= 0.35 for accuracy in stress
            ),
        },
        "maximum_gated_accuracy": max(
            loo, fixed, _nearest_rank(stress, 0.95)
        ),
    }


def _interface_minority_accuracy(
    rows: list[tuple[str, str, dict[str, str]]],
    test_splits: Iterable[Sequence[int]],
) -> float:
    labels = sorted({label for _, label, _ in rows})
    all_indices = set(range(len(rows)))
    correct = 0
    total = 0
    for split in test_splits:
        test_indices = sorted(set(split))
        train_indices = sorted(all_indices - set(test_indices))
        if not test_indices or not train_indices:
            raise ValueError("metadata decoder folds must have train and test rows")
        prior = Counter(rows[index][1] for index in train_indices)
        by_interface: dict[str, Counter[str]] = defaultdict(Counter)
        for index in train_indices:
            by_interface[rows[index][2]["retrieval_interface"]][
                rows[index][1]
            ] += 1
        for index in test_indices:
            counts = by_interface.get(
                rows[index][2]["retrieval_interface"],
                prior,
            )
            predicted = min(
                labels,
                key=lambda label: (counts[label], label),
            )
            correct += predicted == rows[index][1]
            total += 1
    return correct / total if total else 0.0


def _interface_minority_audit(
    rows: list[tuple[str, str, dict[str, str]]],
) -> dict[str, Any]:
    interface_count = len(
        {
            features["retrieval_interface"]
            for _, _, features in rows
        }
    )
    if interface_count < 2:
        return {
            "evaluated": False,
            "group_key": "normalized_retrieval_interface",
            "reason": (
                "a single public interface equals the full release population; "
                "the mandated global 25-per-class quota is outside the "
                "metadata-decoder threat model"
            ),
            "global_release_quota_used": False,
            "maximum_gated_accuracy": 0.0,
        }
    loo = _interface_minority_accuracy(
        rows, ([index] for index in range(len(rows)))
    )
    fixed_splits = [
        [
            index
            for index, (task_id, _, _) in enumerate(rows)
            if _fold(task_id) == held_out_fold
        ]
        for held_out_fold in range(5)
    ]
    fixed = _interface_minority_accuracy(rows, fixed_splits)
    stress = []
    for seed in range(200):
        splits = [
            [
                index
                for index, (task_id, _, _) in enumerate(rows)
                if _fold(task_id, str(seed)) == held_out_fold
            ]
            for held_out_fold in range(5)
        ]
        stress.append(_interface_minority_accuracy(rows, splits))
    return {
        "evaluated": True,
        "group_key": "normalized_retrieval_interface",
        "prediction_rule": (
            "least_frequent_training_label_with_lexicographic_tie_break"
        ),
        "global_release_quota_used": False,
        "leave_one_out_accuracy": loo,
        "fixed_5_fold_accuracy": fixed,
        "hash_fold_stress": {
            "seeds": len(stress),
            "mean_accuracy": sum(stress) / len(stress),
            "p95_accuracy": _nearest_rank(stress, 0.95),
            "maximum_accuracy": max(stress),
            "runs_at_or_above_threshold": sum(
                accuracy >= 0.35 for accuracy in stress
            ),
        },
        "maximum_gated_accuracy": max(
            loo, fixed, _nearest_rank(stress, 0.95)
        ),
    }


def _tree_decoder_accuracy(
    rows: list[tuple[str, str, dict[str, str]]],
    test_splits: Iterable[Sequence[int]],
) -> float:
    all_indices = set(range(len(rows)))
    correct = 0
    total = 0
    for split in test_splits:
        test_indices = sorted(set(split))
        train_indices = sorted(all_indices - set(test_indices))
        if not test_indices or not train_indices:
            raise ValueError("metadata decoder folds must have train and test rows")
        vectorizer = DictVectorizer(sparse=True, sort=True)
        train_matrix = vectorizer.fit_transform(
            rows[index][2] for index in train_indices
        )
        test_matrix = vectorizer.transform(
            rows[index][2] for index in test_indices
        )
        classifier = DecisionTreeClassifier(
            max_depth=4,
            min_samples_leaf=3,
            random_state=0,
        )
        classifier.fit(
            train_matrix, [rows[index][1] for index in train_indices]
        )
        predictions = classifier.predict(test_matrix)
        correct += sum(
            prediction == rows[index][1]
            for prediction, index in zip(
                predictions, test_indices, strict=True
            )
        )
        total += len(test_indices)
    return correct / total if total else 0.0


def _tree_decoder_audit(
    rows: list[tuple[str, str, dict[str, str]]],
) -> dict[str, Any]:
    loo = _tree_decoder_accuracy(
        rows, ([index] for index in range(len(rows)))
    )
    fixed_splits = [
        [
            index
            for index, (task_id, _, _) in enumerate(rows)
            if _fold(task_id) == held_out_fold
        ]
        for held_out_fold in range(5)
    ]
    fixed = _tree_decoder_accuracy(rows, fixed_splits)
    stress = []
    for seed in range(200):
        splits = [
            [
                index
                for index, (task_id, _, _) in enumerate(rows)
                if _fold(task_id, str(seed)) == held_out_fold
            ]
            for held_out_fold in range(5)
        ]
        stress.append(_tree_decoder_accuracy(rows, splits))
    p95 = _nearest_rank(stress, 0.95)
    return {
        "model": (
            "DictVectorizer+DecisionTreeClassifier(max_depth=4,"
            "min_samples_leaf=3,random_state=0)"
        ),
        "selection_scope": "all_registered_non_text_metadata_features",
        "leave_one_out_accuracy": loo,
        "fixed_5_fold_accuracy": fixed,
        "hash_fold_stress": {
            "seeds": len(stress),
            "mean_accuracy": sum(stress) / len(stress),
            "p95_accuracy": p95,
            "maximum_accuracy": max(stress),
            "runs_at_or_above_threshold": sum(
                accuracy >= 0.35 for accuracy in stress
            ),
        },
        "maximum_gated_accuracy": max(loo, fixed, p95),
    }


def metadata_decoder_audit(
    tasks: Sequence[Mapping[str, Any]],
    gold: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    gold_labels = {
        str(row["id"]): str(row["patch_class"])
        for row in gold
        if isinstance(row.get("id"), str)
        and isinstance(row.get("patch_class"), str)
    }
    rows = []
    task_count = len(tasks)
    for row_index, task in enumerate(tasks, start=1):
        task_id = task.get("id")
        if not isinstance(task_id, str) or task_id not in gold_labels:
            continue
        features = _metadata_features(task)
        for modulus in range(2, 17):
            features[f"release_row_mod_{modulus}"] = str(row_index % modulus)
        features["release_row_quartile"] = str(
            min(3, ((row_index - 1) * 4) // max(1, task_count))
        )
        features["release_row_decile"] = str(
            min(9, ((row_index - 1) * 10) // max(1, task_count))
        )
        rows.append((task_id, gold_labels[task_id], features))
    if len(rows) != 100 or len(set(gold_labels.values())) != 4:
        return {
            "evaluated": False,
            "reason": "requires the complete 100-row four-class release population",
        }
    base_feature_names = tuple(rows[0][2])
    _augment_population_metadata_features(tasks, rows)
    feature_names = tuple(rows[0][2])
    attacks = {
        name: _cross_validated_categorical_accuracy(rows, (name,))
        for name in feature_names
    }
    attacks["all_nonsemantic_metadata"] = _cross_validated_categorical_accuracy(
        rows,
        feature_names,
    )
    leave_one_out = {
        name: _leave_one_out_categorical_accuracy(rows, name)
        for name in feature_names
    }
    leave_one_out_interactions = {
        str(order): _leave_one_out_interaction_summary(
            rows, base_feature_names, order=order
        )
        for order in (2, 3)
    }
    stress_seeds = tuple(str(seed) for seed in range(200))
    hash_fold_stress: dict[str, dict[str, float | int]] = {}
    for name in feature_names:
        accuracies = [
            _cross_validated_majority_accuracy(rows, name, seed=seed)
            for seed in stress_seeds
        ]
        hash_fold_stress[name] = {
            "mean_accuracy": sum(accuracies) / len(accuracies),
            "p95_accuracy": _nearest_rank(accuracies, 0.95),
            "maximum_accuracy": max(accuracies),
            "runs_at_or_above_threshold": sum(
                accuracy >= 0.35 for accuracy in accuracies
            ),
        }
    random_baseline = 0.25
    threshold = 0.35
    fixed_maximum = max(attacks.values())
    loo_maximum = max(
        max(leave_one_out.values()),
        *(
            row["maximum_accuracy"]
            for row in leave_one_out_interactions.values()
        ),
    )
    stress_p95_maximum = max(
        row["p95_accuracy"] for row in hash_fold_stress.values()
    )
    group_quota = _group_quota_completion_audit(rows)
    interface_minority = _interface_minority_audit(rows)
    tree_decoder = _tree_decoder_audit(rows)
    gated_maximum = max(
        fixed_maximum,
        loo_maximum,
        stress_p95_maximum,
        attacks["all_nonsemantic_metadata"],
        tree_decoder["maximum_gated_accuracy"],
        group_quota["maximum_gated_accuracy"],
        interface_minority["maximum_gated_accuracy"],
    )
    return {
        "evaluated": True,
        "target": "patch_class",
        "protocol": (
            "fixed_5_fold_laplace_plus_deterministic_leave_one_out_majority"
            "_interactions_through_order_3_plus_200_hash_fold_majority_stress"
            "_plus_fold_fitted_tree_plus_cross_group_quota_completion"
            "_plus_interface_minority"
        ),
        "features_exclude_problem_text": True,
        "random_baseline": random_baseline,
        "fail_threshold": threshold,
        "attacks": attacks,
        "robustness": {
            "leave_one_out_majority": {
                "attacks": leave_one_out,
                "interaction_attacks": leave_one_out_interactions,
                "interaction_feature_scope": {
                    "features": list(base_feature_names),
                    "population_rank_features_are_single_or_precomposed_pairs": True,
                },
                "maximum_accuracy": loo_maximum,
            },
            "hash_fold_stress": {
                "seeds": len(stress_seeds),
                "tie_break": "lexicographically_largest_label",
                "gate_statistic": "maximum_per_feature_p95_accuracy",
                "features": hash_fold_stress,
                "maximum_p95_accuracy": stress_p95_maximum,
            },
            "cross_group_quota_completion": group_quota,
            "interface_minority_decoder": interface_minority,
            "fold_fitted_tree_decoder": tree_decoder,
            "registered_hard_gate_summary": {
                "fixed_single_feature_maximum": fixed_maximum,
                "leave_one_out_single_or_interaction_maximum": loo_maximum,
                "hash_fold_single_feature_maximum_p95": stress_p95_maximum,
                "all_are_release_gated": True,
            },
        },
        "maximum_accuracy": gated_maximum,
        "passed": gated_maximum < threshold,
    }


def _redacted_template_text(
    text: str,
    task: Mapping[str, Any],
    gold: Mapping[str, Any],
) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    for field in ("id", "entity", "jurisdiction", "decision_time"):
        token = task.get(field)
        if isinstance(token, str) and token:
            value = value.replace(unicodedata.normalize("NFKC", token).casefold(), " ")
    mappings = gold.get("claim_to_model_mapping")
    if isinstance(mappings, list):
        for mapping in mappings:
            if isinstance(mapping, Mapping):
                claim = mapping.get("claim_zh")
                if isinstance(claim, str) and claim:
                    value = value.replace(
                        unicodedata.normalize("NFKC", claim).casefold(), " "
                    )
    value = re.sub(r"\d+(?:[.\-:/]\d+)*", "#", value)
    value = re.sub(r"[a-f0-9]{16,}", "<hash>", value)
    return re.sub(r"\s+", "", value)


def _char_ngrams(value: str, width: int = 5) -> set[str]:
    if len(value) <= width:
        return {value} if value else set()
    return {value[index : index + width] for index in range(len(value) - width + 1)}


def _maximum_template_similarity(
    rows: list[tuple[str, str]],
) -> tuple[float, tuple[str, str] | None]:
    prepared = [(row_id, _char_ngrams(text)) for row_id, text in rows]
    maximum = 0.0
    pair: tuple[str, str] | None = None
    for left_index, (left_id, left) in enumerate(prepared):
        for right_id, right in prepared[left_index + 1 :]:
            union = left | right
            similarity = len(left & right) / len(union) if union else 1.0
            if similarity > maximum:
                maximum = similarity
                pair = (left_id, right_id)
    return maximum, pair


def _walk_keys(value: Any, path: str) -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield key, child_path
            yield from _walk_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def _duplicates(
    values: Iterable[tuple[str, str]],
    *,
    code: str,
    message: str,
) -> list[Issue]:
    seen: dict[str, str] = {}
    errors: list[Issue] = []
    for value, path in values:
        if value in seen:
            errors.append(issue(code, path, f"{message}; first seen at {seen[value]}"))
        else:
            seen[value] = path
    return errors


def _gold_private_tokens(
    gold: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    patch_class = gold.get("patch_class")
    if isinstance(patch_class, str):
        tokens.append((patch_class, "patch_class"))
    passport = gold.get("source_passport")
    if isinstance(passport, dict):
        for key in ("source_id", "source_uri", "url", "title"):
            value = passport.get(key)
            if isinstance(value, str) and len(normalize_text(value)) >= 6:
                tokens.append((value, f"source_passport.{key}"))
    evidence_ids = gold.get("evidence_ids")
    if isinstance(evidence_ids, list):
        for evidence_id in evidence_ids:
            evidence = evidence_by_id.get(str(evidence_id))
            if not isinstance(evidence, dict):
                continue
            content = evidence.get("content")
            if isinstance(content, str) and len(normalize_text(content)) >= 40:
                tokens.append((content, f"evidence[{evidence_id}].content"))
    return tokens


def _canonical_action_tokens(gold: Mapping[str, Any]) -> list[str]:
    certificate = gold.get("decision_certificate")
    if not isinstance(certificate, dict):
        return []
    tokens: list[str] = []
    for key in ("base_acceptable_actions", "patched_acceptable_actions"):
        actions = certificate.get(key)
        if not isinstance(actions, list):
            continue
        for action in actions:
            encoded = canonical_bytes(action).decode("utf-8")
            if len(encoded) >= 5:
                tokens.append(encoded)
    return tokens


def evidence_role_leakage_audit(
    evidence: Sequence[Mapping[str, Any]],
    gold: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    selected_ids = {
        str(applicability["selected_evidence_id"])
        for row in gold
        if isinstance((applicability := row.get("applicability")), dict)
        and isinstance(applicability.get("selected_evidence_id"), str)
    }
    direct_marker_hits: list[dict[str, Any]] = []
    invalid_ids: list[str] = []
    structural_signatures: dict[str, list[int]] = {}
    surface_signatures: dict[tuple[int, int, int], list[int]] = {}
    for index, row in enumerate(evidence):
        evidence_id = str(row.get("id", ""))
        if re.fullmatch(r"DOC-[0-9A-F]{16}", evidence_id) is None:
            invalid_ids.append(evidence_id)
        passport = row.get("source_passport")
        passport = passport if isinstance(passport, dict) else {}
        metadata_blob = normalize_text(
            "|".join(
                str(value)
                for value in (
                    evidence_id,
                    row.get("source_kind", ""),
                    passport.get("availability", ""),
                    passport.get("version", ""),
                    passport.get("issuer", ""),
                )
            )
        )
        for marker in EVIDENCE_ROLE_MARKERS:
            if marker in metadata_blob:
                direct_marker_hits.append(
                    {
                        "row_index": index,
                        "evidence_id": evidence_id,
                        "marker": marker,
                    }
                )
        def recursive_shape(value: Any) -> Any:
            if isinstance(value, Mapping):
                return {
                    str(key): recursive_shape(item)
                    for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
                }
            if isinstance(value, list):
                return {
                    "type": "list",
                    "length": len(value),
                    "item_shapes": [recursive_shape(item) for item in value],
                }
            if value is None:
                return "null"
            if isinstance(value, bool):
                return "bool"
            if isinstance(value, (int, float)):
                return "number"
            return "string"

        signature = canonical_bytes(
            {
                "row_shape": recursive_shape(row),
            }
        ).decode("utf-8")
        structural_signatures.setdefault(signature, []).append(index)
        content = str(row.get("content", ""))
        surface_signature = (
            len(content.encode("utf-8")),
            len(content),
            sum(ord(char) < 128 for char in content),
        )
        surface_signatures.setdefault(surface_signature, []).append(index)

    def maximum_selected_rate(values: Sequence[int]) -> dict[str, Any]:
        scored = []
        for modulus in range(2, 17):
            for residue in range(modulus):
                indices = [
                    index
                    for index, value in enumerate(values)
                    if value % modulus == residue
                ]
                if not indices:
                    continue
                selected = sum(
                    str(evidence[index].get("id", "")) in selected_ids
                    for index in indices
                )
                scored.append(
                    {
                        "modulus": modulus,
                        "residue": residue,
                        "rows": len(indices),
                        "selected": selected,
                        "selected_rate": selected / len(indices),
                    }
                )
        scored.sort(
            key=lambda row: (
                float(row["selected_rate"]),
                int(row["rows"]),
            ),
            reverse=True,
        )
        return {
            "maximum_selected_rate": (
                float(scored[0]["selected_rate"]) if scored else 0.0
            ),
            "worst_bucket": scored[0] if scored else None,
        }

    row_position = maximum_selected_rate(list(range(len(evidence))))
    id_hash_values = [
        (
            int(str(row.get("id", "")).split("-", 1)[1], 16)
            if re.fullmatch(r"DOC-[0-9A-F]{16}", str(row.get("id", "")))
            else index
        )
        for index, row in enumerate(evidence)
    ]
    id_hash = maximum_selected_rate(id_hash_values)
    signature_buckets = []
    for signature, indices in structural_signatures.items():
        selected = sum(
            str(evidence[index].get("id", "")) in selected_ids
            for index in indices
        )
        signature_buckets.append(
            {
                "signature": signature,
                "rows": len(indices),
                "selected": selected,
                "selected_rate": selected / len(indices),
            }
        )
    signature_buckets.sort(
        key=lambda row: (float(row["selected_rate"]), int(row["rows"])),
        reverse=True,
    )
    structural_signature = {
        "bucket_count": len(signature_buckets),
        "maximum_selected_rate": (
            float(signature_buckets[0]["selected_rate"])
            if signature_buckets
            else 0.0
        ),
        "worst_bucket": signature_buckets[0] if signature_buckets else None,
    }
    surface_buckets = []
    for signature, indices in surface_signatures.items():
        selected = sum(
            str(evidence[index].get("id", "")) in selected_ids
            for index in indices
        )
        surface_buckets.append(
            {
                "signature": list(signature),
                "rows": len(indices),
                "selected": selected,
                "selected_rate": selected / len(indices),
            }
        )
    surface_buckets.sort(
        key=lambda row: (float(row["selected_rate"]), int(row["rows"])),
        reverse=True,
    )
    surface_signature = {
        "bucket_count": len(surface_buckets),
        "maximum_selected_rate": (
            float(surface_buckets[0]["selected_rate"]) if surface_buckets else 0.0
        ),
        "worst_bucket": surface_buckets[0] if surface_buckets else None,
    }
    threshold = 0.50
    passed = (
        len(evidence) == 400
        and len(selected_ids) == 100
        and not direct_marker_hits
        and not invalid_ids
        and row_position["maximum_selected_rate"] < threshold
        and id_hash["maximum_selected_rate"] < threshold
        and structural_signature["maximum_selected_rate"] < threshold
        and surface_signature["maximum_selected_rate"] < threshold
    )
    return {
        "evaluated": True,
        "random_baseline": 0.25,
        "fail_threshold": threshold,
        "evidence_rows": len(evidence),
        "selected_evidence_ids": len(selected_ids),
        "direct_marker_hits": direct_marker_hits,
        "invalid_ids": invalid_ids,
        "row_position_modulo_attack": row_position,
        "id_hash_modulo_attack": id_hash,
        "structural_signature_attack": structural_signature,
        "surface_length_attack": surface_signature,
        "passed": passed,
    }


def audit_records(
    tasks: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    gold: Sequence[Mapping[str, Any]],
    *,
    model_files: Sequence[Path] = (),
    root: Path | None = None,
) -> AuditReport:
    report = AuditReport()

    task_id_values = [
        (str(row.get("id")), f"public/tasks_zh.jsonl:{index}.id")
        for index, row in enumerate(tasks, start=1)
        if isinstance(row.get("id"), str)
    ]
    base_values = [
        (str(row.get("base_id")), f"private/gold.jsonl:{index}.base_id")
        for index, row in enumerate(gold, start=1)
        if isinstance(row.get("base_id"), str)
    ]
    problem_values = [
        (
            normalized_hash(str(row.get("problem_zh"))),
            f"public/tasks_zh.jsonl:{index}.problem_zh",
        )
        for index, row in enumerate(tasks, start=1)
        if isinstance(row.get("problem_zh"), str)
    ]
    report.errors.extend(
        _duplicates(
            task_id_values,
            code="duplicate.task_id",
            message="duplicate public task id",
        )
    )
    report.errors.extend(
        _duplicates(
            base_values,
            code="duplicate.base_id",
            message="each task must use a different base_id",
        )
    )
    report.errors.extend(
        _duplicates(
            problem_values,
            code="duplicate.problem_text",
            message="NFKC/whitespace-normalized task text is duplicated",
        )
    )

    evidence_id_values: list[tuple[str, str]] = []
    evidence_hash_values: list[tuple[str, str]] = []
    source_version_values: list[tuple[str, str]] = []
    evidence_by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(evidence, start=1):
        row_path = f"private/evidence_corpus.jsonl:{index}"
        evidence_id = row.get("id")
        if isinstance(evidence_id, str):
            evidence_id_values.append((evidence_id, f"{row_path}.id"))
            evidence_by_id[evidence_id] = row
        content = row.get("content")
        if isinstance(content, str):
            evidence_hash_values.append(
                (normalized_hash(content), f"{row_path}.content")
            )
        passport = row.get("source_passport")
        if isinstance(passport, dict):
            source_uri = passport.get("source_uri", passport.get("url"))
            version = passport.get("version")
            content_hash = passport.get("content_sha256")
            if all(isinstance(value, str) for value in (source_uri, version, content_hash)):
                key = json.dumps(
                    [source_uri, version, content_hash],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                source_version_values.append((key, f"{row_path}.source_passport"))
    report.errors.extend(
        _duplicates(
            evidence_id_values,
            code="duplicate.evidence_id",
            message="duplicate evidence id",
        )
    )
    report.errors.extend(
        _duplicates(
            evidence_hash_values,
            code="duplicate.evidence_content",
            message="normalized evidence content is duplicated",
        )
    )
    report.errors.extend(
        _duplicates(
            source_version_values,
            code="duplicate.source_version",
            message="same source/version/content passport is duplicated",
        )
    )

    gold_by_id = {
        str(row.get("id")): row
        for row in gold
        if isinstance(row.get("id"), str)
    }
    public_blob = "\n".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) for row in tasks
    )
    normalized_public_blob = normalize_text(public_blob)
    raw_public_blob = public_blob.casefold()
    for index, row in enumerate(tasks, start=1):
        row_path = f"public/tasks_zh.jsonl:{index}"
        for key, key_path in _walk_keys(row, row_path):
            if key.casefold() in PUBLIC_FORBIDDEN_KEYS:
                report.errors.append(
                    issue(
                        "leakage.private_key_in_public",
                        key_path,
                        f"private-only key {key!r} appears in public data",
                    )
                )
        row_blob = json.dumps(row, ensure_ascii=False, sort_keys=True).casefold()
        for marker in (*PUBLIC_FORBIDDEN_MARKERS, *PATCH_LABELS):
            if marker.casefold() in row_blob:
                report.errors.append(
                    issue(
                        "leakage.private_marker_in_public",
                        row_path,
                        f"public task contains forbidden marker {marker!r}",
                    )
                )

    leaked_private_tokens = 0
    leaked_actions = 0
    for gold_id, gold_row in gold_by_id.items():
        for token, origin in _gold_private_tokens(gold_row, evidence_by_id):
            normalized_token = normalize_text(token)
            if normalized_token and normalized_token in normalized_public_blob:
                leaked_private_tokens += 1
                report.errors.append(
                    issue(
                        "leakage.private_token_in_public",
                        f"private/gold.jsonl[{gold_id}].{origin}",
                        "private source or evidence text occurs in public tasks",
                    )
                )
        for action_token in _canonical_action_tokens(gold_row):
            if action_token.casefold() in raw_public_blob:
                leaked_actions += 1
                report.errors.append(
                    issue(
                        "leakage.gold_action_in_public",
                        f"private/gold.jsonl[{gold_id}].decision_certificate",
                        "canonical gold action occurs verbatim in public tasks",
                    )
                )

    model_hash_values: list[tuple[str, str]] = []
    if root is not None:
        for model_path in model_files:
            relative = model_path.relative_to(root).as_posix()
            model_hash_values.append((sha256_file(model_path), relative))
    report.errors.extend(
        _duplicates(
            model_hash_values,
            code="duplicate.model_file",
            message="byte-identical model artifact is reused",
        )
    )

    split_bases: dict[str, set[str]] = defaultdict(set)
    for row in gold:
        split = row.get("split", row.get("release_split", "release"))
        base_id = row.get("base_id")
        if isinstance(split, str) and isinstance(base_id, str):
            split_bases[split].add(base_id)
    split_names = sorted(split_bases)
    for left_index, left in enumerate(split_names):
        for right in split_names[left_index + 1 :]:
            overlap = split_bases[left] & split_bases[right]
            if overlap:
                report.errors.append(
                    issue(
                        "leakage.base_across_splits",
                        "public/tasks_zh.jsonl",
                        f"base ids cross splits {left!r}/{right!r}: {sorted(overlap)}",
                    )
                )

    report.stats.update(
        {
            "tasks": len(tasks),
            "unique_task_ids": len(set(value for value, _ in task_id_values)),
            "unique_base_ids": len(set(value for value, _ in base_values)),
            "unique_problem_hashes": len(set(value for value, _ in problem_values)),
            "evidence_records": len(evidence),
            "unique_evidence_hashes": len(
                set(value for value, _ in evidence_hash_values)
            ),
            "model_files": len(model_files),
            "unique_model_hashes": len(set(value for value, _ in model_hash_values)),
            "private_token_leaks": leaked_private_tokens,
            "gold_action_leaks": leaked_actions,
            "splits": {key: len(value) for key, value in split_bases.items()},
        }
    )
    decoder = metadata_decoder_audit(tasks, gold)
    report.stats["metadata_decoder"] = decoder
    if decoder.get("evaluated") and not decoder.get("passed"):
        report.errors.append(
            issue(
                "leakage.metadata_decoder_above_random",
                "public/tasks_zh.jsonl",
                (
                    "a non-semantic metadata decoder predicts patch_class above "
                    f"the frozen threshold: {decoder['maximum_accuracy']:.3f} > "
                    f"{decoder['fail_threshold']:.3f}"
                ),
            )
        )
    evidence_role_audit = evidence_role_leakage_audit(evidence, gold)
    report.stats["evidence_role_leakage"] = evidence_role_audit
    if not evidence_role_audit["passed"]:
        report.errors.append(
            issue(
                "leakage.evidence_role_metadata",
                "private/evidence_corpus.jsonl",
                (
                    "retrievable evidence metadata, row position, or ID hash "
                    "predicts the selected evidence role above the frozen gate"
                ),
            )
        )
    task_by_id = {
        str(row["id"]): row
        for row in tasks
        if isinstance(row.get("id"), str)
    }
    applicable_private_templates: list[tuple[str, str]] = []
    public_templates: list[tuple[str, str]] = []
    for gold_row in gold:
        task_id = str(gold_row.get("id", ""))
        task = task_by_id.get(task_id)
        if task is None:
            continue
        problem = task.get("problem_zh")
        if isinstance(problem, str):
            public_templates.append(
                (
                    task_id,
                    _redacted_template_text(problem, task, gold_row),
                )
            )
        if gold_row.get("evidence_mode") != "fresh-private":
            continue
        evidence_ids = gold_row.get("evidence_ids")
        if not isinstance(evidence_ids, list) or len(evidence_ids) != 1:
            continue
        selected = evidence_by_id.get(str(evidence_ids[0]))
        content = selected.get("content") if isinstance(selected, Mapping) else None
        if isinstance(content, str):
            applicable_private_templates.append(
                (
                    task_id,
                    _redacted_template_text(content, task, gold_row),
                )
            )
    private_similarity, private_pair = _maximum_template_similarity(
        applicable_private_templates
    )
    public_similarity, public_pair = _maximum_template_similarity(public_templates)
    template_stats = {
        "method": "redacted_character_5gram_jaccard",
        "applicable_private_documents": {
            "rows": len(applicable_private_templates),
            "maximum_similarity": private_similarity,
            "most_similar_pair": private_pair,
            "fail_threshold": 0.9,
            "passed": private_similarity < 0.9,
        },
        "public_tasks": {
            "rows": len(public_templates),
            "maximum_similarity": public_similarity,
            "most_similar_pair": public_pair,
            "fail_threshold": 0.95,
            "passed": public_similarity < 0.95,
        },
    }
    report.stats["near_template_reuse"] = template_stats
    if not template_stats["applicable_private_documents"]["passed"]:
        report.errors.append(
            issue(
                "duplicate.private_document_template",
                "private/evidence_corpus.jsonl",
                (
                    "redacted applicable private documents exceed the frozen "
                    f"near-template threshold at pair {private_pair}"
                ),
            )
        )
    if not template_stats["public_tasks"]["passed"]:
        report.errors.append(
            issue(
                "duplicate.public_problem_template",
                "public/tasks_zh.jsonl",
                (
                    "redacted public problems exceed the frozen near-template "
                    f"threshold at pair {public_pair}"
                ),
            )
        )
    return report


def audit_dataset(root: Path) -> AuditReport:
    root = root.resolve()
    tasks, task_errors = load_jsonl(
        root / "public" / "tasks_zh.jsonl", "public/tasks_zh.jsonl"
    )
    evidence, evidence_errors = load_jsonl(
        root / "private" / "evidence_corpus.jsonl",
        "private/evidence_corpus.jsonl",
    )
    gold, gold_errors = load_jsonl(
        root / "private" / "gold.jsonl", "private/gold.jsonl"
    )
    model_files = sorted(
        path
        for path in (root / "models").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    report = audit_records(
        tasks,
        evidence,
        gold,
        model_files=model_files,
        root=root,
    )
    report.errors[:0] = [*task_errors, *evidence_errors, *gold_errors]
    return report


def _format_human(report: AuditReport) -> str:
    status = "PASS" if report.ok else "FAIL"
    lines = [
        f"SearchWorthyOR-100 duplicate/leakage gate: {status}",
        f"errors={len(report.errors)} warnings={len(report.warnings)}",
    ]
    for entry in report.errors:
        lines.append(f"ERROR [{entry.code}] {entry.path}: {entry.message}")
    for entry in report.warnings:
        lines.append(f"WARN  [{entry.code}] {entry.path}: {entry.message}")
    lines.append(f"stats={json.dumps(report.stats, ensure_ascii=False, sort_keys=True)}")
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
        help="optionally write the complete JSON report as UTF-8",
    )
    args = parser.parse_args(argv)
    report = audit_dataset(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                report.as_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_format_human(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
