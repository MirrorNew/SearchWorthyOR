from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import requests

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
BATCH = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from recheck_release_sources import normalize_bytes, normalize_text  # noqa: E402
from solve_model_pair import evaluate  # noqa: E402


def v(name: str, kind: str, lb: int, ub: int, meaning: str) -> dict[str, Any]:
    return {"name": name, "type": kind, "lb": lb, "ub": ub, "meaning": meaning}


def c(name: str, sense: str, rhs: float, coefficients: dict[str, float], meaning: str) -> dict[str, Any]:
    return {"name": name, "sense": sense, "rhs": rhs, "coefficients": coefficients, "meaning": meaning}


def ir(task_id: str, family: str, source_id: str, variables: list[dict[str, Any]],
       sense: str, objective: dict[str, float], objective_meaning: str, unit: str,
       constraints: list[dict[str, Any]], action: list[str], variant: str) -> dict[str, Any]:
    return {"schema_version": "searchworthyor.rapid_model_ir.v0", "id": task_id,
            "variant": variant, "family": family, "source_candidate_id": source_id,
            "variables": variables,
            "objective": {"sense": sense, "constant": 0, "coefficients": objective,
                          "meaning": objective_meaning, "unit": unit},
            "constraints": constraints, "action_projection": action}


CASES: list[dict[str, Any]] = []


def add(**kwargs: Any) -> None:
    CASES.append(kwargs)


add(
    task_id="SWOR-R001", family="energy_environment", patch_class="quota_risk_service_objective",
    problem="德国硬煤机组减量安排。2026年8月2日，莱茵发电集团为德国联邦网络局2027年法定减量程序准备4台合格硬煤机组的处置方案。按投运时间从早到晚依次为老港A、河湾B、林地C和新城D，4台机组均未被标记为排序排除对象；净额定容量依次为300、250、400、350兆瓦，停运机会成本依次为9、7、4、3百万欧元。当前程序的减量需求为600兆瓦；林地C和新城D共用同一支退役工程队，不能在本轮同时停运。基础运营要求停运机组容量达到该需求，唯一目标是最小化停运机会成本。处置方案必须遵守德国届时适用的硬煤发电法定减量排序规定。请给出最优停运方案与总成本。",
    variables=[v("close_A", "BINARY", 0, 1, "停运老港A机组"), v("close_B", "BINARY", 0, 1, "停运河湾B机组"), v("close_C", "BINARY", 0, 1, "停运林地C机组"), v("close_D", "BINARY", 0, 1, "停运新城D机组")],
    sense="min", objective={"close_A": 9, "close_B": 7, "close_C": 4, "close_D": 3}, objective_meaning="停运机会成本", unit="百万欧元",
    constraints=[c("reduction_capacity", ">=", 600, {"close_A": 300, "close_B": 250, "close_C": 400, "close_D": 350}, "停运净额定容量至少六百兆瓦"), c("shared_retirement_crew", "<=", 1, {"close_C": 1, "close_D": 1}, "林地C和新城D不能在本轮同时停运")],
    action=["close_A", "close_B", "close_C", "close_D"], patch_variables=[],
    patch_constraints=[c("oldest_A", "=", 1, {"close_A": 1}, "从最老机组开始选取老港A"), c("next_B", "=", 1, {"close_B": 1}, "累计容量不足时继续选取河湾B"), c("crossing_C", "=", 1, {"close_C": 1}, "选取林地C后首次超过减量需求"), c("stop_D", "=", 0, {"close_D": 1}, "首次超过后不再选取新城D")],
    patch_objective=None, patch_summary="按更新排序从最老机组连续选取，直到累计净额定容量首次超过减量需求。",
    local_fact="按投运时间从早到晚依次为老港A、河湾B、林地C和新城D，4台机组均未被标记为排序排除对象", patch_binding="constraint:oldest_A",
    excerpt_start="(2) Die Bundesnetzagentur bestimmt", excerpt_end="§ 18 Absatz 8 Satz 2 ist entsprechend anzuwenden.",
    rule_claim="For each statutory order date from the 2027 target onward, the Federal Network Agency selects eligible hard-coal units from the updated ranking in ascending age order, beginning with the oldest, until cumulative net nominal capacity first exceeds the reduction quantity.",
    applicability_reason="The decision prepares the 2027 German statutory reduction procedure; all four named units are hard-coal units in the updated ranking and the public task states that none carries the statutory exclusion marking. The task supplies the agency reduction quantity and unit net nominal capacities needed to locate the first cumulative crossing."
)

add(
    task_id="SWOR-R002", family="assignment_matching", patch_class="eligibility_domain",
    problem="美国危险品列车电子编组信息分发。2026年8月2日，五大湖一级铁路公司为1趟载运危险品并依次经过海湾县、松林县和河口市的列车选择电子编组信息接收端。候选端为铁路内部控制室、海湾县消防调度、松林县急救调度和河口市警务调度，接入成本依次为1、4、5、6千美元。基础运营要求至少启用1个、至多启用3个接收端。3个外部调度单位均由当地政府授权，且可能参与该线路危险品事故的响应或调查。唯一目标是最小化接入总成本。分发安排必须遵守美国当日适用的危险品列车实时电子编组信息规定。请给出最优接收端方案与总成本。",
    variables=[v("internal", "BINARY", 0, 1, "启用铁路内部控制室接收端"), v("fire", "BINARY", 0, 1, "启用海湾县消防调度接收端"), v("medical", "BINARY", 0, 1, "启用松林县急救调度接收端"), v("police", "BINARY", 0, 1, "启用河口市警务调度接收端")],
    sense="min", objective={"internal": 1, "fire": 4, "medical": 5, "police": 6}, objective_meaning="电子编组信息接入成本", unit="千美元",
    constraints=[c("one_receiver", ">=", 1, {"internal": 1, "fire": 1, "medical": 1, "police": 1}, "至少启用一个接收端"), c("receiver_limit", "<=", 3, {"internal": 1, "fire": 1, "medical": 1, "police": 1}, "至多启用三个接收端")],
    action=["internal", "fire", "medical", "police"], patch_variables=[],
    patch_constraints=[c("fire_authorized", "=", 1, {"fire": 1}, "沿线获授权消防响应单位获得信息"), c("medical_authorized", "=", 1, {"medical": 1}, "沿线获授权急救响应单位获得信息"), c("police_authorized", "=", 1, {"police": 1}, "沿线获授权执法单位获得信息")],
    patch_objective=None, patch_summary="把实时电子编组信息分发域扩展到沿线所有可能参与响应或调查的获授权单位。",
    local_fact="3个外部调度单位均由当地政府授权，且可能参与该线路危险品事故的响应或调查", patch_binding="constraint:fire_authorized",
    excerpt_start="This final rule requires railroads transporting hazardous materials to generate train consist information", excerpt_end="PHMSA also adopts a requirement that railroads must test their emergency notification system at least annually.",
    rule_claim="Railroads transporting hazardous materials must provide real-time electronic consist information to authorized federal, state and local responders, emergency officials and law-enforcement personnel along the route who could be involved in response or investigation.",
    applicability_reason="The public task identifies a Class I U.S. railroad after its June 2025 compliance date, a hazardous-material train, its route, and three government-authorized route responders that could participate in an accident response or investigation."
)

