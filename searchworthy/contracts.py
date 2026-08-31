"""Typed contracts for SearchWorthy's OR-specific information-effect state.

These objects are the auditable boundary between model proposals and
program-owned checks.  They are not a generic conversation-memory schema:
facts, gaps, targets, evidence, patches, and solves all refer to an explicit OR
model interface.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any


class FactUsageStatus(str, Enum):
    MODELED = "MODELED"
    APPLICABILITY_USED = "APPLICABILITY_USED"
    DERIVED = "DERIVED"
    IRRELEVANT_JUSTIFIED = "IRRELEVANT_JUSTIFIED"
    UNACCOUNTED = "UNACCOUNTED"


class GapRoute(str, Enum):
    EXTERNAL_RULE = "EXTERNAL_RULE"
    LOCAL_FACT = "LOCAL_FACT"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class TargetBindingStatus(str, Enum):
    BOUND = "BOUND"
    UNBOUND = "UNBOUND"


class PotentialEffect(str, Enum):
    UNKNOWN = "UNKNOWN"
    NO_EFFECT = "NO_EFFECT"
    VALUE_CHANGE = "VALUE_CHANGE"
    DECISION_CHANGE = "DECISION_CHANGE"
    FEASIBILITY_CHANGE = "FEASIBILITY_CHANGE"


class GapState(str, Enum):
    OPEN = "OPEN"
    NEED_SEARCH = "NEED_SEARCH"
    PATCH_READY = "PATCH_READY"
    CLOSED_NO_SEARCH = "CLOSED_NO_SEARCH"
    CLOSED_RETAIN = "CLOSED_RETAIN"
    CLOSED_PATCH = "CLOSED_PATCH"
    UNRESOLVED_ABSTAIN = "UNRESOLVED_ABSTAIN"


class AuditDimension(str, Enum):
    SUBJECT_ELIGIBILITY = "SUBJECT_ELIGIBILITY"
    LOCATION_JURISDICTION = "LOCATION_JURISDICTION"
    TIME_VERSION = "TIME_VERSION"
    OBJECT_SCOPE = "OBJECT_SCOPE"
    UNIT_THRESHOLD = "UNIT_THRESHOLD"
    CAPACITY_FEASIBILITY = "CAPACITY_FEASIBILITY"
    EXCEPTION_EXEMPTION = "EXCEPTION_EXEMPTION"
    ACTION_CONSEQUENCE = "ACTION_CONSEQUENCE"
    COST_BENEFIT = "COST_BENEFIT"


REGISTERED_APPLICABILITY_TARGETS = frozenset(
    f"applicability.{dimension.value.lower()}" for dimension in AuditDimension
)


class Admission(str, Enum):
    REJECT = "REJECT"
    NOT_APPLIES = "NOT_APPLIES"
    ALREADY_MODELED = "ALREADY_MODELED"
    ADMIT_PATCH = "ADMIT_PATCH"
    CONFLICT = "CONFLICT"


class EvidenceRoute(str, Enum):
    SEARCH_AGAIN = "SEARCH_AGAIN"
    RETAIN = "RETAIN"
    PATCH = "PATCH"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class PublicCase:
    eval_id: str
    prompt_zh: str


@dataclass
class AuditSummary:
    prompt_fact_to_model_complete: bool
    model_interface_to_grounding_complete: bool
    negative_space_checked: dict[AuditDimension, bool]
    overflow_detected: bool = False
    overflow_count: int = 0
    self_contained_reason: str | None = None
    prompt_fact_unit_total: int = 0
    prompt_fact_unit_covered: int = 0
    prompt_fact_coverage_ratio: float = 0.0


@dataclass(frozen=True)
class FactCoverageDraft:
    quote: str
    or_role: str
    mapped_targets: list[str]
    usage_status: FactUsageStatus
    reason: str


@dataclass(frozen=True)
class CandidateGapDraft:
    fact_quotes: list[str]
    reality_role: str
    gap_claim: str
    target: str
    gap_route: GapRoute
    hypothetical_variants: list[dict[str, Any]]
    first_query: str | None


@dataclass
class InitialDecision:
    model_ir: dict[str, Any]
    fact_coverage: list[FactCoverageDraft]
    audit_summary: AuditSummary
    candidate_gaps: list[CandidateGapDraft]
    self_contained_candidate: bool


@dataclass
class SolveCapture:
    status: str
    feasible: bool
    actions: list[dict[str, int]] | None
    objective: dict[str, Any] | None
    solver_status: int | str | None
    diagnostic: dict[str, Any] = field(default_factory=dict)


@dataclass
class FactCoverageRow:
    fact_id: str
    quote: str
    or_role: str
    mapped_targets: list[str]
    usage_status: FactUsageStatus
    reason: str
    gap_id: str | None


@dataclass
class ModelingGapRow:
    """One missing reality-to-OR link and its complete decision-impact history."""

    gap_id: str
    fact_quotes: list[str]
    reality_role: str
    gap_claim: str
    target: str | None
    proposed_information_target: str
    target_binding_status: TargetBindingStatus
    gap_route: GapRoute
    potential_effect: PotentialEffect = PotentialEffect.UNKNOWN
    probe_coverage: bool = False
    evidence: dict[str, Any] | None = None
    patch: dict[str, Any] | None = None
    realized_effect: dict[str, Any] | None = None
    pending_query: str | None = None
    state: GapState = GapState.OPEN


@dataclass
class DecisionCompleteORState:
    """Program-owned state required before a reality-grounded answer may close."""

    eval_id: str
    input_digest: str
    round: int
    search_budget_left: int
    base_ir_digest: str
    current_ir_digest: str
    base_solve: SolveCapture
    current_solve: SolveCapture
    audit_summary: AuditSummary
    self_contained: bool
    fact_coverage: list[FactCoverageRow]
    active_gap_id: str | None
    gaps: list[ModelingGapRow]
    information_audit_failure: dict[str, Any] | None = None
    evidence_ledger: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceCard:
    evidence_id: str
    url: str
    quote: str
    claim: str
    case_quote: str
    scope_quote: str
    target: str
    supported: bool
    applies: bool
    bindable: bool
    consistent: bool
    binding_path: str | None = None
    binding_value: Any = None


@dataclass(frozen=True)
class PatchPlan:
    patch_family: str
    target: str
    parameters: dict[str, Any]
    before_guard: Any
    evidence_ids: list[str]


@dataclass
class EvidenceDecision:
    evidence_cards: list[EvidenceCard]
    admission: Admission
    patch_plan: PatchPlan | None
    next_query: str | None
    reason: str


@dataclass(frozen=True)
class SearchDecision:
    authorized: bool
    reason: str
    query: str | None


@dataclass
class RetrievalTrace:
    gap_id: str
    planned_query: str
    query_attempted: bool
    executed_query: str | None = None
    executed_queries: list[str] = field(default_factory=list)
    query_budget_consumed: int = 1
    results_discarded: bool = False
    backend_raw_result_count: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    opened_pages: list[dict[str, Any]] = field(default_factory=list)
    page_attempts: list[dict[str, Any]] = field(default_factory=list)
    failure_type: str | None = None
    failure_detail: str | None = None
    wall_seconds: float = 0.0


@dataclass(frozen=True)
class PatchOperation:
    op: str
    target: str
    before: Any
    after: Any


@dataclass(frozen=True)
class PatchBundle:
    gap_id: str
    evidence_ids: list[str]
    operations: list[PatchOperation]


@dataclass(frozen=True)
class StateUpdate:
    kind: str
    gap_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def probe(
        cls,
        gap_id: str,
        effect: PotentialEffect,
        coverage: bool,
        reason: str,
        exhaustive_local: bool = False,
    ) -> "StateUpdate":
        return cls(
            "PROBE",
            gap_id,
            {
                "effect": effect,
                "coverage": coverage,
                "reason": reason,
                "exhaustive_local": exhaustive_local,
            },
        )

    @classmethod
    def search_authorized(cls, gap_id: str) -> "StateUpdate":
        return cls("SEARCH_AUTHORIZED", gap_id)

    @classmethod
    def search_again(cls, gap_id: str, query: str) -> "StateUpdate":
        return cls("SEARCH_AGAIN", gap_id, {"query": query})

    @classmethod
    def retain(cls, gap_id: str, evidence: dict[str, Any], already_modeled: bool) -> "StateUpdate":
        return cls("RETAIN", gap_id, {"evidence": evidence, "already_modeled": already_modeled})

    @classmethod
    def patch_ready(cls, gap_id: str, evidence: dict[str, Any]) -> "StateUpdate":
        return cls("PATCH_READY", gap_id, {"evidence": evidence})

    @classmethod
    def patch_closed(
        cls, gap_id: str, patch: dict[str, Any], realized_effect: dict[str, Any]
    ) -> "StateUpdate":
        return cls("PATCH_CLOSED", gap_id, {"patch": patch, "realized_effect": realized_effect})

    @classmethod
    def evidence_observed(cls, gap_id: str, cards: list[dict[str, Any]]) -> "StateUpdate":
        return cls("EVIDENCE_OBSERVED", gap_id, {"cards": cards})

    @classmethod
    def abstain(cls, gap_id: str, reason: str) -> "StateUpdate":
        return cls("ABSTAIN", gap_id, {"reason": reason})


def jsonable(value: Any) -> Any:
    """Convert dataclasses and string enums into deterministic JSON values."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(jsonable(key)): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


