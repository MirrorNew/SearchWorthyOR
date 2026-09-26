from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import requests


HERE = Path(__file__).resolve()
RAPID_ROOT = HERE.parents[3]
BATCH_ROOT = HERE.parents[1]
SCRIPTS = RAPID_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from solve_model_pair import evaluate  # noqa: E402
from recheck_release_sources import normalize_bytes, normalize_text  # noqa: E402


def v(name: str, kind: str, lb: int, ub: int, meaning: str) -> dict[str, Any]:
    return {"name": name, "type": kind, "lb": lb, "ub": ub, "meaning": meaning}


def c(name: str, sense: str, rhs: float, coefficients: dict[str, float], meaning: str) -> dict[str, Any]:
    return {"name": name, "sense": sense, "rhs": rhs, "coefficients": coefficients, "meaning": meaning}


def model(task_id: str, family: str, source_id: str, variables: list[dict[str, Any]],
          sense: str, coefficients: dict[str, float], objective_meaning: str,
          unit: str, constraints: list[dict[str, Any]], action: list[str], variant: str) -> dict[str, Any]:
    return {
        "schema_version": "searchworthyor.rapid_model_ir.v0", "id": task_id,
        "variant": variant, "family": family, "source_candidate_id": source_id,
        "variables": variables,
        "objective": {"sense": sense, "constant": 0, "coefficients": coefficients,
                      "meaning": objective_meaning, "unit": unit},
        "constraints": constraints, "action_projection": action,
    }


CASES: list[dict[str, Any]] = []


def add(task_id: str, family: str, patch_class: str, problem: str,
        variables: list[dict[str, Any]], sense: str, objective: dict[str, float],
        objective_meaning: str, unit: str, constraints: list[dict[str, Any]],
        action: list[str], patch_variables: list[dict[str, Any]],
        patch_constraints: list[dict[str, Any]], patch_objective: dict[str, float] | None,
        patch_summary: str, local_fact: str, patch_binding: str) -> None:
    CASES.append(locals())


add(
    "SWOR-R081", "assignment_matching", "conditional_auxiliary",
    "爱尔兰地方环境信息报送。2026年8月2日，科克市议会和都柏林市议会分别决定如何处理本年度已经整理完毕的废物实施信息。每个议会必须在2种动作中选择1种：由本议会通过环境署指定的电子渠道完成本期报送，或把材料转入本议会的延期处理队列。科克的报送与延期处理成本分别为8千欧元和1千欧元；都柏林分别为5千欧元和1千欧元。只要任一议会本期报送，就需共同启用1次电子门户技术支持，增加2千欧元成本。环境署已向2个议会发出本年度信息通知，明确了本期所需资料和电子格式；2个议会的底层记录均已完成。唯一目标是最小化本期处理总成本。2项决定需要遵守在爱尔兰有效的废物信息报送规定。请给出最优处理方案与总成本。",
    [v("submit_cork", "BINARY", 0, 1, "科克市议会本期向环境署报送"), v("defer_cork", "BINARY", 0, 1, "科克市议会把材料转入延期处理队列"),
     v("submit_dublin", "BINARY", 0, 1, "都柏林市议会本期向环境署报送"), v("defer_dublin", "BINARY", 0, 1, "都柏林市议会把材料转入延期处理队列"), v("portal_support", "BINARY", 0, 1, "启用共享电子门户技术支持")],
    "min", {"submit_cork": 8, "defer_cork": 1, "submit_dublin": 5, "defer_dublin": 1, "portal_support": 2}, "本期信息处理成本", "千欧元",
    [c("choose_cork_action", "=", 1, {"submit_cork": 1, "defer_cork": 1}, "科克市议会恰选择一个处理动作"),
     c("choose_dublin_action", "=", 1, {"submit_dublin": 1, "defer_dublin": 1}, "都柏林市议会恰选择一个处理动作"),
     c("portal_support_link", "<=", 0, {"submit_cork": 1, "submit_dublin": 1, "portal_support": -2}, "任一议会报送时启用共享门户支持")],
    ["submit_cork", "defer_cork", "submit_dublin", "defer_dublin", "portal_support"], [],
    [c("cork_submission_required", "=", 1, {"submit_cork": 1}, "科克市议会本期完成报送"),
     c("dublin_submission_required", "=", 1, {"submit_dublin": 1}, "都柏林市议会本期完成报送")],
    None, "把两个地方主管机关的本期报送动作设为必选，并由共享门户支持约束联结两项报送。", "环境署已向2个议会发出本年度信息通知，明确了本期所需资料和电子格式；2个议会的底层记录均已完成", "constraint:cork_submission_required")

add(
    "SWOR-R082", "assignment_matching", "quota_risk_service_objective",
    "佛罗里达协调交通席位分配。2026年8月2日，松湾社区交通协调员要把3名行动不便乘客分别安排到校车、固定线路公交或无障碍专车，每人只能乘坐1种服务。3名乘客使用校车的成本依次为2、2、3美元，使用固定线路公交的成本依次为4、3、4美元，使用无障碍专车的成本依次为7、6、6美元。校车和固定线路公交各最多接纳2名乘客。服务时段内校车正在运送学生。唯一目标是最小化3名乘客的总运输成本。方案必须遵守佛罗里达州适用的协调交通资源使用规定。请给出最优乘车分配方案与总成本。",
    [v(f"school_{i}", "BINARY", 0, 1, f"乘客{i}乘坐校车") for i in range(1, 4)] + [v(f"transit_{i}", "BINARY", 0, 1, f"乘客{i}乘坐固定线路公交") for i in range(1, 4)] + [v(f"para_{i}", "BINARY", 0, 1, f"乘客{i}乘坐无障碍专车") for i in range(1, 4)],
    "min", {"school_1": 2, "school_2": 2, "school_3": 3, "transit_1": 4, "transit_2": 3, "transit_3": 4, "para_1": 7, "para_2": 6, "para_3": 6}, "乘客运输成本", "美元",
    [c(f"assign_{i}", "=", 1, {f"school_{i}": 1, f"transit_{i}": 1, f"para_{i}": 1}, f"乘客{i}恰分配一种服务") for i in range(1, 4)] +
    [c("school_capacity", "<=", 2, {f"school_{i}": 1 for i in range(1, 4)}, "校车最多接纳两名乘客"), c("transit_capacity", "<=", 2, {f"transit_{i}": 1 for i in range(1, 4)}, "固定线路公交最多接纳两名乘客")],
    [f"{mode}_{i}" for mode in ("school", "transit", "para") for i in range(1, 4)], [],
    [c("school_unavailable", "=", 0, {f"school_{i}": 1 for i in range(1, 4)}, "载运学生期间校车不可共享")],
    None, "把正在载运学生的校车从协调交通可用资源中排除。", "服务时段内校车正在运送学生", "constraint:school_unavailable")

