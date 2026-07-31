# GPT-5.6-sol high one-shot live-web web20 full-run summary

- Expected: 20
- Submitted: 20
- Active failures: 0
- Recovered infrastructure failures: 1
- Missing: 0

| Metric | Success / expected | Rate | Success / submitted | Rate |
|---|---:|---:|---:|---:|
| `reasoning_reported_high` | 20/20 | 100.0% | 20/20 | 100.0% |
| `reasoning_validated` | 0/20 | 0.0% | 0/20 | 0.0% |
| `trace_complete` | 19/20 | 95.0% | 19/20 | 95.0% |
| `evidence_hit_at_1` | 0/20 | 0.0% | 0/20 | 0.0% |
| `evidence_hit_at_5` | 1/20 | 5.0% | 1/20 | 5.0% |
| `base_model_success` | 20/20 | 100.0% | 20/20 | 100.0% |
| `evidence_selected` | 3/20 | 15.0% | 3/20 | 15.0% |
| `claim_evidence_consistent` | 16/20 | 80.0% | 16/20 | 80.0% |
| `applicability_valid` | 19/20 | 95.0% | 19/20 | 95.0% |
| `model_structurally_changed` | 19/20 | 95.0% | 19/20 | 95.0% |
| `generated_code_ir_consistent` | 20/20 | 100.0% | 20/20 | 100.0% |
| `projected_feasible_set_match` | 16/20 | 80.0% | 16/20 | 80.0% |
| `optimal_action_set_match` | 16/20 | 80.0% | 16/20 | 80.0% |
| `decision_changed_from_base` | 19/20 | 95.0% | 19/20 | 95.0% |
| `outcome_match` | 16/20 | 80.0% | 16/20 | 80.0% |
| `model_success` | 16/20 | 80.0% | 16/20 | 80.0% |
| `semantic_e2e` | 2/20 | 10.0% | 2/20 | 10.0% |
| `decision_model_equivalent` | 16/20 | 80.0% | 16/20 | 80.0% |
| `decision_e2e` | 3/20 | 15.0% | 3/20 | 15.0% |
| `strict_e2e` | 0/20 | 0.0% | 0/20 | 0.0% |
| `evidence_driven_model_change` | 3/20 | 15.0% | 3/20 | 15.0% |

## Process diagnostics

| Failure category | Count / submitted |
|---|---:|
| `base_model_failure` | 0/20 |
| `generated_code_ir_inconsistent` | 0/20 |
| `model_change_missing` | 1/20 |
| `decision_model_mismatch` | 4/20 |
| `final_decision_e2e_failure` | 17/20 |
| `evidence_selection_failure` | 17/20 |
| `claim_evidence_inconsistent` | 4/20 |
| `applicability_invalid` | 1/20 |
| `representation_mismatch_despite_decision_equivalence` | 14/20 |
