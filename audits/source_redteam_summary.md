# Source red-team summary

- 审计行数：140
- 主 supplemental：36 pass / 7 reject
- supplemental reserve：40 pass / 0 reject
- OptMiner release verdict：0 pass / 57 reject
- OptMiner结构/双求解器门：30 pass / 27 reject
- 当前可释放的不同来源：76
- 主 supplemental rejects：SWOR-BASE-066, SWOR-BASE-073, SWOR-BASE-076, SWOR-BASE-080, SWOR-BASE-092, SWOR-BASE-093, SWOR-BASE-098

## Release blockers

- 57个OptMiner候选均缺题面到IR的互盲逐句语义映射；30个只通过结构/双求解器门，27个还在非线性或规模/许可门失败。
- OptMiner存储证书不含完整assignment，COPT version为unknown；action_projection机械排除连续变量，OMB073甚至为空。
- 主supplemental新增发现2个无题面依据的变量上界错误；连同原5个拒绝，仅36/43通过。
- 主supplemental脚本在模型冻结循环之前加载legacy answers，虽未观察到流向建模函数，仍不满足严格先冻结后加载顺序。
- 主supplemental认证产物未由独立manifest逐文件绑定；reserve的40条则已逐文件hash绑定。
- 当前可释放来源仅76条（36主supplemental+40 reserve），不足100；不得用未语义认证的OptMiner补数。

## Extractor findings

- Gurobi结构检查能识别quadratic/general/SOS和非单目标结构，当前43个线性IR均有当前audit哈希。
- 当前13个大线性IR在restricted Gurobi许可下失败，不能算双求解器证书；它们不是stale文件。
- AST筛查只是副作用启发式，不是安全沙箱；允许numpy和间接builtins访问仍可绕过。
- 提取器没有可发布的显式规模上限；超过2000变量或约束时尝试Gurobi presolve，但无法为原变量提供完整行动证书。
