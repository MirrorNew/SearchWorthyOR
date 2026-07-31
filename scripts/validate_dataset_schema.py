"""Fail-closed schema and semantic validation for SearchWorthyOR-100.

The validator intentionally recomputes release-critical facts instead of trusting
summary booleans in ``gold.jsonl`` or ``manifest.json``.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import hashlib
import itertools
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DATASET_ID = "SearchWorthyOR-100"
EXPECTED_TASKS = 100
EXPECTED_EVIDENCE_MODES = {"fresh-private": 80, "real-web": 20}
EXPECTED_FAMILIES = {
    "routing_transport": 10,
    "scheduling_workforce": 10,
    "production_capacity": 10,
    "assignment_matching": 10,
    "facility_network": 10,
    "inventory_supply_chain": 10,
    "energy_environment": 10,
    "healthcare_resources": 10,
    "finance_portfolio": 10,
    "telecom_service": 10,
}
EXPECTED_PATCH_CLASSES = {
    "eligibility_domain": 25,
    "temporal_coupling": 25,
    "conditional_auxiliary": 25,
    "quota_risk_service_objective": 25,
}
REQUIRED_PAYLOAD_FILES = (
    "public/tasks_zh.jsonl",
    "private/evidence_corpus.jsonl",
    "private/gold.jsonl",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UNRESOLVED_MARKERS = {
    "unresolved",
    "pending",
    "pending_review",
    "tbd",
    "todo",
    "unknown",
    "not_reviewed",
}
VALID_PATCH_OPERATIONS = {
    "add_constraint",
    "remove_constraint",
    "replace_constraint",
    "add_variable",
    "remove_variable",
    "change_domain",
    "change_index_set",
    "change_eligibility",
    "add_temporal_link",
    "add_condition",
    "add_auxiliary",
    "change_objective_term",
    "change_quota",
    "change_risk",
    "change_service_level",
}
TOLERANCE_MAX = 1e-5
MAX_ENUM_BINARY_VARS = 20


@dataclasses.dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ValidationReport:
    errors: list[Issue] = dataclasses.field(default_factory=list)
    warnings: list[Issue] = dataclasses.field(default_factory=list)
    stats: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, issues: Iterable[Issue]) -> None:
        self.errors.extend(issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
            "stats": self.stats,
        }


def issue(code: str, path: str, message: str) -> Issue:
    return Issue(code=code, path=path, message=message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


MANIFEST_RAW_HASH_PREFIXES = (
    "private/web_snapshots/raw/",
    "reports/rejected_snapshots/",
)
EXPECTED_FILE_HASH_POLICY = {
    "utf8_text_eol": "lf",
    "raw_prefixes": list(MANIFEST_RAW_HASH_PREFIXES),
}


def manifest_file_bytes(path: Path, root: Path) -> bytes:
    data = path.read_bytes()
    relative = path.relative_to(root).as_posix()
    if relative.startswith(MANIFEST_RAW_HASH_PREFIXES) or b"\x00" in data:
        return data
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value.lower()))


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _require_keys(
    record: Mapping[str, Any], keys: Iterable[str], path: str
) -> list[Issue]:
    return [
        issue("schema.missing_field", f"{path}.{key}", "required field is missing")
        for key in keys
        if key not in record
    ]


def _parse_json_file(path: Path, display_path: str) -> tuple[Any | None, list[Issue]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, [issue("file.missing", display_path, "required file is missing")]
    except UnicodeDecodeError as exc:
        return None, [
            issue("file.not_utf8", display_path, f"UTF-8 decoding failed: {exc}")
        ]
    try:
        return json.loads(text), []
    except json.JSONDecodeError as exc:
        return None, [
            issue(
                "json.invalid",
                display_path,
                f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            )
        ]


def load_jsonl(path: Path, display_path: str) -> tuple[list[dict[str, Any]], list[Issue]]:
    rows: list[dict[str, Any]] = []
    errors: list[Issue] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return rows, [issue("file.missing", display_path, "required file is missing")]
    except UnicodeDecodeError as exc:
        return rows, [
            issue("file.not_utf8", display_path, f"UTF-8 decoding failed: {exc}")
        ]
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        row_path = f"{display_path}:{line_number}"
        if not line:
            errors.append(
                issue("jsonl.blank_line", row_path, "blank JSONL lines are forbidden")
            )
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                issue(
                    "jsonl.invalid",
                    row_path,
                    f"invalid JSON at column {exc.colno}: {exc.msg}",
                )
            )
            continue
        if not isinstance(value, dict):
            errors.append(
                issue("jsonl.not_object", row_path, "each JSONL row must be an object")
            )
            continue
        rows.append(value)
    return rows, errors


def _parse_iso_datetime(value: Any) -> dt.datetime | None:
    if not _is_nonempty_string(value):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed_date = dt.date.fromisoformat(text)
        except ValueError:
            return None
        parsed = dt.datetime.combine(parsed_date, dt.time.min)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _canonical_actions(
    actions: Any, path: str
) -> tuple[set[bytes], list[Issue]]:
    errors: list[Issue] = []
    if not isinstance(actions, list) or not actions:
        return set(), [
            issue(
                "certificate.actions_missing",
                path,
                "a non-empty complete optimal-action list is required",
            )
        ]
    result: set[bytes] = set()
    for index, action in enumerate(actions):
        if action is None or action == "" or action == [] or action == {}:
            errors.append(
                issue(
                    "certificate.empty_action",
                    f"{path}[{index}]",
                    "empty actions are forbidden",
                )
            )
            continue
        try:
            encoded = canonical_bytes(action)
        except (TypeError, ValueError) as exc:
            errors.append(
                issue(
                    "certificate.invalid_action",
                    f"{path}[{index}]",
                    f"action is not canonical JSON: {exc}",
                )
            )
            continue
        if encoded in result:
            errors.append(
                issue(
                    "certificate.duplicate_action",
                    f"{path}[{index}]",
                    "duplicate optimal action",
                )
            )
        result.add(encoded)
    return result, errors


def _objective_fingerprint_from_ir(ir: Mapping[str, Any]) -> str | None:
    sense = ir.get("sense")
    objective = ir.get("objective")
    if sense not in {"min", "max"} or not isinstance(objective, dict):
        return None
    return sha256_json(objective)


def _objective_fingerprint(base_audit: Mapping[str, Any]) -> str | None:
    for key in ("objective_fingerprint", "objective_hash"):
        value = base_audit.get(key)
        if _is_sha256(value):
            return str(value).lower()
    objective = base_audit.get("objective")
    sense = base_audit.get("sense")
    if isinstance(objective, dict) and sense in {"min", "max"}:
        return sha256_json(objective)
    return None


def validate_public_task(record: Mapping[str, Any], path: str) -> list[Issue]:
    errors = _require_keys(record, ("id", "problem_zh"), path)
    if not _is_nonempty_string(record.get("id")):
        errors.append(issue("task.id_invalid", f"{path}.id", "id must be non-empty"))
    if "base_id" in record and not _is_nonempty_string(record.get("base_id")):
        errors.append(
            issue("task.base_id_invalid", f"{path}.base_id", "base_id must be non-empty")
        )
    text = record.get("problem_zh")
    if not _is_nonempty_string(text):
        errors.append(
            issue("task.problem_missing", f"{path}.problem_zh", "Chinese task text is empty")
        )
    elif len(text.strip()) < 40:
        errors.append(
            issue(
                "task.problem_too_short",
                f"{path}.problem_zh",
                "task text must contain at least 40 characters",
            )
        )
    return errors


def _validate_frozen_passport(
    passport: Mapping[str, Any],
    applicability: Mapping[str, Any],
    path: str,
    *,
    evidence_mode: str | None,
) -> list[Issue]:
    """Validate the dataset's compact passport/applicability representation."""

    errors = _require_keys(
        passport,
        (
            "authority",
            "availability",
            "issuer",
            "jurisdiction",
            "subject_scope",
            "version",
            "issued_at",
            "effective_from",
        ),
        path,
    )
    errors.extend(
        _require_keys(
            applicability,
            (
                "status",
                "authority_valid",
                "decision_time",
                "jurisdiction",
                "jurisdiction_match",
                "subject",
                "subject_scope_match",
                "effective_at_decision",
                "exception_inactive_or_resolved",
                "unique_applicable_source",
                "selected_evidence_id",
                "comparison",
            ),
            f"{path}.applicability",
        )
    )
    for key in (
        "authority",
        "availability",
        "issuer",
        "jurisdiction",
        "subject_scope",
        "version",
    ):
        if not _is_nonempty_string(passport.get(key)):
            errors.append(
                issue(
                    "source.passport_field_empty",
                    f"{path}.{key}",
                    "passport field must be non-empty",
                )
            )
    if passport.get("content_sha256") is not None and not _is_sha256(
        passport.get("content_sha256")
    ):
        errors.append(
            issue(
                "source.hash_invalid",
                f"{path}.content_sha256",
                "content_sha256 must be SHA-256 when present",
            )
        )
    if not _is_nonempty_string(passport.get("authority")):
        errors.append(
            issue(
                "source.not_authoritative",
                f"{path}.authority",
                "authority classification must be non-empty",
            )
        )
    if passport.get("authoritative") is not True:
        errors.append(
            issue(
                "source.not_authoritative",
                f"{path}.authoritative",
                "gold-linked passport must explicitly set authoritative=true",
            )
        )
    if evidence_mode == "fresh-private":
        if passport.get("generated_after_base_freeze") is not True:
            errors.append(
                issue(
                    "source.not_generated_after_freeze",
                    f"{path}.generated_after_base_freeze",
                    "fresh-private evidence must be generated after base freeze",
                )
            )
        if not _is_sha256(passport.get("base_freeze_sha256")):
            errors.append(
                issue(
                    "source.base_freeze_hash_invalid",
                    f"{path}.base_freeze_sha256",
                    "fresh-private passport requires the frozen base hash",
                )
            )
    if evidence_mode == "real-web":
        url = passport.get("url")
        if not _is_nonempty_string(url) or not str(url).startswith(
            ("https://", "http://")
        ):
            errors.append(
                issue(
                    "source.web_uri_invalid",
                    f"{path}.url",
                    "real-web passport requires an HTTP(S) URL",
                )
            )
        if not _is_sha256(passport.get("snapshot_sha256")):
            errors.append(
                issue(
                    "source.snapshot_hash_invalid",
                    f"{path}.snapshot_sha256",
                    "real-web passport requires a frozen snapshot hash",
                )
            )
        if _parse_iso_datetime(passport.get("fetched_at")) is None:
            errors.append(
                issue(
                    "source.fetched_at_invalid",
                    f"{path}.fetched_at",
                    "real-web fetched_at must be ISO-8601",
                )
            )

    if str(applicability.get("status", "")).lower() not in {"pass", "applicable"}:
        errors.append(
            issue(
                "source.not_applicable",
                f"{path}.applicability.status",
                "gold-linked applicability status must pass",
            )
        )
    for key in (
        "authority_valid",
        "jurisdiction_match",
        "subject_scope_match",
        "effective_at_decision",
        "exception_inactive_or_resolved",
        "unique_applicable_source",
    ):
        if applicability.get(key) is not True:
            errors.append(
                issue(
                    f"source.{key}_false",
                    f"{path}.applicability.{key}",
                    f"{key} must be explicitly true",
                )
            )
    if passport.get("jurisdiction") != applicability.get("jurisdiction"):
        errors.append(
            issue(
                "source.wrong_jurisdiction",
                f"{path}.jurisdiction",
                "passport jurisdiction differs from task applicability",
            )
        )
    if evidence_mode == "fresh-private":
        subject = applicability.get("subject")
        scope = passport.get("subject_scope")
        if _is_nonempty_string(subject) and _is_nonempty_string(scope):
            if str(subject) not in str(scope):
                errors.append(
                    issue(
                        "source.wrong_entity",
                        f"{path}.subject_scope",
                        "private passport scope does not include the required subject",
                    )
                )

    effective_from = _parse_iso_datetime(passport.get("effective_from"))
    effective_to_raw = passport.get("effective_to")
    effective_to = (
        None
        if effective_to_raw in (None, "")
        else _parse_iso_datetime(effective_to_raw)
    )
    decision_time = _parse_iso_datetime(applicability.get("decision_time"))
    issued_at = _parse_iso_datetime(passport.get("issued_at"))
    if effective_from is None:
        errors.append(
            issue(
                "source.effective_from_invalid",
                f"{path}.effective_from",
                "effective_from must be ISO-8601",
            )
        )
    if effective_to_raw not in (None, "") and effective_to is None:
        errors.append(
            issue(
                "source.effective_to_invalid",
                f"{path}.effective_to",
                "effective_to must be ISO-8601 or null",
            )
        )
    if decision_time is None:
        errors.append(
            issue(
                "source.decision_time_invalid",
                f"{path}.applicability.decision_time",
                "decision_time must be ISO-8601",
            )
        )
    if issued_at is None:
        errors.append(
            issue(
                "source.issued_at_invalid",
                f"{path}.issued_at",
                "issued_at must be ISO-8601",
            )
        )
    if effective_from and decision_time and decision_time < effective_from:
        errors.append(
            issue(
                "source.not_yet_effective",
                path,
                "source was not effective at decision_time",
            )
        )
    if effective_to and decision_time and decision_time > effective_to:
        errors.append(
            issue(
                "source.old_version",
                path,
                "source expired before decision_time",
            )
        )
    if effective_from and effective_to and effective_from > effective_to:
        errors.append(
            issue(
                "source.effective_period_invalid",
                path,
                "effective_from occurs after effective_to",
            )
        )
    selected = applicability.get("selected_evidence_id")
    comparison = applicability.get("comparison")
    if not _is_nonempty_string(selected):
        errors.append(
            issue(
                "source.selected_evidence_missing",
                f"{path}.applicability.selected_evidence_id",
                "selected evidence id must be non-empty",
            )
        )
    if not isinstance(comparison, list) or not comparison:
        errors.append(
            issue(
                "source.comparison_missing",
                f"{path}.applicability.comparison",
                "applicability comparison must be non-empty",
            )
        )
    else:
        selected_rows = [
            row
            for row in comparison
            if isinstance(row, dict)
            and row.get("evidence_id") == selected
            and row.get("applicable") is True
            and row.get("role") == "applicable"
        ]
        if len(selected_rows) != 1:
            errors.append(
                issue(
                    "source.selected_evidence_not_unique",
                    f"{path}.applicability.comparison",
                    "selected evidence must be the unique applicable comparison row",
                )
            )
    return errors


