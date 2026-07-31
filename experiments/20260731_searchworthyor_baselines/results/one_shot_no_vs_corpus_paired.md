# Full-run paired comparison

Tasks: 100; bootstrap samples: 20000; seed: 20260731. Missing or failed tasks count as false.

Statistical pairing does not make differently defined metrics semantically comparable. In particular, frozen-corpus exact document ID and live-web exact Gold URL measure identity, not authoritative-source semantic equivalence.

## Coverage

| Run | Submitted | Expected | Active failures |
|---|---:|---:|---:|
| no_search | 100 | 100 | 0 |
| corpus_search | 99 | 100 | 1 |

## End-to-end model usage

Means are computed over submissions with recorded usage; the parenthesized value is that usage count. Accuracy denominators remain the preregistered task count above.

| Run | Input tokens | Output tokens | Reasoning tokens | Model calls | Search calls | Model wall seconds |
|---|---:|---:|---:|---:|---:|---:|
| no_search | 15891.90 (100) | 3499.29 (100) | 1172.21 (100) | 1.00 (100) | 0.00 (100) | 74.73 (100) |
| corpus_search | 17771.39 (99) | 4770.68 (99) | 2112.40 (99) | 1.00 (99) | 1.00 (99) | 105.02 (99) |

## Per-run rates and task-bootstrap 95% CI

| Run | Metric | Success | Rate | 95% CI |
|---|---|---:|---:|---:|
| no_search | base_model_success | 100/100 | 1.000 | [1.000, 1.000] |
| no_search | generated_code_ir_consistent | 100/100 | 1.000 | [1.000, 1.000] |
| no_search | evidence_selected | 0/100 | 0.000 | [0.000, 0.000] |
| no_search | model_structurally_changed | 0/100 | 0.000 | [0.000, 0.000] |
| no_search | decision_model_equivalent | 0/100 | 0.000 | [0.000, 0.000] |
| no_search | decision_e2e | 0/100 | 0.000 | [0.000, 0.000] |
| no_search | semantic_e2e | 0/100 | 0.000 | [0.000, 0.000] |
| no_search | strict_e2e | 0/100 | 0.000 | [0.000, 0.000] |
| corpus_search | base_model_success | 99/100 | 0.990 | [0.970, 1.000] |
| corpus_search | generated_code_ir_consistent | 99/100 | 0.990 | [0.970, 1.000] |
| corpus_search | evidence_selected | 97/100 | 0.970 | [0.930, 1.000] |
| corpus_search | model_structurally_changed | 98/100 | 0.980 | [0.950, 1.000] |
| corpus_search | decision_model_equivalent | 95/100 | 0.950 | [0.900, 0.990] |
| corpus_search | decision_e2e | 89/100 | 0.890 | [0.820, 0.950] |
| corpus_search | semantic_e2e | 47/100 | 0.470 | [0.370, 0.570] |
| corpus_search | strict_e2e | 0/100 | 0.000 | [0.000, 0.000] |

## Paired comparisons

`Difference` is left minus right. McNemar uses an exact two-sided binomial test over discordant tasks.

| Left | Right | Metric | Difference | 95% CI | Left only | Right only | Exact p |
|---|---|---|---:|---:|---:|---:|---:|
| no_search | corpus_search | base_model_success | 0.010 | [0.000, 0.030] | 1 | 0 | 1 |
| no_search | corpus_search | generated_code_ir_consistent | 0.010 | [0.000, 0.030] | 1 | 0 | 1 |
| no_search | corpus_search | evidence_selected | -0.970 | [-1.000, -0.930] | 0 | 97 | 1.262e-29 |
| no_search | corpus_search | model_structurally_changed | -0.980 | [-1.000, -0.950] | 0 | 98 | 6.311e-30 |
| no_search | corpus_search | decision_model_equivalent | -0.950 | [-0.990, -0.900] | 0 | 95 | 5.049e-29 |
| no_search | corpus_search | decision_e2e | -0.890 | [-0.950, -0.830] | 0 | 89 | 3.231e-27 |
| no_search | corpus_search | semantic_e2e | -0.470 | [-0.570, -0.370] | 0 | 47 | 1.421e-14 |
| no_search | corpus_search | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
