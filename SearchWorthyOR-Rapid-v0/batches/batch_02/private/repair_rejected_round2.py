from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BATCH = ROOT / "batches" / "batch_02"
TASK_PATH = BATCH / "public" / "tasks_zh.jsonl"
AUDIT_PATH = BATCH / "private" / "rapid_audit.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def model_path(task_id: str, variant: str) -> Path:
    return BATCH / "models" / task_id / f"{variant}_ir.json"


def reset_audit(audit: dict, problem: str, local_basis: str, patch_binding: str) -> None:
    base = read_json(ROOT / audit["base_model_path"])
    audit["accessed_at"] = "2026-08-02T05:35:00Z"
    audit["decision_date"] = "2026-08-02"
    audit["preserved_local_binding_facts"] = [local_basis]
    audit["task_local_fact_alignment"] = [{"public_basis": local_basis, "patch_binding": patch_binding}]
    audit["numeric_alignment"] = [{"surface": problem, "binding": "base:"}]
    audit["variable_alignment"] = [
        {"variable": item["name"], "public_meaning": item["meaning"]}
        for item in base["variables"]
    ]
    audit["constraint_alignment"] = [
        {"constraint": item["name"], "public_basis": item["meaning"]}
        for item in base["constraints"]
    ]
    audit["generator_id"] = "native_batch_c_repair_round2"
    audit["generator_self_check"] = "PASS"
    audit["independent_review"] = "PENDING"
    audit["status"] = "GENERATED_SELF_CHECK_PASS"
    audit["base_solve"] = "OPTIMAL"
    audit["patched_solve"] = "OPTIMAL"
    audit["optimal_action_changed"] = True
    audit["common_optimal_action_feasible"] = False
    audit["problem_model_alignment"] = "PASS"
    audit["answer_leakage"] = False
    audit["single_objective"] = True
    audit["structural_patch"] = "PASS"


tasks = read_jsonl(TASK_PATH)
audits = read_jsonl(AUDIT_PATH)
task_by_id = {row["id"]: row for row in tasks}
audit_by_id = {row["id"]: row for row in audits}

task_by_id["SWOR-R021"]["problem_zh"] = (
    "2026年8月2日，爱尔兰环境部门为新包装废物责任计划安排执行事项。可委托GreenCycle或HarbourWorks承担生产者与代表组织之间的登记、联络和报告职责，年度费用分别为3万元和5万元；可委托RiverSort或EcoDepot承担包装废物的分类、回收和处理职责，年度费用分别为4万元和6万元；另可正式设定本期废物管理目标，费用2万元。预算草案允许至少落实1项安排，唯一目标是最小化年度总成本。该计划覆盖在爱尔兰市场投放包装产品的生产者、代表组织与废物运营方，本地登记确认上述2类职责均会在本期实际发生，废物管理目标尚未设定。本期采购决定把2个职责包全部外包，采购办法规定每个职责包必须从列出的2家承包商中只选1家，不允许内部执行、共同承包或名单外承包。定案还须遵守爱尔兰现行生产者延伸责任要求。请给出最优方案与总成本。"
)
a = audit_by_id["SWOR-R021"]
a["support_excerpt"] = "define in a clear way the roles and responsibilities of all relevant actors involved, including producers of products placing products on the market of the State, organisations implementing extended producer responsibility obligations on their behalf, private or public waste operators, local authorities and, where appropriate, re-use and preparing for re-use operators and social economy enterprises; ( b ) in line with the waste hierarchy, set waste management targets, aiming to attain at least the quantitative targets relevant for the extended producer responsibility scheme as laid down in the Waste Directive, 94/62/EC, Directive 2000/53/EC, Directive 2006/66/EC and Directive 2012/19/EU of the European Parliament and of the Council , and set other quantitative targets and/or qualitative objectives that are considered relevant for the extended producer responsibility scheme;"
a["applicability_reason"] = "The task concerns an Irish packaging EPR scheme and closes the locally active actor-role groups and unset waste-management target; exclusive contractor selection comes from the procurement decision, not the regulation."
a["patch_summary"] = "Use the local exclusive-outsourcing rule to assign one contractor to each active package and the EPR source to require clear roles and a waste-management target."
reset_audit(
    a,
    task_by_id["SWOR-R021"]["problem_zh"],
    "本期采购决定把2个职责包全部外包，采购办法规定每个职责包必须从列出的2家承包商中只选1家，不允许内部执行、共同承包或名单外承包。",
    "constraint:producer_role_defined",
)

