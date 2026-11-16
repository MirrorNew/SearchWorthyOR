# 20 道 ORLM 训练案例的 C3 类补充实验

输入来自作者提供的 `SFT1991_sample20/SFT1991_sample20`，作者说明为从杉数取得的 ORLM 训练案例。完整保留题面及其 CSV，按信息已给定的 C3 类任务评测。该来源说明不等同于已认证的独立真实部署案例。

`public_cases.jsonl` 包含 20 条 `{id, prompt, output_schema}` 输入；`source_manifest.json` 记录 20 份题面和 110 份 CSV 的散列。转换程序只允许读取 `题面.md` 和 `data/*.csv`，不把 `答案.md` 或参考程序交给运行中的模型。保留原有业务条件和数值，不人为删除规则。

本批问题允许从题面自由声明整数、二元、连续及辅助变量。因此本地适配在原有 Standard / SWAgent 控制流程外接入通用变量 JSON IR 和同一 COPT 求解后端。两方法的输入、骨干与预算相同；SWAgent 的信息表和 UPDATE 流程保留，Standard 使用已有的 `legacy_knowledge_v1` 协议。完整评分定义见 `SCORING_PROTOCOL.md`。

文件与流程：

- `convert_public_cases.py`：确定性输入转换与来源清单。
- `free_variable_adapter.py`、`copt_solver.py`：原控制流程的变量／求解适配。
- `run_batch.py`、`run_worker.py`：准备配对输入、记录代码散列、执行并保存轨迹。
- `batches/smoke_b01_v1/`：独立接口试跑，不计入正式成绩。
- `batches/main20_v1/`：全部 20 题 × 两方法，每题每方法一次；技术和模型失败都保留在分母中。
- `../score_orlm_runs.py`：离线评分，记录最优目标值匹配和运行状态。
- `../verify_orlm_batch.py`：完成后核查输入一致性、代码／来源散列、实际模型身份及访问日志。

在活动项目环境中可运行：

```powershell
$env:PYTHONUTF8='1'
python rebuttal/20261116/orlm_c3/convert_public_cases.py
python rebuttal/20261116/orlm_c3/run_batch.py --name NEW_UNIQUE_BATCH --workers 8 --check-isolation --run
python rebuttal/20261116/score_orlm_runs.py NEW_UNIQUE_BATCH
python rebuttal/20261116/verify_orlm_batch.py NEW_UNIQUE_BATCH
```

这些脚本是当前迁移后本地项目的运行记录，依赖配套的 `agent/`、`reevaluation/`、已有历史配置、COPT 环境和本机凭据。公开仓库现有运行时不一定与本地这次运行的散列完全一致；不能仅凭这几个新增文件声称任意干净 checkout 可以直接重跑。模型实际使用的代码文件散列保存在 batch manifest 中。凭据文件和含本机凭据配置的运行文件不纳入本次发布包。

实验 worker 在载入公开输入后限制其对项目根目录中其他数据文件的访问，并保存探针及访问记录；没有提供模型可调用的本地文件／代码执行工具。这是本批已知数据路径的隔离措施，不是操作系统级沙箱。离线参考求解和评分在独立进程中进行。