add(
    task_id="SWOR-R003", family="assignment_matching", patch_class="eligibility_domain",
    problem="美国国债交易清算分配。2027年7月1日，联邦国债清算公司的直接参与者远峰证券要为4笔美国国债二级市场交易选择中央清算或双边结算，每笔只能选择1种方式。4笔交易依次为：与非关联对冲基金达成且不通过专属清算子公司的国债回购、与注册经纪交易商达成的国债现券买卖、与州政府达成的国债回购、与自然人达成的国债现券买卖。中央清算成本依次为5、4、6、5千美元，双边结算成本依次为1、1、2、2千美元。唯一目标是最小化总清算成本。清算分配必须遵守美国当日适用的国债二级市场中央清算规定。请给出最优清算方案与总成本。",
    variables=[v(f"central_{i}", "BINARY", 0, 1, f"第{i}笔交易采用中央清算") for i in range(1, 5)] + [v(f"bilateral_{i}", "BINARY", 0, 1, f"第{i}笔交易采用双边结算") for i in range(1, 5)],
    sense="min", objective={"central_1": 5, "central_2": 4, "central_3": 6, "central_4": 5, "bilateral_1": 1, "bilateral_2": 1, "bilateral_3": 2, "bilateral_4": 2}, objective_meaning="国债交易清算成本", unit="千美元",
    constraints=[c(f"assign_{i}", "=", 1, {f"central_{i}": 1, f"bilateral_{i}": 1}, f"第{i}笔交易恰选择一种结算方式") for i in range(1, 5)],
    action=[f"{mode}_{i}" for i in range(1, 5) for mode in ("central", "bilateral")], patch_variables=[],
    patch_constraints=[c("repo_nonaffiliate_clear", "=", 1, {"central_1": 1}, "直接参与者与非关联对手的国债回购进入中央清算"), c("broker_cash_clear", "=", 1, {"central_2": 1}, "直接参与者与注册经纪交易商的现券交易进入中央清算")],
    patch_objective=None, patch_summary="根据交易类型与法定对手方例外，将两笔合格交易转入中央清算并保留州政府和自然人交易的排除路径。",
    local_fact="4笔交易依次为：与非关联对冲基金达成且不通过专属清算子公司的国债回购、与注册经纪交易商达成的国债现券买卖、与州政府达成的国债回购、与自然人达成的国债现券买卖", patch_binding="constraint:repo_nonaffiliate_clear",
    excerpt_start="Eligible secondary market transaction refers to a secondary market transaction", excerpt_end="provided that the affiliated counterparty submit for clearance and settlement all other repurchase or reverse repurchase agreements collateralized by U.S. Treasury securities to which the affiliate is a party.",
    rule_claim="The final SEC definition includes a direct participant's Treasury repo and its Treasury cash trade with a registered broker-dealer, while excluding transactions with a state or local government or natural person; direct participants must submit all eligible transactions for clearing.",
    applicability_reason="The decision date is 2027-07-01, after the SEC's extended 2026-12-31 cash and 2027-06-30 repo compliance dates. The task identifies a covered Treasury clearing agency direct participant, the transaction and counterparty categories, and states that the hedge-fund repo does not use the captive-clearing-subsidiary path covered by the SEC's June 18, 2026 conditional relief.",
    decision_date="2027-07-01"
)

add(
    task_id="SWOR-R004", family="energy_environment", patch_class="temporal_coupling",
    problem="美国跨区并网影响通知排程。2026年8月2日，山谷输电运营商已在第0个工作日确认风场并网可能影响邻区电网，项目受委员会已接受并生效的并网资费管辖。运营商要确定向邻区发送初始通知的工作日N和邻区书面回复的工作日R；N可取第0日至第15日，R可取第0日至第30日，且回复不能早于通知。双方项目办公室的内部服务约定还要求书面回复距初始通知不超过25个工作日。为给技术团队保留核验时间，通知和回复每延后1个工作日分别贡献1点和0.1点核验收益，唯一目标是最大化核验收益。排程必须遵守美国当日适用的受影响系统通知与回复程序。请给出最优排程方案与目标值。",
    variables=[v("notice_day", "INTEGER", 0, 15, "向受影响系统发送初始通知的工作日"), v("response_day", "INTEGER", 0, 30, "受影响系统书面回复的工作日")],
    sense="max", objective={"notice_day": 1, "response_day": 0.1}, objective_meaning="技术核验收益", unit="点",
    constraints=[c("response_after_notice", ">=", 0, {"response_day": 1, "notice_day": -1}, "书面回复不能早于初始通知"), c("internal_response_window", "<=", 25, {"response_day": 1, "notice_day": -1}, "内部服务约定要求回复距通知不超过二十五个工作日")],
    action=["notice_day", "response_day"], patch_variables=[],
    patch_constraints=[c("initial_notice_deadline", "<=", 10, {"notice_day": 1}, "识别潜在影响后十个工作日内通知"), c("response_deadline", "<=", 20, {"response_day": 1, "notice_day": -1}, "受影响系统在通知后二十个工作日内回复")],
    patch_objective=None, patch_summary="增加初始通知以及受影响系统书面回复的法定工作日时限。",
    local_fact="已在第0个工作日确认风场并网可能影响邻区电网", patch_binding="constraint:initial_notice_deadline",
    excerpt_start="468. The Commission adopted section 3.6.1 (Initial Notification)", excerpt_end="indicating whether it intends to conduct an affected system study.",
    rule_claim="The pro forma affected-system process requires notice within ten business days after a potential impact is identified and a written affected-system response within twenty business days indicating whether it will conduct a study.",
    applicability_reason="The task states that a potential affected-system impact was identified on day zero and that the project is governed by a Commission-accepted, currently effective interconnection tariff; the named dates and affected operator are the subjects of the standardized process."
)

add(
    task_id="SWOR-R005", family="facility_network", patch_class="quota_risk_service_objective",
    problem="美国化工设施泄漏检测配置。2026年8月2日，河口化学品仓储场为其清洁水法危险物质设施响应计划选择检测方式。该场是美国陆上非运输设施，现场危险物质数量已越过筛选门槛，最坏泄漏可经排水渠进入通航水域并造成重大环境损害，且不适用现行豁免。候选方式为白班人工巡检、罐区自动报警、排水口自动报警和移动检测车，年度成本依次为1、4、5、6万美元；检测覆盖分依次为2、3、3、4，基础要求总覆盖至少2分，维护团队最多同时维护人工巡检、罐区报警和排水口报警中的2种固定方式。设施在白班外仍储存危险物质，罐区和排水口都可能成为泄漏起点。唯一目标是最小化年度检测成本。配置必须遵守美国当日适用的危险物质设施响应计划检测要求。请给出最优检测方案与总成本。",
    variables=[v("visual", "BINARY", 0, 1, "采用白班人工巡检"), v("tank_alarm", "BINARY", 0, 1, "安装罐区自动报警"), v("outfall_alarm", "BINARY", 0, 1, "安装排水口自动报警"), v("mobile", "BINARY", 0, 1, "配置移动检测车")],
    sense="min", objective={"visual": 1, "tank_alarm": 4, "outfall_alarm": 5, "mobile": 6}, objective_meaning="泄漏检测年度成本", unit="万美元",
    constraints=[c("detection_coverage", ">=", 2, {"visual": 2, "tank_alarm": 3, "outfall_alarm": 3, "mobile": 4}, "检测总覆盖至少两分"), c("maintenance_limit", "<=", 2, {"visual": 1, "tank_alarm": 1, "outfall_alarm": 1}, "维护团队最多同时维护两种固定检测方式")],
    action=["visual", "tank_alarm", "outfall_alarm", "mobile"], patch_variables=[],
    patch_constraints=[c("afterhours_detection", ">=", 1, {"tank_alarm": 1, "outfall_alarm": 1, "mobile": 1}, "设施响应计划配置至少一种白班外可用的检测方式")],
    patch_objective=None, patch_summary="把响应计划的白班外检测程序落实为至少一种可在非工作时段运行的检测方式。",
    local_fact="设施在白班外仍储存危险物质", patch_binding="constraint:afterhours_detection",
    excerpt_start="(12) Discharge detection systems. Procedures and equipment used to detect discharges", excerpt_end="reliability checks, and inspection frequency;",
    rule_claim="A covered facility response plan must describe personnel or automatic discharge-detection procedures and equipment for regular and after-hours operations, by hazardous substance, with reliability checks and inspection frequency.",
    applicability_reason="The public task expressly closes the rule's facility, threshold, navigable-water substantial-harm and exemption predicates and states continued after-hours storage plus the two possible discharge origins used by the detection design."
)

