"""Search authorization and evidence-admission hard gates.

Search is authorized only for an active external-rule gap with solver-observed
potential effect and remaining budget.  A Patch requires every cited card to
pass SUPPORTED, APPLIES, BINDABLE, and CONSISTENT; the program recomputes the
observable quote/binding parts and preserves the remaining semantic limits for
audit.
"""

from __future__ import annotations

import copy
import re
import urllib.parse
from dataclasses import replace
from typing import Any, Callable

from .contracts import (
    Admission,
    DecisionCompleteORState,
    EvidenceCard,
    EvidenceDecision,
    EvidenceRoute,
    GapRoute,
    GapState,
    RetrievalTrace,
    SearchDecision,
    jsonable,
)
from .or_model import ValidatedIR, target_exists_or_legal_slot, target_value
from .patch import PatchValidationError, cards_bind_patch_plan
from .state import SIGNIFICANT_EFFECTS


def _collapse(value: str) -> str:
    return " ".join(str(value).split())


def _contains(text: str, quote: str) -> bool:
    return bool(quote.strip()) and _collapse(quote) in _collapse(text)


def _canonical_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))


_BINDING_PATHS = {
    "target_value",
    "parameters",
    "parameters.coefficient",
    "parameters.lb",
    "parameters.ub",
    "parameters.constraint.rhs",
    "parameters.constraint.sense",
}


def _scalar_visible_in_quote(value: Any, quote: str) -> bool:
    """Lexically verify scalar evidence values; structured values are compared later."""
    if isinstance(value, bool):
        terms = ("true", "是", "适用") if value else ("false", "否", "不适用")
        return any(term in quote.lower() for term in terms)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        rendered = format(float(value), "g")
        return re.search(rf"(?<![0-9.]){re.escape(rendered)}(?![0-9.])", quote) is not None
    if isinstance(value, str):
        equivalents = {
            "<=": ("<=", "≤", "不超过", "不得超过", "至多", "上限"),
            ">=": (">=", "≥", "不少于", "不得少于", "至少", "下限"),
            "==": ("==", "=", "等于", "恰好", "必须为"),
        }
        candidates = equivalents.get(value, (value,))
        return any(candidate and candidate in quote for candidate in candidates)
    return False


def _verified_binding(card: EvidenceCard, quote_ok: bool) -> bool:
    if card.binding_path is None:
        return card.binding_value is None
    return (
        card.binding_path in _BINDING_PATHS
        and quote_ok
        and _scalar_visible_in_quote(card.binding_value, card.quote)
    )


def _expanded_binding_pairs(target: str, path: str, value: Any) -> list[tuple[str, Any]]:
    if path != "target_value":
        return [(path, value)]
    family = target.split(".", 1)[0]
    if family == "objective":
        return [("parameters.coefficient", value)]
    if family == "variable" and isinstance(value, dict):
        return [(f"parameters.{key}", value[key]) for key in ("lb", "ub") if key in value]
    if family == "constraint" and isinstance(value, dict):
        return [
            (f"parameters.constraint.{key}", value[key])
            for key in ("rhs", "sense")
            if key in value
        ]
    return [(path, value)]


def _binding_conflict_paths(
    state: DecisionCompleteORState,
    target: str,
    cards: list[EvidenceCard],
) -> set[str]:
    values: dict[str, list[Any]] = {}
    for row in state.evidence_ledger:
        if (
            row.get("target") == target
            and isinstance(row.get("binding_path"), str)
            and row.get("supported") is True
            and row.get("applies") is True
            and row.get("bindable") is True
        ):
            for path, value in _expanded_binding_pairs(
                target,
                row["binding_path"],
                row.get("binding_value"),
            ):
                values.setdefault(path, []).append(value)
    for card in cards:
        if (
            card.target == target
            and card.binding_path is not None
            and card.supported
            and card.applies
            and card.bindable
        ):
            for path, value in _expanded_binding_pairs(card.target, card.binding_path, card.binding_value):
                values.setdefault(path, []).append(value)
    return {
        path
        for path, observed in values.items()
        if len(observed) > 1 and any(value != observed[0] for value in observed[1:])
    }