INITIAL_DECISION_JSON_SCHEMA: dict[str, Any] = {
    "name": "InitialDecision",
    "required": ["model_ir", "fact_coverage", "audit_summary", "candidate_gaps", "self_contained_candidate"],
    "fact_usage_status": [status.value for status in FactUsageStatus if status != FactUsageStatus.IRRELEVANT_JUSTIFIED],
    "gap_routes": [route.value for route in GapRoute],
    "audit_dimensions": [dimension.value for dimension in AuditDimension],
    "max_candidate_gaps": 3,
    "max_hypothetical_variants_per_gap": 3,
}


EVIDENCE_DECISION_JSON_SCHEMA: dict[str, Any] = {
    "name": "EvidenceDecision",
    "required": ["evidence_cards", "admission", "patch_plan", "next_query", "reason"],
    "admissions": [admission.value for admission in Admission],
    "hard_gate": "SUPPORTED && APPLIES && BINDABLE && CONSISTENT",
    "executable_patch_families": ["SET_VARIABLE_BOUNDS", "SET_OBJECTIVE_COEFFICIENT"],
    "not_applies_closure": "DISABLED_UNTIL_STRUCTURED_SCOPE_ATOMS",
}


def _exact_dict(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} must contain exactly {sorted(keys)}")
    return value


