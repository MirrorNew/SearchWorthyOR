# OptiMiner training-free compatibility frozen corpus full-run summary

- Expected: 100
- Submitted: 92
- Active failures: 8
- Recovered infrastructure failures: 3
- Missing: 8

| Metric | Success / expected | Rate | Success / submitted | Rate |
|---|---:|---:|---:|---:|
| `reasoning_reported_high` | 92/100 | 92.0% | 92/92 | 100.0% |
| `reasoning_validated` | 0/100 | 0.0% | 0/92 | 0.0% |
| `trace_complete` | 92/100 | 92.0% | 92/92 | 100.0% |
| `evidence_hit_at_1` | 28/100 | 28.0% | 28/92 | 30.4% |
| `evidence_hit_at_5` | 89/100 | 89.0% | 89/92 | 96.7% |
| `base_model_success` | 92/100 | 92.0% | 92/92 | 100.0% |
| `evidence_selected` | 90/100 | 90.0% | 90/92 | 97.8% |
| `claim_evidence_consistent` | 77/100 | 77.0% | 77/92 | 83.7% |
| `applicability_valid` | 92/100 | 92.0% | 92/92 | 100.0% |
| `model_structurally_changed` | 92/100 | 92.0% | 92/92 | 100.0% |
| `generated_code_ir_consistent` | 92/100 | 92.0% | 92/92 | 100.0% |
| `projected_feasible_set_match` | 89/100 | 89.0% | 89/92 | 96.7% |
| `optimal_action_set_match` | 89/100 | 89.0% | 89/92 | 96.7% |
| `decision_changed_from_base` | 91/100 | 91.0% | 91/92 | 98.9% |
| `outcome_match` | 89/100 | 89.0% | 89/92 | 96.7% |
| `model_success` | 89/100 | 89.0% | 89/92 | 96.7% |
| `semantic_e2e` | 39/100 | 39.0% | 39/92 | 42.4% |
| `decision_model_equivalent` | 89/100 | 89.0% | 89/92 | 96.7% |
| `decision_e2e` | 72/100 | 72.0% | 72/92 | 78.3% |
| `strict_e2e` | 0/100 | 0.0% | 0/92 | 0.0% |
| `evidence_driven_model_change` | 87/100 | 87.0% | 87/92 | 94.6% |

## Process diagnostics

| Failure category | Count / submitted |
|---|---:|
| `base_model_failure` | 0/92 |
| `generated_code_ir_inconsistent` | 0/92 |
| `model_change_missing` | 0/92 |
| `decision_model_mismatch` | 3/92 |
| `final_decision_e2e_failure` | 20/92 |
| `evidence_selection_failure` | 2/92 |
| `claim_evidence_inconsistent` | 15/92 |
| `applicability_invalid` | 0/92 |
| `representation_mismatch_despite_decision_equivalence` | 50/92 |

## Active pipeline failure taxonomy

| Cause | Count |
|---|---:|
| `cli_process_failure` | 1 |
| `max_research_turns_without_final` | 7 |

| Stage | Count |
|---|---:|
| `Controller` | 8 |