def validate_source_passport(
    passport: Any,
    applicability: Any,
    path: str,
    *,
    evidence_mode: str | None = None,
) -> list[Issue]:
    errors: list[Issue] = []
    if not isinstance(passport, dict):
        return [
            issue(
                "source.passport_missing",
                path,
                "source_passport must be a non-empty object",
            )
        ]
    if not isinstance(applicability, dict):
        return [
            issue(
                "source.applicability_missing",
                f"{path}.applicability",
                "applicability must be a non-empty object",
            )
        ]
    if "authority" in passport and "source_id" not in passport:
        return _validate_frozen_passport(
            passport,
            applicability,
            path,
            evidence_mode=evidence_mode,
        )
    passport_required = (
        "source_id",
        "publisher",
        "title",
        "document_type",
        "source_uri",
        "jurisdiction",
        "entity_scope",
        "version",
        "effective_from",
        "effective_to",
        "retrieved_at",
        "content_sha256",
        "authoritative",
    )
    applicability_required = (
        "verdict",
        "required_jurisdiction",
        "required_entity_scope",
        "decision_time",
        "jurisdiction_match",
        "entity_match",
        "version_current",
        "effective_at_decision_time",
        "exception_checked",
        "rationale",
    )
    errors.extend(_require_keys(passport, passport_required, path))
    errors.extend(
        _require_keys(applicability, applicability_required, f"{path}.applicability")
    )
    for key in (
        "source_id",
        "publisher",
        "title",
        "document_type",
        "source_uri",
        "jurisdiction",
        "entity_scope",
        "version",
    ):
        if not _is_nonempty_string(passport.get(key)):
            errors.append(
                issue(
                    "source.passport_field_empty",
                    f"{path}.{key}",
                    "passport field must be non-empty",
                )
            )
    if not _is_sha256(passport.get("content_sha256")):
        errors.append(
            issue(
                "source.hash_invalid",
                f"{path}.content_sha256",
                "content_sha256 must be a lowercase SHA-256 digest",
            )
        )
    if passport.get("authoritative") is not True:
        errors.append(
            issue(
                "source.not_authoritative",
                f"{path}.authoritative",
                "gold-linked evidence must be explicitly authoritative",
            )
        )
    if evidence_mode == "real-web":
        uri = str(passport.get("source_uri", ""))
        if not uri.startswith(("https://", "http://")):
            errors.append(
                issue(
                    "source.web_uri_invalid",
                    f"{path}.source_uri",
                    "real-web evidence requires an HTTP(S) source URI",
                )
            )
    if evidence_mode == "fresh-private":
        uri = str(passport.get("source_uri", ""))
        if not uri.startswith(("private://", "sealed://", "file://")):
            errors.append(
                issue(
                    "source.private_uri_invalid",
                    f"{path}.source_uri",
                    "fresh-private evidence requires a private/sealed URI",
                )
            )

    verdict = str(applicability.get("verdict", "")).strip().lower()
    if verdict not in {"applicable", "accept"}:
        errors.append(
            issue(
                "source.not_applicable",
                f"{path}.applicability.verdict",
                "gold-linked evidence must be adjudicated applicable",
            )
        )
    required_jurisdiction = applicability.get("required_jurisdiction")
    if passport.get("jurisdiction") != required_jurisdiction:
        errors.append(
            issue(
                "source.wrong_jurisdiction",
                f"{path}.jurisdiction",
                "passport jurisdiction does not match the task requirement",
            )
        )
    required_entity = applicability.get("required_entity_scope")
    source_entity = passport.get("entity_scope")
    if isinstance(source_entity, list):
        entity_matches = required_entity in source_entity
    else:
        entity_matches = source_entity == required_entity
    if not entity_matches:
        errors.append(
            issue(
                "source.wrong_entity",
                f"{path}.entity_scope",
                "passport entity scope does not match the task requirement",
            )
        )
    for key in (
        "jurisdiction_match",
        "entity_match",
        "version_current",
        "effective_at_decision_time",
        "exception_checked",
    ):
        if applicability.get(key) is not True:
            errors.append(
                issue(
                    f"source.{key}_false",
                    f"{path}.applicability.{key}",
                    f"{key} must be explicitly true for gold-linked evidence",
                )
            )
    if not _is_nonempty_string(applicability.get("rationale")):
        errors.append(
            issue(
                "source.rationale_missing",
                f"{path}.applicability.rationale",
                "applicability rationale must be non-empty",
            )
        )

    effective_from = _parse_iso_datetime(passport.get("effective_from"))
    effective_to = _parse_iso_datetime(passport.get("effective_to"))
    decision_time = _parse_iso_datetime(applicability.get("decision_time"))
    retrieved_at = _parse_iso_datetime(passport.get("retrieved_at"))
    if effective_from is None:
        errors.append(
            issue(
                "source.effective_from_invalid",
                f"{path}.effective_from",
                "effective_from must be ISO-8601",
            )
        )
    if effective_to is None:
        errors.append(
            issue(
                "source.effective_to_invalid",
                f"{path}.effective_to",
                "effective_to must be ISO-8601",
            )
        )
    if decision_time is None:
        errors.append(
            issue(
                "source.decision_time_invalid",
                f"{path}.applicability.decision_time",
                "decision_time must be ISO-8601",
            )
        )
    if retrieved_at is None:
        errors.append(
            issue(
                "source.retrieved_at_invalid",
                f"{path}.retrieved_at",
                "retrieved_at must be ISO-8601",
            )
        )
    if effective_from and effective_to and effective_from > effective_to:
        errors.append(
            issue(
                "source.effective_period_invalid",
                path,
                "effective_from occurs after effective_to",
            )
        )
    if decision_time and effective_from and decision_time < effective_from:
        errors.append(
            issue(
                "source.not_yet_effective",
                path,
                "source was not effective at decision_time",
            )
        )
    if decision_time and effective_to and decision_time > effective_to:
        errors.append(
            issue(
                "source.old_version",
                path,
                "source expired before decision_time",
            )
        )
    if passport.get("superseded_by") not in (None, "", []):
        errors.append(
            issue(
                "source.superseded",
                f"{path}.superseded_by",
                "gold-linked source is marked superseded",
            )
        )
    return errors


def _changed_leaf_kinds(before: Any, after: Any) -> set[str]:
    """Return semantic leaf-change kinds; numeric-only changes remain distinguishable."""

    if type(before) is not type(after):
        return {"type"}
    if isinstance(before, dict):
        kinds: set[str] = set()
        if set(before) != set(after):
            kinds.add("shape")
        for key in set(before) & set(after):
            child_kinds = _changed_leaf_kinds(before[key], after[key])
            if child_kinds:
                kinds.update(child_kinds)
        return kinds
    if isinstance(before, list):
        if before == after:
            return set()
        if len(before) != len(after):
            return {"shape", "structural"}
        kinds: set[str] = set()
        for left, right in zip(before, after):
            kinds.update(_changed_leaf_kinds(left, right))
        return kinds
    if before == after:
        return set()
    if _is_number(before) and _is_number(after):
        return {"numeric"}
    return {"structural"}


def _expression_change_is_numeric_only(before: str, after: str) -> bool:
    numeric = re.compile(r"(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?![\w.])")
    before_skeleton = " ".join(numeric.sub("<NUM>", before).split())
    after_skeleton = " ".join(numeric.sub("<NUM>", after).split())
    return before != after and before_skeleton == after_skeleton


def _validate_ops_typed_patch(
    patch: Mapping[str, Any],
    path: str,
    *,
    expected_patch_class: str | None,
) -> list[Issue]:
    errors = _require_keys(
        patch,
        (
            "ops",
            "minimality_check",
            "pure_numeric_parameter_fill",
            "structural",
            "base_model_hash",
            "patched_model_hash",
        ),
        path,
    )
    if expected_patch_class not in EXPECTED_PATCH_CLASSES:
        errors.append(
            issue(
                "patch.class_invalid",
                path,
                "gold patch_class is outside the frozen allowlist",
            )
        )
    if patch.get("structural") is not True:
        errors.append(
            issue(
                "patch.not_structural",
                f"{path}.structural",
                "structural must be explicitly true",
            )
        )
    if patch.get("pure_numeric_parameter_fill") is not False:
        errors.append(
            issue(
                "patch.numeric_only",
                f"{path}.pure_numeric_parameter_fill",
                "pure numeric parameter fill is forbidden",
            )
        )
    if not _is_nonempty_string(patch.get("minimality_check")):
        errors.append(
            issue(
                "patch.minimality_missing",
                f"{path}.minimality_check",
                "minimality check must be recorded",
            )
        )
    for key in ("base_model_hash", "patched_model_hash"):
        if not _is_sha256(patch.get(key)):
            errors.append(
                issue(
                    "patch.model_hash_invalid",
                    f"{path}.{key}",
                    f"{key} must be SHA-256",
                )
            )
    if _is_sha256(patch.get("base_model_hash")) and _is_sha256(
        patch.get("patched_model_hash")
    ):
        if patch["base_model_hash"].lower() == patch["patched_model_hash"].lower():
            errors.append(
                issue(
                    "patch.model_hashes_equal",
                    path,
                    "base and patched model file hashes must differ",
                )
            )
    ops = patch.get("ops")
    if not isinstance(ops, list) or not ops:
        return errors + [
            issue(
                "patch.ops_empty",
                f"{path}.ops",
                "typed patch must contain at least one operation",
            )
        ]
    valid_slot_types = {"variable_domain", "constraint", "variable"}
    for index, operation in enumerate(ops):
        operation_path = f"{path}.ops[{index}]"
        if not isinstance(operation, dict):
            errors.append(
                issue(
                    "patch.op_not_object",
                    operation_path,
                    "patch operation must be an object",
                )
            )
            continue
        errors.extend(
            _require_keys(
                operation,
                (
                    "op",
                    "slot_type",
                    "evidence_claim_id",
                    "model_slot_id",
                    "code_region_id",
                    "before_expression",
                    "after_expression",
                ),
                operation_path,
            )
        )
        if operation.get("op") not in {"add", "modify", "remove"}:
            errors.append(
                issue(
                    "patch.operation_invalid",
                    f"{operation_path}.op",
                    "operation must be add, modify or remove",
                )
            )
        if operation.get("slot_type") not in valid_slot_types:
            errors.append(
                issue(
                    "patch.slot_type_invalid",
                    f"{operation_path}.slot_type",
                    "slot_type is not a registered structural slot",
                )
            )
        for key in (
            "evidence_claim_id",
            "model_slot_id",
            "code_region_id",
        ):
            if not _is_nonempty_string(operation.get(key)):
                errors.append(
                    issue(
                        "patch.binding_missing",
                        f"{operation_path}.{key}",
                        "typed operation binding field must be non-empty",
                    )
                )
        before = operation.get("before_expression")
        after = operation.get("after_expression")
        op_kind = operation.get("op")
        if op_kind in {"modify", "remove"} and not _is_nonempty_string(before):
            errors.append(
                issue(
                    "patch.binding_missing",
                    f"{operation_path}.before_expression",
                    f"{op_kind} operation requires a non-empty before expression",
                )
            )
        if op_kind in {"modify", "add"} and not _is_nonempty_string(after):
            errors.append(
                issue(
                    "patch.binding_missing",
                    f"{operation_path}.after_expression",
                    f"{op_kind} operation requires a non-empty after expression",
                )
            )
        if op_kind == "add" and before not in (None, ""):
            errors.append(
                issue(
                    "patch.add_before_not_absent",
                    f"{operation_path}.before_expression",
                    "add operation must represent an absent before state",
                )
            )
        if op_kind == "remove" and after not in (None, ""):
            errors.append(
                issue(
                    "patch.remove_after_not_absent",
                    f"{operation_path}.after_expression",
                    "remove operation must represent an absent after state",
                )
            )
        if _is_nonempty_string(before) and _is_nonempty_string(after):
            if before == after:
                errors.append(
                    issue(
                        "patch.no_change",
                        operation_path,
                        "before and after expressions are identical",
                    )
                )
            elif _expression_change_is_numeric_only(before, after):
                errors.append(
                    issue(
                        "patch.numeric_only",
                        operation_path,
                        "operation changes only numeric literals",
                    )
                )
    return errors