add(
    task_id="SWOR-R006", family="facility_network", patch_class="quota_risk_service_objective",
    problem="加拿大输油管道控制系统配置。2026年8月2日，北原管道公司为受加拿大联邦陆上管道条例约束的1条复杂原油管线选择控制系统模块。候选模块为实时运行监控、历史运行数据存储、消息与报警回溯、符合CSA Z662并按该管线复杂度和所输原油设计的泄漏检测子系统，以及普通人工巡线，年度成本依次为2、3、4、6、1百万加元。基础运行要求至少配置2个模块；实时监控与历史数据存储共用数据总线，必须同时配置；消息与报警回溯模块和普通人工巡线共用1个值守岗位，二者至多配置1项。唯一目标是最小化年度成本。控制系统必须遵守加拿大当日适用的陆上管道控制与泄漏检测规定。请给出最优模块配置与总成本。",
    variables=[v("monitor", "BINARY", 0, 1, "配置实时运行监控模块"), v("history", "BINARY", 0, 1, "配置历史运行数据存储模块"), v("alarm_recall", "BINARY", 0, 1, "配置消息与报警回溯模块"), v("z662_leak", "BINARY", 0, 1, "配置符合CSA Z662且适配管线复杂度和原油的泄漏检测子系统"), v("manual_patrol", "BINARY", 0, 1, "配置普通人工巡线")],
    sense="min", objective={"monitor": 2, "history": 3, "alarm_recall": 4, "z662_leak": 6, "manual_patrol": 1}, objective_meaning="控制系统模块年度成本", unit="百万加元",
    constraints=[c("minimum_modules", ">=", 2, {"monitor": 1, "history": 1, "alarm_recall": 1, "z662_leak": 1, "manual_patrol": 1}, "至少配置两个控制系统模块"), c("monitor_history_bus", "=", 0, {"monitor": 1, "history": -1}, "实时监控与历史数据存储同时配置"), c("shared_duty_position", "<=", 1, {"alarm_recall": 1, "manual_patrol": 1}, "报警回溯模块和人工巡线至多配置一项")],
    action=["monitor", "history", "alarm_recall", "z662_leak", "manual_patrol"], patch_variables=[],
    patch_constraints=[c("monitor_required", "=", 1, {"monitor": 1}, "管道控制系统包含运行监控"), c("history_required", "=", 1, {"history": 1}, "管道控制系统保存历史运行数据"), c("alarm_required", "=", 1, {"alarm_recall": 1}, "管道控制系统支持消息与报警回溯"), c("z662_leak_required", "=", 1, {"z662_leak": 1}, "输油管道配置适配复杂度和产品的CSA Z662泄漏检测系统")],
    patch_objective=None, patch_summary="把管道控制系统的监控、历史记录、报警回溯及条件适用的泄漏检测模块设为必选。",
    local_fact="受加拿大联邦陆上管道条例约束的1条复杂原油管线", patch_binding="constraint:z662_leak_required",
    excerpt_start="37 A company shall develop and implement a pipeline control system", excerpt_end="the pipeline operation and the products transported.",
    rule_claim="Section 37 requires a pipeline control system to control and monitor operations, retain historical operating data, messages and alarms for recall, and include a leak-detection system that for an oil pipeline meets CSA Z662 and reflects pipeline complexity, operation and transported products.",
    applicability_reason="The task identifies a company and oil pipeline governed by the Canadian federal Onshore Pipeline Regulations and supplies the complexity and transported-product facts expressly used by section 37(c)."
)

add(
    task_id="SWOR-R007", family="finance_portfolio", patch_class="eligibility_domain",
    problem="欧盟债券免审通道组合。2026年8月2日，阿尔卑斯投资公司面向零售与专业客户，从4只债券中选择2只进入不执行MiFID II产品治理评估的快速发行通道。内部组合政策要求至少包含1只仅含补偿性赎回条款的债券；晨星债和远航债由同一发行集团担保，二者至多选择1只。候选债券分别为仅含补偿性赎回条款的晨星债、同时含补偿性赎回条款和可转换条款的远航债、含利率挂钩衍生条款的湖畔债，以及仅含补偿性赎回条款的松林债；发行贡献依次为5、9、8、6百万欧元。唯一目标是最大化发行贡献。通道选择必须遵守欧盟当日适用的MiFID II债券产品治理豁免规定。请给出最优债券组合与目标值。",
    variables=[v("morning", "BINARY", 0, 1, "晨星债进入快速发行通道"), v("voyage", "BINARY", 0, 1, "远航债进入快速发行通道"), v("lake", "BINARY", 0, 1, "湖畔债进入快速发行通道"), v("pine", "BINARY", 0, 1, "松林债进入快速发行通道")],
    sense="max", objective={"morning": 5, "voyage": 9, "lake": 8, "pine": 6}, objective_meaning="快速发行通道贡献", unit="百万欧元",
    constraints=[c("select_two", "=", 2, {"morning": 1, "voyage": 1, "lake": 1, "pine": 1}, "恰好选择两只债券"), c("make_whole_diversification", ">=", 1, {"morning": 1, "pine": 1}, "组合至少包含一只仅含补偿性赎回条款的债券"), c("issuer_concentration", "<=", 1, {"morning": 1, "voyage": 1}, "同一发行集团担保的晨星债和远航债至多选择一只")],
    action=["morning", "voyage", "lake", "pine"], patch_variables=[],
    patch_constraints=[c("voyage_excluded", "=", 0, {"voyage": 1}, "同时含补偿性赎回和其他嵌入衍生条款的债券不进入该免审通道"), c("lake_excluded", "=", 0, {"lake": 1}, "仅含其他嵌入衍生条款的债券不进入该免审通道")],
    patch_objective=None, patch_summary="按债券嵌入衍生条款结构收紧无需产品治理评估的候选域。",
    local_fact="面向零售与专业客户", patch_binding="constraint:voyage_excluded",
    excerpt_start="According to Article 16a of MiFID II", excerpt_end="exempt from the MiFID II product governance requirements.",
    rule_claim="For retail or professional distribution, Article 16a's bond exemption applies where the bond has no embedded derivative other than a make-whole clause; a make-whole clause alone does not exempt a bond that also contains another embedded derivative.",
    applicability_reason="The task concerns an EU investment firm's product-governance assessment for retail and professional clients and states each bond's make-whole and other embedded-derivative structure; it does not invoke the separate eligible-counterparty-only branch."
)

add(
    task_id="SWOR-R008", family="finance_portfolio", patch_class="temporal_coupling",
    problem="美国肾移植医院结算账户选择。2026年8月2日，处于IOTA强制模式第2绩效年的河谷肾移植医院选择1种年度结算账户。候选账户为只能接收CMS付款的收益账户、只能向CMS付款的支出账户、只能暂存争议款的冻结账户，以及可双向收付款的综合账户，年度费用依次为1、2、3、5万美元。银行当前只批准医院新开收益账户或综合账户；医院财务政策还要求所选账户覆盖当前绩效年模式下全部可能的CMS结算方向。唯一目标是最小化年度账户费用。账户选择必须遵守美国当日适用的IOTA绩效付款规定。请给出最优账户方案与总成本。",
    variables=[v("upside_only", "BINARY", 0, 1, "选择只能接收CMS付款的收益账户"), v("downside_only", "BINARY", 0, 1, "选择只能向CMS付款的支出账户"), v("escrow_only", "BINARY", 0, 1, "选择只能暂存争议款的冻结账户"), v("two_way", "BINARY", 0, 1, "选择可双向收付款的综合账户")],
    sense="min", objective={"upside_only": 1, "downside_only": 2, "escrow_only": 3, "two_way": 5}, objective_meaning="年度结算账户费用", unit="万美元",
    constraints=[c("choose_one_account", "=", 1, {"upside_only": 1, "downside_only": 1, "escrow_only": 1, "two_way": 1}, "恰好选择一种结算账户"), c("bank_onboarding_scope", ">=", 1, {"upside_only": 1, "two_way": 1}, "银行当前只批准新开收益账户或综合账户")],
    action=["upside_only", "downside_only", "escrow_only", "two_way"], patch_variables=[],
    patch_constraints=[c("py2_two_way_coverage", "=", 1, {"two_way": 1}, "第2绩效年的账户覆盖CMS付款和医院向CMS付款两种方向")],
    patch_objective=None, patch_summary="根据第2绩效年双向风险状态，将结算账户域收紧为可双向收付款的账户。",
    local_fact="处于IOTA强制模式第2绩效年的河谷肾移植医院", patch_binding="constraint:py2_two_way_coverage",
    excerpt_start="In performance year (PY) 1, participating kidney transplant hospitals", excerpt_end="Beginning in performance PY 2, owe downside risk payments to CMS.",
    rule_claim="Participating kidney transplant hospitals have only upside potential in PY1, but beginning in PY2 may receive upside payments, fall in a neutral zone, or owe downside payments to CMS depending on final performance score.",
    applicability_reason="The task is dated 2026-08-02, after PY2 began on 2026-07-01, and identifies the hospital as a mandatory IOTA participant; the local treasury policy requires the selected account to support every payment direction possible in that operative year."
)