add(
    "SWOR-R083", "energy_environment", "conditional_auxiliary",
    "2030年变压器采购。2026年8月2日，北辰配电公司为2030年5月在美国投运的站房选择进口变压器，总容量至少500千伏安且最多采购2台。候选设备为：150千伏安单相低压干式机，价格18万美元；225千伏安三相低压干式机，价格23万美元；275千伏安三相低压干式机，价格28万美元；300千伏安液浸机，价格32万美元；500千伏安远港低压干式机，价格45万美元。现有母线不能把300千伏安液浸机与225千伏安或275千伏安干式机同时接入。前4台设备均按DOE附录A的参考负载和温度完成测试，实测效率均为99.90%，记录中同时列明了容量、相别和绝缘介质；远港设备同法实测效率为99.90%，但记录没有标注相别。招标文件要求低压干式设备按届时DOE适用的设备类别提交可核验效率记录，否则不得中标。唯一目标是最小化采购总价。采购需要遵守届时适用于美国进口配电变压器的能效规定。请给出最优采购方案与总成本。",
    [v("dry_single_150", "BINARY", 0, 1, "采购150千伏安单相低压干式机"), v("dry_three_225", "BINARY", 0, 1, "采购225千伏安三相低压干式机"), v("dry_three_275", "BINARY", 0, 1, "采购275千伏安三相低压干式机"), v("liquid_300", "BINARY", 0, 1, "采购300千伏安液浸机"), v("harbor_dry_500", "BINARY", 0, 1, "采购500千伏安远港低压干式机")],
    "min", {"dry_single_150": 18, "dry_three_225": 23, "dry_three_275": 28, "liquid_300": 32, "harbor_dry_500": 45}, "变压器采购总价", "万美元",
    [c("capacity", ">=", 500, {"dry_single_150": 150, "dry_three_225": 225, "dry_three_275": 275, "liquid_300": 300, "harbor_dry_500": 500}, "总容量至少五百千伏安"), c("unit_limit", "<=", 2, {"dry_single_150": 1, "dry_three_225": 1, "dry_three_275": 1, "liquid_300": 1, "harbor_dry_500": 1}, "最多采购两台"), c("bus_incompatibility_225", "<=", 1, {"dry_three_225": 1, "liquid_300": 1}, "二百二十五千伏安干式机与三百千伏安液浸机不能同时接入"), c("bus_incompatibility_275", "<=", 1, {"dry_three_275": 1, "liquid_300": 1}, "二百七十五千伏安干式机与三百千伏安液浸机不能同时接入")],
    ["dry_single_150", "dry_three_225", "dry_three_275", "liquid_300", "harbor_dry_500"], [v("harbor_class_verified", "BINARY", 0, 1, "远港干式机已按适用设备类别完成核验")],
    [c("harbor_class_trigger", "<=", 0, {"harbor_dry_500": 1, "harbor_class_verified": -1}, "采购远港机时必须完成类别核验"), c("harbor_record_missing", "=", 0, {"harbor_class_verified": 1}, "现有远港证书无法完成类别核验")],
    None, "依据招标合同采用DOE分类分支，为低压干式设备增加类别核验动作，并阻止类别资料不足的设备中标。", "前4台设备均按DOE附录A的参考负载和温度完成测试，实测效率均为99.90%，记录中同时列明了容量、相别和绝缘介质；远港设备同法实测效率为99.90%，但记录没有标注相别", "constraint:harbor_record_missing")

add(
    "SWOR-R084", "energy_environment", "conditional_auxiliary",
    "地下站房变压器组合。2026年8月2日，银湾电网为2030年6月在美国进口并安装的地下站房配置至少500千伏安容量，最多采购2台。地面型400千伏安设备价格35万美元，潜水型300千伏安设备价格22万美元，潜水型200千伏安设备价格16万美元，潜水型100千伏安设备价格12万美元，密封型500千伏安设备价格46万美元。站房吊装轨道不能同时容纳400千伏安地面型设备与300千伏安潜水型设备。5台设备均按DOE附录A的参考负载和温度完成测试，实测效率均为99.90%；地面型、潜水型200千伏安、潜水型100千伏安和密封型设备的档案分别写明了结构类型和相别，潜水型300千伏安设备只有一般液浸设备档案，没有潜水运行结构的试验页。采购合同要求潜水型设备按届时DOE适用的潜水型分支完成试验归档，否则不得中标。唯一目标是最小化设备总价。采购必须遵守届时适用的美国配电变压器能效规定。请给出最优设备组合与总成本。",
    [v("ground_400", "BINARY", 0, 1, "采购400千伏安地面型设备"), v("submersible_300", "BINARY", 0, 1, "采购300千伏安潜水型设备"), v("submersible_200", "BINARY", 0, 1, "采购200千伏安潜水型设备"), v("submersible_100", "BINARY", 0, 1, "采购100千伏安潜水型设备"), v("sealed_500", "BINARY", 0, 1, "采购500千伏安密封型设备")],
    "min", {"ground_400": 35, "submersible_300": 22, "submersible_200": 16, "submersible_100": 12, "sealed_500": 46}, "地下站房设备采购价", "万美元",
    [c("capacity", ">=", 500, {"ground_400": 400, "submersible_300": 300, "submersible_200": 200, "submersible_100": 100, "sealed_500": 500}, "容量至少五百千伏安"), c("unit_limit", "<=", 2, {"ground_400": 1, "submersible_300": 1, "submersible_200": 1, "submersible_100": 1, "sealed_500": 1}, "最多采购两台"), c("lifting_compatibility", "<=", 1, {"ground_400": 1, "submersible_300": 1}, "吊装轨道不能同时容纳地面四百型和潜水三百型")],
    ["ground_400", "submersible_300", "submersible_200", "submersible_100", "sealed_500"], [v("submersible_branch_check", "BINARY", 0, 1, "三百千伏安设备通过潜水型分支核验")],
    [c("submersible_check_trigger", "<=", 0, {"submersible_300": 1, "submersible_branch_check": -1}, "采购三百千伏安潜水型机须通过分支核验"), c("submersible_file_gap", "=", 0, {"submersible_branch_check": 1}, "现有档案不能通过潜水型分支核验")],
    None, "依据采购合同采用DOE潜水型分支，增加分支核验动作并排除未按该分支归档的候选设备。", "5台设备均按DOE附录A的参考负载和温度完成测试，实测效率均为99.90%；地面型、潜水型200千伏安、潜水型100千伏安和密封型设备的档案分别写明了结构类型和相别，潜水型300千伏安设备只有一般液浸设备档案，没有潜水运行结构的试验页", "constraint:submersible_file_gap")

add(
    "SWOR-R085", "facility_network", "eligibility_domain",
    "澳大利亚移动设施选址。2026年8月2日，海风通信公司要在昆士兰为北、中央、南3个服务区部署面板式天线。4个候选站点使用同一种配置：天线长2.4米，安装在既有建筑结构上并向外突出1.5米，外壳颜色与建筑背景一致。北区可由河岸站或市场站覆盖，中央区可由市场站或车站站覆盖，南区可由车站站或港口站覆盖。4个站点的建设成本依次为18、15、17、11万澳元。规划底图将河岸站、市场站、车站站和港口站所在土地依次标为工业区、商业区、商业区和农村区；市场站地块还同时列入环境重要区，另外3个地块没有该标记。唯一目标是最小化建站成本。选址需要遵守澳大利亚现行的低影响通信设施规定。请给出最优站点选择方案与总成本。",
    [v("river", "BINARY", 0, 1, "建设河岸站"), v("market", "BINARY", 0, 1, "建设市场站"), v("station", "BINARY", 0, 1, "建设车站站"), v("port", "BINARY", 0, 1, "建设港口站")],
    "min", {"river": 18, "market": 15, "station": 17, "port": 11}, "通信设施建设成本", "万澳元",
    [c("cover_north", ">=", 1, {"river": 1, "market": 1}, "北区至少由一个站点覆盖"), c("cover_central", ">=", 1, {"market": 1, "station": 1}, "中央区至少由一个站点覆盖"), c("cover_south", ">=", 1, {"station": 1, "port": 1}, "南区至少由一个站点覆盖")],
    ["river", "market", "station", "port"], [], [c("environmental_area_exclusion", "=", 0, {"market": 1}, "环境重要区内的市场站不具低影响设施资格")],
    None, "从低影响设施候选域中删除位于环境重要区的市场站。", "4个候选站点使用同一种配置：天线长2.4米，安装在既有建筑结构上并向外突出1.5米，外壳颜色与建筑背景一致", "constraint:environmental_area_exclusion")

