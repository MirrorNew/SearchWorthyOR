# OPTIMUS-inspired frozen-corpus full full-run summary

- Expected: 100
- Submitted: 100
- Active failures: 0
- Recovered infrastructure failures: 6
- Missing: 0

| Metric | Success / expected | Rate | Success / submitted | Rate |
|---|---:|---:|---:|---:|
| `reasoning_reported_high` | 100/100 | 100.0% | 100/100 | 100.0% |
| `reasoning_validated` | 0/100 | 0.0% | 0/100 | 0.0% |
| `trace_complete` | 98/100 | 98.0% | 98/100 | 98.0% |
| `evidence_hit_at_1` | 37/100 | 37.0% | 37/100 | 37.0% |
| `evidence_hit_at_5` | 98/100 | 98.0% | 98/100 | 98.0% |
| `base_model_success` | 100/100 | 100.0% | 100/100 | 100.0% |
| `evidence_selected` | 97/100 | 97.0% | 97/100 | 97.0% |
| `claim_evidence_consistent` | 90/100 | 90.0% | 90/100 | 90.0% |
| `applicability_valid` | 99/100 | 99.0% | 99/100 | 99.0% |
| `model_structurally_changed` | 98/100 | 98.0% | 98/100 | 98.0% |
| `generated_code_ir_consistent` | 100/100 | 100.0% | 100/100 | 100.0% |
| `projected_feasible_set_match` | 93/100 | 93.0% | 93/100 | 93.0% |
| `optimal_action_set_match` | 94/100 | 94.0% | 94/100 | 94.0% |
| `decision_changed_from_base` | 98/100 | 98.0% | 98/100 | 98.0% |
| `outcome_match` | 94/100 | 94.0% | 94/100 | 94.0% |
| `model_success` | 94/100 | 94.0% | 94/100 | 94.0% |
| `semantic_e2e` | 44/100 | 44.0% | 44/100 | 44.0% |
| `decision_model_equivalent` | 93/100 | 93.0% | 93/100 | 93.0% |
| `decision_e2e` | 84/100 | 84.0% | 84/100 | 84.0% |
| `strict_e2e` | 0/100 | 0.0% | 0/100 | 0.0% |
| `evidence_driven_model_change` | 93/100 | 93.0% | 93/100 | 93.0% |

## Process diagnostics

| Failure category | Count / submitted |
|---|---:|
| `base_model_failure` | 0/100 |
| `generated_code_ir_inconsistent` | 0/100 |
| `model_change_missing` | 2/100 |
| `decision_model_mismatch` | 7/100 |
| `final_decision_e2e_failure` | 16/100 |
| `evidence_selection_failure` | 3/100 |
| `claim_evidence_inconsistent` | 10/100 |
| `applicability_invalid` | 1/100 |
| `representation_mismatch_despite_decision_equivalence` | 49/100 |
