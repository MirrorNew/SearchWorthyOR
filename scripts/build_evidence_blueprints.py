#!/usr/bin/env python3
"""Build and validate the 100 evidence blueprints for SearchWorthyOR-100.

This file deliberately emits construction metadata rather than public prompts,
policy answers, solver results, or benchmark source identifiers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "staging" / "evidence_blueprints.jsonl"

TOP_LEVEL_FIELDS = {
    "family",
    "evidence_mode",
    "patch_class",
    "entity",
    "jurisdiction",
    "decision_time",
    "search_cues",
    "applicable_policy_blueprint",
    "distractors",
    "anti_fogging_reason",
    "web_source_url",
}

PATCH_CLASSES = (
    "eligibility_domain",
    "temporal_coupling",
    "conditional_auxiliary",
    "quota_risk_service_objective",
)
FROZEN_PATCH_ORDINALS = (
    "20333112010311032223023101210103121313230312203101"
    "32000312232310313001022202012300212021013331213023"
)


def frozen_patch_assignments() -> dict[int, str]:
    if len(FROZEN_PATCH_ORDINALS) != 100:
        raise AssertionError("frozen patch ordinal vector must have 100 entries")
    assignments = {
        index: PATCH_CLASSES[int(ordinal)]
        for index, ordinal in enumerate(FROZEN_PATCH_ORDINALS)
    }
    if Counter(assignments.values()) != Counter(
        {patch_class: 25 for patch_class in PATCH_CLASSES}
    ):
        raise AssertionError("frozen patch assignment is not globally balanced")
    return assignments


FROZEN_PATCH_ASSIGNMENTS = frozen_patch_assignments()

FAMILY_ALLOWLIST = (
    "routing_transport",
    "scheduling_workforce",
    "production_capacity",
    "assignment_matching",
    "facility_network",
    "inventory_supply_chain",
    "energy_environment",
    "healthcare_resources",
    "finance_portfolio",
    "telecom_service",
)

PATCH_SPECS = {
    "eligibility_domain": {
        "label": "资格、动作可用性与变量域",
        "search_focus": "哪些资源或动作在该实体、辖区和日期下可用",
        "slots": (
            ("base_rule", "找出覆盖对象及默认可用动作集合的条款。"),
            ("eligibility_test", "找出使资源或动作进入变量域的全部资格条件。"),
            ("exception_override", "找出命中例外时恢复、缩减或禁止动作的条款。"),
            ("precedence", "找出冲突条款的优先级及在决策时点适用的版本。"),
        ),
    },
    "temporal_coupling": {
        "label": "时间窗、先后、耦合与跨期",
        "search_focus": "哪些时间窗、先后关系和跨期状态必须联合满足",
        "slots": (
            ("base_window", "找出默认起止窗口、持续期或间隔规则。"),
            ("coupling_rule", "找出跨任务、跨班次或跨期联动的先后与累计规则。"),
            ("exception_recovery", "找出例外情形下窗口如何延展、暂停或重置。"),
            ("precedence", "找出决策时点有效的过渡条款及冲突规则优先级。"),
        ),
    },
    "conditional_auxiliary": {
        "label": "条件激活、分段与辅助变量",
        "search_focus": "何种组合条件会激活额外约束、分段规则或辅助状态",
        "slots": (
            ("activation_predicate", "找出激活附加规则所需的完整条件组合。"),
            ("activated_consequence", "找出激活后新增的约束、分段或辅助状态语义。"),
            ("exception_deactivation", "找出能够豁免、替代或解除附加规则的例外。"),
            ("precedence", "找出激活条款与一般条款冲突时的优先级和有效版本。"),
        ),
    },
    "quota_risk_service_objective": {
        "label": "配额、风险、服务组合与目标项结构",
        "search_focus": "配额、风险和服务项如何进入约束及单一目标结构",
        "slots": (
            ("quota_or_service_rule", "找出必须满足的配额、服务层级或组合要求。"),
            ("risk_aggregation", "找出风险或服务缺口的聚合口径与适用范围。"),
            ("exception_priority", "找出例外任务的优先级、豁免或替代服务口径。"),
            ("objective_composition", "找出进入单一目标的项、方向与层级，但不在蓝图写入数值。"),
        ),
    },
}

FAMILIES = (
    {
        "name": "routing_transport",
        "label": "运输路由",
        "company": "澄舟综合运输有限公司",
        "entity_type": "多式联运运营人",
        "resource": "车辆、运输任务、枢纽与司机",
        "action": "任务—车辆—线路—枢纽指派",
        "clock": "驾驶、装卸、服务与回场窗口",
        "service": "准时送达、线路覆盖与转运衔接",
        "policy": "运输路由与车队使用规则",
    },
    {
        "name": "scheduling_workforce",
        "label": "人员与任务排程",
        "company": "星桥综合服务运营有限公司",
        "entity_type": "多站点用工与服务运营人",
        "resource": "员工、技能、任务与班次",
        "action": "员工—岗位—任务—班次指派",
        "clock": "工时、休息、换班与任务窗口",
        "service": "岗位覆盖、任务响应与连续服务",
        "policy": "人员排程与休息规则",
    },
    {
        "name": "production_capacity",
        "label": "生产与产能计划",
        "company": "衡川多工序制造有限公司",
        "entity_type": "多产线制造企业",
        "resource": "产线、批次、原料与产能模块",
        "action": "批次—产线—期间—产能指派",
        "clock": "生产、换线、保质与扩容周期",
        "service": "订单履约、质量与产能保障",
        "policy": "生产与产能合规规则",
    },
    {
        "name": "assignment_matching",
        "label": "资格指派与匹配",
        "company": "云岬专业任务运营有限公司",
        "entity_type": "多资格任务分配运营人",
        "resource": "人员、资格、任务与备份席位",
        "action": "人员—资格—任务匹配",
        "clock": "执勤、任务、休息与交接窗口",
        "service": "任务覆盖、资格匹配与备份服务",
        "policy": "资格匹配与任务指派规则",
    },
    {
        "name": "facility_network",
        "label": "设施与网络设计",
        "company": "林港区域设施网络有限公司",
        "entity_type": "设施与基础网络运营人",
        "resource": "候选设施、节点、弧与容量模块",
        "action": "设施启用、弧配置与客户分配",
        "clock": "建设、启用、过渡与容量周期",
        "service": "区域覆盖、连通性与响应服务",
        "policy": "设施准入与网络容量规则",
    },
    {
        "name": "inventory_supply_chain",
        "label": "库存与供应链",
        "company": "麦辰多仓供应链有限公司",
        "entity_type": "多仓采购与配送网络",
        "resource": "供应商、仓库、库存品与补货批次",
        "action": "采购、补货、调拨与库存保留",
        "clock": "订货、到货、盘点与保质周期",
        "service": "缺货保护、门店覆盖与供应连续性",
        "policy": "库存、采购与补货规则",
    },
    {
        "name": "energy_environment",
        "label": "能源与环境运营",
        "company": "青屿清洁能源环境有限公司",
        "entity_type": "综合能源与环境设施运营人",
        "resource": "机组、储能、负荷、排放源与处理设施",
        "action": "启停、出力、充放电与处理路径安排",
        "clock": "爬坡、开停、结算、暂存与处置周期",
        "service": "负荷满足、备用、排放与合规处置",
        "policy": "能源调度与环境合规规则",
    },
    {
        "name": "healthcare_resources",
        "label": "医疗健康资源配置",
        "company": "和岚医疗健康运营有限公司",
        "entity_type": "多站点医疗健康服务运营人",
        "resource": "医护人员、床位、设备、药品与营养物资",
        "action": "人员—患者—床位—物资指派",
        "clock": "值班、休息、治疗与补给窗口",
        "service": "患者覆盖、连续照护与关键物资保障",
        "policy": "医疗健康资源与服务规则",
    },
    {
        "name": "finance_portfolio",
        "label": "金融与投资组合",
        "company": "衡信产业投资管理有限公司",
        "entity_type": "多资产投资与预算管理人",
        "resource": "项目、资产、预算与风险额度",
        "action": "资产选择、资本配置与风险对冲",
        "clock": "取得、投入使用、持有与再平衡周期",
        "service": "收益、流动性、合规与风险保障",
        "policy": "投资资格与组合风险规则",
    },
    {
        "name": "telecom_service",
        "label": "通信网络与服务",
        "company": "联岬通信服务有限公司",
        "entity_type": "多区域通信网络与现场服务运营人",
        "resource": "站点、链路、频谱、服务车辆与工单",
        "action": "链路启用、容量配置与工单—团队指派",
        "clock": "建设、维护、驾驶与服务恢复窗口",
        "service": "连接覆盖、容量与故障恢复",
        "policy": "通信网络接入与现场服务规则",
    },
)

PRIVATE_JURISDICTIONS = (
    "北湾经营辖区（合成）",
    "东岚经营辖区（合成）",
    "南浦经营辖区（合成）",
    "西川经营辖区（合成）",
    "云岭经营辖区（合成）",
    "海桥经营辖区（合成）",
    "松原经营辖区（合成）",
    "星港经营辖区（合成）",
)

PRIVATE_DECISION_DATES = (
    "2026-02-17",
    "2026-03-05",
    "2026-03-26",
    "2026-04-14",
    "2026-05-08",
    "2026-05-29",
    "2026-06-18",
    "2026-07-09",
)

PRIVATE_EFFECTIVE_DATES = (
    "2026-01-01",
    "2026-01-15",
    "2026-02-01",
    "2026-03-01",
    "2026-04-01",
    "2026-04-15",
    "2026-05-15",
    "2026-06-01",
)

PRIVATE_EXCEPTIONS = (
    "经辖区负责人书面确认的连续性应急任务",
    "跨辖区任务且本实体被指定为主责执行方",
    "受监管的公共服务任务并具备完整留痕",
    "已登记试运行项目且尚未转入常规运营",
    "第三方代履行但本实体仍承担最终责任",
    "设施或资源故障触发的临时替代安排",
    "弱势客户或关键基础服务的优先保障",
    "决策日前已签署且未被新规明确撤销的过渡安排",
)

PRIVATE_UNIT_NAMES = (
    "晨汐单元",
    "岚桥单元",
    "星湾单元",
    "澄岳单元",
    "云港单元",
    "青浦单元",
    "霁原单元",
    "镜川单元",
)

WEB_SOURCES = {
    "transport_crew": (
        {
            "official_title": "49 CFR 395.3 Maximum Driving Time for Property-Carrying Vehicles",
            "agency": "美国电子联邦法规（规则主管机关为 FMCSA）",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-06-15/title-49.xml?part=395&section=395.3",
            "entity": "北辰州际货运（合成场景，财产承运人）",
            "jurisdiction": "美国联邦州际道路运输",
            "decision_time": "2026-06-15",
            "entity_scope": "从事州际商业机动车财产运输的承运人与驾驶员",
            "exception_scope": "核验短途、恶劣驾驶条件、卧铺及其他适用例外，且区分财产与客运驾驶员。",
            "focus": "驾驶窗口、休息、累计执勤与例外如何共同约束线路安排",
        },
        {
            "official_title": "14 CFR Part 117 Flight and Duty Limitations and Rest Requirements",
            "agency": "美国电子联邦法规（eCFR）/美国联邦航空管理局规则",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-10/title-14.xml?part=117",
            "entity": "云岬航空（合成场景，Part 121 客运合格证持有人）",
            "jurisdiction": "美国联邦民航",
            "decision_time": "2026-07-10",
            "entity_scope": "受 Part 117 适用条款覆盖的 Part 121 客运机组与合格证持有人",
            "exception_scope": "核验扩编机组、备份、适应状态、不可预见运行情况和获批疲劳风险管理安排。",
            "focus": "飞行执勤、休息、备份与运行例外如何耦合机组指派",
        },
        {
            "official_title": "49 CFR Part 395 Hours of Service of Drivers",
            "agency": "美国电子联邦法规（规则主管机关为 FMCSA）",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-06-20/title-49.xml?part=395",
            "entity": "星桥车队服务（合成场景，州际财产承运人）",
            "jurisdiction": "美国联邦州际道路运输",
            "decision_time": "2026-06-20",
            "entity_scope": "安排property-carrying商业机动车驾驶任务的州际财产承运人与驾驶员",
            "exception_scope": "核验short-haul、商业蜜蜂或牲畜运输、爆炸物押运及其他§395.1例外，不把试点招募说明当作一般规则。",
            "focus": "当前生效的一般工时规则与试点或例外的边界",
        },
        {
            "official_title": "49 CFR Part 395 Subpart A General Hours-of-Service Rules",
            "agency": "美国电子联邦法规（规则主管机关为 FMCSA）",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-05-12/title-49.xml?part=395&subpart=A",
            "entity": "岚箱州际配送（合成场景，财产承运人）",
            "jurisdiction": "美国联邦州际道路运输",
            "decision_time": "2026-05-12",
            "entity_scope": "承担州际财产运输及装载交接的商业机动车承运人和驾驶员",
            "exception_scope": "核验装载等待计入何种状态以及短途、恶劣条件和卧铺例外的适用条件。",
            "focus": "装载等待、驾驶状态和休息规则如何影响货件—车辆联合安排",
        },
    ),
    "food_nutrition": (
        {
            "official_title": "FDA Menu Labeling Requirements",
            "agency": "美国食品药品监督管理局（FDA）",
            "url": "https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/menu-labeling-requirements",
            "entity": "衡川连锁餐食生产网络（合成场景，连锁餐饮设施与标准菜单生产运营人）",
            "jurisdiction": "美国联邦食品标签监管",
            "decision_time": "2026-05-18",
            "entity_scope": "需要核验是否属于受菜单标签规则覆盖的连锁餐饮或类似零售设施",
            "exception_scope": "核验临时项目、非标准项目、设施类型和实体规模等覆盖边界。",
            "focus": "设施覆盖资格与标准菜单项义务如何改变可生产菜单项及标签配置",
        },
        {
            "official_title": "21 CFR 101.91 Gluten-Free Labeling of Food",
            "agency": "美国电子联邦法规（规则主管机关为 FDA）",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-04-22/title-21.xml?part=101&section=101.91",
            "entity": "衡川包装食品（合成场景，包装食品制造商）",
            "jurisdiction": "美国联邦食品标签监管",
            "decision_time": "2026-04-22",
            "entity_scope": "生产需要核验营养成分标签要求的包装食品企业",
            "exception_scope": "核验产品类别、包装形式、自愿声明与强制声明的差异。",
            "focus": "麸质含量阈值与gluten-free声明如何约束同一包装食品的配方和标签组合",
        },
        {
            "official_title": "7 CFR 210.10 Meal Requirements for Lunches",
            "agency": "美国电子联邦法规（规则主管机关为 USDA FNS）",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-03-25/title-7.xml?part=210&section=210.10",
            "entity": "麦辰学区食品管理机构（合成场景，参与全国学校午餐计划的SFA）",
            "jurisdiction": "美国联邦学校餐项目",
            "decision_time": "2026-03-25",
            "entity_scope": "参与全国学校午餐计划并负责提交完整可报销午餐组合的学校食品管理机构",
            "exception_scope": "核验餐别、学年、年级组、短周计算和过渡时间表的适用性。",
            "focus": "菜单组件、周度口径与过渡标准如何影响补货及库存组合",
        },
        {
            "official_title": "21 CFR 101.9 Nutrition Labeling of Food",
            "agency": "美国电子联邦法规（规则主管机关为 FDA）",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-06-02/title-21.xml?part=101&section=101.9",
            "entity": "麦辰食品包装供应链（合成场景，包装、标签与补货服务商）",
            "jurisdiction": "美国联邦食品标签监管",
            "decision_time": "2026-06-02",
            "entity_scope": "为不同食品类别设计包装与标签配置的服务商及其客户产品",
            "exception_scope": "核验21 CFR 101.9(j)的小企业、低销量、餐馆直接销售及其他豁免，并区分普通食品、膳食补充剂、婴儿配方和医疗食品。",
            "focus": "产品类别与标签分支如何改变可用包装版式和组合",
        },
    ),
    "clean_vehicles": (
        {
            "official_title": "IRS Commercial Clean Vehicle Credit",
            "agency": "美国国税局（IRS）",
            "url": "https://www.irs.gov/newsroom/topic-g-frequently-asked-questions-about-qualified-commercial-clean-vehicle-credit",
            "entity": "衡信车队资产组合（合成场景，商业车辆投资与购买方）",
            "jurisdiction": "美国联邦税收",
            "decision_time": "2025-09-01",
            "entity_scope": "为商业用途取得并投入使用车辆的美国纳税实体",
            "exception_scope": "核验取得日、投入使用日、车辆用途、关联主体和终止或过渡规定。",
            "focus": "不同清洁车辆抵免分支是否可同时用于同一车辆投资",
        },
        {
            "official_title": "IRS Alternative Fuel Vehicle Refueling Property Credit",
            "agency": "美国国税局（IRS）",
            "url": "https://www.irs.gov/credits-deductions/alternative-fuel-vehicle-refueling-property-credit",
            "entity": "沧源充能网络（合成场景，商业充电设施投资方）",
            "jurisdiction": "美国联邦税收",
            "decision_time": "2026-05-20",
            "entity_scope": "在美国商业地点安装并投入使用合格补能或充电财产的纳税实体",
            "exception_scope": "核验地点、投入使用日期、财产用途、原始使用和工资学徒要求等分支。",
            "focus": "节点地点和设施资格如何改变充能网络的候选域与成本项",
        },
        {
            "official_title": "IRS Clean Vehicle Tax Credits",
            "agency": "美国国税局（IRS）",
            "url": "https://www.irs.gov/clean-vehicle-tax-credits",
            "entity": "衡信移动资产组合（合成场景，商业车辆投资与使用方）",
            "jurisdiction": "美国联邦税收",
            "decision_time": "2025-08-15",
            "entity_scope": "需要区分新车、二手车和商业车辆规则的车辆取得方",
            "exception_scope": "核验取得与交付时点、个人或商业用途、卖方报告以及过渡规则。",
            "focus": "车辆取得截止日期如何改变投资组合候选域及一次性目标项",
        },
        {
            "official_title": "EPA Clean Heavy-Duty Vehicles Grant Program",
            "agency": "美国环境保护署（EPA）",
            "url": "https://www.epa.gov/system/files/documents/2024-04/2024-chdv-grants-nofo-2024-04.pdf",
            "entity": "净陆重型车队与站点网络（合成场景，公共服务车辆网络运营人）",
            "jurisdiction": "美国联邦清洁重型车辆项目",
            "decision_time": "2024-06-15",
            "entity_scope": "拟以零排放车辆替换合格重型车辆并配置相关基础设施的申请主体",
            "exception_scope": "核验申请轮次、主体类型、车辆用途、既有车辆EMY、替换资产处置、reduced-service替代处置和可报销活动边界。",
            "focus": "项目资格与服务优先级如何改变车辆—站点网络配置组合",
        },
    ),
    "emissions_hazardous_waste": (
        {
            "official_title": "EPA Categories of Hazardous Waste Generators",
            "agency": "美国环境保护署（EPA）",
            "url": "https://www.epa.gov/hwgenerators/categories-hazardous-waste-generators",
            "entity": "林港处理设施（合成场景，危险废物产生场所）",
            "jurisdiction": "美国联邦 RCRA",
            "decision_time": "2026-06-12",
            "entity_scope": "按具体场所和废物产生情况分类的危险废物产生者",
            "exception_scope": "核验产生者类别、场所口径、废物类型、联邦例外及应急事件；本题不主张任何州级加严规则。",
            "focus": "产生者类别和处置义务如何改变能源与处理方案的可用域",
        },
        {
            "official_title": "EPA Frequent Questions About Hazardous Waste Generation",
            "agency": "美国环境保护署（EPA）",
            "url": "https://www.epa.gov/hwgenerators/frequent-questions-about-hazardous-waste-generation",
            "entity": "和岚医疗中心（合成场景，产生并积存危险废物的医疗设施）",
            "jurisdiction": "美国联邦 RCRA",
            "decision_time": "2026-05-27",
            "entity_scope": "在医疗服务中产生、暂存或处理受监管废物的医疗设施",
            "exception_scope": "核验卫星积存、偶发事件、容器或罐处理、培训与记录分支；本题不主张任何州级加严规则。",
            "focus": "按月产生量确定的产生者类别如何激活医疗废物服务单元的合规状态",
        },
        {
            "official_title": "EPA Land Disposal Restrictions for Hazardous Waste",
            "agency": "美国环境保护署（EPA）",
            "url": "https://www.epa.gov/hw/land-disposal-restrictions-hazardous-waste",
            "entity": "沧源废物流网络（合成场景，危险废物处理网络运营人）",
            "jurisdiction": "美国联邦 RCRA",
            "decision_time": "2026-04-30",
            "entity_scope": "产生、处理、储存或处置拟土地处置危险废物的处理网络参与方",
            "exception_scope": "核验废物是否危险、是否拟土地处置、家庭或其他联邦豁免及处理标准分支；本题不主张任何州级加严规则。",
            "focus": "处理资格与禁止路径如何改变能源处理方案及转运组合",
        },
        {
            "official_title": "40 CFR Part 63 Subpart EEE National Emission Standards for Hazardous Waste Combustors",
            "agency": "美国电子联邦法规（规则主管机关为 EPA）",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-06-10/title-40.xml?part=63&subpart=EEE",
            "entity": "净陆医疗废物焚烧转运系统（合成场景，危险废物燃烧设施运营人）",
            "jurisdiction": "美国联邦清洁空气法危险空气污染物标准",
            "decision_time": "2026-06-10",
            "entity_scope": "属于危险废物燃烧器规则覆盖类型的医疗废物处理设施运营人",
            "exception_scope": "核验设施是否为现有危险废物焚烧炉、规则修订生效日、启动停机故障、延期和其他Subpart EEE例外。",
            "focus": "排放规则和运行状态如何要求医疗废物服务组合配置污染控制能力",
        },
    ),
    "labor_rest": (
        {
            "official_title": "California DLSE Rest Periods FAQ",
            "agency": "加利福尼亚州劳工标准执行局（DLSE）",
            "url": "https://www.dir.ca.gov/dlse/faq_restperiods.htm",
            "entity": "联岬通信地面机组（合成场景，加州非豁免现场员工雇主）",
            "jurisdiction": "美国加利福尼亚州",
            "decision_time": "2026-05-05",
            "entity_scope": "受相应工资令休息期规定覆盖的加州非豁免雇员及雇主",
            "exception_scope": "核验适用工资令、工作时长、特殊行业和特定照护设施例外。",
            "focus": "休息期覆盖、安排位置和例外如何限制通信现场服务模块",
        },
        {
            "official_title": "29 CFR Part 785 Hours Worked",
            "agency": "美国电子联邦法规（规则主管机关为 DOL WHD）",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-04-16/title-29.xml?part=785",
            "entity": "星桥现场服务排班（合成场景，按小时计酬员工雇主）",
            "jurisdiction": "美国联邦 FLSA",
            "decision_time": "2026-04-16",
            "entity_scope": "安排按小时计酬员工执行现场服务且需判定休息、用餐或待命是否计工时的雇主",
            "exception_scope": "核验员工是否完全解除职责、是否被打断或待命；本题只裁决联邦FLSA口径，不主张州法加严。",
            "focus": "可计工时与被打断用餐如何影响班次组合和岗位覆盖",
        },
        {
            "official_title": "WAC 296-126-092 Meal Periods—Rest Periods",
            "agency": "华盛顿州法典修订办公室（Washington State Code Reviser）",
            "url": "https://app.leg.wa.gov/wac/default.aspx?cite=296-126-092",
            "entity": "星桥华盛顿站点（合成场景，普通成年员工雇主）",
            "jurisdiction": "美国华盛顿州",
            "decision_time": "2026-06-08",
            "entity_scope": "在华盛顿州安排普通成年员工班次的受覆盖雇主",
            "exception_scope": "核验未成年、农业、医疗、豁免或经批准变通安排等不同分支。",
            "focus": "休息、用餐、连续工作与加班分支如何耦合岗位覆盖",
        },
        {
            "official_title": "California DLSE Meal Periods FAQ",
            "agency": "加利福尼亚州劳工标准执行局（DLSE）",
            "url": "https://www.dir.ca.gov/dlse/faq_mealperiods.htm",
            "entity": "青屿通信园区运维（合成场景，加州非豁免现场员工雇主）",
            "jurisdiction": "美国加利福尼亚州",
            "decision_time": "2026-05-21",
            "entity_scope": "在加州安排非豁免现场员工连续工作超过五小时的通信运维雇主",
            "exception_scope": "核验不超过六小时的双方同意豁免、行业工资令、在岗用餐书面协议和第二次用餐要求。",
            "focus": "连续工作时长、用餐覆盖与豁免如何改变通信现场服务模块组合",
        },
    ),
}

WEB_ASSIGNMENTS = {
    "routing_transport": (("transport_crew", 0), ("transport_crew", 1)),
    "scheduling_workforce": (("labor_rest", 1), ("labor_rest", 2)),
    "production_capacity": (("food_nutrition", 0), ("food_nutrition", 1)),
    "assignment_matching": (("transport_crew", 2), ("transport_crew", 3)),
    "facility_network": (("clean_vehicles", 1), ("clean_vehicles", 3)),
    "inventory_supply_chain": (("food_nutrition", 3), ("food_nutrition", 2)),
    "energy_environment": (
        ("emissions_hazardous_waste", 0),
        ("emissions_hazardous_waste", 2),
    ),
    "healthcare_resources": (
        ("emissions_hazardous_waste", 1),
        ("emissions_hazardous_waste", 3),
    ),
    "finance_portfolio": (("clean_vehicles", 2), ("clean_vehicles", 0)),
    "telecom_service": (("labor_rest", 0), ("labor_rest", 3)),
}


def _policy_slots(patch_class: str, family: dict[str, str]) -> list[dict[str, str]]:
    context = (
        f"绑定到{family['resource']}及{family['action']}；时间语义为{family['clock']}；"
        f"服务语义为{family['service']}。"
    )
    return [
        {"slot": slot, "retrieve": f"{instruction}{context}"}
        for slot, instruction in PATCH_SPECS[patch_class]["slots"]
    ]


def _private_distractors(
    family: dict[str, str],
    jurisdiction: str,
    wrong_jurisdiction: str,
    entity: str,
    decision_time: str,
) -> list[dict[str, str]]:
    return [
        {
            "distractor_type": "old_version",
            "blueprint": (
                f"同一实体“{entity}”、同一辖区“{jurisdiction}”的已废止修订版；"
                f"标题和关键词高度相似，但有效期在 {decision_time} 前结束。"
            ),
            "rejection_basis": "时间适用性错误；不得用旧版填补当前条款。",
        },
        {
            "distractor_type": "wrong_jurisdiction",
            "blueprint": (
                f"同一实体“{entity}”在“{wrong_jurisdiction}”的现行专编；"
                f"业务对象相近但不治理本题辖区“{jurisdiction}”。"
            ),
            "rejection_basis": "辖区不匹配；相似业务规则不能跨辖区迁移。",
        },
        {
            "distractor_type": "wrong_entity",
            "blueprint": (
                f"同一辖区“{jurisdiction}”内另一{family['entity_type']}的现行规则；"
                f"含相似的{family['policy']}术语，但签约或治理主体不是“{entity}”。"
            ),
            "rejection_basis": "主体不匹配；不得把邻近组织的政策当作本实体规则。",
        },
    ]


def _web_distractors(source: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "distractor_type": "old_version",
            "blueprint": (
                f"“{source['official_title']}”的历史版、已结束项目轮次或仅为提案的材料；"
                "主题一致但可能不覆盖决策时点。"
            ),
            "rejection_basis": "必须进行 point-in-time 核验，不能把历史版或提案当现行规则。",
        },
        {
            "distractor_type": "wrong_jurisdiction",
            "blueprint": (
                f"其他国家、州或地方政府发布的同主题官方页面；"
                f"不能替代“{source['jurisdiction']}”的适用规则。"
            ),
            "rejection_basis": "官方性不等于本辖区适用性。",
        },
        {
            "distractor_type": "wrong_entity",
            "blueprint": (
                "同一官方站点面向邻近主体类别、项目类型或运营活动的页面；"
                f"未证明覆盖“{source['entity_scope']}”。"
            ),
            "rejection_basis": "必须先完成实体与活动分类，不能仅凭主题相似采纳。",
        },
    ]


def build_private_row(
    family: dict[str, str],
    family_index: int,
    case_index: int,
    global_index: int,
) -> dict[str, Any]:
    patch_class = FROZEN_PATCH_ASSIGNMENTS[global_index]
    metadata_order = sorted(
        range(8),
        key=lambda value: hashlib.sha256(
            f"private-metadata-v2|{family_index}|{value}".encode("utf-8")
        ).hexdigest(),
    )
    metadata_index = metadata_order[case_index]
    jurisdiction = PRIVATE_JURISDICTIONS[metadata_index]
    wrong_jurisdiction = PRIVATE_JURISDICTIONS[
        (metadata_index + 3) % len(PRIVATE_JURISDICTIONS)
    ]
    decision_time = PRIVATE_DECISION_DATES[metadata_index]
    effective_from = PRIVATE_EFFECTIVE_DATES[metadata_index]
    exception = PRIVATE_EXCEPTIONS[
        (family_index * 3 + metadata_index) % len(PRIVATE_EXCEPTIONS)
    ]
    entity = f"{family['company']}（{jurisdiction}{PRIVATE_UNIT_NAMES[metadata_index]}）"
    retrieval_anchor = (
        f"{family['company']}《{family['policy']}：{PATCH_SPECS[patch_class]['label']}专编》"
        f"—{jurisdiction}—自{effective_from}起生效"
    )

    return {
        "family": family["name"],
        "evidence_mode": "fresh-private",
        "patch_class": patch_class,
        "entity": entity,
        "jurisdiction": jurisdiction,
        "decision_time": decision_time,
        "search_cues": [
            f"{entity}在{jurisdiction}执行{family['label']}时使用的内部规则",
            f"查找{decision_time}当日有效版本，并核验“{exception}”是否适用",
            PATCH_SPECS[patch_class]["search_focus"],
            f"与{family['resource']}、{family['action']}和{family['clock']}相关的联合条款",
        ],
        "applicable_policy_blueprint": {
            "document_type": "冻结后生成并隔离保存的合成私有政策",
            "retrieval_anchor": retrieval_anchor,
            "source_topic": "fresh_private_operational_policy",
            "clause_slots": _policy_slots(patch_class, family),
            "applicability": {
                "jurisdiction": jurisdiction,
                "entity_scope": f"仅覆盖{entity}这一{family['entity_type']}及其命名业务单元。",
                "effective_period": {
                    "starts_on": effective_from,
                    "ends_on": "直至被后续正式版本明确取代",
                    "decision_time_test": f"必须证明在{decision_time}仍然有效。",
                },
                "exception_scope": (
                    f"必须联合检索例外“{exception}”的触发条件、证明材料、适用动作和退出条件。"
                ),
            },
            "required_resolution_order": [
                "先按辖区、实体和决策时点筛选版本。",
                "再联合读取一般条款、条件条款、例外与优先级。",
                "最后把证据绑定到 typed patch；蓝图本身不提供最终参数值。",
            ],
        },
        "distractors": _private_distractors(
            family, jurisdiction, wrong_jurisdiction, entity, decision_time
        ),
        "anti_fogging_reason": (
            "公开题面只应暴露实体、辖区、决策时点和自然业务线索，不应复制政策正文、"
            "适用结论或最终参数。该蓝图要求先检索多个相互作用条款，再做版本、辖区、"
            "主体和例外核验；因此不是删词式语义雾化，也不能直接充当参考答案。"
        ),
        "web_source_url": None,
    }


def build_web_row(
    family: dict[str, str],
    source_topic: str,
    source_index: int,
    global_index: int,
) -> dict[str, Any]:
    patch_class = FROZEN_PATCH_ASSIGNMENTS[global_index]
    source = WEB_SOURCES[source_topic][source_index]
    return {
        "family": family["name"],
        "evidence_mode": "real-web",
        "patch_class": patch_class,
        "entity": source["entity"],
        "jurisdiction": source["jurisdiction"],
        "decision_time": source["decision_time"],
        "search_cues": [
            f"{source['agency']}关于{source['focus']}的官方规则入口",
            f"核验“{source['entity']}”在{source['decision_time']}的实体与活动分类",
            f"从一般规则、定义、有效期和例外共同判断{PATCH_SPECS[patch_class]['search_focus']}",
            "优先使用官方当前页并追溯其链接的 point-in-time 主规则或历史版本",
        ],
        "applicable_policy_blueprint": {
            "document_type": "真实官方网页及其链接的时点有效主规则",
            "retrieval_anchor": source["official_title"],
            "source_topic": source_topic,
            "clause_slots": [
                {
                    "slot": "applicability",
                    "retrieve": (
                        f"核验该官方来源在{source['decision_time']}是否治理"
                        f"{source['entity_scope']}。"
                    ),
                },
                {
                    "slot": "operative_rule",
                    "retrieve": (
                        f"提取与“{source['focus']}”直接相关的现行定义、资格、约束或目标项结构；"
                        "蓝图不预写数值。"
                    ),
                },
                {
                    "slot": "exception_or_alternate_path",
                    "retrieve": source["exception_scope"],
                },
                {
                    "slot": "point_in_time_precedence",
                    "retrieve": (
                        "区分现行规则、历史版、提案、指南和项目公告；记录决策时点版本与冲突规则优先级。"
                    ),
                },
            ],
            "applicability": {
                "jurisdiction": source["jurisdiction"],
                "entity_scope": source["entity_scope"],
                "effective_period": {
                    "decision_time": source["decision_time"],
                    "verification": "以官方 point-in-time 规则、修订记录或项目轮次材料核验。",
                },
                "exception_scope": source["exception_scope"],
            },
            "required_resolution_order": [
                "确认官方域名与来源机构。",
                "确认决策时点、辖区、实体和活动类别。",
                "联合解析一般规则、定义、例外与过渡条款。",
                "只把经核验内容绑定到 typed patch，不把 URL 或页面标题写入公开题面。",
            ],
        },
        "distractors": _web_distractors(source),
        "anti_fogging_reason": (
            "该条目仅是 real-web E?：URL 与检索线索可支持来源和适用性审计，但不能证明所有"
            "离线模型都不知道网页内容。公开题面不得出现 URL、页面标题、条文数值、patch 标签"
            "或适用结论；模型仍需区分现行/历史、辖区、主体与例外后才能修改优化模型。"
        ),
        "web_source_url": source["url"],
    }


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family_index, family in enumerate(FAMILIES):
        for case_index in range(8):
            rows.append(
                build_private_row(
                    family=family,
                    family_index=family_index,
                    case_index=case_index,
                    global_index=len(rows),
                )
            )
        for source_topic, source_index in WEB_ASSIGNMENTS[family["name"]]:
            rows.append(
                build_web_row(
                    family=family,
                    source_topic=source_topic,
                    source_index=source_index,
                    global_index=len(rows),
                )
            )
    return rows


def _iter_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _iter_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_keys(child)


def validate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assert len(rows) == 100, f"expected 100 rows, got {len(rows)}"
    assert tuple(family["name"] for family in FAMILIES) == FAMILY_ALLOWLIST
    for row_number, row in enumerate(rows, start=1):
        assert set(row) == TOP_LEVEL_FIELDS, f"row {row_number}: top-level field drift"
        assert row["family"] in FAMILY_ALLOWLIST
        assert row["evidence_mode"] in {"fresh-private", "real-web"}
        assert row["patch_class"] in PATCH_CLASSES
        assert isinstance(row["search_cues"], list) and len(row["search_cues"]) >= 3
        blueprint = row["applicable_policy_blueprint"]
        assert len(blueprint["clause_slots"]) >= 4
        applicability = blueprint["applicability"]
        assert applicability["jurisdiction"]
        assert applicability["entity_scope"]
        assert applicability["effective_period"]
        assert applicability["exception_scope"]
        assert [item["distractor_type"] for item in row["distractors"]] == [
            "old_version",
            "wrong_jurisdiction",
            "wrong_entity",
        ]
        banned_keys = {
            "source_id",
            "gold",
            "gold_value",
            "answer",
            "reference_answer",
            "solution",
            "objective_value",
            "solver_result",
        }
        assert not (set(_iter_keys(row)) & banned_keys), f"row {row_number}: leaked field"

    family_counts = Counter(row["family"] for row in rows)
    assert family_counts == Counter({family: 10 for family in FAMILY_ALLOWLIST})

    evidence_counts = Counter(row["evidence_mode"] for row in rows)
    assert evidence_counts == Counter({"fresh-private": 80, "real-web": 20})

    for family in FAMILIES:
        family_modes = Counter(
            row["evidence_mode"] for row in rows if row["family"] == family["name"]
        )
        assert family_modes == Counter({"fresh-private": 8, "real-web": 2})
    patch_counts = Counter(row["patch_class"] for row in rows)
    assert patch_counts == Counter({patch_class: 25 for patch_class in PATCH_CLASSES})

    private_rows = [row for row in rows if row["evidence_mode"] == "fresh-private"]
    assert all(row["web_source_url"] is None for row in private_rows)
    assert len(
        {
            row["applicable_policy_blueprint"]["retrieval_anchor"]
            for row in private_rows
        }
    ) == len(private_rows)
    assert all(
        row["applicable_policy_blueprint"]["document_type"]
        == "冻结后生成并隔离保存的合成私有政策"
        for row in private_rows
    )

    web_rows = [row for row in rows if row["evidence_mode"] == "real-web"]
    official_domains = {
        "www.fmcsa.dot.gov",
        "www.ecfr.gov",
        "www.fda.gov",
        "www.fns.usda.gov",
        "www.irs.gov",
        "www.epa.gov",
        "www.dir.ca.gov",
        "www.dol.gov",
        "www.lni.wa.gov",
        "app.leg.wa.gov",
    }
    assert all(
        urlparse(row["web_source_url"]).scheme == "https"
        and urlparse(row["web_source_url"]).netloc in official_domains
        for row in web_rows
    )
    assert len({row["web_source_url"] for row in web_rows}) == len(web_rows)
    web_topic_counts = Counter(
        row["applicable_policy_blueprint"]["source_topic"] for row in web_rows
    )
    assert web_topic_counts == Counter(
        {
            "transport_crew": 4,
            "food_nutrition": 4,
            "clean_vehicles": 4,
            "emissions_hazardous_waste": 4,
            "labor_rest": 4,
        }
    )

    return {
        "rows": len(rows),
        "families": dict(sorted(family_counts.items())),
        "evidence_modes": dict(sorted(evidence_counts.items())),
        "patch_classes": dict(sorted(patch_counts.items())),
        "web_topics": dict(sorted(web_topic_counts.items())),
        "private_distractor_pattern": {
            "old_version": len(private_rows),
            "wrong_jurisdiction": len(private_rows),
            "wrong_entity": len(private_rows),
        },
    }


def serialize(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )


def read_output() -> list[dict[str, Any]]:
    with OUTPUT.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate the existing JSONL and prove it matches deterministic generation.",
    )
    args = parser.parse_args()

    expected_rows = build_rows()
    expected_summary = validate(expected_rows)
    if args.check_only:
        actual_rows = read_output()
        actual_summary = validate(actual_rows)
        assert actual_rows == expected_rows, "JSONL differs from deterministic generation"
        assert actual_summary == expected_summary
        print(json.dumps({"status": "PASS", **actual_summary}, ensure_ascii=False))
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(serialize(expected_rows), encoding="utf-8", newline="\n")
    actual_rows = read_output()
    assert actual_rows == expected_rows, "UTF-8 JSONL round-trip mismatch"
    print(json.dumps({"status": "BUILT", **expected_summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