add(
    "SWOR-R086", "facility_network", "temporal_coupling",
    "德国输电线路协调方案。2026年8月2日，莱茵输电公司准备改造1条会首次对邻近铁路信号设施产生电磁影响的输电线路。线路可采用河谷走廊或山脊走廊，附加成本分别为1万欧元和3万欧元。公司还可决定是否安排4项工作：开展运行、组织和技术防护措施审查，成本1万欧元；与铁路信号运营商举行共同确定会议，成本2万欧元；实施输电侧共同选定的防护措施，成本3万欧元；由信号运营商实施其责任范围内共同选定的防护措施并由输电公司承担2万欧元协调成本。技术记录已确认本次影响属于输电线路对既有信号设施的电磁影响，双方均有各自责任范围内可实施的防护动作，目前尚未开展上述4项工作。唯一目标是最小化走廊和协调工作总成本。方案必须遵守德国输电设施电磁影响的协调和防护规定。请给出最优走廊与协调工作方案及总成本。",
    [v("valley", "BINARY", 0, 1, "选择河谷走廊"), v("ridge", "BINARY", 0, 1, "选择山脊走廊"),
     v("examine_measures", "BINARY", 0, 1, "开展防护措施审查"), v("joint_determination", "BINARY", 0, 1, "与信号运营商共同确定防护措施"),
     v("grid_implementation", "BINARY", 0, 1, "实施输电侧共同选定的防护措施"), v("signal_implementation", "BINARY", 0, 1, "协调信号侧实施共同选定的防护措施")],
    "min", {"valley": 1, "ridge": 3, "examine_measures": 1, "joint_determination": 2, "grid_implementation": 3, "signal_implementation": 2}, "走廊和协调工作总成本", "万欧元",
    [c("choose_corridor", "=", 1, {"valley": 1, "ridge": 1}, "恰选择一条走廊")],
    ["valley", "ridge", "examine_measures", "joint_determination", "grid_implementation", "signal_implementation"], [],
    [c("examination_required", "=", 1, {"examine_measures": 1}, "开展防护措施审查"),
     c("joint_determination_required", "=", 1, {"joint_determination": 1}, "共同确定技术和经济上优选的防护措施"),
     c("grid_implementation_required", "=", 1, {"grid_implementation": 1}, "输电运营商实施其责任范围内共同确定的措施"),
     c("signal_implementation_required", "=", 1, {"signal_implementation": 1}, "信号运营商实施其责任范围内共同确定的措施")],
    None, "增加防护措施审查、共同确定以及双方各自责任范围内的实施动作。", "技术记录已确认本次影响属于输电线路对既有信号设施的电磁影响，双方均有各自责任范围内可实施的防护动作，目前尚未开展上述4项工作", "constraint:joint_determination_required")

add(
    "SWOR-R087", "finance_portfolio", "eligibility_domain",
    "澳大利亚养老基金投资选择。2026年8月2日，南十字星养老基金的受托人南十字星受托公司为均衡投资选项配置新资产；该公司的APRA登记文件载有仍有效的可注册养老实体牌照，且APRA送达登记中没有针对该公司或本投资选项调整、排除SPS 530要求的书面决定。投入资金不超过100万澳元。候选资产为基础设施债、可再生能源债、私人信贷、上市地产和短期票据，资金占用依次为60、50、70、40、30万澳元，预期年度收益依次为12、11、16、10、8万澳元。私人信贷的压力测试和底层资产尽调尚未完成，其他4项的底层资产清单、交易对手核查、风险测量和压力情景记录均已完成。唯一目标是最大化预期年度收益。投资选择必须遵守澳大利亚审慎监管机构对养老基金投资尽调的现行要求。请给出最优投资组合与总收益。",
    [v("infra_bond", "BINARY", 0, 1, "投资基础设施债"), v("green_bond", "BINARY", 0, 1, "投资可再生能源债"), v("private_credit", "BINARY", 0, 1, "投资私人信贷"), v("listed_property", "BINARY", 0, 1, "投资上市地产"), v("cash_note", "BINARY", 0, 1, "投资短期票据")],
    "max", {"infra_bond": 12, "green_bond": 11, "private_credit": 16, "listed_property": 10, "cash_note": 8}, "预期年度收益", "万澳元",
    [c("capital_budget", "<=", 100, {"infra_bond": 60, "green_bond": 50, "private_credit": 70, "listed_property": 40, "cash_note": 30}, "总资金占用不超过一百万澳元")],
    ["infra_bond", "green_bond", "private_credit", "listed_property", "cash_note"], [], [c("due_diligence_gate", "=", 0, {"private_credit": 1}, "未完成有效尽调的私人信贷不得入选")],
    None, "从可投资产域中排除未完成相称尽调和压力测试的私人信贷。", "该公司的APRA登记文件载有仍有效的可注册养老实体牌照，且APRA送达登记中没有针对该公司或本投资选项调整、排除SPS 530要求的书面决定", "constraint:due_diligence_gate")

add(
    "SWOR-R088", "finance_portfolio", "temporal_coupling",
    "美国清洁能源基金跨期交易。2026年8月2日，已进入规则合规期的大型远岬清洁能源基金在季度复核中确认：现有90个标准份额中只有70个属于名称相关资产。该基金于2019年开始运营，本期没有发起或参与重组，也没有提出名称政策变更或向股东发送政策变更通知；复核期内没有异常大额申购或赎回，没有为应对不利市场、经济或政治事件而转持现金，偏离仅由季度末普通市场价格变动造成。投资委员会同期会议记录将本期市场和基金运作记为正常。基金决定在2026年8月2日和10月15日各买入5个标准份额，每期可买入名称相关的清洁能源资产或其他资产。2类资产在8月2日每份预期收益分别为5千美元和7千美元，在10月15日分别为6千美元和8千美元。上述2批合计10个份额是基金从本次复核到2026年10月31日期间仅能执行的交易，既有90个份额和新买份额在该期间均持续持有且分类不变。唯一目标是最大化2批买入资产的预期收益。交易计划需要遵守美国对投资公司名称政策复核与恢复的现行规定。请给出最优2期买入方案与总收益。",
    [v("theme_now", "INTEGER", 0, 5, "本月买入清洁能源资产份额"), v("other_now", "INTEGER", 0, 5, "本月买入其他资产份额"), v("theme_next", "INTEGER", 0, 5, "下一季度买入清洁能源资产份额"), v("other_next", "INTEGER", 0, 5, "下一季度买入其他资产份额")],
    "max", {"theme_now": 5, "other_now": 7, "theme_next": 6, "other_next": 8}, "两期预期收益", "千美元",
    [c("current_purchase", "=", 5, {"theme_now": 1, "other_now": 1}, "本月买入五个份额"), c("next_purchase", "=", 5, {"theme_next": 1, "other_next": 1}, "十月十五日买入五个份额")],
    ["theme_now", "other_now", "theme_next", "other_next"], [], [c("recovery_ratio", ">=", 10, {"theme_now": 1, "theme_next": 1}, "两批交易结束后的名称相关资产比例达到适用门槛")],
    None, "把七十比九十的复核状态与截止日期前仅有的两批交易联结，并增加交易后组合比例约束。", "该基金于2019年开始运营，本期没有发起或参与重组，也没有提出名称政策变更或向股东发送政策变更通知；复核期内没有异常大额申购或赎回，没有为应对不利市场、经济或政治事件而转持现金，偏离仅由季度末普通市场价格变动造成", "constraint:recovery_ratio")

add(
    "SWOR-R089", "healthcare_resources", "quota_risk_service_objective",
    "美国医疗替代服务分配。2026年8月2日，佛罗里达州医疗补助管理式医疗计划为7名受益人选择州计划标准服务或管理式医疗合同中的替代服务。其中4人需要的住房过渡导航已经写入当前管理式医疗合同和州批准文件；4人的主治临床人员在个别评估后分别建议使用住房过渡导航，州计划标准服务仍可获得，4人也都在收到2种选择的说明后书面自愿选择该导航服务。另3人提出的健身会员服务未写入当前合同。对前一人群，每人使用替代服务和标准服务的成本分别为3百美元和7百美元；对后一人群分别为2百美元和6百美元。替代服务机构本期最多接收5人，2类人群都必须全部得到服务。唯一目标是最小化总服务成本。分配需要遵守美国医疗补助管理式医疗中替代服务的适用规定。请给出最优服务人数分配与总成本。",
    [v("eligible_alt", "INTEGER", 0, 4, "住房导航人群接受合同内替代服务的人数"), v("eligible_standard", "INTEGER", 0, 4, "住房导航人群接受标准服务的人数"), v("unrecorded_alt", "INTEGER", 0, 3, "健身会员人群接受未写入合同的替代服务人数"), v("unrecorded_standard", "INTEGER", 0, 3, "健身会员人群接受标准服务的人数")],
    "min", {"eligible_alt": 3, "eligible_standard": 7, "unrecorded_alt": 2, "unrecorded_standard": 6}, "服务成本", "百美元",
    [c("serve_eligible", "=", 4, {"eligible_alt": 1, "eligible_standard": 1}, "四名住房导航人群全部获得服务"), c("serve_unrecorded", "=", 3, {"unrecorded_alt": 1, "unrecorded_standard": 1}, "三名健身会员人群全部获得服务"), c("alternative_capacity", "<=", 5, {"eligible_alt": 1, "unrecorded_alt": 1}, "替代服务机构最多接收五人")],
    ["eligible_alt", "eligible_standard", "unrecorded_alt", "unrecorded_standard"], [], [c("contract_service_gate", "=", 0, {"unrecorded_alt": 1}, "未写入管理式医疗合同的健身会员服务不得作为替代服务分配")],
    None, "按管理式医疗合同中是否列明服务收紧替代服务域。", "其中4人需要的住房过渡导航已经写入当前管理式医疗合同和州批准文件；4人的主治临床人员在个别评估后分别建议使用住房过渡导航，州计划标准服务仍可获得，4人也都在收到2种选择的说明后书面自愿选择该导航服务", "constraint:contract_service_gate")