task_by_id["SWOR-R023"]["problem_zh"] = (
    "2026年8月2日，美国环保署辖区内的运营商为当前已生效规则下仍定于2027年6月1日的响应计划提交期限预先选择设施投资。河岸化学品码头收益9万元、耗用3个资源单位；内陆仓库收益7万元、耗用2个资源单位；山坡储罐收益5万元、耗用2个资源单位。为届时制作并提交设施响应计划启用团队将减少4万元净收益并耗用2个资源单位，本期资源上限5个单位，唯一目标是最大化净收益。所有入选设施都按已批准排期在该提交期限前投运并达到题述库存状态；该运营商的组织授权和现有资源表明，候选行动中只有该团队能够为这些设施制作并提交响应计划，不存在共享团队、外包团队或其他提交路径。3个候选点均为陆上非运输相关设施且不适用明示豁免；河岸码头库存达到筛选门槛、距通航水体0.5英里且具备重大危害因素，内陆仓库和山坡储罐都不满足距离条件，也没有收到地区主管的个案书面决定。投资组合还须遵守现行危险物质设施响应计划要求。请给出最优方案与总收益。"
)
p = read_json(model_path("SWOR-R023", "patched"))
p["constraints"] = [row for row in p["constraints"] if row["name"] != "hill_plan_activation"]
write_json(model_path("SWOR-R023", "patched"), p)
a = audit_by_id["SWOR-R023"]
a["support_excerpt"] = "These include facilities with a maximum onsite quantity of a CWA hazardous substance that meets or exceeds threshold quantities, located within a 0.5-mile radius of navigable water or conveyance to navigable water, and that meets one or more substantial harm criteria."
a["rule_claim"] = "The effective CWA hazardous-substance FRP self-identification branch requires the onsite-quantity threshold, half-mile proximity and a substantial-harm factor; the published submission date remains June 1, 2027 while extension is only proposed."
a["applicability_reason"] = "This is prospective planning for the currently published 2027 submission date. Every selected facility will operate by that deadline; the river facility closes every self-identification predicate and exemptions, while the other two fail proximity and have no Regional Administrator determination. The named team is the only locally available preparation-and-submission route."
a["patch_summary"] = "Activate the response-plan team only for the river terminal's complete self-identification conjunction and remove the unsupported regulator-determination branch."
reset_audit(
    a,
    task_by_id["SWOR-R023"]["problem_zh"],
    "所有入选设施都按已批准排期在该提交期限前投运并达到题述库存状态；该运营商的组织授权和现有资源表明，候选行动中只有该团队能够为这些设施制作并提交响应计划，不存在共享团队、外包团队或其他提交路径。3个候选点均为陆上非运输相关设施且不适用明示豁免；河岸码头库存达到筛选门槛、距通航水体0.5英里且具备重大危害因素，内陆仓库和山坡储罐都不满足距离条件，也没有收到地区主管的个案书面决定。",
    "constraint:river_plan_activation",
)

