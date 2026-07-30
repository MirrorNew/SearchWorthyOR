# Implementation contract

## Frozen acceptance contract

1. Exactly 100 tasks and 100 unique `base_id` values.
2. Exactly 80 `fresh-private` and 20 `real-web` tasks.
3. Ten OR families with ten tasks each; each family has eight private and two web tasks.
4. Four patch classes with 25 tasks each:
   - `eligibility_domain`
   - `temporal_coupling`
   - `conditional_auxiliary`
   - `quota_risk_service_objective`
5. Every base and patched model is single-objective and reaches `OPTIMAL` in Gurobi and COPT.
6. Canonical IR, solver status, objective, projected action, residual, and integrality checks agree within the registered tolerance.
7. A structural typed patch is non-empty and changes the canonical model hash.
8. Complete enumerated epsilon-optimal projected action sets satisfy
   `A0_epsilon ∩ A1_epsilon = ∅`.
9. Public prompts contain no source ID, policy text, patch label, solver code, objective value, or reference answer.
10. Every source has an applicability passport and a frozen content hash. Private tasks have one applicable document and three metadata/semantic distractors.
11. Two independent reviews plus adjudication are present. The release gate computes agreement from the recorded blind labels and requires at least 0.8.
12. All released files are hashed in `manifest.json`.

## Canonical model

The first release intentionally uses compact binary MILPs so that each result has three independent numerical certificates:

- Gurobi solve;
- COPT solve;
- exhaustive enumeration of every binary assignment.

Each IR contains one linear objective, typed variables, linear constraints, and a pre-registered action projection. The 100 bases are independently authored compact instances with unique structural fingerprints. The reviewed NLP4LP/MAMO records are background inspiration only: no source formulation, reference answer, reference code, or claimed source correspondence is inherited.

## Data build order

1. Build and audit the 100-source candidate pool.
2. Build balanced evidence blueprints.
3. Fetch and freeze 20 official HTTPS responses; save exact raw bytes, response metadata, separate raw/metadata hashes, and verify every ordered support excerpt in normalized text extracted from the exact HTML/XML/PDF response.
4. Freeze base IR and base hashes.
5. Generate private evidence documents and commitments after each base hash exists.
6. Apply typed patches only after evidence binding.
7. Solve both worlds with both solvers and enumerate all projected optimal actions.
8. Write public/private/model artifacts.
9. Run two fresh blind reviews, merge/adjudicate, compute all file hashes, and run the independent release gate.

## Non-claims

- The 20 public-web tasks are `E?`, not universally proven no-memory tasks.
- Synthetic private policies are benchmark evidence, not statements about real organizations.
- Adapted compact bases are not claimed to be untouched reproductions of the source datasets.
- A passport's `issued_at`, legal-rule date, page-version date, application window, HTTP fetch time, and `verified_as_of` are distinct semantics. Compatibility intervals state their kind and are not silently relabeled as legal effective dates.
- Passing the release gate does not evaluate any search Agent.