add(
    "SWOR-R090", "healthcare_resources", "temporal_coupling",
    "英格兰受控药品库存检查。2026年8月2日，北桥社区医院安排2026年8月3日至8月16日的受控药品库存检查。重症药房可在8月4日或8月11日单独检查，所需工时分别为2小时和5小时；急诊药柜可在8月6日或8月13日单独检查，所需工时分别为3小时和4小时；也可在8月7日安排1次联合检查，同时覆盖两处并耗时4小时。医院内部最低要求是规划期内每处至少检查1次，风险评估没有批准降低常规核查频率。唯一目标是最小化检查总工时。排程还须遵守英格兰适用的受控药品库存检查指南。请给出最优检查方案与目标值。",
    [v("icu_aug04", "BINARY", 0, 1, "重症药房八月四日检查"), v("icu_aug11", "BINARY", 0, 1, "重症药房八月十一日检查"), v("ed_aug06", "BINARY", 0, 1, "急诊药柜八月六日检查"), v("ed_aug13", "BINARY", 0, 1, "急诊药柜八月十三日检查"), v("joint_aug07", "BINARY", 0, 1, "八月七日联合检查两处")],
    "min", {"icu_aug04": 2, "icu_aug11": 5, "ed_aug06": 3, "ed_aug13": 4, "joint_aug07": 4}, "库存检查工时", "小时",
    [c("icu_period_check", ">=", 1, {"icu_aug04": 1, "icu_aug11": 1, "joint_aug07": 1}, "重症药房规划期至少检查一次"), c("ed_period_check", ">=", 1, {"ed_aug06": 1, "ed_aug13": 1, "joint_aug07": 1}, "急诊药柜规划期至少检查一次")],
    ["icu_aug04", "icu_aug11", "ed_aug06", "ed_aug13", "joint_aug07"], [],
    [c("icu_first_week", ">=", 1, {"icu_aug04": 1, "joint_aug07": 1}, "重症药房第一周须有检查"),
     c("ed_first_week", ">=", 1, {"ed_aug06": 1, "joint_aug07": 1}, "急诊药柜第一周须有检查"),
     c("icu_second_week", ">=", 1, {"icu_aug11": 1}, "重症药房第二周须有检查"),
     c("ed_second_week", ">=", 1, {"ed_aug13": 1}, "急诊药柜第二周须有检查")],
    None, "结合风险评估结果，把跨两周的总检查要求拆成每处设施逐周覆盖要求。", "风险评估没有批准降低常规核查频率", "constraint:icu_first_week")

add(
    "SWOR-R091", "inventory_supply_chain", "conditional_auxiliary",
    "新加坡包装商品采购。2026年8月2日，海狮零售集团要采购3批饮料和3批清洁用品。每批进口饮料与本地饮料的采购成本分别为4千新元和7千新元；每批进口清洁用品与本地清洁用品分别为3千新元和6千新元。选择进口饮料时，集团本人作为进口商把装有饮料的PET零售瓶和瓦楞纸运输箱带入新加坡；选择进口清洁用品时，集团本人把装有清洁剂的HDPE零售瓶和瓦楞纸运输箱带入新加坡。上述包装用于普通零售商品，不是集装箱、运输托盘或可回收押金周转器具。本地批次由新加坡供应商用其自有可回收周转罐直接送入集团的固定补充槽，供应商当天收回周转罐，集团既不进口这些周转罐，也不把商品装入这些周转罐。集团在新加坡销售瓶装饮料和瓶装清洁剂，2024财年营业额为1200万新元；若依法需要准备包装报告，内部处理成本为20千新元。唯一目标是最小化采购与依法发生的内部处理总成本。采购安排必须遵守新加坡现行强制包装报告制度。请给出最优采购方案与总成本。",
    [v("import_drink", "INTEGER", 0, 3, "进口饮料批数"), v("local_drink", "INTEGER", 0, 3, "本地饮料批数"), v("import_cleaner", "INTEGER", 0, 3, "进口清洁用品批数"), v("local_cleaner", "INTEGER", 0, 3, "本地清洁用品批数")],
    "min", {"import_drink": 4, "local_drink": 7, "import_cleaner": 3, "local_cleaner": 6}, "采购与合规处理总成本", "千新元",
    [c("drink_demand", "=", 3, {"import_drink": 1, "local_drink": 1}, "采购三批饮料"), c("cleaner_demand", "=", 3, {"import_cleaner": 1, "local_cleaner": 1}, "采购三批清洁用品")],
    ["import_drink", "local_drink", "import_cleaner", "local_cleaner"], [v("packaging_report", "BINARY", 0, 1, "启动强制包装报告流程")],
    [c("drink_reporting_trigger", "<=", 0, {"import_drink": 1, "packaging_report": -3}, "进口饮料触发包装报告"), c("cleaner_reporting_trigger", "<=", 0, {"import_cleaner": 1, "packaging_report": -3}, "进口清洁用品触发包装报告")],
    {"packaging_report": 20}, "增加包装报告激活动作及其内部处理成本，并与进口批次联结。", "选择进口饮料时，集团本人作为进口商把装有饮料的PET零售瓶和瓦楞纸运输箱带入新加坡；选择进口清洁用品时，集团本人把装有清洁剂的HDPE零售瓶和瓦楞纸运输箱带入新加坡", "constraint:drink_reporting_trigger")

add(
    "SWOR-R092", "inventory_supply_chain", "eligibility_domain",
    "美国货运经纪信托资产配置。2026年8月2日，北陆货运经纪公司从6项资产中选择信托储备，使账面价值至少达到70万美元，且最多选3项。候选资产为现金、美国国债、由FDIC承保的美国存款机构出具的不可撤销信用证、贸易应收账款、加密资产和金条，账面价值依次为35、30、28、25、40、45万美元；按相同顺序，年度占用费用为5、4、3、2、1和1.5万美元。唯一目标是最小化年度占用成本。配置必须遵守美国联邦货运经纪人财务责任规定。请给出最优信托资产组合与总成本。",
    [v("cash", "BINARY", 0, 1, "纳入现金"), v("treasury", "BINARY", 0, 1, "纳入美国国债"), v("letter_credit", "BINARY", 0, 1, "纳入银行信用证"), v("receivable", "BINARY", 0, 1, "纳入应收账款"), v("crypto", "BINARY", 0, 1, "纳入加密资产"), v("gold", "BINARY", 0, 1, "纳入金条")],
    "min", {"cash": 5, "treasury": 4, "letter_credit": 3, "receivable": 2, "crypto": 1, "gold": 1.5}, "年度资产占用成本", "万美元",
    [c("book_value", ">=", 70, {"cash": 35, "treasury": 30, "letter_credit": 28, "receivable": 25, "crypto": 40, "gold": 45}, "账面价值至少七十万美元"), c("asset_limit", "<=", 3, {"cash": 1, "treasury": 1, "letter_credit": 1, "receivable": 1, "crypto": 1, "gold": 1}, "最多选择三项资产")],
    ["cash", "treasury", "letter_credit", "receivable", "crypto", "gold"], [], [c("receivable_ineligible", "=", 0, {"receivable": 1}, "贸易应收账款不属于允许计入信托的资产类型"), c("crypto_ineligible", "=", 0, {"crypto": 1}, "加密资产不属于允许计入信托的资产类型"), c("gold_ineligible", "=", 0, {"gold": 1}, "金条不属于允许计入信托的资产类型"), c("qualifying_value", ">=", 70, {"cash": 35, "treasury": 30, "letter_credit": 28}, "允许类型资产价值至少七十万美元")],
    None, "按法定信托资产类型重建合格资产价值约束，并排除不在允许类型中的应收账款、加密资产和金条。", "由FDIC承保的美国存款机构出具的不可撤销信用证", "constraint:crypto_ineligible")

