# SearchWorthyOR-100 release-gate contract

`scripts/run_release_gate.py` is the only release verdict. Every check below is
mandatory and fail-closed; adding fields does not waive a required field or
invariant.

## Invocation and result

```powershell
python scripts/run_release_gate.py --root .
python scripts/run_release_gate.py --root . --json
```

Exit code `0` means every gate passed. Exit code `1` means release is blocked.
The scripts do not rewrite data, repair hashes, or silently drop bad rows.

## Frozen population contract

- Exactly 100 public tasks and 100 gold rows with identical ID sets.
- Exactly 100 unique `base_id` values. A task's base and patched worlds share
  that same `base_id`; a base may not be reused by another task or cross a
  declared split.
- Evidence modes: `fresh-private` 80, `real-web` 20.
- Each family has 10 tasks, including 8 private and 2 web tasks:
  `routing_transport`, `scheduling_workforce`, `production_capacity`,
  `assignment_matching`, `facility_network`, `inventory_supply_chain`,
  `energy_environment`, `healthcare_resources`, `finance_portfolio`, and
  `telecom_service`.
- Patch classes: `eligibility_domain`, `temporal_coupling`,
  `conditional_auxiliary`, and `quota_risk_service_objective`, 25 each.

The manifest repeats the frozen counts through `expected_counts` or
`required_counts`; changing the manifest cannot change the validator's
hard-coded allowlists or observed-distribution checks.

## Required row interfaces

`public/tasks_zh.jsonl` requires:

```json
{"id":"SWOR001","problem_zh":"..."}
```

`base_id` is intentionally private and is read from gold. The public row must
not contain source IDs/text, evidence mode, family,
patch labels, model hashes, typed patches, solver output, acceptable actions,
objective values, reference answers, or other gold fields.

`private/evidence_corpus.jsonl` requires:

```json
{
  "id":"EVID-SWOR-001-A",
  "source_kind":"fresh-private",
  "content":"...",
  "content_sha256":"<sha256 of exact UTF-8 content>",
  "source_passport":{},
  "applicability":{
    "gold_status_exposed":false,
    "predicate_fields":[
      "issuer_authority","effective_interval","jurisdiction",
      "subject_scope","exception_state"
    ]
  }
}
```

The retrieval corpus never exposes role or applicability gold. Roles are frozen
only in each gold row's four-way `applicability.comparison`. Private bundles
contain `applicable`, `old_version`, `wrong_jurisdiction`, `wrong_entity`;
web bundles replace the last role with `non_authoritative`. The gate verifies
the underlying passport actually exhibits the declared failure.

`private/gold.jsonl` requires:

```json
{
  "id":"SWOR-001",
  "base_id":"BASE-001",
  "family":"routing_transport",
  "evidence_mode":"fresh-private",
  "patch_class":"eligibility_domain",
  "base_audit":{},
  "source_passport":{},
  "applicability":{},
  "evidence_ids":["EVID-SWOR-001-A"],
  "typed_patch":{},
  "model_hashes":{},
  "action_projection":{},
  "solver_results":{},
  "decision_certificate":{},
  "reviews":[],
  "adjudication":{}
}
```

## Evidence and applicability passport

An applied `source_passport` has non-empty `authority`, `availability`,
`issuer`, `jurisdiction`, `subject_scope`, `version`, ISO-8601 `issued_at` and
`effective_from`, nullable ISO-8601 `effective_to`, the evidence
`content_sha256`, and `authoritative: true`. Private passports additionally
carry `generated_after_base_freeze: true` and `base_freeze_sha256`. Web
passports carry an HTTPS `url`, actual-GET `fetched_at`, `verified_as_of`,
`raw_path`, `raw_content_sha256`, `snapshot_sha256_kind:
exact_http_response_bytes`, and a separate `fetch_metadata_sha256`.
`private/web_snapshots/raw/` stores the exact official response bytes, while
`private/web_snapshots/fetch_manifest.jsonl` stores status, final URL, selected
response headers and metadata hashes. A serialized metadata object may never be
presented as a webpage snapshot hash. eCFR evidence uses the decision-date
versioner API rather than `/current/` pages. Each web claim records an ordered
`operative_support_excerpts` set. Every fragment must be recoverable from
normalized text extracted from the exact frozen response; the normalization
contract explicitly records HTML entity decoding, Unicode quote/dash folding,
whitespace collapse, and case folding. PDF sources are verified by text
extraction from the frozen PDF bytes.

The passport also records `issued_at_kind`, `effective_from_basis`, and
`effective_interval_kind`. These distinguish a legal effective/compliance
date, a program application window, an exact point-in-time edition, and a
verified page-version lower bound. `fetched_at` and `verified_as_of` are never
substitutes for legal or program dates.

