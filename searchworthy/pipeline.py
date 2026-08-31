"""SearchWorthy controller: model, audit, probe, search, admit, Patch, re-solve.

The LLM proposes structured modeling/gap/evidence objects.  Program-owned
contracts, solver results, retrieval traces, hard gates, and state transitions
decide whether those proposals can affect the current OR model.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import (
    Admission,
    AuditDimension,
    CandidateGapDraft,
    DecisionCompleteORState,
    EvidenceDecision,
    EvidenceRoute,
    FactCoverageRow,
    FactUsageStatus,
    GapRoute,
    GapState,
    InitialDecision,
    ModelingGapRow,
    PublicCase,
    REGISTERED_APPLICABILITY_TARGETS,
    RetrievalTrace,
    StateUpdate,
    TargetBindingStatus,
    jsonable,
    parse_evidence_decision,
    parse_initial_decision,
)
from .evidence import assess_evidence, authorize_search, evidence_payload, route_evidence, search_round
from .or_model import (
    IRValidationError,
    SolverError,
    ValidatedIR,
    apply_patch_and_solve,
    compact_binary_upper_bound_constraints,
    compare_solves,
    probe_all_gaps,
    solve_initial,
    target_value,
)
from .patch import PatchValidationError, expand_patch_plan
from .state import apply_state_update, audit_complete, digest_json, is_decision_complete, render_state_table, select_next_gap


INFORMATION_AUDIT_FAILURE_CODE = "STAGE3_CANDIDATE_GAP_LINK_FAILURE"
FACT_COVERAGE_AUDIT_FAILURE_CODE = "STAGE2_FACT_COVERAGE_INCOMPLETE"
PROGRAM_FACT_COVERAGE_CLOSURE_MARKER = "PROGRAM_UNCOVERED_PROMPT_FACT_UNIT"
PROGRAM_FACT_COVERAGE_CLOSURE_REASON = (
    f"{PROGRAM_FACT_COVERAGE_CLOSURE_MARKER}: Stage2 omitted this enumerated fact unit"
)
PROGRAM_FACT_COVERAGE_AUDIT_REASON = (
    f"{PROGRAM_FACT_COVERAGE_CLOSURE_MARKER}: Stage2 coverage is incomplete; "
    "program fallback rows are diagnostic only"
)
PROGRAM_EXACT_FACT_QUOTE_RESTORED_MARKER = "PROGRAM_RESTORED_EXACT_FACT_QUOTE"
PROGRAM_DECISION_CRITICAL_TARGET_MARKER = "PROGRAM_DECISION_CRITICAL_TARGET"
SEARCH_QUERY_BUDGET = 3


class SearchBudgetOverrun(RuntimeError):
    def __init__(self, *, prior_budget: int, remaining_budget: int, actual_consumed: int):
        self.prior_budget = prior_budget
        self.remaining_budget = remaining_budget
        self.actual_consumed = actual_consumed
        super().__init__(
            "search query budget overrun: "
            f"prior={prior_budget}, remaining={remaining_budget}, actual={actual_consumed}"
        )


INITIAL_SYSTEM = """You are the Initial Modeling stage of SearchWorthy. Use only public prompt_zh. Return exactly one JSON object and no Markdown, following the InitialDecision schema below.

Build one linear canonical OR model_ir with:
{"variables":[{"id":"public action_id","type":"BINARY|INTEGER|CONTINUOUS","lb":0,"ub":1}],"constraints":[{"name":"unique","terms":[{"var":"action_id","coef":1}],"sense":"<=|==|>=","rhs":1}],"objective":{"direction":"min|max","terms":[{"var":"action_id","coef":1}],"constant":0,"unit":"accepted public unit"},"parameters":{}}

In the SAME call perform both audits:
1) Prompt Fact -> Model Use: fact_coverage rows use exact prompt quotes and usage_status MODELED/APPLICABILITY_USED/DERIVED/UNACCOUNTED. Never output IRRELEVANT_JUSTIFIED. Before the public output_schema, cover every non-title fact/optimization unit separated by Chinese periods, semicolons, or line breaks with one sufficiently long verbatim FactCoverage quote, or with several distinct verbatim quotes whose exact non-overlapping spans collectively cover almost all of that unit; do not omit a sentence or clause.
2) Model Interface -> Information Grounding: check exactly all nine dimensions SUBJECT_ELIGIBILITY, LOCATION_JURISDICTION, TIME_VERSION, OBJECT_SCOPE, UNIT_THRESHOLD, CAPACITY_FEASIBILITY, EXCEPTION_EXEMPTION, ACTION_CONSEQUENCE, COST_BENEFIT.

Keep local case attributes separate from external operative rules. A header such as `本 case 权威事实` means the stated date, location, license, certificate, category, capacity, cost and benefit facts are true; it does not mean an unstated law, regulation, policy or technical eligibility rule is automatically satisfied. Likewise, a local optimization instruction such as choose k actions defines the requested decision/capacity, not whether every action is legally or operationally eligible in reality. Choose-k, capacity, cost and benefit facts are ordinary OR inputs and are not search triggers by themselves. A local objective gain, loss, score or cost maps to COST_BENEFIT and its canonical objective target only; it is never ACTION_CONSEQUENCE unless the same quote states a real-world permission, prohibition, duty, liability or other operative result of taking the action. A license/certificate/category record is only an attribute, not an eligibility conclusion. Close an applicability dimension only when prompt_zh explicitly states the operative rule that maps those attributes to the action's eligibility/consequence, or explicitly gives the authoritative eligibility conclusion for that action. For example, `the firm has a license and item X has a certificate` does not entail `item X is eligible`; an explicit `licensed firms may register certified category X` or `item X is eligible` can close it. If the attribute also has an ordinary model use, keep that use in a MODELED row and add a separate UNACCOUNTED row quoting the same prompt unit for the missing reality mapping; then create an EXTERNAL_RULE gap for a decision-critical existing binary action, return its one disable counterfactual, and set self_contained_candidate=false. Do not relabel an already modeled cost, benefit, capacity or choose-k fact as UNACCOUNTED merely because a separate reality mapping is missing.

Each candidate gap must connect exact prompt fact_quotes -> reality_role -> gap_claim -> target -> gap_route. target is variable.*, parameter.*, constraint.* or objective.*. gap_route is EXTERNAL_RULE, LOCAL_FACT or OUT_OF_SCOPE. Include at most 3 gaps. V0 deliberately admits only one program-verifiable Impact Probe family: for uncertainty about one public action's eligibility, exclusion or scope, target that existing BINARY variable.<action_id> and return exactly one disable counterfactual: {"target":"variable.<same action_id>","operation":"SET","value":{"lb":0,"ub":0},"range_basis":"MODEL_BOUNDARY","basis_quote":null}. Compare the Base [0,1] action with disabled [0,0]. Eligibility=true only preserves [0,1]; it never forces selection, so never emit an lb=ub=1 probe. This variant tests whether losing the action changes feasibility, decision or value; it is never a fact or Patch. Do not invent PROMPT or PREREGISTERED_RULE ranges, objective values, eligible_action_ids objects, synthetic constraints, or mandatory-selection probes. For parameter.*, constraint.* or objective.* gaps, use hypothetical_variants=[]; V0 will fail closed rather than authorize search without a program-bound range. Prioritize at most three decision-critical action variables. If more than 3 material gaps exist, return only the top 3 and set overflow_detected=true with the omitted count; otherwise overflow_detected=false and overflow_count=0. Only EXTERNAL_RULE gets a first_query.

Use these exact nested contracts; do not rename fields or replace a boolean with an object:
- fact_coverage is a non-empty array of exactly {"quote":"verbatim prompt quote","or_role":"OR role","mapped_targets":["existing variable.*, constraint.*, objective.* or applicability.* target"],"usage_status":"MODELED|APPLICABILITY_USED|DERIVED|UNACCOUNTED","reason":"why"}.
- FactCoverage status-target matrix is strict: MODELED and DERIVED may map only to existing variable.*, constraint.* or objective.* canonical IR targets, never parameter.* or applicability.*. APPLICABILITY_USED requires at least one of exactly applicability.subject_eligibility, applicability.location_jurisdiction, applicability.time_version, applicability.object_scope, applicability.unit_threshold, applicability.capacity_feasibility, applicability.exception_exemption, applicability.action_consequence or applicability.cost_benefit; it may also include existing canonical IR targets when one fact has both applicability and model use, so choose APPLICABILITY_USED for every mixed row. Never invent another applicability suffix. An uncertain, unknown, pending-verification or question-form quote cannot close any applicability dimension. For subject_eligibility, object_scope, exception_exemption and action_consequence, the same quote must independently state that target's operative mapping or direct authoritative conclusion; attributes or generic feasibility alone do not qualify. A non-exhaustive quote about action A may map only the variable.* interface for A, identifiable from its public output_schema meaning; never map an A-only quote to A and B. Map several action interfaces from one quote only when it explicitly states a universal conclusion for all candidate actions. UNACCOUNTED uses mapped_targets=[] and must link to a Candidate Gap with the same quote unless it represents an omitted gap counted by overflow_count. Every returned Candidate Gap must still link to at least one UNACCOUNTED row.
- FactCoverage covers only the auditable prompt prefix before the independent `公开 output_schema：` heading; standalone output-instruction units such as `请按output_schema...` are excluded without truncating earlier or later fact units. Never create FactCoverage or Candidate Gap rows for output instructions, action-schema JSON, accepted_units JSON or schema_version; use those only to construct and return the public-ID model_ir.
- Canonical objective targets are mechanically `objective.<term.var>` for variables actually present in model_ir.objective.terms, plus `objective.constant`. There is no aggregate objective ID. For a whole-objective fact, list every relevant `objective.<same public action_id>` term target; never invent umbrella names such as objective.listing_value, objective.total_value, objective.score or objective.value.
- audit_summary is exactly {"prompt_fact_to_model_complete":true|false,"model_interface_to_grounding_complete":true|false,"negative_space_checked":{"SUBJECT_ELIGIBILITY":true|false,"LOCATION_JURISDICTION":true|false,"TIME_VERSION":true|false,"OBJECT_SCOPE":true|false,"UNIT_THRESHOLD":true|false,"CAPACITY_FEASIBILITY":true|false,"EXCEPTION_EXEMPTION":true|false,"ACTION_CONSEQUENCE":true|false,"COST_BENEFIT":true|false},"overflow_detected":true|false,"overflow_count":0,"self_contained_reason":"reason or null"}.
- candidate_gaps is an array of exactly {"fact_quotes":["verbatim prompt quote"],"reality_role":"role","gap_claim":"missing reality knowledge","target":"variable.<public action_id>","gap_route":"EXTERNAL_RULE|LOCAL_FACT|OUT_OF_SCOPE","hypothetical_variants":[{"target":"variable.<same public action_id>","operation":"SET","value":{"lb":0,"ub":0},"range_basis":"MODEL_BOUNDARY","basis_quote":null}],"first_query":"query or null"}. Every gap must link to at least one UNACCOUNTED fact_coverage row with the same quote. If target is not a probeable binary variable, keep the same seven keys but set hypothetical_variants=[] instead.
- self_contained_candidate is a JSON boolean, never a candidate solution object. It may be true only when candidate_gaps is empty, all prompt facts and all nine dimensions are fully grounded, overflow is false, and the public model is solvable as written; otherwise false. A non-empty public `随题规则材料` block is authoritative in-prompt rule material, but every rule sentence must still be covered and bound into canonical model/applicability targets. When prompt_zh instead declares a dated `本 case 权威事实` reality interface without that rule block, a true self_contained_candidate additionally requires quote-grounded APPLICABILITY_USED witnesses for each of subject_eligibility, object_scope, exception_exemption and action_consequence; across those witnesses every existing model_ir variable.* decision interface must also be mapped. A negative_space_checked boolean is not itself a grounding witness.

Top-level keys are exactly: model_ir, fact_coverage, audit_summary, candidate_gaps, self_contained_candidate. No solver results, selected actions, objective value, closure decisions, private data, Gold, source task or benchmark roles."""


MODEL_IR_SYSTEM = """You are SearchWorthy stage 1/3: canonical OR modeling. Use only public prompt_zh and return exactly one JSON object with the single top-level key model_ir. No Markdown, audit, gap, solution or explanation.

model_ir is exactly {"variables":[{"id":"public action_id","type":"BINARY|INTEGER|CONTINUOUS","lb":0,"ub":1}],"constraints":[{"name":"unique","terms":[{"var":"action_id","coef":1}],"sense":"<=|==|>=","rhs":1}],"objective":{"direction":"min|max","terms":[{"var":"action_id","coef":1}],"constant":0,"unit":"accepted public unit"},"parameters":{}}.

Use every public output_schema action_id exactly once. Encode only the stated optimization skeleton and stated local case facts. Do not invent external legal, policy, eligibility or technical rules. Do not solve the model.

Keep the linear IR exact but non-redundant. For repeated `any k selected binary actions have weighted sum at most B` rules, omit tautologies and dominated supersets. Encode only inclusion-minimal violating action sets as no-goods `sum(x_i for i in S) <= |S|-1`, plus any independent balance constraint. Do not enumerate a constraint that cannot cut off any assignment."""


FACT_COVERAGE_SYSTEM = """You are SearchWorthy stage 2/3: Prompt Fact -> Model Use audit. The user supplies public_prompt_zh, program-enumerated auditable_fact_units and the canonical model_ir from stage 1. Return exactly one JSON object with the single top-level key fact_coverage and no Markdown.

fact_coverage is a non-empty array. Every row has exactly {"quote":"verbatim prompt quote","or_role":"short OR role","mapped_targets":["canonical target"],"usage_status":"MODELED|APPLICABILITY_USED|DERIVED|UNACCOUNTED","reason":"concise reason"}.

Cover exactly the supplied auditable_fact_units. Use sufficiently long exact prompt quotes; several distinct exact quotes may cover one unit. Do not add ledger/database provenance-only sentences that the program omitted. Never cover output instructions, action-schema JSON, accepted_units JSON or schema_version. A residual closure such as `no other assets` belongs to the same canonical balance constraint as the stated exact total; it is not a new variable or a knowledge gap.