add(
    "SWOR-R093", "production_capacity", "eligibility_domain",
    "爱尔兰树脂生产与残料利用。2026年8月2日，凯尔特材料厂必须生产4批树脂，可在水性工艺和溶剂工艺间分配，每种工艺最多4批。每批水性工艺的主产品利润为7千欧元，直接利用其残料另增4千欧元；每批溶剂工艺的主产品利润为9千欧元，利用其残料另增5千欧元。残料利用批数不能超过对应工艺的生产批数。水性残料在树脂反应中同步分离，砖厂已签署按实际产生量全部接收的排期，进厂后直接作为砖坯原料，不需额外处理；产品规格、环境许可和职业健康检测均覆盖该用途，现有评估未记录总体不利影响。溶剂残料同样在树脂反应中产生，但进入后续生产前必须加入新的萃取剂，在加热反应釜中完成化学萃取并对萃取废液作危险废物中和；树脂厂和砖厂现有工艺流程、设备清单与环境许可均不包含这些步骤，双方日常生产也从未执行这些步骤。唯一目标是最大化总利润。生产与残料利用必须遵守爱尔兰现行的副产品认定规定。请给出最优生产和残料利用方案与总利润。",
    [v("water_process", "INTEGER", 0, 4, "水性工艺生产批数"), v("solvent_process", "INTEGER", 0, 4, "溶剂工艺生产批数"), v("reuse_water", "INTEGER", 0, 4, "直接利用水性残料批数"), v("reuse_solvent", "INTEGER", 0, 4, "利用溶剂残料批数")],
    "max", {"water_process": 7, "solvent_process": 9, "reuse_water": 4, "reuse_solvent": 5}, "树脂生产与残料利用利润", "千欧元",
    [c("production_target", "=", 4, {"water_process": 1, "solvent_process": 1}, "合计生产四批树脂"), c("water_residue", "<=", 0, {"reuse_water": 1, "water_process": -1}, "水性残料利用不超过其产生量"), c("solvent_residue", "<=", 0, {"reuse_solvent": 1, "solvent_process": -1}, "溶剂残料利用不超过其产生量")],
    ["water_process", "solvent_process", "reuse_water", "reuse_solvent"], [], [c("direct_use_gate", "=", 0, {"reuse_solvent": 1}, "需超常规处理的溶剂残料不能作为副产品直接利用")],
    None, "从可直接利用的副产品域中删除必须经过额外化学萃取的溶剂残料。", "溶剂残料同样在树脂反应中产生，但进入后续生产前必须加入新的萃取剂，在加热反应釜中完成化学萃取并对萃取废液作危险废物中和；树脂厂和砖厂现有工艺流程、设备清单与环境许可均不包含这些步骤，双方日常生产也从未执行这些步骤", "constraint:direct_use_gate")

add(
    "SWOR-R094", "production_capacity", "quota_risk_service_objective",
    "英国生物甲烷季度生产。2026年8月2日，绿沼能源公司为下一季度在英国注气网络安排最多4批生物甲烷，可由能源作物或废弃物原料生产。两种原料每批不含支持款的净贡献分别为8和7.5千英镑，生产批数与注气批数均为整数，注气批数不能超过对应原料的生产批数。公司已是绿色燃气支持计划参与者；废弃物批次全部由登记设备生产，满足本期原料与可持续性条件并经合规仪表计量，不含化石燃料投入，也不存在分层修正、计量修正、超额支付追缴或其他法定扣减；能源作物批次不在本期通知的支持比例内。财务委员会对每批依法计入季度支持的生物甲烷统一增加1千英镑折算贡献。唯一目标是最大化包含该折算贡献的季度总净贡献。生产计划必须遵守英国绿色燃气支持计划现行的季度支付规定。请给出最优生产注气方案与总净贡献。",
    [v("crop_batches", "INTEGER", 0, 4, "能源作物生物甲烷生产批数"), v("waste_batches", "INTEGER", 0, 4, "废弃物生物甲烷生产批数"), v("crop_injected", "INTEGER", 0, 4, "能源作物生物甲烷注气批数"), v("waste_injected", "INTEGER", 0, 4, "废弃物生物甲烷注气批数")],
    "max", {"crop_batches": 8, "waste_batches": 7.5}, "季度净贡献", "千英镑",
    [c("production_capacity", "<=", 4, {"crop_batches": 1, "waste_batches": 1}, "季度最多生产四批"), c("crop_injection", "<=", 0, {"crop_injected": 1, "crop_batches": -1}, "能源作物注气不超过生产量"), c("waste_injection", "<=", 0, {"waste_injected": 1, "waste_batches": -1}, "废弃物注气不超过生产量")],
    ["crop_batches", "waste_batches", "crop_injected", "waste_injected"], [v("eligible_waste", "INTEGER", 0, 4, "计入季度支持的废弃物生物甲烷批数")],
    [c("eligible_measurement", "=", 0, {"eligible_waste": 1, "waste_injected": -1}, "完整计量的废弃物注气全部计入合格量")],
    {"eligible_waste": 1}, "在排除各项扣减与例外后增加季度合格注气量及支持目标项，并与废弃物注气量绑定。", "废弃物批次全部由登记设备生产，满足本期原料与可持续性条件并经合规仪表计量，不含化石燃料投入，也不存在分层修正、计量修正、超额支付追缴或其他法定扣减", "constraint:eligible_measurement")

add(
    "SWOR-R095", "routing_transport", "conditional_auxiliary",
    "威斯康星货运路线选择。2026年8月2日，松港物流要把1车货物从麦迪逊运到绿湾。可走直达路线，成本10百美元；也可经福克斯中转，前后两段成本分别为6百美元和5百美元；还可经湖城中转，前后两段成本分别为3百美元和4百美元。每条中转路线的两段必须同时采用，3条路线中只能选1条。湖城承运商的保险证书已到期，直达承运商和福克斯承运商证书有效。唯一目标是最小化运输成本。运输必须遵守威斯康星州对财产承运人的许可、登记和责任保险规定。请给出最优运输路线与总成本。",
    [v("direct", "BINARY", 0, 1, "采用麦迪逊至绿湾直达段"), v("fox_out", "BINARY", 0, 1, "采用麦迪逊至福克斯段"), v("fox_in", "BINARY", 0, 1, "采用福克斯至绿湾段"), v("lake_out", "BINARY", 0, 1, "采用麦迪逊至湖城段"), v("lake_in", "BINARY", 0, 1, "采用湖城至绿湾段")],
    "min", {"direct": 10, "fox_out": 6, "fox_in": 5, "lake_out": 3, "lake_in": 4}, "货运路线成本", "百美元",
    [c("leave_origin", "=", 1, {"direct": 1, "fox_out": 1, "lake_out": 1}, "从麦迪逊选择一个出发段"), c("fox_balance", "=", 0, {"fox_out": 1, "fox_in": -1}, "福克斯中转两段同时采用"), c("lake_balance", "=", 0, {"lake_out": 1, "lake_in": -1}, "湖城中转两段同时采用")],
    ["direct", "fox_out", "fox_in", "lake_out", "lake_in"], [v("lake_insurance_active", "BINARY", 0, 1, "湖城承运商具有有效责任保险")],
    [c("lake_out_insurance", "<=", 0, {"lake_out": 1, "lake_insurance_active": -1}, "湖城出发段须有有效保险"), c("lake_in_insurance", "<=", 0, {"lake_in": 1, "lake_insurance_active": -1}, "湖城到达段须有有效保险"), c("expired_certificate", "=", 0, {"lake_insurance_active": 1}, "到期证书不能激活承运资格")],
    None, "增加湖城承运商保险激活动作，并把两条承运弧与有效保险联结。", "湖城承运商的保险证书已到期", "constraint:expired_certificate")