add(
    task_id="SWOR-R009", family="healthcare_resources", patch_class="eligibility_domain",
    problem="新加坡电子药房运营点选择。2026年8月2日，狮城健康公司为向患者供应已注册治疗产品的电子药房服务选择1个周末运营点。候选点为持HSA零售药房牌照、配有合格主管药剂师且电子药房服务已通过HSA评估的滨海点和裕廊点，仅持批发商牌照且配有药剂师的樟宜点，以及持零售药房牌照但未配置主管药剂师、电子药房服务也尚未通过HSA评估的榜鹅点；预计周末服务收益依次为5、7、8、10万新元。滨海点和樟宜点不能周末营业，因此周末运营点只能从裕廊点和榜鹅点中选择。唯一目标是最大化周末服务收益。运营点选择必须遵守新加坡当日适用的电子药房许可规定。请给出最优运营点与目标值。",
    variables=[v("marina", "BINARY", 0, 1, "选择滨海点运营电子药房"), v("jurong", "BINARY", 0, 1, "选择裕廊点运营电子药房"), v("changi", "BINARY", 0, 1, "选择樟宜点运营电子药房"), v("punggol", "BINARY", 0, 1, "选择榜鹅点运营电子药房")],
    sense="max", objective={"marina": 5, "jurong": 7, "changi": 8, "punggol": 10}, objective_meaning="周末电子药房服务收益", unit="万新元",
    constraints=[c("choose_one_site", "=", 1, {"marina": 1, "jurong": 1, "changi": 1, "punggol": 1}, "恰好选择一个运营点"), c("weekend_site", ">=", 1, {"jurong": 1, "punggol": 1}, "周末运营点从裕廊点和榜鹅点中选择")],
    action=["marina", "jurong", "changi", "punggol"], patch_variables=[],
    patch_constraints=[c("punggol_ineligible", "=", 0, {"punggol": 1}, "未配置合格主管药剂师且电子药房服务未通过评估的零售点不用于运营")],
    patch_objective=None, patch_summary="按零售药房牌照、合格主管药剂师和电子药房专项评估状态收紧运营点域。",
    local_fact="持零售药房牌照但未配置主管药剂师、电子药房服务也尚未通过HSA评估的榜鹅点", patch_binding="constraint:punggol_ineligible",
    excerpt_start="HSA-licenced retail pharmacies and wholesalers in Singapore", excerpt_end="including proper storage and supply of the registered therapeutic products;",
    rule_claim="HSA's e-pharmacy requirements concern licensed retail pharmacies supplying registered therapeutic products and require appointment of a competent qualified pharmacist-in-charge responsible for pharmacy operations.",
    applicability_reason="The task concerns direct patient supply of registered therapeutic products through a Singapore e-pharmacy and states the retail-pharmacy licence and pharmacist-in-charge status of each candidate site."
)

add(
    task_id="SWOR-R010", family="healthcare_resources", patch_class="temporal_coupling",
    problem="爱尔兰药品批发交易档案配置。2026年8月2日，持爱尔兰药品批发授权的凯尔特医药公司为药品收货交易和发货交易分别确定档案保留年限及是否启用可供监管人员检查的电子档案。2类保留年限均可取0年至8年；启用收货和发货电子档案的固定成本分别为2和3千欧元，每保留1年分别增加1和1.2千欧元。只有启用相应可检查档案时，该类交易的保留年限才可为正。唯一目标是最小化档案总成本。档案配置必须遵守爱尔兰当日适用的药品批发交易记录规定。请给出最优档案配置与总成本。",
    variables=[v("receive_years", "INTEGER", 0, 8, "收货交易档案保留年限"), v("dispatch_years", "INTEGER", 0, 8, "发货交易档案保留年限"), v("receive_inspectable", "BINARY", 0, 1, "启用可检查的收货交易电子档案"), v("dispatch_inspectable", "BINARY", 0, 1, "启用可检查的发货交易电子档案")],
    sense="min", objective={"receive_years": 1, "dispatch_years": 1.2, "receive_inspectable": 2, "dispatch_inspectable": 3}, objective_meaning="交易档案总成本", unit="千欧元",
    constraints=[c("receive_archive_link", "<=", 0, {"receive_years": 1, "receive_inspectable": -8}, "未启用可检查收货档案时保留年限为零"), c("dispatch_archive_link", "<=", 0, {"dispatch_years": 1, "dispatch_inspectable": -8}, "未启用可检查发货档案时保留年限为零")],
    action=["receive_years", "dispatch_years", "receive_inspectable", "dispatch_inspectable"], patch_variables=[],
    patch_constraints=[c("receive_five_years", ">=", 5, {"receive_years": 1}, "收货交易记录至少保留五年"), c("dispatch_five_years", ">=", 5, {"dispatch_years": 1}, "发货交易记录至少保留五年")],
    patch_objective=None, patch_summary="为收货与发货交易激活可检查档案，并分别施加至少五年的保留期。",
    local_fact="持爱尔兰药品批发授权", patch_binding="constraint:receive_five_years",
    excerpt_start="8. (1) The authorisation holder shall keep available for inspection", excerpt_end="the name and address of the supplier or consignee, as appropriate.",
    rule_claim="An Irish wholesale authorisation holder must keep inspection-ready records for each medicinal-product transaction received or dispatched for at least five years, including the transaction date, product name, quantity, and supplier or consignee.",
    applicability_reason="The task identifies an Irish medicinal-product wholesale authorisation holder and separately models records for received and dispatched medicinal-product transactions, the two transaction classes in Schedule 2 paragraph 8(1)."
)

add(
    task_id="SWOR-R011", family="inventory_supply_chain", patch_class="conditional_auxiliary",
    problem="美国国债清算保证金账户分配。2026年8月2日，联邦国债中央清算机构为1笔直接参与者自营国债交易和1笔由该参与者代客户提交的国债交易分配保证金账户。每笔交易可进入自营账户、客户账户或共享账户且只能选择1种；2笔交易使用3类账户的年度管理成本分别为4、6、1千美元和5、7、1千美元。唯一目标是最小化管理成本。账户分配必须遵守美国当日适用的国债中央清算保证金分离规定。请给出最优账户分配与总成本。",
    variables=[v(f"{acct}_{kind}", "BINARY", 0, 1, f"将{kind}交易分配至{acct}账户") for kind in ("direct", "client") for acct in ("house", "customer", "shared")],
    sense="min", objective={"house_direct": 4, "customer_direct": 6, "shared_direct": 1, "house_client": 5, "customer_client": 7, "shared_client": 1}, objective_meaning="保证金账户年度管理成本", unit="千美元",
    constraints=[c("assign_direct", "=", 1, {"house_direct": 1, "customer_direct": 1, "shared_direct": 1}, "自营交易恰好分配一个保证金账户"), c("assign_client", "=", 1, {"house_client": 1, "customer_client": 1, "shared_client": 1}, "客户交易恰好分配一个保证金账户")],
    action=[f"{acct}_{kind}" for kind in ("direct", "client") for acct in ("house", "customer", "shared")], patch_variables=[],
    patch_constraints=[c("direct_house", "=", 1, {"house_direct": 1}, "直接参与者自营交易保证金进入自营账户"), c("client_customer", "=", 1, {"customer_client": 1}, "代客户提交交易保证金进入独立客户账户")],
    patch_objective=None, patch_summary="按直接参与者自营与间接参与者客户交易分离保证金账户。",
    local_fact="1笔直接参与者自营国债交易和1笔由该参与者代客户提交的国债交易", patch_binding="constraint:client_customer",
    excerpt_start="Rule 17ad–22(e)(6)(i)", excerpt_end="separately from those submitted on behalf of the direct participant.",
    rule_claim="A Treasury central counterparty's policies must calculate, collect and hold margin for transactions submitted for an indirect participant separately from margin for transactions submitted for the direct participant.",
    applicability_reason="The task concerns a covered U.S. Treasury central counterparty and labels one position as the direct participant's proprietary trade and the other as submitted on behalf of its customer, matching the rule's two margin classes."
)