def validate_typed_patch(
    patch: Any,
    path: str,
    *,
    expected_patch_class: str | None = None,
) -> list[Issue]:
    errors: list[Issue] = []
    if not isinstance(patch, dict):
        return [
            issue(
                "patch.missing",
                path,
                "typed_patch must be a non-empty object",
            )
        ]
    if "ops" in patch:
        return _validate_ops_typed_patch(
            patch,
            path,
            expected_patch_class=expected_patch_class,
        )
    required = (
        "patch_class",
        "claim_id",
        "model_slot",
        "operation",
        "before",
        "after",
        "before_hash",
        "after_hash",
        "base_model_hash",
        "patched_model_hash",
        "structural",
    )
    errors.extend(_require_keys(patch, required, path))
    patch_class = patch.get("patch_class")
    if patch_class not in EXPECTED_PATCH_CLASSES:
        errors.append(
            issue(
                "patch.class_invalid",
                f"{path}.patch_class",
                "patch_class is not in the frozen allowlist",
            )
        )
    if expected_patch_class and patch_class != expected_patch_class:
        errors.append(
            issue(
                "patch.class_mismatch",
                f"{path}.patch_class",
                "typed patch class differs from the gold row",
            )
        )
    for key in ("claim_id", "model_slot"):
        if not _is_nonempty_string(patch.get(key)):
            errors.append(
                issue(
                    "patch.binding_missing",
                    f"{path}.{key}",
                    "claim-to-model binding field must be non-empty",
                )
            )
    operation = patch.get("operation")
    if operation not in VALID_PATCH_OPERATIONS:
        errors.append(
            issue(
                "patch.operation_invalid",
                f"{path}.operation",
                "operation must be a registered structural operation",
            )
        )
    before = patch.get("before")
    after = patch.get("after")
    if not isinstance(before, (dict, list)) or not before:
        errors.append(
            issue(
                "patch.before_empty",
                f"{path}.before",
                "before must be a non-empty structured model fragment",
            )
        )
    if not isinstance(after, (dict, list)) or not after:
        errors.append(
            issue(
                "patch.after_empty",
                f"{path}.after",
                "after must be a non-empty structured model fragment",
            )
        )
    before_hash = patch.get("before_hash")
    after_hash = patch.get("after_hash")
    if not _is_sha256(before_hash):
        errors.append(
            issue(
                "patch.before_hash_invalid",
                f"{path}.before_hash",
                "before_hash must be SHA-256",
            )
        )
    elif isinstance(before, (dict, list)) and before_hash.lower() != sha256_json(before):
        errors.append(
            issue(
                "patch.before_hash_mismatch",
                f"{path}.before_hash",
                "before_hash does not match canonical before content",
            )
        )
    if not _is_sha256(after_hash):
        errors.append(
            issue(
                "patch.after_hash_invalid",
                f"{path}.after_hash",
                "after_hash must be SHA-256",
            )
        )
    elif isinstance(after, (dict, list)) and after_hash.lower() != sha256_json(after):
        errors.append(
            issue(
                "patch.after_hash_mismatch",
                f"{path}.after_hash",
                "after_hash does not match canonical after content",
            )
        )
    if _is_sha256(before_hash) and _is_sha256(after_hash):
        if before_hash.lower() == after_hash.lower():
            errors.append(
                issue(
                    "patch.no_change",
                    path,
                    "before and after hashes must differ",
                )
            )
    base_model_hash = patch.get("base_model_hash")
    patched_model_hash = patch.get("patched_model_hash")
    if not _is_sha256(base_model_hash):
        errors.append(
            issue(
                "patch.base_model_hash_invalid",
                f"{path}.base_model_hash",
                "base_model_hash must be SHA-256",
            )
        )
    if not _is_sha256(patched_model_hash):
        errors.append(
            issue(
                "patch.patched_model_hash_invalid",
                f"{path}.patched_model_hash",
                "patched_model_hash must be SHA-256",
            )
        )
    if _is_sha256(base_model_hash) and _is_sha256(patched_model_hash):
        if base_model_hash.lower() == patched_model_hash.lower():
            errors.append(
                issue(
                    "patch.model_hashes_equal",
                    path,
                    "base and patched canonical model hashes must differ",
                )
            )
    if patch.get("structural") is not True:
        errors.append(
            issue(
                "patch.not_structural",
                f"{path}.structural",
                "structural must be explicitly true",
            )
        )
    if isinstance(before, (dict, list)) and isinstance(after, (dict, list)):
        change_kinds = _changed_leaf_kinds(before, after)
        if not change_kinds:
            errors.append(
                issue("patch.no_change", path, "before and after fragments are identical")
            )
        elif change_kinds <= {"numeric"}:
            errors.append(
                issue(
                    "patch.numeric_only",
                    path,
                    "purely numeric value replacement is not a structural typed patch",
                )
            )
        elif not ({"structural", "shape", "type"} & change_kinds):
            errors.append(
                issue(
                    "patch.structure_unproven",
                    path,
                    "the patch does not contain a machine-detectable structural change",
                )
            )
    return errors


def _contains_subvalue(container: Any, target: Any) -> bool:
    if container == target:
        return True
    if isinstance(container, dict):
        return any(_contains_subvalue(value, target) for value in container.values())
    if isinstance(container, list):
        return any(_contains_subvalue(value, target) for value in container)
    return False


def _evaluate_ir_assignment(
    ir: Mapping[str, Any],
    assignment: Mapping[str, Any],
    tolerance: float,
) -> tuple[float | None, list[Any] | None, bool, dict[str, float], list[Issue]]:
    """Independently evaluate one canonical binary-MILP assignment."""

    errors: list[Issue] = []
    variables = ir.get("variables")
    constraints = ir.get("constraints")
    objective = ir.get("objective")
    projection = ir.get("action_projection")
    if (
        not isinstance(variables, list)
        or not isinstance(constraints, list)
        or not isinstance(objective, dict)
        or not isinstance(projection, list)
    ):
        return None, None, False, {}, [
            issue(
                "model.ir_incomplete",
                "model",
                "variables, constraints, objective and action_projection are required",
            )
        ]
    variable_names = [
        variable.get("name") for variable in variables if isinstance(variable, dict)
    ]
    if (
        len(variable_names) != len(variables)
        or any(not _is_nonempty_string(name) for name in variable_names)
        or len(set(variable_names)) != len(variable_names)
    ):
        return None, None, False, {}, [
            issue(
                "model.variable_schema_invalid",
                "model.variables",
                "variables require unique non-empty names",
            )
        ]
    expected_names = set(variable_names)
    if set(assignment) != expected_names:
        errors.append(
            issue(
                "solver.assignment_variables_mismatch",
                "assignment",
                "assignment keys must exactly match canonical model variables",
            )
        )
    numeric_assignment: dict[str, float] = {}
    for name in variable_names:
        value = assignment.get(name)
        if not _is_number(value):
            errors.append(
                issue(
                    "solver.assignment_value_invalid",
                    f"assignment.{name}",
                    "assignment values must be finite numeric",
                )
            )
        else:
            numeric_assignment[name] = float(value)
    if errors:
        return None, None, False, {}, errors

    max_bound_violation = 0.0
    max_integrality_violation = 0.0
    for variable in variables:
        name = variable["name"]
        value = numeric_assignment[name]
        lower = variable.get("lb", 0.0)
        upper = variable.get("ub", 1.0)
        if not _is_number(lower) or not _is_number(upper):
            errors.append(
                issue(
                    "model.variable_bound_invalid",
                    f"model.variables[{name}]",
                    "variable bounds must be finite numeric",
                )
            )
            continue
        max_bound_violation = max(
            max_bound_violation,
            max(0.0, float(lower) - value),
            max(0.0, value - float(upper)),
        )
        if variable.get("vartype") in {"B", "I"}:
            max_integrality_violation = max(
                max_integrality_violation, abs(value - round(value))
            )

    objective_terms = objective.get("terms")
    if not isinstance(objective_terms, dict):
        errors.append(
            issue(
                "model.objective_terms_invalid",
                "model.objective.terms",
                "objective terms must be an object",
            )
        )
        return None, None, False, {}, errors
    unknown_objective_terms = set(objective_terms) - expected_names
    if unknown_objective_terms:
        errors.append(
            issue(
                "model.objective_unknown_variable",
                "model.objective.terms",
                f"unknown variables: {sorted(unknown_objective_terms)}",
            )
        )
    constant = objective.get("constant", 0.0)
    if not _is_number(constant) or any(
        not _is_number(coefficient) for coefficient in objective_terms.values()
    ):
        errors.append(
            issue(
                "model.objective_coefficient_invalid",
                "model.objective",
                "objective constant and coefficients must be finite numeric",
            )
        )
        return None, None, False, {}, errors
    objective_value = float(constant) + sum(
        float(coefficient) * numeric_assignment[name]
        for name, coefficient in objective_terms.items()
        if name in numeric_assignment
    )

    max_constraint_violation = 0.0
    for index, constraint in enumerate(constraints):
        if not isinstance(constraint, dict):
            errors.append(
                issue(
                    "model.constraint_invalid",
                    f"model.constraints[{index}]",
                    "constraint must be an object",
                )
            )
            continue
        terms = constraint.get("terms")
        sense = constraint.get("sense")
        rhs = constraint.get("rhs")
        if not isinstance(terms, dict) or sense not in {"<=", ">=", "=="}:
            errors.append(
                issue(
                    "model.constraint_schema_invalid",
                    f"model.constraints[{index}]",
                    "constraint requires terms and a supported sense",
                )
            )
            continue
        if not _is_number(rhs) or any(
            not _is_number(coefficient) for coefficient in terms.values()
        ):
            errors.append(
                issue(
                    "model.constraint_numeric_invalid",
                    f"model.constraints[{index}]",
                    "constraint rhs and coefficients must be finite numeric",
                )
            )
            continue
        unknown_terms = set(terms) - expected_names
        if unknown_terms:
            errors.append(
                issue(
                    "model.constraint_unknown_variable",
                    f"model.constraints[{index}].terms",
                    f"unknown variables: {sorted(unknown_terms)}",
                )
            )
            continue
        lhs = sum(
            float(coefficient) * numeric_assignment[name]
            for name, coefficient in terms.items()
        )
        rhs_value = float(rhs)
        if sense == "<=":
            violation = max(0.0, lhs - rhs_value)
        elif sense == ">=":
            violation = max(0.0, rhs_value - lhs)
        else:
            violation = abs(lhs - rhs_value)
        max_constraint_violation = max(max_constraint_violation, violation)

    if any(name not in expected_names for name in projection):
        errors.append(
            issue(
                "model.projection_unknown_variable",
                "model.action_projection",
                "action projection references an unknown variable",
            )
        )
        projected_action = None
    else:
        projected_action = [
            int(round(numeric_assignment[name])) for name in projection
        ]
    residuals = {
        "max_constraint_violation": max_constraint_violation,
        "integrality_violation": max_integrality_violation,
        "bound_violation": max_bound_violation,
    }
    feasible = all(value <= tolerance for value in residuals.values())
    return objective_value, projected_action, feasible, residuals, errors


def _enumerate_ir_optimal_actions(
    ir: Mapping[str, Any], tolerance: float
) -> tuple[set[bytes], float | None, list[Issue]]:
    """Recompute the full projected epsilon-optimal action set from canonical IR."""

    errors: list[Issue] = []
    variables = ir.get("variables")
    if not isinstance(variables, list) or not variables:
        return set(), None, [
            issue(
                "model.variables_missing",
                "model.variables",
                "non-empty binary variables are required for exact enumeration",
            )
        ]
    if len(variables) > MAX_ENUM_BINARY_VARS:
        return set(), None, [
            issue(
                "model.too_large_for_complete_enumeration",
                "model.variables",
                (
                    f"{len(variables)} variables exceed the frozen complete-enumeration "
                    f"limit {MAX_ENUM_BINARY_VARS}"
                ),
            )
        ]
    if any(
        not isinstance(variable, dict) or variable.get("vartype") != "B"
        for variable in variables
    ):
        return set(), None, [
            issue(
                "model.not_binary",
                "model.variables",
                "first-release completeness certificate requires binary variables only",
            )
        ]
    names = [variable.get("name") for variable in variables]
    if any(not _is_nonempty_string(name) for name in names) or len(set(names)) != len(
        names
    ):
        return set(), None, [
            issue(
                "model.variable_schema_invalid",
                "model.variables",
                "variables require unique non-empty names",
            )
        ]
    feasible: list[tuple[float, list[Any]]] = []
    for bits in itertools.product((0.0, 1.0), repeat=len(names)):
        assignment = dict(zip(names, bits, strict=True))
        objective, action, is_feasible, _, evaluation_errors = _evaluate_ir_assignment(
            ir, assignment, tolerance
        )
        if evaluation_errors:
            return set(), None, evaluation_errors
        if is_feasible and objective is not None and action is not None:
            feasible.append((objective, action))
    if not feasible:
        return set(), None, [
            issue(
                "model.enumeration_not_optimal",
                "model",
                "canonical IR has no feasible assignment",
            )
        ]
    sense = ir.get("sense")
    if sense == "min":
        best = min(value for value, _ in feasible)
        acceptable = [
            action for value, action in feasible if value <= best + tolerance
        ]
    elif sense == "max":
        best = max(value for value, _ in feasible)
        acceptable = [
            action for value, action in feasible if value >= best - tolerance
        ]
    else:
        return set(), None, [
            issue(
                "model.sense_invalid",
                "model.sense",
                "sense must be min or max",
            )
        ]
    return {canonical_bytes(action) for action in acceptable}, best, errors


def _validate_solver_assignment_against_ir(
    result: Mapping[str, Any],
    ir: Mapping[str, Any],
    path: str,
    tolerance: float,
) -> list[Issue]:
    errors: list[Issue] = []
    assignment = result.get("assignment")
    if not isinstance(assignment, dict):
        return [
            issue(
                "solver.assignment_missing",
                f"{path}.assignment",
                "solver assignment is required for independent recomputation",
            )
        ]
    objective, projected_action, feasible, residuals, evaluation_errors = (
        _evaluate_ir_assignment(ir, assignment, tolerance)
    )
    for entry in evaluation_errors:
        errors.append(issue(entry.code, f"{path}.{entry.path}", entry.message))
    if objective is not None and _is_number(result.get("objective")):
        if abs(objective - float(result["objective"])) > tolerance:
            errors.append(
                issue(
                    "solver.recomputed_objective_disagreement",
                    f"{path}.objective",
                    "reported objective differs from canonical-IR recomputation",
                )
            )
    if projected_action is not None and result.get("projected_action") != projected_action:
        errors.append(
            issue(
                "solver.recomputed_action_disagreement",
                f"{path}.projected_action",
                "reported projected action differs from canonical-IR recomputation",
            )
        )
    if not feasible:
        errors.append(
            issue(
                "solver.assignment_infeasible",
                f"{path}.assignment",
                "reported assignment violates canonical IR or integrality",
            )
        )
    for metric, recomputed in residuals.items():
        reported = result.get(metric)
        if _is_number(reported) and abs(float(reported) - recomputed) > tolerance:
            errors.append(
                issue(
                    "solver.residual_mismatch",
                    f"{path}.{metric}",
                    f"reported {metric} differs from recomputation",
                )
            )
    return errors


