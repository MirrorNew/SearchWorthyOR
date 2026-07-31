# GPT-5.6-sol high one-shot frozen corpus full-run summary

- Expected: 100
- Submitted: 99
- Active failures: 1
- Recovered infrastructure failures: 2
- Missing: 1

| Metric | Success / expected | Rate | Success / submitted | Rate |
|---|---:|---:|---:|---:|
| `reasoning_reported_high` | 99/100 | 99.0% | 99/99 | 100.0% |
| `reasoning_validated` | 0/100 | 0.0% | 0/99 | 0.0% |
| `trace_complete` | 98/100 | 98.0% | 98/99 | 99.0% |
| `evidence_hit_at_1` | 36/100 | 36.0% | 36/99 | 36.4% |
| `evidence_hit_at_5` | 97/100 | 97.0% | 97/99 | 98.0% |
| `base_model_success` | 99/100 | 99.0% | 99/99 | 100.0% |
| `evidence_selected` | 97/100 | 97.0% | 97/99 | 98.0% |
| `claim_evidence_consistent` | 92/100 | 92.0% | 92/99 | 92.9% |
| `applicability_valid` | 99/100 | 99.0% | 99/99 | 100.0% |
| `model_structurally_changed` | 98/100 | 98.0% | 98/99 | 99.0% |
| `generated_code_ir_consistent` | 99/100 | 99.0% | 99/99 | 100.0% |
| `projected_feasible_set_match` | 95/100 | 95.0% | 95/99 | 96.0% |
| `optimal_action_set_match` | 95/100 | 95.0% | 95/99 | 96.0% |
| `decision_changed_from_base` | 98/100 | 98.0% | 98/99 | 99.0% |
| `outcome_match` | 96/100 | 96.0% | 96/99 | 97.0% |
| `model_success` | 96/100 | 96.0% | 96/99 | 97.0% |
| `semantic_e2e` | 47/100 | 47.0% | 47/99 | 47.5% |
| `decision_model_equivalent` | 95/100 | 95.0% | 95/99 | 96.0% |
| `decision_e2e` | 89/100 | 89.0% | 89/99 | 89.9% |
| `strict_e2e` | 0/100 | 0.0% | 0/99 | 0.0% |
| `evidence_driven_model_change` | 95/100 | 95.0% | 95/99 | 96.0% |

## Process diagnostics

| Failure category | Count / submitted |
|---|---:|
| `base_model_failure` | 0/99 |
| `generated_code_ir_inconsistent` | 0/99 |
| `model_change_missing` | 1/99 |
| `decision_model_mismatch` | 4/99 |
| `final_decision_e2e_failure` | 10/99 |
| `evidence_selection_failure` | 2/99 |
| `claim_evidence_inconsistent` | 7/99 |
| `applicability_invalid` | 0/99 |
| `representation_mismatch_despite_decision_equivalence` | 48/99 |
