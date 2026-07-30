"""Certify NLP4LP and MAMO supplemental bases from problem text only.

The benchmark answer is loaded only after the formulation has been fixed and
solved.  It is reported as a comparison field and is never used to change the
model.  Benchmark code/formulation fields are deliberately not read.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


DATASET_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = DATASET_ROOT.parents[1]
STAGING_ROOT = DATASET_ROOT / "staging"
OUTPUT_ROOT = STAGING_ROOT / "certified_sources" / "supplemental"
AUDIT_PATH = STAGING_ROOT / "supplemental_base_audit.jsonl"
SUMMARY_PATH = STAGING_ROOT / "supplemental_base_audit_summary.json"
MANIFEST_PATH = STAGING_ROOT / "supplemental_certification_manifest.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from solver_backend import (  # noqa: E402
    inspect_assignment,
    objective_value,
    sha256_json,
    solve_copt,
    solve_gurobi,
)


TOL = 1e-6
INF = 1_000_000_000.0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_source_sha256(text: str) -> str:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def var(
    name: str,
    semantic_name: str,
    vartype: str,
    ub: float | None,
    unit: str,
    source_claim: str,
    lb: float = 0.0,
) -> dict[str, Any]:
    return {
        "name": name,
        "semantic_name": semantic_name,
        "vartype": vartype,
        "lb": lb,
        "ub": ub,
        "unit": unit,
        "source_claim": source_claim,
        "domain_expression": (
            f"{name} >= {lb}, {vartype}"
            if ub is None
            else (
                f"{lb} <= {name} <= {ub}, {vartype}"
                if vartype != "B"
                else f"{name} in {{0,1}}"
            )
        ),
    }


def con(
    name: str,
    terms: dict[str, float],
    sense: str,
    rhs: float,
    requirement: str,
    source_claim: str,
    unit: str,
) -> dict[str, Any]:
    expression = " + ".join(f"{coef:g}*{key}" for key, coef in terms.items())
    return {
        "name": name,
        "terms": terms,
        "sense": sense,
        "rhs": rhs,
        "expression": f"{expression} {sense} {rhs:g}",
        "requirement": requirement,
        "source_claim": source_claim,
        "unit": unit,
        "source": "problem_text",
    }


def make_spec(
    source_id: str,
    *,
    variables: list[dict[str, Any]],
    sense: str,
    objective_terms: dict[str, float],
    objective_name: str,
    objective_unit: str,
    objective_claim: str,
    constraints: list[dict[str, Any]],
    parameters: dict[str, Any],
    sets: dict[str, Any] | None = None,
    interpretation: list[str] | None = None,
    semantic_risks: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "variables": variables,
        "sense": sense,
        "objective": {
            "name": objective_name,
            "terms": objective_terms,
            "constant": 0.0,
            "unit": objective_unit,
            "source_claim": objective_claim,
        },
        "constraints": constraints,
        "parameters": parameters,
        "sets": sets or {},
        "interpretation": interpretation or [],
        "semantic_risks": semantic_risks or [],
    }


def two_var_spec(
    source_id: str,
    *,
    x: tuple[str, str, str, float, str, str],
    y: tuple[str, str, str, float, str, str],
    sense: str,
    objective: tuple[float, float, str, str, str],
    constraints: list[dict[str, Any]],
    parameters: dict[str, Any],
    interpretation: list[str] | None = None,
    semantic_risks: list[str] | None = None,
) -> dict[str, Any]:
    return make_spec(
        source_id,
        variables=[var(*x), var(*y)],
        sense=sense,
        objective_terms={x[0]: objective[0], y[0]: objective[1]},
        objective_name=objective[2],
        objective_unit=objective[3],
        objective_claim=objective[4],
        constraints=constraints,
        parameters=parameters,
        sets={"decision_categories": [x[1], y[1]]},
        interpretation=interpretation,
        semantic_risks=semantic_risks,
    )


def supplemental_specs() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}

    specs["nlp4lp_000001"] = two_var_spec(
        "nlp4lp_000001",
        x=("top", "top-loading machines", "I", 140, "machine", "buy two types of washing machines"),
        y=("front", "front-loading machines", "I", 100, "machine", "buy two types of washing machines"),
        sense="min",
        objective=(1, 1, "minimize_machine_count", "machine", "minimize the total number of washing machines"),
        constraints=[
            con("wash_floor", {"top": 50, "front": 75}, ">=", 5000, "wash at least 5000 items/day", "must be able to wash at least 5000 items per day", "item/day"),
            con("energy_cap", {"top": 85, "front": 100}, "<=", 7000, "use at most 7000 kWh/day", "has available 7000 kWh per day", "kWh/day"),
            con("top_share", {"top": 0.6, "front": -0.4}, "<=", 0, "top-loading share at most 40%", "at most 40% of the machines can be top-loading", "machine"),
            con("front_floor", {"front": 1}, ">=", 10, "at least 10 front-loading machines", "at least 10 machines should be front-loading", "machine"),
        ],
        parameters={"wash_rate": [50, 75], "energy": [85, 100], "wash_floor": 5000, "energy_cap": 7000, "top_share_cap": 0.4, "front_floor": 10},
        interpretation=["Machine counts are integer because the requested decisions are numbers of machines."],
    )

    specs["nlp4lp_000008"] = two_var_spec(
        "nlp4lp_000008",
        x=("seasonal", "seasonal snow removers", "I", 60, "worker", "employs seasonal and permanent snow removers"),
        y=("permanent", "permanent snow removers", "I", 30, "worker", "employs seasonal and permanent snow removers"),
        sense="min",
        objective=(1, 1, "minimize_workers", "worker", "minimize the total number of snow removers"),
        constraints=[
            con("labor_floor", {"seasonal": 6, "permanent": 10}, ">=", 300, "provide 300 labor-hours", "needs 300 hours of snow remover labor", "hour"),
            con("budget_cap", {"seasonal": 120, "permanent": 250}, "<=", 6500, "stay within budget", "has a budget of $6500", "USD"),
        ],
        parameters={"shift_hours": [6, 10], "wage": [120, 250], "labor_floor": 300, "budget": 6500},
        interpretation=["Worker counts are integer."],
    )

    specs["nlp4lp_000015"] = two_var_spec(
        "nlp4lp_000015",
        x=("desk", "desks", "I", 100, "item", "makes desks and drawers"),
        y=("drawer", "drawers", "I", 134, "item", "makes desks and drawers"),
        sense="max",
        objective=(100, 90, "maximize_profit", "USD", "profit per desk is $100 and the profit per drawer is $90"),
        constraints=[
            con("assembly_cap", {"desk": 40, "drawer": 30}, "<=", 4000, "assembly time limit", "4000 minutes for assembly", "minute"),
            con("sanding_cap", {"desk": 20, "drawer": 10}, "<=", 3500, "sanding time limit", "3500 minutes for sanding", "minute"),
        ],
        parameters={"assembly_minutes": [40, 30], "sanding_minutes": [20, 10], "capacities": [4000, 3500], "profit": [100, 90]},
        interpretation=["Finished product counts are integer."],
    )

    specs["nlp4lp_000023"] = two_var_spec(
        "nlp4lp_000023",
        x=("large", "large pills", "I", 334, "pill", "make two pills, a large pill and a small pill"),
        y=("small", "small pills", "I", 500, "pill", "make two pills, a large pill and a small pill"),
        sense="min",
        objective=(2, 1, "minimize_filler", "filler_unit", "minimize the total number of filler material needed"),
        constraints=[
            con("ingredient_cap", {"large": 3, "small": 2}, "<=", 1000, "medicinal ingredient capacity", "has 1000 units of medicinal ingredients", "ingredient_unit"),
            con("large_floor", {"large": 1}, ">=", 100, "make at least 100 large pills", "at least 100 large pills", "pill"),
            con("small_share", {"small": 0.4, "large": -0.6}, ">=", 0, "small pills at least 60%", "at least 60% of the total number of pills must be small", "pill"),
        ],
        parameters={"ingredient": [3, 2], "filler": [2, 1], "ingredient_cap": 1000, "large_floor": 100, "small_share_floor": 0.6},
        interpretation=["Pill counts are integer."],
    )

    specs["nlp4lp_000030"] = two_var_spec(
        "nlp4lp_000030",
        x=("small", "small suitcases", "I", 70, "suitcase", "small and large suitcases"),
        y=("large", "large suitcases", "I", 50, "suitcase", "small and large suitcases"),
        sense="max",
        objective=(50, 80, "maximize_snacks", "snack", "maximize the total number of snacks that can be delivered"),
        constraints=[
            con("small_ratio", {"small": 1, "large": -2}, ">=", 0, "small suitcases at least twice large", "at least twice as many small suitcases", "suitcase"),
            con("total_cap", {"small": 1, "large": 1}, "<=", 70, "at most 70 suitcases total", "at most 70 suitcases in total", "suitcase"),
            con("large_floor", {"large": 1}, ">=", 15, "at least 15 large suitcases", "at least 15 large suitcases", "suitcase"),
        ],
        parameters={"capacity": [50, 80], "small_cap": 70, "large_cap": 50, "total_cap": 70, "large_floor": 15},
        interpretation=["Suitcase counts are integer; the stated individual upper bounds are variable bounds."],
    )

    specs["nlp4lp_000037"] = two_var_spec(
        "nlp4lp_000037",
        x=("plane", "cargo-plane trips", "I", 22, "trip", "either by cargo planes or ultrawide trucks"),
        y=("truck", "ultrawide-truck trips", "I", 34, "trip", "either by cargo planes or ultrawide trucks"),
        sense="min",
        objective=(1, 1, "minimize_trips", "trip", "minimize the total number of trips"),
        constraints=[
            con("tire_floor", {"plane": 10, "truck": 6}, ">=", 200, "transport at least 200 tires", "needs to transport at least 200 tires", "tire"),
            con("cost_cap", {"plane": 1000, "truck": 700}, "<=", 22000, "stay within budget", "has available $22000", "USD"),
            con("plane_not_more", {"plane": 1, "truck": -1}, "<=", 0, "plane trips cannot exceed truck trips", "plane trips cannot exceed the number of ultrawide truck trips", "trip"),
        ],
        parameters={"tire_capacity": [10, 6], "trip_cost": [1000, 700], "tire_floor": 200, "budget": 22000},
        interpretation=["Trip counts are integer."],
    )

    specs["nlp4lp_000046"] = two_var_spec(
        "nlp4lp_000046",
        x=("large", "large mobile production units", "I", None, "vehicle", "large mobile production units"),
        y=("small", "small mobile production units", "I", None, "vehicle", "small mobile production units"),
        sense="min",
        objective=(2, 1, "minimize_parking_spots", "parking_spot", "minimize the total number of parking spots"),
        constraints=[
            con("people_floor", {"large": 6, "small": 2}, ">=", 80, "transport 80 people", "needs to transport 80 people", "person"),
            con("small_floor", {"small": 1}, ">=", 5, "use at least 5 small units", "at least 5 units must be small mobile units", "vehicle"),
            con("large_share", {"large": 0.25, "small": -0.75}, ">=", 0, "large units at least 75% of vehicles", "must make up at least 75% of all vehicles", "vehicle"),
        ],
        parameters={"people": [6, 2], "parking": [2, 1], "people_floor": 80, "small_floor": 5, "large_share_floor": 0.75},
        interpretation=["Vehicle counts are integer."],
    )

    specs["nlp4lp_000055"] = two_var_spec(
        "nlp4lp_000055",
        x=("a_hours", "hours using method A", "C", 100, "hour", "Method A produces ... per hour"),
        y=("b_hours", "hours using method B", "C", 100, "hour", "Method B produces ... per hour"),
        sense="min",
        objective=(1, 1, "minimize_time", "hour", "minimize the total time needed"),
        constraints=[
            con("fabric_floor", {"a_hours": 25, "b_hours": 45}, ">=", 1400, "fabric production floor", "at least 1400 units of fabric", "fabric_unit"),
            con("plastic_floor", {"a_hours": 14, "b_hours": 25}, ">=", 1000, "plastic production floor", "at least 1000 units of plastic", "plastic_unit"),
            con("element_cap", {"a_hours": 60, "b_hours": 65}, "<=", 3500, "special-element limit", "available 3500 units of the special element", "element_unit"),
        ],
        parameters={"output_fabric": [25, 45], "output_plastic": [14, 25], "element": [60, 65], "floors": [1400, 1000], "element_cap": 3500},
        interpretation=["Variables are operating hours because outputs are specified per hour."],
    )

    specs["nlp4lp_000062"] = {
        "source_id": "nlp4lp_000062",
        "reject": True,
        "reject_reason": "vacuous_zero_solution_missing_required_experiment_count",
        "details": "All stated constraints are upper bounds and the objective minimizes nonnegative radiation. Scheduling zero experiments is feasible and optimal; the text supplies no experimental workload or lower bound.",
        "partial_mapping": {
            "variables": ["number of in-vivo experiments", "number of ex-vivo experiments"],
            "objective": "minimize 2*in_vivo + 3*ex_vivo radiation units",
            "constraints": ["30*in_vivo + 45*ex_vivo <= 400", "60*in_vivo + 30*ex_vivo <= 500"],
        },
    }

    specs["nlp4lp_000070"] = two_var_spec(
        "nlp4lp_000070",
        x=("small", "small crates", "I", 100, "crate", "small crates"),
        y=("large", "large crates", "I", 50, "crate", "large crates"),
        sense="max",
        objective=(200, 500, "maximize_grapes", "grape", "maximize the total number of grapes"),
        constraints=[
            con("small_ratio", {"small": 1, "large": -3}, ">=", 0, "small crates at least three times large", "at least 3 times as many small crates", "crate"),
            con("total_cap", {"small": 1, "large": 1}, "<=", 60, "truck holds at most 60 crates", "truck can take at most 60 crates total", "crate"),
            con("large_floor", {"large": 1}, ">=", 10, "use at least 10 large crates", "must use at least 10 large crates", "crate"),
        ],
        parameters={"capacity": [200, 500], "individual_caps": [100, 50], "total_cap": 60, "large_floor": 10},
        interpretation=["Crate counts are integer; individual availability is encoded in bounds."],
    )

    specs["nlp4lp_000077"] = two_var_spec(
        "nlp4lp_000077",
        x=("otter", "otter performers", "I", 66, "performer", "shows using otters and dolphins"),
        y=("dolphin", "dolphin performers", "I", 40, "performer", "shows using otters and dolphins"),
        sense="max",
        objective=(3, 1, "maximize_tricks", "trick", "maximize the total number of tricks"),
        constraints=[
            con("treat_cap", {"otter": 3, "dolphin": 5}, "<=", 200, "treat availability", "only has 200 treats available", "treat"),
            con("dolphin_floor", {"dolphin": 1}, ">=", 10, "at least 10 dolphins", "at least 10 dolphins must be used", "performer"),
            con("otter_share", {"otter": 0.7, "dolphin": -0.3}, "<=", 0, "otters at most 30% of performers", "at most 30% of the performers can be otters", "performer"),
        ],
        parameters={"tricks": [3, 1], "treats": [3, 5], "treat_cap": 200, "dolphin_floor": 10, "otter_share_cap": 0.3},
        interpretation=["Performer counts are integer."],
    )

    specs["nlp4lp_000085"] = two_var_spec(
        "nlp4lp_000085",
        x=("dine_in", "dine-in stores", "I", 10, "store", "open two types of stores"),
        y=("food_truck", "food trucks", "I", 12, "store", "open two types of stores"),
        sense="min",
        objective=(1, 1, "minimize_stores", "store", "minimize the total number of stores"),
        constraints=[
            con("sandwich_floor", {"dine_in": 100, "food_truck": 50}, ">=", 500, "make at least 500 sandwiches/day", "must make at least 500 sandwiches per day", "sandwich/day"),
            con("employee_cap", {"dine_in": 8, "food_truck": 3}, "<=", 35, "employee availability", "only have available 35 employees", "employee"),
        ],
        parameters={"sandwich_capacity": [100, 50], "employees": [8, 3], "sandwich_floor": 500, "employee_cap": 35},
        interpretation=["Store counts are integer."],
    )

    specs["nlp4lp_000092"] = two_var_spec(
        "nlp4lp_000092",
        x=("premium", "premium printers", "I", 12, "printer", "premium model"),
        y=("regular", "regular printers", "I", 12, "printer", "regular model"),
        sense="min",
        objective=(1, 1, "minimize_printers", "printer", "minimize the total number of printers"),
        constraints=[
            con("page_floor", {"premium": 30, "regular": 20}, ">=", 200, "print at least 200 pages/minute", "at least 200 pages can be printed per minute", "page/minute"),
            con("ink_cap", {"premium": 4, "regular": 3}, "<=", 35, "use at most 35 ink units/minute", "at most 35 units of ink are used per minute", "ink_unit/minute"),
            con("strict_count_order", {"regular": 1, "premium": -1}, "<=", -1, "regular count strictly less than premium count", "regular printers must be less than the number of premium printers", "printer"),
        ],
        parameters={"page_rate": [30, 20], "ink_rate": [4, 3], "page_floor": 200, "ink_cap": 35},
        interpretation=["Printer counts are integer, so the strict inequality regular < premium is exactly regular <= premium - 1."],
    )

    specs["nlp4lp_000099"] = two_var_spec(
        "nlp4lp_000099",
        x=("train", "model trains", "I", 40, "model", "makes model trains and planes"),
        y=("plane", "model planes", "I", 30, "model", "makes model trains and planes"),
        sense="max",
        objective=(8, 10, "maximize_profit", "USD", "profit per model train is $8 and ... plane is $10"),
        constraints=[
            con("wood_cap", {"train": 3, "plane": 4}, "<=", 120, "wood availability", "120 units of wood", "wood_unit"),
            con("paint_cap", {"train": 3, "plane": 2}, "<=", 90, "paint availability", "90 units of paint", "paint_unit"),
        ],
        parameters={"wood": [3, 4], "paint": [3, 2], "caps": [120, 90], "profit": [8, 10]},
        interpretation=["Model counts are integer."],
    )

    specs["nlp4lp_000108"] = two_var_spec(
        "nlp4lp_000108",
        x=("feed_a", "kilograms of Feed A", "C", None, "kg", "Feed A costs $100 per kilogram"),
        y=("feed_b", "kilograms of Feed B", "C", None, "kg", "Feed B costs $80 per kilogram"),
        sense="min",
        objective=(100, 80, "minimize_feed_cost", "USD", "Determine the minimum cost of the mixture"),
        constraints=[
            con("protein_floor", {"feed_a": 10, "feed_b": 7}, ">=", 30, "protein floor", "minimum of 30 units of protein", "protein_unit"),
            con("fat_floor", {"feed_a": 8, "feed_b": 15}, ">=", 50, "fat floor", "minimum of ... 50 units of fat", "fat_unit"),
        ],
        parameters={"protein": [10, 7], "fat": [8, 15], "cost_per_kg": [100, 80], "floors": [30, 50]},
        interpretation=["Feed amounts are continuous kilograms."],
    )

    specs["nlp4lp_000115"] = {
        "source_id": "nlp4lp_000115",
        "reject": True,
        "reject_reason": "vacuous_zero_solution_missing_production_requirement",
        "details": "The only nontrivial rule is a ratio and all resource constraints are upper bounds. Producing zero bars minimizes time. No demand or minimum production is given.",
        "partial_mapping": {
            "variables": ["milk chocolate bars", "dark chocolate bars"],
            "objective": "minimize 15*milk + 12*dark minutes",
            "constraints": ["4*milk + 6*dark <= 2000", "7*milk + 3*dark <= 1750", "milk >= 2*dark"],
        },
    }

    specs["nlp4lp_000122"] = two_var_spec(
        "nlp4lp_000122",
        x=("almond", "servings of almonds", "C", None, "serving", "a serving of almonds"),
        y=("cashew", "servings of cashews", "C", None, "serving", "a serving of cashews"),
        sense="min",
        objective=(15, 12, "minimize_fat", "gram_fat", "minimize her fat intake"),
        constraints=[
            con("calorie_floor", {"almond": 200, "cashew": 300}, ">=", 10000, "weekly calorie floor", "at least 10000 calories", "calorie"),
            con("protein_floor", {"almond": 20, "cashew": 25}, ">=", 800, "weekly protein floor", "800 grams of protein", "gram_protein"),
            con("almond_ratio", {"almond": 1, "cashew": -2}, ">=", 0, "almond servings at least twice cashew", "at least twice as many servings of almonds", "serving"),
        ],
        parameters={"calories": [200, 300], "protein": [20, 25], "fat": [15, 12], "floors": [10000, 800]},
        interpretation=["A nutritional serving is a divisible amount here; no package, bottle, pill, or other indivisible container is stated."],
    )

    specs["nlp4lp_000129"] = two_var_spec(
        "nlp4lp_000129",
        x=("bus", "bus trips", "I", 10, "trip", "transported either by bus or by car"),
        y=("car", "car trips", "I", None, "trip", "transported either by bus or by car"),
        sense="min",
        objective=(2, 1.5, "minimize_trip_time", "hour", "minimize the total time needed"),
        constraints=[
            con("chicken_floor", {"bus": 100, "car": 40}, ">=", 1200, "transport at least 1200 chickens", "needs to transport 1200 chicken", "chicken"),
            con("car_share", {"car": 0.4, "bus": -0.6}, ">=", 0, "car trips at least 60%", "at least 60% of the trips must be by car", "trip"),
        ],
        parameters={"capacity": [100, 40], "trip_hours": [2, 1.5], "bus_cap": 10, "car_share_floor": 0.6},
        interpretation=["Trip counts are integer; the bus availability is encoded as a variable bound."],
    )

    specs["nlp4lp_000136"] = two_var_spec(
        "nlp4lp_000136",
        x=("blueberry", "packs of blueberries", "I", 100, "pack", "a pack of blueberries"),
        y=("strawberry", "packs of strawberries", "I", 300, "pack", "a pack of strawberries"),
        sense="min",
        objective=(5, 7, "minimize_sugar", "gram_sugar", "minimize her sugar intake"),
        constraints=[
            con("antioxidant_floor", {"blueberry": 3, "strawberry": 1}, ">=", 90, "antioxidant floor", "at least 90 units of anti-oxidants", "antioxidant_unit"),
            con("mineral_floor", {"blueberry": 5, "strawberry": 7}, ">=", 100, "mineral floor", "100 units of minerals", "mineral_unit"),
            con("strawberry_ratio", {"strawberry": 1, "blueberry": -3}, ">=", 0, "strawberry packs at least three times blueberry", "at least 3 times as many packs of strawberries", "pack"),
        ],
        parameters={"antioxidants": [3, 1], "minerals": [5, 7], "sugar": [5, 7], "floors": [90, 100]},
        interpretation=["Packs are indivisible, so counts are integer."],
    )

    specs["nlp4lp_000144"] = two_var_spec(
        "nlp4lp_000144",
        x=("pill", "pill vaccinations", "I", 1000, "patient", "vaccine is taken as a pill"),
        y=("shot", "shot vaccinations", "I", 500, "patient", "another is taken as a shot"),
        sense="max",
        objective=(1, 1, "maximize_patients", "patient", "maximize the number of patients"),
        constraints=[
            con("time_cap", {"pill": 10, "shot": 20}, "<=", 10000, "clinic operating time", "only operates for 10000 minutes", "minute"),
            con("shot_ratio", {"shot": 1, "pill": -3}, ">=", 0, "shots at least three times pills", "at least 3 times as many shots as pill", "patient"),
            con("pill_floor", {"pill": 1}, ">=", 30, "at least 30 pill vaccines", "at least 30 pill vaccines", "patient"),
        ],
        parameters={"minutes": [10, 20], "time_cap": 10000, "shot_ratio_floor": 3, "pill_floor": 30},
        interpretation=["Each administered vaccine corresponds to one patient, hence integer counts."],
    )

    specs["nlp4lp_000151"] = two_var_spec(
        "nlp4lp_000151",
        x=("graph", "reams of graph paper", "I", 234, "ream", "ream of graph paper"),
        y=("music", "reams of music paper", "I", 234, "ream", "ream of music paper"),
        sense="max",
        objective=(4, 2.5, "maximize_profit", "USD", "profit of $4 ... and ... $2.5"),
        constraints=[
            con("printing_cap", {"graph": 3, "music": 1.5}, "<=", 350, "printing-machine time", "printing machine ... maximum of 350 minutes", "minute"),
            con("scanning_cap", {"graph": 5.5, "music": 3}, "<=", 350, "scanning-machine time", "scanning machine ... maximum of 350 minutes", "minute"),
        ],
        parameters={"printing": [3, 1.5], "scanning": [5.5, 3], "machine_minutes": 350, "profit": [4, 2.5]},
        interpretation=["A ream is a countable finished package, so production quantities are integer."],
    )

    specs["nlp4lp_000158"] = two_var_spec(
        "nlp4lp_000158",
        x=("rural", "rural factories", "I", 40, "factory", "building rural and urban factories"),
        y=("urban", "urban factories", "I", 20, "factory", "building rural and urban factories"),
        sense="min",
        objective=(1, 1, "minimize_factories", "factory", "minimize the total number of factories"),
        constraints=[
            con("phone_floor", {"rural": 100, "urban": 200}, ">=", 3000, "phone production floor", "must make at least 3000 phones per day", "phone/day"),
            con("manager_cap", {"rural": 8, "urban": 20}, "<=", 260, "manager availability", "available 260 managers", "manager"),
        ],
        parameters={"phone_capacity": [100, 200], "managers": [8, 20], "phone_floor": 3000, "manager_cap": 260},
        interpretation=["Factory counts are integer."],
    )

    specs["nlp4lp_000166"] = two_var_spec(
        "nlp4lp_000166",
        x=("beam1", "minutes of Beam 1", "C", 20, "minute", "Beam 1 ... per minute"),
        y=("beam2", "minutes of Beam 2", "C", 30, "minute", "Beam 2 ... per minute"),
        sense="min",
        objective=(0.3, 0.2, "minimize_pancreas_dose", "dose_unit", "minimize the total radiation received by the pancreas"),
        constraints=[
            con("skin_cap", {"beam1": 0.2, "beam2": 0.1}, "<=", 4, "skin dose cap", "At most 4 units ... received by the skin", "dose_unit"),
            con("tumor_floor", {"beam1": 0.6, "beam2": 0.4}, ">=", 3, "tumor dose floor", "at least 3 units ... delivered to the tumor", "dose_unit"),
        ],
        parameters={"pancreas_rate": [0.3, 0.2], "skin_rate": [0.2, 0.1], "tumor_rate": [0.6, 0.4], "skin_cap": 4, "tumor_floor": 3},
        interpretation=["Treatment duration is continuous minutes."],
    )

    specs["nlp4lp_000173"] = two_var_spec(
        "nlp4lp_000173",
        x=("wide", "wide pipes", "I", None, "pipe", "wide pipes"),
        y=("narrow", "narrow pipes", "I", None, "pipe", "narrow pipes"),
        sense="min",
        objective=(1, 1, "minimize_pipes", "pipe", "minimize the total number of pipes"),
        constraints=[
            con("water_floor", {"wide": 25, "narrow": 15}, ">=", 900, "water-flow floor", "at least 900 units of water ... every minute", "water_unit/minute"),
            con("wide_ratio", {"wide": 3, "narrow": -1}, "<=", 0, "wide pipes at most one third of narrow pipes", "wide pipes can be at most a third the number of narrow pipes", "pipe"),
            con("wide_floor", {"wide": 1}, ">=", 5, "at least 5 wide pipes", "at least 5 wide pipes must be used", "pipe"),
        ],
        parameters={"flow": [25, 15], "flow_floor": 900, "wide_ratio_cap": "1/3", "wide_floor": 5},
        interpretation=["Pipe counts are integer."],
    )

    specs["nlp4lp_000181"] = two_var_spec(
        "nlp4lp_000181",
        x=("cart", "cart delivery shifts", "I", None, "shift", "deliver ... by cart"),
        y=("hand", "hand delivery shifts", "I", None, "shift", "deliver ... by hand"),
        sense="min",
        objective=(5, 20, "minimize_refills", "refill/hour", "minimize the total number of refills per hour"),
        constraints=[
            con("interaction_floor", {"cart": 70, "hand": 85}, ">=", 4000, "customer-interaction floor", "4000 customer interactions per hour", "interaction/hour"),
            con("cart_share", {"cart": 0.3, "hand": -0.7}, ">=", 0, "cart shifts at least 70%", "at least 70% of delivery shifts must be by cart", "shift"),
            con("hand_floor", {"hand": 1}, ">=", 3, "at least 3 hand-delivery servers", "at least 3 servers delivering by hand", "shift"),
        ],
        parameters={"interactions": [70, 85], "refills": [5, 20], "interaction_floor": 4000, "cart_share_floor": 0.7, "hand_floor": 3},
        interpretation=["A scheduled delivery shift is treated as one server-shift and is integer."],
    )

    specs["nlp4lp_000189"] = two_var_spec(
        "nlp4lp_000189",
        x=("chem_a", "units of chemical A", "C", None, "chemical_unit", "chemical A"),
        y=("chem_b", "units of chemical B", "C", None, "chemical_unit", "chemical B"),
        sense="min",
        objective=(30, 45, "minimize_effect_time", "second", "minimize the total time it takes"),
        constraints=[
            con("a_ratio", {"chem_a": 3, "chem_b": -1}, "<=", 0, "A at most one third of B", "at most a third as much chemical A as chemical B", "chemical_unit"),
            con("a_floor", {"chem_a": 1}, ">=", 300, "at least 300 units A", "at least 300 units of chemical A", "chemical_unit"),
            con("total_floor", {"chem_a": 1, "chem_b": 1}, ">=", 1500, "at least 1500 total units", "at least 1500 units of total chemicals", "chemical_unit"),
        ],
        parameters={"seconds": [30, 45], "a_ratio_cap": "1/3 of B", "a_floor": 300, "total_floor": 1500},
        interpretation=["Chemical quantities are continuous units."],
    )

    specs["nlp4lp_000197"] = two_var_spec(
        "nlp4lp_000197",
        x=("golf", "golf carts", "I", None, "cart", "golf carts"),
        y=("pull", "pull carts", "I", None, "cart", "pull carts"),
        sense="min",
        objective=(1, 1, "minimize_carts", "cart", "minimize the total number of carts"),
        constraints=[
            con("guest_floor", {"golf": 4, "pull": 1}, ">=", 80, "guest-transport floor", "transport at least 80 guests", "guest"),
            con("golf_share", {"golf": 0.4, "pull": -0.6}, "<=", 0, "golf carts at most 60%", "at most 60% of carts can be golf carts", "cart"),
        ],
        parameters={"guest_capacity": [4, 1], "guest_floor": 80, "golf_share_cap": 0.6},
        interpretation=["Cart counts are integer."],
    )

    specs["nlp4lp_000205"] = two_var_spec(
        "nlp4lp_000205",
        x=("reaction_a", "number of reaction-A batches", "I", 200, "batch", "chemical reaction A"),
        y=("reaction_b", "number of reaction-B batches", "I", 267, "batch", "chemical reaction B"),
        sense="max",
        objective=(10, 8, "maximize_compound", "compound_unit", "maximize the amount of rare compound produced"),
        constraints=[
            con("gas_cap", {"reaction_a": 5, "reaction_b": 7}, "<=", 1000, "inert-gas availability", "1000 units of the rare inert gas", "gas_unit"),
            con("water_cap", {"reaction_a": 6, "reaction_b": 3}, "<=", 800, "treated-water availability", "800 units of treated water", "water_unit"),
        ],
        parameters={"gas": [5, 7], "water": [6, 3], "output": [10, 8], "caps": [1000, 800]},
        interpretation=["The decision is explicitly how many reaction executions are done, so counts are integer batches."],
    )

    specs["nlp4lp_000213"] = two_var_spec(
        "nlp4lp_000213",
        x=("ship", "ship trips", "I", None, "trip", "uses ships and planes"),
        y=("plane", "plane trips", "I", 10, "trip", "uses ships and planes"),
        sense="min",
        objective=(500, 300, "minimize_fuel", "liter", "minimize the total amount of fuel consumed"),
        constraints=[
            con("container_floor", {"ship": 40, "plane": 20}, ">=", 500, "container-transport floor", "at least 500 containers", "container"),
            con("ship_share", {"ship": 0.5, "plane": -0.5}, ">=", 0, "ship trips at least 50%", "minimum of 50% of the trips ... by ship", "trip"),
        ],
        parameters={"container_capacity": [40, 20], "fuel": [500, 300], "container_floor": 500, "plane_cap": 10, "ship_share_floor": 0.5},
        interpretation=["Trip counts are integer; the plane trip cap is encoded as a variable bound."],
    )

    specs["nlp4lp_000220"] = two_var_spec(
        "nlp4lp_000220",
        x=("sulfate", "units of sulfate", "I", None, "ingredient_unit", "units of sulfate"),
        y=("ginger", "units of ginger", "I", None, "ingredient_unit", "units of ginger"),
        sense="min",
        objective=(0.5, 0.75, "minimize_sequential_effect_time", "minute", "minimize the total amount of time"),
        constraints=[
            con("sulfate_floor", {"sulfate": 1}, ">=", 100, "sulfate floor", "at least 100 units of sulfates", "ingredient_unit"),
            con("total_floor", {"sulfate": 1, "ginger": 1}, ">=", 400, "total ingredient floor", "a total of 400 units", "ingredient_unit"),
            con("sulfate_ratio", {"sulfate": 1, "ginger": -2}, "<=", 0, "sulfate at most twice ginger", "at most twice the amount of sulfate as ginger", "ingredient_unit"),
        ],
        parameters={"effect_minutes": [0.5, 0.75], "sulfate_floor": 100, "total_floor": 400, "sulfate_ratio_cap": 2},
        interpretation=["The source asks for numbers of discrete ingredient units. Because one ingredient must be added before the other, the stated per-unit times add rather than run in parallel."],
    )

    specs["nlp4lp_000228"] = two_var_spec(
        "nlp4lp_000228",
        x=("painkiller", "painkiller pills", "I", 300, "pill", "make painkillers and sleeping pills"),
        y=("sleeping", "sleeping pills", "I", 500, "pill", "make painkillers and sleeping pills"),
        sense="min",
        objective=(3, 5, "minimize_digestive_medicine", "medicine_unit", "minimize the total amount of digestive medicine"),
        constraints=[
            con("morphine_cap", {"painkiller": 10, "sleeping": 6}, "<=", 3000, "morphine availability", "has 3000 mg of morphine", "mg"),
            con("painkiller_floor", {"painkiller": 1}, ">=", 50, "at least 50 painkillers", "at least 50 painkiller pills", "pill"),
            con("sleeping_share", {"sleeping": 0.3, "painkiller": -0.7}, ">=", 0, "sleeping pills at least 70%", "at least 70% of the pills should be sleeping pills", "pill"),
        ],
        parameters={"morphine_mg": [10, 6], "digestive_medicine": [3, 5], "morphine_cap": 3000, "painkiller_floor": 50, "sleeping_share_floor": 0.7},
        interpretation=["Pill counts are integer."],
    )

    specs["nlp4lp_000235"] = two_var_spec(
        "nlp4lp_000235",
        x=("small", "small bottles", "I", 300, "bottle", "small bottles"),
        y=("large", "large bottles", "I", 100, "bottle", "large bottles"),
        sense="max",
        objective=(5, 20, "maximize_honey", "honey_unit", "maximize the total amount of honey"),
        constraints=[
            con("small_ratio", {"small": 1, "large": -2}, ">=", 0, "small bottles at least twice large", "at least twice as many small bottles", "bottle"),
            con("total_cap", {"small": 1, "large": 1}, "<=", 200, "at most 200 bottles", "at most 200 bottles total", "bottle"),
            con("large_floor", {"large": 1}, ">=", 50, "at least 50 large bottles", "at least 50 must be large bottles", "bottle"),
        ],
        parameters={"honey_capacity": [5, 20], "individual_caps": [300, 100], "total_cap": 200, "large_floor": 50},
        interpretation=["Bottle counts are integer; availability limits are variable bounds."],
    )

    specs["nlp4lp_000242"] = two_var_spec(
        "nlp4lp_000242",
        x=("pill_a", "amount of pill A", "C", None, "pill_equivalent", "pill A"),
        y=("pill_b", "amount of pill B", "C", None, "pill_equivalent", "pill B"),
        sense="min",
        objective=(4, 5, "minimize_cost", "USD", "Formulate a LP to minimize the cost"),
        constraints=[
            con("sleep_floor", {"pill_a": 3, "pill_b": 6}, ">=", 40, "sleep-inducing medicine floor", "at least 40 units of sleep-inducing medicine", "medicine_unit"),
            con("anti_floor", {"pill_a": 5, "pill_b": 1}, ">=", 50, "anti-inflammatory medicine floor", "50 units of anti-inflammatory medicine", "medicine_unit"),
        ],
        parameters={"sleep_units": [3, 6], "anti_units": [5, 1], "cost": [4, 5], "floors": [40, 50]},
        interpretation=["The prompt explicitly asks for an LP, so variables are continuous pill-equivalents despite the physical noun."],
    )

    # MAMO diet LP.
    foods = ["steak", "tofu", "chicken", "broccoli", "rice", "spinach"]
    food_claim = {
        "steak": "Steak",
        "tofu": "Tofu",
        "chicken": "Chicken",
        "broccoli": "Broccoli",
        "rice": "Rice",
        "spinach": "Spinach",
    }
    food_vars = [
        var(f, f"units of {f}", "I", None, "food_item", food_claim[f])
        for f in foods
    ]
    protein = dict(zip(foods, [14, 2, 17, 3, 15, 2], strict=True))
    carbs = dict(zip(foods, [23, 13, 13, 1, 23, 8], strict=True))
    calories = dict(zip(foods, [63, 162, 260, 55, 231, 297], strict=True))
    costs = dict(zip(foods, [4, 6, 6, 8, 8, 5], strict=True))
    specs["mamo_complexlp_000001"] = make_spec(
        "mamo_complexlp_000001",
        variables=food_vars,
        sense="min",
        objective_terms=costs,
        objective_name="minimize_meal_cost",
        objective_unit="USD",
        objective_claim="keep the cost as low as possible",
        constraints=[
            con("protein_floor", protein, ">=", 83, "protein floor", "at least 83 grams of protein", "gram"),
            con("carb_floor", carbs, ">=", 192, "carbohydrate floor", "192 grams of carbohydrates", "gram"),
            con("calorie_floor", calories, ">=", 2089, "calorie floor", "2089 calories", "calorie"),
        ],
        parameters={"foods": foods, "protein": list(protein.values()), "carbohydrates": list(carbs.values()), "calories": list(calories.values()), "cost": list(costs.values()), "requirements": [83, 192, 2089]},
        sets={"foods": foods},
        interpretation=["The source enumerates food items with nutrition and cost per item; item quantities are integer."],
    )

    specs["mamo_complexlp_000041"] = {
        "source_id": "mamo_complexlp_000041",
        "reject": True,
        "reject_reason": "redistribution_balance_and_transshipment_scope_ambiguous",
        "details": "The text gives current stock and required stock but does not say whether surplus may remain, be discarded, or transit through intermediate warehouses. These choices change the network-flow model and cost.",
        "partial_mapping": {"sets": ["six warehouses"], "variables": ["flow x_ij"], "objective": "minimize sum c_ij*x_ij"},
    }
    specs["mamo_complexlp_000049"] = {
        "source_id": "mamo_complexlp_000049",
        "reject": True,
        "reject_reason": "exact_final_inventory_conflicts_with_total_supply",
        "details": "The task says every facility ends with exactly its need, while total current inventory exceeds total required inventory and no disposal variable/cost is specified. Conservation therefore makes the literal model infeasible.",
        "partial_mapping": {"sets": ["seven facilities"], "variables": ["transfer x_ij"], "objective": "minimize sum c_ij*x_ij"},
    }

    # Symmetric 5-city TSP with undirected edge variables and exhaustive SECs.
    cities = ["E", "F", "G", "H", "I"]
    cost_pairs = {
        ("E", "F"): 50, ("E", "G"): 48, ("E", "H"): 99, ("E", "I"): 91,
        ("F", "G"): 57, ("F", "H"): 84, ("F", "I"): 72,
        ("G", "H"): 46, ("G", "I"): 86, ("H", "I"): 29,
    }
    tsp_vars = []
    tsp_terms: dict[str, float] = {}
    for (i, j), cost in cost_pairs.items():
        name = f"x_{i}_{j}"
        tsp_vars.append(var(name, f"use edge {i}-{j}", "B", 1, "edge", f"cost from City {i} to {j}"))
        tsp_terms[name] = cost
    tsp_constraints = []
    for city in cities:
        terms = {
            f"x_{i}_{j}": 1
            for i, j in cost_pairs
            if city in (i, j)
        }
        tsp_constraints.append(con(f"degree_{city}", terms, "==", 2, f"visit {city} once in a tour", "visit each city exactly once and then return", "edge"))
    # SEC for all proper subsets with 2..n-2 nodes.
    for size in range(2, len(cities) - 1):
        for subset in itertools.combinations(cities, size):
            terms = {
                f"x_{i}_{j}": 1
                for i, j in cost_pairs
                if i in subset and j in subset
            }
            tsp_constraints.append(con(
                "sec_" + "_".join(subset),
                terms,
                "<=",
                size - 1,
                f"prevent subtour on {subset}",
                "single route visits every city and returns to start",
                "edge",
            ))
    specs["mamo_complexlp_000060"] = make_spec(
        "mamo_complexlp_000060",
        variables=tsp_vars,
        sense="min",
        objective_terms=tsp_terms,
        objective_name="minimize_tour_cost",
        objective_unit="cost_unit",
        objective_claim="minimize the total delivery cost",
        constraints=tsp_constraints,
        parameters={"cities": cities, "undirected_edge_costs": {f"{i}-{j}": c for (i, j), c in cost_pairs.items()}},
        sets={"cities": cities, "edges": [f"{i}-{j}" for i, j in cost_pairs]},
        interpretation=["Costs are symmetric in the text, so one binary variable per undirected edge is sufficient.", "Degree equations plus all proper-subset SECs encode one Hamiltonian cycle."],
    )

    # Capacitated facility location.
    centers = range(1, 6)
    stores = range(1, 6)
    opening = [151000, 192000, 114000, 171000, 160000]
    capacities = [1954, 1446, 820, 1640, 966]
    demands = [589, 962, 966, 643, 904]
    transport = [
        [5, 2, 3, 3, 3],
        [5, 4, 3, 5, 2],
        [4, 2, 4, 5, 1],
        [4, 2, 5, 4, 1],
        [1, 3, 3, 2, 4],
    ]
    facility_vars = [
        var(f"y_{i}", f"open center {i}", "B", 1, "binary", f"opening cost Center {i}")
        for i in centers
    ]
    for i in centers:
        for j in stores:
            facility_vars.append(var(f"x_{i}_{j}", f"units from center {i} to store {j}", "C", demands[j - 1], "unit", f"transportation cost from Center {i} to Store {j}"))
    facility_obj = {f"y_{i}": opening[i - 1] for i in centers}
    facility_obj.update({
        f"x_{i}_{j}": transport[i - 1][j - 1]
        for i in centers for j in stores
    })
    facility_constraints = []
    for j in stores:
        facility_constraints.append(con(
            f"demand_{j}",
            {f"x_{i}_{j}": 1 for i in centers},
            "==",
            demands[j - 1],
            f"meet Store {j} demand",
            f"Demand of Store {j}: {demands[j - 1]}",
            "unit",
        ))
    for i in centers:
        terms = {f"x_{i}_{j}": 1 for j in stores}
        terms[f"y_{i}"] = -capacities[i - 1]
        facility_constraints.append(con(
            f"capacity_{i}",
            terms,
            "<=",
            0,
            f"Center {i} ships only if open and within capacity",
            f"Supply Capacity of Center {i}: {capacities[i - 1]}",
            "unit",
        ))
    specs["mamo_complexlp_000140"] = make_spec(
        "mamo_complexlp_000140",
        variables=facility_vars,
        sense="min",
        objective_terms=facility_obj,
        objective_name="minimize_opening_and_transport_cost",
        objective_unit="USD",
        objective_claim="minimal total cost ... includes both opening costs and transportation costs",
        constraints=facility_constraints,
        parameters={"opening_cost": opening, "capacity": capacities, "demand": demands, "transport_cost": transport},
        sets={"centers": list(centers), "stores": list(stores)},
        interpretation=["Shipment quantities are continuous; center-opening decisions are binary.", "Positive shipping costs imply no oversupply, so demands are encoded as equalities."],
    )

    # Cyclic 5-on/2-off schedule LP.
    demand = [2, 4, 4, 3, 1, 2, 3]
    nurse_vars = [
        var(f"start_{d}", f"nurses starting on day {d}", "C", None, "nurse", "Every nurse works 5 days in a row")
        for d in range(1, 8)
    ]
    nurse_constraints = []
    for day in range(7):
        covering = {
            f"start_{start + 1}": 1
            for start in range(7)
            if (day - start) % 7 in range(5)
        }
        nurse_constraints.append(con(
            f"demand_day_{day + 1}",
            covering,
            ">=",
            demand[day],
            f"meet night-shift demand on day {day + 1}",
            f"d{day + 1} = {demand[day]} and every nurse works 5 days in a row",
            "nurse",
        ))
    specs["mamo_complexlp_000179"] = make_spec(
        "mamo_complexlp_000179",
        variables=nurse_vars,
        sense="min",
        objective_terms={f"start_{d}": 1 for d in range(1, 8)},
        objective_name="minimize_nurses",
        objective_unit="nurse",
        objective_claim="minimize the total number of nurses used",
        constraints=nurse_constraints,
        parameters={"daily_demand": demand, "consecutive_workdays": 5, "cycle_days": 7},
        sets={"days": list(range(1, 8))},
        interpretation=["Each variable is the number starting a cyclic five-day block.", "The prompt explicitly relaxes integrality, so nurse variables are continuous."],
    )

    # Undirected shortest path, unit s-t flow.
    nodes = ["S", "2", "3", "4", "5", "6", "7", "T"]
    undirected_edges = {
        ("S", "2"): 5, ("S", "3"): 4, ("2", "4"): 3, ("2", "3"): 2,
        ("3", "5"): 1, ("3", "6"): 7, ("4", "6"): 2, ("5", "T"): 5,
        ("6", "7"): 3, ("7", "T"): 1,
    }
    arc_costs: dict[tuple[str, str], float] = {}
    for (i, j), cost in undirected_edges.items():
        arc_costs[i, j] = cost
        arc_costs[j, i] = cost
    sp_vars = [
        var(f"x_{i}_{j}", f"use directed arc {i}->{j}", "B", 1, "arc", f"{i} connected to {j} with weight {cost:g}")
        for (i, j), cost in arc_costs.items()
    ]
    sp_constraints = []
    for node in nodes:
        terms: dict[str, float] = {}
        for i, j in arc_costs:
            if i == node:
                terms[f"x_{i}_{j}"] = terms.get(f"x_{i}_{j}", 0) + 1
            if j == node:
                terms[f"x_{i}_{j}"] = terms.get(f"x_{i}_{j}", 0) - 1
        rhs = 1 if node == "S" else (-1 if node == "T" else 0)
        sp_constraints.append(con(f"flow_{node}", terms, "==", rhs, f"unit s-t flow balance at {node}", "shortest distance from S to T", "flow_unit"))
    specs["mamo_complexlp_000186"] = make_spec(
        "mamo_complexlp_000186",
        variables=sp_vars,
        sense="min",
        objective_terms={f"x_{i}_{j}": c for (i, j), c in arc_costs.items()},
        objective_name="minimize_path_distance",
        objective_unit="meter",
        objective_claim="find the shortest distance from S to T",
        constraints=sp_constraints,
        parameters={"undirected_edges": {f"{i}-{j}": c for (i, j), c in undirected_edges.items()}},
        sets={"nodes": nodes, "directed_arcs": [f"{i}->{j}" for i, j in arc_costs]},
        interpretation=["The repeated reverse connections establish an undirected graph; it is encoded as two directed arcs per edge.", "Positive weights rule out beneficial cycles."],
    )

    specs["mamo_complexlp_000198"] = {
        "source_id": "mamo_complexlp_000198",
        "reject": True,
        "reject_reason": "worst_case_revenue_definition_ambiguous",
        "details": "The text supplies purchase prices but asks for maximum worst-case revenue, not profit, and gives no budget. If revenue means payoff, prices are irrelevant; if it means net payoff, prices enter every scenario. The two formulations are materially different.",
        "partial_mapping": {"sets": ["five securities", "five World Cup outcomes"], "variables": ["shares of each security", "worst-case value z"]},
    }

    # Vertex cover on the explicitly enumerated outer cycle, spokes and inner K5.
    vertices = list("abcdefghij")
    outer = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "a")]
    spokes = [("a", "f"), ("b", "g"), ("c", "h"), ("d", "i"), ("e", "j")]
    inner = list(itertools.combinations(list("fghij"), 2))
    edges = outer + spokes + inner
    vc_vars = [
        var(f"x_{v}", f"select vertex {v}", "B", 1, "binary", f"Vertex '{v}'")
        for v in vertices
    ]
    vc_constraints = [
        con(f"cover_{u}_{v}", {f"x_{u}": 1, f"x_{v}": 1}, ">=", 1, f"cover edge {u}-{v}", f"{u} connects to {v}", "vertex")
        for u, v in edges
    ]
    specs["mamo_complexlp_000200"] = make_spec(
        "mamo_complexlp_000200",
        variables=vc_vars,
        sense="min",
        objective_terms={f"x_{v}": 1 for v in vertices},
        objective_name="minimize_vertex_cover_size",
        objective_unit="vertex",
        objective_claim="find the minimum vertex cover",
        constraints=vc_constraints,
        parameters={"vertices": vertices, "edges": [f"{u}-{v}" for u, v in edges]},
        sets={"vertices": vertices, "edges": [f"{u}-{v}" for u, v in edges]},
        interpretation=["The colored vertices are treated only as a proposed solution, not as a constraint or gold label.", "The edge set uses only the explicitly described outer cycle, spokes, and complete inner K5."],
    )

    # Four-quarter production and inventory balance.
    quarters = range(1, 5)
    sail_vars = []
    for q in quarters:
        sail_vars.extend([
            var(f"regular_{q}", f"regular-time production in quarter {q}", "C", 40, "sailboat", "produce up to 40 sailboats with regular-time labor"),
            var(f"overtime_{q}", f"overtime production in quarter {q}", "C", None, "sailboat", "produce additional sailboats with overtime labor"),
            var(f"inventory_{q}", f"ending inventory in quarter {q}", "C", None, "sailboat", "At the end of each quarter ... holding cost"),
        ])
    sail_obj: dict[str, float] = {}
    for q in quarters:
        sail_obj[f"regular_{q}"] = 400
        sail_obj[f"overtime_{q}"] = 450
        sail_obj[f"inventory_{q}"] = 20
    sail_demand = [40, 60, 75, 25]
    sail_constraints = []
    for q in quarters:
        terms = {f"regular_{q}": 1, f"overtime_{q}": 1, f"inventory_{q}": -1}
        rhs = sail_demand[q - 1]
        if q == 1:
            rhs -= 10
        else:
            terms[f"inventory_{q - 1}"] = 1
        sail_constraints.append(con(
            f"balance_{q}",
            terms,
            "==",
            rhs,
            f"quarter {q} inventory balance",
            f"demand during quarter {q} is {sail_demand[q - 1]} and demands must be met on time",
            "sailboat",
        ))
    specs["mamo_complexlp_000207"] = make_spec(
        "mamo_complexlp_000207",
        variables=sail_vars,
        sense="min",
        objective_terms=sail_obj,
        objective_name="minimize_production_and_inventory_cost",
        objective_unit="USD",
        objective_claim="minimize the sum of production and inventory costs",
        constraints=sail_constraints,
        parameters={"demand": sail_demand, "initial_inventory": 10, "regular_capacity": 40, "regular_cost": 400, "overtime_cost": 450, "holding_cost": 20},
        sets={"quarters": list(quarters)},
        interpretation=["All variables are continuous because the prompt explicitly asks for linear programming.", "No terminal inventory requirement is added; positive costs make excess terminal inventory suboptimal."],
    )

    return specs


def build_ir(candidate: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    variables = [
        {k: value for k, value in variable.items() if k not in {"source_claim", "unit"}}
        for variable in spec["variables"]
    ]
    constraints = [
        {k: value for k, value in constraint.items() if k not in {"source_claim", "requirement", "unit"}}
        for constraint in spec["constraints"]
    ]
    return {
        "schema_version": "1.0",
        "model_id": f"{candidate['candidate_id']}_source_certification",
        "candidate_id": candidate["candidate_id"],
        "source_dataset": candidate["source_dataset"],
        "source_id": candidate["source_id"],
        "source_problem_sha256": candidate["source_hash"],
        "single_objective": True,
        "sense": spec["sense"],
        "variables": variables,
        "objective": {
            k: value
            for k, value in spec["objective"].items()
            if k != "source_claim"
        },
        "constraints": constraints,
        "action_projection": [variable["name"] for variable in variables],
        "metadata": {
            "formulation_authority": "problem_text_only",
            "legacy_answer_used_to_formulate": False,
            "legacy_code_read": False,
            "interpretation": spec["interpretation"],
            "semantic_risks": spec["semantic_risks"],
        },
    }


def semantic_mapping(candidate: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "source_id": candidate["source_id"],
        "problem_sha256": candidate["source_hash"],
        "formulation_authority": "problem_text_only",
        "sets": spec["sets"],
        "parameters": spec["parameters"],
        "variables": [
            {
                "name": variable["name"],
                "meaning": variable["semantic_name"],
                "domain": variable["vartype"],
                "bounds": [variable["lb"], variable["ub"]],
                "unit": variable["unit"],
                "source_claim": variable["source_claim"],
            }
            for variable in spec["variables"]
        ],
        "objective": {
            "direction": spec["sense"],
            "name": spec["objective"]["name"],
            "terms": spec["objective"]["terms"],
            "unit": spec["objective"]["unit"],
            "source_claim": spec["objective"]["source_claim"],
        },
        "constraints": [
            {
                "name": constraint["name"],
                "equation": constraint["expression"],
                "meaning": constraint["requirement"],
                "unit": constraint["unit"],
                "source_claim": constraint["source_claim"],
            }
            for constraint in spec["constraints"]
        ],
        "interpretation_decisions": spec["interpretation"],
        "semantic_risks": spec["semantic_risks"],
        "completeness_check": {
            "sets_mapped": True,
            "parameters_mapped": True,
            "variables_mapped": True,
            "single_objective_mapped": True,
            "constraints_mapped": True,
            "units_mapped": True,
        },
    }


def exhaustive_integer_oracle(
    ir: dict[str, Any],
    optimal_objective_hint: float | None = None,
) -> dict[str, Any]:
    variables = ir["variables"]
    if any(variable["vartype"] not in {"I", "B"} for variable in variables):
        return {"attempted": False, "reason": "contains_continuous_variables"}
    names = [variable["name"] for variable in variables]
    lower = {
        variable["name"]: int(math.ceil(float(variable.get("lb", 0.0)) - TOL))
        for variable in variables
    }
    upper: dict[str, int | None] = {
        variable["name"]: (
            None
            if variable.get("ub") is None
            else int(math.floor(float(variable["ub"]) + TOL))
        )
        for variable in variables
    }
    bound_basis: dict[str, str] = {
        variable["name"]: "canonical_variable_bound"
        for variable in variables
        if variable.get("ub") is not None
    }

    # For a minimization model with nonnegative objective coefficients, every
    # optimum lies in the box implied by objective <= the independently solved
    # optimum.  This is an oracle search bound, not a canonical model bound.
    objective_terms = ir["objective"]["terms"]
    if (
        ir["sense"] == "min"
        and optimal_objective_hint is not None
        and all(float(coef) >= 0 for coef in objective_terms.values())
    ):
        constant = float(ir["objective"].get("constant", 0.0))
        for name in names:
            coefficient = float(objective_terms.get(name, 0.0))
            if coefficient <= 0:
                continue
            other_min = sum(
                float(objective_terms.get(other, 0.0)) * lower[other]
                for other in names
                if other != name
            )
            derived = math.floor(
                (optimal_objective_hint - constant - other_min + TOL)
                / coefficient
            )
            if upper[name] is None or derived < upper[name]:
                upper[name] = derived
                bound_basis[name] = "optimal_objective_upper_face"

    # Propagate safe linear upper bounds. A >= row is multiplied by -1.
    rows: list[tuple[dict[str, float], float, str]] = []
    for constraint in ir["constraints"]:
        terms = {name: float(value) for name, value in constraint["terms"].items()}
        rhs = float(constraint["rhs"])
        if constraint["sense"] in {"<=", "=="}:
            rows.append((terms, rhs, constraint["name"]))
        if constraint["sense"] in {">=", "=="}:
            rows.append(
                (
                    {name: -value for name, value in terms.items()},
                    -rhs,
                    constraint["name"] + "_reversed",
                )
            )
    changed = True
    while changed:
        changed = False
        for terms, rhs, row_name in rows:
            for name, coefficient in terms.items():
                if coefficient <= 0:
                    continue
                minimum_other = 0.0
                safe = True
                for other, other_coefficient in terms.items():
                    if other == name:
                        continue
                    if other_coefficient >= 0:
                        minimum_other += other_coefficient * lower[other]
                    elif upper[other] is not None:
                        minimum_other += other_coefficient * upper[other]
                    else:
                        safe = False
                        break
                if not safe:
                    continue
                derived = math.floor((rhs - minimum_other + TOL) / coefficient)
                if upper[name] is None or derived < upper[name]:
                    upper[name] = derived
                    bound_basis[name] = f"linear_bound_propagation:{row_name}"
                    changed = True

    if any(upper[name] is None for name in names):
        return {
            "attempted": False,
            "reason": "unbounded_integer_domain_no_finite_exhaustive_box",
            "derived_bounds": {
                name: {"lb": lower[name], "ub": upper[name], "basis": bound_basis.get(name)}
                for name in names
            },
        }
    domain_sizes = [
        int(upper[name]) - lower[name] + 1
        for name in names
    ]
    state_count = math.prod(domain_sizes)
    if state_count > 1_000_000:
        return {
            "attempted": False,
            "reason": "state_space_above_1000000",
            "state_count": state_count,
            "derived_bounds": {
                name: {"lb": lower[name], "ub": upper[name], "basis": bound_basis.get(name)}
                for name in names
            },
        }
    domains = [
        range(lower[name], int(upper[name]) + 1)
        for name in names
    ]
    enumeration_ir = json.loads(json.dumps(ir, ensure_ascii=False))
    for variable in enumeration_ir["variables"]:
        variable["ub"] = upper[variable["name"]]
    feasible: list[tuple[float, dict[str, float]]] = []
    for values in itertools.product(*domains):
        assignment = dict(zip(names, map(float, values), strict=True))
        inspection = inspect_assignment(enumeration_ir, assignment)
        if (
            inspection["max_constraint_violation"] <= TOL
            and inspection["bound_violation"] <= TOL
        ):
            feasible.append((objective_value(ir, assignment), assignment))
    if not feasible:
        return {
            "attempted": True,
            "state_count": state_count,
            "status": "INFEASIBLE",
            "passed": False,
        }
    best = (
        max(value for value, _ in feasible)
        if ir["sense"] == "max"
        else min(value for value, _ in feasible)
    )
    optima = [
        assignment
        for value, assignment in feasible
        if abs(value - best) <= TOL
    ]
    return {
        "attempted": True,
        "state_count": state_count,
        "feasible_count": len(feasible),
        "status": "OPTIMAL",
        "objective": best,
        "optimal_assignment_count": len(optima),
        "optimal_assignments": optima[:100],
        "all_optima_stored": len(optima) <= 100,
        "derived_bounds": {
            name: {"lb": lower[name], "ub": upper[name], "basis": bound_basis.get(name)}
            for name in names
        },
    }


def certify(ir: dict[str, Any]) -> dict[str, Any]:
    # The shared solver backend expects finite numeric bounds.  Canonical IR
    # keeps a missing source upper bound as null; only the solver copy receives
    # a very large implementation bound.  Positive objective/constraints make
    # this proxy inactive at every returned optimum, which is verified below.
    solver_ir = json.loads(json.dumps(ir, ensure_ascii=False))
    proxy_bound_variables = []
    for variable in solver_ir["variables"]:
        if variable.get("ub") is None:
            variable["ub"] = INF
            proxy_bound_variables.append(variable["name"])
    gurobi = solve_gurobi(solver_ir)
    copt = solve_copt(solver_ir)
    all_optimal = gurobi["status"] == "OPTIMAL" and copt["status"] == "OPTIMAL"
    objective_agreement = (
        all_optimal
        and abs(gurobi["objective"] - copt["objective"]) <= TOL
    )
    residuals_pass = (
        all_optimal
        and max(
            gurobi["max_constraint_violation"],
            gurobi["bound_violation"],
            gurobi["integrality_violation"],
            copt["max_constraint_violation"],
            copt["bound_violation"],
            copt["integrality_violation"],
        )
        <= TOL
    )
    oracle = exhaustive_integer_oracle(
        ir,
        gurobi.get("objective") if all_optimal else None,
    )
    oracle_agreement = (
        not oracle["attempted"]
        or (
            oracle["status"] == "OPTIMAL"
            and abs(oracle["objective"] - gurobi["objective"]) <= TOL
            and abs(oracle["objective"] - copt["objective"]) <= TOL
        )
    )
    proxy_bounds_inactive = all(
        result.get("assignment", {}).get(name, 0.0) < INF - 1
        for result in (gurobi, copt)
        for name in proxy_bound_variables
    )
    return {
        "gurobi": gurobi,
        "copt": copt,
        "independent_integer_enumeration": oracle,
        "solver_only_proxy_bounds": {
            "value": INF,
            "variables": proxy_bound_variables,
            "inactive_at_gurobi_solution": all(
                gurobi.get("assignment", {}).get(name, 0.0) < INF - 1
                for name in proxy_bound_variables
            ),
            "inactive_at_copt_solution": all(
                copt.get("assignment", {}).get(name, 0.0) < INF - 1
                for name in proxy_bound_variables
            ),
            "not_part_of_canonical_ir": True,
        },
        "checks": {
            "gurobi_optimal": gurobi["status"] == "OPTIMAL",
            "copt_optimal": copt["status"] == "OPTIMAL",
            "objectives_agree": objective_agreement,
            "residuals_bounds_integrality_pass": residuals_pass,
            "integer_oracle_agrees_when_attempted": oracle_agreement,
            "solver_only_proxy_bounds_inactive": proxy_bounds_inactive,
            "passed": all_optimal
            and objective_agreement
            and residuals_pass
            and oracle_agreement
            and proxy_bounds_inactive,
        },
    }


def legacy_answer_lookup() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for filename in ("nlp4lp.jsonl", "mamo_complexlp.jsonl"):
        for row in read_jsonl(WORKFLOW_ROOT / "benchmark" / filename):
            result[row["id"]] = row.get("answer")
    return result


def compare_legacy(answer: Any, objective: float) -> dict[str, Any]:
    try:
        old = float(answer)
    except (TypeError, ValueError):
        return {"legacy_answer": answer, "status": "unavailable", "used_as_gold": False}
    delta = objective - old
    return {
        "legacy_answer": old,
        "certified_objective": objective,
        "absolute_difference": abs(delta),
        "status": "match" if abs(delta) <= 1e-2 else "mismatch",
        "used_as_gold": False,
        "comparison_performed_after_model_freeze": True,
    }


def main() -> int:
    candidates = [
        row
        for row in read_jsonl(STAGING_ROOT / "base_candidates.jsonl")
        if row["source_dataset"] in {"NLP4LP", "MAMO-ComplexLP"}
    ]
    specs = supplemental_specs()
    answers = legacy_answer_lookup()
    selected_ids = {row["source_id"] for row in candidates}
    missing_specs = sorted(selected_ids - set(specs))
    extra_specs = sorted(set(specs) - selected_ids)
    if missing_specs:
        raise RuntimeError(f"Missing specs for selected sources: {missing_specs}")

    audit_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        source_id = candidate["source_id"]
        spec = specs[source_id]
        output_dir = OUTPUT_ROOT / candidate["candidate_id"]
        source_snapshot = {
            "candidate_id": candidate["candidate_id"],
            "source_dataset": candidate["source_dataset"],
            "source_id": source_id,
            "source_hash": candidate["source_hash"],
            "problem_text": candidate["problem_zh_or_en"],
            "raw_text_sha256": sha256_text(candidate["problem_zh_or_en"]),
            "normalized_source_sha256_recomputed": normalized_source_sha256(
                candidate["problem_zh_or_en"]
            ),
            "normalized_source_sha256_matches_candidate": (
                normalized_source_sha256(candidate["problem_zh_or_en"])
                == candidate["source_hash"]
            ),
            "legacy_answer_excluded_from_snapshot": True,
            "legacy_code_excluded": True,
        }
        write_json(output_dir / "source_snapshot.json", source_snapshot)

        if spec.get("reject"):
            rejection = {
                "candidate_id": candidate["candidate_id"],
                "source_dataset": candidate["source_dataset"],
                "source_id": source_id,
                "status": "rejected",
                "reason": spec["reject_reason"],
                "details": spec["details"],
                "partial_semantic_mapping": spec.get("partial_mapping", {}),
                "legacy_answer": answers.get(source_id),
                "legacy_answer_used_as_gold": False,
                "model_generated": False,
            }
            write_json(output_dir / "rejection.json", rejection)
            audit_rows.append(rejection)
            continue

        ir = build_ir(candidate, spec)
        mapping = semantic_mapping(candidate, spec)
        certificate = certify(ir)
        comparison = compare_legacy(
            answers.get(source_id),
            certificate["gurobi"].get("objective", float("nan")),
        )
        ir_hash = sha256_json(ir)
        status = "unchanged_pass" if certificate["checks"]["passed"] else "rejected"
        audit = {
            "candidate_id": candidate["candidate_id"],
            "source_dataset": candidate["source_dataset"],
            "source_id": source_id,
            "status": status,
            "source_problem_sha256": candidate["source_hash"],
            "canonical_ir_sha256": ir_hash,
            "semantic_mapping_complete": all(mapping["completeness_check"].values()),
            "single_objective": True,
            "solver_certificate_passed": certificate["checks"]["passed"],
            "gurobi_version": certificate["gurobi"].get("version"),
            "copt_version": certificate["copt"].get("version"),
            "certified_objective": certificate["gurobi"].get("objective"),
            "legacy_answer_comparison": comparison,
            "legacy_code_used": False,
            "legacy_answer_used_as_gold": False,
            "semantic_risks": spec["semantic_risks"],
            "files": {
                "canonical_ir": f"certified_sources/supplemental/{candidate['candidate_id']}/canonical_ir.json",
                "semantic_mapping": f"certified_sources/supplemental/{candidate['candidate_id']}/semantic_mapping.json",
                "solver_certificate": f"certified_sources/supplemental/{candidate['candidate_id']}/solver_certificate.json",
                "source_snapshot": f"certified_sources/supplemental/{candidate['candidate_id']}/source_snapshot.json",
            },
        }
        write_json(output_dir / "canonical_ir.json", ir)
        write_json(output_dir / "semantic_mapping.json", mapping)
        write_json(output_dir / "solver_certificate.json", certificate)
        write_json(output_dir / "audit.json", audit)
        audit_rows.append(audit)

    write_jsonl(AUDIT_PATH, audit_rows)
    counts: dict[str, int] = {}
    for row in audit_rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    mismatch_count = sum(
        1
        for row in audit_rows
        if row.get("legacy_answer_comparison", {}).get("status") == "mismatch"
    )
    summary = {
        "selected_supplemental_count": len(candidates),
        "source_distribution": {
            source: sum(1 for row in candidates if row["source_dataset"] == source)
            for source in sorted({row["source_dataset"] for row in candidates})
        },
        "status_counts": counts,
        "legacy_answer_mismatch_count": mismatch_count,
        "extra_specs_not_selected": extra_specs,
        "all_selected_have_audit": len(audit_rows) == len(candidates),
        "all_pass_rows_dual_solver_certified": all(
            row.get("solver_certificate_passed", False)
            for row in audit_rows
            if row["status"] != "rejected"
        ),
        "formulation_policy": {
            "problem_text_only": True,
            "legacy_code_read": False,
            "legacy_answer_read_after_solve_only": True,
            "no_semantic_change_to_match_answer": True,
        },
    }
    write_json(SUMMARY_PATH, summary)
    artifact_paths = sorted(
        [
            path
            for path in OUTPUT_ROOT.rglob("*")
            if path.is_file()
        ]
        + [AUDIT_PATH, SUMMARY_PATH, Path(__file__).resolve()]
    )
    manifest = {
        "schema_version": "1.0",
        "hash_algorithm": "sha256",
        "self_excluded": True,
        "inputs": {
            str((STAGING_ROOT / "base_candidates.jsonl").relative_to(DATASET_ROOT)).replace("\\", "/"):
                sha256_file(STAGING_ROOT / "base_candidates.jsonl"),
            str((WORKFLOW_ROOT / "benchmark" / "nlp4lp.jsonl").relative_to(WORKFLOW_ROOT)).replace("\\", "/"):
                sha256_file(WORKFLOW_ROOT / "benchmark" / "nlp4lp.jsonl"),
            str((WORKFLOW_ROOT / "benchmark" / "mamo_complexlp.jsonl").relative_to(WORKFLOW_ROOT)).replace("\\", "/"):
                sha256_file(WORKFLOW_ROOT / "benchmark" / "mamo_complexlp.jsonl"),
        },
        "artifacts": {
            (
                str(path.relative_to(DATASET_ROOT)).replace("\\", "/")
                if path.is_relative_to(DATASET_ROOT)
                else str(path)
            ): sha256_file(path)
            for path in artifact_paths
        },
    }
    write_json(MANIFEST_PATH, manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["all_pass_rows_dual_solver_certified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
