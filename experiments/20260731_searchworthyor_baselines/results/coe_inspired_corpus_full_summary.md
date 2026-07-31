# CoE-inspired corpus full full-run summary

- Expected: 100
- Submitted: 13
- Active failures: 87
- Recovered infrastructure failures: 0
- Missing: 87

| Metric | Success / expected | Rate | Success / submitted | Rate |
|---|---:|---:|---:|---:|
| `reasoning_reported_high` | 13/100 | 13.0% | 13/13 | 100.0% |
| `reasoning_validated` | 0/100 | 0.0% | 0/13 | 0.0% |
| `trace_complete` | 12/100 | 12.0% | 12/13 | 92.3% |
| `evidence_hit_at_1` | 4/100 | 4.0% | 4/13 | 30.8% |
| `evidence_hit_at_5` | 12/100 | 12.0% | 12/13 | 92.3% |
| `base_model_success` | 13/100 | 13.0% | 13/13 | 100.0% |
| `evidence_selected` | 12/100 | 12.0% | 12/13 | 92.3% |
| `claim_evidence_consistent` | 8/100 | 8.0% | 8/13 | 61.5% |
| `applicability_valid` | 12/100 | 12.0% | 12/13 | 92.3% |
| `model_structurally_changed` | 12/100 | 12.0% | 12/13 | 92.3% |
| `generated_code_ir_consistent` | 13/100 | 13.0% | 13/13 | 100.0% |
| `projected_feasible_set_match` | 12/100 | 12.0% | 12/13 | 92.3% |
| `optimal_action_set_match` | 12/100 | 12.0% | 12/13 | 92.3% |
| `decision_changed_from_base` | 12/100 | 12.0% | 12/13 | 92.3% |
| `outcome_match` | 12/100 | 12.0% | 12/13 | 92.3% |
| `model_success` | 12/100 | 12.0% | 12/13 | 92.3% |
| `semantic_e2e` | 4/100 | 4.0% | 4/13 | 30.8% |
| `decision_model_equivalent` | 12/100 | 12.0% | 12/13 | 92.3% |
| `decision_e2e` | 8/100 | 8.0% | 8/13 | 61.5% |
| `strict_e2e` | 0/100 | 0.0% | 0/13 | 0.0% |
| `evidence_driven_model_change` | 12/100 | 12.0% | 12/13 | 92.3% |

## Process diagnostics

| Failure category | Count / submitted |
|---|---:|
| `base_model_failure` | 0/13 |
| `generated_code_ir_inconsistent` | 0/13 |
| `model_change_missing` | 1/13 |
| `decision_model_mismatch` | 1/13 |
| `final_decision_e2e_failure` | 5/13 |
| `evidence_selection_failure` | 1/13 |
| `claim_evidence_inconsistent` | 5/13 |
| `applicability_invalid` | 1/13 |
| `representation_mismatch_despite_decision_equivalence` | 8/13 |

## Active pipeline failure taxonomy

| Cause | Count |
|---|---:|
| `cli_process_failure` | 2 |
| `forbidden_mcp_tool_call` | 85 |

| Stage | Count |
|---|---:|
| `CodeReviewer` | 24 |
| `ModelingExpert` | 1 |
| `ParameterExtractor` | 16 |
| `ProgrammingExpert` | 44 |
| `TerminologyInterpreter` | 2 |