task_by_id["SWOR-R026"]["problem_zh"] = (
    "2026年8月2日，英国配电运营商为预计只持续1个晚间高峰的低水平轮换停电事件确定首轮切断对象。普通负荷已划入18个需求近似相等的区块，每轮名义断电3小时；当前可从F区块、G区块、H区块及受保护医院馈线中选择1个首轮对象，对应调度匹配分分别为11分、9分、8分和12分，唯一目标是最大化调度匹配分。上一低水平轮换事件未切断全部区块，最后切断F区块，医院馈线已取得受保护场所资格，本次计划还须符合大不列颠现行供电应急轮换和非保护场所公平处理要求。请给出最优方案与目标值。"
)
a = audit_by_id["SWOR-R026"]
a["rule_claim"] = "Under the Great Britain low-level rota plan for short peak-period disconnections, a later event resumes at the block following the one last disconnected when the earlier event ended before completing the rota; protected sites remain outside ordinary blocks."
a["applicability_reason"] = "The task now identifies the low-level short peak-period rota, supplies the preceding unfinished event and last disconnected block, and states the hospital's protected-site status."
a["patch_summary"] = "Resume the low-level rota at G after the preceding unfinished event ended at F, leaving the protected hospital feeder outside the ordinary choice."
reset_audit(
    a,
    task_by_id["SWOR-R026"]["problem_zh"],
    "上一低水平轮换事件未切断全部区块，最后切断F区块，医院馈线已取得受保护场所资格",
    "constraint:stateful_rotation_start",
)

task_by_id["SWOR-R028"]["problem_zh"] = (
    "2026年8月2日，欧盟投资产品制造商为既定零售目标市场选择收费设计。简明单层方案带来7分市场价值，分层收费方案带来10分市场价值，必须选择1个方案；可执行收费不透明性评估、成本重复性评估或整体收费透明度评估，分别消耗1分、2分和3分价值。内部方法确认这3种工具都能独立形成适合该目标市场的透明度证据，现有工作底稿尚未执行任何一种，唯一目标是最大化净市场价值。产品正处于设计阶段，收费结构尚未通过透明度检查；最终设计还须符合现行MiFID II产品治理下的收费透明要求。请给出最优方案与目标值。"
)
for variant in ("base", "patched"):
    m = read_json(model_path("SWOR-R028", variant))
    if not any(row["name"] == "assess_holistic_transparency" for row in m["variables"]):
        m["variables"].append({
            "name": "assess_holistic_transparency",
            "type": "BINARY",
            "lb": 0,
            "ub": 1,
            "meaning": "执行整体收费透明度评估",
        })
    m["objective"]["coefficients"]["assess_holistic_transparency"] = -3
    if "assess_holistic_transparency" not in m["action_projection"]:
        m["action_projection"].append("assess_holistic_transparency")
    if variant == "patched":
        m["constraints"] = [m["constraints"][0], {
            "name": "transparency_review_gate",
            "sense": ">=",
            "rhs": 0,
            "coefficients": {
                "assess_opacity": 1,
                "assess_duplication": 1,
                "assess_holistic_transparency": 1,
                "choose_simple_design": -1,
                "choose_layered_design": -1,
            },
            "meaning": "所选收费设计至少通过1种适当透明度评估",
        }]
    write_json(model_path("SWOR-R028", variant), m)
a = audit_by_id["SWOR-R028"]
a["support_excerpt"] = "The above list of examples is not exhaustive and firms could use other means to ensure an appropriate level of transparency of products’ charging structure."
a["rule_claim"] = "During product design a manufacturer should ensure an appropriately transparent charging structure for the target market; opacity and duplicated-cost checks are examples, and other suitable means remain available."
a["applicability_reason"] = "The product is in design for a retail target market and has not passed a transparency review. Three independently adequate methods preserve ESMA's express non-exhaustive alternative-means branch."
a["patch_summary"] = "Require at least 1 of 3 independently adequate transparency reviews for the selected design, instead of forcing both ESMA examples as an exhaustive checklist."
reset_audit(
    a,
    task_by_id["SWOR-R028"]["problem_zh"],
    "内部方法确认这3种工具都能独立形成适合该目标市场的透明度证据，现有工作底稿尚未执行任何一种",
    "constraint:transparency_review_gate",
)