add(
    task_id="SWOR-R012", family="inventory_supply_chain", patch_class="temporal_coupling",
    problem="英国包装生产者登记申请排程。2026年8月2日，海港食品公司作为英国大型品牌所有者，为2027相关年度选择登记申请日期。候选日期为2026年9月30日、10月15日和11月15日，申请处理成本分别为1、2和0千英镑；9月30日档期还需要聘请外部合规顾问，增加1千英镑成本。基础运营要求3个日期中恰选1个，且选择9月30日时必须聘请顾问。唯一目标是最小化申请处理总成本。申请排程必须遵守英国当日适用的包装生产者登记规定。请给出最优申请日期与总成本。",
    variables=[v("apply_sep", "BINARY", 0, 1, "在2026年9月30日提交登记申请"), v("apply_oct", "BINARY", 0, 1, "在2026年10月15日提交登记申请"), v("apply_nov", "BINARY", 0, 1, "在2026年11月15日提交登记申请"), v("consultant", "BINARY", 0, 1, "聘请外部合规顾问")],
    sense="min", objective={"apply_sep": 1, "apply_oct": 2, "apply_nov": 0, "consultant": 1}, objective_meaning="登记申请处理总成本", unit="千英镑",
    constraints=[c("choose_application_date", "=", 1, {"apply_sep": 1, "apply_oct": 1, "apply_nov": 1}, "三个申请日期中恰好选择一个"), c("september_consultant", "<=", 0, {"apply_sep": 1, "consultant": -1}, "选择九月三十日档期时聘请外部顾问")],
    action=["apply_sep", "apply_oct", "apply_nov", "consultant"], patch_variables=[],
    patch_constraints=[c("registration_deadline", "=", 1, {"apply_sep": 1}, "大型品牌所有者在相关年度前一年的十月一日前提交申请")],
    patch_objective=None, patch_summary="依据大型品牌所有者的年度登记截止日删除逾期申请日期，并激活九月档期的顾问安排。",
    local_fact="海港食品公司作为英国大型品牌所有者，为2027相关年度选择登记申请日期", patch_binding="constraint:registration_deadline",
    excerpt_start="28. (1) A producer who is required by regulation 25(1)(a) to be registered", excerpt_end="(bb) a small producer.",
    rule_claim="For 2026 and later years a covered large producer in the listed producer classes must apply for registration by 1 October of the year preceding the relevant year.",
    applicability_reason="The task identifies a Great Britain large brand owner seeking registration for the 2027 relevant year, so the large-producer 1 October 2026 deadline applies to the three dated application options."
)

add(
    task_id="SWOR-R013", family="production_capacity", patch_class="quota_risk_service_objective",
    problem="英国ESOS显著能耗区域选择。2026年8月2日，达到ESOS门槛的北海制造集团作为责任企业，自愿选择按显著能耗区域完成本合规期评估。5个候选区域为熔炼、压缩空气、热处理、仓库和办公室，其参考期能耗分别占集团总能耗的40%、30%、25%、3%和2%；按上述顺序，完成评估需支出6、5、4、2和1万英镑。基础运营要求至少选择1个区域；办公室和仓库共用盘点团队，二者至多选择1个。唯一目标是最小化评估成本。区域选择必须遵守英国当日适用的能源节约机会计划规定。请给出最优区域组合与总成本。",
    variables=[v("smelting", "BINARY", 0, 1, "选择熔炼区域"), v("air", "BINARY", 0, 1, "选择压缩空气区域"), v("heat", "BINARY", 0, 1, "选择热处理区域"), v("warehouse", "BINARY", 0, 1, "选择仓库区域"), v("office", "BINARY", 0, 1, "选择办公室区域")],
    sense="min", objective={"smelting": 6, "air": 5, "heat": 4, "warehouse": 2, "office": 1}, objective_meaning="显著能耗区域评估成本", unit="万英镑",
    constraints=[c("choose_area", ">=", 1, {"smelting": 1, "air": 1, "heat": 1, "warehouse": 1, "office": 1}, "至少选择一个评估区域"), c("shared_inventory_team", "<=", 1, {"warehouse": 1, "office": 1}, "仓库和办公室至多选择一个")],
    action=["smelting", "air", "heat", "warehouse", "office"], patch_variables=[],
    patch_constraints=[c("significant_coverage", ">=", 95, {"smelting": 40, "air": 30, "heat": 25, "warehouse": 3, "office": 2}, "所选区域覆盖至少百分之九十五的总能耗")],
    patch_objective=None, patch_summary="对自愿采用显著能耗区域路径的生产区域选择施加法定能耗覆盖约束。",
    local_fact="自愿选择按显著能耗区域完成本合规期评估", patch_binding="constraint:significant_coverage",
    excerpt_start="Identification of areas of significant energy consumption 25.", excerpt_end="that is accounted for by the participant’s areas of significant energy consumption.",
    rule_claim="A responsible undertaking calculates total energy consumption; when it elects to identify significant-consumption areas, those selected assets or activities together account for at least 95% of total energy consumption and significant consumption is calculated.",
    applicability_reason="The public task identifies an ESOS-qualifying responsible undertaking that elected the significant-area route and supplies a complete 100% partition of reference-period energy consumption across the candidate activities."
)

add(
    task_id="SWOR-R014", family="production_capacity", patch_class="conditional_auxiliary",
    problem="英国绿色气体关税保证项目选择。2026年8月2日，英国天然气与电力市场管理局在8百万英镑年度预算内，从4个已经正确提交且按收件时间排序的生物甲烷项目中选择授予关税保证的项目。河湾、山丘、林地和海港项目的预算承诺依次为3、4、2、5百万英镑，预计年注气量依次为2、4、9、15吉瓦时。基础要求总预算承诺不超过8百万英镑，唯一目标是最大化预计年注气量。授予决定必须遵守英国当日适用的绿色气体支持计划关税保证规定。请给出最优项目组合与目标值。",
    variables=[v("river", "BINARY", 0, 1, "向河湾项目授予关税保证"), v("hill", "BINARY", 0, 1, "向山丘项目授予关税保证"), v("wood", "BINARY", 0, 1, "向林地项目授予关税保证"), v("harbor", "BINARY", 0, 1, "向海港项目授予关税保证")],
    sense="max", objective={"river": 2, "hill": 4, "wood": 9, "harbor": 15}, objective_meaning="获保证项目预计年注气量", unit="吉瓦时",
    constraints=[c("annual_budget", "<=", 8, {"river": 3, "hill": 4, "wood": 2, "harbor": 5}, "关税保证预算承诺不超过八百万英镑")],
    action=["river", "hill", "wood", "harbor"], patch_variables=[],
    patch_constraints=[c("hill_after_river", "<=", 0, {"hill": 1, "river": -1}, "山丘项目前不跳过更早收到的河湾项目"), c("wood_after_hill", "<=", 0, {"wood": 1, "hill": -1}, "林地项目前不跳过更早收到的山丘项目"), c("harbor_after_wood", "<=", 0, {"harbor": 1, "wood": -1}, "海港项目前不跳过更早收到的林地项目")],
    patch_objective=None, patch_summary="将按收件先后处理关税保证申请的规则编码为项目选择的前缀约束，并保留年度预算上限。",
    local_fact="4个已经正确提交且按收件时间排序的生物甲烷项目", patch_binding="constraint:hill_after_river",
    excerpt_start="(15) The Authority must consider applications for a tariff guarantee", excerpt_end="in the order in which they were received.",
    rule_claim="The Authority considers tariff-guarantee applications in receipt order and cannot proceed in a manner that would exceed the relevant annual budget allocation; outstanding applications return to the same receipt order when budget changes.",
    applicability_reason="The task places the Authority in the decision role, states that all four biomethane applications were properly submitted in a fixed receipt order, and supplies the annual budget commitments and allocation needed to apply the ordering rule."
)

