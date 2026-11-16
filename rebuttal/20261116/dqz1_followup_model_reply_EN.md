# Follow-up on full-model equivalence and model-update reliability

Thank you for recognizing the additional evidence. We would like to clarify what the 55.33% statistic measures and provide more direct evidence concerning mathematical model updates.

Our contributions begin with **identifying and formalizing proactive discovery of unstated external rules as an optimization-modeling problem**, and constructing a benchmark that makes rule applicability and visibility explicitly evaluable. SWAgent is an approach to this newly characterized problem. The remaining performance gap should therefore be considered alongside these problem-formulation and benchmark contributions, as well as the demonstrated progress in rule-informed modeling.

The 55.33% figure is a **strict reference-equivalence rate**: it requires the entire projected feasible-action set and its objective values to match the frozen reference, including all non-optimal actions. It is not a direct estimate of the proportion of models with semantically incorrect constraints, or a measured failure rate of external-rule discovery and incorporation. Our additional audit provides concrete reasons for this distinction.

First, the results and saved update trajectories show substantial model-level improvement:

| Evidence | Result |
|---|---|
| Full-model equivalence under the same backbone | 33.33% for Standard-online → 55.33% for SWAgent-online; +22.00 percentage points |
| Revisions from a non-equivalent initial model to a fully equivalent final model | 156 runs |
| Within these 156 revisions: external body windows verified in actual API requests, with matched responses consumed as accepted nonempty UPDATE patches | 156/156 |
| Additional runs where updates corrected the initial optimum and the complete optimal-action set, with only non-optimal-region differences remaining | 28 runs |

The 22-point gain in strict model equivalence matches the gain in answer accuracy. It is also consistent across the three evaluation runs: the model-equivalence gains are 24, 21, and 21 percentage points. These observations show that the improvement extends beyond obtaining the correct final numerical answer. The request-to-patch verification also makes the external information supplied to the model and the subsequent accepted revisions auditable.

Second, we exhaustively examined **all 33 SWAgent runs with correct answers but failed full-model equivalence**, covering 18 source tasks. All 33 preserve both the reference optimal value and its **complete optimal-action set**. For five of these 33 runs, we further verified explicit optimality-preserving reduction certificates under the recorded constraints and costs.

For example, R103 excludes purchasing a service that only advances employee A's vaccination date when A is not selected. R105 excludes purchasing a dog-segregation service for a non-dog production line. In these cases, and the R025 route-selection cases, **every excluded action has a strictly better retained alternative with the same primary business choice**. All retained alternatives are reference-feasible and have matching objective values. These five instances therefore have a mathematical explanation for preserving optimization despite failing full-feasible-set equality. This conclusion is specific to these five audited instances.

We retain the original 55.33% result. The additional evidence clarifies its interpretation: **a strict reference mismatch cannot uniformly be read as incorrect or missing constraints, nor does that aggregate statistic by itself establish that external-rule incorporation is unreliable.** We hope that the direct revision evidence and the case-level verification strengthen your confidence in the reliability of the demonstrated mathematical model updates, while making clearer the paper's broader contribution in defining, benchmarking, and advancing this problem.