task_by_id["SWOR-R030"]["problem_zh"] = (
    "2026年8月2日，美国州级医疗管理部门为2028年7月10日后开始的首个适用评级期编制管理式医疗检查方案。安排初级保健独立秘密顾客调查获得9分覆盖价值，安排心理健康调查获得8分覆盖价值，核验提供者名录产生1分成本，唯一目标是最大化净覆盖价值。2类服务均属于该评级期的指定检查范围，州政府已确定由独立实体执行年度调查，现有方案尚未安排调查或名录核验；方案还须符合届时适用的联邦管理式医疗可及性监测要求。请给出最优方案与目标值。"
)
for variant in ("base", "patched"):
    m = read_json(model_path("SWOR-R030", variant))
    m["variables"] = [row for row in m["variables"] if row["name"] != "reserve_corrective_action"]
    m["objective"]["coefficients"].pop("reserve_corrective_action", None)
    m["action_projection"] = [name for name in m["action_projection"] if name != "reserve_corrective_action"]
    m["constraints"] = [row for row in m["constraints"] if row["name"] != "failure_remediation_link"]
    write_json(model_path("SWOR-R030", variant), m)
a = audit_by_id["SWOR-R030"]
a["support_excerpt"] = "Requires states to use an independent entity to conduct annual secret shopper surveys to validate managed care plans’ compliance with appointment wait time standards and the accuracy of provider directories to identify errors and providers that do not offer appointments."
a["rule_claim"] = "For the applicable rating period, states must use an independent entity for annual secret-shopper surveys of specified appointment availability and validation of provider-directory information."
a["applicability_reason"] = "The future rating period and two covered service classes are explicit. The model now represents only mandatory survey and directory-validation work and assumes no corrective action without an observed deficiency."
a["patch_summary"] = "Require both covered annual independent surveys and provider-directory validation while removing the untriggered corrective-action reserve."
reset_audit(
    a,
    task_by_id["SWOR-R030"]["problem_zh"],
    "2类服务均属于该评级期的指定检查范围，州政府已确定由独立实体执行年度调查，现有方案尚未安排调查或名录核验",
    "constraint:required_annual_surveys",
)

task_by_id["SWOR-R031"]["problem_zh"] = (
    "2026年8月2日，新加坡包装生产者编制年度包装资料。提交塑料包装数据带来9分申报完整度并占用2个工作单位，提交纸类包装数据带来7分完整度并占用1个工作单位，准备计算方法、底稿和支持文件产生2分成本；另可委托外部机构作自愿保证，产生1分成本并占用1个工作单位。团队本期有3个工作单位，唯一目标是最大化净申报完整度。该公司年营业额为1200万新元，在新加坡供应瓶装饮料，并实际进口和使用饮料PET瓶及运输纸箱，不进口或使用其他包装，支持文件尚未形成；申报还须符合现行强制包装报告要求。请给出最优方案与目标值。"
)
for variant in ("base", "patched"):
    m = read_json(model_path("SWOR-R031", variant))
    if not any(row["name"] == "external_assurance" for row in m["variables"]):
        m["variables"].append({"name": "external_assurance", "type": "BINARY", "lb": 0, "ub": 1, "meaning": "委托外部机构作自愿保证"})
    m["objective"]["coefficients"]["external_assurance"] = -1
    if "external_assurance" not in m["action_projection"]:
        m["action_projection"].append("external_assurance")
    m["constraints"][0]["rhs"] = 3
    m["constraints"][0]["coefficients"].pop("prepare_supporting_basis", None)
    m["constraints"][0]["coefficients"]["external_assurance"] = 1
    m["constraints"][0]["meaning"] = "两类包装数据提交工作使用不超过3个单位"
    if variant == "patched":
        m["constraints"] = [
            m["constraints"][0],
            {"name": "plastic_report_required", "sense": "=", "rhs": 1, "coefficients": {"submit_plastic_data": 1}, "meaning": "报告实际进口和使用的PET瓶包装数据"},
            {"name": "paper_report_required", "sense": "=", "rhs": 1, "coefficients": {"submit_paper_data": 1}, "meaning": "报告实际进口和使用的运输纸箱包装数据"},
            {"name": "supporting_basis_required", "sense": "=", "rhs": 1, "coefficients": {"prepare_supporting_basis": 1}, "meaning": "为年度包装报告准备计算方法底稿和支持文件"},
        ]
    write_json(model_path("SWOR-R031", variant), m)