def validate_query(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("search query must be non-empty")
    normalized = _collapse(query)
    if len(normalized) > 320 or len(re.findall(r"(?i)\bsite\s*:", normalized)) > 1:
        raise ValueError("search query exceeds the fixed query contract")
    lowered = normalized.lower()
    forbidden = ("searchworthyor", "gold", "private", "output_schema", "source_task", "c1", "c2", "c3", "\\", "/runs/")
    if any(token in lowered for token in forbidden):
        raise ValueError("search query contains benchmark/private/runtime identifiers")
    return normalized


def authorize_search(state: DecisionCompleteORState, gap_id: str) -> SearchDecision:
    """Apply the fixed search boundary; this function never performs retrieval."""

    gap = next((row for row in state.gaps if row.gap_id == gap_id), None)
    if gap is None:
        return SearchDecision(False, "UNKNOWN_GAP", None)
    if state.active_gap_id not in {None, gap_id}:
        return SearchDecision(False, "ANOTHER_GAP_ACTIVE", None)
    if gap.state != GapState.OPEN:
        return SearchDecision(False, "GAP_NOT_OPEN", None)
    if gap.gap_route != GapRoute.EXTERNAL_RULE:
        return SearchDecision(False, f"GAP_ROUTE_{gap.gap_route.value}", None)
    if gap.potential_effect not in SIGNIFICANT_EFFECTS:
        return SearchDecision(False, "NO_SOLVER_CRITICAL_EFFECT", None)
    if state.search_budget_left <= 0:
        return SearchDecision(False, "SEARCH_BUDGET_EXHAUSTED", None)
    try:
        query = validate_query(gap.pending_query or "")
    except ValueError:
        return SearchDecision(False, "MISSING_OR_INVALID_QUERY", None)
    return SearchDecision(True, "SOLVER_IMPACT_AUTHORIZED", query)


def search_round(
    state: DecisionCompleteORState,
    gap_id: str,
    query: str,
    searcher: Callable[[str, str], RetrievalTrace],
) -> RetrievalTrace:
    if state.active_gap_id != gap_id:
        raise ValueError("search_round may only run for the active gap")
    normalized = validate_query(query)
    trace = searcher(gap_id, normalized)
    if not isinstance(trace, RetrievalTrace) or trace.gap_id != gap_id or trace.planned_query != normalized:
        raise ValueError("search backend returned a mismatched RetrievalTrace")
    return trace


def assess_evidence(
    proposed: EvidenceDecision,
    state: DecisionCompleteORState,
    gap_id: str,
    trace: RetrievalTrace,
    prompt_zh: str,
    current_ir: ValidatedIR,
) -> EvidenceDecision:
    """Recompute observable gates; ``consistent`` remains partly model-authored.

    Same-target structured binding conflicts are rejected programmatically, but
    this function does not claim general semantic consistency proof.
    """
    gap = next((row for row in state.gaps if row.gap_id == gap_id), None)
    if gap is None or gap.state != GapState.NEED_SEARCH:
        raise ValueError("evidence assessment requires a NEED_SEARCH gap")
    pages: dict[str, dict[str, Any]] = {}
    for page in trace.opened_pages:
        if not isinstance(page, dict):
            continue
        url = str(page.get("final_url") or page.get("url") or "")
        if url:
            pages[_canonical_url(url)] = page

    verified_cards: list[EvidenceCard] = []
    for card in proposed.evidence_cards:
        canonical_url = _canonical_url(card.url)
        page = pages.get(canonical_url)
        page_text = str(page.get("visible_text") or "") if page else ""
        quote_ok = bool(page) and _contains(page_text, card.quote)
        scope_ok = bool(page) and _contains(page_text, card.scope_quote)
        case_ok = _contains(prompt_zh, card.case_quote)
        target_ok = card.target == gap.target and target_exists_or_legal_slot(current_ir, card.target)
        supported = card.supported and quote_ok
        applies = card.applies and scope_ok and case_ok
        binding_ok = _verified_binding(card, quote_ok)
        bindable = card.bindable and target_ok and binding_ok
        consistent = card.consistent
        verified_cards.append(
            EvidenceCard(
                evidence_id=card.evidence_id,
                url=canonical_url,
                quote=_collapse(card.quote),
                claim=card.claim.strip(),
                case_quote=_collapse(card.case_quote),
                scope_quote=_collapse(card.scope_quote),
                target=card.target,
                supported=supported,
                applies=applies,
                bindable=bindable,
                consistent=consistent,
                binding_path=card.binding_path,
                binding_value=copy.deepcopy(card.binding_value),
            )
        )

    conflict_paths = _binding_conflict_paths(state, gap.target, verified_cards)
    if conflict_paths:
        verified_cards = [
            replace(card, consistent=False)
            if card.binding_path is not None
            and any(
                path in conflict_paths
                for path, _ in _expanded_binding_pairs(card.target, card.binding_path, card.binding_value)
            )
            else card
            for card in verified_cards
        ]

    admission = proposed.admission
    reason = proposed.reason
    hard_cards = [
        card
        for card in verified_cards
        if card.supported and card.applies and card.bindable and card.consistent
    ]
    by_id = {card.evidence_id: card for card in hard_cards}
    if conflict_paths:
        admission = Admission.CONFLICT
        reason = "verified same-target evidence has conflicting structured bindings: " + ", ".join(sorted(conflict_paths))
    elif admission == Admission.ADMIT_PATCH:
        plan = proposed.patch_plan
        try:
            valid = (
                plan is not None
                and plan.target == gap.target
                and bool(plan.evidence_ids)
                and set(plan.evidence_ids).issubset(by_id)
                and cards_bind_patch_plan([by_id[evidence_id] for evidence_id in plan.evidence_ids], plan)
            )
        except PatchValidationError:
            valid = False
        if not valid:
            admission, reason = Admission.REJECT, "ADMIT_PATCH failed a hard gate or exact evidence-to-Patch binding"
    elif admission == Admission.NOT_APPLIES:
        # Two verbatim quotes prove that text exists, not that their scope atoms
        # mismatch.  V0 has no deterministic jurisdiction/time/entity atom
        # comparator, so a model-authored applies=false may never close a gap.
        admission, reason = (
            Admission.REJECT,
            "NOT_APPLIES is disabled until structured scope atoms can prove a case/source mismatch",
        )
    elif admission == Admission.ALREADY_MODELED:
        current = target_value(current_ir, gap.target)
        if (
            not isinstance(current, (str, int, float, bool))
            or not hard_cards
            or not any(card.binding_path == "target_value" and card.binding_value == current for card in hard_cards)
            or proposed.patch_plan is not None
        ):
            admission, reason = Admission.REJECT, "ALREADY_MODELED lacks a quote-grounded scalar equal to the canonical IR target"
    elif admission == Admission.CONFLICT:
        conflict = any(card.supported and not card.consistent for card in verified_cards)
        if not conflict:
            admission, reason = Admission.REJECT, "CONFLICT lacks a verified conflicting evidence card"
    elif proposed.patch_plan is not None:
        admission, reason = Admission.REJECT, "REJECT cannot carry a PatchPlan"

    return EvidenceDecision(
        evidence_cards=verified_cards,
        admission=admission,
        patch_plan=proposed.patch_plan if admission == Admission.ADMIT_PATCH else None,
        next_query=proposed.next_query,
        reason=reason,
    )


def route_evidence(decision: EvidenceDecision, search_budget_left: int) -> EvidenceRoute:
    if decision.admission in {Admission.REJECT, Admission.CONFLICT}:
        return EvidenceRoute.SEARCH_AGAIN if search_budget_left > 0 and decision.next_query else EvidenceRoute.ABSTAIN
    if decision.admission in {Admission.NOT_APPLIES, Admission.ALREADY_MODELED}:
        return EvidenceRoute.RETAIN
    if decision.admission == Admission.ADMIT_PATCH and decision.patch_plan is not None:
        return EvidenceRoute.PATCH
    return EvidenceRoute.ABSTAIN


def evidence_payload(decision: EvidenceDecision) -> dict[str, Any]:
    return {
        **jsonable(decision),
        "program_gate_note": (
            "SUPPORTED is recomputed from an http(s) opened-page verbatim quote; APPLIES is constrained by "
            "verbatim source-scope and prompt-case quotes; BINDABLE requires a canonical target plus an exact "
            "structured evidence-to-Patch binding whose scalar is visible in the quote. CONSISTENT remains a "
            "constrained semantic proposal, but same-target binding conflicts are deterministically forced false "
            "across cards, rounds and gaps; no gate may compensate for another."
        ),
    }