MODELED and DERIVED map only to existing variable.*, constraint.* or objective.* targets, never parameter.* or applicability.*. APPLICABILITY_USED requires at least one of exactly applicability.subject_eligibility, applicability.location_jurisdiction, applicability.time_version, applicability.object_scope, applicability.unit_threshold, applicability.capacity_feasibility, applicability.exception_exemption, applicability.action_consequence or applicability.cost_benefit; mixed model/applicability rows must use APPLICABILITY_USED. UNACCOUNTED has mapped_targets=[]. Canonical objective targets are objective.<term.var> and objective.constant only. A quote about one action may map only that action unless it explicitly states a universal conclusion.

Keep stated local attributes/capacity/cost/benefit model uses separate from any missing external operative mapping. An attribute, certificate or license is not itself an eligibility conclusion. An uncertain or question-form quote cannot close an applicability dimension. When a non-empty `随题规则材料` block explicitly supplies an operative rule, bind the rule quote and its matching case-attribute quote to the same applicability target; this is an in-prompt compositional witness, not an external-search gap. Do not return gaps in this stage."""


GAP_AUDIT_SYSTEM = """You are SearchWorthy stage 3/3: Model Interface -> Information Grounding audit. The user supplies public_prompt_zh, canonical model_ir, validated fact_coverage, action_target_catalog and required_probe_targets. Return exactly one JSON object and no Markdown. Top-level keys are exactly audit_summary, candidate_gaps, self_contained_candidate.

Audit exactly SUBJECT_ELIGIBILITY, LOCATION_JURISDICTION, TIME_VERSION, OBJECT_SCOPE, UNIT_THRESHOLD, CAPACITY_FEASIBILITY, EXCEPTION_EXEMPTION, ACTION_CONSEQUENCE and COST_BENEFIT. A checked boolean records that a dimension was examined, not that it was grounded. Close subject/object/exception/action-consequence only with an explicit operative rule mapping the case attributes to the action or an explicit authoritative conclusion. Local choose-k, capacity, score, cost and benefit facts are ordinary OR inputs, not search triggers. A local objective value maps to COST_BENEFIT, never ACTION_CONSEQUENCE unless it also states a permission, prohibition, duty, liability or other operative result.

audit_summary is exactly {"prompt_fact_to_model_complete":true|false,"model_interface_to_grounding_complete":true|false,"negative_space_checked":{"SUBJECT_ELIGIBILITY":true|false,"LOCATION_JURISDICTION":true|false,"TIME_VERSION":true|false,"OBJECT_SCOPE":true|false,"UNIT_THRESHOLD":true|false,"CAPACITY_FEASIBILITY":true|false,"EXCEPTION_EXEMPTION":true|false,"ACTION_CONSEQUENCE":true|false,"COST_BENEFIT":true|false},"overflow_detected":true|false,"overflow_count":0,"self_contained_reason":"reason or null"}.

Return at most three decision-critical gaps. Every UNACCOUNTED fact_coverage row must link to a returned gap with the same quote, unless it is counted by overflow_count. Copy every fact_quotes string exactly and completely from fact_coverage; never shorten, translate or paraphrase it. The user payload provides allowed_gap_targets, allowed_information_targets and action_target_catalog. The catalog is a public, program-generated OR interface: each row gives one existing BINARY variable, its public action meaning, Base bounds, objective coefficient/direction and constraint memberships.

required_probe_targets is program-computed from the exact Base optimum, never from Gold. When it is non-empty and the missing external rule can affect those actions, candidate_gaps must include its targets in the supplied order before any action whose disable_probe_priority is NO_BASE_EFFECT or UNKNOWN. Never reverse this ordering for a minimization objective: use required_probe_targets directly. This is the OR-specific search boundary—search a missing rule only through an action whose removal can change the current optimal decision.

Route and bind in this order:
1) First test the missing knowledge against every action_target_catalog row. When an unstated public operative rule, current standard, eligibility rule, scope rule, exception or action consequence could permit, prohibit, disqualify or exclude a listed action, this is not OUT_OF_SCOPE: emit an action-specific EXTERNAL_RULE gap targeting that exact variable.*, with one public first_query and hypothetical_variants=[]. The program materializes the one exact disable Impact Probe {"target":"variable.<same action_id>","operation":"SET","value":{"lb":0,"ub":0},"range_basis":"MODEL_BOUNDARY","basis_quote":null} from the canonical binary Base bounds; the LLM must not invent it. Never force selection. The missing external rule itself is the reason to search, not a reason to fail closed before search.
2) Every variable.* gap must contain at least one exact fact_quote that explicitly names that catalog action (its full public meaning, exact action_id or unique labeled action identifier), or one quote that explicitly applies to all candidate actions. Context-only quotes, gap_claim and first_query cannot substitute for this target binding. If the same external rule could affect several listed actions, emit separate action-specific gaps for up to three actions with the greatest visible decision leverage from the catalog; a true all-actions quote may support each, while an action-specific quote may bind only its matching catalog action: do not fan it out to other actions. Count further affected actions in overflow_count. Overflow keeps the final decision incomplete and forces ABSTAIN, but the runtime may still probe and search the returned top-three gaps as bounded exploration. Do not solve or claim that the catalog ranking proves impact; the program will run the Impact Probes.
3) Use LOCAL_FACT only when the prompt explicitly says the missing value resides in a local record that was not supplied; it has no query and no probe unless another admitted V0 contract explicitly supports one.
4) Use an exact applicability.* allowed_information_targets entry with OUT_OF_SCOPE, hypothetical_variants=[] and first_query=null only after checking the complete action_target_catalog and determining that the missing knowledge cannot change the availability, bounds, objective or constraints of any existing OR action. applicability.* is an information-audit target, never an executable OR/Patch target. Do not choose applicability.* merely because one external rule applies to several actions.

Every executable gap target must be exactly one allowed_gap_targets entry. Every gap has exactly {"fact_quotes":["verbatim quote from an UNACCOUNTED fact_coverage row"],"reality_role":"role","gap_claim":"missing reality knowledge","target":"canonical or audit-only target","gap_route":"EXTERNAL_RULE|LOCAL_FACT|OUT_OF_SCOPE","hypothetical_variants":[],"first_query":"query or null"}. Only EXTERNAL_RULE has a query. All non-probeable targets use hypothetical_variants=[]. If more than three material gaps exist, return the top three and report the omitted count in overflow_count.

self_contained_candidate is a boolean and may be true only when candidate_gaps is empty, fact/model and interface/grounding audits are complete, overflow is false, and the public model is solvable as written. A dated local authority header does not supply an unstated operative rule. Do not solve or use private/Gold data."""


EVIDENCE_SYSTEM = """You are the second and final LLM schema of SearchWorthy. You receive one authorized active gap, its solver Impact Probe, canonical target value, public prompt_zh, and newly opened public page bodies. Return exactly one EvidenceDecision JSON object and no Markdown.

Top-level keys: evidence_cards, admission, patch_plan, next_query, reason.
Each EvidenceCard has exactly: evidence_id, url, quote, claim, case_quote, scope_quote, target, supported, applies, bindable, consistent, binding_path, binding_value. quote and scope_quote must be verbatim from one supplied page body; case_quote must be verbatim from prompt_zh. Titles/snippets are not evidence. target must equal the active gap target. binding_path/binding_value are both null when the card does not bind a value. Otherwise use target_value, parameters.coefficient, parameters.lb, parameters.ub, parameters.constraint.rhs, parameters.constraint.sense, or parameters. Every scalar binding_value must be visible in quote (for senses, use the quoted equivalent such as 不超过 for <=).

Admission is REJECT, NOT_APPLIES, ALREADY_MODELED, ADMIT_PATCH or CONFLICT. ADMIT_PATCH requires SUPPORTED && APPLIES && BINDABLE && CONSISTENT and one PatchPlan with patch_family, target, parameters, before_guard, evidence_ids. The cited cards must bind every externally determined Patch parameter exactly. before_guard must equal current_target_value. V0 executable patch_family values are only SET_VARIABLE_BOUNDS and SET_OBJECTIVE_COEFFICIENT; constraint insertion/removal must be REJECT because V0 cannot ground every term and coefficient. ALREADY_MODELED is allowed only for a scalar current_target_value and requires binding_path=target_value plus a quote-grounded binding_value exactly equal to it. V0 cannot close NOT_APPLIES without program-verifiable structured scope atoms, so use REJECT and optionally one revised query. Treat any current/prior same-target same-path value disagreement as CONFLICT. REJECT/CONFLICT may provide one revised next_query; other admissions use null. Never solve, close a gap, or use private/Gold data."""


@dataclass(frozen=True)
class PipelineServices:
    initial_modeler: Callable[[PublicCase], InitialDecision]
    searcher: Callable[[str, str], RetrievalTrace]
    evidence_proposer: Callable[
        [PublicCase, DecisionCompleteORState, str, RetrievalTrace, ValidatedIR], EvidenceDecision
    ]


def _public_case(value: PublicCase | dict[str, Any]) -> PublicCase:
    if isinstance(value, PublicCase):
        return value
    if not isinstance(value, dict):
        raise ValueError("public case must be an object")
    eval_id = value.get("eval_id", value.get("id"))
    prompt = value.get("prompt_zh")
    if not isinstance(eval_id, str) or not eval_id or not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("public case requires eval_id and prompt_zh")
    return PublicCase(eval_id, prompt)


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    # Some otherwise complete provider responses omit only the outermost final
    # brace.  Repair exactly that one-byte envelope defect; never complete an
    # inner object/array or an unfinished string/value.
    stack: list[str] = []
    in_string = False
    escaped = False
    structurally_valid = True
    for char in stripped:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            expected = "{" if char == "}" else "["
            if not stack or stack[-1] != expected:
                structurally_valid = False
                break
            stack.pop()
    if structurally_valid and not in_string and stack == ["{"]:
        try:
            value = json.loads(f"{stripped}}}")
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("LLM response contains no JSON object")


def _response_object(response: Any, label: str) -> dict[str, Any]:
    if isinstance(response, dict) and isinstance(response.get("content"), str):
        response = _extract_json(response["content"])
    if not isinstance(response, dict):
        raise ValueError(f"{label} response must be a JSON object")
    return response


def _normalize_unbound_gap_targets(
    audit_row: dict[str, Any],
    fact_coverage: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mark a well-formed registered information target for fail-closed materialization."""
    result = copy.deepcopy(audit_row)
    summary = result.get("audit_summary")
    gaps = result.get("candidate_gaps")
    if (
        result.get("self_contained_candidate") is not False
        or not isinstance(summary, dict)
        or not isinstance(gaps, list)
    ):
        return result
    exact_unaccounted_quotes = {
        row["quote"]
        for row in fact_coverage
        if isinstance(row, dict)
        and row.get("usage_status") == FactUsageStatus.UNACCOUNTED.value
        and isinstance(row.get("quote"), str)
    }
    expected_gap_keys = {
        "fact_quotes",
        "reality_role",
        "gap_claim",
        "target",
        "gap_route",
        "hypothetical_variants",
        "first_query",
    }

    def deletion_only_copy(candidate: str, observed: str) -> bool:
        candidate_text = " ".join(candidate.split())
        observed_text = " ".join(observed.split())
        if len(observed_text) < 40 or not 1 <= len(candidate_text) - len(observed_text) <= 2:
            return False
        iterator = iter(candidate_text)
        return all(any(char == source for source in iterator) for char in observed_text)

    for gap in gaps:
        if not isinstance(gap, dict) or set(gap) != expected_gap_keys:
            continue
        quotes = gap.get("fact_quotes")
        if not isinstance(quotes, list) or not quotes or any(not isinstance(quote, str) for quote in quotes):
            continue
        restored = 0
        normalized_quotes: list[str] = []
        for quote in quotes:
            if quote in exact_unaccounted_quotes:
                normalized_quotes.append(quote)
                continue
            matches = [
                candidate
                for candidate in exact_unaccounted_quotes
                if deletion_only_copy(candidate, quote)
            ]
            if len(matches) == 1:
                normalized_quotes.append(matches[0])
                restored += 1
            else:
                normalized_quotes.append(quote)
        if restored:
            gap["fact_quotes"] = normalized_quotes
            claim = gap.get("gap_claim")
            if isinstance(claim, str) and claim.strip():
                gap["gap_claim"] = (
                    f"{claim.strip()} [{PROGRAM_EXACT_FACT_QUOTE_RESTORED_MARKER}:{restored}]"
                )
    if summary.get("model_interface_to_grounding_complete") is True:
        summary_keys = {
            "prompt_fact_to_model_complete",
            "model_interface_to_grounding_complete",
            "negative_space_checked",
            "overflow_detected",
            "overflow_count",
            "self_contained_reason",
        }
        gap_keys = {
            "fact_quotes",
            "reality_role",
            "gap_claim",
            "target",
            "gap_route",
            "hypothetical_variants",
            "first_query",
        }
        negative_space = summary.get("negative_space_checked")
        pure_audit_only_gaps = 1 <= len(gaps) <= 3 and all(
            isinstance(gap, dict)
            and set(gap) == gap_keys
            and gap.get("target") in REGISTERED_APPLICABILITY_TARGETS
            and gap.get("gap_route") == GapRoute.OUT_OF_SCOPE.value
            and gap.get("hypothetical_variants") == []
            and gap.get("first_query") is None
            and isinstance(gap.get("fact_quotes"), list)
            and bool(gap["fact_quotes"])
            and all(
                isinstance(quote, str) and bool(quote.strip()) and quote == quote.strip()
                for quote in gap["fact_quotes"]
            )
            and all(
                isinstance(gap.get(key), str) and bool(gap[key].strip())
                for key in ("reality_role", "gap_claim")
            )
            for gap in gaps
        )
        has_exact_unaccounted_anchor = pure_audit_only_gaps and any(
            quote in exact_unaccounted_quotes
            for gap in gaps
            for quote in gap["fact_quotes"]
        )
        pure_audit_only_contradiction = (
            set(summary) == summary_keys
            and summary.get("prompt_fact_to_model_complete") is False
            and isinstance(negative_space, dict)
            and set(negative_space) == {dimension.value for dimension in AuditDimension}
            and all(type(value) is bool for value in negative_space.values())
            and summary.get("overflow_detected") is False
            and type(summary.get("overflow_count")) is int
            and summary["overflow_count"] == 0
            and isinstance(summary.get("self_contained_reason"), str)
            and bool(summary["self_contained_reason"].strip())
            and has_exact_unaccounted_anchor
        )
        if not pure_audit_only_contradiction:
            return result
        summary["model_interface_to_grounding_complete"] = False
        summary_marker = "[PROGRAM_DOWNGRADED_AUDIT_ONLY_GROUNDING_CONTRADICTION]"
        reason = summary["self_contained_reason"].strip()
        summary["self_contained_reason"] = (
            reason if summary_marker in reason else f"{reason} {summary_marker}"
        )
    elif summary.get("model_interface_to_grounding_complete") is not False:
        return result
    unaccounted_quotes = {
        " ".join(row["quote"].split())
        for row in fact_coverage
        if isinstance(row, dict)
        and row.get("usage_status") == FactUsageStatus.UNACCOUNTED.value
        and isinstance(row.get("quote"), str)
    }
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        raw_target = gap.get("target")
        target = {
            f"applicability.{dimension.value}": f"applicability.{dimension.value.lower()}"
            for dimension in AuditDimension
        }.get(raw_target, raw_target)
        quotes = gap.get("fact_quotes")
        claim = gap.get("gap_claim")
        route = gap.get("gap_route")
        query = gap.get("first_query")
        route_query_is_valid = (
            route == GapRoute.OUT_OF_SCOPE.value and query is None
        ) or (
            route == GapRoute.LOCAL_FACT.value and query is None
        ) or (
            route == GapRoute.EXTERNAL_RULE.value
            and isinstance(query, str)
            and bool(query.strip())
        )
        non_link_contract_is_invalid = (
            target not in REGISTERED_APPLICABILITY_TARGETS
            or gap.get("hypothetical_variants") != []
            or not isinstance(claim, str)
            or not claim.strip()
            or not route_query_is_valid
            or not isinstance(quotes, list)
            or not quotes
        )
        if non_link_contract_is_invalid:
            continue
        gap["target"] = target
        if any(not isinstance(quote, str) or " ".join(quote.split()) not in unaccounted_quotes for quote in quotes):
            continue
        marker = f"[PROGRAM_UNBOUND_OR_TARGET:{target}]"
        gap["gap_claim"] = claim.strip() if marker in claim else f"{claim.strip()} {marker}"
    return result


