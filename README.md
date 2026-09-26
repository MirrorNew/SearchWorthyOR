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
## 安装

使用Python 3.12，在独立环境中安装依赖：

```powershell
python -m pip install -r requirements.txt
```

需要可用的Gurobi许可证。依赖版本取自打包环境；没有把许可证或API凭据放入仓库。

模型和搜索沿用树标标API，模型为 `gpt-5.6-luna / xhigh / temperature=1`。每题预算为12次模型调用、3次搜索、6次网页读取、1200秒总时间；具体规则以 `agent/configs/i01_lite_runtime.json` 和源码为准。不要为重跑已有设置而直接替换provider或模型。

复制 `.env.example` 为 `.env` 并填入自己的 `OPENOR_API_KEY`，或在环境变量中设置它。`.env` 与运行输出已加入Git忽略列表。
