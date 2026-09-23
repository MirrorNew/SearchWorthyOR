# SearchWorthyOR

SearchWorthyOR研究优化Agent如何主动查找外部规则、判断规则是否适用于当前任务，并把证据落实到数学模型与最终决策。

本仓库发布 **SearchWorthy Agent `i01-lite-007-c2fix-002-format001`** 和 **SearchWorthyOR v1.6.2** 数据集。更新日期：2026年9月23日。

## 仓库内容

```text
agent/                         当前Agent源码与固定运行配置
  lite_worker.py               单题运行与输入访问隔离
  searchworthy/table_loop.py   信息表、规则获取与模型更新
  searchworthy/api_lite.py     模型与搜索调用
  searchworthy/page_read.py    网页和PDF读取
  searchworthy/compiler.py    数学模型编译
  adapters/solver.py           Gurobi求解
datasets/SearchWorthyOR-v1.6.2/
  public/                     公开任务与题面
  private/                    评分答案、规则依据和适用性记录
  models/                     参考Base/Full模型
scripts/
  run_case.py                 可迁移的单题启动入口
  validate_release.py         离线源码和数据校验
release_manifest.json          发布版本与文件对应关系
```

共120个来源任务、360题，每个任务对应C1、C2、C3三个条件。构造方式、来源和原有数据校验说明见 [数据集README](datasets/SearchWorthyOR-v1.6.2/README.md)。

`private` 表示**不向推理Agent开放的评分材料**，不是GitHub访问权限。运行入口只提取公开题面、公开输出格式和题号；C1/C2/C3标签、参考规则及Gold不能传给Agent。

本仓库只保留当前Agent和这一版数据集。Baseline、自研策略对照、四模型诊断程序、大型实验记录、旧Agent快照和论文工作稿不在本次发布范围内。`agent/searchworthy/direct_agent.py` 是当前主流程所导入的题面与证据处理依赖，不是Direct对照实验程序。

## 安装

使用Python 3.12，在独立环境中安装依赖：

```powershell
python -m pip install -r requirements.txt
```

需要可用的Gurobi许可证。依赖版本取自打包环境；没有把许可证或API凭据放入仓库。

模型和搜索沿用树标标API，模型为 `gpt-5.6-luna / xhigh / temperature=1`。每题预算为12次模型调用、3次搜索、6次网页读取、1200秒总时间；具体规则以 `agent/configs/i01_lite_runtime.json` 和源码为准。不要为重跑已有设置而直接替换provider或模型。

复制 `.env.example` 为 `.env` 并填入自己的 `OPENOR_API_KEY`，或在环境变量中设置它。`.env` 与运行输出已加入Git忽略列表。

## 检查文件

```powershell
python -B scripts/validate_release.py
```

此命令只用Python标准库检查源码与数据，无模型、搜索或求解器调用。

## 运行一题

先准备公开输入和独立运行目录。下面的题号来自公开数据：

```powershell
python -B scripts/run_case.py --eval-id SWOR-E-3CB1FDA1E9C064C6BED9 --output runs/prepared_case
```

默认只准备文件。需要真实调用模型和搜索时，使用一个新的输出目录并显式加 `--run`：

```powershell
python -B scripts/run_case.py --eval-id SWOR-E-3CB1FDA1E9C064C6BED9 --output runs/live_case --run
```

程序不会覆盖已有目录。输出位于该目录的 `cases/<eval_id>/`，包含最终结果、输入、模型与搜索请求、响应、证据读取和求解记录。运行失败也应保留原记录，不按答案是否正确选择重跑。

安装依赖后，还可在仓库内的新目录检查原worker的访问隔离：

```powershell
python -B scripts/run_case.py --eval-id SWOR-E-3CB1FDA1E9C064C6BED9 --output runs/isolation_check --check-isolation
```

该检查不执行模型、搜索或求解。启动脚本只准备公开输入、路径和配置；Agent的提示、算法、预算及判定逻辑与所收录源码一致。

## 版本与实验范围

发布源码来自冻结版本 `aa407f7cc03618ed77ac9b9e5d2c093176c10d1bd45eb6c6b1bcc0b7978a786f`。除省略本机凭据配置和旧Smoke配置外，所收录的Agent与数据文件保持来源字节；新增的两个脚本负责启动和离线检查。

已有SWAgent **253/360** 是三份代码、不同执行渠道选中记录的汇总，并非本仓库版本从头完成360题的结果。本仓库不发布大型运行档案，也不把文件校验或单题访问检查作为新的全量实验成绩。冻结代码的完整重跑和匹配消融仍需单独执行。

数据集原有数学校验检查了240个Base/Full模型；这证明给定模型与参考解的算术一致性，不替代对所有规则含义与适用性的人工审核。原有审核范围与限制保留在数据集文档中。
