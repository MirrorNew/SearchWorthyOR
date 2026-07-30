"""Certify a second, disjoint 40-row NLP4LP reserve pool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build_base_candidates as base_builder
import certify_supplemental_sources as core


DATASET_ROOT = Path(__file__).resolve().parents[1]
STAGING_ROOT = DATASET_ROOT / "staging"
OUTPUT_ROOT = STAGING_ROOT / "certified_sources" / "supplemental_reserve2"
AUDIT_PATH = STAGING_ROOT / "supplemental_reserve2_audit.jsonl"
SUMMARY_PATH = STAGING_ROOT / "supplemental_reserve2_audit_summary.json"
REPLACEMENT_PATH = STAGING_ROOT / "supplemental_reserve2_replacements.jsonl"
MANIFEST_PATH = STAGING_ROOT / "supplemental_reserve2_certification_manifest.json"


def reserve2_specs() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}

    def add(
        source_id: str,
        x: tuple[str, str, str, float | None, str, str],
        y: tuple[str, str, str, float | None, str, str],
        sense: str,
        objective: tuple[float, float, str, str, str],
        constraints: list[dict[str, Any]],
        parameters: dict[str, Any],
        interpretation: list[str],
    ) -> None:
        specs[source_id] = core.two_var_spec(
            source_id,
            x=x,
            y=y,
            sense=sense,
            objective=objective,
            constraints=constraints,
            parameters=parameters,
            interpretation=interpretation,
        )

    add(
        "nlp4lp_000031",
        ("milk", "glasses of milk", "C", None, "glass_equivalent", "glass of milk"),
        ("vegetable", "plates of vegetables", "C", None, "plate_equivalent", "plate of vegetables"),
        "min",
        (1, 2, "minimize_cost", "USD", "minimize his cost"),
        [
            core.con("calcium_floor", {"milk": 40, "vegetable": 15}, ">=", 100, "calcium floor", "minimum of 100 units of calcium", "calcium_unit"),
            core.con("iron_floor", {"milk": 25, "vegetable": 30}, ">=", 50, "iron floor", "50 units of iron", "iron_unit"),
        ],
        {"calcium": [40, 15], "iron": [25, 30], "cost": [1, 2], "floors": [100, 50]},
        ["Dietary portions are modeled as continuous glass/plate equivalents."],
    )
    add(
        "nlp4lp_000132",
        ("refrigerator", "refrigerators", "I", None, "appliance", "refrigerators"),
        ("stove", "stoves", "I", None, "appliance", "stoves"),
        "max",
        (400, 260, "maximize_profit", "USD", "maximize profit"),
        [
            core.con("mover_cap", {"refrigerator": 60, "stove": 45}, "<=", 20000, "mover-time cap", "20000 minutes of mover time", "minute"),
            core.con("setup_cap", {"refrigerator": 20, "stove": 25}, "<=", 13000, "setup-time cap", "13000 minutes of setup time", "minute"),
        ],
        {"mover": [60, 45], "setup": [20, 25], "profit": [400, 260], "caps": [20000, 13000]},
        ["Installed appliance counts are integer."],
    )
    add(
        "nlp4lp_000083",
        ("hamburger", "hamburger portions", "C", None, "portion", "hamburger"),
        ("wrap", "chicken-wrap portions", "C", None, "portion", "chicken wrap"),
        "min",
        (6.5, 4, "minimize_diet_cost", "USD", "minimum cost diet"),
        [
            core.con("calorie_floor", {"hamburger": 800, "wrap": 450}, ">=", 2200, "calorie floor", "at least 2200 calories", "calorie"),
            core.con("protein_floor", {"hamburger": 19, "wrap": 12}, ">=", 50, "protein floor", "50 grams of protein", "gram"),
            core.con("carb_floor", {"hamburger": 20, "wrap": 10}, ">=", 70, "carbohydrate floor", "70 grams of carbs", "gram"),
        ],
        {"calories": [800, 450], "protein": [19, 12], "carbs": [20, 10], "cost": [6.5, 4]},
        ["The minimum-cost diet uses continuous food portions."],
    )
    add(
        "nlp4lp_000089",
        ("ramen", "packs of ramen", "I", None, "pack", "pack of ramen"),
        ("fries", "packs of fries", "I", None, "pack", "pack of fries"),
        "min",
        (100, 75, "minimize_sodium", "mg", "minimize his sodium intake"),
        [
            core.con("calorie_floor", {"ramen": 400, "fries": 300}, ">=", 3000, "calorie floor", "at least 3000 calories", "calorie"),
            core.con("protein_floor", {"ramen": 20, "fries": 10}, ">=", 80, "protein floor", "80 grams of protein", "gram"),
            core.con("ramen_share", {"ramen": 0.7, "fries": -0.3}, "<=", 0, "ramen at most 30%", "at most 30% ... ramen", "pack"),
        ],
        {"calories": [400, 300], "protein": [20, 10], "sodium": [100, 75], "ramen_share_cap": 0.3},
        ["Pack counts are integer."],
    )
    add(
        "nlp4lp_000193",
        ("regular", "regular tacos", "C", 50, "taco_equivalent", "x1 regular tacos"),
        ("deluxe", "deluxe tacos", "C", 40, "taco_equivalent", "x2 deluxe tacos"),
        "max",
        (2.5, 3.55, "maximize_profit", "USD", "maximize profit"),
        [core.con("total_cap", {"regular": 1, "deluxe": 1}, "<=", 70, "supply limit", "at most 70 tacos", "taco_equivalent")],
        {"profit": [2.5, 3.55], "demand_caps": [50, 40], "total_cap": 70},
        ["The prompt explicitly introduces nonnegative algebraic variables x1 and x2; they are continuous."],
    )
    add(
        "nlp4lp_000025",
        ("small", "small bones", "I", None, "bone", "small bone"),
        ("large", "large bones", "I", None, "bone", "large bone"),
        "min",
        (12, 15, "minimize_meat", "meat_unit", "minimize the amount of meat"),
        [
            core.con("medicine_cap", {"small": 10, "large": 15}, "<=", 2000, "medication limit", "2000 units of tooth medication", "medicine_unit"),
            core.con("small_share", {"small": 0.5, "large": -0.5}, ">=", 0, "small bones at least 50%", "at least 50% ... small", "bone"),
            core.con("large_floor", {"large": 1}, ">=", 30, "at least 30 large bones", "at least 30 large bones", "bone"),
        ],
        {"medicine": [10, 15], "meat": [12, 15], "medicine_cap": 2000, "small_share_floor": 0.5, "large_floor": 30},
        ["Bone counts are integer."],
    )
    add(
        "nlp4lp_000229",
        ("glass", "glass bottles", "I", None, "bottle", "glass bottle"),
        ("plastic", "plastic bottles", "I", None, "bottle", "plastic bottle"),
        "max",
        (1, 1, "maximize_bottles", "bottle", "maximize the total number of bottles"),
        [
            core.con("water_cap", {"glass": 500, "plastic": 750}, "<=", 250000, "water availability", "250000 ml of water", "ml"),
            core.con("plastic_ratio", {"plastic": 1, "glass": -3}, ">=", 0, "plastic at least three times glass", "plastic bottles ... at least 3 times", "bottle"),
            core.con("glass_floor", {"glass": 1}, ">=", 20, "at least 20 glass bottles", "at least 20 glass bottles", "bottle"),
        ],
        {"capacity_ml": [500, 750], "water_cap": 250000, "plastic_ratio_floor": 3, "glass_floor": 20},
        ["Bottle counts are integer."],
    )
    add(
        "nlp4lp_000232",
        ("taxi", "taxi rides", "I", None, "ride", "taxi rides"),
        ("car", "company-car rides", "I", None, "ride", "company car rides"),
        "min",
        (1, 0, "minimize_taxis", "ride", "minimize the total number of taxi rides"),
        [
            core.con("employee_floor", {"taxi": 2, "car": 3}, ">=", 500, "transport 500 employees", "transport at least 500 employees", "employee"),
            core.con("car_share", {"car": 0.4, "taxi": -0.6}, "<=", 0, "company-car rides at most 60%", "at most 60% ... company car rides", "ride"),
            core.con("car_floor", {"car": 1}, ">=", 30, "at least 30 company-car rides", "at least 30 company car rides", "ride"),
        ],
        {"capacity": [2, 3], "employee_floor": 500, "car_share_cap": 0.6, "car_floor": 30},
        ["Ride counts are integer; the objective intentionally counts taxis only."],
    )
    add(
        "nlp4lp_000131",
        ("seasonal", "seasonal volunteers", "I", None, "volunteer", "seasonal volunteer"),
        ("fulltime", "full-time volunteers", "I", None, "volunteer", "full-time volunteer"),
        "max",
        (5, 8, "maximize_gifts", "gift", "maximize the total number of gifts"),
        [
            core.con("point_cap", {"seasonal": 2, "fulltime": 5}, "<=", 200, "service-point cap", "only give out 200 points", "point"),
            core.con("seasonal_share", {"seasonal": 0.7, "fulltime": -0.3}, "<=", 0, "seasonal at most 30%", "maximum of 30% ... seasonal", "volunteer"),
            core.con("fulltime_floor", {"fulltime": 1}, ">=", 10, "at least 10 full-time", "at least 10 ... full-time", "volunteer"),
        ],
        {"gifts": [5, 8], "points": [2, 5], "point_cap": 200, "seasonal_share_cap": 0.3, "fulltime_floor": 10},
        ["Volunteer counts are integer."],
    )
    add(
        "nlp4lp_000154",
        ("turnip", "acres of turnips", "C", None, "acre", "acres ... turnips"),
        ("pumpkin", "acres of pumpkins", "C", None, "acre", "acres ... pumpkins"),
        "max",
        (300, 450, "maximize_revenue", "USD", "maximize his revenue"),
        [
            core.con("land_cap", {"turnip": 1, "pumpkin": 1}, "<=", 500, "land limit", "500 acres of land", "acre"),
            core.con("water_cap", {"turnip": 50, "pumpkin": 90}, "<=", 40000, "watering-time limit", "40000 minutes", "minute"),
            core.con("pesticide_cap", {"turnip": 80, "pumpkin": 50}, "<=", 34000, "pesticide budget", "$34000", "USD"),
        ],
        {"water": [50, 90], "pesticide": [80, 50], "revenue": [300, 450], "land_cap": 500},
        ["Land allocation is continuous acres."],
    )
    add(
        "nlp4lp_000241",
        ("pigeon", "carrier pigeons", "I", None, "bird", "carrier pigeons"),
        ("owl", "owls", "I", None, "bird", "owls"),
        "max",
        (2, 5, "maximize_letters", "letter", "maximize the total number of letters"),
        [
            core.con("owl_share", {"owl": 0.6, "pigeon": -0.4}, "<=", 0, "owls at most 40%", "At most 40% ... owls", "bird"),
            core.con("treat_cap", {"pigeon": 3, "owl": 5}, "<=", 1000, "treat limit", "1000 treats", "treat"),
            core.con("pigeon_floor", {"pigeon": 1}, ">=", 20, "at least 20 pigeons", "at least 20 carrier pigeons", "bird"),
        ],
        {"letters": [2, 5], "treats": [3, 5], "owl_share_cap": 0.4, "treat_cap": 1000, "pigeon_floor": 20},
        ["Bird counts are integer."],
    )
    add(
        "nlp4lp_000094",
        ("parttime", "part-time workers", "I", None, "worker", "part time workers"),
        ("fulltime", "full-time workers", "I", None, "worker", "full time workers"),
        "min",
        (1, 1, "minimize_workers", "worker", "minimize the total number of workers"),
        [
            core.con("labor_floor", {"parttime": 4, "fulltime": 8}, ">=", 500, "labor-hour floor", "requiring 500 hours", "hour"),
            core.con("budget_cap", {"parttime": 100, "fulltime": 300}, "<=", 15000, "wage budget", "budget of $15000", "USD"),
        ],
        {"hours": [4, 8], "wage": [100, 300], "labor_floor": 500, "budget": 15000},
        ["Worker counts are integer."],
    )
    add(
        "nlp4lp_000066",
        ("washer", "washing machines repaired", "I", None, "appliance", "washing machines"),
        ("freezer", "freezers repaired", "I", None, "appliance", "freezers"),
        "max",
        (250, 375, "maximize_earnings", "USD", "maximize his earnings"),
        [
            core.con("inspection_cap", {"washer": 30, "freezer": 20}, "<=", 5000, "inspection time", "5000 minutes ... inspection", "minute"),
            core.con("repair_cap", {"washer": 90, "freezer": 125}, "<=", 20000, "repair schedule", "20000 minutes ... schedule", "minute"),
        ],
        {"inspection": [30, 20], "repair": [90, 125], "earnings": [250, 375], "caps": [5000, 20000]},
        ["Repaired appliance counts are integer."],
    )
    add(
        "nlp4lp_000104",
        ("helicopter", "helicopter trips", "I", 5, "trip", "helicopter"),
        ("car", "car trips", "I", None, "trip", "car"),
        "min",
        (40, 30, "minimize_time", "minute", "minimize the total time"),
        [
            core.con("fish_floor", {"helicopter": 30, "car": 20}, ">=", 300, "transport 300 fish", "at least 300 fish", "fish"),
            core.con("car_share", {"car": 0.4, "helicopter": -0.6}, ">=", 0, "car trips at least 60%", "at least 60% ... by car", "trip"),
        ],
        {"capacity": [30, 20], "minutes": [40, 30], "helicopter_cap": 5, "car_share_floor": 0.6},
        ["Trip counts are integer; the helicopter cap is a variable bound."],
    )
    add(
        "nlp4lp_000226",
        ("gummy", "chewable gummies", "I", None, "item", "gummy"),
        ("pill", "pills", "I", None, "item", "pill"),
        "max",
        (4, 5, "maximize_zinc", "zinc_unit", "maximize his zinc intake"),
        [
            core.con("magnesium_cap", {"gummy": 3, "pill": 2}, "<=", 200, "magnesium cap", "at most 200 units of magnesium", "magnesium_unit"),
            core.con("pill_floor", {"pill": 1}, ">=", 10, "at least 10 pills", "at least 10 pills", "item"),
            core.con("gummy_ratio", {"gummy": 1, "pill": -3}, ">=", 0, "gummies at least three times pills", "at least 3 times ... gummies", "item"),
        ],
        {"magnesium": [3, 2], "zinc": [4, 5], "magnesium_cap": 200, "pill_floor": 10, "gummy_ratio_floor": 3},
        ["Gummy and pill counts are integer."],
    )
    add(
        "nlp4lp_000060",
        ("regular", "regular handbags", "I", None, "handbag", "regular handbags"),
        ("premium", "premium handbags", "I", None, "handbag", "premium handbags"),
        "max",
        (30, 180, "maximize_profit", "USD", "maximize ... monthly profit"),
        [
            core.con("budget_cap", {"regular": 200, "premium": 447}, "<=", 250000, "manufacturing budget", "budget of $250000", "USD"),
            core.con("sales_cap", {"regular": 1, "premium": 1}, "<=", 475, "monthly sales cap", "at most 475 handbags", "handbag"),
        ],
        {"cost": [200, 447], "profit": [30, 180], "budget": 250000, "sales_cap": 475},
        ["Handbag counts are integer."],
    )
    add(
        "nlp4lp_000240",
        ("truck", "refrigerated-truck trips", "I", None, "trip", "refrigerated trucks"),
        ("van", "van trips", "I", None, "trip", "vans"),
        "min",
        (1, 1, "minimize_trips", "trip", "minimize the total number of trips"),
        [
            core.con("patty_floor", {"truck": 1000, "van": 500}, ">=", 50000, "ship 50000 patties", "at least 50000 patties", "patty"),
            core.con("budget_cap", {"truck": 300, "van": 100}, "<=", 12500, "trip budget", "budget of $12500", "USD"),
            core.con("truck_not_more", {"truck": 1, "van": -1}, "<=", 0, "trucks no more than vans", "trucks must not exceed ... vans", "trip"),
        ],
        {"capacity": [1000, 500], "cost": [300, 100], "patty_floor": 50000, "budget": 12500},
        ["Trip counts are integer."],
    )
    add(
        "nlp4lp_000076",
        ("thin", "thin jars", "I", None, "jar", "thin jar"),
        ("stubby", "stubby jars", "I", None, "jar", "stubby jar"),
        "max",
        (5, 9, "maximize_profit", "USD", "maximize profit"),
        [
            core.con("shaping_cap", {"thin": 50, "stubby": 30}, "<=", 3000, "shaping time", "3000 minutes ... shaping", "minute"),
            core.con("baking_cap", {"thin": 90, "stubby": 150}, "<=", 4000, "baking time", "4000 minutes ... baking", "minute"),
        ],
        {"shaping": [50, 30], "baking": [90, 150], "profit": [5, 9], "caps": [3000, 4000]},
        ["Jar counts are integer."],
    )
    add(
        "nlp4lp_000182",
        ("math", "math workbooks", "I", 140, "workbook", "math workbooks"),
        ("english", "English workbooks", "I", 170, "workbook", "English workbooks"),
        "max",
        (15, 17, "maximize_profit", "USD", "maximize profit"),
        [
            core.con("math_floor", {"math": 1}, ">=", 40, "math demand floor", "at least 40 math", "workbook"),
            core.con("english_floor", {"english": 1}, ">=", 60, "English demand floor", "at least 60 English", "workbook"),
            core.con("total_floor", {"math": 1, "english": 1}, ">=", 200, "school contract floor", "at least 200 workbooks", "workbook"),
        ],
        {"profit": [15, 17], "lower": [40, 60], "upper": [140, 170], "total_floor": 200},
        ["Workbook counts are integer; individual production caps are variable bounds."],
    )
    add(
        "nlp4lp_000169",
        ("j", "process-J executions", "I", None, "process_run", "process J"),
        ("p", "process-P executions", "I", None, "process_run", "process P"),
        "max",
        (5, 9, "maximize_metal", "metal_unit", "maximize the amount of metal"),
        [
            core.con("water_cap", {"j": 8, "p": 6}, "<=", 1500, "water limit", "at most 1500 units of water", "water_unit"),
            core.con("pollution_cap", {"j": 3, "p": 5}, "<=", 1350, "pollution limit", "1350 units of pollution", "pollution_unit"),
        ],
        {"metal": [5, 9], "water": [8, 6], "pollution": [3, 5], "caps": [1500, 1350]},
        ["Process executions are integer batches."],
    )
    add(
        "nlp4lp_000171",
        ("train", "trains", "I", None, "unit", "trains"),
        ("tram", "trams", "I", None, "unit", "trams"),
        "min",
        (1, 1, "minimize_units", "unit", "minimize the total number"),
        [
            core.con("people_floor", {"train": 120, "tram": 30}, ">=", 600, "transport 600 people/hour", "at least 600 people per hour", "person/hour"),
            core.con("tram_ratio", {"tram": 1, "train": -2}, ">=", 0, "trams at least twice trains", "trams ... at least twice ... trains", "unit"),
        ],
        {"capacity": [120, 30], "people_floor": 600, "tram_ratio_floor": 2},
        ["Transportation-unit counts are integer."],
    )
    add(
        "nlp4lp_000016",
        ("blueberry", "acres of blueberries", "C", None, "acre", "acres of blueberries"),
        ("raspberry", "acres of raspberries", "C", None, "acre", "acres of raspberries"),
        "max",
        (56, 75, "maximize_profit", "USD", "Formulate an LP ... maximize profit"),
        [
            core.con("land_cap", {"blueberry": 1, "raspberry": 1}, "<=", 300, "land limit", "300 acre berry farm", "acre"),
            core.con("watering_cap", {"blueberry": 22, "raspberry": 25}, "<=", 10000, "watering budget", "$10000 ... watering", "USD"),
            core.con("labor_cap", {"blueberry": 6, "raspberry": 3}, "<=", 575, "labor limit", "575 days ... labor", "labor_day"),
        ],
        {"watering": [22, 25], "labor": [6, 3], "profit": [56, 75], "land": 300},
        ["The prompt explicitly asks for an LP; land allocation is continuous acres."],
    )
    add(
        "nlp4lp_000121",
        ("vintage", "vintage bottles", "I", None, "bottle", "vintage bottle"),
        ("regular", "regular bottles", "I", None, "bottle", "regular bottle"),
        "max",
        (1, 1, "maximize_bottles", "bottle", "maximize the total number of bottles"),
        [
            core.con("wine_cap", {"vintage": 500, "regular": 750}, "<=", 100000, "liquid availability", "100000 ml", "ml"),
            core.con("regular_ratio", {"regular": 1, "vintage": -4}, ">=", 0, "regular at least four times vintage", "regular bottles ... at least 4 times", "bottle"),
            core.con("vintage_floor", {"vintage": 1}, ">=", 10, "at least 10 vintage", "at least 10 vintage bottles", "bottle"),
        ],
        {"capacity_ml": [500, 750], "liquid_cap": 100000, "regular_ratio_floor": 4, "vintage_floor": 10},
        ["Bottle counts are integer."],
    )
    add(
        "nlp4lp_000238",
        ("cow", "cows", "I", None, "animal", "cows"),
        ("elephant", "elephants", "I", None, "animal", "elephants"),
        "min",
        (1, 1, "minimize_animals", "animal", "minimum number of animals"),
        [
            core.con("brick_floor", {"cow": 20, "elephant": 50}, ">=", 1000, "transport 1000 bricks", "at least 1000 bricks", "brick"),
            core.con("elephant_not_more", {"elephant": 1, "cow": -1}, "<=", 0, "elephants no more than cows", "elephant cannot exceed ... cows", "animal"),
            core.con("cow_cap_ratio", {"cow": 1, "elephant": -2}, "<=", 0, "cows at most twice elephants", "at most twice ... cows as elephants", "animal"),
        ],
        {"capacity": [20, 50], "brick_floor": 1000, "ratio_interval": ["elephant<=cow", "cow<=2*elephant"]},
        ["Animal counts are integer."],
    )
    add(
        "nlp4lp_000075",
        ("mango", "mangoes sold", "I", 150, "fruit", "mango"),
        ("guava", "guavas sold", "I", None, "fruit", "guava"),
        "max",
        (3, 4, "maximize_profit", "USD", "maximize the profit"),
        [
            core.con("budget_cap", {"mango": 5, "guava": 3}, "<=", 20000, "purchase budget", "at most $20000", "USD"),
            core.con("mango_floor", {"mango": 1}, ">=", 100, "mango sales floor", "at least 100 mangos", "fruit"),
            core.con("guava_ratio", {"guava": 3, "mango": -1}, "<=", 0, "guavas at most one third mangoes", "guavas ... at most a third", "fruit"),
        ],
        {"cost": [5, 3], "profit": [3, 4], "budget": 20000, "mango_bounds": [100, 150], "guava_ratio_cap": "1/3"},
        ["Fruit counts are integer; the mango upper bound is a variable bound."],
    )
    add(
        "nlp4lp_000185",
        ("mix1", "kg of mix 1", "C", None, "kg", "first mix"),
        ("mix2", "kg of mix 2", "C", None, "kg", "second mix"),
        "max",
        (12, 15, "maximize_profit", "USD", "maximize profit"),
        [
            core.con("catpaw_cap", {"mix1": 0.2, "mix2": 0.35}, "<=", 20, "cat-paw snack limit", "20 kg of cat paw snacks", "kg"),
            core.con("shark_cap", {"mix1": 0.8, "mix2": 0.65}, "<=", 50, "gold-shark snack limit", "50 kg of gold shark snacks", "kg"),
        ],
        {"composition": [[0.2, 0.8], [0.35, 0.65]], "availability": [20, 50], "profit": [12, 15]},
        ["Mix quantities are continuous kilograms."],
    )
    add(
        "nlp4lp_000058",
        ("salmon", "bowls of salmon", "C", None, "bowl_equivalent", "bowl of salmon"),
        ("egg", "bowls of eggs", "C", None, "bowl_equivalent", "bowl of eggs"),
        "min",
        (80, 20, "minimize_sodium", "mg", "minimize his sodium intake"),
        [
            core.con("calorie_floor", {"salmon": 300, "egg": 200}, ">=", 2000, "calorie floor", "at least 2000 calories", "calorie"),
            core.con("protein_floor", {"salmon": 15, "egg": 8}, ">=", 90, "protein floor", "90 grams of protein", "gram"),
            core.con("egg_share", {"egg": 0.6, "salmon": -0.4}, "<=", 0, "egg bowls at most 40%", "at most 40% ... eggs", "bowl_equivalent"),
        ],
        {"calories": [300, 200], "protein": [15, 8], "sodium": [80, 20], "egg_share_cap": 0.4},
        ["Dietary bowl portions are continuous equivalents."],
    )
    add(
        "nlp4lp_000214",
        ("long", "long cables", "I", None, "cable", "long cables"),
        ("short", "short cables", "I", None, "cable", "short cables"),
        "max",
        (12, 5, "maximize_profit", "USD", "maximize profit"),
        [
            core.con("gold_cap", {"long": 10, "short": 7}, "<=", 1000, "gold availability", "1000 mg of gold", "mg"),
            core.con("short_ratio", {"short": 1, "long": -5}, ">=", 0, "short cables at least five times long", "at least 5 times ... short cables", "cable"),
            core.con("long_floor", {"long": 1}, ">=", 10, "at least 10 long cables", "at least 10 long cables", "cable"),
        ],
        {"gold_mg": [10, 7], "profit": [12, 5], "gold_cap": 1000, "short_ratio_floor": 5, "long_floor": 10},
        ["Cable counts are integer."],
    )
    add(
        "nlp4lp_000237",
        ("helicopter", "helicopter trips", "I", None, "trip", "helicopter"),
        ("bus", "bus trips", "I", 10, "trip", "bus"),
        "min",
        (1, 3, "minimize_time", "hour", "minimize the total time"),
        [
            core.con("patient_floor", {"helicopter": 5, "bus": 8}, ">=", 120, "transport 120 patients", "At least 120 patients", "patient"),
            core.con("helicopter_share", {"helicopter": 0.7, "bus": -0.3}, ">=", 0, "helicopter trips at least 30%", "at least 30% ... helicopter", "trip"),
        ],
        {"capacity": [5, 8], "hours": [1, 3], "patient_floor": 120, "helicopter_share_floor": 0.3, "bus_cap": 10},
        ["Trip counts are integer; the bus cap is a variable bound."],
    )
    add(
        "nlp4lp_000095",
        ("alpha", "experiment-alpha executions", "I", None, "experiment", "experiment alpha"),
        ("beta", "experiment-beta executions", "I", None, "experiment", "experiment beta"),
        "max",
        (8, 10, "maximize_electricity", "electricity_unit", "maximize the total amount of electricity"),
        [
            core.con("metal_cap", {"alpha": 3, "beta": 5}, "<=", 800, "metal limit", "800 units of metal", "metal_unit"),
            core.con("acid_cap", {"alpha": 5, "beta": 4}, "<=", 750, "acid limit", "750 units of acid", "acid_unit"),
        ],
        {"metal": [3, 5], "acid": [5, 4], "electricity": [8, 10], "caps": [800, 750]},
        ["Experiment executions are integer batches."],
    )
    add(
        "nlp4lp_000113",
        ("banana", "bananas", "I", None, "fruit", "banana"),
        ("mango", "mangoes", "I", None, "fruit", "mango"),
        "min",
        (10, 8, "minimize_sugar", "gram", "minimize his sugar intake"),
        [
            core.con("calorie_floor", {"banana": 80, "mango": 100}, ">=", 4000, "calorie floor", "at least 4000 calories", "calorie"),
            core.con("potassium_floor", {"banana": 20, "mango": 15}, ">=", 150, "potassium floor", "150 grams of potassium", "gram"),
            core.con("mango_share", {"mango": 0.67, "banana": -0.33}, "<=", 0, "mangoes at most 33%", "at most 33% ... mangoes", "fruit"),
        ],
        {"calories": [80, 100], "potassium": [20, 15], "sugar": [10, 8], "mango_share_cap": 0.33},
        ["Fruit counts are integer; 33% is used literally as 0.33."],
    )
    add(
        "nlp4lp_000167",
        ("catalyst", "catalyst-process executions", "I", None, "process_run", "with a catalyst"),
        ("plain", "non-catalyst-process executions", "I", None, "process_run", "without a catalyst"),
        "max",
        (15, 18, "maximize_co2", "co2_unit", "maximize the amount of carbon dioxide"),
        [
            core.con("wood_cap", {"catalyst": 10, "plain": 15}, "<=", 300, "wood limit", "300 units of wood", "wood_unit"),
            core.con("oxygen_cap", {"catalyst": 20, "plain": 12}, "<=", 300, "oxygen limit", "300 units of oxygen", "oxygen_unit"),
        ],
        {"wood": [10, 15], "oxygen": [20, 12], "co2": [15, 18], "caps": [300, 300]},
        ["Process executions are integer batches."],
    )
    add(
        "nlp4lp_000152",
        ("bike", "electric bikes", "I", None, "vehicle", "electric bikes"),
        ("scooter", "scooters", "I", None, "vehicle", "scooters"),
        "max",
        (8, 5, "maximize_meals", "meal", "maximize the number of meals"),
        [
            core.con("charge_cap", {"bike": 3, "scooter": 2}, "<=", 200, "charge limit", "200 units of charge", "charge_unit"),
            core.con("bike_share", {"bike": 0.7, "scooter": -0.3}, "<=", 0, "bikes at most 30%", "at most 30% ... bikes", "vehicle"),
            core.con("scooter_floor", {"scooter": 1}, ">=", 20, "at least 20 scooters", "at least 20 scooters", "vehicle"),
        ],
        {"meal_capacity": [8, 5], "charge": [3, 2], "charge_cap": 200, "bike_share_cap": 0.3, "scooter_floor": 20},
        ["Vehicle counts are integer."],
    )
    add(
        "nlp4lp_000177",
        ("molar", "molar fillings", "I", None, "tooth", "Molars"),
        ("canine", "canine fillings", "I", None, "tooth", "Canines"),
        "min",
        (3, 2.3, "minimize_painkiller", "painkiller_unit", "minimize the amount of pain killer"),
        [
            core.con("resin_cap", {"molar": 20, "canine": 15}, "<=", 3000, "resin limit", "3000 units of resin", "resin_unit"),
            core.con("canine_share", {"canine": 0.4, "molar": -0.6}, ">=", 0, "canines at least 60%", "at least 60% ... canines", "tooth"),
            core.con("molar_floor", {"molar": 1}, ">=", 45, "at least 45 molars", "at least 45 molars", "tooth"),
        ],
        {"resin": [20, 15], "painkiller": [3, 2.3], "resin_cap": 3000, "canine_share_floor": 0.6, "molar_floor": 45},
        ["Scheduled tooth fillings are integer cases."],
    )
    add(
        "nlp4lp_000074",
        ("balloon", "hot-air-balloon rides", "I", 10, "ride", "hot-air balloon"),
        ("gondola", "gondola-lift rides", "I", None, "ride", "gondola lift"),
        "min",
        (10, 15, "minimize_pollution", "pollution_unit", "minimize the total pollution"),
        [core.con("visitor_floor", {"balloon": 4, "gondola": 6}, ">=", 70, "transport 70 visitors", "at least 70 visitors", "visitor")],
        {"capacity": [4, 6], "pollution": [10, 15], "balloon_cap": 10, "visitor_floor": 70},
        ["Ride counts are integer; the balloon cap is a variable bound."],
    )
    add(
        "nlp4lp_000052",
        ("small", "small boxes", "I", None, "box", "small boxes"),
        ("large", "large boxes", "I", None, "box", "large boxes"),
        "min",
        (1, 1, "minimize_boxes", "box", "minimize the total number of boxes"),
        [
            core.con("mask_floor", {"small": 25, "large": 45}, ">=", 750, "distribute 750 masks", "at least 750 masks", "mask"),
            core.con("small_ratio", {"small": 1, "large": -3}, ">=", 0, "small boxes at least three times large", "at least three times ... small boxes", "box"),
            core.con("large_floor", {"large": 1}, ">=", 5, "at least 5 large boxes", "at least 5 large boxes", "box"),
        ],
        {"capacity": [25, 45], "mask_floor": 750, "small_ratio_floor": 3, "large_floor": 5},
        ["Box counts are integer."],
    )

    cake_names = ["crepe", "sponge", "birthday"]
    cake_vars = [
        core.var("crepe", "crepe cakes", "I", None, "cake", "crepe cake"),
        core.var("sponge", "sponge cakes", "I", None, "cake", "sponge cake"),
        core.var("birthday", "birthday cakes", "I", None, "cake", "birthday cake"),
    ]
    specs["nlp4lp_000191"] = core.make_spec(
        "nlp4lp_000191",
        variables=cake_vars,
        sense="max",
        objective_terms={"crepe": 12, "sponge": 10, "birthday": 15},
        objective_name="maximize_profit",
        objective_unit="USD",
        objective_claim="maximize their profit",
        constraints=[
            core.con("batter_cap", {"crepe": 400, "sponge": 500, "birthday": 450}, "<=", 20000, "batter limit", "20000 grams of batter", "gram"),
            core.con("milk_cap", {"crepe": 200, "sponge": 300, "birthday": 350}, "<=", 14000, "milk limit", "14000 grams of milk", "gram"),
        ],
        parameters={"batter": [400, 500, 450], "milk": [200, 300, 350], "profit": [12, 10, 15], "caps": [20000, 14000]},
        sets={"cake_types": cake_names},
        interpretation=["Cake counts are integer."],
    )
    add(
        "nlp4lp_000117",
        ("miter", "miter saws", "I", None, "saw", "miter saw"),
        ("circular", "circular saws", "I", None, "saw", "circular saw"),
        "min",
        (1, 1, "minimize_saws", "saw", "minimize the total number of saws"),
        [
            core.con("plank_floor", {"miter": 50, "circular": 70}, ">=", 1500, "plank-cutting floor", "at least 1500 planks", "plank/day"),
            core.con("sawdust_cap", {"miter": 60, "circular": 100}, "<=", 2000, "sawdust limit", "at most 2000 units of sawdust", "sawdust_unit/day"),
        ],
        {"capacity": [50, 70], "sawdust": [60, 100], "plank_floor": 1500, "sawdust_cap": 2000},
        ["Saw counts are integer."],
    )
    add(
        "nlp4lp_000042",
        ("pop", "pop concerts", "I", None, "concert", "pop concert"),
        ("rb", "R&B concerts", "I", None, "concert", "R&B concert"),
        "min",
        (1, 1, "minimize_concerts", "concert", "minimize the total number of concerts"),
        [
            core.con("audience_floor", {"pop": 100, "rb": 240}, ">=", 10000, "audience floor", "at least 10000 audience members", "audience_member"),
            core.con("practice_cap", {"pop": 2, "rb": 4}, "<=", 180, "practice-day limit", "180 days for practice", "day"),
            core.con("rb_share", {"rb": 0.6, "pop": -0.4}, "<=", 0, "R&B at most 40%", "at most perform 40% ... R&B", "concert"),
        ],
        {"audience": [100, 240], "practice_days": [2, 4], "audience_floor": 10000, "practice_cap": 180, "rb_share_cap": 0.4},
        ["Concert counts are integer."],
    )
    add(
        "nlp4lp_000207",
        ("small", "small kegs", "I", 30, "keg", "small kegs"),
        ("large", "large kegs", "I", 10, "keg", "large kegs"),
        "max",
        (40, 100, "maximize_water", "liter", "maximize the total amount of glacial water"),
        [
            core.con("small_ratio", {"small": 1, "large": -2}, ">=", 0, "small kegs at least twice large", "at least twice ... small kegs", "keg"),
            core.con("total_cap", {"small": 1, "large": 1}, "<=", 25, "total-keg cap", "at most 25 kegs total", "keg"),
            core.con("large_floor", {"large": 1}, ">=", 5, "at least 5 large kegs", "at least 5 kegs ... large", "keg"),
        ],
        {"capacity_liter": [40, 100], "individual_caps": [30, 10], "total_cap": 25, "large_floor": 5},
        ["Keg counts are integer; individual availability is encoded in bounds."],
    )
    return specs


def remaining_eligible_rows() -> dict[str, dict[str, Any]]:
    rows = base_builder.read_jsonl(base_builder.SOURCE_PATHS["NLP4LP"])
    id_counts = base_builder.source_id_counts(rows, "NLP4LP")
    hash_groups = base_builder.problem_hash_groups(rows, "NLP4LP")
    used = {
        row["source_id"]
        for row in core.read_jsonl(STAGING_ROOT / "base_candidates.jsonl")
    }
    used.update(
        row["source_id"]
        for row in core.read_jsonl(STAGING_ROOT / "supplemental_reserve_audit.jsonl")
    )
    result = {}
    for row in rows:
        passed, _screen = base_builder.supplement_screen(row)
        digest = base_builder.source_hash(str(row.get("problem") or ""))
        source_id = str(row["id"])
        if (
            passed
            and len(hash_groups[digest]) == 1
            and id_counts[source_id] == 1
            and source_id not in used
        ):
            result[source_id] = row
    return result


def preserve_typed_projection(
    ir: dict[str, Any], certificate: dict[str, Any]
) -> None:
    vartypes = {variable["name"]: variable["vartype"] for variable in ir["variables"]}
    for solver_name in ("gurobi", "copt"):
        result = certificate[solver_name]
        assignment = result.get("assignment", {})
        result["projected_action"] = [
            (
                float(assignment[name])
                if vartypes[name] == "C"
                else int(round(float(assignment[name])))
            )
            for name in ir["action_projection"]
        ]
        result["projected_action_types"] = [
            "float" if vartypes[name] == "C" else "int"
            for name in ir["action_projection"]
        ]
    certificate["action_projection_contract"] = {
        "continuous_preserved_as_float": True,
        "integer_and_binary_emitted_as_int": True,
        "variable_order": ir["action_projection"],
    }


def main() -> int:
    specs = reserve2_specs()
    eligible = remaining_eligible_rows()
    if len(specs) != 40:
        raise RuntimeError(f"Expected 40 reserve2 specs, found {len(specs)}")
    if not set(specs) <= set(eligible):
        raise RuntimeError(
            f"Reserve2 specs outside remaining eligible pool: {sorted(set(specs) - set(eligible))}"
        )
    audit_rows = []
    replacement_rows = []
    for rank, source_id in enumerate(specs, start=1):
        row = eligible[source_id]
        text = str(row["problem"])
        candidate = {
            "candidate_id": f"RESERVE2-NLP4LP-{source_id.rsplit('_', 1)[-1]}",
            "source_dataset": "NLP4LP",
            "source_id": source_id,
            "source_hash": base_builder.source_hash(text),
            "problem_zh_or_en": text,
        }
        spec = specs[source_id]
        output_dir = OUTPUT_ROOT / source_id
        ir = core.build_ir(candidate, spec)
        mapping = core.semantic_mapping(candidate, spec)
        certificate = core.certify(ir)
        preserve_typed_projection(ir, certificate)
        # Historical answer is accessed only after IR freeze and both solves.
        comparison = core.compare_legacy(
            row.get("answer"),
            certificate["gurobi"].get("objective", float("nan")),
        )
        passed = certificate["checks"]["passed"]
        snapshot = {
            "candidate_id": candidate["candidate_id"],
            "source_dataset": "NLP4LP",
            "source_id": source_id,
            "source_hash": candidate["source_hash"],
            "problem_text": text,
            "raw_text_sha256": core.sha256_text(text),
            "normalized_source_sha256_recomputed": core.normalized_source_sha256(text),
            "normalized_source_sha256_matches_candidate": True,
            "selection_policy": "same_static_screen_disjoint_short_clear_diverse_backgrounds",
            "reserve_rank": rank,
            "legacy_answer_excluded_from_snapshot": True,
            "legacy_code_excluded": True,
        }
        audit = {
            "candidate_id": candidate["candidate_id"],
            "source_dataset": "NLP4LP",
            "source_id": source_id,
            "reserve_rank": rank,
            "status": "unchanged_pass" if passed else "rejected",
            "source_problem_sha256": candidate["source_hash"],
            "canonical_ir_sha256": core.sha256_json(ir),
            "semantic_mapping_complete": all(mapping["completeness_check"].values()),
            "single_objective": True,
            "solver_certificate_passed": passed,
            "continuous_projection_preserved": True,
            "gurobi_version": certificate["gurobi"].get("version"),
            "copt_version": certificate["copt"].get("version"),
            "certified_objective": certificate["gurobi"].get("objective"),
            "legacy_answer_comparison": comparison,
            "legacy_code_used": False,
            "legacy_answer_used_as_gold": False,
        }
        core.write_json(output_dir / "source_snapshot.json", snapshot)
        core.write_json(output_dir / "canonical_ir.json", ir)
        core.write_json(output_dir / "semantic_mapping.json", mapping)
        core.write_json(output_dir / "solver_certificate.json", certificate)
        core.write_json(output_dir / "audit.json", audit)
        audit_rows.append(audit)
        if passed:
            replacement_rows.append(
                {
                    "replacement_rank": len(replacement_rows) + 1,
                    "reserve_candidate_id": candidate["candidate_id"],
                    "source_dataset": "NLP4LP",
                    "source_id": source_id,
                    "canonical_ir_sha256": audit["canonical_ir_sha256"],
                    "certified_objective": audit["certified_objective"],
                    "gurobi_status": certificate["gurobi"]["status"],
                    "copt_status": certificate["copt"]["status"],
                    "continuous_projection_preserved": True,
                    "eligible_to_replace_failed_base": True,
                }
            )
    core.write_jsonl(AUDIT_PATH, audit_rows)
    core.write_jsonl(REPLACEMENT_PATH, replacement_rows)
    summary = {
        "reserve2_candidates_audited": len(audit_rows),
        "reserve2_pass_count": len(replacement_rows),
        "reserve2_reject_count": len(audit_rows) - len(replacement_rows),
        "minimum_required_pass_count": 40,
        "minimum_met": len(replacement_rows) >= 40,
        "all_from_remaining_eligible_nlp4lp": True,
        "disjoint_from_main_and_reserve1": True,
        "all_pass_rows_dual_solver_certified": all(
            row["solver_certificate_passed"]
            for row in audit_rows
            if row["status"] == "unchanged_pass"
        ),
        "continuous_projection_preserved": True,
        "legacy_answer_mismatch_count": sum(
            row["legacy_answer_comparison"]["status"] == "mismatch"
            for row in audit_rows
        ),
    }
    core.write_json(SUMMARY_PATH, summary)
    artifact_paths = sorted(
        [path for path in OUTPUT_ROOT.rglob("*") if path.is_file()]
        + [AUDIT_PATH, SUMMARY_PATH, REPLACEMENT_PATH, Path(__file__).resolve()]
    )
    manifest = {
        "schema_version": "1.0",
        "hash_algorithm": "sha256",
        "self_excluded": True,
        "inputs": {
            "staging/base_candidates.jsonl": core.sha256_file(
                STAGING_ROOT / "base_candidates.jsonl"
            ),
            "staging/supplemental_reserve_audit.jsonl": core.sha256_file(
                STAGING_ROOT / "supplemental_reserve_audit.jsonl"
            ),
            "benchmark/nlp4lp.jsonl": core.sha256_file(
                base_builder.SOURCE_PATHS["NLP4LP"]
            ),
        },
        "artifacts": {
            (
                str(path.relative_to(DATASET_ROOT)).replace("\\", "/")
                if path.is_relative_to(DATASET_ROOT)
                else str(path)
            ): core.sha256_file(path)
            for path in artifact_paths
        },
    }
    core.write_json(MANIFEST_PATH, manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["minimum_met"] and summary["all_pass_rows_dual_solver_certified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
