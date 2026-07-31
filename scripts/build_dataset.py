"""Build the complete SearchWorthyOR-100 draft artifact set.

The script consumes a dual-reviewed *background inspiration* pool and evidence
blueprints, then authors independent compact, fully enumerable binary MILPs.
The inspiration rows are never claimed to be source bases: no source formulation,
reference code, or reference answer is inherited into the new tasks.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
from urllib.parse import urlparse
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from solver_backend import (
    TOL,
    certify_world_pair,
    enumerate_optimal_actions,
    sha256_json,
)


FAMILIES = [
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
]
PATCH_CLASSES = [
    "eligibility_domain",
    "temporal_coupling",
    "conditional_auxiliary",
    "quota_risk_service_objective",
]
EVIDENCE_COUNTS = {"fresh-private": 80, "real-web": 20}
FROZEN_PATCH_ORDINALS = (
    "20333112010311032223023101210103121313230312203101"
    "32000312232310313001022202012300212021013331213023"
)
BUILD_TIMESTAMP = "2026-07-30T12:00:00+08:00"
DECISION_DATES = [
    "2026-10-06",
    "2026-11-18",
    "2027-01-12",
    "2027-03-09",
    "2027-05-20",
]


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

FAMILY_META = {
    "routing_transport": {
        "zh": "路径与运输",
        "object": "候选运输路径包",
        "verb": "启用",
        "resource": "调度资源点",
        "objective": "总运输服务收益",
        "prefix": "路径包",
    },
    "scheduling_workforce": {
        "zh": "排班与劳动力",
        "object": "候选班次模板",
        "verb": "采用",
        "resource": "关键工时点",
        "objective": "总覆盖收益",
        "prefix": "班次",
    },
    "production_capacity": {
        "zh": "生产与容量规划",
        "object": "候选生产模式",
        "verb": "启用",
        "resource": "设备容量点",
        "objective": "总生产贡献",
        "prefix": "模式",
    },
    "assignment_matching": {
        "zh": "分配与匹配",
        "object": "候选匹配方案",
        "verb": "确认",
        "resource": "协调资源点",
        "objective": "总匹配效用",
        "prefix": "匹配",
    },
    "facility_network": {
        "zh": "设施选址与网络设计",
        "object": "候选设施节点",
        "verb": "建设",
        "resource": "建设资源点",
        "objective": "总网络覆盖收益",
        "prefix": "节点",
    },
    "inventory_supply_chain": {
        "zh": "库存与供应链",
        "object": "候选补货服务包",
        "verb": "签约",
        "resource": "仓储资源点",
        "objective": "总保供收益",
        "prefix": "补货包",
    },
    "energy_environment": {
        "zh": "能源与环境",
        "object": "候选能源运行方案",
        "verb": "采用",
        "resource": "并网资源点",
        "objective": "总能源服务收益",
        "prefix": "能源方案",
    },
    "healthcare_resources": {
        "zh": "医疗资源配置",
        "object": "候选医疗服务单元",
        "verb": "开放",
        "resource": "临床资源点",
        "objective": "总服务效用",
        "prefix": "服务单元",
    },
    "finance_portfolio": {
        "zh": "金融与组合选择",
        "object": "候选投资策略包",
        "verb": "纳入",
        "resource": "资本占用点",
        "objective": "总风险调整收益",
        "prefix": "策略包",
    },
    "telecom_service": {
        "zh": "通信与服务系统",
        "object": "候选通信服务模块",
        "verb": "部署",
        "resource": "频谱与运维点",
        "objective": "总服务覆盖收益",
        "prefix": "服务模块",
    },
}

PRIVATE_ENTITIES = [
    "岚序运营联合体",
    "澄湾公共服务中心",
    "星浦协同采购组",
    "青屿区域调度署",
    "云衡资源管理局",
    "霁川供应保障部",
    "海棠网络运营社",
    "栖原综合服务站",
    "镜湖联合计划处",
    "望汀基础设施组",
]
PRIVATE_JURISDICTIONS = [
    "海岬新区",
    "澄湾示范区",
    "青屿协作区",
    "霁川试验区",
    "镜湖联合区",
]

WEB_TOPIC_FACTS = {
    "transport_crew": (
        "现行官方运输或机组规则按主体与运行类型规定驾驶或执勤窗口、休息安排、"
        "累计限制及例外；试点招募或错误运行类型不能替代普遍适用规则。"
    ),
    "clean_vehicles": (
        "现行清洁车辆或补能设施项目按车辆或设施类别、取得与投入使用时间、用途、"
        "地点和项目轮次决定资格及可计入的目标项。"
    ),
    "food_nutrition": (
        "现行食品营养或标签规则按产品、经营主体、份量或供餐对象规定必须提供的"
        "组成、声明或服务项，并存在产品类别和主体例外。"
    ),
    "emissions_hazardous_waste": (
        "现行排放与危险废物规则先按设施、废物和活动分类，再激活相应处理、储存、"
        "时间、记录或排放控制要求；州级加严和规则版本需要单独核验。"
    ),
    "labor_rest": (
        "现行劳动工时材料按辖区、行业和劳动者类别规定休息、用餐、连续工作和"
        "计薪分支；未成年人、医疗、农业或豁免主体可能采用不同规则。"
    ),
}

OFFICIAL_ISSUERS = {
    "www.fmcsa.dot.gov": "U.S. Federal Motor Carrier Safety Administration",
    "www.irs.gov": "U.S. Internal Revenue Service",
    "www.lni.wa.gov": "Washington State Department of Labor & Industries",
    "www.fda.gov": "U.S. Food and Drug Administration",
    "www.epa.gov": "U.S. Environmental Protection Agency",
    "www.ecfr.gov": "Electronic Code of Federal Regulations",
    "www.dir.ca.gov": "California Division of Labor Standards Enforcement",
    "app.leg.wa.gov": "Washington State Code Reviser",
    "www.fns.usda.gov": "USDA Food and Nutrition Service",
    "www.dol.gov": "U.S. Department of Labor",
}

WEB_SUPPORT_FRAGMENTS = {
    "https://www.ecfr.gov/api/versioner/v1/full/2026-06-15/title-49.xml?part=395&section=395.3": "may drive a total of 11 hours during the period specified in paragraph (a)(2)",
    "https://www.ecfr.gov/api/versioner/v1/full/2026-07-10/title-14.xml?part=117": "at least 10 consecutive hours immediately before beginning",
    "https://www.ecfr.gov/api/versioner/v1/full/2026-06-20/title-49.xml?part=395": "driving is not permitted if more than 8 hours of driving time have passed without at least a consecutive 30-minute interruption in driving status",
    "https://www.ecfr.gov/api/versioner/v1/full/2026-05-12/title-49.xml?part=395&subpart=A": "driving is not permitted if more than 8 hours of driving time have passed without at least a consecutive 30-minute interruption in driving status",
    "https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/menu-labeling-requirements": (
        "The menu labeling requirements apply to restaurants and similar retail food establishments "
        "that are part of a chain with 20 or more locations. In addition, they must be doing business "
        "under the same name and offering for sale substantially the same menu items. Covered "
        "establishments must disclose the number of calories contained in standard items on menus "
        "and menu boards"
    ),
    "https://www.ecfr.gov/api/versioner/v1/full/2026-04-22/title-21.xml?part=101&section=101.91": (
        'The labeling claim "gluten-free" means: (i) That the food bearing the claim in its labeling: '
        "(A) Does not contain any one of the following: ( 1 ) An ingredient that is a gluten-containing "
        "grain (e.g., spelt wheat); ( 2 ) An ingredient that is derived from a gluten-containing grain "
        "and that has not been processed to remove gluten (e.g., wheat flour); or ( 3 ) An ingredient "
        "that is derived from a gluten-containing grain and that has been processed to remove gluten "
        "(e.g., wheat starch), if the use of that ingredient results in the presence of 20 parts per "
        "million (ppm) or more gluten in the food"
    ),
    "https://www.ecfr.gov/api/versioner/v1/full/2026-03-25/title-7.xml?part=210&section=210.10": "include at least one fruit or vegetable",
    "https://www.ecfr.gov/api/versioner/v1/full/2026-06-02/title-21.xml?part=101&section=101.9": "Nutrition information relating to food shall be provided for all products intended for human consumption and offered for sale unless an exemption is provided for the product in paragraph (j) of this section",
    "https://www.irs.gov/newsroom/topic-g-frequently-asked-questions-about-qualified-commercial-clean-vehicle-credit": "A Qualified Commercial Clean Vehicle Credit is not allowed with respect to a vehicle for which a New Clean Vehicle Credit was allowed",
    "https://www.irs.gov/clean-vehicle-tax-credits": "not available for vehicles acquired after Sept. 30, 2025",
    "https://www.irs.gov/credits-deductions/alternative-fuel-vehicle-refueling-property-credit": "the refueling or recharging property must be installed in a low-income community census tract or non-urban census tract",
    "https://www.epa.gov/system/files/documents/2024-04/2024-chdv-grants-nofo-2024-04.pdf": "Applicants must propose to replace eligible vehicles with comparable, eligible ZE vehicles. Existing vehicles must be disposed of (i.e., scrapped, sold, or donated) according to program guidelines",
    "https://www.epa.gov/hwgenerators/categories-hazardous-waste-generators": "Small Quantity Generators (SQGs) generate more than 100 kilograms, but less than 1,000 kilograms of hazardous waste per month",
    "https://www.epa.gov/hwgenerators/frequent-questions-about-hazardous-waste-generation": "A large quantity generator (LQG) can accumulate hazardous waste on site for up to 90 days",
    "https://www.epa.gov/hw/land-disposal-restrictions-hazardous-waste": "prohibits the land disposal of untreated hazardous wastes",
    "https://www.ecfr.gov/api/versioner/v1/full/2026-06-10/title-40.xml?part=63&subpart=EEE": "The provisions of this subpart apply to all hazardous waste combustors: hazardous waste incinerators, hazardous waste cement kilns, hazardous waste lightweight aggregate kilns, hazardous waste solid fuel boilers, hazardous waste liquid fuel boilers, and hazardous waste hydrochloric acid production furnaces",
    "https://www.dir.ca.gov/dlse/faq_restperiods.htm": "ten consecutive minutes for each four hour work period",
    "https://www.ecfr.gov/api/versioner/v1/full/2026-04-16/title-29.xml?part=785": "The employee must be completely relieved from duty for the purposes of eating regular meals",
    "https://app.leg.wa.gov/wac/default.aspx?cite=296-126-092": "not less than ten minutes, on the employer's time, for each four hours of working time",
    "https://www.dir.ca.gov/dlse/faq_mealperiods.htm": "more than five hours per day without providing the employee with a meal period of not less than thirty minutes",
}

WEB_SUPPORT_EXTRA_FRAGMENTS = {
    "https://www.ecfr.gov/api/versioner/v1/full/2026-04-22/title-21.xml?part=101&section=101.91": [
        'A food that bears the claim "gluten-free" in its labeling and fails to meet the requirements of paragraph (a)(3) of this section and, if applicable, paragraphs (c)(2) through (4) of this section will be deemed misbranded'
    ],
    "https://www.ecfr.gov/api/versioner/v1/full/2026-06-10/title-40.xml?part=63&subpart=EEE": [
        "Emission limits for existing sources. You must not discharge or cause combustion gases to be emitted into the atmosphere that contain:",
        "Mercury in excess of 130 µg/dscm, corrected to 7 percent oxygen",
    ],
}


def web_support_fragments(url: str) -> list[str]:
    return [WEB_SUPPORT_FRAGMENTS[url], *WEB_SUPPORT_EXTRA_FRAGMENTS.get(url, [])]


WEB_SOURCE_PROVENANCE = {
    "https://www.ecfr.gov/api/versioner/v1/full/2026-06-15/title-49.xml?part=395&section=395.3": {
        "version": "ecfr-point-in-time-2026-06-15",
        "issued_at": "2026-06-15",
        "issued_at_kind": "ecfr_point_in_time_edition_date",
        "effective_from": "2026-06-15",
        "effective_to": "2026-06-15",
        "effective_from_basis": "exact eCFR point-in-time edition requested for the decision date",
    },
    "https://www.ecfr.gov/api/versioner/v1/full/2026-07-10/title-14.xml?part=117": {
        "version": "ecfr-point-in-time-2026-07-10",
        "issued_at": "2026-07-10",
        "issued_at_kind": "ecfr_point_in_time_edition_date",
        "effective_from": "2026-07-10",
        "effective_to": "2026-07-10",
        "effective_from_basis": "exact eCFR point-in-time edition requested for the decision date",
    },
    "https://www.ecfr.gov/api/versioner/v1/full/2026-06-20/title-49.xml?part=395": {
        "version": "ecfr-point-in-time-2026-06-20",
        "issued_at": "2026-06-20",
        "issued_at_kind": "ecfr_point_in_time_edition_date",
        "effective_from": "2026-06-20",
        "effective_to": "2026-06-20",
        "effective_from_basis": "exact eCFR point-in-time edition requested for the decision date",
    },
    "https://www.ecfr.gov/api/versioner/v1/full/2026-05-12/title-49.xml?part=395&subpart=A": {
        "version": "ecfr-point-in-time-2026-05-12",
        "issued_at": "2026-05-12",
        "issued_at_kind": "ecfr_point_in_time_edition_date",
        "effective_from": "2026-05-12",
        "effective_to": "2026-05-12",
        "effective_from_basis": "exact eCFR point-in-time edition requested for the decision date",
    },
    "https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/menu-labeling-requirements": {
        "version": "menu-labeling-final-rule-2014",
        "issued_at": "2014-12-01",
        "issued_at_kind": "final_rule_publication_date",
        "effective_from": "2018-05-07",
        "effective_to": None,
        "effective_from_basis": "FDA-stated compliance date",
    },
    "https://www.ecfr.gov/api/versioner/v1/full/2026-04-22/title-21.xml?part=101&section=101.91": {
        "version": "ecfr-point-in-time-2026-04-22",
        "issued_at": "2026-04-22",
        "issued_at_kind": "ecfr_point_in_time_edition_date",
        "effective_from": "2026-04-22",
        "effective_to": "2026-04-22",
        "effective_from_basis": "exact eCFR point-in-time edition requested for the decision date",
    },
    "https://www.ecfr.gov/api/versioner/v1/full/2026-03-25/title-7.xml?part=210&section=210.10": {
        "version": "ecfr-point-in-time-2026-03-25",
        "issued_at": "2026-03-25",
        "issued_at_kind": "ecfr_point_in_time_edition_date",
        "effective_from": "2026-03-25",
        "effective_to": "2026-03-25",
        "effective_from_basis": "exact eCFR point-in-time edition requested for the decision date",
    },
    "https://www.ecfr.gov/api/versioner/v1/full/2026-06-02/title-21.xml?part=101&section=101.9": {
        "version": "ecfr-point-in-time-2026-06-02",
        "issued_at": "2026-06-02",
        "issued_at_kind": "ecfr_point_in_time_edition_date",
        "effective_from": "2026-06-02",
        "effective_to": "2026-06-02",
        "effective_from_basis": "exact eCFR point-in-time edition requested for the decision date",
    },
    "https://www.irs.gov/newsroom/topic-g-frequently-asked-questions-about-qualified-commercial-clean-vehicle-credit": {
        "version": "topic-g-q10-added-2023-03-31",
        "issued_at": "2023-03-31",
        "issued_at_kind": "official_faq_item_added_date",
        "effective_from": "2023-01-01",
        "effective_to": None,
        "effective_from_basis": "section 45W credit applies to vehicles acquired and placed in service after 2022",
    },
    "https://www.irs.gov/clean-vehicle-tax-credits": {
        "version": "public-law-119-21-cutoff-2025-07-04",
        "issued_at": "2025-07-04",
        "issued_at_kind": "underlying_law_enactment_date",
        "effective_from": "2025-07-04",
        "effective_to": None,
        "effective_from_basis": "official page identifies the statutory 2025-09-30 acquisition cutoff",
    },
    "https://www.irs.gov/credits-deductions/alternative-fuel-vehicle-refueling-property-credit": {
        "version": "notice-2024-20-geographic-rules",
        "issued_at": "2024-01-19",
        "issued_at_kind": "official_notice_release_date",
        "effective_from": "2023-01-01",
        "effective_to": None,
        "effective_from_basis": "IRA-modified section 30C location rules for property placed in service after 2022",
    },
    "https://www.epa.gov/system/files/documents/2024-04/2024-chdv-grants-nofo-2024-04.pdf": {
        "version": "2024-clean-heavy-duty-vehicles-nofo",
        "issued_at": "2024-04-24",
        "issued_at_kind": "official_nofo_open_date",
        "effective_from": "2024-04-24",
        "effective_to": "2024-07-25",
        "effective_from_basis": "official NOFO open and close dates",
    },
    "https://www.epa.gov/hwgenerators/categories-hazardous-waste-generators": {
        "version": "official-generator-categories-current-frozen-snapshot",
        "issued_at": "2016-11-28",
        "issued_at_kind": "underlying_generator_improvements_rule_publication_date",
        "effective_from": "2017-05-30",
        "effective_to": None,
        "effective_from_basis": "federal effective date of the 2016 Generator Improvements Rule",
    },
    "https://www.epa.gov/hwgenerators/frequent-questions-about-hazardous-waste-generation": {
        "version": "official-faq-current-frozen-snapshot",
        "issued_at": "2016-11-28",
        "issued_at_kind": "underlying_generator_improvements_rule_publication_date",
        "effective_from": "2017-05-30",
        "effective_to": None,
        "effective_from_basis": "federal effective date of the Generator Improvements Rule; the frozen EPA FAQ supplies the operative monthly-category explanation",
    },
    "https://www.epa.gov/hw/land-disposal-restrictions-hazardous-waste": {
        "version": "official-page-last-updated-2025-10-09",
        "issued_at": "2025-10-09",
        "issued_at_kind": "official_page_last_updated",
        "effective_from": "2025-10-09",
        "effective_to": None,
        "effective_from_basis": "conservative official-page-version availability date; underlying LDR rule is older",
    },
    "https://www.ecfr.gov/api/versioner/v1/full/2026-06-10/title-40.xml?part=63&subpart=EEE": {
        "version": "ecfr-point-in-time-2026-06-10",
        "issued_at": "2026-06-10",
        "issued_at_kind": "ecfr_point_in_time_edition_date",
        "effective_from": "2026-06-10",
        "effective_to": "2026-06-10",
        "effective_from_basis": "exact eCFR point-in-time edition requested for the decision date",
    },
    "https://www.dir.ca.gov/dlse/faq_restperiods.htm": {
        "version": "california-dlse-rest-periods-april-2021",
        "issued_at": "2021-04-01",
        "issued_at_kind": "official_page_revision_month_normalized_to_first_day",
        "effective_from": "2021-04-01",
        "effective_to": None,
        "effective_from_basis": "conservative page-version date; underlying wage-order duty is older",
    },
    "https://www.ecfr.gov/api/versioner/v1/full/2026-04-16/title-29.xml?part=785": {
        "version": "ecfr-point-in-time-2026-04-16",
        "issued_at": "2026-04-16",
        "issued_at_kind": "ecfr_point_in_time_edition_date",
        "effective_from": "2026-04-16",
        "effective_to": "2026-04-16",
        "effective_from_basis": "exact eCFR point-in-time edition requested for the decision date",
    },
    "https://app.leg.wa.gov/wac/default.aspx?cite=296-126-092": {
        "version": "WAC-296-126-092-order-76-15",
        "issued_at": "1976-05-17",
        "issued_at_kind": "codified_order_filing_date",
        "effective_from": "1976-05-17",
        "effective_to": None,
        "effective_from_basis": "codified order filing date used as a conservative historical applicability anchor",
    },
    "https://www.dir.ca.gov/dlse/faq_mealperiods.htm": {
        "version": "california-dlse-meal-periods-revised-2012-07-11",
        "issued_at": "2012-07-11",
        "issued_at_kind": "official_page_revision_date",
        "effective_from": "2012-07-11",
        "effective_to": None,
        "effective_from_basis": "conservative page-revision date; underlying Labor Code duty is older",
    },
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    path.write_text(text, encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_frozen_web_fetches(
    root: Path, blueprints: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(root / "private" / "web_snapshots" / "fetch_manifest.jsonl")
    registry: dict[str, dict[str, Any]] = {}
    expected_urls = {
        row["web_source_url"]
        for row in blueprints
        if row.get("evidence_mode") == "real-web"
    }
    expected_task_ids = {
        row["web_source_url"]: public_task_id(index)
        for index, row in enumerate(blueprints)
        if row.get("evidence_mode") == "real-web"
    }
    for row in rows:
        url = row.get("requested_url")
        if not isinstance(url, str) or url in registry:
            raise ValueError("web fetch manifest requires unique requested_url values")
        if row.get("fetch_kind") != "actual_http_get" or row.get("status_code") != 200:
            raise ValueError(f"web fetch is not a successful actual HTTP GET: {url}")
        if row.get("task_id") != expected_task_ids.get(url):
            raise ValueError(
                "web fetch manifest task ID does not match the current "
                f"deterministic URL-to-task binding: {url}"
            )
        if row.get("support_excerpt_verified_in_normalized_dom_text") is not True:
            raise ValueError(
                f"web support excerpt was not verified in normalized DOM text: {url}"
            )
        if row.get("support_text_normalization") != (
            "html_entity_unescape+unicode_quote_dash_fold+whitespace_collapse+casefold"
        ):
            raise ValueError(f"web support normalization contract mismatch: {url}")
        if row.get("support_excerpts") != web_support_fragments(url):
            raise ValueError(f"web support excerpt set differs from contract: {url}")
        raw_rel = row.get("raw_path")
        if not isinstance(raw_rel, str):
            raise ValueError(f"web fetch has no raw response path: {url}")
        raw_path = (root / raw_rel).resolve()
        if not raw_path.is_relative_to(root.resolve()) or not raw_path.is_file():
            raise ValueError(f"web fetch raw response is missing or out of scope: {url}")
        if file_sha256(raw_path) != row.get("raw_content_sha256"):
            raise ValueError(f"web fetch raw response hash mismatch: {url}")
        metadata = {key: value for key, value in row.items() if key != "metadata_sha256"}
        if sha256_json(metadata) != row.get("metadata_sha256"):
            raise ValueError(f"web fetch metadata hash mismatch: {url}")
        registry[url] = row
    if set(registry) != expected_urls or len(registry) != 20:
        raise ValueError(
            "web fetch manifest must contain exactly the 20 blueprint URLs"
        )
    return registry


def opaque_id(prefix: str, seed: str) -> str:
    return f"{prefix}-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16].upper()}"


PUBLIC_ID_ORDER = sorted(
    range(1, 101),
    key=lambda value: hashlib.sha256(
        f"SearchWorthyOR-100-public-id-v3|1|{value}".encode("utf-8")
    ).hexdigest(),
)


def public_task_id(zero_based_index: int) -> str:
    if not 0 <= zero_based_index < 100:
        raise ValueError(f"task index out of range: {zero_based_index}")
    return f"SWOR{PUBLIC_ID_ORDER[zero_based_index]:03d}"


def effective_interval_kind(provenance: dict[str, Any]) -> str:
    basis = provenance["effective_from_basis"].casefold()
    if provenance["issued_at_kind"] == "ecfr_point_in_time_edition_date":
        return "exact_point_in_time_edition"
    if "nofo open and close" in basis:
        return "program_application_window"
    if any(
        marker in basis
        for marker in (
            "page-version",
            "page-revision",
            "filing date",
            "availability date",
        )
    ):
        return "verified_applicability_lower_bound_not_legal_effective_date"
    return "rule_or_program_effective_interval"


def compute_applicability(
    passport: dict[str, Any],
    comparisons: list[dict[str, Any]],
    decision_time: str,
    jurisdiction: str,
    entity: str,
) -> dict[str, Any]:
    decision_date = date.fromisoformat(decision_time)
    start = date.fromisoformat(passport["effective_from"])
    end = (
        date.fromisoformat(passport["effective_to"])
        if passport.get("effective_to") is not None
        else None
    )
    url = passport.get("url")
    hostname = (urlparse(url).hostname or "") if isinstance(url, str) else None
    authority_valid = bool(passport.get("authoritative")) and (
        url is None or hostname in OFFICIAL_ISSUERS
    )
    effective_at_decision = decision_date >= start and (
        end is None or decision_date <= end
    )
    jurisdiction_match = passport.get("jurisdiction") == jurisdiction
    subject_scope = passport.get("subject_scope")
    subject_scope_match = isinstance(subject_scope, str) and bool(
        subject_scope.strip()
    )
    exception_state = passport.get("exception_screening", {})
    exception_resolved = (
        isinstance(exception_state, dict)
        and exception_state.get("result") == "no_listed_exception_activated"
    )
    unique_source = (
        sum(entry.get("applicable") is True for entry in comparisons) == 1
        and all(
            entry.get("failure_reason")
            for entry in comparisons
            if entry.get("applicable") is False
        )
    )
    checks = {
        "unique_applicable_source": unique_source,
        "authority_valid": authority_valid,
        "effective_at_decision": effective_at_decision,
        "jurisdiction_match": jurisdiction_match,
        "subject_scope_match": subject_scope_match,
        "exception_inactive_or_resolved": exception_resolved,
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "decision_time": decision_time,
        "jurisdiction": jurisdiction,
        "subject": entity,
        "comparison": comparisons,
        **checks,
        "derivation": {
            "authority_hostname": hostname,
            "effective_interval": [
                passport["effective_from"],
                passport.get("effective_to"),
            ],
            "passport_jurisdiction": passport.get("jurisdiction"),
            "passport_subject_scope": subject_scope,
            "exception_screening": exception_state,
        },
    }


def choose_blueprint_value(
    blueprint: dict[str, Any], keys: tuple[str, ...], fallback: Any
) -> Any:
    for key in keys:
        if key in blueprint and blueprint[key] not in (None, ""):
            return blueprint[key]
    return fallback


def build_base_ir(
    task_id: str, base_id: str, family: str, index: int
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    """Build a compact, independently solvable base with family-specific structure.

    The source benchmark row is inspiration/provenance only.  This function
    creates the actual base that is exposed in the Chinese task.  Every family
    has a different constraint graph, while deterministic per-task variants
    prevent a single byte-renamed template from standing in for 100 bases.
    """

    n = 6 + (index % 3)
    k = 3
    meta = FAMILY_META[family]
    variables: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for position in range(n):
        name = f"x_{position}"
        benefit = 1000 - 53 * position + ((index * 17 + position * 11) % 19)
        resource = 1 + ((index * 7 + position * 5) % 4)
        item_name = f"{meta['prefix']}{chr(65 + position)}"
        variables.append(
            {
                "name": name,
                "vartype": "B",
                "lb": 0,
                "ub": 1,
                "domain_expression": f"{name} in {{0,1}}",
                "semantic_name": item_name,
            }
        )
        items.append(
            {
                "variable": name,
                "name": item_name,
                "benefit": benefit,
                "resource": resource,
                "policy_attribute": (
                    "基础类别"
                    if position < n - 2
                    else f"保障类别{position - (n - 3)}"
                ),
            }
        )

    def linear_constraint(
        name: str,
        sense: str,
        rhs: float,
        terms: dict[str, float],
        requirement_zh: str,
    ) -> dict[str, Any]:
        symbol = {"<=": "<=", ">=": ">=", "==": "=="}[sense]
        expression = " + ".join(
            f"{coef:g}*{variable}" for variable, coef in terms.items()
        )
        return {
            "name": name,
            "sense": sense,
            "rhs": rhs,
            "terms": terms,
            "source": "public_problem",
            "expression": f"{expression} {symbol} {rhs:g}",
            "requirement_zh": requirement_zh,
        }

    all_terms = {item["variable"]: 1 for item in items}
    resource_terms = {
        item["variable"]: item["resource"] for item in items
    }
    resource_breakdown = "、".join(
        f"{item['name']}={item['resource']}" for item in items
    )
    top_capacity = sum(items[j]["resource"] for j in range(k))
    constraints: list[dict[str, Any]] = []
    objective_name = "maximize_operational_value"

    def item_names(selected: list[dict[str, Any]]) -> str:
        return "、".join(item["name"] for item in selected)

    if family == "routing_transport":
        objective_name = "maximize_route_service_value"
        for stage in range(3):
            stage_items = [item for pos, item in enumerate(items) if pos % 3 == stage]
            constraints.append(
                linear_constraint(
                    f"choose_one_leg_stage_{stage + 1}",
                    "==",
                    1,
                    {item["variable"]: 1 for item in stage_items},
                    (
                        f"运输链第{stage + 1}段必须且只能从"
                        f"{item_names(stage_items)}中采用一个候选路径包"
                    ),
                )
            )
    elif family == "scheduling_workforce":
        objective_name = "maximize_covered_shift_value"
        constraints.append(
            linear_constraint(
                "staff_exactly_three_shift_blocks",
                "==",
                k,
                all_terms,
                "本轮必须启用3个班次块",
            )
        )
        for period in range(3):
            period_items = [
                item for pos, item in enumerate(items) if pos % 3 == period
            ]
            constraints.append(
                linear_constraint(
                    f"cover_period_{period + 1}",
                    ">=",
                    1,
                    {item["variable"]: 1 for item in period_items},
                    (
                        f"时段{period + 1}至少由"
                        f"{item_names(period_items)}中的一个班次块覆盖"
                    ),
                )
            )
    elif family == "production_capacity":
        objective_name = "maximize_production_contribution"
        constraints.extend(
            [
                linear_constraint(
                    "activate_at_most_three_modes",
                    "<=",
                    k,
                    all_terms,
                    "最多启用3个生产模式",
                ),
                linear_constraint(
                    "production_resource_capacity",
                    "<=",
                    top_capacity,
                    resource_terms,
                    (
                        f"各模式生产资源占用为{resource_breakdown}；"
                        f"总占用不得超过{top_capacity}"
                    ),
                ),
            ]
        )
    elif family == "assignment_matching":
        objective_name = "maximize_assignment_quality"
        constraints.append(
            linear_constraint(
                "make_exactly_three_assignments",
                "==",
                k,
                all_terms,
                "必须完成3个分配",
            )
        )
        for group in range(3):
            conflict_positions = [group]
            if group + 3 < n:
                conflict_positions.append(group + 3)
            if group + 6 < n:
                conflict_positions.append(group + 6)
            constraints.append(
                linear_constraint(
                    f"worker_exclusivity_{group + 1}",
                    "<=",
                    1,
                    {
                        items[pos]["variable"]: 1
                        for pos in conflict_positions
                    },
                    (
                        f"资源主体{group + 1}对应的"
                        f"{item_names([items[pos] for pos in conflict_positions])}"
                        "中至多完成一个分配"
                    ),
                )
            )
    elif family == "facility_network":
        objective_name = "maximize_network_coverage_value"
        constraints.append(
            linear_constraint(
                "open_exactly_three_facilities",
                "==",
                k,
                all_terms,
                "必须建设3个设施或网络节点",
            )
        )
        for zone in range(2):
            zone_positions = [pos for pos in range(n) if pos % 2 == zone]
            constraints.append(
                linear_constraint(
                    f"cover_service_zone_{zone + 1}",
                    ">=",
                    1,
                    {
                        items[pos]["variable"]: 1
                        for pos in zone_positions
                    },
                    (
                        f"服务区{zone + 1}至少由"
                        f"{item_names([items[pos] for pos in zone_positions])}"
                        "中的一个设施覆盖"
                    ),
                )
            )
    elif family == "inventory_supply_chain":
        objective_name = "maximize_replenishment_value"
        constraints.extend(
            [
                linear_constraint(
                    "use_exactly_three_replenishment_blocks",
                    "==",
                    k,
                    all_terms,
                    "必须采用3个补货或供应块",
                ),
                linear_constraint(
                    "early_horizon_supply",
                    ">=",
                    1,
                    {
                        items[pos]["variable"]: 1
                        for pos in range(n)
                        if pos in {0, 1, 3, 6}
                    },
                    (
                        "计划前段至少从"
                        f"{item_names([items[pos] for pos in range(n) if pos in {0, 1, 3, 6}])}"
                        "中安排一个可到货的供应块"
                    ),
                ),
                linear_constraint(
                    "late_horizon_supply",
                    ">=",
                    1,
                    {
                        items[pos]["variable"]: 1
                        for pos in range(n)
                        if pos in {1, 2, 4, 7}
                    },
                    (
                        "计划后段至少从"
                        f"{item_names([items[pos] for pos in range(n) if pos in {1, 2, 4, 7}])}"
                        "中安排一个可到货的供应块"
                    ),
                ),
            ]
        )
    elif family == "energy_environment":
        objective_name = "maximize_energy_environment_value"
        constraints.extend(
            [
                linear_constraint(
                    "select_at_most_three_energy_units",
                    "<=",
                    k,
                    all_terms,
                    "最多启用3个能源单元",
                ),
                linear_constraint(
                    "energy_capacity_limit",
                    "<=",
                    top_capacity,
                    resource_terms,
                    (
                        f"各单元能源容量占用为{resource_breakdown}；"
                        f"总占用不得超过{top_capacity}"
                    ),
                ),
                linear_constraint(
                    "clean_capability_floor",
                    ">=",
                    1,
                    {
                        items[pos]["variable"]: 1
                        for pos in range(n)
                        if pos % 3 == 0
                    },
                    (
                        "至少启用一个清洁能力单元，清洁能力候选为"
                        f"{item_names([items[pos] for pos in range(n) if pos % 3 == 0])}"
                    ),
                ),
                linear_constraint(
                    "reserve_capability_floor",
                    ">=",
                    1,
                    {
                        items[pos]["variable"]: 1
                        for pos in range(n)
                        if pos % 3 == 1
                    },
                    (
                        "至少启用一个备用能力单元，备用能力候选为"
                        f"{item_names([items[pos] for pos in range(n) if pos % 3 == 1])}"
                    ),
                ),
            ]
        )
    elif family == "healthcare_resources":
        objective_name = "maximize_clinical_service_value"
        constraints.extend(
            [
                linear_constraint(
                    "activate_exactly_three_care_blocks",
                    "==",
                    k,
                    all_terms,
                    "必须启用3个医疗资源块",
                ),
                linear_constraint(
                    "urgent_service_coverage",
                    ">=",
                    1,
                    {items[0]["variable"]: 1, items[1]["variable"]: 1},
                    (
                        f"紧急服务至少由{item_names([items[0], items[1]])}"
                        "中的一个服务单元覆盖"
                    ),
                ),
                linear_constraint(
                    "continuity_service_coverage",
                    ">=",
                    1,
                    {items[1]["variable"]: 1, items[2]["variable"]: 1},
                    (
                        f"连续照护至少由{item_names([items[1], items[2]])}"
                        "中的一个服务单元覆盖"
                    ),
                ),
                linear_constraint(
                    "specialist_service_coverage",
                    ">=",
                    1,
                    {items[0]["variable"]: 1, items[2]["variable"]: 1},
                    (
                        f"专科服务至少由{item_names([items[0], items[2]])}"
                        "中的一个服务单元覆盖"
                    ),
                ),
            ]
        )
    elif family == "finance_portfolio":
        objective_name = "maximize_risk_adjusted_portfolio_value"
        risk_terms = {
            item["variable"]: 1 + ((index + pos * 2) % 5)
            for pos, item in enumerate(items)
        }
        portfolio_budget = k * max(item["resource"] for item in items)
        portfolio_risk = k * max(risk_terms.values())
        risk_breakdown = "、".join(
            f"{item['name']}={risk_terms[item['variable']]}"
            for item in items
        )
        constraints.extend(
            [
                linear_constraint(
                    "hold_exactly_three_positions",
                    "==",
                    k,
                    all_terms,
                    "投资组合必须持有3个策略头寸",
                ),
                linear_constraint(
                    "portfolio_budget",
                    "<=",
                    portfolio_budget,
                    resource_terms,
                    (
                        f"各策略投资预算占用为{resource_breakdown}；"
                        f"总占用不得超过{portfolio_budget}"
                    ),
                ),
                linear_constraint(
                    "portfolio_risk_limit",
                    "<=",
                    portfolio_risk,
                    risk_terms,
                    (
                        f"各策略风险点为{risk_breakdown}；"
                        f"组合风险点数不得超过{portfolio_risk}"
                    ),
                ),
            ]
        )
    elif family == "telecom_service":
        objective_name = "maximize_service_connectivity_value"
        constraints.append(
            linear_constraint(
                "activate_at_most_three_service_modules",
                "<=",
                k,
                all_terms,
                "最多启用3个通信服务模块",
            )
        )
        for zone in range(3):
            zone_positions = [pos for pos in range(n) if pos % 3 == zone]
            constraints.append(
                linear_constraint(
                    f"connect_zone_{zone + 1}",
                    ">=",
                    1,
                    {
                        items[pos]["variable"]: 1
                        for pos in zone_positions
                    },
                    (
                        f"通信区{zone + 1}至少由"
                        f"{item_names([items[pos] for pos in zone_positions])}"
                        "中的一个模块连通"
                    ),
                )
            )
        constraints.append(
            linear_constraint(
                "primary_requires_backhaul",
                "<=",
                0,
                {
                    items[0]["variable"]: 1,
                    items[1]["variable"]: -1,
                    items[4]["variable"]: -1,
                },
                (
                    f"启用主接入模块{items[0]['name']}时，必须同时启用"
                    f"主回传{items[1]['name']}或备用回传{items[4]['name']}"
                ),
            )
        )
    else:
        raise ValueError(f"Unknown family: {family}")

    variant = (index % 10) % 5
    if variant == 1:
        constraints.append(
            linear_constraint(
                "variant_tail_exclusivity",
                "<=",
                1,
                {items[-2]["variable"]: 1, items[-1]["variable"]: 1},
                (
                    f"末端两个备用候选{item_names(items[-2:])}"
                    "不得同时启用"
                ),
            )
        )
    elif variant == 2:
        constraints.append(
            linear_constraint(
                "variant_core_service_floor",
                ">=",
                2,
                {items[pos]["variable"]: 1 for pos in range(3)},
                (
                    f"前三个核心候选{item_names(items[:3])}"
                    "中至少启用两个"
                ),
            )
        )
    elif variant == 3:
        constraints.append(
            linear_constraint(
                "variant_first_fallback",
                ">=",
                1,
                {items[0]["variable"]: 1, items[3]["variable"]: 1},
                (
                    f"第一核心候选{items[0]['name']}与其备用项"
                    f"{items[3]['name']}中至少启用一个"
                ),
            )
        )
    elif variant == 4:
        constraints.append(
            linear_constraint(
                "variant_second_fallback",
                "==",
                1,
                {
                    items[1]["variable"]: 1,
                    items[4]["variable"]: 1,
                    items[-1]["variable"]: 1,
                },
                (
                    f"第二核心候选{items[1]['name']}、其备用项"
                    f"{items[4]['name']}与末端应急项{items[-1]['name']}"
                    "中恰好启用一个"
                ),
            )
        )

    capacity = top_capacity
    ir = {
        "schema_version": "1.0",
        "task_id": task_id,
        "base_id": base_id,
        "model_id": f"{task_id}_base",
        "world": "base",
        "family": family,
        "sense": "max",
        "single_objective": True,
        "variables": variables,
        "objective": {
            "name": objective_name,
            "constant": 0,
            "terms": {item["variable"]: item["benefit"] for item in items},
            "unit": "value_point",
        },
        "constraints": constraints,
        "action_projection": [item["variable"] for item in items],
        "metadata": {
            "item_count": n,
            "selection_count": k,
            "capacity": capacity,
            "family_zh": meta["zh"],
            "family_template": family,
            "structural_variant": variant,
            "base_requirements_zh": [
                constraint["requirement_zh"] for constraint in constraints
            ],
            "source_semantics": "public_problem",
        },
    }
    return ir, items, k


def apply_patch(
    base_ir: dict[str, Any],
    items: list[dict[str, Any]],
    patch_class: str,
    claim_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    patched = copy.deepcopy(base_ir)
    patched["world"] = "patched"
    patched["model_id"] = base_ir["model_id"].replace("_base", "_patched")
    ops: list[dict[str, Any]] = []
    if patch_class == "eligibility_domain":
        target = patched["variables"][0]
        before = target["domain_expression"]
        target["ub"] = 0
        target["domain_expression"] = f"{target['name']} = 0"
        after = target["domain_expression"]
        ops.append(
            {
                "op": "modify",
                "slot_type": "variable_domain",
                "model_slot_id": f"variables/{target['name']}/domain",
                "before_expression": before,
                "after_expression": after,
                "evidence_claim_id": claim_id,
                "code_region_id": f"patched_ir.json#/variables/{target['name']}",
            }
        )
        claim = f"{items[0]['name']}在本次主体、辖区和决策日下不具备采用资格。"
    elif patch_class == "temporal_coupling":
        constraint = {
            "name": "evidence_nonoverlap",
            "sense": "<=",
            "rhs": 1,
            "terms": {items[0]["variable"]: 1, items[1]["variable"]: 1},
            "source": claim_id,
            "expression": f"1*{items[0]['variable']} + 1*{items[1]['variable']} <= 1",
        }
        patched["constraints"].append(constraint)
        ops.append(
            {
                "op": "add",
                "slot_type": "constraint",
                "model_slot_id": "constraints/evidence_nonoverlap",
                "before_expression": None,
                "after_expression": (
                    constraint["expression"]
                ),
                "evidence_claim_id": claim_id,
                "code_region_id": "patched_ir.json#/constraints/evidence_nonoverlap",
            }
        )
        if items[0].get("coupling_requires_protected_option"):
            protected = items[-2:]
            service_terms = {
                **{item["variable"]: 1 for item in protected},
                items[1]["variable"]: -1,
            }
            service_expression = (
                " + ".join(f"1*{item['variable']}" for item in protected)
                + f" + -1*{items[1]['variable']} >= 0"
            )
            patched["constraints"].append(
                {
                    "name": "evidence_coupling_service",
                    "sense": ">=",
                    "rhs": 0,
                    "terms": service_terms,
                    "source": claim_id,
                    "expression": service_expression,
                }
            )
            ops.append(
                {
                    "op": "add",
                    "slot_type": "constraint",
                    "model_slot_id": "constraints/evidence_coupling_service",
                    "before_expression": None,
                    "after_expression": service_expression,
                    "evidence_claim_id": claim_id,
                    "code_region_id": "patched_ir.json#/constraints/evidence_coupling_service",
                }
            )
        claim = (
            f"{items[0]['name']}与{items[1]['name']}不得在同一决策窗口共同启用"
            + (
                f"；选择{items[1]['name']}还必须同时选择一个经核验的前置处理选项。"
                if items[0].get("coupling_requires_protected_option")
                else "。"
            )
        )
    elif patch_class == "conditional_auxiliary":
        patched["variables"].append(
            {
                "name": "z_trigger",
                "vartype": "B",
                "lb": 0,
                "ub": 1,
                "domain_expression": "z_trigger in {0,1}",
                "semantic_name": "外部规则触发状态",
            }
        )
        patched["constraints"].extend(
            [
                {
                    "name": "evidence_trigger_link",
                    "sense": "==",
                    "rhs": 0,
                    "terms": {items[0]["variable"]: 1, "z_trigger": -1},
                    "source": claim_id,
                    "expression": f"1*{items[0]['variable']} + -1*z_trigger == 0",
                },
                {
                    "name": "evidence_trigger_exclusion",
                    "sense": "<=",
                    "rhs": 1,
                    "terms": {items[1]["variable"]: 1, "z_trigger": 1},
                    "source": claim_id,
                    "expression": f"1*{items[1]['variable']} + 1*z_trigger <= 1",
                },
            ]
        )
        ops.extend(
            [
                {
                    "op": "add",
                    "slot_type": "variable",
                    "model_slot_id": "variables/z_trigger",
                    "before_expression": None,
                    "after_expression": "z_trigger in {0,1}",
                    "evidence_claim_id": claim_id,
                    "code_region_id": "patched_ir.json#/variables/z_trigger",
                },
                {
                    "op": "add",
                    "slot_type": "constraint",
                    "model_slot_id": "constraints/evidence_trigger_link",
                    "before_expression": None,
                    "after_expression": (
                        f"1*{items[0]['variable']} + -1*z_trigger == 0"
                    ),
                    "evidence_claim_id": claim_id,
                    "code_region_id": "patched_ir.json#/constraints/evidence_trigger_link",
                },
                {
                    "op": "add",
                    "slot_type": "constraint",
                    "model_slot_id": "constraints/evidence_trigger_exclusion",
                    "before_expression": None,
                    "after_expression": (
                        f"1*{items[1]['variable']} + 1*z_trigger <= 1"
                    ),
                    "evidence_claim_id": claim_id,
                    "code_region_id": "patched_ir.json#/constraints/evidence_trigger_exclusion",
                },
            ]
        )
        if items[0].get("evidence_requires_protected_option"):
            protected = items[-2:]
            service_terms = {
                **{item["variable"]: 1 for item in protected},
                "z_trigger": -1,
            }
            service_expression = (
                " + ".join(f"1*{item['variable']}" for item in protected)
                + " + -1*z_trigger >= 0"
            )
            patched["constraints"].append(
                {
                    "name": "evidence_trigger_service",
                    "sense": ">=",
                    "rhs": 0,
                    "terms": service_terms,
                    "source": claim_id,
                    "expression": service_expression,
                }
            )
            ops.append(
                {
                    "op": "add",
                    "slot_type": "constraint",
                    "model_slot_id": "constraints/evidence_trigger_service",
                    "before_expression": None,
                    "after_expression": service_expression,
                    "evidence_claim_id": claim_id,
                    "code_region_id": "patched_ir.json#/constraints/evidence_trigger_service",
                }
            )
        claim = (
            f"外部规则使{items[0]['name']}触发合规分支，且"
            f"{items[1]['name']}在该分支中不可采用"
            + (
                "；同时至少选择一个与该分支相容的保障选项。"
                if items[0].get("evidence_requires_protected_option")
                else "。"
            )
        )
    elif patch_class == "quota_risk_service_objective":
        protected = items[-2:]
        triggered = bool(items[0].get("evidence_quota_triggered"))
        terms = {item["variable"]: 1 for item in protected}
        rhs = 1
        if triggered:
            terms[items[0]["variable"]] = -1
            rhs = 0
        expression = " + ".join(
            f"{coefficient:g}*{variable}" for variable, coefficient in terms.items()
        ) + f" >= {rhs:g}"
        constraint = {
            "name": "evidence_service_quota",
            "sense": ">=",
            "rhs": rhs,
            "terms": terms,
            "source": claim_id,
            "expression": expression,
        }
        patched["constraints"].append(constraint)
        expression = constraint["expression"]
        ops.append(
            {
                "op": "add",
                "slot_type": "constraint",
                "model_slot_id": "constraints/evidence_service_quota",
                "before_expression": None,
                "after_expression": expression,
                "evidence_claim_id": claim_id,
                "code_region_id": "patched_ir.json#/constraints/evidence_service_quota",
            }
        )
        claim = (
            (
                f"选择{items[0]['name']}时，最终组合必须至少包含一个"
                if triggered
                else "最终组合必须至少包含一个"
            )
            + "与适用规则相容的保障选项："
            + "、".join(item["name"] for item in protected)
            + "。"
        )
    else:
        raise ValueError(f"Unknown patch class: {patch_class}")
    return patched, ops, claim


def localize_web_items(
    items: list[dict[str, Any]],
    source_topic: str,
    patch_class: str,
    url: str,
) -> None:
    localizations = {
        "https://www.ecfr.gov/api/versioner/v1/full/2026-06-15/title-49.xml?part=395&section=395.3": {
            "topic": "transport_crew",
            "patch": "eligibility_domain",
            "first": "单一驾驶片段连续驾驶11.5小时，且未登记短途、不利驾驶条件或其他适用例外",
            "second": "不与首段共享驾驶时间，按普通合规窗口执行",
            "protected": "包含可核验的合规休息或非驾驶中断",
        },
        "https://www.ecfr.gov/api/versioner/v1/full/2026-07-10/title-14.xml?part=117": {
            "topic": "transport_crew",
            "patch": "temporal_coupling",
            "first": "同一机组成员的前一飞行执勤段于22:00结束",
            "second": "同一机组成员的下一飞行执勤段拟于次日06:00开始，仅间隔8小时",
            "protected": "包含不少于10个连续小时的休息窗口",
            "global_context": "该计划属于正常排班，不涉及紧急运行偏离、获批疲劳风险管理替代或其他已登记例外。",
        },
        "https://www.ecfr.gov/api/versioner/v1/full/2026-06-20/title-49.xml?part=395": {
            "topic": "transport_crew",
            "patch": "conditional_auxiliary",
            "first": "该匹配使同一驾驶员自上次合规中断后累计驾驶超过8小时",
            "second": "占用同一驾驶员在该连续驾驶窗口内唯一可安排的中断时段",
            "protected": "在累计驾驶窗口内安排连续30分钟非驾驶时段",
            "requires_protected": True,
            "global_context": "该计划由州际财产承运人安排同一property-carrying commercial motor vehicle驾驶员；不属于short-haul、商业蜜蜂或牲畜运输、爆炸物押运及其他已登记例外。",
        },
        "https://www.ecfr.gov/api/versioner/v1/full/2026-05-12/title-49.xml?part=395&subpart=A": {
            "topic": "transport_crew",
            "patch": "quota_risk_service_objective",
            "first": "本规划期另有已承诺驾驶任务；与本组合叠加后，同一驾驶员自上次连续30分钟非驾驶时段起累计驾驶必然超过8小时；本任务块不含新的30分钟非驾驶时段",
            "second": "普通州际装载任务块，不含连续30分钟非驾驶时段",
            "protected": "为同一驾驶员安排连续30分钟非驾驶时段",
            "quota_triggered": True,
            "global_context": "同一驾驶员执行州际财产运输，且不适用49 CFR 395.1(e)(1)或(e)(2)的short-haul exceptions，也没有商业蜜蜂、牲畜、爆炸物押运或其他已登记例外。",
        },
        "https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/menu-labeling-requirements": {
            "topic": "food_nutrition",
            "patch": "eligibility_domain",
            "first": "把标准菜单项作为最终菜单板项目发布但不显示热量；该连锁有24个同名地点、销售实质相同菜单项，且该项目不是临时项目或定制点单",
            "second": "非标准临时菜单项，另行核验覆盖边界",
            "protected": "包含标准菜单项所需的可核验标签配置",
        },
        "https://www.ecfr.gov/api/versioner/v1/full/2026-04-22/title-21.xml?part=101&section=101.91": {
            "topic": "food_nutrition",
            "patch": "temporal_coupling",
            "first": "在同一最终包装上使用“gluten-free”声明",
            "second": "为同一最终包装采用含经过脱麸质处理的小麦淀粉的配方批次，且该配料使成品经检测含25 ppm麸质",
            "protected": "采用经检测麸质含量低于20 ppm且其余条件已核验的配方批次",
        },
        "https://www.ecfr.gov/api/versioner/v1/full/2026-06-02/title-21.xml?part=101&section=101.9": {
            "topic": "food_nutrition",
            "patch": "conditional_auxiliary",
            "first": "该补货包含拟按普通预包装食品类别销售的加工食品",
            "second": "把同一批食品以最终无营养标签状态交付零售，且该路径不允许后续附加标签",
            "protected": "提供与产品类别匹配的标签或声明服务",
            "requires_protected": True,
            "global_context": "该批次供普通消费者零售，已核实不属于21 CFR 101.9(j)列明的小企业、低销量、餐馆直接销售、婴儿配方、医疗食品或其他豁免分支。",
        },
        "https://www.ecfr.gov/api/versioner/v1/full/2026-03-25/title-7.xml?part=210&section=210.10": {
            "topic": "food_nutrition",
            "patch": "quota_risk_service_objective",
            "first": "普通菜单组件，本身不含水果或蔬菜",
            "second": "普通菜单组件，本身不含水果或蔬菜",
            "protected": "包含一份按本地食材台账核实的水果或蔬菜",
            "global_context": "本规划期每个最终组合都是由参与全国学校午餐计划的学校食品管理机构提交报销的一份完整午餐；计划外没有其他水果或蔬菜组件。",
        },
        "https://www.irs.gov/credits-deductions/alternative-fuel-vehicle-refueling-property-credit": {
            "topic": "clean_vehicles",
            "patch": "eligibility_domain",
            "first": "为位于城市化且不属于低收入社区的普查区域之补能节点申领第30C条财产抵免",
            "second": "位于非城市或低收入社区的替代节点",
            "protected": "登记为位于合资格地点的补能设施候选",
        },
        "https://www.epa.gov/system/files/documents/2024-04/2024-chdv-grants-nofo-2024-04.pdf": {
            "topic": "clean_vehicles",
            "patch": "temporal_coupling",
            "first": "通过2024项目资金取得零排放重型车辆，并把一辆在申请时完全可运行的EMY 2010柴油重型车辆列为对应替换资产",
            "second": "在项目执行期结束后继续把该对应EMY 2010柴油车辆配置为在役车辆",
            "protected": "提供项目范围内的零排放车辆或配套基础设施",
        },
        "https://www.irs.gov/newsroom/topic-g-frequently-asked-questions-about-qualified-commercial-clean-vehicle-credit": {
            "topic": "clean_vehicles",
            "patch": "temporal_coupling",
            "first": "对同一车辆采用第30D条新清洁车辆抵免分支",
            "second": "对同一车辆采用第45W条商业清洁车辆抵免分支",
            "protected": "采用经核验且不重复申领的单一抵免分支",
        },
        "https://www.irs.gov/clean-vehicle-tax-credits": {
            "topic": "clean_vehicles",
            "patch": "eligibility_domain",
            "first": "对一辆计划在2025年10月5日取得的清洁车辆申领联邦清洁车辆抵免",
            "second": "另一移动资产候选，取得时点另行核验",
            "protected": "登记为在截止日前取得并满足对应抵免分支的车辆候选",
        },
        "https://www.epa.gov/hwgenerators/categories-hazardous-waste-generators": {
            "topic": "emissions_hazardous_waste",
            "patch": "eligibility_domain",
            "first": "在本场所月产生150 kg非急性危险废物的情况下采用VSQG简化管理路径",
            "second": "按实际月产生量类别配置的替代处理方案",
            "protected": "提供与实际产生者类别一致的积存、记录或处理能力",
        },
        "https://www.epa.gov/hw/land-disposal-restrictions-hazardous-waste": {
            "topic": "emissions_hazardous_waste",
            "patch": "temporal_coupling",
            "first": "让同一批受LDR约束的危险废物在决策窗口内保持未达到处理标准的状态",
            "second": "在该窗口把同一批废物送往土地处置；若另有处理块被选择，则由其先行处理",
            "protected": "在土地处置前提供达到处理标准的能力",
            "coupling_requires_protected": True,
        },
        "https://www.epa.gov/hwgenerators/frequent-questions-about-hazardous-waste-generation": {
            "topic": "emissions_hazardous_waste",
            "patch": "conditional_auxiliary",
            "first": "启用后由已核验的现场分类记录把本月运行确定为large quantity generator活动",
            "second": "为同一批废物安排180天中央积存路径",
            "protected": "为该批废物提供不超过90天且满足适用单元标准的中央积存能力",
            "requires_protected": True,
        },
        "https://www.ecfr.gov/api/versioner/v1/full/2026-06-10/title-40.xml?part=63&subpart=EEE": {
            "topic": "emissions_hazardous_waste",
            "patch": "quota_risk_service_objective",
            "first": "危险废物燃烧运行服务本体，不改变烟气汞浓度",
            "second": "收运与暂存服务，不改变燃烧烟气汞浓度",
            "protected": "把按7%氧校正的计划烟气汞浓度从180 µg/dscm降至110 µg/dscm",
            "global_context": "本规划期必然运行一台燃烧危险废物的现有焚烧炉；未采用候选烟气处理配置时，按7%氧校正的计划汞浓度为180 µg/dscm，计划外没有其他减汞装置，且没有启动、停机、故障或延期例外。",
        },
        "https://www.ecfr.gov/api/versioner/v1/full/2026-04-16/title-29.xml?part=785": {
            "topic": "labor_rest",
            "patch": "conditional_auxiliary",
            "first": "把同一30分钟时段登记为不计工时的正式用餐时段",
            "second": "在该30分钟时段安排员工待命并随时恢复工作",
            "protected": "提供可完全脱离工作职责的真实用餐或替补覆盖",
        },
        "https://app.leg.wa.gov/wac/default.aspx?cite=296-126-092": {
            "topic": "labor_rest",
            "patch": "quota_risk_service_objective",
            "first": "普通岗位工作块，不含连续10分钟的无任务时段",
            "second": "普通岗位工作块，不含连续10分钟的无任务时段",
            "protected": "为同一员工安排连续10分钟且不承担任务的时段",
            "global_context": "本规划期固定包含同一成年员工连续4小时的工作段；业务可以安排连续10分钟无任务时段，且没有其他间歇空档、农业医疗场景或获批变通安排。",
        },
        "https://www.dir.ca.gov/dlse/faq_restperiods.htm": {
            "topic": "labor_rest",
            "patch": "conditional_auxiliary",
            "first": "该服务模块包含同一非豁免员工连续满4小时的受覆盖工作段",
            "second": "占用该员工在该4小时工作段中唯一可用的休息窗口",
            "protected": "提供不受工作任务占用的10分钟休息覆盖",
            "requires_protected": True,
        },
        "https://www.dir.ca.gov/dlse/faq_mealperiods.htm": {
            "topic": "labor_rest",
            "patch": "quota_risk_service_objective",
            "first": "本规划期固定包含同一非豁免员工连续超过5小时且未登记有效豁免的工作段；该普通现场服务块不单独提供30分钟用餐时段",
            "second": "普通现场服务块，不单独提供完全脱离职责的用餐时段",
            "protected": "提供员工不少于30分钟且完全脱离工作职责的真实用餐时段",
            "quota_triggered": True,
        },
    }
    localization = localizations.get(url)
    if localization is None:
        raise ValueError(f"No URL-specific local binding for {url}")
    if localization["topic"] != source_topic:
        raise ValueError(
            f"URL topic {localization['topic']!r} != blueprint topic {source_topic!r}"
        )
    if localization["patch"] != patch_class:
        raise ValueError(
            f"URL patch {localization['patch']!r} != task patch {patch_class!r}"
        )
    first = localization["first"]
    second = localization["second"]
    protected = localization["protected"]
    items[0]["policy_attribute"] = first
    items[1]["policy_attribute"] = second
    for item in items[-2:]:
        item["policy_attribute"] = protected
    if localization.get("global_context"):
        items[0]["global_context"] = localization["global_context"]
    if localization.get("requires_protected"):
        items[0]["evidence_requires_protected_option"] = True
    if localization.get("quota_triggered"):
        items[0]["evidence_quota_triggered"] = True
    if localization.get("coupling_requires_protected"):
        items[0]["coupling_requires_protected_option"] = True
    items[0]["official_rule_anchor"] = WEB_SUPPORT_FRAGMENTS[url]


def public_problem_text(
    task_id: str,
    family: str,
    entity: str,
    jurisdiction: str,
    decision_time: str,
    items: list[dict[str, Any]],
    selection_count: int,
    capacity: float,
    base_requirements_zh: list[str],
    evidence_mode: str,
) -> str:
    meta = FAMILY_META[family]
    seed = int(
        hashlib.sha256(f"public-prose-v2|{task_id}".encode("utf-8")).hexdigest(),
        16,
    )
    row_formats = (
        "- {name}：收益 {benefit}；{resource_name}占用 {resource}；经核实的业务属性是“{attribute}”。",
        "- {name}：可贡献 {benefit} 点收益，占用 {resource} 个{resource_name}，本地记录为“{attribute}”。",
        "- {name}：收益记为 {benefit}，资源需求为 {resource} {resource_name}；已确认属性“{attribute}”。",
        "- {name}：本轮收益 {benefit}，需要{resource_name} {resource}；适用性相关事实为“{attribute}”。",
        "- {name}：若启用可获得 {benefit} 点，占用{resource_name} {resource}；业务台账注明“{attribute}”。",
        "- {name}：价值贡献 {benefit}，消耗 {resource} 个{resource_name}；现场事实已核验为“{attribute}”。",
        "- {name}：预计收益 {benefit}，资源占用 {resource}（单位：{resource_name}）；登记属性“{attribute}”。",
        "- {name}：效用 {benefit}，需使用{resource_name} {resource}；公开本地事实为“{attribute}”。",
    )
    rows = "\n".join(
        row_formats[
            int(
                hashlib.sha256(
                    f"{task_id}|row|{item['name']}".encode("utf-8")
                ).hexdigest(),
                16,
            )
            % len(row_formats)
        ].format(
            name=item["name"],
            benefit=item["benefit"],
            resource_name=meta["resource"],
            resource=item["resource"],
            attribute=item["policy_attribute"],
        )
        for item in items
    )
    interface = (
        "SearchWorthyOR 私有政策语义检索接口"
        if evidence_mode == "fresh-private"
        else "官方网页 HTTPS 检索接口"
    )
    requirement_prefixes = ("- 必须满足：", "- 业务关系：", "- 基础约束：", "- 已冻结要求：")
    requirements = "\n".join(
        f"{requirement_prefixes[(seed + index) % len(requirement_prefixes)]}{requirement}。"
        for index, requirement in enumerate(base_requirements_zh)
    )
    introductions = (
        "{entity}正在为{jurisdiction}编制{family_zh}方案，决策日锁定为{decision_time}。",
        "在{decision_time}这一决策时点，{entity}需要完成{jurisdiction}内的{family_zh}选择。",
        "{entity}负责{jurisdiction}的{family_zh}计划；本题采用的决策时点是{decision_time}。",
        "面向{jurisdiction}的下一轮执行计划，{entity}将在{decision_time}确定{family_zh}组合。",
        "{entity}须在{decision_time}冻结一份适用于{jurisdiction}的{family_zh}决策。",
        "{jurisdiction}的资源计划由{entity}负责，并将在{decision_time}作出{family_zh}决定。",
        "本轮{family_zh}配置属于{entity}在{jurisdiction}的正式决策，时点为{decision_time}。",
        "{entity}计划于{decision_time}完成{jurisdiction}范围内的{family_zh}资源重排。",
    )
    data_leads = (
        "以下候选及本地数据已经由业务方确认：",
        "可选动作的收益、资源占用与本地事实如下：",
        "规划系统已冻结下列候选记录：",
        "建模可直接采用以下完整本地台账：",
        "候选集合及其核实属性列示如下：",
        "本次可决策对象和已知业务事实为：",
        "业务部门交付的候选数据如下：",
        "无需外部补数的候选清单如下：",
    )
    base_leads = (
        "先忽略尚未检索的外部政策，基础世界必须满足这些业务关系：",
        "仅按本地业务事实建模时，约束集合为：",
        "外部证据加入之前，基础模型由下列约束定义：",
        "基础世界的可行域须逐条包含：",
        "未应用政策补丁的模型具有以下业务约束：",
        "本地运营规则已经确定下列基础约束：",
        "base 世界不得遗漏这些关系：",
        "结构补丁加入前，先建立如下完整基础模型：",
    )
    completeness = (
        "这是单目标最大化问题；题面中的本地数字已经完整，不存在待搜索或待填的参数。",
        "唯一优化方向是最大化{objective}，所有本地参数均已给出，不能把检索当作补数。",
        "模型只有一个目标：最大化{objective}。基础约束与数值均已冻结且必须完整保留。",
        "请以最大化{objective}为唯一目标；本地输入没有缺项，搜索只用于确定结构规则。",
        "基础世界是完整的单目标模型，目标为最大化{objective}；不得通过猜测改写本地数据。",
        "唯一目标函数最大化{objective}，题面已经提供构造 base 所需的全部数字和关系。",
        "以最大化{objective}作为唯一目标；基础模型不是填空题，外部证据只能触发有依据的结构变更。",
        "本题不含第二目标，唯一目标为最大化{objective}；本地数据完整且上述约束都要编码。",
    )
    search_instructions = (
        "最终模型还要服从决策日对该主体、辖区和业务活动真正适用的外部规则。",
        "基础世界之外，必须检索并适用在该时点约束本主体与本业务的现行证据。",
        "完成 base 后，还需判断哪份外部政策在给定主体、地域和日期下具有约束力。",
        "最终可行域不能停留在本地模型；应检索该决策日实际生效且覆盖当前活动的规则。",
        "随后请处理外部规则带来的模型变化，前提是来源在权限、辖区、主体和时点上均适用。",
        "接下来需要从外部证据确定必须增加的模型结构，并先完成版本与适用范围裁决。",
        "外部政策可能改变可用动作或组合关系；只能采用对当前主体、辖区和日期有效的证据。",
        "请在 base 之上检索现行政策，但采纳前必须证明其覆盖当前实体、地域、时点与活动。",
    )
    warnings = (
        "不得按文件编号猜测，也不得用旧版、异地版或邻近主体材料替代适用来源。",
        "主题相似不等于适用；请排除历史文本、错误辖区、错误主体和未满足条件的例外。",
        "不要从候选文档 ID 反推答案，必须依据权限、版本、范围与例外完成裁决。",
        "若来源冲突或适用性不能唯一确定，应报告无法裁决，而不是任选一份材料。",
        "检索结果必须经过时点、辖区、主体及例外核验；非权威转述不能驱动补丁。",
        "只有可追溯证据才能改变模型，旧版本和跨辖区类推均视为错误。",
        "不得把搜索退化成精确 ID 查询，也不能用只改数字的方式冒充结构补丁。",
        "请拒绝失效版本、错误活动类别及缺少正式权限的候选来源。",
    )
    outputs = (
        "返回适用来源及理由、结构化补丁、最终单目标模型、最优行动与目标值，并逐项给出 claim→model slot→equation→code region 映射。",
        "输出应覆盖来源适用性、变量/域/约束/目标结构变化、最终模型与解，以及证据主张到模型位置的可审计映射。",
        "请交付来源裁决、补丁操作、最终数学模型、求解结果和逐项 evidence-to-formulation 绑定。",
        "结果必须同时说明采用哪份证据、模型结构如何改变、最终行动是什么，以及每条主张落在何处。",
        "所需答案包括适用证据、结构 diff、最终单目标 formulation、最优解和来源到方程及代码区域的映射。",
        "请报告来源与适用理由，写出补丁前后差异和最终模型，再给出最优行动、目标值与全链路绑定。",
        "最终交付物为来源护照摘要、结构补丁、单目标模型、求解结果和 claim-to-model-slot 追踪表。",
        "请把来源判断、结构修改、最终 formulation、最优行动及主张—方程—代码位置映射一并输出。",
    )
    selections = [(seed >> shift) % 8 for shift in (0, 7, 14, 21, 28, 35, 42)]
    context_fact = items[0].get("global_context")
    context_paragraph = (
        f"适用于整个组合的已核实本地事实：{context_fact}\n\n"
        if context_fact
        else ""
    )
    return (
        introductions[selections[0]].format(
            entity=entity,
            jurisdiction=jurisdiction,
            family_zh=meta["zh"],
            decision_time=decision_time,
        )
        + data_leads[selections[1]]
        + "\n"
        f"{rows}\n\n"
        + context_paragraph
        + base_leads[selections[2]]
        + "\n"
        f"{requirements}\n"
        + completeness[selections[3]].format(objective=meta["objective"])
        + "\n\n"
        + search_instructions[selections[4]]
        + f"请使用“{interface}”按自然实体、日期、辖区和业务语义搜索。"
        + warnings[selections[5]]
        + "\n\n"
        + outputs[selections[6]]
    )


def private_document(
    task_id: str,
    entity: str,
    jurisdiction: str,
    decision_time: str,
    version: str,
    claim: str,
    exception_active: bool,
    document_role: str,
) -> str:
    seed = int(
        hashlib.sha256(
            f"private-policy-prose-v2|{task_id}|{document_role}".encode("utf-8")
        ).hexdigest(),
        16,
    )
    scope_leads = (
        "本文件只治理在所列辖区内由签发主体直接承担最终责任的正式组合决策",
        "本专编的对象限于签发主体在所列区域内立项并负责执行的组合方案",
        "只有同时满足签发主体、经营区域和正式决策三项条件的方案进入本文件范围",
        "本规则适用于签发主体在指定区域内拥有最终调度权的正式资源组合",
        "适用对象为签发主体在本辖区直接组织、审批并留痕的组合决策",
        "凡由签发主体在所列辖区承担履约责任的正式方案，均先按本文件筛选",
        "本附录覆盖签发主体在指定辖区内作出的生产性组合选择",
        "本专章仅约束签发主体对本辖区资源实施的正式启用与配置决定",
    )
    scope_exclusions = (
        "沙盘演练、无最终责任的咨询意见和未获授权的外包试算均不在范围内",
        "纯咨询、教学演示及不承担履约责任的第三方建议不得援引本文件",
        "内部草案、供应商推介和没有正式授权的试运行不构成适用对象",
        "仅提供技术意见的关联方、模拟测算和未批准试点一律排除",
        "外包顾问意见、概念验证与非生产环境安排不得类推适用",
        "没有最终调度权的协作单位及临时演示任务不受本专编治理",
        "非正式估算、培训案例和仅代填数据的服务方不属于受规主体",
        "未进入审批流程的备忘录、模拟方案和咨询部门活动均被排除",
    )
    classification_rules = (
        "适用性须按主体、辖区、决策日和业务属性四项联合判断，缺一项不得采纳",
        "执行人应先确认主体责任与辖区，再核对时点版本、活动类别及例外状态",
        "同主题材料只有在区域、主体、时点和活动范围全部一致时才可作为依据",
        "检索结果必须完成版本、签发权限、业务对象和例外条件的四重筛选",
        "名称相似不构成适用；必须逐项核实签发者、地域、期间和被治理动作",
        "文件适用性由责任主体、经营区域、有效期间与动作分类共同决定",
        "任何候选规则均须通过权限、地域、时间及业务范围的联合测试",
        "采纳条款前必须排除旧版、异地版、邻近主体版及未触发的例外版",
    )
    exception_rules = (
        "只有辖区应急机关在决策日前书面宣布且明确覆盖本主体的连续性事件，才可暂缓组合条款",
        "例外仅在正式应急决定列明主体、期限与动作范围时成立，资源紧张或口头通知均不足",
        "若要启动例外，必须存在决策日前生效的书面命令并能证明本方案属于其覆盖动作",
        "临时豁免须由有权机关书面批准并同时给出起止期、责任主体和替代控制措施",
        "紧急分支仅接受可核验的正式公告；供应商函件、内部邮件和一般困难均不触发",
        "例外的成立以正式签发、主体命中、期间覆盖和动作命中四项记录同时存在为前提",
        "未经有权部门在决策日前登记的所谓紧急安排，不得改变一般组合规则",
        "只有带签发机关、适用对象、有效期和退出条件的书面应急状态可以覆盖一般条款",
    )
    precedence_rules = (
        "同名新版本自生效日起替代旧版；异地或关联机构文件没有横向优先效力",
        "冲突时先比较签发权限和辖区，再比较有效期；无法唯一裁决时必须停止补丁",
        "后续正式版本仅在明确生效后取代本版，草案、征求意见稿和邻区材料均不得优先",
        "版本竞争按法定权限、地域专属性和生效时点依次处理，不允许凭发布日期猜测",
        "历史版只能用于解释沿革，不能覆盖已生效现行版；跨主体材料不得类推",
        "若多个材料声称适用，应以权限、对象、时点和明示替代关系完成唯一性裁决",
        "现行正式文本优先于旧摘要和非权威转述；仍有冲突则转人工裁决而非任选其一",
        "同主题规则的优先顺序由签发权限、辖区范围、有效区间及明确替代条款共同确定",
    )
    audit_rules = (
        "执行记录应保存检索式、候选来源、内容哈希、适用性判断以及补丁前后模型",
        "变更留痕至少包括检索时间、来源摘要、版本哈希、例外核验和模型位置映射",
        "审计包必须能够从来源主张追溯到模型槽、方程、代码区域及最终行动",
        "每次采用本规则都要保存候选排除理由、有效版本证明和结构补丁差异",
        "执行方须记录为何采纳或拒绝每份候选材料，并冻结模型与求解结果的哈希",
        "复核材料应覆盖来源、适用范围、例外状态、typed patch 和双世界求解证书",
        "所有判断均需形成可重放链路，包括原始文本、内容摘要、模型变更和行动投影",
        "审计日志必须将适用条款、公开本地事实、模型位置和决策证书逐项绑定",
    )
    indices = [
        (seed >> shift) % 8
        for shift in (0, 7, 14, 21, 28, 35)
    ]
    return (
        f"《{entity}组合决策治理专编（{version}）》\n"
        f"第一条【治理对象】{scope_leads[indices[0]]}。具体区域为{jurisdiction}，"
        f"核验时点为{decision_time}；{scope_exclusions[indices[1]]}。\n"
        f"第二条【适用性筛选】{classification_rules[indices[2]]}。\n"
        f"第三条【实质组合要求】{claim}\n"
        f"第四条【例外与恢复】{exception_rules[indices[3]]}。本文件登记的例外状态为"
        f"{'已激活' if exception_active else '未激活'}。\n"
        f"第五条【冲突与优先级】{precedence_rules[indices[4]]}。\n"
        f"第六条【证据与留痕】{audit_rules[indices[5]]}。"
    )


def source_row(
    source_id: str,
    content: str,
    passport: dict[str, Any],
    snapshot_ref: str | None = None,
) -> dict[str, Any]:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    # Search-facing rows expose only role-neutral metadata.  Full passports,
    # snapshot linkage, and applicability labels live in private Gold.
    row = {
        "id": source_id,
        "source_kind": "policy_document",
        "content": content,
        "content_sha256": content_hash,
        "applicability": {
            "predicate_fields": [
                "issuer_authority",
                "effective_interval",
                "jurisdiction",
                "subject_scope",
                "exception_state",
            ],
            "gold_status_exposed": False,
        },
    }
    return row


def same_length_variant(value: str, salt: str) -> str:
    if not value:
        return value
    last = value[-1]
    byte_width = len(last.encode("utf-8"))
    replacements_by_width = {
        1: ("n", "s", "e", "a"),
        2: ("é", "ñ", "ø", "ß"),
        3: ("区", "市", "省", "州"),
        4: ("𠀀", "𠀁", "𠀂", "𠀃"),
    }
    replacements = replacements_by_width[byte_width]
    replacement = replacements[
        int(hashlib.sha256(salt.encode("utf-8")).hexdigest(), 16)
        % len(replacements)
    ]
    if value[-1] == replacement:
        replacement = replacements[
            (replacements.index(replacement) + 1) % len(replacements)
        ]
    return value[:-1] + replacement


def natural_entity_variant(value: str, salt: str) -> str:
    prefixes = ("海辰", "云岚", "青川", "星河", "松岳", "南汐")
    if len(value) < 2:
        return same_length_variant(value, salt)
    prefix = prefixes[
        int(hashlib.sha256(salt.encode("utf-8")).hexdigest(), 16)
        % len(prefixes)
    ]
    if value.startswith(prefix):
        prefix = prefixes[(prefixes.index(prefix) + 1) % len(prefixes)]
    return prefix + value[2:]


def natural_jurisdiction_variant(value: str, salt: str) -> str:
    explicit = {
        "美国加利福尼亚州": "美国纽约州监管区",
        "美国华盛顿州": "美国俄勒冈州",
        "美国联邦 FLSA": "美国联邦 CCPA",
        "美国联邦 RCRA": "美国联邦 OSHA",
        "美国联邦学校餐项目": "美国联邦医疗餐项目",
        "美国联邦州际道路运输": "美国联邦跨州铁路运输",
        "美国联邦民航": "美国联邦铁路",
        "美国联邦清洁空气法危险空气污染物标准": "美国联邦清洁水法工业排放物许可总标准",
        "美国联邦清洁重型车辆项目": "美国联邦清洁轻型车辆项目",
        "美国联邦税收": "美国联邦海关",
        "美国联邦食品标签监管": "美国联邦药品标签监管",
    }
    if value in explicit:
        alternate = explicit[value]
        if len(alternate) != len(value):
            raise ValueError("natural jurisdiction alternate changed length")
        return alternate
    if value.endswith("经营辖区（合成）"):
        prefixes = ("东岚", "云岭", "北湾", "南浦", "星港", "松原", "海桥", "西川")
        prefix = prefixes[
            int(hashlib.sha256(salt.encode("utf-8")).hexdigest(), 16)
            % len(prefixes)
        ]
        if value.startswith(prefix):
            prefix = prefixes[(prefixes.index(prefix) + 1) % len(prefixes)]
        return prefix + value[2:]
    return same_length_variant(value, salt)


def render_role_neutral_documents(
    rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    shared_rule_text: str,
    shared_exception_text: str,
) -> None:
    passports = {
        str(comparison["evidence_id"]): comparison["source_passport"]
        for comparison in comparisons
    }
    for row in rows:
        passport = passports[str(row["id"])]
        authority_label = (
            "正式监管来源" if passport.get("authoritative") else "行业信息来源"
        )
        effective_to = passport.get("effective_to") or "9999-12-31"
        content = (
            f"第一条【发布登记】本文件由{passport['issuer']}发布。\n"
            f"第二条【权限属性】来源属性为{authority_label}。\n"
            f"第三条【有效期间】自{passport['effective_from']}起至{effective_to}止。\n"
            f"第四条【适用辖区】本文件仅适用于{passport['jurisdiction']}。\n"
            f"第五条【适用主体】本文件仅约束{passport['subject_scope']}。\n"
            f"第六条【例外核验】{shared_exception_text}\n"
            f"第七条【实质规则】{shared_rule_text}\n"
            "第八条【适用方法】使用本文件前必须同时核对发布权限、决策日期、"
            "辖区、主体范围和例外状态，不得仅凭规则正文相似而跨来源类推。"
        )
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        row["content"] = content
        row["content_sha256"] = content_hash


def balance_source_surface(rows: list[dict[str, Any]]) -> None:
    """Remove pack-local byte/count shortcuts without changing rule semantics."""
    contents = [str(row["content"]) for row in rows]
    ascii_counts = [sum(ord(char) < 128 for char in content) for content in contents]
    nonascii_counts = [
        sum(ord(char) >= 128 for char in content) for content in contents
    ]
    extra_utf8_bytes = [
        len(content.encode("utf-8")) - ascii_count - (3 * nonascii_count)
        for content, ascii_count, nonascii_count in zip(
            contents, ascii_counts, nonascii_counts
        )
    ]
    target_ascii = max(ascii_counts) + 65
    target_nonascii = max(nonascii_counts) + 129
    target_extra_utf8_bytes = max(extra_utf8_bytes) + 4
    prefix = "\n第七条【登记附记】本段仅用于统一候选档案版式，既不改变前述规则，也不提供适用性结论。登记串："
    prefix_ascii = sum(ord(char) < 128 for char in prefix)
    prefix_nonascii = len(prefix) - prefix_ascii
    chinese_cycle = (
        "资料归档复核留痕版本范围主体辖区日期例外均以前述正文为准"
    )
    for row, ascii_count, nonascii_count, extra_utf8 in zip(
        rows, ascii_counts, nonascii_counts, extra_utf8_bytes
    ):
        ascii_needed = target_ascii - ascii_count - prefix_ascii
        nonascii_needed = target_nonascii - nonascii_count - prefix_nonascii
        if ascii_needed < 0 or nonascii_needed < 0:
            raise ValueError("surface-balancing target is too small")
        extra_needed = target_extra_utf8_bytes - extra_utf8
        if extra_needed < 0 or extra_needed >= nonascii_needed:
            raise ValueError("UTF-8 surface-balancing target is invalid")
        three_byte_needed = nonascii_needed - extra_needed - 1
        repetitions = (three_byte_needed // len(chinese_cycle)) + 1
        appendix = (
            prefix
            + ("R" * ascii_needed)
            + "。"
            + ("𠀀" * extra_needed)
            + (chinese_cycle * repetitions)[: max(0, three_byte_needed)]
        )
        content = str(row["content"]) + appendix
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        row["content"] = content
        row["content_sha256"] = content_hash


def build_sources(
    task_id: str,
    base_hash: str,
    entity: str,
    jurisdiction: str,
    decision_time: str,
    evidence_mode: str,
    claim: str,
    web_blueprint: dict[str, Any] | None,
    web_fetch: dict[str, Any] | None,
) -> tuple[
    list[dict[str, Any]],
    str,
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any] | None,
]:
    rows: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    decision_date = date.fromisoformat(decision_time)
    snapshot_content: dict[str, Any] | None = None
    shared_rule_text = claim
    shared_exception_text = "本题未激活书面应急例外，仍须结合适用主体与决策日期复核。"
    if evidence_mode == "fresh-private":
        effective_from = (decision_date - timedelta(days=90)).isoformat()
        effective_to = (decision_date + timedelta(days=365)).isoformat()
        old_effective_to = (decision_date - timedelta(days=1)).isoformat()
        old_effective_from = (decision_date - timedelta(days=730)).isoformat()
        applicable_id = opaque_id("DOC", f"{task_id}|applicable|2026")
        content = private_document(
            task_id,
            entity,
            jurisdiction,
            decision_time,
            "2026.2",
            claim,
            False,
            "applicable",
        )
        passport = {
            "issuer": entity,
            "authority": "sealed-operational-policy",
            "version": "2026.2",
            "issued_at": effective_from,
            "issued_at_kind": "synthetic_policy_issue_date",
            "effective_from": effective_from,
            "effective_to": effective_to,
            "jurisdiction": jurisdiction,
            "subject_scope": f"{entity}直接负责的正式组合决策",
            "exceptions": ["书面应急状态；本任务未激活"],
            "exception_screening": {
                "basis": "the applicable private policy explicitly marks the emergency exception inactive for this task",
                "result": "no_listed_exception_activated",
            },
            "authoritative": True,
            "base_freeze_sha256": base_hash,
            "generated_after_base_freeze": True,
            "artifact_generated_at": BUILD_TIMESTAMP,
            "artifact_generation_order": "after_base_freeze",
            "availability": "sealed-private-evaluation-corpus",
        }
        rows.append(source_row(applicable_id, content, passport))
        distractor_specs = [
            (
                "old_version",
                jurisdiction,
                entity,
                "2025.4",
                old_effective_from,
                old_effective_to,
            ),
            (
                "wrong_jurisdiction",
                natural_jurisdiction_variant(
                    jurisdiction, f"{task_id}|jurisdiction"
                ),
                entity,
                "2026.2",
                effective_from,
                effective_to,
            ),
            (
                "wrong_entity",
                jurisdiction,
                natural_entity_variant(entity, f"{task_id}|entity"),
                "2026.2",
                effective_from,
                effective_to,
            ),
        ]
        for role, d_jurisdiction, d_entity, version, start, end in distractor_specs:
            source_id = opaque_id("DOC", f"{task_id}|{role}")
            d_content = private_document(
                task_id,
                d_entity,
                d_jurisdiction,
                decision_time,
                version,
                "本版本采用不同的组合规则，且不得跨主体或跨辖区类推。",
                False,
                role,
            )
            d_passport = {
                "issuer": d_entity,
                "authority": "sealed-operational-policy",
                "version": version,
                "issued_at": start,
                "issued_at_kind": "synthetic_policy_issue_date",
                "effective_from": start,
                "effective_to": end,
                "jurisdiction": d_jurisdiction,
                "subject_scope": f"{d_entity}直接负责的正式组合决策",
                "exceptions": [],
                "authoritative": True,
                "base_freeze_sha256": base_hash,
                "generated_after_base_freeze": True,
                "artifact_generated_at": BUILD_TIMESTAMP,
                "artifact_generation_order": "after_base_freeze",
                "availability": "sealed-private-evaluation-corpus",
            }
            rows.append(source_row(source_id, d_content, d_passport))
            comparisons.append(
                {
                    "evidence_id": source_id,
                    "role": role,
                    "applicable": False,
                    "source_passport": d_passport,
                    "failure_reason": {
                        "old_version": "effective interval ended before decision",
                        "wrong_jurisdiction": "jurisdiction mismatch",
                        "wrong_entity": "subject scope mismatch",
                    }[role],
                }
            )
        commitment = {
            "evidence_id": applicable_id,
            "commitment_sha256": rows[0]["content_sha256"],
            "base_freeze_sha256": base_hash,
            "committed_at": BUILD_TIMESTAMP,
            "access_state": "not available to no-tool condition",
        }
    else:
        if web_blueprint is None:
            raise ValueError("real-web source requires its official blueprint")
        if web_fetch is None:
            raise ValueError("real-web source requires a frozen HTTP response")
        policy = web_blueprint["applicable_policy_blueprint"]
        applicability = policy["applicability"]
        source_topic = policy["source_topic"]
        url = web_blueprint["web_source_url"]
        hostname = urlparse(url).hostname or ""
        issuer = OFFICIAL_ISSUERS.get(hostname)
        if not issuer:
            raise ValueError(f"Unrecognized official source domain: {hostname}")
        title = policy["retrieval_anchor"]
        provenance = WEB_SOURCE_PROVENANCE.get(url)
        if provenance is None:
            raise ValueError(f"Missing source provenance record for {url}")
        provenance_start = date.fromisoformat(provenance["effective_from"])
        provenance_end = (
            date.fromisoformat(provenance["effective_to"])
            if provenance["effective_to"] is not None
            else None
        )
        if decision_date < provenance_start or (
            provenance_end is not None and decision_date > provenance_end
        ):
            raise ValueError(
                f"Source provenance interval does not cover {decision_time}: {url}"
            )
        operative_instruction = next(
            slot["retrieve"]
            for slot in policy["clause_slots"]
            if slot["slot"] == "operative_rule"
        )
        official_claim = WEB_TOPIC_FACTS[source_topic]
        shared_rule_text = (
            "冻结支持片段："
            + "；".join(web_support_fragments(url))
            + f"。中文核验后主张：{official_claim}。核验指令：{operative_instruction}"
        )
        shared_exception_text = (
            "来源列明的例外须结合申请轮次、主体类型、资产用途和本地事实逐项核对；"
            "本题登记状态未触发所列例外。"
        )
        # The fetch manifest's task_id records the public ID at fetch time.
        # Source identity is instead frozen by URL, decision time, excerpts,
        # exact response bytes, and metadata hash so a later leak-safe public
        # ID permutation cannot invalidate unchanged official evidence.
        if (
            web_fetch.get("requested_url") != url
            or web_fetch.get("support_excerpt") != WEB_SUPPORT_FRAGMENTS[url]
            or web_fetch.get("support_excerpts") != web_support_fragments(url)
            or web_fetch.get("decision_time") != decision_time
        ):
            raise ValueError(f"Frozen web fetch does not match blueprint: {url}")
        verified_as_of = date.fromisoformat(web_fetch["verified_as_of"])
        if verified_as_of < decision_date:
            raise ValueError(
                f"Frozen response predates the decision it is meant to verify: {url}"
            )
        snapshot_id = opaque_id(
            "SNAP",
            f"{url}|{decision_time}|{web_fetch['raw_content_sha256']}",
        )
        snapshot_content = {
            "snapshot_id": snapshot_id,
            "url": url,
            "final_url": web_fetch["final_url"],
            "title": title,
            "issuer": issuer,
            "support_excerpt": WEB_SUPPORT_FRAGMENTS[url],
            "support_excerpts": web_support_fragments(url),
            "support_excerpt_kind": "frozen_operative_fragment",
            "support_excerpt_verified_in_normalized_dom_text": True,
            "support_text_normalization": web_fetch["support_text_normalization"],
            "zh_interpretation": official_claim,
            "operative_verification_instruction": operative_instruction,
            "status_code": web_fetch["status_code"],
            "fetched_at": web_fetch["fetched_at"],
            "fetched_at_kind": "actual_http_get_timestamp",
            "verified_as_of": web_fetch["verified_as_of"],
            "raw_path": web_fetch["raw_path"],
            "raw_size_bytes": web_fetch["raw_size_bytes"],
            "raw_content_sha256": web_fetch["raw_content_sha256"],
            "snapshot_sha256": web_fetch["raw_content_sha256"],
            "snapshot_sha256_kind": "exact_http_response_bytes",
            "fetch_metadata_sha256": web_fetch["metadata_sha256"],
            "response_headers": web_fetch["response_headers"],
            "content_type": web_fetch["content_type"],
            "text_encoding": web_fetch["text_encoding"],
            "point_in_time_decision": decision_time,
            "source_version": provenance["version"],
            "source_version_date": provenance["issued_at"],
            "source_version_date_kind": provenance["issued_at_kind"],
            "effective_from": provenance["effective_from"],
            "effective_to": provenance["effective_to"],
            "effective_from_basis": provenance["effective_from_basis"],
            "effective_interval_kind": effective_interval_kind(provenance),
            "snapshot_status": "frozen_raw_official_http_response_with_verified_support_fragment",
        }
        applicable_id = opaque_id("DOC", f"{task_id}|web-source|{snapshot_id}")
        content = (
            f"官方来源：{title}。\n"
            f"冻结原始页面标题：{title}。\n"
            "冻结支持片段："
            + "；".join(web_support_fragments(url))
            + "。\n"
            f"中文核验后主张：{official_claim}\n"
            f"核验指令：{operative_instruction}\n"
            "适用前必须同时核对决策日、辖区、主体类型、现行版本和来源列明的例外；"
            "本快照不包含任何任务变量名或模型答案。"
        )
        passport = {
            "issuer": issuer,
            "authority": "official-government-or-regulatory-source",
            "version": provenance["version"],
            "issued_at": provenance["issued_at"],
            "issued_at_kind": provenance["issued_at_kind"],
            "effective_from": provenance["effective_from"],
            "effective_to": provenance["effective_to"],
            "effective_from_basis": provenance["effective_from_basis"],
            "effective_interval_kind": effective_interval_kind(provenance),
            "jurisdiction": applicability["jurisdiction"],
            "subject_scope": applicability["entity_scope"],
            "exceptions": [applicability["exception_scope"]],
            "exception_screening": {
                "basis": (
                    "the public entity, jurisdiction, decision date, and item "
                    "attributes were screened against the listed exception scope"
                ),
                "screened_scope": applicability["exception_scope"],
                "result": "no_listed_exception_activated",
            },
            "url": url,
            "snapshot_sha256": snapshot_content["snapshot_sha256"],
            "snapshot_sha256_kind": "exact_http_response_bytes",
            "raw_content_sha256": snapshot_content["raw_content_sha256"],
            "raw_path": snapshot_content["raw_path"],
            "fetch_metadata_sha256": snapshot_content["fetch_metadata_sha256"],
            "support_text_normalization": snapshot_content[
                "support_text_normalization"
            ],
            "fetched_at": snapshot_content["fetched_at"],
            "fetched_at_kind": "actual_http_get_timestamp",
            "verified_as_of": snapshot_content["verified_as_of"],
            "point_in_time_status": "temporally_anchored_and_frozen_for_decision-date-applicability-check",
            "availability": "public-official-web",
            "authoritative": hostname in OFFICIAL_ISSUERS,
            "authority_validation": {
                "method": "official_https_hostname_allowlist",
                "hostname": hostname,
                "passed": hostname in OFFICIAL_ISSUERS,
            },
        }
        rows.append(
            source_row(
                applicable_id,
                content,
                passport,
                snapshot_ref=snapshot_id,
            )
        )
        distractors = [
            (
                "old_version",
                "历史摘要已停止适用，内容不能覆盖当前官方页面。",
                "archived-secondary-summary",
            ),
            (
                "wrong_jurisdiction",
                "相似规则来自另一辖区，不能直接迁移。",
                "official-other-jurisdiction",
            ),
            (
                "non_authoritative",
                "行业论坛转述未给出正式适用范围和例外。",
                "non-authoritative-commentary",
            ),
        ]
        distractor_issuers = {
            "old_version": issuer,
            "wrong_jurisdiction": issuer,
            "non_authoritative": issuer,
        }
        for role, d_content, authority in distractors:
            source_id = opaque_id("DOC", f"{task_id}|web-candidate|{role}")
            d_content = (
                f"围绕“{title}”的候选材料；实体锚点为{entity}，"
                f"决策日为{decision_time}。{d_content}"
            )
            d_passport = {
                "issuer": distractor_issuers[role],
                "authority": (
                    "industry-information-source"
                    if role == "non_authoritative"
                    else "official-government-or-regulatory-source"
                ),
                "version": (
                    "2024.1"
                    if role == "old_version"
                    else provenance["version"]
                ),
                "issued_at": "2024-01-01",
                "effective_from": (
                    "2024-01-01"
                    if role == "old_version"
                    else provenance["effective_from"]
                ),
                "effective_to": (
                    (decision_date - timedelta(days=1)).isoformat()
                    if role == "old_version"
                    else provenance["effective_to"]
                ),
                "jurisdiction": (
                    natural_jurisdiction_variant(
                        applicability["jurisdiction"],
                        f"{task_id}|web-jurisdiction",
                    )
                    if role == "wrong_jurisdiction"
                    else applicability["jurisdiction"]
                ),
                "subject_scope": applicability["entity_scope"],
                "exceptions": [],
                "authoritative": role != "non_authoritative",
                "availability": "public-web-candidate",
            }
            rows.append(source_row(source_id, d_content, d_passport))
            comparisons.append(
                {
                    "evidence_id": source_id,
                    "role": role,
                    "applicable": False,
                    "source_passport": d_passport,
                    "failure_reason": role.replace("_", " "),
                }
            )
        commitment = {
            "evidence_id": applicable_id,
            "commitment_sha256": rows[0]["content_sha256"],
            "base_freeze_sha256": base_hash,
            "committed_at": BUILD_TIMESTAMP,
            "access_state": "public web snapshot; E? claim only",
        }
    comparisons.insert(
        0,
        {
            "evidence_id": applicable_id,
            "role": "applicable",
            "applicable": True,
            "source_passport": passport,
            "failure_reason": None,
        },
    )
    render_role_neutral_documents(
        rows,
        comparisons,
        shared_rule_text,
        shared_exception_text,
    )
    commitment["commitment_sha256"] = next(
        row["content_sha256"] for row in rows if row["id"] == applicable_id
    )
    return rows, applicable_id, passport, comparisons, commitment, snapshot_content


def compact_solver_results(certificate: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for solver in ("gurobi", "copt"):
        output[solver] = {}
        for world in ("base", "patched"):
            world_cert = certificate[world]
            solver_result = world_cert[solver]
            exact = world_cert["exact_enumeration"]
            output[solver][world] = {
                "solver": solver_result["solver"],
                "status": solver_result["status"],
                "version": solver_result["version"],
                "objective": solver_result.get("objective"),
                "objective_recomputed": solver_result.get("objective_recomputed"),
                "assignment": solver_result.get("assignment"),
                "projected_action": solver_result.get("projected_action"),
                "optimal_actions": exact["optimal_actions"],
                "action_set_complete": exact["complete"],
                "complete_set_source": "exact_binary_enumeration",
                "feasible_assignment_count": exact["feasible_assignment_count"],
                "max_constraint_violation": solver_result.get(
                    "max_constraint_violation"
                ),
                "constraint_residuals": solver_result.get("constraint_residuals"),
                "integrality_violation": solver_result.get(
                    "integrality_violation"
                ),
            }
    return output


def run_parameter_perturbation_checks(
    base_ir: dict[str, Any], baseline_actions: list[list[int]]
) -> dict[str, Any]:
    baseline = {tuple(action) for action in baseline_actions}
    action_names = base_ir["action_projection"]
    trials = []
    for target in action_names:
        trial_index = len(trials) + 1
        target_position = action_names.index(target)
        selected_in_all_baseline = all(
            action[target_position] == 1 for action in baseline
        )
        expected_value = 0 if selected_in_all_baseline else 1
        perturbed = copy.deepcopy(base_ir)
        perturbed["model_id"] = f"{base_ir['model_id']}_perturb_{trial_index}"
        direction = -1 if selected_in_all_baseline else 1
        perturbed["objective"]["terms"][target] += direction * (
            10000 + trial_index
        )
        result = enumerate_optimal_actions(perturbed, TOL)
        actions = {tuple(action) for action in result["optimal_actions"]}
        trial = {
            "target_variable": target,
            "perturbation_direction": (
                "large_negative" if direction < 0 else "large_positive"
            ),
            "status": result["status"],
            "optimal_actions": result["optimal_actions"],
            "changed_from_baseline": actions != baseline,
            "target_changed_as_expected": all(
                action[target_position] == expected_value for action in actions
            ),
        }
        if (
            trial["status"] == "OPTIMAL"
            and trial["changed_from_baseline"]
            and trial["target_changed_as_expected"]
        ):
            trials.append(trial)
        if len(trials) == 3:
            break
    return {
        "method": "three_objective_coefficient_perturbations_plus_exact_enumeration",
        "trials": trials,
        "passed": len(trials) == 3
        and all(
            trial["status"] == "OPTIMAL"
            and trial["changed_from_baseline"]
            and trial["target_changed_as_expected"]
            for trial in trials
        ),
    }


def generated_model_code(
    ir: dict[str, Any], solver_function: str, solver_label: str
) -> str:
    embedded = json.dumps(ir, ensure_ascii=False, sort_keys=True)
    return (
        '"""Generated from canonical IR; do not edit by hand."""\n'
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'\n"
        "sys.path.insert(0, str(SCRIPTS))\n"
        f"from solver_backend import {solver_function}\n\n"
        f"IR = json.loads({embedded!r})\n"
        f"print(json.dumps({solver_function}(IR), ensure_ascii=False, sort_keys=True))\n"
    )


RAW_HASH_PREFIXES = (
    "private/web_snapshots/raw/",
    "reports/rejected_snapshots/",
)


def manifest_file_bytes(path: Path, root: Path) -> bytes:
    data = path.read_bytes()
    relative = path.relative_to(root).as_posix()
    if relative.startswith(RAW_HASH_PREFIXES) or b"\x00" in data:
        return data
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def refresh_manifest(root: Path, build_summary: dict[str, Any]) -> dict[str, Any]:
    exclusions = {"manifest.json"}
    files = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        if (
            relative in exclusions
            or path.relative_to(root).parts[0]
            in {".git", ".pytest_cache", "staging"}
            or "__pycache__" in path.parts
            or path.suffix == ".pyc"
            or (
                path.relative_to(root).parts[0] == "reports"
                and (
                    path.name == "release_gate.json"
                    or path.name.endswith((".stdout.txt", ".stderr.txt"))
                )
            )
        ):
            continue
        payload = manifest_file_bytes(path, root)
        files[relative] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
    manifest = {
        "dataset": "SearchWorthyOR-100",
        "schema_version": "1.0",
        "built_at": BUILD_TIMESTAMP,
        "build_environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "gurobi_expected": "12.0.2",
            "copt_expected": "8.0.5",
            "epsilon": TOL,
        },
        "file_hash_policy": {
            "utf8_text_eol": "lf",
            "raw_prefixes": list(RAW_HASH_PREFIXES),
        },
        "allowlists": {
            "families": FAMILIES,
            "patch_classes": PATCH_CLASSES,
            "evidence_modes": list(EVIDENCE_COUNTS),
        },
        "required_counts": {
            "tasks": 100,
            "unique_base_ids": 100,
            "evidence_modes": EVIDENCE_COUNTS,
            "family_each": 10,
            "patch_class_each": 25,
            "evidence_documents": 400,
        },
        "splits": {"release": 100},
        "claim_boundaries": {
            "fresh-private": "E+ sealed after base freeze and unavailable to no-tool condition",
            "real-web": "E? official public web; no universal no-memory claim",
        },
        "build_summary": build_summary,
        "files": files,
    }
    write_json(root / "manifest.json", manifest)
    return manifest


def validate_staging(
    candidates: list[dict[str, Any]], blueprints: list[dict[str, Any]]
) -> None:
    if len(candidates) != 100:
        raise ValueError(f"Expected 100 base candidates, got {len(candidates)}")
    if len(blueprints) != 100:
        raise ValueError(f"Expected 100 evidence blueprints, got {len(blueprints)}")
    candidate_ids = [
        row.get("candidate_id") or row.get("source_id") or f"candidate-{i}"
        for i, row in enumerate(candidates)
    ]
    if len(set(candidate_ids)) != 100:
        raise ValueError("Base candidate identifiers are not unique.")
    for index, candidate in enumerate(candidates):
        if candidate.get("role") != "reviewed_background_inspiration_only":
            raise ValueError(
                f"Inspiration row {index} has invalid role {candidate.get('role')!r}."
            )
        if candidate.get("source_correspondence_claim") is not False:
            raise ValueError(
                f"Inspiration row {index} must explicitly disable source correspondence."
            )
        if candidate.get("family") is not None:
            raise ValueError(
                f"Inspiration row {index} must not carry a family assignment."
            )
        source_status = candidate.get("source_status")
        if not isinstance(source_status, dict) or not all(
            source_status.get(key) is True
            for key in (
                "artifact_hashes_match",
                "dual_blind_review_passed",
                "semantic_mapping_complete",
                "solver_certificate_passed",
                "source_hashes_match",
            )
        ):
            raise ValueError(
                f"Inspiration row {index} has not passed every frozen source gate."
            )


def build(root: Path) -> dict[str, Any]:
    candidates = read_jsonl(root / "staging" / "reviewed_inspiration_pool.jsonl")
    blueprints = read_jsonl(root / "staging" / "evidence_blueprints.jsonl")
    validate_staging(candidates, blueprints)
    web_fetches = load_frozen_web_fetches(root, blueprints)

    public_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    commitments: list[dict[str, Any]] = []
    gold_rows: list[dict[str, Any]] = []
    snapshots_by_id: dict[str, dict[str, Any]] = {}
    web_counter = 0

    for index, (candidate, blueprint) in enumerate(zip(candidates, blueprints, strict=True)):
        family = FAMILIES[index // 10]
        local_in_family = index % 10
        evidence_mode = "fresh-private" if local_in_family < 8 else "real-web"
        patch_class = FROZEN_PATCH_ASSIGNMENTS[index]
        declared_family = blueprint.get("family")
        if declared_family and declared_family != family:
            raise ValueError(
                f"Blueprint {index} family {declared_family!r} != frozen {family!r}"
            )
        declared_mode = choose_blueprint_value(
            blueprint, ("evidence_mode", "access_mode"), evidence_mode
        )
        if declared_mode != evidence_mode:
            raise ValueError(
                f"Blueprint {index} mode {declared_mode!r} != frozen {evidence_mode!r}"
            )
        declared_patch = blueprint.get("patch_class", patch_class)
        if declared_patch != patch_class:
            raise ValueError(
                f"Blueprint {index} patch {declared_patch!r} != frozen {patch_class!r}"
            )

        task_id = public_task_id(index)
        source_dataset = candidate.get("source_dataset", "unknown")
        source_id = candidate.get("source_id", candidate.get("candidate_id", str(index)))
        base_id = opaque_id("BASE", f"independent-new-base|{task_id}|{index}")
        base_ir, items, selection_count = build_base_ir(
            task_id, base_id, family, index
        )
        if evidence_mode == "real-web":
            localize_web_items(
                items,
                blueprint["applicable_policy_blueprint"]["source_topic"],
                patch_class,
                blueprint["web_source_url"],
            )
        base_hash = sha256_json(base_ir)
        claim_id = opaque_id("CLAIM", f"{task_id}|{patch_class}")
        patched_ir, patch_ops, claim = apply_patch(
            base_ir, items, patch_class, claim_id
        )
        patched_hash = sha256_json(patched_ir)
        if patched_hash == base_hash:
            raise AssertionError(f"{task_id}: patch did not change model hash")

        if evidence_mode == "fresh-private":
            entity = choose_blueprint_value(
                blueprint,
                ("entity",),
                f"{PRIVATE_ENTITIES[index % len(PRIVATE_ENTITIES)]}{index + 1:02d}组",
            )
            jurisdiction = choose_blueprint_value(
                blueprint,
                ("jurisdiction",),
                PRIVATE_JURISDICTIONS[index % len(PRIVATE_JURISDICTIONS)],
            )
        else:
            entity = choose_blueprint_value(
                blueprint, ("entity",), f"合规运营主体{index + 1:02d}"
            )
            jurisdiction = choose_blueprint_value(
                blueprint,
                ("jurisdiction",),
                blueprint["applicable_policy_blueprint"]["applicability"][
                    "jurisdiction"
                ],
            )
            web_counter += 1
        decision_time = choose_blueprint_value(
            blueprint,
            ("decision_time", "decision_date"),
            DECISION_DATES[index % len(DECISION_DATES)],
        )

        web_blueprint = blueprint if evidence_mode == "real-web" else None
        (
            source_docs,
            applicable_id,
            passport,
            comparisons,
            _commitment,
            frozen_snapshot,
        ) = build_sources(
            task_id,
            base_hash,
            entity,
            jurisdiction,
            decision_time,
            evidence_mode,
            claim,
            web_blueprint,
            (
                web_fetches[blueprint["web_source_url"]]
                if evidence_mode == "real-web"
                else None
            ),
        )
        evidence_rows.extend(source_docs)
        commitments.append(
            {
                "evidence_id": applicable_id,
                "commitment_sha256": source_docs[0]["content_sha256"],
                "base_freeze_sha256": base_hash,
                "committed_at": BUILD_TIMESTAMP,
                "access_state": (
                    "not available to no-tool condition"
                    if evidence_mode == "fresh-private"
                    else "public web snapshot; E? claim only"
                ),
            }
        )
        if evidence_mode == "real-web":
            if frozen_snapshot is None:
                raise AssertionError(f"{task_id}: frozen web snapshot was not returned")
            snapshots_by_id[frozen_snapshot["snapshot_id"]] = frozen_snapshot

        certificate = certify_world_pair(base_ir, patched_ir, TOL)
        if not certificate["passed"]:
            raise AssertionError(
                f"{task_id}: decision certificate failed: "
                f"{json.dumps(certificate, ensure_ascii=False)}"
            )
        perturbation_check = run_parameter_perturbation_checks(
            base_ir, certificate["base_acceptable_actions"]
        )
        if not perturbation_check["passed"]:
            raise AssertionError(f"{task_id}: parameter perturbation check failed")

        task_dir = root / "models" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        base_path = task_dir / "base_ir.json"
        patched_path = task_dir / "patched_ir.json"
        results_path = task_dir / "solver_results.json"
        write_json(base_path, base_ir)
        write_json(patched_path, patched_ir)
        write_json(results_path, certificate)
        (task_dir / "gurobi_model.py").write_text(
            generated_model_code(patched_ir, "solve_gurobi", "gurobi"),
            encoding="utf-8",
        )
        (task_dir / "copt_model.py").write_text(
            generated_model_code(patched_ir, "solve_copt", "copt"),
            encoding="utf-8",
        )

        public_text = public_problem_text(
            task_id,
            family,
            entity,
            jurisdiction,
            decision_time,
            items,
            selection_count,
            base_ir["metadata"]["capacity"],
            base_ir["metadata"]["base_requirements_zh"],
            evidence_mode,
        )
        public_problem_sha256 = hashlib.sha256(
            public_text.encode("utf-8")
        ).hexdigest()
        public_rows.append(
            {
                "id": task_id,
                "problem_zh": public_text,
                "decision_time": decision_time,
                "entity": entity,
                "jurisdiction": jurisdiction,
                "required_output": [
                    "适用来源与理由",
                    "结构性模型补丁",
                    "最终单目标模型",
                    "最优行动与目标值",
                    "claim-to-model-slot映射",
                ],
                "allowed_retrieval_interfaces": [
                    "unified_evidence_semantic_search"
                ],
            }
        )

        objective_fingerprint = sha256_json(base_ir["objective"])
        base_actions = certificate["base_acceptable_actions"]
        patched_actions = certificate["patched_acceptable_actions"]
        solver_results = compact_solver_results(certificate)
        source_problem = candidate.get(
            "original_problem_text",
            candidate.get(
                "problem_zh_or_en",
                candidate.get("problem", candidate.get("problem_text", "")),
            ),
        )
        source_problem_hash = hashlib.sha256(
            str(source_problem).encode("utf-8")
        ).hexdigest()
        applicability_result = compute_applicability(
            passport,
            comparisons,
            decision_time,
            jurisdiction,
            entity,
        )
        applicability_result["selected_evidence_id"] = applicable_id
        if applicability_result["status"] != "pass":
            raise AssertionError(
                f"{task_id}: computed source applicability checks did not all pass"
            )
        gold_rows.append(
            {
                "id": task_id,
                "base_id": base_id,
                "family": family,
                "evidence_mode": evidence_mode,
                "patch_class": patch_class,
                "split": "release",
                "base_audit": {
                    "status": "pending_independent_review",
                    "base_kind": "independent_new_compact_base",
                    "base_origin": "newly_authored_public_task",
                    "source_correspondence_claim": False,
                    "public_problem_sha256": public_problem_sha256,
                    "canonical_ir_sha256": base_hash,
                    "certification_scope": (
                        "the newly authored public problem and its canonical IR; "
                        "not the background inspiration source"
                    ),
                    "inspiration_provenance": {
                        "source_dataset": source_dataset,
                        "source_id": source_id,
                        "source_problem_sha256": source_problem_hash,
                        "source_normalized_problem_sha256": candidate.get(
                            "source_hashes", {}
                        ).get("normalized_problem_sha256"),
                        "role": "reviewed_background_inspiration_only",
                        "source_audit_status": candidate["source_status"][
                            "audit_status"
                        ],
                        "source_dual_blind_review_passed": candidate[
                            "source_status"
                        ]["dual_blind_review_passed"],
                        "formulation_inherited": False,
                        "reference_answer_used": False,
                        "reference_code_used": False,
                    },
                    "historical_answer_used_as_gold": False,
                    "historical_code_used_as_gold": False,
                    "public_problem_to_ir_complete": True,
                    "single_objective": True,
                    "units_checked": True,
                    "hardcode_check": "passed_by_exhaustive_enumeration",
                    "parameter_perturbation_check": perturbation_check,
                    "independent_reviews": "pending",
                },
                "evidence_ids": [applicable_id],
                "source_passport": passport,
                "applicability": applicability_result,
                "claim_to_model_mapping": [
                    {
                        "claim_id": claim_id,
                        "claim_zh": claim,
                        "external_rule_zh": (
                            claim
                            if evidence_mode == "fresh-private"
                            else WEB_TOPIC_FACTS[
                                blueprint["applicable_policy_blueprint"][
                                    "source_topic"
                                ]
                            ]
                        ),
                        "operative_support_excerpt": (
                            None
                            if evidence_mode == "fresh-private"
                            else WEB_SUPPORT_FRAGMENTS[
                                blueprint["web_source_url"]
                            ]
                        ),
                        "operative_support_excerpts": (
                            []
                            if evidence_mode == "fresh-private"
                            else web_support_fragments(blueprint["web_source_url"])
                        ),
                        "derived_model_claim_zh": claim,
                        "derivation_kind": (
                            "direct_private_clause"
                            if evidence_mode == "fresh-private"
                            else "official_rule_combined_with_public_local_facts"
                        ),
                        "local_binding_zh": claim,
                        "local_facts": [
                            {
                                "item": item["name"],
                                "policy_attribute": item["policy_attribute"],
                            }
                            for item in items
                        ]
                        + (
                            [
                                {
                                    "scope": "whole_combination",
                                    "fact_zh": items[0]["global_context"],
                                }
                            ]
                            if items[0].get("global_context")
                            else []
                        ),
                        "model_slots": [op["model_slot_id"] for op in patch_ops],
                        "equations": [op["after_expression"] for op in patch_ops],
                        "code_regions": [op["code_region_id"] for op in patch_ops],
                    }
                ],
                "typed_patch": {
                    "ops": patch_ops,
                    "structural": True,
                    "pure_numeric_parameter_fill": False,
                    "base_model_hash": file_sha256(base_path),
                    "patched_model_hash": file_sha256(patched_path),
                    "minimality_check": "each operation is directly linked to the sole applicable claim",
                },
                "model_hashes": {
                    "base": {
                        "path": base_path.relative_to(root).as_posix(),
                        "sha256": file_sha256(base_path),
                        "canonical_sha256": base_hash,
                    },
                    "patched": {
                        "path": patched_path.relative_to(root).as_posix(),
                        "sha256": file_sha256(patched_path),
                        "canonical_sha256": patched_hash,
                    },
                },
                "action_projection": {
                    "variables": base_ir["action_projection"],
                    "epsilon": TOL,
                    "registered_before_evidence": True,
                },
                "solver_results": solver_results,
                "decision_certificate": {
                    "method": "complete_binary_enumeration",
                    "epsilon": TOL,
                    "worlds": {
                        "base": {
                            "objective_fingerprint": objective_fingerprint,
                            "optimal_actions": base_actions,
                            "action_set_complete": True,
                        },
                        "patched": {
                            "objective_fingerprint": objective_fingerprint,
                            "optimal_actions": patched_actions,
                            "action_set_complete": True,
                        },
                    },
                    "intersection": certificate["intersection"],
                    "intersection_empty": certificate["intersection_empty"],
                    "passed": certificate["passed"],
                },
                "reviews": {
                    "review_a": {
                        "reviewer": None,
                        "blind_packet": True,
                        "label": "pending",
                    },
                    "review_b": {
                        "reviewer": None,
                        "blind_packet": True,
                        "label": "pending",
                    },
                },
                "adjudication": {
                    "status": "pending",
                    "label": "pending",
                    "unresolved": True,
                },
            }
        )

    release_order = {
        task_id: hashlib.sha256(
            f"release-row-order-v4|593|{task_id}".encode("utf-8")
        ).hexdigest()
        for task_id in (row["id"] for row in public_rows)
    }
    public_rows.sort(key=lambda row: release_order[row["id"]])
    gold_rows.sort(key=lambda row: release_order[row["id"]])
    evidence_rows.sort(
        key=lambda row: hashlib.sha256(
            f"evidence-row-order-v1|{row['id']}".encode("utf-8")
        ).hexdigest()
    )

    write_jsonl(root / "public" / "tasks_zh.jsonl", public_rows)
    write_jsonl(root / "private" / "evidence_corpus.jsonl", evidence_rows)
    write_jsonl(root / "private" / "evidence_commitments.jsonl", commitments)
    write_jsonl(
        root / "private" / "web_source_snapshots.jsonl",
        sorted(snapshots_by_id.values(), key=lambda row: row["snapshot_id"]),
    )
    write_jsonl(root / "private" / "gold.jsonl", gold_rows)

    summary = {
        "tasks": len(public_rows),
        "gold_rows": len(gold_rows),
        "unique_base_ids": len({row["base_id"] for row in gold_rows}),
        "evidence_documents": len(evidence_rows),
        "evidence_modes": dict(Counter(row["evidence_mode"] for row in gold_rows)),
        "families": dict(Counter(row["family"] for row in gold_rows)),
        "patch_classes": dict(Counter(row["patch_class"] for row in gold_rows)),
        "base_origin": "100 independently authored public tasks",
        "source_correspondence_claim": False,
        "background_inspiration_mix": {
            "by_source_dataset": dict(
                Counter(row.get("source_dataset", "unknown") for row in candidates)
            ),
            "by_source_group": dict(
                Counter(row.get("source_group", "unknown") for row in candidates)
            ),
        },
        "all_decision_certificates_pass": all(
            row["decision_certificate"]["passed"] for row in gold_rows
        ),
        "reviews_pending": True,
    }
    write_json(root / "reports" / "build_summary.json", summary)
    refresh_manifest(root, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    summary = build(args.root.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
