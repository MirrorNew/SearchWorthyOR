"""Create immutable writing and full-evidence handoff ZIPs from the local project."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
STAMP = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
OUT = BASE / ("coauthor_handoff_" + STAMP)
OUT.mkdir(exist_ok=False)
PROJECT = "SWAgent-for-ICLR/"
SENSITIVE = re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
selected = {}
excluded = []


def add(path):
    if not path.is_file():
        return
    rel = path.relative_to(ROOT).as_posix()
    if any(p in {".git", "__pycache__", ".venv", "node_modules"} for p in path.parts):
        return
    name = path.name.lower()
    config = name == "config.json" or (name.startswith("config.") and path.suffix.lower() in {".json", ".yaml", ".yml"})
    if config or name.startswith(".env") or path.suffix.lower() in {".dpapi", ".lic", ".key", ".pem", ".pyc"}:
        excluded.append({"file": rel, "reason": "configuration, credential, license, or cache excluded"})
        return
    selected[rel] = path


def tree(path):
    for file in path.rglob("*"):
        add(file)


for file in BASE.iterdir():
    if file.is_file() and file.suffix in {".md", ".json", ".py"}:
        add(file)
for name in ["dqz1_prior", "full_model_audit", "orlm_c3", "orlm_reference", "SFT1991_sample20"]:
    tree(BASE / name)
for rel in ["datasets/SearchWorthyOR-v1.6.3", "analysis/rebuttal_dqz1_evidence_20261114", "agent", "reevaluation"]:
    tree(ROOT / rel)
for name in ["prompt_zh.txt", "runner.py", "solver.py"]:
    add(ROOT / "SearchWorthy_Submission_20260923/code/e1_three_models" / name)
add(ROOT / "rebuttal/20261114/SearchWorthy_revise_20261114.pdf")
add(ROOT / "rebuttal/20261114/SearchWorthy_revise_source_20261114.zip")

with (BASE / "full_model_audit/independent_model_equivalence_records.csv").open(encoding="utf-8-sig", newline="") as handle:
    audit_rows = list(csv.DictReader(handle))
assert len(audit_rows) == 600
case_dirs = {(ROOT / row["model_file"]).parent for row in audit_rows}
assert len(case_dirs) == 600
for case in case_dirs:
    tree(case)
    for name in ["input.json", "execution.json", "manifest.json"]:
        add(case.parent / name)

draft_path = BASE / "dqz1_followup_complete_ZH.md"
draft_bytes = draft_path.read_bytes()
draft = draft_bytes.decode("utf-8")
section_a = draft.split("## **（b）", 1)[0]
assert "## **（a）" in section_a and "## **（b）" in draft
draft_hash = hashlib.sha256(draft_bytes).hexdigest()
status = {
    "snapshot_time_asia_shanghai": STAMP,
    "authoritative_chinese": "01_最新中文回复_保留a_改写b.md",
    "source_file": draft_path.relative_to(ROOT).as_posix(),
    "source_sha256": draft_hash,
    "section_a_and_opening_sha256_utf8": hashlib.sha256(section_a.encode("utf-8")).hexdigest(),
    "instruction": "Preserve the author's (a); coauthor should revise (b)'s wording and evidence presentation. No new experiment or score changes requested.",
    "english_status": "Reference draft; not synchronized with the author's latest Chinese edits.",
    "c2_records": len(audit_rows),
    "c2_case_directories": len(case_dirs),
    "c3_formal_runs": 40,
}

readme = """# 给 coauthor：dqz1 后续回复表述交接

## 先读什么、改哪里

1. 打开 `01_最新中文回复_保留a_改写b.md`。这是作者最新中文稿的逐字快照；**（a）由作者整理完成，保留；本轮重点是重组、润色（b）**。原稿的表4–6、注释及现有表述全部保留，供你决定如何呈现。
2. 阅读 `03_审稿人最新回复.md`，然后看 `04_证据导航与口径.md`。
3. `02_英文参考稿_未同步最新中文.md` 只作写法参考，不覆盖中文稿的最新修改。中文（b）定稿后再同步英文。

