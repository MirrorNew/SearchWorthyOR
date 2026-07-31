# Full-run paired comparison

Tasks: 20; bootstrap samples: 20000; seed: 20260731. Missing or failed tasks count as false.

Statistical pairing does not make differently defined metrics semantically comparable. In particular, frozen-corpus exact document ID and live-web exact Gold URL measure identity, not authoritative-source semantic equivalence.

## Coverage

| Run | Submitted | Expected | Active failures |
|---|---:|---:|---:|
| no_search | 20 | 20 | 0 |
| frozen_snapshot | 20 | 20 | 0 |
| live_web | 20 | 20 | 0 |

## End-to-end model usage

Means are computed over submissions with recorded usage; the parenthesized value is that usage count. Accuracy denominators remain the preregistered task count above.

| Run | Input tokens | Output tokens | Reasoning tokens | Model calls | Search calls | Model wall seconds |
|---|---:|---:|---:|---:|---:|---:|
| no_search | 15965.60 (20) | 3322.10 (20) | 1170.85 (20) | 1.00 (20) | 0.00 (20) | 71.75 (20) |
| frozen_snapshot | 18256.30 (20) | 5758.65 (20) | 3066.40 (20) | 1.00 (20) | 1.00 (20) | 130.33 (20) |
| live_web | 475785.90 (20) | 8726.65 (20) | 4638.05 (20) | 1.00 (20) | 8.00 (20) | 239.16 (20) |

## Per-run rates and task-bootstrap 95% CI

| Run | Metric | Success | Rate | 95% CI |
|---|---|---:|---:|---:|
| no_search | base_model_success | 20/20 | 1.000 | [1.000, 1.000] |
| no_search | generated_code_ir_consistent | 20/20 | 1.000 | [1.000, 1.000] |
| no_search | evidence_selected | 0/20 | 0.000 | [0.000, 0.000] |
| no_search | model_structurally_changed | 0/20 | 0.000 | [0.000, 0.000] |
| no_search | decision_model_equivalent | 0/20 | 0.000 | [0.000, 0.000] |
| no_search | decision_e2e | 0/20 | 0.000 | [0.000, 0.000] |
| no_search | semantic_e2e | 0/20 | 0.000 | [0.000, 0.000] |
| no_search | strict_e2e | 0/20 | 0.000 | [0.000, 0.000] |
| frozen_snapshot | base_model_success | 20/20 | 1.000 | [1.000, 1.000] |
| frozen_snapshot | generated_code_ir_consistent | 20/20 | 1.000 | [1.000, 1.000] |
| frozen_snapshot | evidence_selected | 18/20 | 0.900 | [0.750, 1.000] |
| frozen_snapshot | model_structurally_changed | 19/20 | 0.950 | [0.850, 1.000] |
| frozen_snapshot | decision_model_equivalent | 16/20 | 0.800 | [0.600, 0.950] |
| frozen_snapshot | decision_e2e | 16/20 | 0.800 | [0.600, 0.950] |
| frozen_snapshot | semantic_e2e | 9/20 | 0.450 | [0.250, 0.650] |
| frozen_snapshot | strict_e2e | 0/20 | 0.000 | [0.000, 0.000] |
| live_web | base_model_success | 20/20 | 1.000 | [1.000, 1.000] |
| live_web | generated_code_ir_consistent | 20/20 | 1.000 | [1.000, 1.000] |
| live_web | evidence_selected | 3/20 | 0.150 | [0.000, 0.300] |
| live_web | model_structurally_changed | 19/20 | 0.950 | [0.850, 1.000] |
| live_web | decision_model_equivalent | 16/20 | 0.800 | [0.600, 0.950] |
| live_web | decision_e2e | 3/20 | 0.150 | [0.000, 0.300] |
| live_web | semantic_e2e | 2/20 | 0.100 | [0.000, 0.250] |
| live_web | strict_e2e | 0/20 | 0.000 | [0.000, 0.000] |

## Paired comparisons

`Difference` is left minus right. McNemar uses an exact two-sided binomial test over discordant tasks.

| Left | Right | Metric | Difference | 95% CI | Left only | Right only | Exact p |
|---|---|---|---:|---:|---:|---:|---:|
| no_search | frozen_snapshot | base_model_success | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| no_search | frozen_snapshot | generated_code_ir_consistent | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| no_search | frozen_snapshot | evidence_selected | -0.900 | [-1.000, -0.750] | 0 | 18 | 7.629e-06 |
| no_search | frozen_snapshot | model_structurally_changed | -0.950 | [-1.000, -0.850] | 0 | 19 | 3.815e-06 |
| no_search | frozen_snapshot | decision_model_equivalent | -0.800 | [-0.950, -0.600] | 0 | 16 | 3.052e-05 |
| no_search | frozen_snapshot | decision_e2e | -0.800 | [-0.950, -0.600] | 0 | 16 | 3.052e-05 |
| no_search | frozen_snapshot | semantic_e2e | -0.450 | [-0.650, -0.250] | 0 | 9 | 0.003906 |
| no_search | frozen_snapshot | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| no_search | live_web | base_model_success | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| no_search | live_web | generated_code_ir_consistent | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| no_search | live_web | evidence_selected | -0.150 | [-0.300, 0.000] | 0 | 3 | 0.25 |
| no_search | live_web | model_structurally_changed | -0.950 | [-1.000, -0.850] | 0 | 19 | 3.815e-06 |
| no_search | live_web | decision_model_equivalent | -0.800 | [-0.950, -0.600] | 0 | 16 | 3.052e-05 |
| no_search | live_web | decision_e2e | -0.150 | [-0.300, 0.000] | 0 | 3 | 0.25 |
| no_search | live_web | semantic_e2e | -0.100 | [-0.250, 0.000] | 0 | 2 | 0.5 |
| no_search | live_web | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| frozen_snapshot | live_web | base_model_success | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| frozen_snapshot | live_web | generated_code_ir_consistent | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| frozen_snapshot | live_web | evidence_selected | 0.750 | [0.500, 0.950] | 16 | 1 | 0.0002747 |
| frozen_snapshot | live_web | model_structurally_changed | 0.000 | [-0.150, 0.150] | 1 | 1 | 1 |
| frozen_snapshot | live_web | decision_model_equivalent | 0.000 | [-0.250, 0.250] | 3 | 3 | 1 |
| frozen_snapshot | live_web | decision_e2e | 0.650 | [0.400, 0.900] | 14 | 1 | 0.0009766 |
| frozen_snapshot | live_web | semantic_e2e | 0.350 | [0.150, 0.550] | 7 | 0 | 0.01562 |
| frozen_snapshot | live_web | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