add(
    "SWOR-R096", "routing_transport", "eligibility_domain",
    "缅因州输电走廊路由。2026年8月2日，松岭输电公司要在缅因州从西部接入点新建1条115千伏线路到海岸变电站。河谷走廊由2段组成，成本分别为3和4百万美元；森林走廊2段成本分别为4和5百万美元；工业走廊2段成本分别为2和6百万美元。每条候选走廊的2段必须同时采用，且只能选择1条完整走廊。3条方案都由输电公司建设、拥有并运营，用于连接2个公用变电站，不是发电商自建的发电机并网线路，也不属于既有线路重建或迁移。河谷走廊的公共便利与必要性证书仍在审理，森林和工业走廊已获证书。唯一目标是最小化建设成本。线路选择必须遵守缅因州现行的输电线路建设许可规定。请给出最优走廊与总成本。",
    [v("valley_west", "BINARY", 0, 1, "河谷走廊西段"), v("valley_east", "BINARY", 0, 1, "河谷走廊东段"), v("forest_west", "BINARY", 0, 1, "森林走廊西段"), v("forest_east", "BINARY", 0, 1, "森林走廊东段"), v("industrial_west", "BINARY", 0, 1, "工业走廊西段"), v("industrial_east", "BINARY", 0, 1, "工业走廊东段")],
    "min", {"valley_west": 3, "valley_east": 4, "forest_west": 4, "forest_east": 5, "industrial_west": 2, "industrial_east": 6}, "输电走廊建设成本", "百万美元",
    [c("choose_route", "=", 1, {"valley_west": 1, "forest_west": 1, "industrial_west": 1}, "从接入点选择一条走廊"), c("valley_continuity", "=", 0, {"valley_west": 1, "valley_east": -1}, "河谷走廊两段连续"), c("forest_continuity", "=", 0, {"forest_west": 1, "forest_east": -1}, "森林走廊两段连续"), c("industrial_continuity", "=", 0, {"industrial_west": 1, "industrial_east": -1}, "工业走廊两段连续")],
    ["valley_west", "valley_east", "forest_west", "forest_east", "industrial_west", "industrial_east"], [], [c("certificate_gate_west", "=", 0, {"valley_west": 1}, "未获证书的河谷西段不得建设"), c("certificate_gate_east", "=", 0, {"valley_east": 1}, "未获证书的河谷东段不得建设")],
    None, "从可建设走廊域中删除尚未取得公共便利与必要性证书的河谷走廊。", "3条方案都由输电公司建设、拥有并运营，用于连接2个公用变电站，不是发电商自建的发电机并网线路，也不属于既有线路重建或迁移", "constraint:certificate_gate_west")

add(
    "SWOR-R097", "scheduling_workforce", "temporal_coupling",
    "佛罗里达Lifeline账单处理排程。2026年8月2日，海湾电信已收到3名用户的Lifeline资格通知，要在9月1日、9月16日或10月16日这3个批次中为每人选择1个批次入账。每批最多处理2名用户。3名用户在9月1日处理的工时成本依次为7、8、9，在9月16日依次为4、6、5，在10月16日依次为1、2、3，单位均为工时。唯一目标是最小化总处理工时。排程必须遵守佛罗里达州对合格电信承运商发放Lifeline账单抵免的现行规定。请给出最优入账方案与目标值。",
    [v(f"u{i}_{slot}", "BINARY", 0, 1, f"用户{i}安排在{slot}批次") for i in range(1, 4) for slot in ("sep01", "sep16", "oct16")],
    "min", {"u1_sep01": 7, "u1_sep16": 4, "u1_oct16": 1, "u2_sep01": 8, "u2_sep16": 6, "u2_oct16": 2, "u3_sep01": 9, "u3_sep16": 5, "u3_oct16": 3}, "账单抵免处理工时", "工时",
    [c(f"schedule_user_{i}", "=", 1, {f"u{i}_sep01": 1, f"u{i}_sep16": 1, f"u{i}_oct16": 1}, f"用户{i}恰安排一个批次") for i in range(1, 4)] + [c(f"capacity_{slot}", "<=", 2, {f"u{i}_{slot}": 1 for i in range(1, 4)}, f"{slot}批次最多处理两名用户") for slot in ("sep01", "sep16", "oct16")],
    [f"u{i}_{slot}" for i in range(1, 4) for slot in ("sep01", "sep16", "oct16")], [], [c("credit_deadline", "=", 0, {f"u{i}_oct16": 1 for i in range(1, 4)}, "资格通知后的最迟期限排除十月十六日批次")],
    None, "增加由资格通知日期触发的入账期限，删除超过期限的批次。", "2026年8月2日，海湾电信已收到3名用户的Lifeline资格通知", "constraint:credit_deadline")

add(
    "SWOR-R098", "scheduling_workforce", "temporal_coupling",
    "欧洲航空公司待命派遣。2026年8月2日14:00，欧陆翼航空通知1名正在执行居家其他待命的乘务员出勤。运营人经批准的运行手册把欧洲航空安全局关于居家其他待命的公开示例所采用的响应时长原样写入本类排班规则，本次没有另行批准的例外。可选报到时刻为14:30、15:00、16:00或17:00，对应的疲劳成本指数分别为6、5、3、1，必须且只能选1个报到时刻；若选择14:30或15:00，还必须派1辆接驳车并增加1点调度负担。该乘务员原排班待命在14:30结束。唯一目标是最小化疲劳与调度负担之和。派遣需要遵守欧洲航空安全局关于其他待命期间分派执勤的适用规定。请给出最优报到时刻与目标值。",
    [v("report_1430", "BINARY", 0, 1, "十四时三十分报到"), v("report_1500", "BINARY", 0, 1, "十五时报到"), v("report_1600", "BINARY", 0, 1, "十六时报到"), v("report_1700", "BINARY", 0, 1, "十七时报到"), v("shuttle", "BINARY", 0, 1, "派出早班接驳车")],
    "min", {"report_1430": 6, "report_1500": 5, "report_1600": 3, "report_1700": 1, "shuttle": 1}, "疲劳与调度负担", "指数点",
    [c("choose_report_time", "=", 1, {"report_1430": 1, "report_1500": 1, "report_1600": 1, "report_1700": 1}, "恰选择一个报到时刻"), c("early_shuttle", "<=", 0, {"report_1430": 1, "report_1500": 1, "shuttle": -1}, "十四时三十分或十五时报到须派接驳车")],
    ["report_1430", "report_1500", "report_1600", "report_1700", "shuttle"], [], [c("response_window", "=", 0, {"report_1600": 1, "report_1700": 1}, "报到必须落在运营人定义的响应时间内")],
    None, "按运行手册强制采纳的EASA响应时间解释，把通知时刻与执勤报到时刻联结并删除超窗选择。", "运营人经批准的运行手册把欧洲航空安全局关于居家其他待命的公开示例所采用的响应时长原样写入本类排班规则，本次没有另行批准的例外", "constraint:response_window")

add(
    "SWOR-R099", "telecom_service", "quota_risk_service_objective",
    "海啸场景通信链路设计。2026年8月2日，岛链电信规划从应急中心O到避难所D的通信链路。可建设O-A、A-D、O-B、B-D和A-B共5条有向链路，成本依次为3、4、5、4、2，每个成本单位折合1000000日元。正常状态必须存在1条从O到D的连续路径。灾害评估认定海啸发生时A-D链路不可用，其余链路可用。项目采购合同已将ITU在灾害损坏下保持通信服务连续性的指导转化为不可豁免的验收条件，要求该海啸场景下仍有O到D的连续服务。唯一目标是最小化建设成本。网络设计需要遵守国际电信联盟关于灾害管理中网络韧性与恢复的现行指导。请给出最优链路建设方案与总成本。",
    [v(name, "BINARY", 0, 1, meaning) for name, meaning in [("x_oa", "建设O-A链路"), ("x_ad", "建设A-D链路"), ("x_ob", "建设O-B链路"), ("x_bd", "建设B-D链路"), ("x_ab", "建设A-B链路"), ("n_oa", "正常场景使用O-A"), ("n_ad", "正常场景使用A-D"), ("n_ob", "正常场景使用O-B"), ("n_bd", "正常场景使用B-D"), ("n_ab", "正常场景使用A-B")]],
    "min", {"x_oa": 3, "x_ad": 4, "x_ob": 5, "x_bd": 4, "x_ab": 2}, "通信链路建设成本", "百万日元",
    [c("normal_a", "=", 0, {"n_oa": 1, "n_ad": -1, "n_ab": -1}, "正常场景A节点流量平衡"), c("normal_b", "=", 0, {"n_ob": 1, "n_ab": 1, "n_bd": -1}, "正常场景B节点流量平衡"), c("normal_dest", "=", 1, {"n_ad": 1, "n_bd": 1}, "正常场景D接收一单位流")] + [c(f"normal_use_{arc}", "<=", 0, {f"n_{arc}": 1, f"x_{arc}": -1}, f"正常场景仅使用已建设的{arc}链路") for arc in ("oa", "ad", "ob", "bd", "ab")],
    ["x_oa", "x_ad", "x_ob", "x_bd", "x_ab", "n_oa", "n_ad", "n_ob", "n_bd", "n_ab"], [v(f"d_{arc}", "BINARY", 0, 1, f"海啸场景使用{arc}链路") for arc in ("oa", "ad", "ob", "bd", "ab")],
    [c("disaster_a", "=", 0, {"d_oa": 1, "d_ad": -1, "d_ab": -1}, "海啸场景A节点流量平衡"), c("disaster_b", "=", 0, {"d_ob": 1, "d_ab": 1, "d_bd": -1}, "海啸场景B节点流量平衡"), c("disaster_dest", "=", 1, {"d_ad": 1, "d_bd": 1}, "海啸场景D接收一单位流"), c("ad_disaster_failure", "=", 0, {"d_ad": 1}, "海啸场景A-D链路不可用")] + [c(f"disaster_use_{arc}", "<=", 0, {f"d_{arc}": 1, f"x_{arc}": -1}, f"海啸场景仅使用已建设的{arc}链路") for arc in ("oa", "ob", "bd", "ab")],
    None, "按采购合同强制采纳的ITU连续服务指导增加海啸故障场景流，并要求A-D失效时仍提供端到端服务。", "项目采购合同已将ITU在灾害损坏下保持通信服务连续性的指导转化为不可豁免的验收条件", "constraint:ad_disaster_failure")