## 作者确定的主线

- 55.33%是相对冻结参考的严格全模型等价率，不能直接解释为生成模型中错误／缺失约束的比例，也不能直接换算成外部规则发现与纳入的失败率。
- 本文贡献不止一个agent的最终成绩；发现和定义问题、构建可评测基准同样是核心贡献。结合这些贡献和已验证的建模进展评价方法。
- 数据展示有侧重点：强调同骨干双指标均提高22个百分点、156次完整模型修正、另28次最优解修正、33条完整最优行动集一致，以及5条有数学证书的安全约简。
- 结尾回应审稿人：希望更新轨迹和逐例核验证据增强其对数学模型更新可靠性的信心。
- 不把完整审计清单一股脑放进正文；完整记录留作核查依据。选例不能把局部结论扩展成全部模型正确，也不能改动原始分母和成绩。

## 本包中的版本与数据

`SWAgent-for-ICLR/` 保留原项目相对路径，便于定位脚本、数据与运行记录。

- 最新中文稿、英文参考稿、原始审稿意见、此前dqz1 rebuttal和当日分析材料。
- C2两方法共600条记录的独立复算；SWAgent与Standard各33条重点子集审计；全量模型、参考模型、反例和初始／最终更新轨迹。
- 20题C3补充实验的输入、来源CSV及答案、生成模型、求解记录、逐题成绩、参考程序与交叉求解结果；首题smoke独立保存，不混入正式成绩。
- REAL6来源材料及“8天、12产品”描述性改写示例；该版本未运行新实验。
- 2026-11-14论文PDF和源码zip作为背景，不将其标成与最新中文稿自动同步的版本。

## 两个压缩包

**writing_package**：用于改稿与大多数数字复核，包含上面的文稿、数据、模型、semantic/trace等证据；不含体积最大的api/reads/search目录。

**complete_evidence**：在同一结构上补齐原始API请求／响应和检索／读取记录；完整请求到补丁的载荷复核需用这一包。

两包均不包含Git仓库、环境、凭据、许可证和运行config文件。协议、模型、预算和代码散列保存在manifest与报告中。离线评分及模型审计可按相对路径定位；联网重跑需要另配环境和凭据。原始config未分发，因此不要在本包中直接要求原config字节散列复核通过。每个包根目录的`MANIFEST.json`给出所有科学材料的SHA-256。

## 交回什么

请交回修改后的中文（b）；（a）保持作者版本。如同步英文，请标记为与此次中文（b）同步的版本。改动主要围绕论证顺序、表格取舍、案例解释及结尾，不改原始结果。
"""

navigation = """# 证据导航与口径

所有下述路径均相对于 `SWAgent-for-ICLR/`。

