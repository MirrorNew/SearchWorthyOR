# 来源与实现索引

## 1. 当前实验实现（以代码为准）

- [实验 README](../../README_zh.md)
- [冻结配置](../../EXPERIMENT_CONFIG.json)
- [Direct/Search-First 核心 pipeline](../../scripts/gated_search_pipeline.py)
- [hosted search 与网页打开](../../scripts/web_retrieval.py)
- [CoE/OptiMUS adapter](../../scripts/run_local.py)
- [optiminer-training-free adapter](../../scripts/run_optiminer.py)
- [training-free opaque harness](../../scripts/prepare_harness.py)
- [统一结果与状态](../../scripts/common.py)
- [统一评分](../../scripts/score_report.py)
- [Smoke 验证汇总](../../reports/smoke_validation_summary.json)

## 2. 五个 baseline 对应的原始研究来源

1. **Chain-of-Experts (CoE)** — Xiao et al., “Chain-of-Experts: When LLMs Meet Complex Operations Research Problems,” ICLR 2024. [OpenReview PDF](https://openreview.net/pdf?id=HobyL1B9CZ)

2. **OptiMUS** — AhmadiTeshnizi et al., “OptiMUS: Scalable Optimization Modeling with (MI)LP Solvers and Large Language Models,” 2024. [arXiv:2402.10172](https://arxiv.org/abs/2402.10172)

3. **OptiMUS-0.3** — “OptiMUS-0.3: Using Large Language Models to Model and Solve Optimization Problems at Scale,” latest arXiv version consulted. [arXiv:2407.19633](https://arxiv.org/abs/2407.19633)

4. **Opt-Miner** — “Opt-Miner: Empowering Information-Seeking Agent with Tree-Guided Data Synthesis for Optimization Modeling,” ICML 2026. [MIRA Lab publication page](https://miralab.ai/publication/icml-2026-opt-miner/)

注意：本实验名为 `optiminer-training-free` 的方法不是官方训练版 Opt-Miner，二者必须分开表述。

## 3. 与“何时检索”相关的代表性工作

这些工作说明“让模型按需检索”本身已有充分先例；下一版方法需要提出 OR-specific 的搜索授权机制。

- Asai et al., **Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection**. [arXiv:2310.11511](https://arxiv.org/abs/2310.11511)
- Jeong et al., **Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity**. [arXiv:2403.14403](https://arxiv.org/abs/2403.14403)
- Jiang et al., **Active Retrieval Augmented Generation** (FLARE). [arXiv:2305.06983](https://arxiv.org/abs/2305.06983)

## 4. 引用边界

- 论文用于解释原方法和研究空白。
- 本实验实际配置只能由本仓库代码、配置和日志证明。
- Smoke 只证明链路和失败分类可运行；Formal 未运行前，不得写 V1.5.1 性能排名。
- 未来 Agent 的 GapCard、Search Authorization Certificate、EvidenceCard 和 Proof-Carrying Patch 均是候选研究设计，不是当前 baseline 已有模块。