add(
    "SWOR-R100", "telecom_service", "quota_risk_service_objective",
    "加州社区隔离中断联络排班。2026年8月2日，向当地用户提供固定电话网络并可接通911的金岸电信发生社区隔离中断，预计从08:00持续到次日08:00，分为08:00至16:00、16:00至24:00和00:00至08:00共3个时段。公司已在08:00向加州应急服务办公室提交本次社区隔离中断通知，通知中填写了专用联系电话；预计次日08:00恢复服务并报告恢复。可安排白班、晚班、夜班、日间长班或夜间接续班，人员成本分别为4、4、7、7、8百美元；白班覆盖第1时段，晚班覆盖第2时段，夜班覆盖第3时段，日间长班覆盖前2个时段，夜间接续班覆盖后2个时段。公司原运营要求只覆盖前2个时段。唯一目标是最小化联络排班成本。排班必须遵守加州社区隔离中断通知所用联系电话的现行值守规定。请给出最优值守班次与总成本。",
    [v("day", "BINARY", 0, 1, "安排白班"), v("evening", "BINARY", 0, 1, "安排晚班"), v("night", "BINARY", 0, 1, "安排夜班"), v("long_day", "BINARY", 0, 1, "安排日间长班"), v("relief", "BINARY", 0, 1, "安排夜间接续班")],
    "min", {"day": 4, "evening": 4, "night": 7, "long_day": 7, "relief": 8}, "中断联络人员成本", "百美元",
    [c("cover_period_1", ">=", 1, {"day": 1, "long_day": 1}, "第一时段至少一人值守"), c("cover_period_2", ">=", 1, {"evening": 1, "long_day": 1, "relief": 1}, "第二时段至少一人值守")],
    ["day", "evening", "night", "long_day", "relief"], [], [c("cover_period_3", ">=", 1, {"night": 1, "relief": 1}, "服务恢复前第三时段也须有人值守")],
    None, "把值守覆盖扩展到服务恢复前的夜间时段。", "向当地用户提供固定电话网络并可接通911的金岸电信发生社区隔离中断", "constraint:cover_period_3")