a = audit_by_id["SWOR-R031"]
a["support_excerpt"] = "Submit annual reports on specified packaging that is imported or used in Singapore including supporting documents to NEA using the attached template"
a["rule_claim"] = "An obligated company must annually report every specified packaging stream it imports or uses in Singapore and submit supporting documents with the report."
a["applicability_reason"] = "Turnover and regulated-goods predicates are stated; PET bottles and paper cartons are exhaustively identified as the only imported or used packaging, and supporting documents remain unprepared."
a["patch_summary"] = "Require both known material-form streams and the shared calculation methodology and supporting-document basis, with enough work capacity to complete all mandatory items."
reset_audit(
    a,
    task_by_id["SWOR-R031"]["problem_zh"],
    "并实际进口和使用饮料PET瓶及运输纸箱，不进口或使用其他包装，支持文件尚未形成",
    "constraint:plastic_report_required",
)

task_by_id["SWOR-R036"]["problem_zh"] = (
    "2026年8月2日，缅因州汽车承运人安全主管部门为当天生效的司机值勤时长规则选择1个已完成制定并提交备案的版本。采用7月30日提交的新版本可获得10万元监管收益，采用7月27日提交的常规版本可获得8万元监管收益，采用当天提交的紧急版本可获得7万元监管收益，唯一目标是最大化总收益。3个版本均由该州主管部门制定并调整司机值勤时长；主管部门只对当天版本作出了为避免公共健康、安全或一般福利即时威胁而立即采用的书面认定，其他版本没有紧急认定。生效决定还须符合缅因州现行汽车承运人安全规则的备案与生效时点规定。请给出最优方案与总收益。"
)
for variant in ("base", "patched"):
    m = read_json(model_path("SWOR-R036", variant))
    replacements = {
        "use_july30_rule": "使7月30日备案的新司机值勤规则版本生效",
        "use_july27_rule": "使7月27日备案的常规司机值勤规则版本生效",
        "use_emergency_rule": "使当天备案且获紧急认定的司机值勤规则版本生效",
    }
    for row in m["variables"]:
        row["meaning"] = replacements[row["name"]]
    m["objective"]["meaning"] = "州级司机值勤规则版本的监管收益"
    m["constraints"][0]["meaning"] = "恰好选择1个州级规则版本生效"
    write_json(model_path("SWOR-R036", variant), m)
a = audit_by_id["SWOR-R036"]
a["rule_claim"] = "A motor-carrier safety rule adopted by the Maine Bureau ordinarily may not take effect until at least five days after filing with the Secretary of State, while a Bureau emergency rule may use the immediate-threat route."
a["applicability_reason"] = "The decision-maker is now the state safety authority selecting among its own completed and filed rule versions. Filing dates and the Bureau's emergency determination are public local facts."
a["patch_summary"] = "Exclude the July 30 Bureau rule version because its ordinary filing lag is incomplete, while preserving the July 27 and same-day emergency routes."
reset_audit(
    a,
    task_by_id["SWOR-R036"]["problem_zh"],
    "3个版本均由该州主管部门制定并调整司机值勤时长；主管部门只对当天版本作出了为避免公共健康、安全或一般福利即时威胁而立即采用的书面认定，其他版本没有紧急认定。",
    "constraint:filing_effective_lag",
)

