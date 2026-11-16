# Response to Reviewer dqz1

Dear Reviewer dqz1,

Thank you for your thoughtful review. We appreciate your recognition of the problem formulation, benchmark design, and experimental evaluation. Below, we provide additional explanations and experiments addressing your comments. We have also updated the paper PDF. **If you have any further questions, we would be happy to discuss and address them.**

# (W1) R1: Benchmark coverage and realism

Thank you for your comments on benchmark coverage and realism.

SearchWorthyOR addresses a specific practical gap: business requirements may state the objective, resources, and candidate decisions without listing all external rules that determine feasibility. We use verifiable real-world rules to construct controlled optimization instances that test rule discovery, applicability judgments, and mathematical model updates.

## (a) Application categories

The current benchmark contains 100 source tasks. Each has C1/C2/C3, giving 300 condition-specific instances. Each category contains 9–12 source tasks. The categories are listed below; we also included them in the appendix of the original submission.

**Table 1. Application coverage.**

| Application category | Source tasks | Specific scenarios covered |
| --- | :--- | --- |
| Assignment and matching | 10 | Lighting recalls, room matching, hazardous materials |
| Energy and environment | 9 | Interregional grid connections, oil storage design, secondary containment design |
| Facilities and networks | 11 | Parking facilities, oil pipelines, control-function configuration |
| Finance and portfolios | 11 | ISA investment accounts, portfolios of positions |
| Healthcare resources | 10 | Treatment slots, eligibility matching, imaging equipment restoration |
| Inventory and supply chains | 9 | Hazardous materials, road freight consolidation, temperature control |
| Production and capacity | 12 | Product ingredients, composition thresholds, vehicle production, certificate resources |
| Routing and transportation | 9 | Cross-sea transportation, ferries, shuttle route planning |
| Scheduling and workforce | 10 | Cabin crew scheduling, vaccination services |
| Telecommunications services | 9 | Project delivery, SMS providers, message routing |