| 写作时使用的事实 | 数字／范围 | 直接证据 |
|---|---|---|
| C2同骨干比较 | Standard答案133/300、模型100/300；SWAgent答案199/300、模型166/300 | `rebuttal/20261116/full_model_audit/independent_model_equivalence_summary.json`、同名records.csv |
| 三次运行的模型提升 | +24、+21、+21个百分点 | `rebuttal/20261116/full_model_audit/focused_evidence_summary.json` |
| 完整模型修正 | 156次FAIL→PASS；初始PASS14、最终PASS166，净增152 | `rebuttal/20261116/full_model_audit/independent_model_equivalence_report_zh.md` |
| 外部正文与实际补丁可追踪 | 上述156次均核实实际请求含正文、匹配响应被消费、非空补丁接受 | `rebuttal/20261116/full_model_audit/model_payload_validation.json` |
| 另28次优化改进 | 与156次不重叠；修正最优值及完整最优行动集 | `rebuttal/20261116/full_model_audit/semantic_33_run_index.csv`、`semantic_optima_recompute.json` |
| SWAgent答案正确但严格不等价 | 全部33次、18个源任务；33/33完整最优行动集相同 | `rebuttal/20261116/full_model_audit/semantic_fullmodel_case_audit_20261116.md` |
| 安全优化约简 | R025三次、R103一次、R105一次；10个被删组合均有同一业务选择、更优的保留替代 | `rebuttal/20261116/full_model_audit/dominance_audit.json`、`dominance_audit_zh.md` |
| SWAgent语义子集 | 7参考边界、5安全约简、9明确错误、3混合、9未定；确认含错12/33 | `rebuttal/20261116/full_model_audit/semantic_33_run_index.csv`及语义报告 |
| Standard语义子集（新增材料） | 33次、14源任务；6确认含错、12安全约简、6参考边界、9未定 | `rebuttal/20261116/full_model_audit/standard_33_semantic_audit_20261116.md`及同名JSON |
| C3正式试验 | Standard17/20=85%，SWAgent18/20=90%；全部失败保留分母 | `rebuttal/20261116/orlm_c3/RESULTS_20261116.md`、`batches/main20_v1/objective_scores.csv` |
| C3参考与输入 | 20题、110张CSV；20个参考COPT最优，19个跨求解器一致，1个Gurobi许可证规模限制 | `rebuttal/20261116/orlm_c3/source_manifest.json`、`orlm_reference/reference_results.json`与`reference_crosscheck.json` |
| 描述性输入示例 | REAL_RB-CO-00，8天、12产品；仅改写展示，未跑新实验 | `rebuttal/20261116/dqz1_第一点_业务描述还原示例.md`、`real6_example_provenance.json` |

## 表述时需要保持的区分

1. 300是每方法100源任务×3次运行，不是300个独立源任务；33也是运行数。156与28是两类轨迹，不能写成184个完整正确模型。
2. 33条完整最优行动集相同不等于33条全部约束语义正确。5条约简证书限于给定任务的约束与成本；原55.33%不重算。
3. 最新中文表4把各自33条条件子集的确认错误比例与300条全量成绩放在一起。不同方法的33条任务组成不同，不能把6/33与12/33解释成全量可靠性排名。为保持论证重点，可把该列移到单独诊断或核查材料；数据仍完整保留。
4. 156/156的请求到补丁核验是过程证据，不单独证明每份外部正文都相关／适用，也不替代检索因果作用的消融。
5. C3的85%/90%是最优目标值匹配，使用自由变量IR与COPT适配。原始运行协议在 `orlm_c3/SCORING_PROTOCOL.md`；不把它写成全模型正确率。
6. 最新（a）的来源陈述按作者稿保留。本包不额外认证其客户来源；20题C3与REAL6是两套材料。REAL6原文件明确写数值独立合成，不能用它冒充20题成绩对应的客户原始实例。是否使用真实业务／脱敏等来源措辞，应由作者持有的来源证明支持。

## 复核入口