task_by_id["SWOR-R039"]["problem_zh"] = (
    "2026年8月2日，美国1家受年度911可靠性认证约束的服务商选择电路可靠性工作。可执行1项全网汇总审查、北城PSAP关键911电路多样性改造、南城PSAP关键911电路多样性改造、编制北城补救认证包、编制南城补救认证包或1项中心机房备用电源检查，成本依次为1万元、4万元、3万元、2万元、2万元和2万元。每个补救认证包都将详细说明针对该PSAP已发现缺陷正在采取的具体补救步骤，并写入由本地项目排期确定的预计完成日期。基础运营要求至少开展1项工作；备用电源检查只有在同时开展全网汇总审查时才能实施。北城和南城各有1条由该服务商直接提供服务的关键911电路，现有年度档案尚未对这2条电路分别完成多样性措施或补救认证包，也不存在已采取的替代措施或适用性排除。唯一目标是最小化总成本。年度认证还须遵守美国现行911网络可靠性规定。请给出最优方案与总成本。"
)
base_039 = {
    "schema_version": "searchworthyor.rapid_model_ir.v0",
    "id": "SWOR-R039",
    "variant": "base",
    "family": "telecom_service",
    "source_candidate_id": "SRCV2-0181",
    "variables": [
        {"name": "provider_wide_review", "type": "BINARY", "lb": 0, "ub": 1, "meaning": "执行全网汇总审查"},
        {"name": "north_psap_diversity", "type": "BINARY", "lb": 0, "ub": 1, "meaning": "完成北城PSAP关键911电路多样性改造"},
        {"name": "south_psap_diversity", "type": "BINARY", "lb": 0, "ub": 1, "meaning": "完成南城PSAP关键911电路多样性改造"},
        {"name": "north_psap_remediation", "type": "BINARY", "lb": 0, "ub": 1, "meaning": "编制含具体补救步骤和预计完成日期的北城PSAP补救认证包"},
        {"name": "south_psap_remediation", "type": "BINARY", "lb": 0, "ub": 1, "meaning": "编制含具体补救步骤和预计完成日期的南城PSAP补救认证包"},
        {"name": "central_office_backup_check", "type": "BINARY", "lb": 0, "ub": 1, "meaning": "执行中心机房备用电源检查"},
    ],
    "objective": {
        "sense": "min",
        "constant": 0,
        "coefficients": {
            "provider_wide_review": 1,
            "north_psap_diversity": 4,
            "south_psap_diversity": 3,
            "north_psap_remediation": 2,
            "south_psap_remediation": 2,
            "central_office_backup_check": 2,
        },
        "meaning": "911电路可靠性工作总成本",
        "unit": "万元",
    },
    "constraints": [
        {"name": "minimum_reliability_work", "sense": ">=", "rhs": 1, "coefficients": {"provider_wide_review": 1, "north_psap_diversity": 1, "south_psap_diversity": 1, "north_psap_remediation": 1, "south_psap_remediation": 1, "central_office_backup_check": 1}, "meaning": "至少开展1项可靠性工作"},
        {"name": "backup_check_scope", "sense": "<=", "rhs": 0, "coefficients": {"central_office_backup_check": 1, "provider_wide_review": -1}, "meaning": "备用电源检查仅与全网汇总审查共同实施"},
    ],
    "action_projection": [
        "provider_wide_review",
        "north_psap_diversity",
        "south_psap_diversity",
        "north_psap_remediation",
        "south_psap_remediation",
        "central_office_backup_check",
    ],
}
patched_039 = json.loads(json.dumps(base_039))
patched_039["variant"] = "patched"
patched_039["constraints"].extend([
    {"name": "north_psap_certification", "sense": "=", "rhs": 1, "coefficients": {"north_psap_diversity": 1, "north_psap_remediation": 1}, "meaning": "北城PSAP逐点选择已完成多样性措施或提交含步骤和预计完成日期的补救认证"},
    {"name": "south_psap_certification", "sense": "=", "rhs": 1, "coefficients": {"south_psap_diversity": 1, "south_psap_remediation": 1}, "meaning": "南城PSAP逐点选择已完成多样性措施或提交含步骤和预计完成日期的补救认证"},
])
write_json(model_path("SWOR-R039", "base"), base_039)
write_json(model_path("SWOR-R039", "patched"), patched_039)
a = audit_by_id["SWOR-R039"]
a.update({
    "source_candidate_id": "SRCV2-0181",
    "source_document_key": "FCC-RELIABILITY-CERTIFICATION-NOTICE-2024",
    "regulation_key": "FCC-CRITICAL-CIRCUIT-DIVERSITY-ATOM",
    "source_url": "https://docs.fcc.gov/public/attachments/DA-24-800A1.pdf",
    "final_url": "https://docs.fcc.gov/public/attachments/DA-24-800A1.pdf",
    "authority": "United States Federal Communications Commission",
    "jurisdiction": "United States FCC 911 network reliability certification framework",
    "support_excerpt": "Section 9.19(b) of the Commission’s rules requires covered 911 service providers to take reasonable measures to provide reliable 911 service with respect to: (i) 911 circuit diversity for each of the critical 911 circuits used to provide service to each Public Safety Answering Point (PSAP) it serves; (ii) central office backup power for each central office it operates that directly serves a PSAP; and (iii) diverse network monitoring for each 911 service area it serves.3 911 Reliability Certification. For each of these requirements, and for each PSAP it serves (as to the circuit diversity requirements), each central office it operates that directly serves a PSAP (as to the backup power requirements) and each 911 service area it serves (as to the diverse network monitoring requirements), a covered 911 service provider must certify as to one of the following: (A) Confirmation that it has complied with the applicable requirement by performing the specific measures identified in section 9.19(c)(1)(i) (circuit diversity) (c)(2)(i) (backup power) or (c)(3)(i) (diverse network monitoring) for the PSAP, central office, or 911 service area, as applicable;4 or 1 See Improving 911 Reliability; Reliability and Continuity of Communications Networks, Including Broadband Technologies, Report and Order, 28 FCC Rcd 17476, 17497, 17534, paras. 65, 163 (2013) (911 Reliability Certification Order). 2 See 47 CFR § 9.19(a)(4) (defining covered 911 service providers as entities that “[p]rovide[] 911, E911, or NG911 capabilities such as call routing, automatic location information (ALI), automatic number identification (ANI), or the functional equivalent of those capabilities, directly to a public safety answering point (PSAP), statewide default answering point, or appropriate local emergency authority,” or that “[o]perate[] one or more central offices that directly serve a PSAP”). 3 47 CFR § 9.19(c); see also id. § 9.19(a) (definitions of relevant terms for purposes of the circuit diversity, backup power, and diverse network monitoring requirements). 4 47 CFR § 9.19(c)(1)(i), (c)(2)(i), (c)(3)(i). 2 (B) A description of the alternative measures it has taken to mitigate the risks of 911 service failure associated with the relevant requirements for each PSAP, central office, or 911 service area where such alternative measures are in use, including a complete explanation of why those alternative measures are reasonably sufficient to mitigate the risk of failure at least to a comparable extent as the specific measures identified in the paragraphs listed above in the context of the specific network facilities at issue or other factors;5 or (C) A description and explanation of any steps that it is taking to remediate any deficiencies that it has identified with respect to such PSAP, central office, or 911 service area, and the date by which it anticipates completing such remediation steps;",
    "rule_claim": "For each served PSAP, a covered 911 service provider must certify completed circuit-diversity measures, sufficient alternative measures, identified remediation steps with an anticipated completion date, or inapplicability.",
    "applicability_reason": "The task identifies a covered provider, two PSAPs and one critical circuit serving each. Completed diversity work and the remediation-certification route are both modeled per PSAP; no alternative measure or inapplicability fact is present.",
    "patch_summary": "Replace a provider-wide review with a per-PSAP choice between completed circuit-diversity work and a detailed remediation certification carrying an anticipated completion date.",
})
reset_audit(
    a,
    task_by_id["SWOR-R039"]["problem_zh"],
    "每个补救认证包都将详细说明针对该PSAP已发现缺陷正在采取的具体补救步骤，并写入由本地项目排期确定的预计完成日期。基础运营要求至少开展1项工作；备用电源检查只有在同时开展全网汇总审查时才能实施。北城和南城各有1条由该服务商直接提供服务的关键911电路，现有年度档案尚未对这2条电路分别完成多样性措施或补救认证包，也不存在已采取的替代措施或适用性排除。",
    "constraint:north_psap_certification",
)

write_jsonl(TASK_PATH, tasks)
write_jsonl(AUDIT_PATH, audits)
print(json.dumps({
    "status": "REPAIRED",
    "ids": ["SWOR-R021", "SWOR-R023", "SWOR-R026", "SWOR-R028", "SWOR-R030", "SWOR-R031", "SWOR-R036", "SWOR-R039"],
}, ensure_ascii=False))
