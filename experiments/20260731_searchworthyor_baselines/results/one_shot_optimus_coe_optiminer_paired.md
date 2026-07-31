# Full-run paired comparison

Tasks: 100; bootstrap samples: 20000; seed: 20260731. Missing or failed tasks count as false.

Statistical pairing does not make differently defined metrics semantically comparable. In particular, frozen-corpus exact document ID and live-web exact Gold URL measure identity, not authoritative-source semantic equivalence.

## Coverage

| Run | Submitted | Expected | Active failures |
|---|---:|---:|---:|
| one-shot | 99 | 100 | 1 |
| OPTIMUS | 100 | 100 | 0 |
| CoE | 13 | 100 | 87 |
| OptiMiner | 92 | 100 | 8 |

## End-to-end model usage

Means are computed over submissions with recorded usage; the parenthesized value is that usage count. Accuracy denominators remain the preregistered task count above.

| Run | Input tokens | Output tokens | Reasoning tokens | Model calls | Search calls | Model wall seconds |
|---|---:|---:|---:|---:|---:|---:|
| one-shot | 17771.39 (99) | 4770.68 (99) | 2112.40 (99) | 1.00 (99) | 1.00 (99) | 105.02 (99) |
| OPTIMUS | 86511.06 (100) | 8398.64 (100) | 3657.16 (100) | 4.00 (100) | 1.00 (100) | 200.74 (100) |
| CoE | 772721.00 (13) | 28573.00 (13) | 14484.54 (13) | 6.00 (13) | 1.00 (13) | 698.25 (13) |
| OptiMiner | 72881.75 (92) | 6091.20 (92) | 2453.38 (92) | 4.00 (92) | 2.00 (92) | 151.42 (92) |

## Per-run rates and task-bootstrap 95% CI

| Run | Metric | Success | Rate | 95% CI |
|---|---|---:|---:|---:|
| one-shot | base_model_success | 99/100 | 0.990 | [0.970, 1.000] |
| one-shot | generated_code_ir_consistent | 99/100 | 0.990 | [0.970, 1.000] |
| one-shot | evidence_selected | 97/100 | 0.970 | [0.930, 1.000] |
| one-shot | model_structurally_changed | 98/100 | 0.980 | [0.950, 1.000] |
| one-shot | decision_model_equivalent | 95/100 | 0.950 | [0.900, 0.990] |
| one-shot | decision_e2e | 89/100 | 0.890 | [0.830, 0.950] |
| one-shot | semantic_e2e | 47/100 | 0.470 | [0.370, 0.570] |
| one-shot | strict_e2e | 0/100 | 0.000 | [0.000, 0.000] |
| OPTIMUS | base_model_success | 100/100 | 1.000 | [1.000, 1.000] |
| OPTIMUS | generated_code_ir_consistent | 100/100 | 1.000 | [1.000, 1.000] |
| OPTIMUS | evidence_selected | 97/100 | 0.970 | [0.930, 1.000] |
| OPTIMUS | model_structurally_changed | 98/100 | 0.980 | [0.950, 1.000] |
| OPTIMUS | decision_model_equivalent | 93/100 | 0.930 | [0.880, 0.980] |
| OPTIMUS | decision_e2e | 84/100 | 0.840 | [0.760, 0.910] |
| OPTIMUS | semantic_e2e | 44/100 | 0.440 | [0.350, 0.540] |
| OPTIMUS | strict_e2e | 0/100 | 0.000 | [0.000, 0.000] |
| CoE | base_model_success | 13/100 | 0.130 | [0.070, 0.200] |
| CoE | generated_code_ir_consistent | 13/100 | 0.130 | [0.070, 0.200] |
| CoE | evidence_selected | 12/100 | 0.120 | [0.060, 0.190] |
| CoE | model_structurally_changed | 12/100 | 0.120 | [0.060, 0.190] |
| CoE | decision_model_equivalent | 12/100 | 0.120 | [0.060, 0.190] |
| CoE | decision_e2e | 8/100 | 0.080 | [0.030, 0.140] |
| CoE | semantic_e2e | 4/100 | 0.040 | [0.010, 0.080] |
| CoE | strict_e2e | 0/100 | 0.000 | [0.000, 0.000] |
| OptiMiner | base_model_success | 92/100 | 0.920 | [0.860, 0.970] |
| OptiMiner | generated_code_ir_consistent | 92/100 | 0.920 | [0.860, 0.970] |
| OptiMiner | evidence_selected | 90/100 | 0.900 | [0.840, 0.950] |
| OptiMiner | model_structurally_changed | 92/100 | 0.920 | [0.860, 0.970] |
| OptiMiner | decision_model_equivalent | 89/100 | 0.890 | [0.820, 0.950] |
| OptiMiner | decision_e2e | 72/100 | 0.720 | [0.630, 0.810] |
| OptiMiner | semantic_e2e | 39/100 | 0.390 | [0.290, 0.490] |
| OptiMiner | strict_e2e | 0/100 | 0.000 | [0.000, 0.000] |

## Paired comparisons

`Difference` is left minus right. McNemar uses an exact two-sided binomial test over discordant tasks.