Gold applicability records `status: pass`, `authority_valid`,
`jurisdiction_match`, `subject_scope_match`, `effective_at_decision`,
`exception_inactive_or_resolved`, `unique_applicable_source`, `decision_time`,
`selected_evidence_id`, and the four-document `comparison`. The gate recomputes
the effective interval and distractor mismatches; copied `true` booleans cannot
make a future, expired, wrong-jurisdiction, wrong-subject, or non-authoritative
source pass. Gold's passport must be an exact subset of the selected corpus
passport.

## Single objective, models, and hashes

`base_audit` requires:

- `single_objective: true` (and `objective_count: 1` when present);
- an objective fingerprint in the audit or decision certificate, subsequently
  checked against both IR files;
- `historical_answer_used_as_gold: false` and
  `historical_code_used_as_gold: false` (the legacy aliases are accepted).

`model_hashes.base` and `model_hashes.patched` (aliases `base_ir` and
`patched_ir` are accepted) each contain `path`, raw-file `sha256`, and
parsed-JSON `canonical_sha256`. Paths must remain under `models/`. Each
referenced artifact is UTF-8 JSON with the task
`base_id`, the correct `world`, one linear `objective`, `sense` (`min`/`max`),
and a non-empty `action_projection`. The two raw file hashes must differ.
Base and patched objective fingerprints and action projections must be
identical.

### Independent structural-template and provenance gate

The release gate also constructs a signed variable-factor bipartite graph from
every base canonical IR. Variable names, constraint names, coefficient
magnitudes, and row/column order are ignored. The graph retains:

- every nonzero variable-constraint and variable-objective edge, including its
  coefficient sign;
- constraint sense and RHS sign category;
- objective direction and constant sign category;
- variable type, lower/upper-bound sign categories, fixed/range status, and
  whether the variable belongs to the action projection or is auxiliary.

An isomorphism-invariant refinement fingerprint first identifies candidate
collisions. Every collision is then confirmed by an exact colored signed-graph
isomorphism check. Confirmed collisions are reported both over the full
dataset (`structure.template_collision_all`) and within each declared OR
family (`structure.template_collision_family`), and either condition blocks
release. Byte-distinct or differently named model files therefore do not
evade the no-template-reuse requirement.

The same independent gate cross-checks `base_audit` against
`staging/base_candidates.jsonl`. A `new_compact_adaptation` cannot be labeled
`unchanged_pass`, and a gold source certification cannot rely on a staging
candidate that remains `selected_for_manual_review` (or any other
non-certified state). Matching source hashes are required.

Action projections must be unique ordered variable lists and must match across
base IR, patched IR, and gold. A variable introduced only by the patch is an
auxiliary variable and may not enter the pre-registered action projection.
Both worlds must contain at most 20 variables, all binary, so that independent
complete enumeration remains executable rather than merely asserted.

### Duplicate, template, and metadata leakage attacks

Exact normalized public/evidence duplicates and byte-identical model artifacts
are rejected. The duplicate gate additionally removes task IDs, entities,
jurisdictions, dates, numbers and gold claims, then compares character 5-gram
Jaccard similarity. Applicable private policy documents fail at similarity
`>= 0.90`; public problem statements fail at similarity `>= 0.95`. Intentional
near-miss distractors inside one retrieval bundle are not mistaken for 100
independent applicable documents.

Metadata decoders try to recover `patch_class` using only non-semantic public
metadata. Features cover ID and physical-row residues, dates, jurisdictions,
the retrieval interface, entity signatures, dense ranks, rank differences,
quantile buckets and contiguous ordinal blocks for sizes 2--20. Problem text is
excluded. Hard-gated attacks are: every registered single feature under fixed
five-fold decoding; every registered feature and every pair/triple of the base
metadata features under deterministic LOO decoding; the maximum per-feature
P95 across 200 deterministic hash-fold splits; the registered all-feature
categorical decoder; a fold-fitted all-feature decision tree; cross-group quota
completion; and, when at least two public interfaces exist, an interface-level
least-frequent-label decoder. The four-class random baseline is `0.25`; any
hard-gated statistic at or above `0.35` blocks release.

The user-mandated global
`25×4` patch histogram is also excluded from the transductive threat model:
allowing a decoder to see the other 99 private gold labels and use that frozen
global quota would make every contract-compliant dataset deterministically
decodable. Subgroup quotas not mandated by the contract remain release-blocking.

All release files, including review and report artifacts, except
`manifest.json` itself must be listed in
`manifest.files` with their SHA-256. Extra unhashed files and stale manifest
entries both fail. Python bytecode/cache files are excluded.

## Typed structural patch

`typed_patch` contains non-empty `ops`, a non-empty `minimality_check`,
`pure_numeric_parameter_fill: false`, `structural: true`, and
`base_model_hash` / `patched_model_hash` equal to the two raw model-file hashes.
Every op records `op`, `slot_type`, `evidence_claim_id`, `model_slot_id`,
`code_region_id`, `before_expression`, and `after_expression`.

