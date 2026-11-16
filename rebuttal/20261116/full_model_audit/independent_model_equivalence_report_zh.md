# dqz1 full-model equivalence 独立复算

本审计直接读取冻结 v1.6.3 的参考 IR、100 个 C2 源任务、两种方法的 600 份已保存模型和终态记录；未调用模型、搜索、网络或求解器。数字字段按 UTF-8 JSON 中的十进制文本解析为 `Decimal` 后转精确有理数。原始记录、模型和分数文件保持只读。

判据是：公开行动的完整可行集合相同；对每个共享可行动作，目标值在绝对 1e-7 内一致；方向和单位一致。有限 BINARY/INTEGER 变量全枚举，辅助变量按存在可行赋值投影；不检查现实规则本身是否正确，也不把最优值相同视为模型等价。

## 终态统计

| 方法 | PASS | FAIL | UNRESOLVED | PASS率（固定n=300） | 排除R116后 |
|---|---:|---:|---:|---:|---:|
| Standard-online | 100 | 200 | 0 | 33.33% | 33.67%（n=297） |
| SWAgent-online | 166 | 133 | 1 | 55.33% | 55.22%（n=297） |

互斥首要失败分类按“缺交付/未决 → 可行域差异 → 同域目标值差异 → 仅方向或单位差异”的顺序归类；次级重叠计数另存于 JSON，便于看出一个案例是否同时有多种差异。

| 首要类别 | 数量 |
|---|---:|
| PASS | 266 |
| FEASIBLE_REGION_DIFFERENCE | 333 |
| SAME_DOMAIN_OBJECTIVE_DIFFERENCE | 0 |
| DIRECTION_UNIT_ONLY | 0 |
| MISSING_DELIVERABLE | 1 |
| UNRESOLVED_OTHER | 0 |

可行域差异的方向（按case-run计数）：

| 方法 | 仅过约束 | 仅漏约束 | 同时过约束和漏约束 |
|---|---:|---:|---:|
| Standard-online | 56 | 114 | 30 |
| SWAgent-online | 33 | 93 | 7 |
| 合计 | 89 | 207 | 37 |

## 答案正确但完整模型失败的最优集关系

| 方法 | answer-correct + model-FAIL | 最优公开动作集等于冻结gold | 缺少gold最优动作 | 产生额外最优动作 |
|---|---:|---:|---:|---:|
| Standard-online | 33 | 33 | 0 | 0 |
| SWAgent-online | 33 | 33 | 0 | 0 |

这里仅称逐实例最优公开动作集一致。每条仍有非最优部分的可行域差异；该结果不证明模型的一般合法性或语义正确性。逐条action set计数见summary JSON/CSV。


## SWAgent 初始模型到终态模型

| 转移 | 次数 |
|---|---:|
| FAIL -> FAIL | 129 |
| FAIL -> PASS | 156 |
| FAIL -> UNRESOLVED | 1 |
| PASS -> FAIL | 4 |
| PASS -> PASS | 10 |

首要逐条复核名单见 CSV。初始 PASS→终态 FAIL 是已引入错误限制的直接反例；FAIL→FAIL 表示终态仍不匹配，期间可以发生部分修正或错误更新；FAIL→PASS 是按冻结模型定义完成修复。

## 参考契约敏感性

本次枚举未发现参考 IR 与冻结 gold 的最优行动或目标契约不一致；这只验证二者在数学数据上的内部一致。先前语义审阅对 SWOR-R116 的现实规则来源/版本提出争议，内部一致不能消解该问题。因此保留全100源冻结统计，并另列排除 R116 的敏感性值。

## 复算与实现风险

- 原始 600 条记录与旧记录逐条对比，独立状态差异列表见 summary；差异须逐行查明，不能用原报告统计覆盖。
- 另拒绝重复 JSON 对象键，精确读入小数；空变量域保留为空集，避免错误将无界/矛盾整数域变成单点。
- 变量上下界、方向/单位、公开行动映射、条件约束触发、目标/约束中未定义变量、辅助变量目标项及枚举上限均单独校验；不支持的模型作为 UNRESOLVED，而非FAIL或PASS。
- 完整反例 witness（参考可行但生成不可行、生成额外可行以及共享行动目标冲突）按每条失败逐题保存。
- 结论边界：该统计证明的是生成模型相对冻结参考 IR 的全行动空间一致性。若冻结规则解释或版本错误，匹配它仍可能在语义上错误；反过来，若任务语义正确但参考 IR 错，也会被判不等价。语义审阅需单独完成。

复算入口：`independent_model_equivalence_audit.py`；逐行表：`independent_model_equivalence_records.csv`；反例：`independent_model_equivalence_witnesses.jsonl`；机器汇总及散列：`independent_model_equivalence_summary.json`。