def _validate_exact_world(
    world: Any, path: str
) -> tuple[set[bytes], float | None, list[Issue]]:
    errors: list[Issue] = []
    if not isinstance(world, dict):
        return set(), None, [
            issue("solver.world_missing", path, "world solver result must be an object")
        ]
    exact = world.get("exact_enumeration")
    if not isinstance(exact, dict):
        return set(), None, [
            issue(
                "solver.exact_missing",
                f"{path}.exact_enumeration",
                "complete exact enumeration is required; incumbents are insufficient",
            )
        ]
    if str(exact.get("status", "")).upper() != "OPTIMAL":
        errors.append(
            issue(
                "solver.exact_not_optimal",
                f"{path}.exact_enumeration.status",
                "exact enumerator must report OPTIMAL",
            )
        )
    if exact.get("complete") is not True:
        errors.append(
            issue(
                "solver.action_set_incomplete",
                f"{path}.exact_enumeration.complete",
                "multiple-optima handling requires an explicitly complete action set",
            )
        )
    actions, action_errors = _canonical_actions(
        exact.get("optimal_actions"), f"{path}.exact_enumeration.optimal_actions"
    )
    errors.extend(action_errors)
    objective = exact.get("objective")
    if not _is_number(objective):
        errors.append(
            issue(
                "solver.objective_invalid",
                f"{path}.exact_enumeration.objective",
                "exact objective must be finite numeric",
            )
        )
        objective_value: float | None = None
    else:
        objective_value = float(objective)
    return actions, objective_value, errors


def validate_solver_results(
    solver_results: Any,
    path: str,
    *,
    tolerance: float,
    model_irs: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, set[bytes]], list[Issue]]:
    """Validate exact sets plus Gurobi/COPT membership for base and patched worlds."""

    errors: list[Issue] = []
    exact_sets: dict[str, set[bytes]] = {}
    if not isinstance(solver_results, dict):
        return exact_sets, [
            issue(
                "solver.results_missing",
                path,
                "solver_results must contain base and patched certificates",
            )
        ]
    if not _is_number(tolerance) or tolerance <= 0 or tolerance > TOLERANCE_MAX:
        errors.append(
            issue(
                "solver.tolerance_invalid",
                f"{path}.tolerance",
                f"tolerance must be in (0, {TOLERANCE_MAX}]",
            )
        )
        tolerance = 1e-6
    for world_name in ("base", "patched"):
        world_path = f"{path}.{world_name}"
        world = solver_results.get(world_name)
        exact_actions, exact_objective, world_errors = _validate_exact_world(
            world, world_path
        )
        errors.extend(world_errors)
        exact_sets[world_name] = exact_actions
        if not isinstance(world, dict):
            continue
        ir = model_irs.get(world_name) if model_irs is not None else None
        if ir is not None:
            recomputed_actions, recomputed_objective, enumeration_errors = (
                _enumerate_ir_optimal_actions(ir, tolerance)
            )
            for entry in enumeration_errors:
                errors.append(
                    issue(entry.code, f"{world_path}.{entry.path}", entry.message)
                )
            if recomputed_actions and exact_actions != recomputed_actions:
                errors.append(
                    issue(
                        "solver.exact_action_set_disagreement",
                        f"{world_path}.exact_enumeration.optimal_actions",
                        "declared complete action set differs from independent IR enumeration",
                    )
                )
            if (
                recomputed_objective is not None
                and exact_objective is not None
                and abs(recomputed_objective - exact_objective) > tolerance
            ):
                errors.append(
                    issue(
                        "solver.exact_objective_disagreement",
                        f"{world_path}.exact_enumeration.objective",
                        "exact objective differs from independent IR enumeration",
                    )
                )
        solver_actions: dict[str, bytes] = {}
        solver_objectives: dict[str, float] = {}
        for solver_name in ("gurobi", "copt"):
            result = world.get(solver_name)
            result_path = f"{world_path}.{solver_name}"
            if not isinstance(result, dict):
                errors.append(
                    issue(
                        "solver.backend_missing",
                        result_path,
                        f"{solver_name} result is required",
                    )
                )
                continue
            if result.get("solver") != solver_name:
                errors.append(
                    issue(
                        "solver.backend_identity_mismatch",
                        f"{result_path}.solver",
                        f"solver identity must be {solver_name!r}",
                    )
                )
            if not _is_nonempty_string(result.get("version")):
                errors.append(
                    issue(
                        "solver.version_missing",
                        f"{result_path}.version",
                        "solver version must be recorded",
                    )
                )
            if str(result.get("status", "")).upper() != "OPTIMAL":
                errors.append(
                    issue(
                        "solver.not_optimal",
                        f"{result_path}.status",
                        f"{solver_name} must report OPTIMAL",
                    )
                )
            if ir is not None:
                errors.extend(
                    _validate_solver_assignment_against_ir(
                        result, ir, result_path, tolerance
                    )
                )
            objective = result.get("objective")
            if not _is_number(objective):
                errors.append(
                    issue(
                        "solver.objective_invalid",
                        f"{result_path}.objective",
                        "solver objective must be finite numeric",
                    )
                )
            else:
                solver_objectives[solver_name] = float(objective)
                if (
                    exact_objective is not None
                    and abs(float(objective) - exact_objective) > tolerance
                ):
                    errors.append(
                        issue(
                            "solver.objective_disagreement",
                            f"{result_path}.objective",
                            "solver objective differs from exact enumeration",
                        )
                    )
            action = result.get("projected_action")
            if action is None:
                errors.append(
                    issue(
                        "solver.action_missing",
                        f"{result_path}.projected_action",
                        "solver projected action is required",
                    )
                )
            else:
                encoded = canonical_bytes(action)
                solver_actions[solver_name] = encoded
                if exact_actions and encoded not in exact_actions:
                    errors.append(
                        issue(
                            "solver.action_disagreement",
                            f"{result_path}.projected_action",
                            "solver incumbent is not in the complete optimal-action set",
                        )
                    )
            for metric in (
                "max_constraint_violation",
                "integrality_violation",
                "bound_violation",
            ):
                value = result.get(metric)
                if not _is_number(value) or float(value) > tolerance:
                    errors.append(
                        issue(
                            "solver.residual_invalid",
                            f"{result_path}.{metric}",
                            f"{metric} must be finite and within tolerance",
                        )
                    )
        if len(solver_objectives) == 2:
            values = list(solver_objectives.values())
            if abs(values[0] - values[1]) > tolerance:
                errors.append(
                    issue(
                        "solver.cross_backend_objective_disagreement",
                        world_path,
                        "Gurobi and COPT objectives disagree",
                    )
                )
        checks = world.get("checks")
        required_checks = (
            "all_optimal",
            "objectives_agree",
            "solver_actions_in_exact_set",
            "residuals_pass",
            "integrality_pass",
            "passed",
        )
        if not isinstance(checks, dict):
            errors.append(
                issue(
                    "solver.checks_missing",
                    f"{world_path}.checks",
                    "solver checks summary is required",
                )
            )
        else:
            for key in required_checks:
                if checks.get(key) is not True:
                    errors.append(
                        issue(
                            "solver.check_failed",
                            f"{world_path}.checks.{key}",
                            f"{key} must be explicitly true",
                        )
                    )
    return exact_sets, errors


def _validate_worlds_decision_certificate(
    certificate: Mapping[str, Any],
    path: str,
    *,
    base_id: str | None,
    objective_fingerprint: str | None,
    solver_action_sets: Mapping[str, set[bytes]] | None,
) -> list[Issue]:
    errors: list[Issue] = []
    if certificate.get("method") not in {
        "complete_binary_enumeration",
        "complete_action_set",
    }:
        errors.append(
            issue(
                "certificate.method_invalid",
                f"{path}.method",
                "certificate must use a complete action-set method",
            )
        )
    worlds = certificate.get("worlds")
    if not isinstance(worlds, dict):
        return errors + [
            issue(
                "certificate.worlds_missing",
                f"{path}.worlds",
                "base and patched world certificates are required",
            )
        ]
    action_sets: dict[str, set[bytes]] = {}
    fingerprints: dict[str, str] = {}
    for world_name in ("base", "patched"):
        world = worlds.get(world_name)
        world_path = f"{path}.worlds.{world_name}"
        if not isinstance(world, dict):
            errors.append(
                issue(
                    "certificate.world_missing",
                    world_path,
                    "world certificate must be an object",
                )
            )
            continue
        if world.get("action_set_complete") is not True:
            errors.append(
                issue(
                    "certificate.incomplete",
                    f"{world_path}.action_set_complete",
                    "incumbent-only action comparison is forbidden",
                )
            )
        actions, action_errors = _canonical_actions(
            world.get("optimal_actions"),
            f"{world_path}.optimal_actions",
        )
        action_sets[world_name] = actions
        errors.extend(action_errors)
        fingerprint = world.get("objective_fingerprint")
        if not _is_sha256(fingerprint):
            errors.append(
                issue(
                    "certificate.objective_missing",
                    f"{world_path}.objective_fingerprint",
                    "objective fingerprint must be SHA-256",
                )
            )
        else:
            fingerprints[world_name] = str(fingerprint).lower()
            if objective_fingerprint and fingerprints[world_name] != objective_fingerprint:
                errors.append(
                    issue(
                        "certificate.objective_mismatch",
                        f"{world_path}.objective_fingerprint",
                        "world objective differs from the registered single objective",
                    )
                )
        if "base_id" in world and base_id is not None and world.get("base_id") != base_id:
            errors.append(
                issue(
                    "certificate.base_id_mismatch",
                    f"{world_path}.base_id",
                    "both worlds must use the task's base_id",
                )
            )
    if (
        fingerprints.get("base")
        and fingerprints.get("patched")
        and fingerprints["base"] != fingerprints["patched"]
    ):
        errors.append(
            issue(
                "certificate.cross_world_objective_mismatch",
                path,
                "base and patched worlds must retain the same objective definition",
            )
        )
    recomputed = action_sets.get("base", set()) & action_sets.get("patched", set())
    declared = certificate.get("intersection")
    if not isinstance(declared, list):
        errors.append(
            issue(
                "certificate.intersection_missing",
                f"{path}.intersection",
                "declared intersection list is required",
            )
        )
    elif {canonical_bytes(action) for action in declared} != recomputed:
        errors.append(
            issue(
                "certificate.intersection_mismatch",
                f"{path}.intersection",
                "declared intersection differs from recomputation",
            )
        )
    if recomputed:
        errors.append(
            issue(
                "certificate.intersection_nonempty",
                path,
                "base and patched complete optimal-action sets must be disjoint",
            )
        )
    if certificate.get("intersection_empty") is not True:
        errors.append(
            issue(
                "certificate.intersection_flag_false",
                f"{path}.intersection_empty",
                "intersection_empty must be explicitly true",
            )
        )
    if certificate.get("passed") is not True:
        errors.append(
            issue(
                "certificate.not_passed",
                f"{path}.passed",
                "decision certificate must be marked passed",
            )
        )
    if solver_action_sets:
        for world_name in ("base", "patched"):
            if action_sets.get(world_name, set()) != solver_action_sets.get(
                world_name, set()
            ):
                errors.append(
                    issue(
                        "certificate.action_set_disagreement",
                        f"{path}.worlds.{world_name}.optimal_actions",
                        "certificate actions differ from independent enumeration",
                    )
                )
    return errors


