# 20 道 ORLM 样例的参考程序复核

2026-11-16，使用提供的 `答案.md` 中唯一 Python 代码块，原样提取后在各题原始 CSV 目录下运行。题面、答案和附件均未修改；20 题均保存运行前后的 SHA-256 核验。

**COPT 执行结果为 20/20 optimal。** 包装器只将单次求解时间上限设为 90 秒、线程数设为 1，并导出参考 MPS 和求解统计。原程序的变量、目标和约束没有重写。实际每题程序运行约 0.7–1.3 秒。

对导出的同一数学模型用 Gurobi 再求解，19/20 获得相同最优值；`B03_00289`（868 变量、17,647 约束）触发本机 Gurobi 许可证规模限制，交叉检查记为未完成。该题原 COPT 程序已经求得最优值 690。许可证异常不计为题目错误或模型错误。

## 证据文件

- `reference_results.json`：全部 20 题原始程序输出、状态、用时、源文件哈希。
- `reference_crosscheck.json`：Gurobi 交叉结果及许可证异常。
- `cases/<source_id>/reference.py`：从答案中原样提取的代码。
- `cases/<source_id>/reference_model_0.mps`：求解前导出的完整数学模型。
- `cases/<source_id>/solver_stats_0.json`、`stdout.txt`、`stderr.txt`：求解与执行记录。
- `check_references.py`、`execute_one.py`、`crosscheck_mps.py`：复核入口。

## 与正式实验隔离

本目录是评分侧材料。SWAgent 和 Standard 的输入只能包含题面及公开数据，不得读取本目录、原始答案、MPS 或参考最优值。

这些检查确认参考程序可执行、所建模型有最优解，以及 19 题跨求解器数值一致；它们不独立证明参考程序已正确表达需求文档中的每一条业务规则。后续汇报若仅比较最优目标值，应明确称为目标值匹配，不能称为全模型正确率。

## 复现

在本机使用 `E:/my_evns/py312_torch28/python.exe` 依次运行 `check_references.py` 和 `crosscheck_mps.py`。其他机器需要 Python、pandas、coptpy、gurobipy 及相应许可证。脚本从相邻的 `SFT1991_sample20/SFT1991_sample20` 读取作者提供的源数据。