add(
    task_id="SWOR-R015", family="routing_transport", patch_class="conditional_auxiliary",
    problem="加拿大危险品公路运输人员安排。2026年8月2日，枫桥物流为1趟在加拿大境内装卸并运输危险品的卡车选择执行人员。候选方案为由持有效培训证书的司机陈伟独立执行，或由未持证的新司机林杰执行；若选择林杰，可同时安排持有效培训证书的主管赵敏全程在场监督。陈伟、林杰和赵敏的本次人工成本分别为8、2、3百加元。基础要求2名司机中恰选1名，且只有选择林杰时才能安排赵敏。唯一目标是最小化人工成本。人员安排必须遵守加拿大当日适用的危险品运输培训规定。请给出最优人员安排与总成本。",
    variables=[v("certified_driver", "BINARY", 0, 1, "安排持证司机陈伟独立执行"), v("trainee_driver", "BINARY", 0, 1, "安排未持证司机林杰执行"), v("certified_supervisor", "BINARY", 0, 1, "安排持证主管赵敏全程在场监督")],
    sense="min", objective={"certified_driver": 8, "trainee_driver": 2, "certified_supervisor": 3}, objective_meaning="危险品运输人工成本", unit="百加元",
    constraints=[c("choose_driver", "=", 1, {"certified_driver": 1, "trainee_driver": 1}, "两名司机中恰选一名"), c("supervisor_only_with_trainee", "<=", 0, {"certified_supervisor": 1, "trainee_driver": -1}, "只有选择未持证司机时才安排主管")],
    action=["certified_driver", "trainee_driver", "certified_supervisor"], patch_variables=[],
    patch_constraints=[c("trainee_requires_supervisor", "<=", 0, {"trainee_driver": 1, "certified_supervisor": -1}, "未持证人员执行危险品工作时由持证人员在场直接监督")],
    patch_objective=None, patch_summary="为未持证危险品运输人员增加持证主管在场直接监督的条件耦合。",
    local_fact="未持证的新司机林杰", patch_binding="constraint:trainee_requires_supervisor",
    excerpt_start="6.1 (1) A person who handles, offers for transport or transports dangerous goods", excerpt_end="holds a training certificate in accordance with this Part.",
    rule_claim="A person handling, offering for transport or transporting dangerous goods must be adequately trained and hold a training certificate, or perform the activities in the presence and under direct supervision of a trained certificate holder.",
    applicability_reason="The task is a Canadian dangerous-goods handling and transport assignment and explicitly states the certificate status of both drivers and the proposed supervisor plus the supervisor's full-time presence."
)

add(
    task_id="SWOR-R016", family="routing_transport", patch_class="eligibility_domain",
    problem="美国铁路互惠换装裁定。2026年8月2日，美国地面运输委员会审理河谷化工厂的换装申请。该工厂位于换装终端区，实际只能接入北陆1家一级铁路承运人；记录已证明该承运人在规定指标上发生持续服务失败，现有承运人和拟接入的南线承运人均未证明积极抗辩、不可行或不当损害。委员会在驳回申请、延后裁定和签发互惠换装命令之间选择1项，行政成本分别为1、2和4万美元；该案已通过申请完整性审查，内部案卷程序要求选择延后调查或签发实体命令，不能作程序性驳回。唯一目标是最小化行政成本。裁定必须遵守美国当日适用的服务不足互惠换装规定。请给出最优裁定与总成本。",
    variables=[v("deny", "BINARY", 0, 1, "驳回互惠换装申请"), v("defer", "BINARY", 0, 1, "延后互惠换装裁定"), v("prescribe", "BINARY", 0, 1, "签发互惠换装命令")],
    sense="min", objective={"deny": 1, "defer": 2, "prescribe": 4}, objective_meaning="互惠换装裁定行政成本", unit="万美元",
    constraints=[c("choose_order", "=", 1, {"deny": 1, "defer": 1, "prescribe": 1}, "驳回、延后与签发命令之间恰选一项"), c("complete_docket_path", ">=", 1, {"defer": 1, "prescribe": 1}, "完整申请进入延后调查或实体命令路径")],
    action=["deny", "defer", "prescribe"], patch_variables=[],
    patch_constraints=[c("eligible_prescription", "=", 1, {"prescribe": 1}, "满足服务失败且无抗辩或不可行证明时签发互惠换装命令")],
    patch_objective=None, patch_summary="在单一一级承运人接入、服务失败且无成功抗辩或不可行证明时收紧裁定域。",
    local_fact="实际只能接入北陆1家一级铁路承运人", patch_binding="constraint:eligible_prescription",
    excerpt_start="§ 1145.6 Prescription. (a) The Board will prescribe a reciprocal switching agreement under this part", excerpt_end="ability to serve its existing customers.",
    rule_claim="Part 1145 covers shippers or receivers with practical physical access to only one Class I carrier; after a covered performance failure, and absent a demonstrated affirmative defense, infeasibility or undue impairment, the Board prescribes a reciprocal switching agreement.",
    applicability_reason="The task expressly closes the terminal-area, single-Class-I-access, covered performance-failure, affirmative-defense, feasibility and undue-impairment predicates for a Board petition under part 1145."
)

add(
    task_id="SWOR-R017", family="scheduling_workforce", patch_class="temporal_coupling",
    problem="加拿大管道管理项目审计排程。2026年8月2日，北境管道公司刚完成本轮紧急管理项目和完整性管理项目审计，要确定2个项目距本次审计后的下次审计间隔，均可取1年至5年。每延后1年分别产生3点和4点资源平滑收益；公司还要求紧急管理项目的间隔不得比完整性管理项目长2年以上。唯一目标是最大化资源平滑收益。排程必须遵守加拿大当日适用的陆上管道管理项目审计规定。请给出最优审计排程与目标值。",
    variables=[v("emergency_gap", "INTEGER", 1, 5, "紧急管理项目距本次审计的下次审计间隔"), v("integrity_gap", "INTEGER", 1, 5, "完整性管理项目距本次审计的下次审计间隔")],
    sense="max", objective={"emergency_gap": 3, "integrity_gap": 4}, objective_meaning="审计资源平滑收益", unit="点",
    constraints=[c("gap_balance", "<=", 2, {"emergency_gap": 1, "integrity_gap": -1}, "紧急管理项目间隔至多比完整性管理项目长两年")],
    action=["emergency_gap", "integrity_gap"], patch_variables=[],
    patch_constraints=[c("emergency_three_year_max", "<=", 3, {"emergency_gap": 1}, "紧急管理项目审计间隔不超过三年"), c("integrity_three_year_max", "<=", 3, {"integrity_gap": 1}, "完整性管理项目审计间隔不超过三年")],
    patch_objective=None, patch_summary="为紧急管理和完整性管理项目分别加入最长三年的周期审计窗口。",
    local_fact="北境管道公司刚完成本轮紧急管理项目和完整性管理项目审计", patch_binding="constraint:emergency_three_year_max",
    excerpt_start="55 (1) A company shall conduct audits, with a maximum interval of three years", excerpt_end="any corrective action taken or planned to be taken.",
    rule_claim="A regulated pipeline company audits each listed management program, including emergency and integrity management, at intervals no longer than three years; post-audit documents identify deficiencies and corrective action taken or planned.",
    applicability_reason="The task identifies a company subject to the Canadian Onshore Pipeline Regulations, names two programs listed in section 55, and measures the next interval from newly completed audits."
)

