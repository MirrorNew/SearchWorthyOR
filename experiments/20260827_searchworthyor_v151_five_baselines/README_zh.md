# SearchWorthyOR V1.5.1：五个 baseline 实验协议

本目录适配 SearchWorthyOR V1.5.1 的 120 个源任务、240 个公开 case（每题 C1/C2）和五种方法，共 1200 个正式实验实例。所有 LLM 调用固定为 Shubiaobiao：`gpt-5.6-luna / xhigh / temperature=1`，不允许 provider fallback。公开 `prompt_zh` 是模型输入；`private/selected_gold.jsonl` 仅供最终 scorer 使用。

## 五条方法链路

### 1. Direct-v2 / Chain1：Base-Solve Gated Search

1. 读取公开 `prompt_zh` 与公开 `output_schema`。
2. 生成可检查的 Base 数学模型，包括变量、目标、约束、假设和原生 Gurobi 代码。
3. 实际执行 Base 代码并记录 solver 状态、动作和目标值。只有明确的上游或解析失败才能解释 Base 未完成；不能把文字摘要视为 Base Solve。
4. Search Gate 同时读取原题、Base 模型和 Base Solve 结果，输出 `search_needed`、触发理由、待查现实未知量和第一条查询。第一轮搜索不是强制的。
5. 若不搜索，仍进入 Final Model + Solve；若搜索，则按共享预算检索、打开网页、核验逐字证据，再进入 Final。
6. Final 只修改证据支持的必要部分，重新生成数学模型、执行求解，并记录 Base 与 Final 的决策是否改变。
7. 检索不完整或页面失败不会跳过 Final；检索质量与最终建模/求解状态分别报告。

### 2. Search-First / Chain2：Gated Raw-NL

1. Search Gate 只读取公开 `prompt_zh`，并被明确禁止提前建模。
2. Gate 输出与 Direct 相同的四个字段；第一轮搜索同样不是强制的。
3. 若触发搜索，使用与 Direct 完全相同的 Shubiaobiao hosted-search、查询预算、页面预算和证据检查。
4. 已核验的信息按自然语言证据包传给最终模型：`SOURCE_URL + PUBLISHER + VERBATIM_EVIDENCE`。这里拼接的是来源地址、发布主体和已在网页正文中逐字匹配的证据，不拼接 Gold。
5. 一次性生成最终数学模型并实际求解。即使 `evidence_sufficient=false` 或页面全部打不开，也必须完成 Final 尝试并单独保留检索失败状态。

### 3. CoE

使用原生 Conductor → Experts → Reducer 流程，不赋予网页搜索权限。LLM 请求经本地兼容层发送到 Shubiaobiao；外部 CoE 仓库只读，本目录只保存 V1.5.1 输入适配和统一输出转换。

### 4. OptiMUS

使用原生 OR 建模、代码生成和求解流程，不赋予网页搜索权限。LLM 请求发送到 Shubiaobiao；外部 OptiMUS 仓库只读，本目录负责 V1.5.1 输入与输出契约适配。

### 5. optiminer-training-free

使用本地 training-free agent loop。LLM 请求仍发送到 Shubiaobiao；方法原生检索权限仅为 `arxiv_document`，不替换成 Direct/Search-First 的 hosted web search，也不冒充官方训练版 Opt-Miner。原 runner 只读，本目录保存 V1.5.1 benchmark 映射与统一结果。

## Direct 与 Search-First 的共享联网协议

- Hosted search：Shubiaobiao `/responses` + `web_search`。
- 每个 case 最多 3 次查询；每次只执行一个规划查询。
- 每次最多暴露 6 条结果、最多尝试打开 6 页、最多计入 3 个成功可读页面。
- 每个 case 最多 18 次页面打开尝试、最多 9 个成功可读页面。
- 打开失败的页面只进入失败诊断，不占成功页面预算。
- 对结果执行查询相关性和显式 `site:` 域约束检查；对候选证据执行 URL、发布者、正文逐字匹配与问题原子覆盖检查。
- 最多三轮的原因不是“同一大查询机械重复”，而是第一轮查最关键未知量，后续轮次根据未覆盖的事实原子生成更有目的的 continuation query。

`Hosted search 成功`、`网页 HTTP 可访问`、`正文可抽取`、`证据相关`、`逐字证据核验通过`、`证据充分` 是不同层级。Smoke 中观察到的网页失败均为 `PAGE_EMPTY_CONTENT`，不应笼统记为 Shubiaobiao 联网失败。

## 运行与门禁

PowerShell 示例（解释器按本机环境替换）：

```powershell
$py = 'E:\my_evns\py312_torch28\python.exe'
& $py scripts/prepare_harness.py --check
& $py scripts/preflight.py
& $py scripts/offline_gate.py
& $py scripts/run_all_parallel.py --phase smoke
& $py scripts/validate_phase.py --phase smoke
& $py scripts/run_all_parallel.py --phase formal
& $py scripts/score_report.py
```

首次运行先复制 `.env.example` 为 `.env.local` 并仅在本地填写 Shubiaobiao key。可选环境变量 `SWOR_PYTHON`、`COE_ROOT`、`OPTIMUS_ROOT` 和 `OPTIMINER_RUNNER` 用于指定本机解释器与三个外部原生方法的位置；这些路径不会改变锁定的 Shubiaobiao provider 或检索权限。

Formal 在启动前强制读取通过的 preflight 与 Smoke gate。Smoke 固定为 `SWOR-R001-C1/C2 × 5 methods = 10 instances`；Formal 固定为 `240 cases × 5 methods = 1200 instances`，不复用旧版本结果。

## 当前 Smoke 结果

- 严格协议门禁：PASS，10/10 终态输出，0 配置违规、0 Gold 泄漏、0 API key 泄漏、0 身份错配。
- Direct：2/2 `OK`，两个 case 均完成真实 Base Solve 和 Final Solve。
- Search-First：2/2 `OK`，两个 case 均完成 Final Solve；其中一个 case 页面正文不可抽取，但没有跳过最终求解。
- optiminer-training-free：2/2 `OK`。
- CoE：1 `OK`、1 `OUTPUT_CONTRACT_FAILURE`。
- OptiMUS：2 `OUTPUT_CONTRACT_FAILURE`。

后两项是模型在原生方法下未满足 V1.5.1 输出契约的 Smoke 观测，不是 runner 崩溃，也不能手工改成成功。Smoke 只验证链路可运行和失败可归因，不代表五种方法的正式性能结论。

## 架构与 Idea 交接文档

面向协作者的五个 baseline 详细架构、Direct/Search-First 对照、联网失败分层、已知漏洞和下一版 Agent 科学问题，见 [`docs/five_baselines_handoff/`](docs/five_baselines_handoff/README.md)。文档严格区分原论文方法、当前实际配置和未来候选设计；Formal 未运行前不包含性能优劣结论。

## 上传安全边界

`.env.local`、`preflight/` 和 `runs/` 不进入 GitHub，API key 与完整上游请求轨迹不得提交。本仓库维护者明确选择公开完整审计版，因此 `private/selected_gold.jsonl` 作为 scorer 角色文件被显式提交；`private` 表示运行时不可见，不表示 GitHub 保密。任何读过该文件、数据集 `private/`、`models/` 或修复记录的模型/开发者，都不能在这 240 个 case 上声称隐藏测试或无污染结果。