def validate_decision_certificate(
    certificate: Any,
    path: str,
    *,
    base_id: str | None = None,
    objective_fingerprint: str | None = None,
    solver_action_sets: Mapping[str, set[bytes]] | None = None,
) -> list[Issue]:
    errors: list[Issue] = []
    if not isinstance(certificate, dict):
        return [
            issue(
                "certificate.missing",
                path,
                "decision_certificate must be a non-empty object",
            )
        ]
    if "worlds" in certificate:
        return _validate_worlds_decision_certificate(
            certificate,
            path,
            base_id=base_id,
            objective_fingerprint=objective_fingerprint,
            solver_action_sets=solver_action_sets,
        )
    method = certificate.get("certificate_method")
    if method not in {"complete_binary_enumeration", "complete_action_set"}:
        errors.append(
            issue(
                "certificate.method_invalid",
                f"{path}.certificate_method",
                "certificate must use a complete action-set method",
            )
        )
    if certificate.get("complete_action_sets") is not True:
        errors.append(
            issue(
                "certificate.incomplete",
                f"{path}.complete_action_sets",
                "incumbent-only or partial action sets are forbidden",
            )
        )
    if str(certificate.get("multiple_optima_handling", "")).lower() not in {
        "full_action_set",
        "complete_enumeration",
    }:
        errors.append(
            issue(
                "certificate.multiple_optima_unhandled",
                f"{path}.multiple_optima_handling",
                "multiple optima must be compared through complete action sets",
            )
        )
    base_actions, base_errors = _canonical_actions(
        certificate.get("base_acceptable_actions"),
        f"{path}.base_acceptable_actions",
    )
    patched_actions, patched_errors = _canonical_actions(
        certificate.get("patched_acceptable_actions"),
        f"{path}.patched_acceptable_actions",
    )
    errors.extend(base_errors)
    errors.extend(patched_errors)
    recomputed_intersection = base_actions & patched_actions
    declared_intersection = certificate.get("intersection")
    if not isinstance(declared_intersection, list):
        errors.append(
            issue(
                "certificate.intersection_missing",
                f"{path}.intersection",
                "declared intersection list is required",
            )
        )
    else:
        declared_set = {canonical_bytes(action) for action in declared_intersection}
        if declared_set != recomputed_intersection:
            errors.append(
                issue(
                    "certificate.intersection_mismatch",
                    f"{path}.intersection",
                    "declared intersection differs from the recomputed intersection",
                )
            )
    if recomputed_intersection:
        errors.append(
            issue(
                "certificate.intersection_nonempty",
                path,
                "base and patched acceptable-action sets must be disjoint",
            )
        )
    if certificate.get("intersection_empty") is not True:
        errors.append(
            issue(
                "certificate.intersection_flag_false",
                f"{path}.intersection_empty",
                "intersection_empty must be explicitly true",
            )
        )
    if certificate.get("passed") is not True:
        errors.append(
            issue(
                "certificate.not_passed",
                f"{path}.passed",
                "decision certificate must be marked passed",
            )
        )
    if solver_action_sets:
        if base_actions != solver_action_sets.get("base", set()):
            errors.append(
                issue(
                    "certificate.base_set_disagreement",
                    f"{path}.base_acceptable_actions",
                    "certificate base actions differ from exact enumeration",
                )
            )
        if patched_actions != solver_action_sets.get("patched", set()):
            errors.append(
                issue(
                    "certificate.patched_set_disagreement",
                    f"{path}.patched_acceptable_actions",
                    "certificate patched actions differ from exact enumeration",
                )
            )
    for world_name in ("base", "patched"):
        world = certificate.get(f"{world_name}_world")
        world_path = f"{path}.{world_name}_world"
        if not isinstance(world, dict):
            errors.append(
                issue(
                    "certificate.world_metadata_missing",
                    world_path,
                    "world metadata is required",
                )
            )
            continue
        if base_id is not None and world.get("base_id") != base_id:
            errors.append(
                issue(
                    "certificate.base_id_mismatch",
                    f"{world_path}.base_id",
                    "both worlds must use the task's same base_id",
                )
            )
        world_objective = world.get("objective_fingerprint")
        if not _is_sha256(world_objective):
            errors.append(
                issue(
                    "certificate.objective_missing",
                    f"{world_path}.objective_fingerprint",
                    "world objective fingerprint must be SHA-256",
                )
            )
        elif objective_fingerprint and world_objective.lower() != objective_fingerprint:
            errors.append(
                issue(
                    "certificate.objective_mismatch",
                    f"{world_path}.objective_fingerprint",
                    "world objective differs from the registered single objective",
                )
            )
    base_world = certificate.get("base_world")
    patched_world = certificate.get("patched_world")
    if isinstance(base_world, dict) and isinstance(patched_world, dict):
        if base_world.get("objective_fingerprint") != patched_world.get(
            "objective_fingerprint"
        ):
            errors.append(
                issue(
                    "certificate.cross_world_objective_mismatch",
                    path,
                    "base and patched worlds must retain the same objective definition",
                )
            )
    return errors


def _model_hash_entry(
    model_hashes: Mapping[str, Any], world: str
) -> Mapping[str, Any] | None:
    for key in (world, f"{world}_ir"):
        value = model_hashes.get(key)
        if isinstance(value, dict):
            return value
    return None


def validate_model_files(
    root: Path,
    gold: Mapping[str, Any],
    path: str,
) -> tuple[dict[str, Mapping[str, Any]], list[Issue]]:
    errors: list[Issue] = []
    models: dict[str, Mapping[str, Any]] = {}
    model_hashes = gold.get("model_hashes")
    if not isinstance(model_hashes, dict):
        return models, [
            issue(
                "model.hashes_missing",
                f"{path}.model_hashes",
                "model_hashes must contain base and patched entries",
            )
        ]
    seen_hashes: dict[str, str] = {}
    for world in ("base", "patched"):
        entry = _model_hash_entry(model_hashes, world)
        entry_path = f"{path}.model_hashes.{world}"
        if entry is None:
            errors.append(
                issue(
                    "model.hash_entry_missing",
                    entry_path,
                    "model hash entry must contain path and sha256",
                )
            )
            continue
        relative_path = entry.get("path")
        expected_hash = entry.get("sha256")
        expected_canonical_hash = entry.get("canonical_sha256")
        if not _is_nonempty_string(relative_path):
            errors.append(
                issue(
                    "model.path_invalid",
                    f"{entry_path}.path",
                    "model path must be non-empty",
                )
            )
            continue
        normalized_relative = str(relative_path).replace("\\", "/")
        if not normalized_relative.startswith("models/"):
            errors.append(
                issue(
                    "model.path_outside_models",
                    f"{entry_path}.path",
                    "model path must be inside models/",
                )
            )
            continue
        model_path = (root / normalized_relative).resolve()
        models_root = (root / "models").resolve()
        if models_root not in model_path.parents:
            errors.append(
                issue(
                    "model.path_traversal",
                    f"{entry_path}.path",
                    "model path escapes models/",
                )
            )
            continue
        if not model_path.is_file():
            errors.append(
                issue(
                    "model.file_missing",
                    normalized_relative,
                    "referenced model file is missing",
                )
            )
            continue
        if not _is_sha256(expected_hash):
            errors.append(
                issue(
                    "model.hash_invalid",
                    f"{entry_path}.sha256",
                    "model hash must be SHA-256",
                )
            )
        else:
            actual_hash = sha256_file(model_path)
            if actual_hash != expected_hash.lower():
                errors.append(
                    issue(
                        "model.hash_mismatch",
                        normalized_relative,
                        "model file hash differs from model_hashes",
                    )
                )
            seen_hashes[world] = actual_hash
        model, parse_errors = _parse_json_file(model_path, normalized_relative)
        errors.extend(parse_errors)
        if not isinstance(model, dict):
            errors.append(
                issue(
                    "model.not_object",
                    normalized_relative,
                    "canonical model file must be a JSON object",
                )
            )
            continue
        if not _is_sha256(expected_canonical_hash):
            errors.append(
                issue(
                    "model.canonical_hash_invalid",
                    f"{entry_path}.canonical_sha256",
                    "canonical_sha256 must be recorded",
                )
            )
        elif sha256_json(model) != expected_canonical_hash.lower():
            errors.append(
                issue(
                    "model.canonical_hash_mismatch",
                    normalized_relative,
                    "canonical JSON hash differs from model_hashes",
                )
            )
        models[world] = model
        if model.get("task_id") != gold.get("id"):
            errors.append(
                issue(
                    "model.task_id_mismatch",
                    f"{normalized_relative}.task_id",
                    "model task_id differs from gold",
                )
            )
        if model.get("base_id") != gold.get("base_id"):
            errors.append(
                issue(
                    "model.base_id_mismatch",
                    f"{normalized_relative}.base_id",
                    "model base_id differs from gold",
                )
            )
        if model.get("world") != world:
            errors.append(
                issue(
                    "model.world_mismatch",
                    f"{normalized_relative}.world",
                    f"model world must be {world!r}",
                )
            )
        objective = model.get("objective")
        if not isinstance(objective, dict) or not isinstance(
            objective.get("terms"), dict
        ):
            errors.append(
                issue(
                    "model.objective_invalid",
                    f"{normalized_relative}.objective",
                    "canonical model requires one linear objective object",
                )
            )
        if model.get("sense") not in {"min", "max"}:
            errors.append(
                issue(
                    "model.sense_invalid",
                    f"{normalized_relative}.sense",
                    "model sense must be min or max",
                )
            )
        if (
            "objectives" in model
            or model.get("objective_count", 1) != 1
            or model.get("single_objective") is not True
        ):
            errors.append(
                issue(
                    "model.multi_objective",
                    normalized_relative,
                    "only one objective is allowed",
                )
            )
        projection = model.get("action_projection")
        if not isinstance(projection, list) or not projection:
            errors.append(
                issue(
                    "model.projection_missing",
                    f"{normalized_relative}.action_projection",
                    "pre-registered action projection must be non-empty",
                )
            )
        errors.extend(_find_unresolved(model, normalized_relative))
    if seen_hashes.get("base") and seen_hashes.get("patched"):
        if seen_hashes["base"] == seen_hashes["patched"]:
            errors.append(
                issue(
                    "model.before_after_same_hash",
                    f"{path}.model_hashes",
                    "base and patched model hashes must differ",
                )
            )
    return models, errors


def load_solver_artifact(
    root: Path,
    gold: Mapping[str, Any],
    path: str,
) -> tuple[Mapping[str, Any] | None, list[Issue]]:
    model_hashes = gold.get("model_hashes")
    if not isinstance(model_hashes, dict):
        return None, []
    base_entry = _model_hash_entry(model_hashes, "base")
    if not isinstance(base_entry, dict) or not _is_nonempty_string(
        base_entry.get("path")
    ):
        return None, []
    base_relative = Path(str(base_entry["path"]).replace("\\", "/"))
    solver_relative = (base_relative.parent / "solver_results.json").as_posix()
    solver_path = (root / solver_relative).resolve()
    models_root = (root / "models").resolve()
    if models_root not in solver_path.parents:
        return None, [
            issue(
                "solver.artifact_path_invalid",
                f"{path}.model_hashes.base.path",
                "derived solver artifact escapes models/",
            )
        ]
    artifact, errors = _parse_json_file(solver_path, solver_relative)
    if not isinstance(artifact, dict):
        if artifact is not None:
            errors.append(
                issue(
                    "solver.artifact_invalid",
                    solver_relative,
                    "solver artifact must be a JSON object",
                )
            )
        return None, errors
    return artifact, errors


def validate_gold_solver_summary(
    summary: Any,
    artifact: Mapping[str, Any],
    path: str,
    *,
    tolerance: float,
) -> list[Issue]:
    """Cross-check the compact gold summary against the full solver artifact."""

    errors: list[Issue] = []
    if not isinstance(summary, dict):
        return [
            issue(
                "solver.gold_summary_missing",
                path,
                "gold solver summary must be an object",
            )
        ]
    for solver_name in ("gurobi", "copt"):
        solver_summary = summary.get(solver_name)
        if not isinstance(solver_summary, dict):
            errors.append(
                issue(
                    "solver.gold_backend_missing",
                    f"{path}.{solver_name}",
                    f"{solver_name} gold summary is required",
                )
            )
            continue
        for world_name in ("base", "patched"):
            compact = solver_summary.get(world_name)
            world = artifact.get(world_name)
            full = world.get(solver_name) if isinstance(world, dict) else None
            exact = world.get("exact_enumeration") if isinstance(world, dict) else None
            compact_path = f"{path}.{solver_name}.{world_name}"
            if not isinstance(compact, dict) or not isinstance(full, dict):
                errors.append(
                    issue(
                        "solver.gold_world_missing",
                        compact_path,
                        "gold and full solver results are both required",
                    )
                )
                continue
            for key in ("status", "version", "projected_action"):
                if compact.get(key) != full.get(key):
                    errors.append(
                        issue(
                            "solver.gold_summary_mismatch",
                            f"{compact_path}.{key}",
                            f"gold {key} differs from full solver artifact",
                        )
                    )
            if not _is_number(compact.get("objective")) or not _is_number(
                full.get("objective")
            ):
                errors.append(
                    issue(
                        "solver.gold_objective_invalid",
                        f"{compact_path}.objective",
                        "gold and full objectives must be finite numeric",
                    )
                )
            elif (
                abs(float(compact["objective"]) - float(full["objective"]))
                > tolerance
            ):
                errors.append(
                    issue(
                        "solver.gold_summary_mismatch",
                        f"{compact_path}.objective",
                        "gold objective differs from full solver artifact",
                    )
                )
            if compact.get("action_set_complete") is not True:
                errors.append(
                    issue(
                        "solver.gold_action_set_incomplete",
                        f"{compact_path}.action_set_complete",
                        "gold summary must explicitly carry a complete action set",
                    )
                )
            if not isinstance(exact, dict) or compact.get(
                "optimal_actions"
            ) != exact.get("optimal_actions"):
                errors.append(
                    issue(
                        "solver.gold_optimal_actions_mismatch",
                        f"{compact_path}.optimal_actions",
                        "gold optimal actions differ from exact enumeration",
                    )
                )
            for metric in (
                "max_constraint_violation",
                "integrality_violation",
                "bound_violation",
            ):
                if metric in compact and compact.get(metric) != full.get(metric):
                    errors.append(
                        issue(
                            "solver.gold_residual_mismatch",
                            f"{compact_path}.{metric}",
                            f"gold {metric} differs from full solver artifact",
                        )
                    )
            if "assignment" in compact and compact.get("assignment") != full.get(
                "assignment"
            ):
                errors.append(
                    issue(
                        "solver.gold_assignment_mismatch",
                        f"{compact_path}.assignment",
                        "gold assignment differs from full solver artifact",
                    )
                )
    return errors


def _mapping_is_subset(
    subset: Mapping[str, Any], superset: Mapping[str, Any]
) -> bool:
    for key, value in subset.items():
        if key not in superset:
            return False
        other = superset[key]
        if isinstance(value, dict):
            if not isinstance(other, dict) or not _mapping_is_subset(value, other):
                return False
        elif value != other:
            return False
    return True