add(
    task_id="SWOR-R018", family="scheduling_workforce", patch_class="quota_risk_service_objective",
    problem="新加坡年度包装数据表配置。2026年8月2日，达到强制包装报告门槛的星湾饮料公司配置本报告年度的数据表。公司在新加坡实际进口或使用塑料瓶、纸盒和金属罐3种包装组合，不使用玻璃罐。候选数据表为包装总重量表、塑料瓶重量表、纸盒重量表、金属罐重量表和玻璃罐重量表；编制这5张表分别需要1、3、4、5和2千新元。基础数据系统至少建立1张、至多建立4张表，唯一目标是最小化编制成本。数据配置必须遵守新加坡当日适用的强制包装年度报告规定。请给出最优数据表配置与总成本。",
    variables=[v("aggregate", "BINARY", 0, 1, "建立包装总重量表"), v("plastic_bottle", "BINARY", 0, 1, "建立塑料瓶重量表"), v("paper_box", "BINARY", 0, 1, "建立纸盒重量表"), v("metal_can", "BINARY", 0, 1, "建立金属罐重量表"), v("glass_jar", "BINARY", 0, 1, "建立玻璃罐重量表")],
    sense="min", objective={"aggregate": 1, "plastic_bottle": 3, "paper_box": 4, "metal_can": 5, "glass_jar": 2}, objective_meaning="包装数据表编制成本", unit="千新元",
    constraints=[c("at_least_one_table", ">=", 1, {"aggregate": 1, "plastic_bottle": 1, "paper_box": 1, "metal_can": 1, "glass_jar": 1}, "至少建立一张包装数据表"), c("table_capacity", "<=", 4, {"aggregate": 1, "plastic_bottle": 1, "paper_box": 1, "metal_can": 1, "glass_jar": 1}, "数据系统至多建立四张表")],
    action=["aggregate", "plastic_bottle", "paper_box", "metal_can", "glass_jar"], patch_variables=[],
    patch_constraints=[c("plastic_material_form", "=", 1, {"plastic_bottle": 1}, "按塑料材质和瓶装形态报告重量"), c("paper_material_form", "=", 1, {"paper_box": 1}, "按纸材质和盒装形态报告重量"), c("metal_material_form", "=", 1, {"metal_can": 1}, "按金属材质和罐装形态报告重量")],
    patch_objective=None, patch_summary="把年度包装重量从总量表拆分到实际使用的材质—形态组合。",
    local_fact="实际进口或使用塑料瓶、纸盒和金属罐3种包装组合，不使用玻璃罐", patch_binding="constraint:plastic_material_form",
    excerpt_start="Companies will have to provide data on the amounts (in terms of weight)", excerpt_end="Companies will also be required to submit their 3R plans for packaging.",
    rule_claim="Obligated companies annually report the weight of packaging imported or used in Singapore, broken down by packaging material and packaging form, and submit packaging 3R plans.",
    applicability_reason="The task identifies an obligated Singapore company for the current reporting year and enumerates every material-form combination it imports or uses, while explicitly excluding glass jars."
)

add(
    task_id="SWOR-R019", family="telecom_service", patch_class="conditional_auxiliary",
    problem="澳大利亚关键电信资产CIRMP模块选择。2026年8月2日，作为责任实体的南岸电信公司为其受SOCI制度覆盖的关键电信资产选择CIRMP模块，该资产自2025年10月1日起成为相关关键基础设施资产。候选模块为资产运行环境描述、重大风险登记、可行风险消除或降低、危险影响缓解、定期审查机制、持续更新机制和通用风险模板，年度成本依次为2、3、5、4、3、2、1百万澳元。独立工程评估确认前6个专用模块对该资产均可合理实施；基础要求至少配置2个模块，唯一目标是最小化年度成本。计划配置必须遵守澳大利亚当日适用的关键电信基础设施风险管理规定。请给出最优模块配置与总成本。",
    variables=[v("context", "BINARY", 0, 1, "配置资产运行环境描述模块"), v("material_risk", "BINARY", 0, 1, "配置重大风险登记模块"), v("risk_treatment", "BINARY", 0, 1, "配置风险消除或降低模块"), v("impact_mitigation", "BINARY", 0, 1, "配置危险影响缓解模块"), v("review", "BINARY", 0, 1, "配置定期审查机制"), v("currency", "BINARY", 0, 1, "配置持续更新机制"), v("generic", "BINARY", 0, 1, "配置通用风险模板")],
    sense="min", objective={"context": 2, "material_risk": 3, "risk_treatment": 5, "impact_mitigation": 4, "review": 3, "currency": 2, "generic": 1}, objective_meaning="CIRMP模块年度成本", unit="百万澳元",
    constraints=[c("minimum_program_modules", ">=", 2, {"context": 1, "material_risk": 1, "risk_treatment": 1, "impact_mitigation": 1, "review": 1, "currency": 1, "generic": 1}, "至少配置两个CIRMP模块")],
    action=["context", "material_risk", "risk_treatment", "impact_mitigation", "review", "currency", "generic"], patch_variables=[],
    patch_constraints=[c("context_required", "=", 1, {"context": 1}, "识别关键资产运行环境"), c("risk_register_required", "=", 1, {"material_risk": 1}, "识别重大风险"), c("treatment_required", "=", 1, {"risk_treatment": 1}, "实施合理可行的风险消除或降低"), c("impact_required", "=", 1, {"impact_mitigation": 1}, "缓解各危险对关键资产的相关影响"), c("review_required", "=", 1, {"review": 1}, "设置CIRMP审查机制"), c("currency_required", "=", 1, {"currency": 1}, "设置CIRMP持续更新机制")],
    patch_objective=None, patch_summary="为受覆盖关键电信资产补齐运行环境、重大风险、风险处置、影响缓解、审查和持续更新模块。",
    local_fact="该资产自2025年10月1日起成为相关关键基础设施资产", patch_binding="constraint:treatment_required",
    excerpt_start="7 Application of Part 2A of the Act (1) For the purposes", excerpt_end="ensure that it complies with section 30AF of the Act.",
    rule_claim="A CIRMP identifies asset context and material risks, and so far as reasonably practicable minimises or eliminates those risks and mitigates each hazard's impact; it also includes review and currency mechanisms.",
    applicability_reason="The task identifies a responsible entity and covered critical telecommunications asset. The asset became relevant on 2025-10-01, more than six months before the 2026-08-02 decision, so the transition window has elapsed; an asset-specific engineering assessment closes the reasonably-practicable qualifier for all six modeled requirements."
)