These ten categories correspond to typical areas such as energy, finance, healthcare, production, logistics, and telecommunications in the [ORSSA overview of application areas](https://www.orssa.org.za/applicationareas). They also cover classic problem types such as transportation and assignment, network optimization, and inventory, discussed in Chapters 9, 10, and 18 of Hillier and Lieberman's [*Introduction to Operations Research*, 11th edition](https://info.mheducation.com/rs/128-SJW-347/images/ISE_Product%20Flyer_Hillier_Intro%20to%20Operations%20Research_11e.pdf). These links between application areas and problem types show that our approach covers a broad range of applications and constructed scenarios.

## (b) Rule complexity and interactions

Thank you and Reviewer RF3z for raising the issue of rule interactions. We checked all 100 C2 tasks and obtained the following results.

**Table 2. Requirement structure in C2.**

| Rule structure | Tasks |
|---|---:|
| Single requirement | 64 |
| Multiple requirements, no clear interaction observed | 29 |
| Multiple requirements with clear interactions | 7 |

We count requirements as obligations or restrictions that can be implemented separately. An interaction is a dependency, exception, or priority relation between requirements. **Multiple requirements occur in 36% of tasks, and clear interactions occur in 7%.**

For example, 

> under the ADA standards, the 240-space parking facility in R005 first requires at least 7 accessible spaces. This count then determines that at least 2 must be van-accessible spaces. The two requirements exclude options A and B in sequence, changing the optimal choice from A (utility 30) to C (utility 20). 

This shows how rule dependencies affect the mathematical model and the decision. Each task has a fixed assessment date. Its rule materials record version dates and items awaiting verification, so that thresholds, exceptions, and scope can be distinguished across versions.

**Overall, the benchmark covers different business domains and tests multiple requirements, rule interactions, and temporal applicability.**

# (W1 / Q1) R2: Task sources and independent evaluation

Thank you for this specific question. **SearchWorthyOR serves as an evaluation set in this study and is not used to train SWAgent.** We evaluate how a shared workflow for condition discovery, evidence checking, and mathematical model updates performs across optimization scenarios.

## (a) Task sources and selection

**The initial backgrounds and mathematical structures draw on IndustryOR, the OptiMiner benchmark, LogiOR, and scenarios from our team.** We use assignment, scheduling, selection, and capacity models as starting points. We then use real-world materials to reconstruct the business setting, assessment date, candidate options, and numerical values, and add external requirements that change the decision. Each source task stores the issuing organization, URL, supporting source excerpts, rule description, Base/Full reference mathematical models, typed changes, and complete sets of optimal actions. Content and mathematical checks examine the interpretation of evidence, applicability to the instance, correspondence with constraints, and solver results.

## (b) Information differences across C1/C2/C3

- **C1: The target rule is not applicable.** We change applicability facts such as object attributes or time to test applicability judgments and preservation of the correct mathematical model.

- **C2: The target rule applies but is omitted from the problem statement.** This tests whether the agent can discover the information gap, obtain the rule, and update the mathematical model.

- **C3: The applicable rule is provided.** It shares the business facts and reference answer with C2, and adds a rule summary to the input. It tests modeling when the rule is known.

The three conditions deliberately control information visibility. The business rules and the grounds for the decisions come from real-world materials. The C2 Base model contains the conditions in the problem statement, while the Full model adds the applicable requirements. Construction requires their optimal action sets to be disjoint, so that omitting the rule changes the optimal decision.

C2 and C3 keep the business facts the same. Providing or withholding the rule allows us to examine the effect of filling the information gap.

## (c) Generality and independent validation

SWAgent reuses the same workflow across application categories and backbones. Its inputs contain the public problem statement and output format, which the agent uses to determine what to check. These results provide evidence across domains and backbones on the current evaluation tasks.

**Evaluation on independently sourced real-world optimization tasks is still pending. Future work will further test external validity using larger-scale real-world tasks, longer rule chains, and dynamically updated tasks.**

**Overall, this study uses an evaluation set to test how a shared workflow handles missing external rules. The current evidence comes from experiments across domains and backbones on these tasks.**

# (W2 / Q2) R3: C2 gains and model correctness

Thank you for focusing on the core capability tested by C2. Proactively discovering and implementing omitted rules is SWAgent's core goal, and C2 specifically tests this capability. Using the frozen data and existing runs, we explain the method's effect at three levels: answers, full mathematical models, and actual evidence traces.

The R3–R4 analyses use existing results and traces for 100 source tasks and 300 condition-specific instances. Corresponding evaluation records from the same source task are paired. SWAgent-offline retains the information–evidence table, mathematical model updates, and solving, while disabling search and reading.

## (a) C2 answer gains

We pair DeepSeek Standard-online and SWAgent-online on the same source tasks. For Opus, we compare SWAgent with Claude Code. The results are as follows.

**Table 3. DeepSeek workflow accuracy.**

| DeepSeek workflow | Overall | C1 | C2 | C3 |
| ------------------ | ----------------: | ---------: | ---------: | ---------: |
| Standard-offline | 71.22% | 81.33% | 34.33% | 98.00% |
| Standard-online | 74.89% | 82.67% | 44.33% | 97.67% |
| **SWAgent-online** | **84.00%** | **88.00%** | **66.33%** | **97.67%** |

Compared with Standard-online, SWAgent improves overall accuracy by **9.11 percentage points** and C2 accuracy by **22.00 percentage points**. Of the 82 additional correct outcomes overall, 66 come from C2, accounting for **80.49%**. The gain therefore mainly occurs in the core condition where applicable rules are missing.

**Table 4. Paired outcomes by condition.**

| Same-backbone comparison | Condition | Both correct | Only SWAgent correct | Only comparator correct | Both incorrect |
| ------------------------------------------ | ---- | -------: | ------------: | ---------: | -------: |
| DeepSeek: SWAgent-online / Standard-online | C1 | 232 | 32 | 16 | 20 |
| DeepSeek: SWAgent-online / Standard-online | C2 | 110 | 89 | 23 | 78 |
| DeepSeek: SWAgent-online / Standard-online | C3 | 289 | 4 | 4 | 3 |
| Opus 5: SWAgent / Claude Code | C1 | 77 | 15 | 3 | 5 |
| Opus 5: SWAgent / Claude Code | C2 | 71 | 10 | 10 | 9 |
| Opus 5: SWAgent / Claude Code | C3 | 89 | 7 | 4 | 0 |

**DeepSeek's C2 accuracy rises from 44.33% to 66.33%, a gain of 22.00 percentage points.** On the same instances, 89 outcomes are correct only for SWAgent and 23 only for Standard, giving a net gain of 66. Both methods have internet access. This comparison supports the added value of SWAgent's full information-gathering and modeling workflow over a standard online baseline. The improvement does not come only from C1/C3.

For Opus, SWAgent's overall advantage over Claude Code is 5.00 percentage points. The net gain comes from 12 C1 instances (80%) and 3 C3 instances (20%). Both Opus agents reach 81% on C2, and each alone answers 10 instances correctly, showing that they succeed on complementary sets of tasks. SWAgent obtains more correct outcomes in both C1 and C3, increasing overall accuracy. DeepSeek gains a net 16 correct outcomes in C1 and has the same total score in C3. Its main overall gain comes from C2.

## (b) Full-model correctness

A correct optimal answer can still hide missing or unnecessary constraints. We therefore check the C2 mathematical models generated by the two DeepSeek online methods.

We compare the entire feasible set and the objective value for every feasible action, as well as the optimization direction and unit. Conditional constraints are evaluated according to when they apply, with an objective-value tolerance of 10⁻⁷.

**Table 5. Answer and full-model correctness.**

| DeepSeek method | Answer accuracy | Full-model equivalence rate |
| --------------- | ---------: | -------------------------------------: |
| Standard-online | 44.33% | 33.33% |
| SWAgent-online | 66.33% | 55.33% |

**The full-model equivalence rate increases from 33.33% to 55.33%, also a gain of 22.00 percentage points.** Comparing SWAgent's initial mathematical model saved before the first UPDATE with its final mathematical model gives the following counts of model revisions.

**Table 6. Initial-to-final model changes.**

| SWAgent initial→final mathematical model status | Records |
|---|---:|
| Not equivalent→equivalent | 156 |
| Equivalent→equivalent | 10 |
| Equivalent→not equivalent | 4 |
| Not equivalent→not equivalent | 129 |
| Not equivalent→unresolved (missing final delivery) | 1 |

**All 156 correct revisions have actual source-body input, a corresponding language-model response, and an accepted nonempty patch. The final decisions agree with the revised mathematical models.**

Full-model checks, together with the rule interpretations and constraint bindings verified window by window below, support SWAgent's improvement in handling omitted rules and revising mathematical models.

## (c) Online/offline and C2/C3 comparisons

To test whether the gains depend on external information, we keep the SWAgent framework and compare online with offline. We also check whether instances answered incorrectly in C2 can be solved in C3, where the rules are provided.

**Table 7. Online/offline and C2/C3 paired outcomes.**

| Backbone | Offline incorrect→online correct | Offline correct→online incorrect | Among online C2 errors, same-source C3 correct |
| -------------- | -----------------: | -----------------: | ---------------------------: |
| DeepSeek | 170 | 8 | 94.06% |
| Opus 5 | 67 | 3 | 89.47% |

DeepSeek's C2 accuracy increases from 12.33% offline to 66.33% online, and Opus increases from 17% to 81%, gains of 54 and 64 percentage points, respectively. On the same instances, 170 outcomes and 67 outcomes change from incorrect to correct, while 8 and 3 change in the reverse direction.

In addition, of the online C2 errors, 95/101 for DeepSeek and 17/19 for Opus are correct in the corresponding C3 instances. **This shows that, when applicable rules are explicitly provided, the mathematical model update workflow supported by the information–evidence table can solve most of these tasks.** Together with the online gains over offline, these results support the role of gathering external information and then implementing it in the mathematical model.

## (d) C2 Effects on failed-recall tasks

We further combine closed-book rule probes with existing optimization results to check whether the language models can fill the information gaps using their existing knowledge. The complete recall rates of DeepSeek and Opus are 20.20% and 3.03% in offline, respectively. More details are in our response to Reviewer ix8z, (W1) R1. For tasks where a language model clearly failed to recall the main rule or key details, enabling external information gathering in the same SWAgent workflow gives the following results.

**Table 8. C2 gains on failed-recall tasks.**

| Backbone       | C2 offline→online |      Gain |
| -------------- | ----------------- | --------: |
| DeepSeek Flash | 12.33%→64.84%     | +52.51 pp |
| Opus 5         | 14.94%→80.46%     | +65.52 pp |

118 DeepSeek outcomes and 59 Opus outcomes change from incorrect to correct. **The reference mathematical models verify that omitting the rules changes the decisions. Actual runs further show that filling the information gaps improves task-solving results on these tasks.** 

## (e) Rule discovery and model-update traces

- **R009: Proactive discovery.** Standard does not trigger search. SWAgent proactively checks age and disease eligibility, revises constraints based on official requirements, and obtains the correct result.

- **R013: Version checking.** SWAgent checks the final rule and its effective date, updates the thresholds, and obtains the correct decision.

- **R107: Stepwise updates.** The information–evidence table retains the unresolved question about the type of buffer car. Further checking completes the buffer-car constraints, and the final mathematical model is equivalent to the reference.

**The C2 gains, full-model checks, and actual traces together support SWAgent's role in proactively discovering omitted rules and implementing them as mathematical model updates.**

# (W2 / Q2) R4: C2 failure modes

Thank you for raising this key distinction. Using the R3 settings, we review DeepSeek SWAgent-online's C2 evaluation records. We combine actual input windows, mathematical model updates, and delivery records to locate errors in information gathering, updating, and execution.

## (a) Workflow states of C2 errors

The C2 evaluation records contain 199 correct outcomes and 101 incorrect outcomes. We check execution exceptions, search, archived body text, and mathematical model changes in that order to obtain the following mutually exclusive states.

**Table 9. Workflow states of C2 errors.**

| Observable state of an incorrect run | Count | Share of the 101 errors |
|---|---:|---:|
| Abnormal termination or timeout | 21 | 20.79% |
| Normal termination, no search observed | 11 | 10.89% |
| Normal termination, search performed but no body text in the READ archive | 9 | 8.91% |
| Normal termination, READ contains body text but no nonempty mathematical model change was accepted | 28 | 27.72% |
| Normal termination, READ contains body text and a change was accepted, but the final answer is still incorrect | 32 | 31.68% |

The 21 exceptions include 8 citation-validation failures, 5 JSON parsing failures, 4 search-transport failures, and 1 each for a language-model request timeout, whole-instance timeout, exhausted wall-clock budget, and missing patch field.

Among the 80 errors with normal termination, 20 have no archived READ body text and 60 have body text, but we still need to check whether it is sufficient and whether its requirements are implemented in the mathematical model. **Errors occur across information gathering, updating, execution, and delivery.**

## (b) Source-text support

We further examine the API inputs, information–evidence tables, and constraints for 33 error records. For 27 records, we have completed the window review or confirmed that no body text was present. Full-window checking is still pending for 6 records.

**Table 10. Source-text support in C2 errors.**

| State of the actual evidence | Count / 33 | Percentage |
|---|---:|---:|
| No external source-body window in the language-model request | 14 | 42.42% |
| Body text is present but is unrelated, lacks key requirements, or does not cover the applicable version | 11 | 33.33% |
| Unresolved: 2 scope/version boundary cases and 6 awaiting completed checks | 8 | 24.24% |

For 25/33 records, the body text does not yet establish complete support for the applicable rules. These include records with no body text and those containing only some requirements.

- R073 implements the lead, mercury, and cadmium thresholds, but the food-use exception is cut off at the end of the input window.

- In R099, the key percentage falls in a gap between adjacent reading windows, and the truncated “1” is then misread as one channel.

- The information-gathering record for R058 shows that the application requirement is implemented, while the annual reporting obligation is still omitted.

In these examples, condition discovery or some constraint changes have been completed. The remaining gaps are in body-text coverage and the gathering of multiple requirements. Improvement therefore requires reading all task-relevant passages and continuing to track requirements that have not yet been implemented. Of the 33 records, 12 contain exceptions or timeouts, which can overlap with insufficient body text.

## (c) Update, constraint, and delivery errors

**Table 11. Diagnostic error cases.**

| Pattern and case | Confirmed process | Specific error |
|---|---|---|
| Update introduces an extra restriction, R039 | The initial mathematical model is fully equivalent to the reference. | An interconnection package triggered by voice services is made mandatory in all cases, excluding 3 additional actions and reducing utility from 135 to 108. |
| Incorrect obligation binding, R058 | The initial mathematical model is fully equivalent to the reference. | The annual reporting obligation is incorrectly bound to the new-operation approval path, wrongly excluding 4 actions and allowing 4 others; cost changes from 17 to 15. |
| Patch execution is interrupted, R024 | The body text already provides the three-year record-retention requirement. | The UPDATE lacks the variable field, so this requirement is not implemented; reporting-deadline information also remains missing. |
| Final delivery is interrupted, R042 | The saved mathematical model's 12 actions and objective values match the reference, and a value of 50 has been obtained. | Further checking times out, leaving no final delivery; the final status is unresolved. |
| Overly restrictive base constraints, R057 | The answer is correct, and the working-time rule has revised the objective from 62 to 53. | Of the reference's 20 actions, the staffing-support constraint retains only 19. |
| Incorrect direction of a condition, R103 | The optimal value of 98 is correct. | A one-way dependency is written as an equality, excluding 3 additional feasible actions. |

R039 and R058 account for the 4 records that change from an equivalent initial mathematical model to a nonequivalent final one. R057 and R103 come from the supplementary checks of correct answers with nonequivalent mathematical models. R057 requires on-call backup for the 26-hour option. It wrongly excludes a combination allowed by the reference: a second on-site operator and 26 hours of paid time, with an objective value of 48.

These cases further illustrate three points.

- **Updates must preserve existing correct constraints.** R039 and R058 show that errors in trigger scope or obligation binding can damage an initially correct mathematical model. Updates should therefore check both new requirements and existing constraint relationships.

- **Execution and delivery after obtaining rules are also important.** R024 shows interrupted patch execution. R042 shows a delivery timeout after a correct mathematical model has already been obtained. Improvements need to cover update interfaces, time-limit handling, and timely delivery of available results.

- **Full-model checks have independent value.** R057 and R103 show that a correct optimal answer can hide the exclusion of feasible actions. Checking the entire feasible set can detect these residual constraint errors.

The trace for the reverse case, R003, shows that, after SWAgent excludes D, B's annual threshold remains unclear when the reading budget is exhausted, yielding 81. Standard excludes B/D and obtains the reference answer of 73. This shows that, after the information–evidence table identifies a need for checking, the remaining unresolved requirements must continue to be tracked until they can support the final mathematical model.

**Together with the 156 correct mathematical model revisions and the success traces that can be checked stage by stage in R3, these results show that SWAgent has converted external requirements into correct mathematical models in actual runs. The failure analysis further shows that improving reliability requires complete requirement gathering, correct mathematical model updates, and stable final delivery.**

# (Q3) R5: Comparison fairness and component effects

Thank you for asking us to clarify the comparison settings. We agree that both resource settings and component contributions need to be explained.

The 11.33-percentage-point result in the original paper is the overall difference between full SWAgent and Codex-Native-Search. The additional experiments use comparisons with the same resource limits and component ablations to further test the roles of the full workflow and its internal design.

## (a) Shared tools, budgets, and scoring

DeepSeek Standard-online and SWAgent-online use the following common settings. Actual calls and usage are recorded for each instance.

**Table 12. Shared experimental settings.**

| Controlled item | Setting |
|---|---|
| Data and scoring | The same frozen 100 source tasks and 300 condition-specific instances, scored jointly against the reference optimal action set and objective value. |
| Backbone and API | deepseek-flash, using the same language-model API. |
| Search and reading | The same DeepSeek Search and webpage-reading implementation; both methods can search, read, and revise the mathematical model. |
| Solving | The same solver implementation and interface, with a 90-second limit per solve. |
| Per-instance resource limits | 12 language-model calls, 3 searches, 6 reads, a 1200-second total time limit, and at most 2 technical retries. |
| Task pairing | Corresponding evaluation records are checked by source task ID. |

## (b) Actual usage and workflow gains

**Table 13. DeepSeek resource use and accuracy.**

| Method | Overall | C2 | Recorded tokens / instance | Searches / instance | Reads / instance |
|---|---:|---:|---:|---:|---:|
| Standard-online | 74.89% | 44.33% | 17,918 | 0.122 | 0.637 |
| SWAgent-online | 84.00% | 66.33% | 34,070 | 0.672 | 1.750 |

SWAgent performs more information gathering and checking. It uses about 1.90 times as many recorded tokens and gains **9.11 percentage points** overall and **22.00 percentage points** on C2. Its full-model equivalence rate also increases by 22 percentage points. These results show the actual resource use and gains of the full workflow under the same tools and resource limits.

We report Opus and the general-purpose search systems using their respective implementations to provide comparisons across systems. The DeepSeek experiments above provide the workflow comparison with the same backbone, tools, and limits. Ablations further test the roles of internal components.

## (c) Component contributions

The original Luna component ablations retain search access and separately remove the information–evidence table, initial modeling, and the closed criterion.

**Table 14. Component ablation results.**

| Method | Overall | C2 |
|---|---:|---:|
| Full SWAgent | 79.00% | 45.00% |
| Without the information–evidence table | 62.33% | 22.00% |
| Without initial modeling | 68.00% | 35.00% |
| Without the closed criterion | 64.33% | 31.00% |

- **Removing the information–evidence table while retaining search lowers C2 accuracy by 23 percentage points. This supports the role of organizing conditions, evidence, and mathematical changes across rounds.**

- Removing initial modeling lowers C2 accuracy by 10 percentage points, indicating that organizing checks around explicit variables and constraints helps modeling.

- Removing the closed criterion lowers it by 14 percentage points. This ablation retains the information–evidence table, updates, and solving, and tests when to continue gathering information and when to finish updating the mathematical model.

**Thus, comparisons with shared resource limits test the gains of the full workflow, while ablations that retain search access test its internal components. The mathematical model revisions and the R107 trace in R3 further show how these designs work together to gather evidence and implement constraints.**