def validate_gold_evidence_bundle(
    gold: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    path: str,
) -> list[Issue]:
    errors: list[Issue] = []
    applicability = gold.get("applicability")
    passport = gold.get("source_passport")
    evidence_ids = gold.get("evidence_ids")
    if not isinstance(applicability, dict) or not isinstance(passport, dict):
        return errors
    selected_id = applicability.get("selected_evidence_id")
    if not isinstance(evidence_ids, list) or evidence_ids != [selected_id]:
        errors.append(
            issue(
                "gold.selected_evidence_ids_mismatch",
                f"{path}.evidence_ids",
                "evidence_ids must contain exactly the selected applicable evidence",
            )
        )
    comparison = applicability.get("comparison")
    if not isinstance(comparison, list):
        return errors
    evidence_mode = gold.get("evidence_mode")
    expected_roles = (
        {"applicable", "old_version", "wrong_jurisdiction", "wrong_entity"}
        if evidence_mode == "fresh-private"
        else {
            "applicable",
            "old_version",
            "wrong_jurisdiction",
            "non_authoritative",
        }
    )
    observed_roles = {
        row.get("role") for row in comparison if isinstance(row, dict)
    }
    if len(comparison) != 4 or observed_roles != expected_roles:
        errors.append(
            issue(
                "gold.evidence_bundle_roles_invalid",
                f"{path}.applicability.comparison",
                f"expected one row for each role {sorted(expected_roles)}",
            )
        )
    comparison_ids: set[str] = set()
    selected_evidence: Mapping[str, Any] | None = None
    decision_time = _parse_iso_datetime(applicability.get("decision_time"))
    required_jurisdiction = applicability.get("jurisdiction")
    required_subject = applicability.get("subject")
    for index, comparison_row in enumerate(comparison):
        comparison_path = f"{path}.applicability.comparison[{index}]"
        if not isinstance(comparison_row, dict):
            errors.append(
                issue(
                    "gold.evidence_comparison_invalid",
                    comparison_path,
                    "comparison row must be an object",
                )
            )
            continue
        evidence_id = comparison_row.get("evidence_id")
        role = comparison_row.get("role")
        if not _is_nonempty_string(evidence_id):
            errors.append(
                issue(
                    "gold.evidence_comparison_id_missing",
                    f"{comparison_path}.evidence_id",
                    "comparison evidence id must be non-empty",
                )
            )
            continue
        if evidence_id in comparison_ids:
            errors.append(
                issue(
                    "gold.evidence_comparison_duplicate",
                    comparison_path,
                    "comparison evidence ids must be unique",
                )
            )
        comparison_ids.add(str(evidence_id))
        evidence = evidence_by_id.get(str(evidence_id))
        if not isinstance(evidence, dict):
            errors.append(
                issue(
                    "gold.evidence_missing",
                    comparison_path,
                    f"evidence {evidence_id!r} is absent from corpus",
                )
            )
            continue
        evidence_passport = comparison_row.get("source_passport")
        if not isinstance(evidence_passport, dict):
            errors.append(
                issue(
                    "gold.evidence_passport_missing",
                    f"{comparison_path}.source_passport",
                    "private comparison row must preserve the candidate source passport",
                )
            )
            continue
        if role == "applicable":
            selected_evidence = evidence
            if evidence_id != selected_id or comparison_row.get("applicable") is not True:
                errors.append(
                    issue(
                        "gold.applicable_selection_mismatch",
                        comparison_path,
                        "applicable row must equal selected_evidence_id",
                    )
                )
            if evidence.get("source_kind") != "policy_document":
                errors.append(
                    issue(
                        "gold.evidence_kind_not_neutral",
                        comparison_path,
                        "retrievable evidence kind must not expose evidence mode or role",
                    )
                )
            errors.extend(
                validate_source_passport(
                    evidence_passport,
                    applicability,
                    f"{comparison_path}.source_passport",
                    evidence_mode=evidence_mode,
                )
            )
        else:
            if comparison_row.get("applicable") is not False:
                errors.append(
                    issue(
                        "gold.distractor_marked_applicable",
                        comparison_path,
                        "distractor comparison row must be inapplicable",
                    )
                )
            if not _is_nonempty_string(comparison_row.get("failure_reason")):
                errors.append(
                    issue(
                        "gold.distractor_reason_missing",
                        f"{comparison_path}.failure_reason",
                        "distractor requires an explicit failure reason",
                    )
                )
            if role == "old_version":
                effective_to = _parse_iso_datetime(
                    evidence_passport.get("effective_to")
                )
                if (
                    decision_time is None
                    or effective_to is None
                    or effective_to >= decision_time
                ):
                    errors.append(
                        issue(
                            "source.old_version_not_proven",
                            comparison_path,
                            "old-version distractor did not expire before decision_time",
                        )
                    )
            elif role == "wrong_jurisdiction":
                if evidence_passport.get("jurisdiction") == required_jurisdiction:
                    errors.append(
                        issue(
                            "source.wrong_jurisdiction_not_proven",
                            comparison_path,
                            "wrong-jurisdiction distractor matches required jurisdiction",
                        )
                    )
            elif role in {"wrong_subject", "wrong_entity"}:
                source_entity = evidence_passport.get("issuer")
                if source_entity == required_subject:
                    errors.append(
                        issue(
                            "source.wrong_subject_not_proven",
                            comparison_path,
                            "wrong-entity distractor has the required issuer",
                        )
                    )
            elif role == "non_authoritative":
                if evidence_passport.get("authoritative") is not False:
                    errors.append(
                        issue(
                            "source.non_authoritative_not_proven",
                            comparison_path,
                            "non-authoritative distractor must carry authoritative=false",
                        )
                    )
    if selected_evidence is not None:
        selected_comparison = next(
            (
                row
                for row in comparison
                if isinstance(row, dict) and row.get("role") == "applicable"
            ),
            None,
        )
        selected_passport = (
            selected_comparison.get("source_passport")
            if isinstance(selected_comparison, dict)
            else None
        )
        if isinstance(selected_passport, dict):
            for key in (
                "authoritative",
                "authority",
                "effective_from",
                "issuer",
                "jurisdiction",
                "subject_scope",
                "version",
            ):
                if passport.get(key) != selected_passport.get(key):
                    errors.append(
                        issue(
                            "gold.passport_link_mismatch",
                            f"{path}.source_passport.{key}",
                            "Gold and retrievable passports disagree on a shared applicability field",
                        )
                    )
    return errors


def validate_gold_record(
    gold: Mapping[str, Any],
    path: str,
    *,
    task: Mapping[str, Any] | None = None,
    evidence_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    root: Path | None = None,
) -> list[Issue]:
    errors = _require_keys(
        gold,
        (
            "id",
            "base_id",
            "family",
            "evidence_mode",
            "patch_class",
            "base_audit",
            "source_passport",
            "applicability",
            "typed_patch",
            "model_hashes",
            "action_projection",
            "solver_results",
            "decision_certificate",
            "reviews",
            "adjudication",
            "evidence_ids",
        ),
        path,
    )
    if task is not None:
        keys_to_compare = ["id"]
        if "base_id" in task:
            keys_to_compare.append("base_id")
        for key in keys_to_compare:
            if gold.get(key) != task.get(key):
                errors.append(
                    issue(
                        "gold.task_mismatch",
                        f"{path}.{key}",
                        f"gold {key} differs from public task",
                    )
                )
    if gold.get("family") not in EXPECTED_FAMILIES:
        errors.append(
            issue(
                "gold.family_invalid",
                f"{path}.family",
                "family is outside the frozen allowlist",
            )
        )
    if gold.get("evidence_mode") not in EXPECTED_EVIDENCE_MODES:
        errors.append(
            issue(
                "gold.evidence_mode_invalid",
                f"{path}.evidence_mode",
                "evidence_mode is outside the frozen allowlist",
            )
        )
    if gold.get("patch_class") not in EXPECTED_PATCH_CLASSES:
        errors.append(
            issue(
                "gold.patch_class_invalid",
                f"{path}.patch_class",
                "patch_class is outside the frozen allowlist",
            )
        )

    base_audit = gold.get("base_audit")
    objective_fingerprint: str | None = None
    if not isinstance(base_audit, dict):
        errors.append(
            issue(
                "gold.base_audit_missing",
                f"{path}.base_audit",
                "base_audit must be an object",
            )
        )
    else:
        if base_audit.get("single_objective") is not True:
            errors.append(
                issue(
                    "gold.not_single_objective",
                    f"{path}.base_audit.single_objective",
                    "single_objective must be explicitly true",
                )
            )
        if "objective_count" in base_audit and base_audit.get("objective_count") != 1:
            errors.append(
                issue(
                    "gold.objective_count_invalid",
                    f"{path}.base_audit.objective_count",
                    "objective_count must equal 1",
                )
            )
        objective_fingerprint = _objective_fingerprint(base_audit)
        if objective_fingerprint is None:
            certificate = gold.get("decision_certificate")
            if isinstance(certificate, dict):
                worlds = certificate.get("worlds")
                if isinstance(worlds, dict) and isinstance(worlds.get("base"), dict):
                    candidate = worlds["base"].get("objective_fingerprint")
                    if _is_sha256(candidate):
                        objective_fingerprint = str(candidate).lower()
                base_world = certificate.get("base_world")
                if objective_fingerprint is None and isinstance(base_world, dict):
                    candidate = base_world.get("objective_fingerprint")
                    if _is_sha256(candidate):
                        objective_fingerprint = str(candidate).lower()
        if objective_fingerprint is None:
            errors.append(
                issue(
                    "gold.objective_fingerprint_missing",
                    f"{path}.base_audit",
                    "a verifiable objective fingerprint is required",
                )
            )
        legacy_answer_used = base_audit.get(
            "legacy_answer_used",
            base_audit.get("historical_answer_used_as_gold"),
        )
        if legacy_answer_used is not False:
            errors.append(
                issue(
                    "gold.legacy_answer_not_rejected",
                    f"{path}.base_audit.legacy_answer_used",
                    "legacy answers must be explicitly excluded from gold",
                )
            )
        legacy_code_used = base_audit.get(
            "legacy_code_used",
            base_audit.get("historical_code_used_as_gold"),
        )
        if legacy_code_used is not False:
            errors.append(
                issue(
                    "gold.legacy_code_not_rejected",
                    f"{path}.base_audit.legacy_code_used",
                    "legacy code must be explicitly excluded from gold",
                )
            )

    errors.extend(
        validate_source_passport(
            gold.get("source_passport"),
            gold.get("applicability"),
            f"{path}.source_passport",
            evidence_mode=gold.get("evidence_mode"),
        )
    )
    errors.extend(
        validate_typed_patch(
            gold.get("typed_patch"),
            f"{path}.typed_patch",
            expected_patch_class=gold.get("patch_class"),
        )
    )
    projection = gold.get("action_projection")
    if not isinstance(projection, dict):
        errors.append(
            issue(
                "gold.action_projection_missing",
                f"{path}.action_projection",
                "action_projection must be a non-empty object",
            )
        )
    else:
        if not _is_nonempty_string(
            projection.get("projection_id")
        ) and projection.get("registered_before_evidence") is not True:
            errors.append(
                issue(
                    "gold.projection_id_missing",
                    f"{path}.action_projection",
                    "projection must have an id or be registered before evidence",
                )
            )
        fields = projection.get("fields", projection.get("variables"))
        if not isinstance(fields, list) or not fields or not all(
            _is_nonempty_string(value) for value in fields
        ):
            errors.append(
                issue(
                    "gold.projection_fields_invalid",
                    f"{path}.action_projection.fields",
                    "projection fields must be a non-empty string list",
                )
            )

    models: dict[str, Mapping[str, Any]] = {}
    if root is not None:
        models, model_errors = validate_model_files(root, gold, path)
        errors.extend(model_errors)
        if len(models) == 2:
            fingerprints = {
                world: _objective_fingerprint_from_ir(model)
                for world, model in models.items()
            }
            if None in fingerprints.values():
                pass
            elif fingerprints["base"] != fingerprints["patched"]:
                errors.append(
                    issue(
                        "model.cross_world_objective_mismatch",
                        f"{path}.model_hashes",
                        "base and patched model objective definitions differ",
                    )
                )
            elif (
                objective_fingerprint
                and fingerprints["base"] != objective_fingerprint
            ):
                errors.append(
                    issue(
                        "model.objective_fingerprint_mismatch",
                        f"{path}.base_audit.objective_fingerprint",
                        "base_audit objective fingerprint differs from model IR",
                    )
                )
            if models["base"].get("sense") != models["patched"].get("sense"):
                errors.append(
                    issue(
                        "model.cross_world_sense_mismatch",
                        f"{path}.model_hashes",
                        "base and patched objective senses differ",
                    )
                )
            base_projection = models["base"].get("action_projection")
            patched_projection = models["patched"].get("action_projection")
            if base_projection != patched_projection:
                errors.append(
                    issue(
                        "model.projection_changed",
                        f"{path}.model_hashes",
                        "base and patched action projections must be identical",
                    )
                )
            if isinstance(projection, dict):
                projection_fields = projection.get(
                    "fields", projection.get("variables")
                )
                if projection_fields != base_projection:
                    errors.append(
                        issue(
                            "model.projection_gold_mismatch",
                            f"{path}.action_projection.fields",
                            "gold action projection differs from canonical IR",
                        )
                    )
            patch = gold.get("typed_patch")
            model_hashes = gold.get("model_hashes")
            if isinstance(patch, dict) and isinstance(model_hashes, dict):
                base_entry = _model_hash_entry(model_hashes, "base")
                patched_entry = _model_hash_entry(model_hashes, "patched")
                if isinstance(base_entry, dict):
                    if patch.get("base_model_hash") != base_entry.get("sha256"):
                        errors.append(
                            issue(
                                "patch.base_model_hash_mismatch",
                                f"{path}.typed_patch.base_model_hash",
                                "typed patch base_model_hash differs from model_hashes",
                            )
                        )
                if isinstance(patched_entry, dict):
                    if patch.get("patched_model_hash") != patched_entry.get("sha256"):
                        errors.append(
                            issue(
                                "patch.patched_model_hash_mismatch",
                                f"{path}.typed_patch.patched_model_hash",
                                "typed patch patched_model_hash differs from model_hashes",
                            )
                        )
                if isinstance(patch.get("ops"), list):
                    for op_index, operation in enumerate(patch["ops"]):
                        if not isinstance(operation, dict):
                            continue
                        before_expression = operation.get("before_expression")
                        after_expression = operation.get("after_expression")
                        if _is_nonempty_string(
                            before_expression
                        ) and not _contains_subvalue(
                            models["base"], before_expression
                        ):
                            errors.append(
                                issue(
                                    "patch.before_fragment_unbound",
                                    (
                                        f"{path}.typed_patch.ops[{op_index}]"
                                        ".before_expression"
                                    ),
                                    "before expression is absent from the base IR",
                                )
                            )
                        if _is_nonempty_string(
                            after_expression
                        ) and not _contains_subvalue(
                            models["patched"], after_expression
                        ):
                            errors.append(
                                issue(
                                    "patch.after_fragment_unbound",
                                    (
                                        f"{path}.typed_patch.ops[{op_index}]"
                                        ".after_expression"
                                    ),
                                    "after expression is absent from the patched IR",
                                )
                            )
                else:
                    if not _contains_subvalue(models["base"], patch.get("before")):
                        errors.append(
                            issue(
                                "patch.before_fragment_unbound",
                                f"{path}.typed_patch.before",
                                "before fragment is absent from the base canonical IR",
                            )
                        )
                    if not _contains_subvalue(models["patched"], patch.get("after")):
                        errors.append(
                            issue(
                                "patch.after_fragment_unbound",
                                f"{path}.typed_patch.after",
                                "after fragment is absent from the patched canonical IR",
                            )
                        )

    tolerance = gold.get("tolerance", 1e-6)
    solver_artifact: Mapping[str, Any] | None = None
    if root is not None:
        solver_artifact, artifact_errors = load_solver_artifact(root, gold, path)
        errors.extend(artifact_errors)
        if solver_artifact is not None:
            errors.extend(
                validate_gold_solver_summary(
                    gold.get("solver_results"),
                    solver_artifact,
                    f"{path}.solver_results",
                    tolerance=tolerance,
                )
            )
    solver_sets, solver_errors = validate_solver_results(
        solver_artifact if solver_artifact is not None else gold.get("solver_results"),
        f"{path}.solver_results",
        tolerance=tolerance,
        model_irs=models if root is not None else None,
    )
    errors.extend(solver_errors)
    errors.extend(
        validate_decision_certificate(
            gold.get("decision_certificate"),
            f"{path}.decision_certificate",
            base_id=gold.get("base_id"),
            objective_fingerprint=objective_fingerprint,
            solver_action_sets=solver_sets,
        )
    )

    evidence_ids = gold.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not evidence_ids or not all(
        _is_nonempty_string(value) for value in evidence_ids
    ):
        errors.append(
            issue(
                "gold.evidence_ids_invalid",
                f"{path}.evidence_ids",
                "at least one applied evidence id is required",
            )
        )
    elif len(evidence_ids) != len(set(evidence_ids)):
        errors.append(
            issue(
                "gold.evidence_ids_duplicate",
                f"{path}.evidence_ids",
                "duplicate evidence ids are forbidden",
            )
        )
    elif evidence_by_id is not None:
        errors.extend(validate_gold_evidence_bundle(gold, evidence_by_id, path))

    errors.extend(validate_reviews(gold, path))
    errors.extend(_find_unresolved(gold, path))
    return errors