def _normalize_decision_critical_gap_targets(
    audit_row: dict[str, Any],
    fact_coverage: list[dict[str, Any]],
    required_probe_targets: list[str],
    prompt_zh: str,
) -> dict[str, Any]:
    """Bind an already-detected universal external gap to Base-critical OR actions."""
    result = copy.deepcopy(audit_row)
    gaps = result.get("candidate_gaps")
    if not required_probe_targets or not isinstance(gaps, list):
        return result
    unaccounted_quotes = {
        row["quote"]
        for row in fact_coverage
        if isinstance(row, dict)
        and row.get("usage_status") == FactUsageStatus.UNACCOUNTED.value
        and isinstance(row.get("quote"), str)
    }
    action_meanings = _public_action_meanings(prompt_zh)
    if not action_meanings:
        return result
    expected_gap_keys = {
        "fact_quotes",
        "reality_role",
        "gap_claim",
        "target",
        "gap_route",
        "hypothetical_variants",
        "first_query",
    }
    dates = list(dict.fromkeys(re.findall(r"20\d{2}年\d{1,2}月\d{1,2}日", prompt_zh)))[:3]
    required_set = set(required_probe_targets)
    for required_target in required_probe_targets:
        if any(isinstance(gap, dict) and gap.get("target") == required_target for gap in gaps):
            continue
        replacement: tuple[dict[str, Any], list[str]] | None = None
        for gap in gaps:
            if (
                not isinstance(gap, dict)
                or set(gap) != expected_gap_keys
                or gap.get("target") in required_set
                or not str(gap.get("target") or "").startswith("variable.")
                or gap.get("gap_route") != GapRoute.EXTERNAL_RULE.value
                or gap.get("hypothetical_variants") != []
                or not isinstance(gap.get("first_query"), str)
                or not gap["first_query"].strip()
                or not isinstance(gap.get("fact_quotes"), list)
            ):
                continue
            binding_quotes = [
                quote
                for quote in gap["fact_quotes"]
                if isinstance(quote, str)
                and quote in unaccounted_quotes
                and _quote_binds_variable_target(quote, required_target, action_meanings)
            ]
            if binding_quotes:
                replacement = (gap, binding_quotes[:3])
                break
        if replacement is None:
            continue
        gap, binding_quotes = replacement
        original_target = str(gap["target"])
        restored_quote_record = re.search(
            rf"\[{PROGRAM_EXACT_FACT_QUOTE_RESTORED_MARKER}:\d+\]",
            str(gap.get("gap_claim") or ""),
        )
        action_id = required_target.split(".", 1)[1]
        meaning = action_meanings.get(action_id, action_id)
        gap["target"] = required_target
        gap["fact_quotes"] = binding_quotes
        gap["reality_role"] = "decision-critical external applicability"
        gap["gap_claim"] = (
            f"外部操作性规则尚未闭合到当前 Base 最优解中的决策关键行动：{meaning}。 "
            f"[{PROGRAM_DECISION_CRITICAL_TARGET_MARKER}:{original_target}->{required_target}]"
            f"{' ' + restored_quote_record.group(0) if restored_quote_record else ''}"
        )
        query_parts = ["官方规则", *dates, meaning, "资格 适用范围 例外 豁免 许可 禁止 行动后果"]
        gap["first_query"] = " ".join(part for part in query_parts if part)
    return result


def initial_modeling(public: PublicCase, llm_call: Callable[[list[dict[str, str]], str], Any]) -> InitialDecision:
    model_response = llm_call(
        [
            {"role": "system", "content": MODEL_IR_SYSTEM},
            {"role": "user", "content": public.prompt_zh},
        ],
        "searchworthy_initial_model_ir",
    )
    if isinstance(model_response, InitialDecision):
        return model_response
    model_row = _response_object(model_response, "model_ir stage")
    if set(model_row) != {"model_ir"} or not isinstance(model_row["model_ir"], dict):
        raise ValueError("model_ir stage must return exactly one model_ir object")
    if set(model_row["model_ir"]) != {"variables", "constraints", "objective", "parameters"} or model_row["model_ir"].get("parameters") != {}:
        raise ValueError("SearchWorthy V0 model_ir must use exactly variables/constraints/objective and parameters={}")
    model_row = {"model_ir": compact_binary_upper_bound_constraints(model_row["model_ir"])}

    coverage_payload = {
        "public_prompt_zh": public.prompt_zh,
        "auditable_fact_units": prompt_fact_units(public.prompt_zh),
        "model_ir": model_row["model_ir"],
    }
    coverage_response = llm_call(
        [
            {"role": "system", "content": FACT_COVERAGE_SYSTEM},
            {"role": "user", "content": json.dumps(coverage_payload, ensure_ascii=False, separators=(",", ":"))},
        ],
        "searchworthy_fact_coverage",
    )
    coverage_row = _response_object(coverage_response, "fact_coverage stage")
    if set(coverage_row) != {"fact_coverage"} or not isinstance(coverage_row["fact_coverage"], list):
        raise ValueError("fact_coverage stage must return exactly one fact_coverage array")
    coverage_row = {
        "fact_coverage": _close_stage_fact_coverage(
            public.prompt_zh,
            _normalize_stage_fact_coverage(
                public.prompt_zh,
                model_row["model_ir"],
                coverage_row["fact_coverage"],
            ),
        )
    }
    if any(
        row.get("or_role") == PROGRAM_FACT_COVERAGE_CLOSURE_MARKER
        and row.get("reason") == PROGRAM_FACT_COVERAGE_CLOSURE_REASON
        for row in coverage_row["fact_coverage"]
    ):
        audit_row = {
            "audit_summary": {
                "prompt_fact_to_model_complete": False,
                "model_interface_to_grounding_complete": False,
                "negative_space_checked": {dimension.value: False for dimension in AuditDimension},
                "overflow_detected": False,
                "overflow_count": 0,
                "self_contained_reason": PROGRAM_FACT_COVERAGE_AUDIT_REASON,
            },
            "candidate_gaps": [],
            "self_contained_candidate": False,
        }
        return parse_initial_decision({**model_row, **coverage_row, **audit_row})

    action_target_catalog = _action_target_catalog(public.prompt_zh, model_row["model_ir"])
    required_probe_targets = [
        row["target"]
        for row in action_target_catalog
        if row["disable_probe_priority"] == "DECISION_CRITICAL"
    ][:3]
    audit_payload = {
        **coverage_payload,
        "fact_coverage": coverage_row["fact_coverage"],
        "allowed_gap_targets": sorted(_existing_targets(model_row["model_ir"])),
        "allowed_information_targets": sorted(REGISTERED_APPLICABILITY_TARGETS),
        "action_target_catalog": action_target_catalog,
        "required_probe_targets": required_probe_targets,
    }
    audit_response = llm_call(
        [
            {"role": "system", "content": GAP_AUDIT_SYSTEM},
            {"role": "user", "content": json.dumps(audit_payload, ensure_ascii=False, separators=(",", ":"))},
        ],
        "searchworthy_gap_audit",
    )
    audit_row = _response_object(audit_response, "gap_audit stage")
    expected_audit_keys = {"audit_summary", "candidate_gaps", "self_contained_candidate"}
    if set(audit_row) != expected_audit_keys:
        raise ValueError("gap_audit stage returned the wrong top-level keys")
    raw_candidate_gaps = audit_row.get("candidate_gaps")
    if not isinstance(raw_candidate_gaps, list) or any(
        not isinstance(gap, dict) or gap.get("hypothetical_variants") != []
        for gap in raw_candidate_gaps
    ):
        raise ValueError("gap_audit stage must leave hypothetical_variants=[] for program-owned Impact Probes")
    if any(
        marker in str(gap.get("gap_claim") or "")
        for gap in raw_candidate_gaps
        for marker in (PROGRAM_EXACT_FACT_QUOTE_RESTORED_MARKER, PROGRAM_DECISION_CRITICAL_TARGET_MARKER)
    ):
        raise ValueError("gap_audit stage cannot supply a program-owned normalization marker")
    audit_row = _normalize_unbound_gap_targets(audit_row, coverage_row["fact_coverage"])
    audit_row = _normalize_decision_critical_gap_targets(
        audit_row,
        coverage_row["fact_coverage"],
        required_probe_targets,
        public.prompt_zh,
    )
    initial = parse_initial_decision({**model_row, **coverage_row, **audit_row})
    allowed_gap_targets = set(audit_payload["allowed_gap_targets"])
    if any(
        gap.target not in REGISTERED_APPLICABILITY_TARGETS
        and gap.target not in allowed_gap_targets
        for gap in initial.candidate_gaps
    ):
        raise ValueError("candidate gap target is absent from allowed_gap_targets")
    return initial