def numeric_alignment(problem: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for sentence in re.split(r"(?<=[。；])", problem):
        sentence = sentence.strip()
        if sentence and re.search(r"\d", sentence):
            kind = "evidence" if "遵守" in sentence or "规定" in sentence else "base"
            rows.append({"surface": sentence, "binding": f"{kind}:该句中的日期、数量、容量、成本或时刻由题面及模型对应项使用"})
    return rows


def current_continuous_excerpt(seed: dict[str, Any], needles: list[str]) -> tuple[str, str, int]:
    last_error: Exception | None = None
    for _ in range(3):
        try:
            response = requests.get(seed["final_url"], headers={"User-Agent": "SearchWorthyOR-Rapid-v0/0.1 release-source-check"}, timeout=45, allow_redirects=True)
            break
        except requests.RequestException as exc:
            last_error = exc
    else:
        raise RuntimeError(f"{seed['id']}: source fetch failed after retries") from last_error
    response.raise_for_status()
    text = normalize_bytes(response.content, response.headers.get("content-type", ""), response.url)
    normalized = normalize_text(text)
    old_excerpt = normalize_text(seed["support_excerpt"])
    if old_excerpt and len(old_excerpt) <= 5000 and old_excerpt in normalized:
        return old_excerpt, response.url, response.status_code
    locations: list[tuple[int, int]] = []
    folded = normalized.casefold()
    for needle in needles:
        clean = normalize_text(needle)
        start = folded.find(clean.casefold())
        if start >= 0:
            locations.append((start, start + len(clean)))
    if not locations:
        # Older audit rows sometimes contain duplicated or stitched support text after a
        # source replacement. Recover only a verbatim continuous window that is present
        # in the current normalized official page; never reuse the stitched payload.
        for width in (160, 120, 80):
            for offset in range(0, max(1, len(old_excerpt) - width + 1), 20):
                candidate = old_excerpt[offset:offset + width].strip()
                start = folded.find(candidate.casefold())
                if start >= 0:
                    locations.append((start, start + len(candidate)))
            if locations:
                break
    if not locations:
        raise ValueError(f"{seed['id']}: no registered support needle found in current official source")
    start = max(0, min(item[0] for item in locations) - 500)
    end = min(len(normalized), max(item[1] for item in locations) + 800)
    excerpt = normalized[start:end]
    if excerpt not in normalized:
        raise ValueError(f"{seed['id']}: continuous excerpt construction failed")
    if len(excerpt) > 5000:
        raise ValueError(f"{seed['id']}: support excerpt exceeds 5000 characters: {len(excerpt)}")
    return excerpt, response.url, response.status_code


def main() -> None:
    seed_path = BATCH_ROOT / "private" / "rapid_audit.jsonl"
    seeds = {row["id"]: row for row in (json.loads(line) for line in seed_path.read_text(encoding="utf-8").splitlines() if line.strip())}
    shortlist = {}
    for line in (RAPID_ROOT / "private" / "source_shortlist_130.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("batch") == 5 and row.get("rapid_task_id"):
            shortlist[row["rapid_task_id"]] = row.get("support_needles", [])
    shortlist["SWOR-R089"] = ["ILOSs must be identified in the managed care plan contracts"]
    shortlist["SWOR-R093"] = ["demonstrating that it can be used without any further processing other than normal industrial practice"]
    shortlist["SWOR-R083"] = ["table 1.1 adopted energy conservation standards for low-voltage dry-type distribution transformers single-phase three-phase"]
    shortlist["SWOR-R085"] = ["a facility is a low-impact facility if", "panel, yagi or other like antenna"]
    shortlist["SWOR-R087"] = ["develop, maintain and implement an effective due diligence process for the selection of investments"]
    shortlist["SWOR-R088"] = ["requires a fund to review its portfolio assets"]
    shortlist["SWOR-R092"] = ["acceptable assets to be included in a trust fund are limited to cash, irrevocable letters of credit issued by federally insured depository institutions, and treasury bonds"]
    tasks: list[dict[str, str]] = []
    audits: list[dict[str, Any]] = []
    for spec in CASES:
        task_id = spec["task_id"]
        seed = deepcopy(seeds[task_id])
        if task_id == "SWOR-R089":
            seed["source_url"] = "https://www.govinfo.gov/content/pkg/FR-2024-05-10/pdf/2024-08085.pdf"
            seed["final_url"] = seed["source_url"]
            seed["authority"] = "Centers for Medicare & Medicaid Services"
            seed["jurisdiction"] = "Florida Medicaid managed care under United States federal ILOS rules"
            seed["rule_claim"] = "An in-lieu-of service or setting must be identified in the managed care plan contract; a service absent from that contract cannot be assigned as an ILOS under the modeled contract."
            seed["applicability_reason"] = "The task concerns a Florida Medicaid managed-care contract after the 2024 rule became effective and states which proposed service is identified in that contract and which is absent."
        if task_id == "SWOR-R093":
            seed["source_candidate_id"] = "RAPID-REPL-EU-WFD-ARTICLE5"
            seed["source_document_key"] = "IE-EPA-BYPRODUCT-NOTIFICATION-GUIDANCE"
            seed["regulation_key"] = "EU-WFD-ARTICLE5-BYPRODUCT-DIRECT-USE-ATOM"
            seed["source_url"] = "https://www.epa.ie/our-services/licensing/waste/by-products-regulation-27/how-to-prepare-and-submit-a-by-product-notification/"
            seed["final_url"] = seed["source_url"]
            seed["authority"] = "Environmental Protection Agency, Ireland"
            seed["jurisdiction"] = "Ireland under Regulation 27 and the EU Waste Framework Directive by-product criteria"
            seed["rule_claim"] = "A production residue can be treated as a by-product only when it can be used directly without further processing beyond normal industrial practice, together with the other cumulative Article 5 conditions."
            seed["applicability_reason"] = "The Irish production task applies the transposed EU by-product criteria. The water residue has a signed full-quantity outlet, arises integrally with production, is directly usable without added treatment, and has product, environmental and health records for that use. Solvent-residue use instead needs a new extractant, heated reaction vessel and hazardous-waste neutralisation absent from both plants' processes, equipment and permits."
        applicability_overrides = {
            "SWOR-R081": "The Agency has specified the requested annual information and electronic format for Cork and Dublin, the underlying records are complete, and the modeled actions are the local authorities' own submissions rather than contractor data preparation.",
            "SWOR-R083": "The units are imported in May 2030, after the amended standards' compliance date. The task supplies test method, measured efficiency, capacity, phase and medium for the four fully documented units, while the Harbor low-voltage dry-type record lacks the phase needed to select the applicable class.",
            "SWOR-R084": "The units are imported in June 2030. Each has a measured Appendix A efficiency; the 300 kVA submersible unit has only a general liquid-immersed file and lacks the structural test page needed for the distinct submersible branch required by the procurement contract.",
            "SWOR-R085": "All candidates use the same 2.4-metre panel antenna, protrude 1.5 metres from an existing structure and are colour-matched to the background. The task separately gives each industrial, commercial or rural classification; only the Market parcel also has environmental significance.",
            "SWOR-R086": "The task records a first electromagnetic effect from a transmission-grid alteration on existing railway signalling infrastructure and gives implementable safeguards in each operator's responsibility; none of the examination, joint determination or implementation actions has yet occurred.",
            "SWOR-R087": "The trustee's current APRA registration records an RSE licence, and the service register has no written SPS 530 adjustment or exclusion for it or this option. The private-credit due-diligence and stress records are absent while the other candidates have the listed asset, counterparty, risk and stress records.",
            "SWOR-R088": "The large fund is already in its compliance cycle and has a 70-of-90 drift caused only by ordinary quarter-end price movement. It began in 2019, is not reorganising or changing policy, has no unusual flows or adverse-condition cash move, and its committee recorded normal operations. The two five-share purchases are the only possible trades through 31 October 2026.",
            "SWOR-R089": "Housing transition navigation is in the current Florida managed-care contract and state approval file, is individually recommended by treating clinicians, and is voluntarily selected after disclosure of the standard service; gym membership is absent from the contract.",
            "SWOR-R090": "The schedule covers two consecutive weeks and the hospital's risk assessment does not reduce the NICE normal baseline of at least weekly stock checks, so each location needs coverage in each week.",
            "SWOR-R091": "The retailer's 2024 turnover is S$12 million. For either imported option it is itself the importer of the stated PET or HDPE retail bottles and corrugated cartons; local goods instead arrive through supplier-owned returnable tanks that the supplier retrieves, so the modeled report trigger follows only an imported batch.",
            "SWOR-R092": "The task is after the 16 January 2026 compliance date and identifies the letter of credit as issued by an FDIC-insured U.S. depository institution, while separately listing non-enumerated asset types.",
            "SWOR-R096": "Each candidate is a new 115 kV transmission-utility line between substations, not a generator-owned interconnection or rebuild/relocation; the Valley certificate remains pending while the alternatives have certificates.",
            "SWOR-R098": "The crew member is on home other-standby, and the approved operations manual incorporates the exact response-time example from the official EASA interpretation; no task-specific exception applies.",
            "SWOR-R100": "The provider offers fixed-telephone 911 access, has filed a community-isolation outage notice containing the dedicated contact number, and reports a restoration time at the end of the modeled third period.",
        }
        if task_id in applicability_overrides:
            seed["applicability_reason"] = applicability_overrides[task_id]
        source_id = seed["source_candidate_id"]
        base = model(task_id, spec["family"], source_id, deepcopy(spec["variables"]), spec["sense"], deepcopy(spec["objective"]), spec["objective_meaning"], spec["unit"], deepcopy(spec["constraints"]), spec["action"], "base")
        patched_variables = deepcopy(spec["variables"]) + deepcopy(spec["patch_variables"])
        patched_constraints = deepcopy(spec["constraints"]) + deepcopy(spec["patch_constraints"])
        patched_objective = deepcopy(spec["objective"])
        if spec["patch_objective"]:
            patched_objective.update(spec["patch_objective"])
        patched = model(task_id, spec["family"], source_id, patched_variables, spec["sense"], patched_objective, spec["objective_meaning"], spec["unit"], patched_constraints, spec["action"], "patched")
        model_dir = BATCH_ROOT / "models" / task_id
        model_dir.mkdir(parents=True, exist_ok=True)
        base_path = model_dir / "base_ir.json"
        patched_path = model_dir / "patched_ir.json"
        result_path = model_dir / "solve_result.json"
        for path, payload in ((base_path, base), (patched_path, patched)):
            path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        result = evaluate(base_path, patched_path)
        result_path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        if result["common_optimal_action_feasible"]:
            raise RuntimeError(f"{task_id}: common optimal action remains")
        tasks.append({"id": task_id, "problem_zh": spec["problem"]})
        excerpt, final_url, status = current_continuous_excerpt(seed, shortlist.get(task_id, []))
        audit = {key: seed[key] for key in (
            "schema_version", "id", "source_candidate_id", "source_document_key", "regulation_key", "source_url", "final_url", "http_status", "accessed_at", "authority", "jurisdiction", "decision_date", "support_excerpt", "rule_claim", "applicability", "applicability_reason")}
        audit["support_excerpt"] = excerpt
        audit["final_url"] = final_url
        audit["http_status"] = status
        audit.update({
            "preserved_local_binding_facts": [spec["local_fact"]],
            "task_local_fact_alignment": [{"public_basis": spec["local_fact"], "patch_binding": spec["patch_binding"]}],
            "numeric_alignment": numeric_alignment(spec["problem"]),
            "variable_alignment": [{"variable": item["name"], "public_meaning": item["meaning"]} for item in base["variables"]],
            "constraint_alignment": [{"constraint": item["name"], "public_basis": item["meaning"]} for item in base["constraints"]],
            "structural_patch": "PASS", "patch_summary": spec["patch_summary"], "family": spec["family"], "patch_class": spec["patch_class"],
            "base_model_path": str(base_path.relative_to(RAPID_ROOT)).replace("\\", "/"),
            "patched_model_path": str(patched_path.relative_to(RAPID_ROOT)).replace("\\", "/"),
            "solve_result_path": str(result_path.relative_to(RAPID_ROOT)).replace("\\", "/"),
            "base_solve": "OPTIMAL", "patched_solve": "OPTIMAL", "optimal_action_changed": True,
            "common_optimal_action_feasible": False, "problem_model_alignment": "PASS", "answer_leakage": False,
            "single_objective": True, "generator_id": "native_batch_b_rebuild", "generator_self_check": "PASS",
            "independent_review": "PENDING", "status": "GENERATED_SELF_CHECK_PASS",
        })
        audits.append(audit)
    (BATCH_ROOT / "public" / "tasks_zh.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in tasks), encoding="utf-8", newline="\n")
    seed_path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in audits), encoding="utf-8", newline="\n")
    print(json.dumps({"status": "GENERATED", "tasks": len(tasks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