def validate_evidence_record(record: Mapping[str, Any], path: str) -> list[Issue]:
    errors = _require_keys(
        record,
        (
            "id",
            "source_kind",
            "content",
            "content_sha256",
            "applicability",
        ),
        path,
    )
    if not _is_nonempty_string(record.get("id")):
        errors.append(
            issue("evidence.id_invalid", f"{path}.id", "evidence id must be non-empty")
        )
    elif re.fullmatch(r"DOC-[0-9A-F]{16}", str(record.get("id"))) is None:
        errors.append(
            issue(
                "evidence.id_not_role_neutral",
                f"{path}.id",
                "evidence id must use the opaque role-neutral DOC namespace",
            )
        )
    source_kind = record.get("source_kind")
    if source_kind != "policy_document":
        errors.append(
            issue(
                "evidence.source_kind_invalid",
                f"{path}.source_kind",
                "source_kind must be the role-neutral value policy_document",
            )
        )
    content = record.get("content")
    content_hash = record.get("content_sha256")
    if not _is_nonempty_string(content):
        errors.append(
            issue(
                "evidence.content_empty",
                f"{path}.content",
                "evidence content must be non-empty",
            )
        )
    elif not _is_sha256(content_hash):
        errors.append(
            issue(
                "evidence.content_hash_invalid",
                f"{path}.content_sha256",
                "content_sha256 must be SHA-256",
            )
        )
    elif sha256_text(content) != content_hash.lower():
        errors.append(
            issue(
                "evidence.content_hash_mismatch",
                f"{path}.content_sha256",
                "content_sha256 differs from UTF-8 evidence content",
            )
        )
    applicability = record.get("applicability")
    if not isinstance(applicability, dict):
        errors.append(
            issue(
                "source.applicability_metadata_missing",
                f"{path}.applicability",
                "evidence applicability metadata must be an object",
            )
        )
    else:
        if applicability.get("gold_status_exposed") is not False:
            errors.append(
                issue(
                    "leakage.evidence_gold_status_exposed",
                    f"{path}.applicability.gold_status_exposed",
                    "retrieval corpus must not expose gold applicability labels",
                )
            )
        predicate_fields = applicability.get("predicate_fields")
        required_predicates = {
            "issuer_authority",
            "effective_interval",
            "jurisdiction",
            "subject_scope",
            "exception_state",
        }
        if not isinstance(predicate_fields, list) or set(predicate_fields) != required_predicates:
            errors.append(
                issue(
                    "source.applicability_predicates_incomplete",
                    f"{path}.applicability.predicate_fields",
                    "retrieval card must declare all applicability predicates",
                )
            )
    errors.extend(_find_unresolved(record, path))
    return errors


def _review_signature(review: Mapping[str, Any]) -> tuple[Any, ...] | None:
    required = (
        "applicability",
        "patch_valid",
        "solver_valid",
        "certificate_valid",
        "decision",
    )
    if all(key in review for key in required):
        return tuple(review[key] for key in required)
    if "label" in review:
        return (review.get("label"),)
    return None


def validate_reviews(gold: Mapping[str, Any], path: str) -> list[Issue]:
    errors: list[Issue] = []
    reviews = gold.get("reviews")
    if isinstance(reviews, dict):
        review_rows = list(reviews.values())
    elif isinstance(reviews, list):
        review_rows = reviews
    else:
        review_rows = []
    if len(review_rows) < 2:
        errors.append(
            issue(
                "review.insufficient",
                f"{path}.reviews",
                "at least two independent reviews are required",
            )
        )
        return errors
    reviewer_ids: list[str] = []
    for index, review in enumerate(review_rows):
        review_path = f"{path}.reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(
                issue("review.not_object", review_path, "review must be an object")
            )
            continue
        reviewer_id = review.get("reviewer_id", review.get("reviewer"))
        if not _is_nonempty_string(reviewer_id):
            errors.append(
                issue(
                    "review.id_missing",
                    f"{review_path}.reviewer_id",
                    "reviewer_id must be non-empty",
                )
            )
        else:
            reviewer_ids.append(reviewer_id)
        signature = _review_signature(review)
        if signature is None:
            errors.append(
                issue(
                    "review.labels_missing",
                    review_path,
                    "blind review labels are incomplete",
                )
            )
        else:
            if len(signature) == 1:
                if review.get("label") not in {"accept", "reject"}:
                    errors.append(
                        issue(
                            "review.decision_label_invalid",
                            f"{review_path}.label",
                            "compact review label must be accept or reject",
                        )
                    )
            else:
                if review.get("applicability") not in {
                    "applicable",
                    "not_applicable",
                }:
                    errors.append(
                        issue(
                            "review.applicability_label_invalid",
                            f"{review_path}.applicability",
                            "applicability label is invalid",
                        )
                    )
                for key in ("patch_valid", "solver_valid", "certificate_valid"):
                    if not isinstance(review.get(key), bool):
                        errors.append(
                            issue(
                                "review.boolean_label_invalid",
                                f"{review_path}.{key}",
                                f"{key} must be boolean",
                            )
                        )
                if review.get("decision") not in {"accept", "reject"}:
                    errors.append(
                        issue(
                            "review.decision_label_invalid",
                            f"{review_path}.decision",
                            "decision must be accept or reject",
                        )
                    )
        if review.get("blind", review.get("blind_packet")) is not True:
            errors.append(
                issue(
                    "review.not_blind",
                    f"{review_path}.blind",
                    "review must be explicitly blind",
                )
            )
    if len(reviewer_ids) != len(set(reviewer_ids)):
        errors.append(
            issue(
                "review.not_independent",
                f"{path}.reviews",
                "reviewer ids must be unique",
            )
        )
    adjudication = gold.get("adjudication")
    if not isinstance(adjudication, dict):
        errors.append(
            issue(
                "review.adjudication_missing",
                f"{path}.adjudication",
                "adjudication object is required",
            )
        )
    else:
        if str(adjudication.get("status", "")).lower() != "resolved":
            errors.append(
                issue(
                    "review.adjudication_unresolved",
                    f"{path}.adjudication.status",
                    "adjudication status must be resolved",
                )
            )
        if adjudication.get("unresolved") is not False:
            errors.append(
                issue(
                    "review.unresolved_flag",
                    f"{path}.adjudication.unresolved",
                    "unresolved must be explicitly false",
                )
            )
        final_decision = adjudication.get(
            "final_decision", adjudication.get("label", "")
        )
        if str(final_decision).lower() not in {
            "accept",
            "approved",
        }:
            errors.append(
                issue(
                    "review.final_decision_invalid",
                    f"{path}.adjudication.final_decision",
                    "release rows must be adjudicated accept",
                )
            )
    return errors


def compute_review_agreement(gold_rows: Sequence[Mapping[str, Any]]) -> float:
    comparisons = 0
    agreements = 0
    for gold in gold_rows:
        reviews = gold.get("reviews")
        if isinstance(reviews, dict):
            review_rows = list(reviews.values())
        elif isinstance(reviews, list):
            review_rows = reviews
        else:
            review_rows = []
        if len(review_rows) < 2:
            continue
        signatures = [
            _review_signature(review)
            for review in review_rows
            if isinstance(review, dict)
        ]
        signatures = [signature for signature in signatures if signature is not None]
        for left_index in range(len(signatures)):
            for right_index in range(left_index + 1, len(signatures)):
                comparisons += 1
                agreements += signatures[left_index] == signatures[right_index]
    if comparisons == 0:
        return 0.0
    return agreements / comparisons