| Left | Right | Metric | Difference | 95% CI | Left only | Right only | Exact p |
|---|---|---|---:|---:|---:|---:|---:|
| one-shot | OPTIMUS | base_model_success | -0.010 | [-0.030, 0.000] | 0 | 1 | 1 |
| one-shot | OPTIMUS | generated_code_ir_consistent | -0.010 | [-0.030, 0.000] | 0 | 1 | 1 |
| one-shot | OPTIMUS | evidence_selected | 0.000 | [-0.030, 0.030] | 1 | 1 | 1 |
| one-shot | OPTIMUS | model_structurally_changed | 0.000 | [-0.030, 0.030] | 1 | 1 | 1 |
| one-shot | OPTIMUS | decision_model_equivalent | 0.020 | [-0.020, 0.060] | 3 | 1 | 0.625 |
| one-shot | OPTIMUS | decision_e2e | 0.050 | [-0.020, 0.120] | 9 | 4 | 0.2668 |
| one-shot | OPTIMUS | semantic_e2e | 0.030 | [-0.020, 0.080] | 5 | 2 | 0.4531 |
| one-shot | OPTIMUS | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| one-shot | CoE | base_model_success | 0.860 | [0.790, 0.930] | 86 | 0 | 2.585e-26 |
| one-shot | CoE | generated_code_ir_consistent | 0.860 | [0.790, 0.920] | 86 | 0 | 2.585e-26 |
| one-shot | CoE | evidence_selected | 0.850 | [0.780, 0.920] | 85 | 0 | 5.17e-26 |
| one-shot | CoE | model_structurally_changed | 0.860 | [0.790, 0.920] | 86 | 0 | 2.585e-26 |
| one-shot | CoE | decision_model_equivalent | 0.830 | [0.750, 0.900] | 83 | 0 | 2.068e-25 |
| one-shot | CoE | decision_e2e | 0.810 | [0.730, 0.880] | 81 | 0 | 8.272e-25 |
| one-shot | CoE | semantic_e2e | 0.430 | [0.330, 0.530] | 43 | 0 | 2.274e-13 |
| one-shot | CoE | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| one-shot | OptiMiner | base_model_success | 0.070 | [0.030, 0.120] | 7 | 0 | 0.01562 |
| one-shot | OptiMiner | generated_code_ir_consistent | 0.070 | [0.030, 0.120] | 7 | 0 | 0.01562 |
| one-shot | OptiMiner | evidence_selected | 0.070 | [0.020, 0.120] | 7 | 0 | 0.01562 |
| one-shot | OptiMiner | model_structurally_changed | 0.060 | [0.010, 0.120] | 7 | 1 | 0.07031 |
| one-shot | OptiMiner | decision_model_equivalent | 0.060 | [0.010, 0.120] | 7 | 1 | 0.07031 |
| one-shot | OptiMiner | decision_e2e | 0.170 | [0.070, 0.270] | 22 | 5 | 0.001514 |
| one-shot | OptiMiner | semantic_e2e | 0.080 | [0.010, 0.160] | 12 | 4 | 0.07681 |
| one-shot | OptiMiner | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| OPTIMUS | CoE | base_model_success | 0.870 | [0.800, 0.930] | 87 | 0 | 1.292e-26 |
| OPTIMUS | CoE | generated_code_ir_consistent | 0.870 | [0.800, 0.930] | 87 | 0 | 1.292e-26 |
| OPTIMUS | CoE | evidence_selected | 0.850 | [0.780, 0.920] | 85 | 0 | 5.17e-26 |
| OPTIMUS | CoE | model_structurally_changed | 0.860 | [0.790, 0.920] | 86 | 0 | 2.585e-26 |
| OPTIMUS | CoE | decision_model_equivalent | 0.810 | [0.720, 0.890] | 82 | 1 | 1.737e-23 |
| OPTIMUS | CoE | decision_e2e | 0.760 | [0.670, 0.840] | 77 | 1 | 5.228e-22 |
| OPTIMUS | CoE | semantic_e2e | 0.400 | [0.300, 0.500] | 41 | 1 | 1.955e-11 |
| OPTIMUS | CoE | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| OPTIMUS | OptiMiner | base_model_success | 0.080 | [0.030, 0.140] | 8 | 0 | 0.007812 |
| OPTIMUS | OptiMiner | generated_code_ir_consistent | 0.080 | [0.030, 0.140] | 8 | 0 | 0.007812 |
| OPTIMUS | OptiMiner | evidence_selected | 0.070 | [0.020, 0.120] | 7 | 0 | 0.01562 |
| OPTIMUS | OptiMiner | model_structurally_changed | 0.060 | [0.010, 0.120] | 7 | 1 | 0.07031 |
| OPTIMUS | OptiMiner | decision_model_equivalent | 0.040 | [-0.020, 0.100] | 7 | 3 | 0.3438 |
| OPTIMUS | OptiMiner | decision_e2e | 0.120 | [0.020, 0.220] | 21 | 9 | 0.04277 |
| OPTIMUS | OptiMiner | semantic_e2e | 0.050 | [-0.020, 0.130] | 10 | 5 | 0.3018 |
| OPTIMUS | OptiMiner | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
| CoE | OptiMiner | base_model_success | -0.790 | [-0.870, -0.700] | 2 | 81 | 7.211e-22 |
| CoE | OptiMiner | generated_code_ir_consistent | -0.790 | [-0.870, -0.700] | 2 | 81 | 7.211e-22 |
| CoE | OptiMiner | evidence_selected | -0.780 | [-0.860, -0.690] | 1 | 79 | 1.34e-22 |
| CoE | OptiMiner | model_structurally_changed | -0.800 | [-0.880, -0.710] | 1 | 81 | 3.433e-23 |
| CoE | OptiMiner | decision_model_equivalent | -0.770 | [-0.850, -0.680] | 1 | 78 | 2.647e-22 |
| CoE | OptiMiner | decision_e2e | -0.640 | [-0.740, -0.530] | 3 | 67 | 9.694e-17 |
| CoE | OptiMiner | semantic_e2e | -0.350 | [-0.450, -0.250] | 2 | 37 | 2.841e-09 |
| CoE | OptiMiner | strict_e2e | 0.000 | [0.000, 0.000] | 0 | 0 | 1 |