The gate recomputes raw and canonical hashes and verifies the before/after
expressions occur in the corresponding IR. Identical expressions, equal
hashes, empty ops, and changes whose only differing tokens are numeric are
rejected.
An objective/quota/risk/service patch must therefore change a typed term,
scope, condition, variable/index structure, or priority—not merely replace one
number. The `before_expression` must occur in the base IR and the
`after_expression` in the patched IR.

## Solver and decision certificate

The full `models/<id>/solver_results.json` contains `base` and `patched`. Each
world has:

```json
{
  "exact_enumeration":{
    "status":"OPTIMAL",
    "objective":0.0,
    "optimal_actions":[[0,1]],
    "complete":true
  },
  "gurobi":{
    "solver":"gurobi",
    "version":"...",
    "status":"OPTIMAL",
    "objective":0.0,
    "projected_action":[0,1],
    "assignment":{"x":0.0,"y":1.0},
    "max_constraint_violation":0.0,
    "integrality_violation":0.0,
    "bound_violation":0.0
  },
  "copt":{},
  "checks":{
    "all_optimal":true,
    "objectives_agree":true,
    "solver_actions_in_exact_set":true,
    "residuals_pass":true,
    "integrality_pass":true,
    "passed":true
  }
}
```

The gate requires both solvers and exact enumeration to be optimal. It
independently enumerates every binary assignment from each canonical IR,
recomputes the objective, action projection, constraint/bound residuals and
integrality from each solver assignment, and then compares these results with
the recorded artifacts. A forged `complete: true` flag is therefore
insufficient. Gurobi and COPT need not choose the same incumbent when multiple
optima exist, but both incumbents must belong to the independently recomputed
complete optimal-action set.

Gold's compact solver summary is arranged as
`solver_results.<gurobi|copt>.<base|patched>` and is cross-checked against the
full artifact. `decision_certificate` contains:

```json
{
  "method":"complete_binary_enumeration",
  "worlds":{
    "base":{
      "action_set_complete":true,
      "objective_fingerprint":"<sha256>",
      "optimal_actions":[[0,1]]
    },
    "patched":{
      "action_set_complete":true,
      "objective_fingerprint":"<same sha256>",
      "optimal_actions":[[1,0]]
    }
  },
  "intersection":[],
  "intersection_empty":true,
  "passed":true
}
```

The gate canonicalizes the two action sets, recomputes their intersection, and
compares both sets with exact enumeration. Comparing only Gurobi/COPT
incumbents is never a completeness certificate. A changed objective is also
invalid: a task is retained only when the same objective is used and the full
projected acceptable-action sets are disjoint.

## Reviews and unresolved states

Each gold row has at least two reviews with distinct `reviewer` (or
`reviewer_id`), `blind_packet: true` (or `blind: true`), and an
`accept`/`reject` label. The expanded five-field form (`applicability`,
`patch_valid`, `solver_valid`, `certificate_valid`, `decision`) is also
accepted. Pairwise exact agreement over the recorded blind labels is
recomputed over the dataset and must be at least `0.8`.

`adjudication.status` is `resolved`, `unresolved` is explicitly `false`, and
`label` (or `final_decision`) is accept/approved. Pending/TBD/unknown/unresolved
markers and a non-empty `manifest.unresolved` block release.

The release merger accepts only the compact frozen packet with exactly
`id`, `label`, `reviewer_id`, `blind_packet`, `issues`, and `checks`.
`checks` must contain exactly `base_semantics`, `source_applicability`,
`patch_semantics`, `solver_dual`, `certificate_complete`, `anti_fogging`, and
`metadata_leakage`. An accept has no issues and all checks true; a reject has
at least one issue and at least one false check.

## Duplicate and leakage audit

The independent audit rejects:

- duplicate task IDs, base IDs, NFKC/whitespace-normalized prompts, evidence
  IDs/content/source-version passports, or byte-identical model artifacts;
- any base shared across declared splits;
- private-only keys or labels in public rows;
- source IDs, URIs, titles, full policy text, or sufficiently long canonical
  gold actions reproduced in the public tasks.

The metadata decoder includes public ID residues, dates, jurisdictions,
retrieval-interface metadata, entity signatures, physical release-row residues
modulo 2--16, row quartile/decile, dense-rank residues, rank-difference
features, quantile buckets 2--20, contiguous ordinal blocks 2--20, and combined
categorical attacks. Hash-shuffling IDs without also shuffling physical JSONL
order is therefore not sufficient. Every registered feature is tested by
deterministic leave-one-out majority decoding and 200 deterministic hash-based
five-fold splits. Single-feature fixed-fold maxima, single/pair/triple LOO
maxima, and maximum per-feature stress P95 are release-blocking alongside the
fold-fitted all-feature, cross-group quota, and multi-interface minority
attacks described above. Stress maxima and threshold-exceedance counts remain
reported for transparency, while the pre-registered P95 is the stress gate
statistic.

These checks protect release hygiene; they do not by themselves establish
causal search benefit or model-independent unknowability for the `real-web`
track.