def _find_unresolved(value: Any, path: str) -> list[Issue]:
    errors: list[Issue] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key.lower() == "unresolved" and child not in (False, None, "", [], {}):
                errors.append(
                    issue(
                        "release.unresolved",
                        child_path,
                        "unresolved release state is forbidden",
                    )
                )
            errors.extend(_find_unresolved(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_find_unresolved(child, f"{path}[{index}]"))
    elif isinstance(value, str) and value.strip().lower() in UNRESOLVED_MARKERS:
        errors.append(
            issue(
                "release.unresolved_marker",
                path,
                f"unresolved marker {value!r} is forbidden",
            )
        )
    return errors


def _manifest_file_entries(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    files = manifest.get("files")
    if isinstance(files, dict):
        entries: dict[str, dict[str, Any]] = {}
        for path, value in files.items():
            if isinstance(value, str):
                entries[str(path).replace("\\", "/")] = {"sha256": value}
            elif isinstance(value, dict):
                entries[str(path).replace("\\", "/")] = dict(value)
        return entries
    if isinstance(files, list):
        entries = {}
        for value in files:
            if isinstance(value, dict) and _is_nonempty_string(value.get("path")):
                entry_path = str(value["path"]).replace("\\", "/")
                entries[entry_path] = dict(value)
        return entries
    return {}


def validate_manifest(
    root: Path,
    manifest: Any,
    *,
    tasks_count: int,
    evidence_count: int,
    gold_count: int,
    review_agreement: float,
) -> list[Issue]:
    errors: list[Issue] = []
    if not isinstance(manifest, dict):
        return [
            issue("manifest.invalid", "manifest.json", "manifest must be a JSON object")
        ]
    manifest_dataset_id = manifest.get("dataset_id", manifest.get("dataset"))
    if manifest_dataset_id != DATASET_ID:
        errors.append(
            issue(
                "manifest.dataset_id_invalid",
                "manifest.json.dataset_id",
                f"dataset_id must equal {DATASET_ID!r}",
            )
        )
    if not _is_nonempty_string(manifest.get("schema_version")):
        errors.append(
            issue(
                "manifest.schema_version_missing",
                "manifest.json.schema_version",
                "schema_version must be non-empty",
            )
        )
    counts = manifest.get("record_counts")
    expected_record_counts = {
        "public/tasks_zh.jsonl": tasks_count,
        "private/evidence_corpus.jsonl": evidence_count,
        "private/gold.jsonl": gold_count,
    }
    required_counts = manifest.get("required_counts")
    if isinstance(counts, dict):
        for path, count in expected_record_counts.items():
            if counts.get(path) != count:
                errors.append(
                    issue(
                        "manifest.record_count_mismatch",
                        f"manifest.json.record_counts.{path}",
                        f"manifest count must equal observed count {count}",
                    )
                )
    elif isinstance(required_counts, dict):
        if required_counts.get("tasks") != tasks_count:
            errors.append(
                issue(
                    "manifest.record_count_mismatch",
                    "manifest.json.required_counts.tasks",
                    f"manifest task count must equal observed count {tasks_count}",
                )
            )
        if required_counts.get("evidence_documents") != evidence_count:
            errors.append(
                issue(
                    "manifest.record_count_mismatch",
                    "manifest.json.required_counts.evidence_documents",
                    (
                        "manifest evidence count must equal observed count "
                        f"{evidence_count}"
                    ),
                )
            )
    else:
        errors.append(
            issue(
                "manifest.record_counts_missing",
                "manifest.json",
                "record_counts or required_counts object is required",
            )
        )
    allowlists = manifest.get("allowlists")
    expected_allowlists = {
        "evidence_modes": set(EXPECTED_EVIDENCE_MODES),
        "families": set(EXPECTED_FAMILIES),
        "patch_classes": set(EXPECTED_PATCH_CLASSES),
    }
    if isinstance(allowlists, dict):
        for key, expected in expected_allowlists.items():
            singular_alias = {
                "evidence_modes": "evidence_mode",
                "families": "family",
                "patch_classes": "patch_class",
            }[key]
            value = allowlists.get(key, allowlists.get(singular_alias))
            if not isinstance(value, list) or set(value) != expected:
                errors.append(
                    issue(
                        "manifest.allowlist_mismatch",
                        f"manifest.json.allowlists.{key}",
                        "manifest allowlist differs from the frozen release contract",
                    )
                )
    expected_counts = manifest.get("expected_counts")
    frozen_counts = {
        "evidence_mode": EXPECTED_EVIDENCE_MODES,
        "family": EXPECTED_FAMILIES,
        "patch_class": EXPECTED_PATCH_CLASSES,
    }
    if isinstance(expected_counts, dict):
        for key, expected in frozen_counts.items():
            if expected_counts.get(key) != expected:
                errors.append(
                    issue(
                        "manifest.expected_count_mismatch",
                        f"manifest.json.expected_counts.{key}",
                        "manifest distribution differs from the hard-coded contract",
                    )
                )
    elif isinstance(required_counts, dict):
        if required_counts.get("evidence_modes") != EXPECTED_EVIDENCE_MODES:
            errors.append(
                issue(
                    "manifest.expected_count_mismatch",
                    "manifest.json.required_counts.evidence_modes",
                    "manifest evidence-mode counts differ from frozen contract",
                )
            )
        if required_counts.get("family_each") != 10:
            errors.append(
                issue(
                    "manifest.expected_count_mismatch",
                    "manifest.json.required_counts.family_each",
                    "each frozen family must contain 10 tasks",
                )
            )
        if required_counts.get("patch_class_each") != 25:
            errors.append(
                issue(
                    "manifest.expected_count_mismatch",
                    "manifest.json.required_counts.patch_class_each",
                    "each frozen patch class must contain 25 tasks",
                )
            )
        if required_counts.get("unique_base_ids") != EXPECTED_TASKS:
            errors.append(
                issue(
                    "manifest.expected_count_mismatch",
                    "manifest.json.required_counts.unique_base_ids",
                    "manifest must require 100 unique base ids",
                )
            )
    else:
        errors.append(
            issue(
                "manifest.expected_counts_missing",
                "manifest.json",
                "expected_counts or required_counts is required",
            )
        )
    unresolved = manifest.get("unresolved", [])
    if unresolved != []:
        errors.append(
            issue(
                "manifest.unresolved",
                "manifest.json.unresolved",
                "manifest unresolved list must be empty",
            )
        )
    review_summary = manifest.get("review_summary")
    if isinstance(review_summary, dict):
        declared_agreement = review_summary.get("agreement")
        if not _is_number(declared_agreement):
            errors.append(
                issue(
                    "manifest.review_agreement_invalid",
                    "manifest.json.review_summary.agreement",
                    "agreement must be finite numeric",
                )
            )
        elif abs(float(declared_agreement) - review_agreement) > 1e-12:
            errors.append(
                issue(
                    "manifest.review_agreement_mismatch",
                    "manifest.json.review_summary.agreement",
                    "declared agreement differs from recomputed blind-label agreement",
                )
            )
    raw_files = manifest.get("files")
    if isinstance(raw_files, list):
        listed_paths = [
            str(entry.get("path")).replace("\\", "/")
            for entry in raw_files
            if isinstance(entry, dict) and _is_nonempty_string(entry.get("path"))
        ]
        if len(listed_paths) != len(set(listed_paths)):
            errors.append(
                issue(
                    "manifest.duplicate_file_entry",
                    "manifest.json.files",
                    "duplicate manifest paths are forbidden",
                )
            )
    entries = _manifest_file_entries(manifest)
    if manifest.get("file_hash_policy") != EXPECTED_FILE_HASH_POLICY:
        errors.append(
            issue(
                "manifest.hash_policy_mismatch",
                "manifest.json.file_hash_policy",
                "manifest must use canonical LF for UTF-8 text and raw frozen snapshots",
            )
        )
    if not entries:
        errors.append(
            issue(
                "manifest.files_missing",
                "manifest.json.files",
                "manifest must hash every released file",
            )
        )
        return errors

    actual_files: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        relative_parts = path.relative_to(root).parts
        if relative == "manifest.json":
            continue
        if relative_parts[0] in {".git", ".pytest_cache", "staging"}:
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if (
            relative_parts[0] == "reports"
            and (
                path.name == "release_gate.json"
                or path.name.endswith((".stdout.txt", ".stderr.txt"))
            )
        ):
            continue
        actual_files.add(relative)
    manifest_files = set(entries)
    missing_entries = sorted(actual_files - manifest_files)
    stale_entries = sorted(manifest_files - actual_files)
    for relative in missing_entries:
        errors.append(
            issue(
                "manifest.file_unhashed",
                relative,
                "released file is not listed in manifest",
            )
        )
    for relative in stale_entries:
        errors.append(
            issue(
                "manifest.file_missing",
                relative,
                "manifest references a missing file",
            )
        )
    for relative in sorted(actual_files & manifest_files):
        expected_hash = entries[relative].get("sha256")
        if not _is_sha256(expected_hash):
            errors.append(
                issue(
                    "manifest.hash_invalid",
                    f"manifest.json.files[{relative}].sha256",
                    "file digest must be SHA-256",
                )
            )
            continue
        payload = manifest_file_bytes(root / relative, root)
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != expected_hash.lower():
            errors.append(
                issue(
                    "manifest.hash_mismatch",
                    relative,
                    "file digest differs from manifest",
                )
            )
        expected_bytes = entries[relative].get("bytes")
        if expected_bytes is not None and expected_bytes != len(payload):
            errors.append(
                issue(
                    "manifest.byte_count_mismatch",
                    relative,
                    "file byte count differs from manifest",
                )
            )
    return errors


def _index_unique(
    rows: Sequence[Mapping[str, Any]], key: str, path: str
) -> tuple[dict[str, Mapping[str, Any]], list[Issue]]:
    index: dict[str, Mapping[str, Any]] = {}
    errors: list[Issue] = []
    for row_number, row in enumerate(rows, start=1):
        value = row.get(key)
        if not _is_nonempty_string(value):
            continue
        if value in index:
            errors.append(
                issue(
                    "schema.duplicate_id",
                    f"{path}:{row_number}.{key}",
                    f"duplicate {key} {value!r}",
                )
            )
        else:
            index[str(value)] = row
    return index, errors


def validate_dataset(root: Path) -> ValidationReport:
    root = root.resolve()
    report = ValidationReport()
    tasks, task_load_errors = load_jsonl(
        root / "public" / "tasks_zh.jsonl", "public/tasks_zh.jsonl"
    )
    evidence, evidence_load_errors = load_jsonl(
        root / "private" / "evidence_corpus.jsonl",
        "private/evidence_corpus.jsonl",
    )
    gold, gold_load_errors = load_jsonl(
        root / "private" / "gold.jsonl", "private/gold.jsonl"
    )
    report.extend(task_load_errors)
    report.extend(evidence_load_errors)
    report.extend(gold_load_errors)

    if len(tasks) != EXPECTED_TASKS:
        report.errors.append(
            issue(
                "dataset.task_count",
                "public/tasks_zh.jsonl",
                f"expected exactly {EXPECTED_TASKS} tasks, observed {len(tasks)}",
            )
        )
    if len(gold) != EXPECTED_TASKS:
        report.errors.append(
            issue(
                "dataset.gold_count",
                "private/gold.jsonl",
                f"expected exactly {EXPECTED_TASKS} gold rows, observed {len(gold)}",
            )
        )
    task_index, task_index_errors = _index_unique(
        tasks, "id", "public/tasks_zh.jsonl"
    )
    evidence_index, evidence_index_errors = _index_unique(
        evidence, "id", "private/evidence_corpus.jsonl"
    )
    gold_index, gold_index_errors = _index_unique(
        gold, "id", "private/gold.jsonl"
    )
    report.extend(task_index_errors)
    report.extend(evidence_index_errors)
    report.extend(gold_index_errors)
    if set(task_index) != set(gold_index):
        report.errors.append(
            issue(
                "dataset.task_gold_id_mismatch",
                "private/gold.jsonl",
                "public and gold id sets must match exactly",
            )
        )

    for row_number, task in enumerate(tasks, start=1):
        report.extend(
            validate_public_task(task, f"public/tasks_zh.jsonl:{row_number}")
        )
        report.extend(_find_unresolved(task, f"public/tasks_zh.jsonl:{row_number}"))
    for row_number, evidence_row in enumerate(evidence, start=1):
        report.extend(
            validate_evidence_record(
                evidence_row, f"private/evidence_corpus.jsonl:{row_number}"
            )
        )
    for row_number, gold_row in enumerate(gold, start=1):
        report.extend(
            validate_gold_record(
                gold_row,
                f"private/gold.jsonl:{row_number}",
                task=task_index.get(str(gold_row.get("id"))),
                evidence_by_id=evidence_index,
                root=root,
            )
        )

    base_ids = [row.get("base_id") for row in gold if _is_nonempty_string(row.get("base_id"))]
    if len(base_ids) != EXPECTED_TASKS or len(set(base_ids)) != EXPECTED_TASKS:
        report.errors.append(
            issue(
                "dataset.base_id_not_unique",
                "private/gold.jsonl",
                "100 tasks must have 100 unique base_id values",
            )
        )
    distributions = {
        "evidence_mode": collections.Counter(row.get("evidence_mode") for row in gold),
        "family": collections.Counter(row.get("family") for row in gold),
        "patch_class": collections.Counter(row.get("patch_class") for row in gold),
    }
    expected_distributions = {
        "evidence_mode": EXPECTED_EVIDENCE_MODES,
        "family": EXPECTED_FAMILIES,
        "patch_class": EXPECTED_PATCH_CLASSES,
    }
    for key, expected in expected_distributions.items():
        observed = dict(distributions[key])
        if observed != expected:
            report.errors.append(
                issue(
                    f"dataset.{key}_distribution",
                    "private/gold.jsonl",
                    f"expected {expected}, observed {observed}",
                )
            )
    family_mode_pairs = collections.Counter(
        (row.get("family"), row.get("evidence_mode")) for row in gold
    )
    for family in EXPECTED_FAMILIES:
        if family_mode_pairs[(family, "fresh-private")] != 8:
            report.errors.append(
                issue(
                    "dataset.family_private_balance",
                    "private/gold.jsonl",
                    f"{family} must contain exactly 8 fresh-private tasks",
                )
            )
        if family_mode_pairs[(family, "real-web")] != 2:
            report.errors.append(
                issue(
                    "dataset.family_web_balance",
                    "private/gold.jsonl",
                    f"{family} must contain exactly 2 real-web tasks",
                )
            )

    referenced_evidence_ids: set[str] = set()
    for gold_row in gold:
        applicability = gold_row.get("applicability")
        comparison = (
            applicability.get("comparison")
            if isinstance(applicability, dict)
            else None
        )
        if not isinstance(comparison, list):
            continue
        for comparison_row in comparison:
            if isinstance(comparison_row, dict) and _is_nonempty_string(
                comparison_row.get("evidence_id")
            ):
                referenced_evidence_ids.add(str(comparison_row["evidence_id"]))
    unreferenced_evidence = set(evidence_index) - referenced_evidence_ids
    missing_evidence = referenced_evidence_ids - set(evidence_index)
    for evidence_id in sorted(unreferenced_evidence):
        report.errors.append(
            issue(
                "evidence.unreferenced",
                f"private/evidence_corpus.jsonl[{evidence_id}]",
                "every corpus document must participate in a frozen comparison bundle",
            )
        )
    for evidence_id in sorted(missing_evidence):
        report.errors.append(
            issue(
                "evidence.referenced_missing",
                f"private/gold.jsonl[{evidence_id}]",
                "comparison references a missing corpus document",
            )
        )

    agreement = compute_review_agreement(gold)
    if agreement < 0.8:
        report.errors.append(
            issue(
                "review.agreement_below_threshold",
                "private/gold.jsonl",
                f"recomputed blind-label agreement {agreement:.6f} is below 0.8",
            )
        )

    manifest, manifest_load_errors = _parse_json_file(
        root / "manifest.json", "manifest.json"
    )
    report.extend(manifest_load_errors)
    if manifest is not None:
        report.extend(
            validate_manifest(
                root,
                manifest,
                tasks_count=len(tasks),
                evidence_count=len(evidence),
                gold_count=len(gold),
                review_agreement=agreement,
            )
        )
        report.extend(_find_unresolved(manifest, "manifest.json"))

    report.stats.update(
        {
            "tasks": len(tasks),
            "evidence_records": len(evidence),
            "gold_records": len(gold),
            "unique_base_ids": len(set(base_ids)),
            "distributions": {
                key: {
                    ("<missing>" if counter_key is None else str(counter_key)): count
                    for counter_key, count in value.items()
                }
                for key, value in distributions.items()
            },
            "review_agreement": agreement,
        }
    )
    return report


def _format_human(report: ValidationReport) -> str:
    status = "PASS" if report.ok else "FAIL"
    lines = [
        f"SearchWorthyOR-100 schema gate: {status}",
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
    args = parser.parse_args(argv)
    report = validate_dataset(args.root)
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_format_human(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