def _finite_probe_bound(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError("hypothetical variable bound must be finite")
    return float(value)


def _validate_hypothetical_variants(value: list[Any], target: str) -> None:
    """Keep the V0 trigger range program-owned and deliberately narrow."""
    if not value:
        return
    if not target.startswith("variable."):
        raise ValueError("V0 hypothetical variants only support variable.* targets")
    assignments: set[int] = set()
    for item in value:
        variant = _exact_dict(
            item,
            {"target", "operation", "value", "range_basis", "basis_quote"},
            "hypothetical variant",
        )
        if (
            variant["target"] != target
            or variant["operation"] != "SET"
            or variant["range_basis"] != "MODEL_BOUNDARY"
            or variant["basis_quote"] is not None
        ):
            raise ValueError("V0 hypothetical variant is not a program-owned variable-bound probe")
        bounds = _exact_dict(variant["value"], {"lb", "ub"}, "hypothetical variable value")
        lower, upper = _finite_probe_bound(bounds["lb"]), _finite_probe_bound(bounds["ub"])
        if lower != 0.0 or upper != 0.0:
            raise ValueError("V0 eligibility probe may only disable the action")
        assignments.add(int(lower))
    if len(value) != 1 or assignments != {0}:
        raise ValueError("V0 variable gap requires exactly one zero-fixed disable probe")


def parse_audit_summary(value: Any) -> AuditSummary:
    row = _exact_dict(
        value,
        {
            "prompt_fact_to_model_complete",
            "model_interface_to_grounding_complete",
            "negative_space_checked",
            "overflow_detected",
            "overflow_count",
            "self_contained_reason",
        },
        "audit_summary",
    )
    checked = row["negative_space_checked"]
    expected = {item.value for item in AuditDimension}
    if not isinstance(checked, dict) or set(checked) != expected or any(not isinstance(v, bool) for v in checked.values()):
        raise ValueError("negative_space_checked must contain exactly the nine OR audit dimensions")
    if not isinstance(row["prompt_fact_to_model_complete"], bool) or not isinstance(
        row["model_interface_to_grounding_complete"], bool
    ):
        raise ValueError("bidirectional audit flags must be boolean")
    if (
        not isinstance(row["overflow_detected"], bool)
        or not isinstance(row["overflow_count"], int)
        or isinstance(row["overflow_count"], bool)
    ):
        raise ValueError("overflow fields are invalid")
    if row["overflow_count"] < 0 or row["overflow_detected"] != (row["overflow_count"] > 0):
        raise ValueError("overflow_detected and overflow_count disagree")
    reason = row["self_contained_reason"]
    if reason is not None and not isinstance(reason, str):
        raise ValueError("self_contained_reason must be a string or null")
    return AuditSummary(
        prompt_fact_to_model_complete=row["prompt_fact_to_model_complete"],
        model_interface_to_grounding_complete=row["model_interface_to_grounding_complete"],
        negative_space_checked={AuditDimension(key): checked[key] for key in checked},
        overflow_detected=row["overflow_detected"],
        overflow_count=row["overflow_count"],
        self_contained_reason=reason.strip() if isinstance(reason, str) else None,
    )


def parse_initial_decision(value: Any) -> InitialDecision:
    row = _exact_dict(
        value,
        {"model_ir", "fact_coverage", "audit_summary", "candidate_gaps", "self_contained_candidate"},
        "InitialDecision",
    )
    if not isinstance(row["model_ir"], dict) or not isinstance(row["self_contained_candidate"], bool):
        raise ValueError("InitialDecision model_ir or self_contained_candidate is invalid")
    facts_value = row["fact_coverage"]
    if not isinstance(facts_value, list) or not facts_value:
        raise ValueError("fact_coverage must be non-empty")
    facts: list[FactCoverageDraft] = []
    for item in facts_value:
        fact = _exact_dict(item, {"quote", "or_role", "mapped_targets", "usage_status", "reason"}, "fact")
        if not all(isinstance(fact[key], str) and fact[key].strip() for key in ("quote", "or_role", "reason")):
            raise ValueError("fact text fields must be non-empty")
        if not isinstance(fact["mapped_targets"], list) or any(
            not isinstance(v, str) or not v or v != v.strip()
            for v in fact["mapped_targets"]
        ):
            raise ValueError("mapped_targets must be exact non-empty canonical strings")
        status = FactUsageStatus(fact["usage_status"])
        if status == FactUsageStatus.IRRELEVANT_JUSTIFIED:
            raise ValueError("InitialDecision cannot claim IRRELEVANT_JUSTIFIED")
        facts.append(
            FactCoverageDraft(
                quote=fact["quote"].strip(),
                or_role=fact["or_role"].strip(),
                mapped_targets=[v.strip() for v in fact["mapped_targets"]],
                usage_status=status,
                reason=fact["reason"].strip(),
            )
        )
    gaps_value = row["candidate_gaps"]
    if not isinstance(gaps_value, list) or len(gaps_value) > 3:
        raise ValueError("candidate_gaps must be a list with at most three rows; use audit overflow fields for extras")
    gaps: list[CandidateGapDraft] = []
    for item in gaps_value:
        gap = _exact_dict(
            item,
            {
                "fact_quotes",
                "reality_role",
                "gap_claim",
                "target",
                "gap_route",
                "hypothetical_variants",
                "first_query",
            },
            "candidate gap",
        )
        if not isinstance(gap["fact_quotes"], list) or not gap["fact_quotes"] or any(
            not isinstance(v, str) or not v.strip() for v in gap["fact_quotes"]
        ):
            raise ValueError("gap fact_quotes must be non-empty strings")
        if not all(isinstance(gap[key], str) and gap[key].strip() for key in ("reality_role", "gap_claim", "target")):
            raise ValueError("gap text fields must be non-empty")
        if gap["target"] != gap["target"].strip():
            raise ValueError("gap target must use an exact canonical spelling without surrounding whitespace")
        variants = gap["hypothetical_variants"]
        if not isinstance(variants, list) or len(variants) > 3 or any(not isinstance(v, dict) for v in variants):
            raise ValueError("hypothetical_variants must contain at most three objects")
        _validate_hypothetical_variants(variants, gap["target"])
        query = gap["first_query"]
        if query is not None and (not isinstance(query, str) or not query.strip()):
            raise ValueError("first_query must be a non-empty string or null")
        gaps.append(
            CandidateGapDraft(
                fact_quotes=[v.strip() for v in gap["fact_quotes"]],
                reality_role=gap["reality_role"].strip(),
                gap_claim=gap["gap_claim"].strip(),
                target=gap["target"].strip(),
                gap_route=GapRoute(gap["gap_route"]),
                hypothetical_variants=variants,
                first_query=query.strip() if isinstance(query, str) else None,
            )
        )
    return InitialDecision(
        model_ir=row["model_ir"],
        fact_coverage=facts,
        audit_summary=parse_audit_summary(row["audit_summary"]),
        candidate_gaps=gaps,
        self_contained_candidate=row["self_contained_candidate"],
    )


def parse_evidence_decision(value: Any) -> EvidenceDecision:
    row = _exact_dict(value, {"evidence_cards", "admission", "patch_plan", "next_query", "reason"}, "EvidenceDecision")
    cards_value = row["evidence_cards"]
    if not isinstance(cards_value, list):
        raise ValueError("evidence_cards must be a list")
    cards: list[EvidenceCard] = []
    seen: set[str] = set()
    card_keys = {
        "evidence_id",
        "url",
        "quote",
        "claim",
        "case_quote",
        "scope_quote",
        "target",
        "supported",
        "applies",
        "bindable",
        "consistent",
        "binding_path",
        "binding_value",
    }
    for item in cards_value:
        card = _exact_dict(item, card_keys, "EvidenceCard")
        evidence_id = card["evidence_id"]
        if not isinstance(evidence_id, str) or not evidence_id or evidence_id in seen:
            raise ValueError("evidence_id must be non-empty and unique")
        if not all(isinstance(card[key], str) and card[key].strip() for key in ("url", "quote", "claim", "target")):
            raise ValueError("EvidenceCard source, quote, claim and target must be non-empty")
        if not isinstance(card["case_quote"], str) or not isinstance(card["scope_quote"], str):
            raise ValueError("EvidenceCard applicability quotes must be strings")
        if any(not isinstance(card[key], bool) for key in ("supported", "applies", "bindable", "consistent")):
            raise ValueError("EvidenceCard gate values must be boolean")
        binding_path = card["binding_path"]
        if binding_path is not None and (not isinstance(binding_path, str) or not binding_path.strip()):
            raise ValueError("EvidenceCard binding_path must be a non-empty string or null")
        if (binding_path is None) != (card["binding_value"] is None):
            raise ValueError("EvidenceCard binding_path and binding_value must either both be present or both be null")
        card["binding_path"] = binding_path.strip() if isinstance(binding_path, str) else None
        seen.add(evidence_id)
        cards.append(EvidenceCard(**card))
    plan_value = row["patch_plan"]
    plan: PatchPlan | None = None
    if plan_value is not None:
        patch = _exact_dict(plan_value, {"patch_family", "target", "parameters", "before_guard", "evidence_ids"}, "PatchPlan")
        if not isinstance(patch["patch_family"], str) or not isinstance(patch["target"], str) or not isinstance(
            patch["parameters"], dict
        ):
            raise ValueError("PatchPlan family, target or parameters are invalid")
        if not isinstance(patch["evidence_ids"], list) or any(not isinstance(v, str) for v in patch["evidence_ids"]):
            raise ValueError("PatchPlan evidence_ids must be strings")
        plan = PatchPlan(**patch)
    query = row["next_query"]
    if query is not None and (not isinstance(query, str) or not query.strip()):
        raise ValueError("next_query must be a non-empty string or null")
    if not isinstance(row["reason"], str) or not row["reason"].strip():
        raise ValueError("EvidenceDecision reason must be non-empty")
    return EvidenceDecision(
        evidence_cards=cards,
        admission=Admission(row["admission"]),
        patch_plan=plan,
        next_query=query.strip() if isinstance(query, str) else None,
        reason=row["reason"].strip(),
    )