def propose_evidence(
    public: PublicCase,
    state: DecisionCompleteORState,
    gap_id: str,
    trace: RetrievalTrace,
    current_ir: ValidatedIR,
    llm_call: Callable[[list[dict[str, str]], str], Any],
) -> EvidenceDecision:
    gap = next(row for row in state.gaps if row.gap_id == gap_id)
    payload = {
        "public_prompt_zh": public.prompt_zh,
        "active_gap": jsonable(gap),
        "current_target_value": target_value(current_ir, gap.target),
        "compact_state": render_state_table(state),
        "prior_evidence_ledger": [
            {
                key: row.get(key)
                for key in (
                    "gap_id",
                    "round",
                    "evidence_id",
                    "target",
                    "binding_path",
                    "binding_value",
                    "supported",
                    "applies",
                    "bindable",
                    "consistent",
                )
            }
            for row in state.evidence_ledger
        ],
        "remaining_search_budget": state.search_budget_left,
        "opened_pages": [
            {
                "final_url": page.get("final_url") or page.get("url"),
                "publisher": page.get("publisher"),
                "title": page.get("title"),
                "page_body": str(page.get("visible_text") or "")[:16000],
            }
            for page in trace.opened_pages
        ],
    }
    response = llm_call(
        [
            {"role": "system", "content": EVIDENCE_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
        ],
        f"searchworthy_evidence_{gap_id}_round_{state.round}",
    )
    if isinstance(response, EvidenceDecision):
        return response
    if isinstance(response, dict) and isinstance(response.get("content"), str):
        response = _extract_json(response["content"])
    return parse_evidence_decision(response)


def _quote_in_prompt(prompt: str, quote: str) -> bool:
    return " ".join(quote.split()) in " ".join(prompt.split())


def _compact_unit(value: str) -> str:
    return re.sub(r"\s+", "", value).strip("，,：:、。；;！？!?")


def _non_fact_unit(unit: str) -> bool:
    if not unit or re.fullmatch(r"【[^】]+】", unit):
        return True
    lowered = unit.lower().replace(" ", "")
    if lowered.startswith(
        (
            "请按output_schema",
            "公开output_schema",
            "请输出",
            "只输出",
            "回答格式",
        )
    ):
        return True
    return False


def _optimization_lead_is_structural_title(unit: str) -> bool:
    """Recognize a narrow nominal task title; ambiguous leads remain auditable facts."""
    statement_cues = (
        "为", "是", "有", "无", "必须", "须", "不得", "可以", "需要", "要求", "允许", "禁止",
        "包含", "要把", "均在", "属于", "不属于", "来自", "载于", "记录在", "记载在",
        "给出", "标明", "发生", "完成", "保持", "等于",
        "互斥", "至少", "至多", "最多", "最少", "恰好", "只能", "仅能", "可取", "取值",
        "优先于", "不晚于", "不早于", "上限", "下限", "预算", "总量", "约束",
        "不可", "不能", "二选一", "任选", "不同时", "不兼容", "依赖", "冲突",
    )
    predicate_verbs = ("安排", "分配", "决定", "制定", "送往")
    imperative_prefixes = (
        "选", "不选", "勿选", "仅选", "只选", "选取", "采用", "执行", "安排", "分配",
        "采购", "启用", "禁用", "排除", "关闭", "开启", "固定", "设置", "决定", "制定",
        "送往", "保持", "最大化", "最小化",
    )
    has_statement_shape = (
        bool(re.search(r"[，,:：；;、≤≥=<>]|供.+使用", unit))
        or ("用于" in unit and not unit.startswith("用于"))
        or unit.startswith(imperative_prefixes)
        or any(cue in unit for cue in statement_cues)
        or bool(re.search(r"先.+后", unit))
        or any(verb in unit and not unit.endswith(verb) for verb in predicate_verbs)
    )
    title_endings = (
        "选择", "组合", "配置", "排程", "分配", "匹配", "方案", "排班", "安排", "采购",
        "配送", "分发", "投放", "配料", "裁定", "排期", "调整", "履约", "网络", "处置",
        "计划", "决策", "规划", "路由", "处理", "拼载", "容量", "项目", "运行包", "设计", "汇入",
    )
    return bool(unit) and not has_statement_shape and unit.endswith(title_endings)


def prompt_fact_prefix(prompt_zh: str) -> str:
    """Return the only prompt region allowed to populate FactCoverage/gaps."""
    boundary = re.search(
        r"^[ \t\u3000]*公开[ \t\u3000]*output_schema[ \t\u3000]*[:：]",
        prompt_zh,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return prompt_zh[: boundary.start()] if boundary else prompt_zh


def _authoritative_rule_material(prompt_zh: str) -> str:
    match = re.search(r"【随题规则材料】(?P<body>.*?)【优化骨架】", prompt_zh, flags=re.DOTALL)
    return match.group("body").strip() if match else ""


def _has_authoritative_rule_material(prompt_zh: str) -> bool:
    return bool(_authoritative_rule_material(prompt_zh))


def _declares_reality_interface(prompt_zh: str) -> bool:
    """Identify the benchmark's explicit dated real-world decision contract."""
    if "【本 case 权威事实】" not in prompt_zh or not re.search(r"20\d{2}年\d{1,2}月\d{1,2}日", prompt_zh):
        return False
    entity_or_domain = (
        r"公司|企业|机构|中心|医院|运营商|合作社|部门|车队|航空|铁路|园区|主体|员工|患者|"
        r"申请人|进口人|设施|项目|列车|管线|设备|货物|交易|证券|保险|车辆|航班|产品|服务|"
        r"政府|海关|客户|承包|废物|包装|候选|农场|学校|大学|研究所|银行|基金|协会|实验室|"
        r"船舶|港口|工厂|团队|委员会|零售商|制造商|采购方|管理局|办公室|经营者|生产者|"
        r"航司|雇主|纳税人|开发商|平台|诊所|药房|仓库|经销商|broker|dealer"
    )
    return bool(re.search(entity_or_domain, prompt_zh, flags=re.IGNORECASE))


def _prompt_fact_unit_spans(prompt_zh: str) -> list[tuple[str, str]]:
    """Pair each compact audit unit with an exact contiguous source span."""
    prefix = prompt_fact_prefix(prompt_zh)
    spans: list[tuple[str, str]] = []
    fragment_start = 0
    fragments: list[tuple[int, str]] = []
    for delimiter in re.finditer(r"[。；;\r\n]+", prefix):
        fragments.append((fragment_start, prefix[fragment_start : delimiter.start()]))
        fragment_start = delimiter.end()
    fragments.append((fragment_start, prefix[fragment_start:]))
    skip_next_optimization_title = False
    for source_start, fragment in fragments:
        if "【优化骨架】" in fragment:
            skip_next_optimization_title = True
        without_headings = re.sub(r"【[^】]+】", "", fragment)
        unit = _compact_unit(without_headings)
        structural_title = False
        if skip_next_optimization_title and unit:
            structural_title = _optimization_lead_is_structural_title(unit)
            skip_next_optimization_title = False
        if structural_title:
            continue
        if not _non_fact_unit(unit):
            exact_candidate = without_headings.strip()
            relative_start = fragment.find(exact_candidate)
            if not exact_candidate or relative_start < 0:
                raise ValueError("auditable fact unit lacks an exact prompt span")
            exact_span = prefix[
                source_start + relative_start : source_start + relative_start + len(exact_candidate)
            ]
            if exact_span != exact_candidate:
                raise ValueError("auditable fact span provenance is inconsistent")
            spans.append((unit, exact_span))
    return spans


def prompt_fact_units(prompt_zh: str) -> list[str]:
    """Deterministically enumerate public fact/OR units before output instructions."""
    return [unit for unit, _ in _prompt_fact_unit_spans(prompt_zh)]


def _fact_unit_covered(unit: str, quotes: list[str]) -> bool:
    compact_unit = _compact_unit(unit)
    minimum = min(4, len(compact_unit))
    seen_quotes: set[str] = set()
    covered_positions: set[int] = set()
    for quote in quotes:
        compact_quote = _compact_unit(quote)
        if len(compact_quote) < minimum or compact_quote in seen_quotes:
            continue
        seen_quotes.add(compact_quote)
        if compact_unit in compact_quote:
            return True
        start = compact_unit.find(compact_quote)
        if start < 0:
            continue
        # Fragmented atomic facts may jointly cover one sentence-level unit.
        # Count each distinct exact quote once and use a span union so repeated
        # or overlapping fragments cannot inflate coverage.
        covered_positions.update(range(start, start + len(compact_quote)))
    return len(covered_positions) / max(1, len(compact_unit)) >= 0.85


def _fact_unit_fully_covered(
    unit: str,
    quotes: list[str],
    exact_span: str | None = None,
) -> bool:
    """Require source-local 100% fact text, ignoring only syntactic separators."""
    source = exact_span if exact_span is not None else unit
    compact_source = re.sub(r"\s+", "", source)
    minimum = min(4, len(compact_source))
    seen_quotes: set[str] = set()
    covered_positions: set[int] = set()
    for quote in quotes:
        # Stage2 commonly preserves the sentence delimiter even though the
        # source-local unit span ends immediately before it.
        compact_quote = re.sub(r"\s+", "", quote).strip("。；;")
        if (
            len(compact_quote) < minimum
            or compact_quote in seen_quotes
            or compact_quote not in compact_source
        ):
            continue
        seen_quotes.add(compact_quote)
        start = compact_source.find(compact_quote)
        covered_positions.update(range(start, start + len(compact_quote)))

    def ignorable_separator(index: int) -> bool:
        char = compact_source[index]
        if char in "，,、":
            return True
        if char not in "：:":
            return False
        left = compact_source[index - 1] if index > 0 else ""
        right = compact_source[index + 1] if index + 1 < len(compact_source) else ""
        return not (left.isdigit() and right.isdigit())

    return all(
        index in covered_positions or ignorable_separator(index)
        for index in range(len(compact_source))
    )


def prompt_fact_coverage(prompt_zh: str, facts: list[Any]) -> tuple[list[str], list[str], float]:
    units = prompt_fact_units(prompt_zh)
    quotes = [str(fact.quote) for fact in facts]
    uncovered = [unit for unit in units if not _fact_unit_covered(unit, quotes)]
    ratio = (len(units) - len(uncovered)) / len(units) if units else 0.0
    return units, uncovered, ratio


def _close_stage_fact_coverage(
    prompt_zh: str,
    normalized_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fail closed by making every Stage2 omission explicit before Stage3."""
    rows = copy.deepcopy(normalized_rows)
    quotes = [row["quote"] for row in rows]
    for unit, exact_span in _prompt_fact_unit_spans(prompt_zh):
        if _fact_unit_fully_covered(unit, quotes, exact_span):
            continue
        rows.append(
            {
                "quote": exact_span,
                "or_role": PROGRAM_FACT_COVERAGE_CLOSURE_MARKER,
                "mapped_targets": [],
                "usage_status": FactUsageStatus.UNACCOUNTED.value,
                "reason": PROGRAM_FACT_COVERAGE_CLOSURE_REASON,
            }
        )
        quotes.append(exact_span)
    if any(
        not _fact_unit_fully_covered(unit, quotes, exact_span)
        for unit, exact_span in _prompt_fact_unit_spans(prompt_zh)
    ):
        raise ValueError("program fact-coverage closure failed")
    return rows


def _existing_targets(model_ir: ValidatedIR) -> set[str]:
    targets = {f"variable.{row['id']}" for row in model_ir["variables"]}
    targets.update(f"constraint.{row['name']}" for row in model_ir["constraints"])
    targets.update(f"objective.{row['var']}" for row in model_ir["objective"]["terms"])
    targets.add("objective.constant")
    return targets


def _action_target_catalog(prompt_zh: str, model_ir: ValidatedIR) -> list[dict[str, Any]]:
    """Expose only public, existing binary OR interfaces to the gap auditor."""
    meanings = _public_action_meanings(prompt_zh)
    validated_ir, base_capture = solve_initial(model_ir)
    objective = validated_ir["objective"]
    objective_coefficients: dict[str, int | float] = {}
    for term in objective["terms"]:
        variable = term["var"]
        objective_coefficients[variable] = objective_coefficients.get(variable, 0) + term["coef"]

    raw_action_sets = base_capture.diagnostic.get("optimal_action_sets")
    action_sets = raw_action_sets if isinstance(raw_action_sets, list) else []
    pool_complete = bool(action_sets) and base_capture.diagnostic.get("optimal_action_sets_truncated") is False
    catalog: list[dict[str, Any]] = []
    for variable_index, variable in enumerate(validated_ir["variables"]):
        if variable["type"] != "BINARY":
            continue
        action_id = variable["id"]
        memberships = []
        for constraint in validated_ir["constraints"]:
            for term in constraint["terms"]:
                if term["var"] == action_id:
                    memberships.append(
                        {
                            "constraint": constraint["name"],
                            "coefficient": term["coef"],
                            "sense": constraint["sense"],
                            "rhs": constraint["rhs"],
                        }
                    )
        selected_values = [
            row[variable_index]
            for row in action_sets
            if isinstance(row, list) and len(row) == len(validated_ir["variables"])
        ]
        selected_in_any = any(value == 1 for value in selected_values)
        selected_in_all = bool(selected_values) and all(value == 1 for value in selected_values)
        if selected_in_any:
            disable_probe_priority = "DECISION_CRITICAL"
        elif pool_complete:
            disable_probe_priority = "NO_BASE_EFFECT"
        else:
            disable_probe_priority = "UNKNOWN"
        catalog.append(
            {
                "target": f"variable.{action_id}",
                "action_meaning": meanings.get(action_id, action_id),
                "base_bounds": {"lb": variable["lb"], "ub": variable["ub"]},
                "objective_direction": objective["direction"],
                "objective_coefficient": objective_coefficients.get(action_id, 0),
                "constraint_memberships": memberships,
                "base_selected_in_any_optimum": selected_in_any,
                "base_selected_in_all_optima": selected_in_all,
                "base_optimal_pool_complete": pool_complete,
                "disable_probe_priority": disable_probe_priority,
            }
        )
    return catalog


def _fact_model_targets(model_ir: ValidatedIR) -> set[str]:
    return _existing_targets(model_ir)


RULE_DEPENDENT_APPLICABILITY_TARGETS = {
    "applicability.subject_eligibility",
    "applicability.object_scope",
    "applicability.exception_exemption",
    "applicability.action_consequence",
}
EXHAUSTIVE_ACTION_CONCLUSION_PATTERNS = (
    r"(?:所有|全部)(?:候选)?(?:方案|行动|型号|对象|产品|批次)(?:均|都)(?:获准|允许|有资格)",
    r"(?:所有|全部)(?:候选)?(?:方案|行动|型号|对象|产品|批次)(?:均|都)(?:可|可以).{0,24}(?:申报|注册|登记|上市|进口|出口|运行|使用|进入|办理|参加|治疗|交易)",
    r"(?:all|every)\s+(?:candidate\s+)?(?:action|option|item|product|batch)s?.{0,24}(?:eligible|permitted|may\s+(?:register|file|market|use|operate|enter|participate|trade))",
)


def _is_applicability_target(target: str) -> bool:
    return target in REGISTERED_APPLICABILITY_TARGETS


def _quote_is_uncertain(quote: str) -> bool:
    text = " ".join(quote.split()).lower()
    uncertainty_patterns = (
        r"(?:是否|未知|不明确|不清楚|不确定|尚待|待核查|待核实|待确认|需核查|需核实|未确定|有待确认|也许)",
        r"(?<!不)可能(?:会|存在|适用|允许|可以|豁免|符合|属于|成为|要求|需要|导致|触发|参与|进入|申报|注册|使用|运行|有|无)",
        r"(?:unknown|unclear|uncertain|whether|to be determined|needs? verification|pending confirmation|may or may not)",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in uncertainty_patterns)


def _provenance_only_applicability_targets(quote: str) -> set[str]:
    """Identify narrow ledger/provenance statements that repeat a known case attribute."""
    if _quote_is_uncertain(quote):
        return set()
    text = " ".join(quote.split()).lower()
    provenance = re.search(
        r"(?:记录|记载|列示|保存).{0,24}(?:台账|名册|数据库|档案|ledger|register|database|record)|"
        r"(?:台账|名册|数据库|档案|ledger|register|database|record).{0,24}(?:记录|记载|列示|给出|保存|shows?|lists?|records?)",
        text,
        flags=re.IGNORECASE,
    )
    if provenance is None:
        return set()
    targets: set[str] = set()
    if re.search(r"(?:合同.{0,12}(?:类型|类别|性质)|(?:养老金|年金).{0,12}合同)", text):
        targets.add("applicability.subject_eligibility")
    if re.search(r"(?:发行人|底层资产|资产.{0,8}(?:类型|类别|归属)|投资.{0,8}(?:类型|类别|归属))", text):
        targets.add("applicability.object_scope")
    return targets


def _quote_asserts_case_attribute(quote: str, target: str) -> bool:
    """Require a concrete, non-provenance case-side value before closing duplicate provenance."""
    if _quote_is_uncertain(quote) or _provenance_only_applicability_targets(quote):
        return False
    text = " ".join(quote.split()).lower()
    patterns = {
        "applicability.subject_eligibility": (
            r"(?:账户|公司|企业|主体|机构|account|company).{0,72}(?:支持|面向|用于|对应|属于|supports?|for).{0,36}(?:非养老金|养老金|可变年金|年金|合同|non[- ]?pension|annuity|contract)",
            r"(?:合同|contract).{0,20}(?:为|是|属于|不属于|类型为|类别为|is|are).{0,28}(?:非养老金|养老金|可变年金|年金|non[- ]?pension|annuity)",
        ),
        "applicability.object_scope": (
            r"(?:债券|资产|投资|发行人|基金|合伙企业|bond|asset|investment|issuer|fund|partnership).{0,112}(?:互不关联|不同发行人|直接发行|不含|不包括|不属于|底层资产|unrelated|distinct issuers?|directly issued|does not include|excludes?)",
        ),
    }
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns.get(target, ()))


def _quote_is_plain_objective_effect(quote: str) -> bool:
    """Separate local objective values from real-world operative consequences."""
    text = " ".join(quote.split()).lower()
    objective_value = re.search(
        r"(?:收益|效用|得分|评分|目标值|价值|利润|成本|损失|增加|减少|加分|扣分|"
        r"\d+(?:\.\d+)?\s*(?:点|分|元)|benefit|utility|score|value|profit|cost|loss|points?)",
        text,
        flags=re.IGNORECASE,
    )
    if not objective_value:
        return False
    operative = re.search(
        r"(?:必须|须|不得|禁止|允许|获准|义务|责任|处罚|罚款|期限|合规要求|豁免|免于|"
        r"申报|注册|登记|上市|进口|出口|运行|使用|进入|办理|治疗|交易|交收|缴款|缴纳|"
        r"报销|释放|销售|处置|采用|执行|must|shall|required|prohibited|permitted|liability|"
        r"penalty|deadline|register|file|market|operate|enter|trade)",
        text,
        flags=re.IGNORECASE,
    )
    return operative is None


def _quote_has_exhaustive_action_conclusion(quote: str) -> bool:
    text = " ".join(quote.split()).lower()
    if _quote_is_uncertain(quote) or _quote_is_plain_objective_effect(quote):
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in EXHAUSTIVE_ACTION_CONCLUSION_PATTERNS)


def _quote_supports_applicability_target(quote: str, target: str) -> bool:
    """Require target-specific rule language, not a generic attribute or choose-k line."""
    text = " ".join(quote.split()).lower()
    if _quote_is_uncertain(quote):
        return False
    if target in RULE_DEPENDENT_APPLICABILITY_TARGETS and _quote_is_plain_objective_effect(quote):
        return False

    target_patterns = {
        "applicability.subject_eligibility": (
            r"(?:公司|企业|主体|人员|员工|患者|申请人|进口人|机构|持证主体|获授权申报人).{0,48}(?:具备|不具备|满足|不满足|符合|不符合).{0,16}(?:资格(?!证|文件|材料|记录)|准入条件|注册条件|许可条件|合规条件|适用条件)",
            r"(?:公司|企业|主体|人员|员工|患者|申请人|进口人|机构|持证主体|获授权申报人|[a-z0-9_-]{1,20}).{0,32}(?:有资格|无资格)(?!证|文件|材料|记录)",
            r"(?:公司|企业|主体|人员|员工|患者|申请人|进口人|机构|持证主体|获授权申报人).{0,48}(?:可|可以|不可|获准|允许|禁止|不得).{0,28}(?:申报|注册|登记|上市|进口|出口|运行|使用|进入|办理|参加|获得|治疗|交易)",
            r"(?:须|必须|只能).{0,20}由.{0,32}(?:获授权|有资格|持证|已注册).{0,24}(?:主体|人员|公司|企业|申报人|机构)",
            r"(?:firm|company|person|patient|applicant|importer).{0,48}(?:eligible|ineligible|permitted|prohibited|may|must not).{0,32}(?:register|file|market|use|operate|enter|participate)",
        ),
        "applicability.object_scope": (
            r"(?:本次|候选|商品|对象|适用).{0,20}(?:范围|清单).{0,28}(?:仅限|包括|包含|列有|排除)",
            r"(?:货物|商品|批次|设备|型号|产品|服务|交易|计划|项目).{0,48}(?:属于|列入|适用|不适用|包括|包含|排除).{0,32}(?:范围|清单|规则)?",
            r"(?:^|[，。；;])\s*[a-z0-9_-]{1,20}.{0,8}(?:属于|列入|适用|不适用|包括|包含|排除)",
            r"(?:item|product|goods|device|service|transaction).{0,48}(?:in scope|out of scope|covered|excluded|applies|does not apply)",
        ),
        "applicability.exception_exemption": (
            r"(?:无|没有|不存在|不设).{0,12}(?:例外|豁免|除外情形)",
            r"(?:例外|豁免|除外情形).{0,24}(?:适用|不适用|存在|不存在|允许|不得|可|无需|免于|排除)",
            r"(?:适用|不适用|存在|不存在|允许|不得|可|无需|免于|排除).{0,24}(?:例外|豁免|除外情形)",
            r"(?:免于|无需|不适用).{0,36}(?:义务|要求|限制|规则|条件|申报|注册|许可|适用)",
            r"(?:不考虑任何题外规则|题外(?:法律|法规|规则).{0,12}不适用|外部(?:限制|规则).{0,12}(?:均|都)?不适用)",
            r"(?:no|without).{0,16}(?:exception|exemption)|(?:exception|exemption).{0,24}(?:applies|does not apply|exists|is unavailable)|(?:is|are).{0,12}exempt",
        ),
        "applicability.action_consequence": (
            *EXHAUSTIVE_ACTION_CONCLUSION_PATTERNS,
            r"(?:一旦|若|如果|当|只有|仅当).{0,100}(?:申报|注册|登记|上市|进口|出口|运行|使用|进入|办理|参加|治疗|交易|交收|缴款|报销|释放|销售|处置).{0,80}(?:必须|须|不得|禁止|允许|可以|可|豁免|免于|才可|方可|才能)",
            r"(?:一旦|若|如果|当|只有|仅当).{0,100}(?:必须|须|不得|禁止|允许|可以|可|豁免|免于|才可|方可|才能).{0,80}(?:申报|注册|登记|上市|进口|出口|运行|使用|进入|办理|参加|治疗|交易|交收|缴款|报销|释放|销售|处置)",
            r"(?:公司|企业|主体|人员|员工|患者|货物|商品|批次|设备|型号|方案|行动|项目|交易|服务|申请人|进口人).{0,48}(?:可|可以|不可|获准|允许|禁止|不得|必须|须).{0,28}(?:申报|注册|登记|上市|进口|出口|采用|执行|使用|进入|办理|参加|治疗|交易)",
            r"(?:^|[，。；;])\s*[a-z0-9_-]{1,20}.{0,8}(?:可|可以|不可|获准|允许|禁止|不得|必须|须).{0,24}(?:申报|注册|登记|上市|进口|出口|采用|执行|使用|进入|办理|参加|治疗|交易)",
            r"(?:申报|注册|登记|上市|进口|出口|运行|使用|进入|办理|治疗|交易|交收|缴款|报销|释放|销售|处置).{0,36}(?:导致|触发|后果为).{0,36}(?:义务|禁止|许可|资格|责任|处罚|费用|期限|要求|限制)",
            r"(?:if|when|only if|unless).{1,100}(?:register|file|market|use|operate|enter|participate|trade).{0,80}(?:must|shall|may|permitted|prohibited|required)",
            r"(?:if|when|only if|unless).{1,100}(?:must|shall|may|permitted|prohibited|required).{0,80}(?:register|file|market|use|operate|enter|participate|trade)",
            r"(?:register|file|market|use|operate|enter|select).{0,40}(?:permitted|prohibited|required|must|shall|may)",
        ),
    }
    patterns = target_patterns.get(target, ())
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _public_action_meanings(prompt_zh: str) -> dict[str, str]:
    marker = re.search(r"公开\s*output_schema：", prompt_zh, flags=re.IGNORECASE)
    if marker is None:
        return {}
    try:
        value, _ = json.JSONDecoder().raw_decode(prompt_zh[marker.end():].lstrip())
    except (json.JSONDecodeError, TypeError):
        return {}
    actions = value.get("actions") if isinstance(value, dict) else None
    if not isinstance(actions, list):
        return {}
    meanings: dict[str, str] = {}
    for row in actions:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("meaning"), str):
            return {}
        meanings[row["id"]] = row["meaning"]
    return meanings


def _interface_text(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())


def _anchor_supports_applicability_target(clause: str, anchor: str, target: str) -> bool:
    if not _quote_supports_applicability_target(clause, target):
        return False
    text = _interface_text(clause)
    escaped = re.escape(anchor)
    if target == "applicability.object_scope":
        patterns = (
            rf"{escaped}.{{0,24}}(?:属于|列入|适用|不适用|包括|包含|排除|范围|清单)",
            rf"(?:范围|清单).{{0,12}}(?:包括|包含|列有|排除|仅限).{{0,24}}{escaped}",
            rf"{escaped}.{{0,32}}(?:inscope|outofscope|covered|excluded|applies|doesnotapply)",
        )
    elif target == "applicability.action_consequence":
        patterns = (
            rf"{escaped}.{{0,40}}(?:可|可以|不可|获准|允许|禁止|不得|必须|须|豁免|免于|才可|方可|才能)",
            rf"(?:获准|允许|禁止|不得|必须|须).{{0,20}}{escaped}",
            rf"{escaped}.{{0,48}}(?:permitted|prohibited|required|must|shall|may)",
        )
    else:
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _unique_action_anchors(target: str, action_meanings: dict[str, str]) -> set[str]:
    action_id = target.split(".", 1)[1]
    compact_action_id = _interface_text(action_id)
    meaning = action_meanings.get(action_id)
    if not meaning:
        return set()
    own = _interface_text(meaning)
    others = [_interface_text(value) for key, value in action_meanings.items() if key != action_id]
    anchors: set[str] = set()
    max_size = min(12, len(own))
    for size in range(max_size, 2, -1):
        for start in range(0, len(own) - size + 1):
            anchor = own[start:start + size]
            if all(anchor not in other for other in others):
                anchors.add(anchor)
    if len(compact_action_id) >= 4:
        anchors.add(compact_action_id)
    return anchors


def _quote_binds_variable_target(
    quote: str,
    target: str,
    action_meanings: dict[str, str],
) -> bool:
    """Bind a gap to one named public action or an explicit all-actions statement."""
    action_id = target.split(".", 1)[1]
    meaning = action_meanings.get(action_id)
    if not meaning:
        return False
    text = " ".join(quote.split())
    residual_scope = re.search(
        r"(?:其他|其它|额外|剩余|之一|其中|除外|只有一个|除(?:了)?.{1,40}?(?:以)?外)|"
        r"\b(?:other|additional|remaining|one\s+of|among|except|only\s+one)\b",
        text,
        flags=re.IGNORECASE,
    )
    universal_negated = re.search(
        r"(?:并非|不是|未必|不一定)\s*(?:是\s*)?(?:所有|全部|全体|每个|各个|各项)|"
        r"\bnot(?:\s+\w+){0,3}\s+(?:all|every|each)\b",
        text,
        flags=re.IGNORECASE,
    )
    generic_universal = re.search(
        r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?(?:行动|动作|方案|选项|决策)|"
        r"\b(?:all|every|each)\s+(?:candidate\s+)?(?:actions?|options?|alternatives?|decisions?)\b",
        text,
        flags=re.IGNORECASE,
    )
    if generic_universal is not None:
        if residual_scope is not None or universal_negated is not None:
            return False
        return True
    universal_categories = (
        (r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?项目|\b(?:all|every|each)\s+(?:candidate\s+)?projects?\b", r"(?:项目|project)"),
        (r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?型号|\b(?:all|every|each)\s+(?:candidate\s+)?models?\b", r"(?:型号|model)"),
        (r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?设备|\b(?:all|every|each)\s+(?:candidate\s+)?devices?\b", r"(?:设备|device)"),
        (r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?(?:服务商|供应商)|\b(?:all|every|each)\s+(?:candidate\s+)?providers?\b", r"(?:服务商|供应商|执行机构|provider)"),
        (r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?资产|\b(?:all|every|each)\s+(?:candidate\s+)?assets?\b", r"(?:资产|asset)"),
        (r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?变量|\b(?:all|every|each)\s+(?:candidate\s+)?variables?\b", r"(?:变量|variable)"),
        (r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?批次|\b(?:all|every|each)\s+(?:candidate\s+)?batches?\b", r"(?:批次|batch)"),
        (r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?产品|\b(?:all|every|each)\s+(?:candidate\s+)?products?\b", r"(?:产品|product)"),
        (r"(?:所有|全部|全体|每个|各个|各项)(?:候选)?(?:线|线路)|\b(?:all|every|each)\s+(?:candidate\s+)?(?:lines?|routes?|services?)\b", r"(?:线|线路|line|route|service)"),
    )
    matched_universal_categories = [
        meaning_pattern
        for quote_pattern, meaning_pattern in universal_categories
        if re.search(quote_pattern, text, flags=re.IGNORECASE)
    ]
    if matched_universal_categories:
        if residual_scope is not None or universal_negated is not None:
            return False
        if any(
            re.search(meaning_pattern, meaning, flags=re.IGNORECASE)
            for meaning_pattern in matched_universal_categories
        ):
            return True

    compact_quote = _interface_text(quote)
    compact_meaning = _interface_text(meaning)
    if compact_meaning:
        own_spans = [match.span() for match in re.finditer(re.escape(compact_meaning), compact_quote)]
        other_spans = [
            match.span()
            for key, value in action_meanings.items()
            if key != action_id and _interface_text(value) != compact_meaning
            for match in re.finditer(re.escape(_interface_text(value)), compact_quote)
        ]
        if any(
            not any(other_start <= start and end <= other_end for other_start, other_end in other_spans)
            for start, end in own_spans
        ):
            return True
    if len(_interface_text(action_id)) >= 4 and re.search(
        rf"(?<![0-9A-Za-z_.-]){re.escape(action_id)}(?![0-9A-Za-z_.-])",
        quote,
        flags=re.IGNORECASE,
    ):
        return True

    labeled_identifier = re.compile(
        r"(方案|选项|行动|项目|型号|设备|配方单|批次|产品|色素|服务商|供应商|资产|线|线路|"
        r"option|alternative|action|project|model|device|formula|batch|product|provider|asset|route|service)"
        r"\s*([A-Za-z][A-Za-z0-9_-]*|\d+)",
        flags=re.IGNORECASE,
    )
    identifier_before_label = re.compile(
        r"([A-Za-z][A-Za-z0-9_-]*|\d+)\s*(?:线|线路|route|service)",
        flags=re.IGNORECASE,
    )

    # A route/line label is a reliable public action-scope anchor even when
    # several different decisions exist for that same line.
    for identifier in identifier_before_label.findall(meaning):
        if re.search(
            rf"(?<![0-9A-Za-z_]){re.escape(identifier)}\s*(?:线|线路|route|service)",
            quote,
            flags=re.IGNORECASE,
        ):
            return True

    def identifiers(value: str) -> set[str]:
        return {
            identifier.lower()
            for _label, identifier in labeled_identifier.findall(value)
        } | {
            identifier.lower() for identifier in identifier_before_label.findall(value)
        }

    own_identifiers = identifiers(meaning)
    other_identifiers = {
        match.lower()
        for key, value in action_meanings.items()
        if key != action_id
        for match in identifiers(value)
    }

    def identifier_has_context(identifier: str) -> bool:
        escaped = re.escape(identifier)
        own_labels = {
            label.lower()
            for label, observed in labeled_identifier.findall(meaning)
            if observed.lower() == identifier
        }
        observed_labels = {
            label.lower()
            for label, observed in labeled_identifier.findall(quote)
            if observed.lower() == identifier
        }
        if observed_labels:
            return bool(own_labels & observed_labels)
        return bool(
            re.search(
                rf"(?<![0-9A-Za-z_]){escaped}\s*(?:线|线路|route|service|为|的|自)",
                quote,
                flags=re.IGNORECASE,
            )
        )

    for identifier in own_identifiers - other_identifiers:
        if identifier_has_context(identifier):
            return True

    named_anchor_patterns = (
        r"把(.{2,80}?)(?:选为|作为)",
        r"采用([A-Za-z][A-Za-z0-9 _-]{1,40}?)(?:双班组合|组合)",
    )
    for pattern in named_anchor_patterns:
        for anchor in re.findall(pattern, meaning, flags=re.IGNORECASE):
            compact_anchor = _interface_text(anchor)
            if len(compact_anchor) >= 2 and compact_anchor in compact_quote:
                return True
    return False


def _quote_binds_action_meaning(
    quote: str,
    target: str,
    action_meanings: dict[str, str],
    applicability_targets: set[str],
) -> bool:
    anchors = _unique_action_anchors(target, action_meanings)
    if not anchors:
        return False
    relevant_targets = applicability_targets & {
        "applicability.object_scope",
        "applicability.action_consequence",
    }
    for clause in re.split(r"[，,。；;]+", quote):
        if not clause.strip() or not any(
            _quote_supports_applicability_target(clause, applicability_target)
            for applicability_target in relevant_targets
        ):
            continue
        compact_clause = _interface_text(clause)
        clause_anchors = {anchor for anchor in anchors if anchor in compact_clause}
        if any(
            _anchor_supports_applicability_target(clause, anchor, applicability_target)
            for anchor in clause_anchors
            for applicability_target in relevant_targets
        ):
            return True
    return False


def _authoritative_rule_targets(prompt_zh: str) -> set[str]:
    """Return rule-dependent dimensions explicitly covered by an in-prompt rule block."""
    body = _authoritative_rule_material(prompt_zh)
    if not body:
        return set()
    targets: set[str] = set()
    normative = r"(?:须|必须|应当|需要|不得|禁止|允许|获准|适用|不适用|不进入|要求|上限|下限|豁免|免于)"
    if re.search(
        rf"(?:公司|企业|主体|人员|员工|患者|申请人|进口人|机构|账户|经营者).{{0,64}}{normative}",
        body,
        flags=re.IGNORECASE,
    ):
        targets.add("applicability.subject_eligibility")
    if re.search(
        rf"(?:合同|产品|服务|投资|资产|货物|商品|批次|设备|型号|项目|交易|账户).{{0,64}}{normative}",
        body,
        flags=re.IGNORECASE,
    ):
        targets.add("applicability.object_scope")
    if re.search(r"(?:例外|豁免|除外|不适用|不进入|免于|排除)", body, flags=re.IGNORECASE):
        targets.add("applicability.exception_exemption")
    if re.search(
        rf"(?:选择|采用|执行|申报|注册|登记|上市|进口|出口|运行|使用|进入|办理|治疗|交易).{{0,64}}{normative}|"
        rf"{normative}.{{0,64}}(?:选择|采用|执行|申报|注册|登记|上市|进口|出口|运行|使用|进入|办理|治疗|交易)",
        body,
        flags=re.IGNORECASE,
    ):
        targets.add("applicability.action_consequence")
    return targets


def _rule_material_matches_provenance_target(prompt_zh: str, target: str) -> bool:
    """Keep a redundant-provenance join inside the same rule/attribute family."""
    body = _authoritative_rule_material(prompt_zh)
    if not body:
        return False
    patterns = {
        "applicability.subject_eligibility": (
            r"(?:合同|养老金|年金|contract|pension|annuity).{0,80}(?:须|必须|不得|禁止|允许|适用|不适用|不进入|要求|测试|must|shall|required|excluded|applies)",
            r"(?:须|必须|不得|禁止|允许|适用|不适用|不进入|要求|测试|must|shall|required|excluded|applies).{0,80}(?:合同|养老金|年金|contract|pension|annuity)",
        ),
        "applicability.object_scope": (
            r"(?:投资|资产|债券|发行人|基金|合伙企业|investment|asset|bond|issuer|fund|partnership).{0,96}(?:须|必须|不得|禁止|允许|适用|不适用|不超过|上限|下限|分散|范围|must|shall|required|excluded|limit|scope)",
            r"(?:须|必须|不得|禁止|允许|适用|不适用|不超过|上限|下限|分散|范围|must|shall|required|excluded|limit|scope).{0,96}(?:投资|资产|债券|发行人|基金|合伙企业|investment|asset|bond|issuer|fund|partnership)",
        ),
    }
    return any(re.search(pattern, body, flags=re.IGNORECASE) for pattern in patterns.get(target, ()))


def _applicability_support_kind(prompt_zh: str, quote: str, target: str) -> str | None:
    if _quote_supports_applicability_target(quote, target):
        return "DIRECT_QUOTE"
    if target not in _authoritative_rule_targets(prompt_zh):
        return None
    rule_body = _authoritative_rule_material(prompt_zh)
    return "AUTHORITATIVE_RULE" if _quote_in_prompt(rule_body, quote) else "COMPOSED_CASE_RULE"


def _quote_matches_fact_unit(quote: str, unit: str) -> bool:
    compact_quote = _compact_unit(quote)
    compact_unit = _compact_unit(unit)
    return bool(compact_quote and compact_unit and (compact_quote in compact_unit or compact_unit in compact_quote))


def _normalize_stage_fact_coverage(
    prompt_zh: str,
    model_ir: ValidatedIR,
    raw_rows: list[Any],
) -> list[dict[str, Any]]:
    """Fail closed on unsupported applicability while repairing deterministic bookkeeping."""
    expected_keys = {"quote", "or_role", "mapped_targets", "usage_status", "reason"}
    for row in raw_rows:
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise ValueError("fact_coverage stage returned an invalid fact row")
        if any(
            isinstance(row.get(key), str)
            and PROGRAM_FACT_COVERAGE_CLOSURE_MARKER in row[key]
            for key in ("or_role", "reason")
        ):
            raise ValueError("fact_coverage stage cannot supply a program-owned closure row")
        if not all(
            isinstance(row.get(key), str) and bool(row[key].strip())
            for key in ("quote", "or_role", "reason", "usage_status")
        ):
            raise ValueError("fact_coverage stage returned invalid text fields")
        if not isinstance(row.get("mapped_targets"), list) or any(
            not isinstance(target, str) or not target or target != target.strip()
            for target in row["mapped_targets"]
        ):
            raise ValueError("fact_coverage stage returned invalid mapped_targets")
        try:
            FactUsageStatus(row["usage_status"])
        except ValueError as exc:
            raise ValueError("fact_coverage stage returned an invalid usage_status") from exc

    fact_units = prompt_fact_units(prompt_zh)
    auditable_prompt = prompt_fact_prefix(prompt_zh)
    filtered: list[dict[str, Any]] = []
    for source in raw_rows:
        row = copy.deepcopy(source)
        quote = row["quote"]
        if quote not in auditable_prompt:
            continue
        if not any(_quote_matches_fact_unit(quote, unit) for unit in fact_units):
            continue
        filtered.append(row)

    existing_targets = _fact_model_targets(model_ir)
    rule_body = _authoritative_rule_material(prompt_zh)
    authoritative_rule_targets = {
        target
        for target in _authoritative_rule_targets(prompt_zh)
        if _rule_material_matches_provenance_target(prompt_zh, target)
    }
    case_attribute_witnesses = {
        target
        for sibling in filtered
        if sibling["usage_status"] == FactUsageStatus.APPLICABILITY_USED.value
        and not _quote_in_prompt(rule_body, sibling["quote"])
        for target in set(sibling["mapped_targets"]) & authoritative_rule_targets
        if _quote_asserts_case_attribute(sibling["quote"], target)
    }
    normalized: list[dict[str, Any]] = []
    pending_unaccounted: list[dict[str, Any]] = []
    for row in filtered:
        quote = row["quote"]
        status = FactUsageStatus(row["usage_status"])
        targets = list(row["mapped_targets"])

        if status == FactUsageStatus.UNACCOUNTED and not targets:
            redundant_provenance_targets = (
                _provenance_only_applicability_targets(quote)
                & case_attribute_witnesses
                & authoritative_rule_targets
            )
            if redundant_provenance_targets:
                targets = sorted(redundant_provenance_targets)
                status = FactUsageStatus.APPLICABILITY_USED
                names = ", ".join(targets)
                row["reason"] += f" [PROGRAM_REDUNDANT_PROVENANCE_BOUND: {names}]"

        if status == FactUsageStatus.UNACCOUNTED and re.search(
            r"(?:无|没有|不存在)(?:任何)?(?:其他|其它|额外|另外|剩余)(?:资产|行动|选项|资源)",
            quote,
        ):
            matching_units = [unit for unit in fact_units if _quote_matches_fact_unit(quote, unit)]
            sibling_targets = sorted(
                {
                    target
                    for sibling in filtered
                    if sibling is not row
                    and any(_quote_matches_fact_unit(sibling["quote"], unit) for unit in matching_units)
                    for target in sibling["mapped_targets"]
                    if target.startswith("constraint.") and target in existing_targets
                }
            )
            if sibling_targets:
                targets = sibling_targets
                status = FactUsageStatus.MODELED
                row["reason"] += " [PROGRAM_BOUND_RESIDUAL_CLOSURE_TO_BALANCE]"

        if status == FactUsageStatus.APPLICABILITY_USED:
            dependent_rule_targets = set(targets) & RULE_DEPENDENT_APPLICABILITY_TARGETS
            unsupported = {
                target
                for target in dependent_rule_targets
                if _applicability_support_kind(prompt_zh, quote, target) is None
            }
            composed = {
                target
                for target in dependent_rule_targets
                if _applicability_support_kind(prompt_zh, quote, target) == "COMPOSED_CASE_RULE"
            }
            if composed:
                names = ", ".join(sorted(composed))
                row["reason"] += f" [PROGRAM_COMPOSED_WITH_IN_PROMPT_RULE: {names}]"
            if unsupported:
                targets = [target for target in targets if target not in unsupported]
                remaining_applicability = {target for target in targets if _is_applicability_target(target)}
                remaining_model = [target for target in targets if target in existing_targets]
                if remaining_applicability:
                    status = FactUsageStatus.APPLICABILITY_USED
                elif remaining_model:
                    status = FactUsageStatus.MODELED
                    targets = remaining_model
                else:
                    status = FactUsageStatus.UNACCOUNTED
                    targets = []
                names = ", ".join(sorted(unsupported))
                row["reason"] += f" [PROGRAM_OPENED_UNSUPPORTED_APPLICABILITY: {names}]"
                if status != FactUsageStatus.UNACCOUNTED:
                    pending_unaccounted.append(
                        {
                            "quote": quote,
                            "or_role": f"{row['or_role']}_REALITY_GAP",
                            "mapped_targets": [],
                            "usage_status": FactUsageStatus.UNACCOUNTED.value,
                            "reason": f"Program opened unsupported applicability targets: {names}",
                        }
                    )

        row["mapped_targets"] = targets
        row["usage_status"] = status.value
        normalized.append(row)

    unaccounted_quotes = {
        " ".join(row["quote"].split())
        for row in normalized
        if row["usage_status"] == FactUsageStatus.UNACCOUNTED.value
    }
    for row in pending_unaccounted:
        key = " ".join(row["quote"].split())
        if key not in unaccounted_quotes:
            normalized.append(row)
            unaccounted_quotes.add(key)
    return normalized


def initialize_state(
    public: PublicCase,
    initial: InitialDecision,
    base_ir: ValidatedIR,
    capture: Any,
) -> DecisionCompleteORState:
    if len(initial.candidate_gaps) > 3:
        raise ValueError("InitialDecision must report overflow instead of returning more than three gaps")
    if initial.audit_summary.overflow_detected != (initial.audit_summary.overflow_count > 0):
        raise ValueError("audit overflow fields disagree")
    existing_targets = _existing_targets(base_ir)
    fact_model_targets = _fact_model_targets(base_ir)
    auditable_prompt = prompt_fact_prefix(public.prompt_zh)
    declared_reality_interface = _declares_reality_interface(auditable_prompt)
    authoritative_rule_material = _has_authoritative_rule_material(auditable_prompt)
    decision_variable_targets = {f"variable.{row['id']}" for row in base_ir["variables"]}
    action_meanings = _public_action_meanings(public.prompt_zh)

    for draft in initial.candidate_gaps:
        route_query_is_valid = (
            draft.gap_route == GapRoute.OUT_OF_SCOPE and draft.first_query is None
        ) or (
            draft.gap_route == GapRoute.LOCAL_FACT and draft.first_query is None
        ) or (
            draft.gap_route == GapRoute.EXTERNAL_RULE and bool(draft.first_query)
        )
        if not route_query_is_valid:
            raise ValueError("candidate gap route/query contract is invalid")
        if draft.target in REGISTERED_APPLICABILITY_TARGETS:
            if (
                draft.hypothetical_variants
                or initial.self_contained_candidate
                or initial.audit_summary.model_interface_to_grounding_complete is not False
            ):
                raise ValueError("audit-only unbound target contract is invalid")
        elif draft.target not in existing_targets:
            raise ValueError("candidate gap target is absent from allowed_gap_targets")

    unaccounted_rows = [
        (index, " ".join(draft.quote.split()))
        for index, draft in enumerate(initial.fact_coverage, start=1)
        if draft.usage_status == FactUsageStatus.UNACCOUNTED
    ]
    unaccounted_quotes = {quote for _, quote in unaccounted_rows}
    program_unaccounted_quotes = {
        draft.quote
        for draft in initial.fact_coverage
        if draft.usage_status == FactUsageStatus.UNACCOUNTED
        and draft.or_role == PROGRAM_FACT_COVERAGE_CLOSURE_MARKER
        and draft.reason == PROGRAM_FACT_COVERAGE_CLOSURE_REASON
    }
    collapsed_program_quotes = {" ".join(quote.split()) for quote in program_unaccounted_quotes}
    quoted_gap_facts = {
        " ".join(quote.split())
        for draft in initial.candidate_gaps
        for quote in draft.fact_quotes
    }
    exact_quoted_gap_facts = {
        quote
        for draft in initial.candidate_gaps
        for quote in draft.fact_quotes
    }
    invalid_gap_indices = [
        index
        for index, draft in enumerate(initial.candidate_gaps, start=1)
        if any(" ".join(quote.split()) not in unaccounted_quotes for quote in draft.fact_quotes)
    ]
    target_binding_gap_indices = [
        index
        for index, draft in enumerate(initial.candidate_gaps, start=1)
        if action_meanings
        and draft.target.startswith("variable.")
        and not any(
            _quote_binds_variable_target(quote, draft.target, action_meanings)
            for quote in draft.fact_quotes
        )
    ]
    program_gap_indices = [
        index
        for index, draft in enumerate(initial.candidate_gaps, start=1)
        if any(" ".join(quote.split()) in collapsed_program_quotes for quote in draft.fact_quotes)
    ]
    invalid_gap_indices = sorted(
        set(invalid_gap_indices)
        | set(program_gap_indices)
        | set(target_binding_gap_indices)
    )
    program_unlinked_fact_indices = [
        index
        for index, draft in enumerate(initial.fact_coverage, start=1)
        if draft.quote in program_unaccounted_quotes
        and draft.quote not in exact_quoted_gap_facts
    ]
    ordinary_unlinked_fact_indices = [] if initial.audit_summary.overflow_detected else [
        index for index, quote in unaccounted_rows if quote not in quoted_gap_facts
    ]
    unlinked_fact_indices = sorted(
        set(ordinary_unlinked_fact_indices) | set(program_unlinked_fact_indices)
    )
    information_audit_failure = None
    if program_unaccounted_quotes or target_binding_gap_indices or (
        (invalid_gap_indices or unlinked_fact_indices)
        and initial.self_contained_candidate is False
        and initial.audit_summary.model_interface_to_grounding_complete is False
    ):
        information_audit_failure = {
            "code": (
                FACT_COVERAGE_AUDIT_FAILURE_CODE
                if program_unaccounted_quotes
                else INFORMATION_AUDIT_FAILURE_CODE
            ),
            "invalid_gap_indices": invalid_gap_indices,
            "unlinked_fact_indices": unlinked_fact_indices,
        }

    gaps: list[ModelingGapRow] = []
    materialized_gap_drafts = [] if information_audit_failure is not None else initial.candidate_gaps
    for index, draft in enumerate(materialized_gap_drafts, start=1):
        if any(not _quote_in_prompt(auditable_prompt, quote) for quote in draft.fact_quotes):
            raise ValueError("candidate gap fact quote is absent from the auditable prompt prefix")
        if draft.target in REGISTERED_APPLICABILITY_TARGETS:
            original_route = draft.gap_route.value
            original_query = draft.first_query
            legacy_external = draft.gap_route == GapRoute.EXTERNAL_RULE and bool(original_query)
            native_out_of_scope = draft.gap_route == GapRoute.OUT_OF_SCOPE and original_query is None
            native_local_fact = draft.gap_route == GapRoute.LOCAL_FACT and original_query is None
            if (
                not (legacy_external or native_out_of_scope or native_local_fact)
                or draft.hypothetical_variants
                or "PROGRAM_UNBOUND_OR_TARGET" not in draft.gap_claim
                or initial.self_contained_candidate
                or initial.audit_summary.model_interface_to_grounding_complete is not False
            ):
                raise ValueError("audit-only unbound target contract is invalid")
            target = None
            proposed_information_target = draft.target
            target_binding_status = TargetBindingStatus.UNBOUND
            state = GapState.UNRESOLVED_ABSTAIN
            realized_effect = {
                "reason": f"PROGRAM_UNBOUND_OR_TARGET: {draft.target}",
                "normalization_record": {
                    "original_target": draft.target,
                    "original_gap_route": original_route,
                    "original_first_query": original_query,
                    "effective_target": None,
                },
            }
            effective_route = GapRoute.OUT_OF_SCOPE
            pending_query = None
        else:
            if draft.target not in existing_targets:
                raise ValueError("candidate gap target is absent from allowed_gap_targets")
            target = draft.target
            proposed_information_target = draft.target
            target_binding_status = TargetBindingStatus.BOUND
            state = GapState.OPEN
            realized_effect = None
            effective_route = draft.gap_route
            pending_query = draft.first_query
        gaps.append(
            ModelingGapRow(
                gap_id=f"G{index}",
                fact_quotes=list(draft.fact_quotes),
                reality_role=draft.reality_role,
                gap_claim=draft.gap_claim,
                target=target,
                proposed_information_target=proposed_information_target,
                target_binding_status=target_binding_status,
                gap_route=effective_route,
                pending_query=pending_query,
                state=state,
                realized_effect=realized_effect,
            )
        )

    facts: list[FactCoverageRow] = []
    grounded_rule_dimensions: set[str] = set()
    grounded_rule_interfaces: set[str] = set()
    downgraded_dimensions: set[AuditDimension] = set()
    for draft in initial.fact_coverage:
        usage_status = draft.usage_status
        mapped_targets = list(draft.mapped_targets)
        reason = draft.reason
        if not _quote_in_prompt(auditable_prompt, draft.quote):
            raise ValueError("FactCoverage quote is absent from the auditable prompt prefix")
        if usage_status == FactUsageStatus.IRRELEVANT_JUSTIFIED:
            raise ValueError("InitialDecision cannot write IRRELEVANT_JUSTIFIED")
        if usage_status in {FactUsageStatus.MODELED, FactUsageStatus.DERIVED}:
            if not mapped_targets or any(target not in fact_model_targets for target in mapped_targets):
                raise ValueError("MODELED/DERIVED fact does not map to an existing canonical IR target")
        if usage_status == FactUsageStatus.APPLICABILITY_USED:
            if _quote_is_uncertain(draft.quote):
                raise ValueError("APPLICABILITY_USED cannot close an uncertain or unverified prompt statement")
            applicability_targets = {
                target for target in mapped_targets if target.startswith("applicability.")
            }
            if (
                not mapped_targets
                or not applicability_targets
                or any(not _is_applicability_target(target) for target in applicability_targets)
                or any(
                    target not in fact_model_targets and not _is_applicability_target(target)
                    for target in mapped_targets
                )
            ):
                raise ValueError("APPLICABILITY_USED fact lacks a valid applicability/model target")
            rule_targets = applicability_targets & RULE_DEPENDENT_APPLICABILITY_TARGETS
            support_kinds = {
                target: _applicability_support_kind(public.prompt_zh, draft.quote, target)
                for target in rule_targets
            }
            unsupported = {
                target
                for target in rule_targets
                if support_kinds[target] is None
            }
            if unsupported:
                if initial.self_contained_candidate:
                    names = ", ".join(sorted(unsupported))
                    raise ValueError(
                        "APPLICABILITY_USED rule-dependent target lacks a target-specific operative rule "
                        f"or authoritative applicability conclusion: {names}"
                    )
                mapped_targets = [target for target in mapped_targets if target not in unsupported]
                downgraded_dimensions.update(
                    AuditDimension(target.split(".", 1)[1].upper()) for target in unsupported
                )
                remaining_applicability = {
                    target for target in mapped_targets if target.startswith("applicability.")
                }
                if remaining_applicability:
                    usage_status = FactUsageStatus.APPLICABILITY_USED
                elif mapped_targets:
                    usage_status = FactUsageStatus.MODELED
                else:
                    raise ValueError(
                        "program normalization removed every unsupported applicability target and left no model use"
                    )
                names = ", ".join(sorted(unsupported))
                reason = (
                    f"{reason} [PROGRAM_NORMALIZED_UNSUPPORTED_APPLICABILITY: removed {names}; "
                    f"status={usage_status.value}; grounding remains open]"
                )
                applicability_targets -= unsupported
                rule_targets -= unsupported
            direct_rule_targets = {
                target
                for target in rule_targets
                if support_kinds.get(target) in {"DIRECT_QUOTE", "AUTHORITATIVE_RULE"}
            }
            grounded_rule_dimensions.update(direct_rule_targets)
            interface_targets = set(mapped_targets) & decision_variable_targets
            if direct_rule_targets & {
                "applicability.object_scope",
                "applicability.action_consequence",
            }:
                if (
                    "applicability.action_consequence" in direct_rule_targets
                    and _quote_has_exhaustive_action_conclusion(draft.quote)
                ):
                    grounded_rule_interfaces.update(interface_targets)
                else:
                    grounded_rule_interfaces.update(
                        target
                        for target in interface_targets
                        if _quote_binds_action_meaning(
                            draft.quote,
                            target,
                            action_meanings,
                            direct_rule_targets,
                        )
                    )
        if usage_status == FactUsageStatus.UNACCOUNTED and mapped_targets:
            raise ValueError("UNACCOUNTED fact must use mapped_targets=[]")
        linked = [
            gap.gap_id
            for gap in gaps
            if usage_status == FactUsageStatus.UNACCOUNTED
            and any(" ".join(draft.quote.split()) == " ".join(quote.split()) for quote in gap.fact_quotes)
        ]
        if (
            usage_status == FactUsageStatus.UNACCOUNTED
            and not linked
            and not initial.audit_summary.overflow_detected
            and information_audit_failure is None
        ):
            raise ValueError("UNACCOUNTED fact must link to a Candidate Gap")
        # One prompt fact may affect several OR interfaces.  Materialize one
        # state row per gap so each effect can close independently while the
        # public LLM schema remains a simple single-gap-id row.
        for linked_gap_id in linked or [None]:
            facts.append(
                FactCoverageRow(
                    fact_id=f"F{len(facts) + 1}",
                    quote=draft.quote,
                    or_role=draft.or_role,
                    mapped_targets=list(mapped_targets),
                    usage_status=usage_status,
                    reason=reason,
                    gap_id=linked_gap_id,
                )
            )
    linked_gap_ids = {fact.gap_id for fact in facts if fact.gap_id}
    if any(gap.gap_id not in linked_gap_ids for gap in gaps):
        raise ValueError("every Candidate Gap must link back to at least one UNACCOUNTED fact")
    if (
        information_audit_failure is None
        and initial.self_contained_candidate
        and declared_reality_interface
        and not authoritative_rule_material
    ):
        missing_witnesses = RULE_DEPENDENT_APPLICABILITY_TARGETS - grounded_rule_dimensions
        if missing_witnesses:
            missing = ", ".join(sorted(missing_witnesses))
            raise ValueError(
                "self_contained_candidate lacks quote-grounded reality-interface witnesses: "
                f"{missing}"
            )
        missing_interfaces = decision_variable_targets - grounded_rule_interfaces
        if missing_interfaces:
            missing = ", ".join(sorted(missing_interfaces))
            raise ValueError(
                "self_contained_candidate lacks quote-grounded applicability coverage for decision interfaces: "
                f"{missing}"
            )
    units, uncovered, ratio = prompt_fact_coverage(public.prompt_zh, initial.fact_coverage)
    audit_summary = copy.deepcopy(initial.audit_summary)
    if information_audit_failure is not None:
        audit_summary.model_interface_to_grounding_complete = False
    if program_unaccounted_quotes:
        audit_summary.prompt_fact_to_model_complete = False
        audit_summary.model_interface_to_grounding_complete = False
        audit_summary.self_contained_reason = PROGRAM_FACT_COVERAGE_AUDIT_REASON
    if downgraded_dimensions:
        audit_summary.model_interface_to_grounding_complete = False
        for dimension in downgraded_dimensions:
            audit_summary.negative_space_checked[dimension] = False
        names = ", ".join(sorted(dimension.value for dimension in downgraded_dimensions))
        audit_summary.self_contained_reason = (
            f"PROGRAM_NORMALIZED_UNSUPPORTED_APPLICABILITY: {names}; grounding remains open"
        )
    audit_summary.prompt_fact_unit_total = len(units)
    audit_summary.prompt_fact_unit_covered = len(units) - len(uncovered)
    audit_summary.prompt_fact_coverage_ratio = ratio
    if not units:
        raise ValueError("prompt_zh contains no auditable fact/optimization units")
    if uncovered:
        preview = " | ".join(uncovered[:3])
        raise ValueError(
            f"FactCoverage omitted {len(uncovered)}/{len(units)} prompt fact units: {preview}"
        )
    self_contained = (
        initial.self_contained_candidate
        and not gaps
        and audit_complete(audit_summary)
        and all(fact.usage_status != FactUsageStatus.UNACCOUNTED for fact in facts)
        and capture.status == "OPTIMAL"
        and capture.feasible
    )
    if initial.self_contained_candidate and gaps:
        raise ValueError("self_contained_candidate cannot coexist with Candidate Gaps")
    return DecisionCompleteORState(
        eval_id=public.eval_id,
        input_digest=digest_json({"eval_id": public.eval_id, "prompt_zh": public.prompt_zh}),
        round=0,
        search_budget_left=SEARCH_QUERY_BUDGET,
        base_ir_digest=digest_json(base_ir),
        current_ir_digest=digest_json(base_ir),
        base_solve=copy.deepcopy(capture),
        current_solve=copy.deepcopy(capture),
        audit_summary=audit_summary,
        self_contained=self_contained,
        fact_coverage=facts,
        active_gap_id=None,
        gaps=gaps,
        information_audit_failure=information_audit_failure,
    )


def variants_by_gap(
    state: DecisionCompleteORState,
    gaps: list[CandidateGapDraft],
    current_ir: ValidatedIR,
) -> dict[str, list[dict[str, Any]]]:
    if len(state.gaps) != len(gaps):
        raise ValueError("typed gaps and materialized state gaps disagree")
    variables = {row["id"]: row for row in current_ir["variables"]}
    result: dict[str, list[dict[str, Any]]] = {}
    for row, draft in zip(state.gaps, gaps):
        variants = copy.deepcopy(draft.hypothetical_variants)
        if (
            not variants
            and row.target_binding_status == TargetBindingStatus.BOUND
            and row.gap_route == GapRoute.EXTERNAL_RULE
            and isinstance(row.target, str)
            and row.target.startswith("variable.")
        ):
            action_id = row.target.split(".", 1)[1]
            variable = variables.get(action_id)
            if (
                variable is not None
                and variable["type"] == "BINARY"
                and variable["lb"] == 0
                and variable["ub"] == 1
            ):
                variants = [
                    {
                        "target": row.target,
                        "operation": "SET",
                        "value": {"lb": 0, "ub": 0},
                        "range_basis": "MODEL_BOUNDARY",
                        "basis_quote": None,
                    }
                ]
        result[row.gap_id] = variants
    return result


def close_or_abstain(
    state: DecisionCompleteORState,
    gap_id: str,
    reason: str,
) -> DecisionCompleteORState:
    return apply_state_update(state, StateUpdate.abstain(gap_id, reason))


def record_search_round(
    state: DecisionCompleteORState,
    gap_id: str,
    trace: RetrievalTrace,
) -> DecisionCompleteORState:
    if state.active_gap_id != gap_id or next(row for row in state.gaps if row.gap_id == gap_id).state != GapState.NEED_SEARCH:
        raise ValueError("only an active NEED_SEARCH gap can record a search round")
    if not trace.query_attempted:
        raise ValueError("search budget may only be charged after a real query attempt")
    budget_consumed = trace.query_budget_consumed
    if (
        not isinstance(budget_consumed, int)
        or isinstance(budget_consumed, bool)
        or budget_consumed < 1
    ):
        raise ValueError("retrieval trace consumed an invalid search budget")
    if budget_consumed > state.search_budget_left:
        raise SearchBudgetOverrun(
            prior_budget=SEARCH_QUERY_BUDGET - state.search_budget_left,
            remaining_budget=state.search_budget_left,
            actual_consumed=budget_consumed,
        )
    if state.search_budget_left <= 0 or state.round >= SEARCH_QUERY_BUDGET:
        raise ValueError("semantic search budget is exhausted")
    result = copy.deepcopy(state)
    result.round += 1
    result.search_budget_left -= budget_consumed
    return result


def record_solve_delta(
    state: DecisionCompleteORState,
    gap_id: str,
    current_ir: ValidatedIR,
    candidate_ir: ValidatedIR,
    capture: Any,
    bundle: Any,
) -> tuple[DecisionCompleteORState, ValidatedIR]:
    """Commit the copied candidate only for the current strict decision-change rule.

    Search authorization accepts value, decision, or feasibility effects, while
    this V0 commit rule accepts only ``DECISION_CHANGE``.  The asymmetry is an
    explicit review point, not an implicit solver behavior.
    """

    effect, delta = compare_solves(state.current_solve, capture)
    if capture.status != "OPTIMAL" or not capture.feasible:
        return (
            apply_state_update(state, StateUpdate.abstain(gap_id, "PATCH_RE_SOLVE_FAILED: candidate IR rolled back")),
            current_ir,
        )
    if effect.value != "DECISION_CHANGE":
        return (
            apply_state_update(
                state,
                StateUpdate.abstain(gap_id, f"PATCH_STABLE_OR_UNCERTAIN({effect.value}): candidate IR rolled back"),
            ),
            current_ir,
        )
    result = copy.deepcopy(state)
    result.current_ir_digest = digest_json(candidate_ir)
    result.current_solve = copy.deepcopy(capture)
    from .patch import semantic_patch_elements

    result = apply_state_update(
        result,
        StateUpdate.patch_closed(
            gap_id,
            {"bundle": jsonable(bundle), "semantic_patch_elements": semantic_patch_elements(bundle)},
            {**delta, "effect": effect.value},
        ),
    )
    return result, candidate_ir


def mark_unresolved_abstain(state: DecisionCompleteORState, gap_id: str, reason: str) -> DecisionCompleteORState:
    return apply_state_update(state, StateUpdate.abstain(gap_id, reason))


def finalize(state: DecisionCompleteORState) -> dict[str, Any]:
    if state.information_audit_failure is not None:
        return {
            "status": "ABSTAIN",
            "decision_state": None,
            "applicability": None,
            "patch": None,
            "actions": None,
            "objective": None,
            "solver_status": None,
            "failure_detail": f"information audit failed: {state.information_audit_failure['code']}",
        }
    if not is_decision_complete(state):
        return {
            "status": "ABSTAIN",
            "decision_state": None,
            "applicability": None,
            "patch": None,
            "actions": None,
            "objective": None,
            "solver_status": None,
            "failure_detail": "decision-complete OR information state is not closed",
        }
    closed_patch = [gap for gap in state.gaps if gap.state == GapState.CLOSED_PATCH]
    closed_retain = [gap for gap in state.gaps if gap.state == GapState.CLOSED_RETAIN]
    if closed_patch:
        final_effect, _ = compare_solves(state.base_solve, state.current_solve)
        if final_effect.value == "NO_EFFECT":
            return {
                "status": "ABSTAIN",
                "decision_state": None,
                "applicability": None,
                "patch": None,
                "actions": None,
                "objective": None,
                "solver_status": None,
                "failure_detail": "PATCH_STABLE after base-to-current comparison",
            }
        decision_state, applicability = "PATCH_CHANGES", True
    elif closed_retain:
        decision_state = "RETAIN"
        applicability = all(
            isinstance(gap.evidence, dict) and gap.evidence.get("admission") == Admission.ALREADY_MODELED.value
            for gap in closed_retain
        )
    else:
        decision_state, applicability = "NO_SEARCH", True
    return {
        "status": "OK",
        "decision_state": decision_state,
        "applicability": applicability,
        "patch": [
            element
            for gap in closed_patch
            for element in ((gap.patch or {}).get("semantic_patch_elements") or [])
        ],
        "actions": state.current_solve.actions,
        "objective": state.current_solve.objective,
        "solver_status": state.current_solve.status,
        "failure_detail": None,
    }


def _search_output(
    traces: list[RetrievalTrace],
    evidence_history: list[EvidenceDecision],
) -> dict[str, Any]:
    pages = []
    for trace in traces:
        for page in trace.opened_pages:
            pages.append(
                {
                    key: page.get(key)
                    for key in ("requested_url", "final_url", "url", "title", "publisher", "content_type", "backend")
                    if page.get(key) is not None
                }
            )
    verified_quotes = {
        (card.url, card.quote)
        for decision in evidence_history
        for card in decision.evidence_cards
        if card.supported
    }
    return {
        "search_backend": "shubiaobiao_responses_web_search",
        "backend_fallback": False,
        "queries": [trace.planned_query for trace in traces if trace.query_attempted],
        "executed_queries": [
            query
            for trace in traces
            for query in trace.executed_queries
            if trace.query_attempted
        ],
        "pages": pages,
        "search_count": sum(
            trace.query_budget_consumed for trace in traces if trace.query_attempted
        ),
        "search_round_count": sum(trace.query_attempted for trace in traces),
        "pages_opened": len(pages),
        "page_open_attempt_count": sum(len(trace.page_attempts) for trace in traces),
        "readable_page_count": sum(len(trace.opened_pages) for trace in traces),
        "verified_quote_count": len(verified_quotes),
        "rounds": [
            {
                "gap_id": trace.gap_id,
                "planned_query": trace.planned_query,
                "executed_query": trace.executed_query,
                "executed_queries": trace.executed_queries,
                "query_attempted": trace.query_attempted,
                "query_budget_consumed": trace.query_budget_consumed,
                "results_discarded": trace.results_discarded,
                "backend_raw_result_count": trace.backend_raw_result_count,
                "result_count": len(trace.results),
                "page_count": len(trace.opened_pages),
                "failure_type": trace.failure_type,
                "failure_detail": trace.failure_detail,
                "wall_seconds": trace.wall_seconds,
            }
            for trace in traces
        ],
    }


def _finish_case(
    state: DecisionCompleteORState,
    base_ir: ValidatedIR,
    current_ir: ValidatedIR,
    traces: list[RetrievalTrace],
    evidence_history: list[EvidenceDecision],
) -> dict[str, Any]:
    final = finalize(state)
    search = _search_output(traces, evidence_history)
    search_performed = search["search_count"] > 0
    if not search_performed:
        retrieval_status = "NOT_SEARCHED"
    elif search["readable_page_count"] > 0 and search["verified_quote_count"] > 0:
        retrieval_status = "RETRIEVAL_COMPLETE"
    elif search["readable_page_count"] > 0:
        retrieval_status = "EVIDENCE_INCOMPLETE"
    elif search["page_open_attempt_count"] > 0:
        retrieval_status = "PAGE_OPEN_FAILURE"
    else:
        retrieval_status = "SEARCH_FAILURE"
    return {
        **final,
        "search": search,
        "search_performed": search_performed,
        "retrieval_status": retrieval_status,
        "state": jsonable(state),
        "base_ir": base_ir,
        "current_ir": current_ir,
    }


def run_case(
    public_value: PublicCase | dict[str, Any],
    output_schema: dict[str, Any],
    services: PipelineServices,
) -> dict[str, Any]:
    """Execute one auditable state trajectory for one public case.

    Order: initial model/solve -> two-way information audit -> impact probes ->
    one active gap -> authorized retrieval -> evidence route -> transactional
    Patch/re-solve -> re-probe -> terminal closure or ABSTAIN.
    """

    public = _public_case(public_value)
    initial = services.initial_modeler(public)
    current_ir, base_capture = solve_initial(initial.model_ir, output_schema)
    base_ir = copy.deepcopy(current_ir)
    state = initialize_state(public, initial, current_ir, base_capture)
    traces: list[RetrievalTrace] = []
    evidence_history: list[EvidenceDecision] = []
    if state.information_audit_failure is not None:
        return _finish_case(state, base_ir, current_ir, traces, evidence_history)
    if any(gap.target_binding_status == TargetBindingStatus.UNBOUND for gap in state.gaps):
        return _finish_case(state, base_ir, current_ir, traces, evidence_history)

    gap_variants = variants_by_gap(state, initial.candidate_gaps, current_ir)
    state = probe_all_gaps(
        state,
        current_ir,
        gap_variants,
        output_schema,
        public.prompt_zh,
    )
    while True:
        gap_id = select_next_gap(state)
        if gap_id is None:
            return _finish_case(state, base_ir, current_ir, traces, evidence_history)

        decision = authorize_search(state, gap_id)
        if not decision.authorized:
            state = close_or_abstain(state, gap_id, decision.reason)
            continue
        state = apply_state_update(state, StateUpdate.search_authorized(gap_id))
        trace = search_round(state, gap_id, decision.query or "", services.searcher)
        if not trace.query_attempted:
            state = mark_unresolved_abstain(state, gap_id, "query was not attempted")
            continue
        traces.append(trace)
        state = record_search_round(state, gap_id, trace)
        proposed = services.evidence_proposer(public, state, gap_id, trace, current_ir)
        evidence = assess_evidence(proposed, state, gap_id, trace, public.prompt_zh, current_ir)
        state = apply_state_update(
            state,
            StateUpdate.evidence_observed(gap_id, jsonable(evidence.evidence_cards)),
        )
        evidence_history.append(evidence)
        route = route_evidence(evidence, state.search_budget_left)

        if route == EvidenceRoute.SEARCH_AGAIN:
            state = apply_state_update(state, StateUpdate.search_again(gap_id, evidence.next_query or ""))
            continue
        if route == EvidenceRoute.RETAIN:
            state = apply_state_update(
                state,
                StateUpdate.retain(
                    gap_id,
                    evidence_payload(evidence),
                    evidence.admission == Admission.ALREADY_MODELED,
                ),
            )
            continue
        if route == EvidenceRoute.PATCH:
            state = apply_state_update(state, StateUpdate.patch_ready(gap_id, evidence_payload(evidence)))
            try:
                if evidence.patch_plan is None:
                    raise PatchValidationError("ADMIT_PATCH lacks PatchPlan")
                bundle = expand_patch_plan(state, current_ir, gap_id, evidence.patch_plan)
                candidate_ir, capture = apply_patch_and_solve(current_ir, bundle, output_schema)
                state, current_ir = record_solve_delta(
                    state, gap_id, current_ir, candidate_ir, capture, bundle
                )
                if next(row for row in state.gaps if row.gap_id == gap_id).state == GapState.CLOSED_PATCH:
                    state = probe_all_gaps(
                        state,
                        current_ir,
                        gap_variants,
                        output_schema,
                        public.prompt_zh,
                    )
            except (PatchValidationError, IRValidationError, SolverError) as exc:
                state = mark_unresolved_abstain(state, gap_id, f"{type(exc).__name__}: {exc}")
            continue
        state = mark_unresolved_abstain(state, gap_id, evidence.reason)