- 新的完整C2复算：`rebuttal/20261116/full_model_audit/independent_model_equivalence_audit.py`。
- 原先（20261114）的统计与载荷源记录：`analysis/rebuttal_dqz1_evidence_20261114/`。
- 全部冻结题面、规则、gold、参考IR：`datasets/SearchWorthyOR-v1.6.3/`。
- C2原始案例目录由records.csv中的`model_file`、`initial_model_file`和`result_file`定位。
- C3离线评分：在项目根运行 `python rebuttal/20261116/score_orlm_runs.py main20_v1`。
- 历史`publication_manifest.json`可能早于作者后来改稿；本次快照的权威清单为本包根目录`MANIFEST.json`及`AUTHOR_DRAFT_STATUS.json`。
"""

front = {
    "00_先读交接说明.md": readme.encode("utf-8"),
    "01_最新中文回复_保留a_改写b.md": draft_bytes,
    "02_英文参考稿_未同步最新中文.md": (BASE / "dqz1_followup_complete_EN.md").read_bytes(),
    "03_审稿人最新回复.md": (BASE / "dqz1_followup_received.md").read_bytes(),
    "04_证据导航与口径.md": navigation.encode("utf-8"),
    "AUTHOR_DRAFT_STATUS.json": (json.dumps(status, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
}
for name, content in front.items():
    (OUT / name).write_bytes(content)


def raw_only(rel):
    parts = Path(rel).parts
    return any(p in {"api", "reads", "search"} for p in parts) and ("experiments" in parts or "batches" in parts)


paths = {"writing_package": OUT / ("dqz1_coauthor_writing_package_" + STAMP + ".zip"),
         "complete_evidence": OUT / ("dqz1_coauthor_complete_evidence_" + STAMP + ".zip")}
manifests = {name: [] for name in paths}
archives = {name: zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=4, allowZip64=True) for name, path in paths.items()}
total_bytes = 0
try:
    for archive in archives.values():
        for name, data in front.items():
            archive.writestr(name, data)
    for index, (rel, source) in enumerate(sorted(selected.items()), 1):
        stat = source.stat()
        data = source.read_bytes()
        if SENSITIVE.search(data):
            raise RuntimeError("Potential secret detected; archive not releasable: " + rel)
        assert source.stat().st_mtime_ns == stat.st_mtime_ns and len(data) == stat.st_size, rel
        sha = hashlib.sha256(data).hexdigest()
        entry = {"file": PROJECT + rel, "bytes": len(data), "sha256": sha}
        for kind, archive in archives.items():
            if kind == "writing_package" and raw_only(rel):
                continue
            archive.writestr(PROJECT + rel, data)
            manifests[kind].append(entry)
        total_bytes += len(data)
        if index % 1000 == 0:
            print(json.dumps({"processed_files": index, "total_files": len(selected), "source_MB": round(total_bytes / 1e6, 1)}), flush=True)
    assert hashlib.sha256(draft_path.read_bytes()).hexdigest() == draft_hash, "Author draft changed during packaging"
    for kind, archive in archives.items():
        manifest = {"snapshot_time_asia_shanghai": STAMP, "package": kind,
                    "source_project": "SWAgent-for-ICLR", "scientific_files": manifests[kind],
                    "front_matter": [{"file": n, "bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()} for n, d in front.items()],
                    "excluded_configuration_files": excluded,
                    "raw_directories_omitted": ["api", "reads", "search"] if kind == "writing_package" else []}
        payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        archive.writestr("MANIFEST.json", payload)
        (OUT / (kind + "_manifest.json")).write_bytes(payload)
finally:
    for archive in archives.values():
        archive.close()

delivery = {"snapshot_time_asia_shanghai": STAMP, "draft_sha256": draft_hash, "packages": []}
for kind, path in paths.items():
    print("Validating " + kind, flush=True)
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        assert archive.testzip() is None
        assert archive.read("01_最新中文回复_保留a_改写b.md") == draft_bytes
        for entry in manifests[kind]:
            data = archive.read(entry["file"])
            assert len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"], entry["file"]
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    delivery["packages"].append({"kind": kind, "file": path.name, "bytes": path.stat().st_size,
                                 "scientific_files": len(manifests[kind]),
                                 "uncompressed_scientific_bytes": sum(r["bytes"] for r in manifests[kind]),
                                 "sha256": h.hexdigest(), "crc_and_all_file_hashes_verified": True})
delivery["author_draft_unchanged_at_end"] = hashlib.sha256(draft_path.read_bytes()).hexdigest() == draft_hash
assert delivery["author_draft_unchanged_at_end"]
(OUT / "DELIVERY.json").write_text(json.dumps(delivery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output_directory": str(OUT), **delivery}, ensure_ascii=False, indent=2), flush=True)