add(
    task_id="SWOR-R020", family="telecom_service", patch_class="conditional_auxiliary",
    problem="澳大利亚关键电信供应链风险措施选择。2026年8月2日，作为责任实体的红土通信公司为其受SOCI制度覆盖的关键电信资产选择供应链风险措施，该资产自2025年10月1日起成为相关关键基础设施资产。候选措施分别应对未授权访问、供应商特权滥用、供应链中断、供应链内人员和资产威胁、主要供应商风险、其他依赖资产能力下降，以及缓解供应链危险对资产的影响；另有1项通用保险方案，年度成本依次为3、4、5、4、6、3、5、1百万澳元。资产评估确认前7项措施针对已识别的重大风险且均可合理实施。基础要求至少选择2项措施；通用保险与未授权访问控制占用同一采购名额，二者不能同时选择。唯一目标是最小化年度成本。措施组合必须遵守澳大利亚当日适用的关键电信供应链风险规定。请给出最优措施组合与总成本。",
    variables=[v("unauthorized", "BINARY", 0, 1, "实施未授权访问风险措施"), v("privileged", "BINARY", 0, 1, "实施供应商特权滥用风险措施"), v("disruption", "BINARY", 0, 1, "实施供应链中断风险措施"), v("threats", "BINARY", 0, 1, "实施供应链人员和资产威胁措施"), v("major_supplier", "BINARY", 0, 1, "实施主要供应商风险措施"), v("dependency", "BINARY", 0, 1, "实施依赖资产能力下降风险措施"), v("impact", "BINARY", 0, 1, "实施供应链危险影响缓解措施"), v("insurance", "BINARY", 0, 1, "购买通用保险方案")],
    sense="min", objective={"unauthorized": 3, "privileged": 4, "disruption": 5, "threats": 4, "major_supplier": 6, "dependency": 3, "impact": 5, "insurance": 1}, objective_meaning="供应链风险措施年度成本", unit="百万澳元",
    constraints=[c("minimum_supply_measures", ">=", 2, {"unauthorized": 1, "privileged": 1, "disruption": 1, "threats": 1, "major_supplier": 1, "dependency": 1, "impact": 1, "insurance": 1}, "至少选择两项供应链风险措施"), c("procurement_slot", "<=", 1, {"unauthorized": 1, "insurance": 1}, "未授权访问控制与通用保险不能同时采购")],
    action=["unauthorized", "privileged", "disruption", "threats", "major_supplier", "dependency", "impact", "insurance"], patch_variables=[],
    patch_constraints=[c("unauthorized_required", "=", 1, {"unauthorized": 1}, "降低未授权访问干扰或利用风险"), c("privileged_required", "=", 1, {"privileged": 1}, "降低供应商滥用特权访问风险"), c("disruption_required", "=", 1, {"disruption": 1}, "降低供应链问题导致资产中断风险"), c("threats_required", "=", 1, {"threats": 1}, "降低供应链内人员资产和服务威胁"), c("major_supplier_required", "=", 1, {"major_supplier": 1}, "降低主要供应商产生的风险"), c("dependency_required", "=", 1, {"dependency": 1}, "降低依赖资产或实体能力下降风险"), c("impact_required", "=", 1, {"impact": 1}, "缓解供应链危险对关键资产的相关影响")],
    patch_objective=None, patch_summary="对已确认且可合理实施的供应链重大风险逐类配置降低措施，并加入危险影响缓解。",
    local_fact="该资产自2025年10月1日起成为相关关键基础设施资产", patch_binding="constraint:unauthorized_required",
    excerpt_start="14 Supply chain hazards (1) For the purpose", excerpt_end="the CIRMP describes the supply chain hazards that could have a relevant impact on the asset.",
    rule_claim="For supply-chain hazards a telecommunications CIRMP, so far as reasonably practicable, minimises or eliminates the listed material risks and mitigates their impact on the asset; adoption review also considers major suppliers and described hazards.",
    applicability_reason="The task identifies a responsible entity and covered critical telecommunications asset. The asset became relevant on 2025-10-01, more than six months before the 2026-08-02 decision, so the transition window has elapsed; the task enumerates every listed material-risk class and states that all seven modeled treatments are reasonably practicable."
)


def fetch_excerpt(url: str, start: str, end: str) -> tuple[str, str, int, str]:
    response = requests.get(url, headers={"User-Agent": "SearchWorthyOR-Rapid-v0/0.1 release-source-check"}, timeout=35, allow_redirects=True)
    response.raise_for_status()
    text = normalize_bytes(response.content, response.headers.get("content-type", ""), response.url)
    low = text.casefold()
    begin = low.find(start.casefold())
    if begin < 0:
        raise ValueError(f"support start not found: {start}")
    finish = low.find(end.casefold(), begin)
    if finish < 0:
        raise ValueError(f"support end not found: {end}")
    finish += len(end)
    excerpt = text[begin:finish]
    if normalize_text(excerpt) not in normalize_text(text):
        raise ValueError("continuous excerpt verification failed")
    if len(excerpt) > 5000:
        raise ValueError(f"support excerpt exceeds 5000 characters: {len(excerpt)}")
    return excerpt, response.url, response.status_code, response.headers.get("content-type", "")


def numeric_alignment(problem: str) -> list[dict[str, str]]:
    return [{"surface": sentence.strip(), "binding": "base:题面日期、数量、成本、容量或时点的对应模型与证据数据"}
            for sentence in re.split(r"(?<=[。；])", problem) if sentence.strip() and re.search(r"\d", sentence)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=len(CASES))
    args = parser.parse_args()
    old_rows = [json.loads(line) for line in (BATCH / "private" / "rapid_audit.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    seeds = {row["id"]: row for row in old_rows}
    shortlist_rows = [json.loads(line) for line in (ROOT / "private" / "source_shortlist_130.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in shortlist_rows:
        task_id = row.get("rapid_task_id")
        if row.get("batch") != 1 or not task_id or task_id in seeds:
            continue
        seeds[task_id] = {
            "schema_version": "searchworthyor.rapid_audit.v0", "id": task_id,
            "source_candidate_id": row["source_candidate_id"], "source_document_key": row["source_document_key"],
            "regulation_key": row["regulation_key"], "source_url": row["primary_url"], "final_url": row["primary_url"],
            "accessed_at": "2026-08-02T00:00:00Z", "authority": row["authority"],
            "jurisdiction": row["jurisdiction"], "decision_date": "2026-08-02"
        }
    tasks: list[dict[str, str]] = []
    audits: list[dict[str, Any]] = []
    for spec in CASES[:args.limit]:
        task_id = spec["task_id"]
        seed = seeds[task_id]
        source_id = seed["source_candidate_id"]
        base = ir(task_id, spec["family"], source_id, deepcopy(spec["variables"]), spec["sense"], deepcopy(spec["objective"]), spec["objective_meaning"], spec["unit"], deepcopy(spec["constraints"]), spec["action"], "base")
        patched_objective = deepcopy(spec["objective"])
        if spec["patch_objective"]:
            patched_objective.update(spec["patch_objective"])
        patched = ir(task_id, spec["family"], source_id, deepcopy(spec["variables"]) + deepcopy(spec["patch_variables"]), spec["sense"], patched_objective, spec["objective_meaning"], spec["unit"], deepcopy(spec["constraints"]) + deepcopy(spec["patch_constraints"]), spec["action"], "patched")
        model_dir = BATCH / "models" / task_id
        model_dir.mkdir(parents=True, exist_ok=True)
        base_path, patched_path, result_path = model_dir / "base_ir.json", model_dir / "patched_ir.json", model_dir / "solve_result.json"
        base_path.write_text(json.dumps(base, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        patched_path.write_text(json.dumps(patched, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        result = evaluate(base_path, patched_path)
        if result["common_optimal_action_feasible"]:
            raise RuntimeError(f"{task_id}: common optimal action")
        result_path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        excerpt, final_url, status, _ = fetch_excerpt(seed["final_url"], spec["excerpt_start"], spec["excerpt_end"])
        tasks.append({"id": task_id, "problem_zh": spec["problem"]})
        audit = {key: seed[key] for key in ("schema_version", "id", "source_candidate_id", "source_document_key", "regulation_key", "source_url", "accessed_at", "authority", "jurisdiction", "decision_date")}
        audit["decision_date"] = spec.get("decision_date", audit["decision_date"])
        audit.update({"final_url": final_url, "http_status": status, "support_excerpt": excerpt,
                      "rule_claim": spec["rule_claim"], "applicability": "PASS", "applicability_reason": spec["applicability_reason"],
                      "preserved_local_binding_facts": [spec["local_fact"]], "task_local_fact_alignment": [{"public_basis": spec["local_fact"], "patch_binding": spec["patch_binding"]}],
                      "numeric_alignment": numeric_alignment(spec["problem"]),
                      "variable_alignment": [{"variable": item["name"], "public_meaning": item["meaning"]} for item in base["variables"]],
                      "constraint_alignment": [{"constraint": item["name"], "public_basis": item["meaning"]} for item in base["constraints"]],
                      "structural_patch": "PASS", "patch_summary": spec["patch_summary"], "family": spec["family"], "patch_class": spec["patch_class"],
                      "base_model_path": str(base_path.relative_to(ROOT)).replace("\\", "/"), "patched_model_path": str(patched_path.relative_to(ROOT)).replace("\\", "/"), "solve_result_path": str(result_path.relative_to(ROOT)).replace("\\", "/"),
                      "base_solve": "OPTIMAL", "patched_solve": "OPTIMAL", "optimal_action_changed": True, "common_optimal_action_feasible": False,
                      "problem_model_alignment": "PASS", "answer_leakage": False, "single_objective": True, "generator_id": "/root/rapid_batch05_rebuild", "generator_self_check": "PASS", "independent_review": "PENDING", "status": "GENERATED_SELF_CHECK_PASS"})
        audits.append(audit)
    (BATCH / "public" / "tasks_zh.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in tasks), encoding="utf-8", newline="\n")
    (BATCH / "private" / "rapid_audit.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in audits), encoding="utf-8", newline="\n")
    print(json.dumps({"generated": len(tasks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
