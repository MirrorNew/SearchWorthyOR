# Full-run paired comparison

Tasks: 100; bootstrap samples: 20000; seed: 20260731. Missing or failed tasks count as false.

Statistical pairing does not make differently defined metrics semantically comparable. In particular, frozen-corpus exact document ID and live-web exact Gold URL measure identity, not authoritative-source semantic equivalence.

## Coverage

| Run | Submitted | Expected | Active failures |
|---|---:|---:|---:|
| one_shot_frozen | 99 | 100 | 1 |
| optimus_inspired | 100 | 100 | 0 |

## End-to-end model usage

Means are computed over submissions with recorded usage; the parenthesized value is that usage count. Accuracy denominators remain the preregistered task count above.

| Run | Input tokens | Output tokens | Reasoning tokens | Model calls | Search calls | Model wall seconds |
|---|---:|---:|---:|---:|---:|---:|
| one_shot_frozen | 17771.39 (99) | 4770.68 (99) | 2112.40 (99) | 1.00 (99) | 1.00 (99) | 105.02 (99) |
| optimus_inspired | 86511.06 (100) | 8398.64 (100) | 3657.16 (100) | 4.00 (100) | 1.00 (100) | 200.74 (100) |

## Per-run rates and task-bootstrap 95% CI

| Run | Metric | Success | Rate | 95% CI |
|---|---|---:|---:|---:|
| one_shot_frozen | base_model_success | 99/100 | 0.990 | [0.970, 1.000] |
| one_shot_frozen | generated_code_ir_consistent | 99/100 | 0.990 | [0.970, 1.000] |
| one_shot_frozen | evidence_selected | 97/100 | 0.970 | [0.930, 1.000] |
| one_shot_frozen | model_structurally_changed | 98/100 | 0.980 | [0.950, 1.000] |
| one_shot_frozen | decision_model_equivalent | 95/100 | 0.950 | [0.900, 0.990] |
| one_shot_frozen | decision_e2e | 89/100 | 0.890 | [0.830, 0.950] |
| one_shot_frozen | semantic_e2e | 47/100 | 0.470 | [0.370, 0.570] |
| one_shot_frozen | strict_e2e | 0/100 | 0.000 | [0.000, 0.000] |
| optimus_inspired | base_model_success | 100/100 | 1.000 | [1.000, 1.000] |
| optimus_inspired | generated_code_ir_consistent | 100/100 | 1.000 | [1.000, 1.000] |
| optimus_inspired | evidence_selected | 97/100 | 0.970 | [0.930, 1.000] |
| optimus_inspired | model_structurally_changed | 98/100 | 0.980 | [0.950, 1.000] |
| optimus_inspired | decision_model_equivalent | 93/100 | 0.930 | [0.880, 0.980] |
| optimus_inspired | decision_e2e | 84/100 | 0.840 | [0.760, 0.910] |
| optimus_inspired | semantic_e2e | 44/100 | 0.440 | [0.350, 0.540] |
| optimus_inspired | strict_e2e | 0/100 | 0.000 | [0.000, 0.000] |

## Paired comparisons

`Difference` is left minus right. McNemar uses an exact two-sided binomial test over discordant tasks.

| Left | Right | Metric | Difference | 95% CI | Left only | Right only | Exact p |
|---|---|---|---:|---:|---:|---:|---:|
| one_shot_frozen | optimus_inspired | base_model_success | -0.010 | [-0.030, 0.000] | 0 | 1 | 1 |
| one_shot_frozen | optimus_inspired | generated_code_ir_consistent | -0.010 | [-0.030, 0.000] | 0 | 1 | 1 |
| one_shot_frozen | optimus_inspired | evidence_selected | 0.000 | [-0.030, 0.030] | 1 | 1 | 1 |
| one_shot_frozen | optimus_inspired | model_structurally_changed | 0.000 | [-0.030, 0.030] | 1 | 1 | 1 |
| one_shot_frozen | optimus_inspired | decision_model_equivalent | 0.020 | [-0.020, 0.060] | 3 | 1 | 0.625 |
| one_shot_frozen | optimus_inspired | decision_e2e | 0.050 | [-0.020, 0.120] | 9 | 4 | 0.2668 |
| one_shot_frozen | optimus_inspired | semantic_e2e | 0.030 | [-0.020, 0.080] | 5 | 2 | 0.4531 |
| one_shot_frozen | optimus_inspired | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
