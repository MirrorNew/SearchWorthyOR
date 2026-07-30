"""Build a provenance-safe reserve pool from unselected NLP4LP rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build_base_candidates as base_builder
import certify_supplemental_sources as core


DATASET_ROOT = Path(__file__).resolve().parents[1]
STAGING_ROOT = DATASET_ROOT / "staging"
OUTPUT_ROOT = STAGING_ROOT / "certified_sources" / "supplemental_reserve"
AUDIT_PATH = STAGING_ROOT / "supplemental_reserve_audit.jsonl"
SUMMARY_PATH = STAGING_ROOT / "supplemental_reserve_audit_summary.json"
REPLACEMENT_PATH = STAGING_ROOT / "supplemental_reserve_replacements.jsonl"
MANIFEST_PATH = STAGING_ROOT / "supplemental_reserve_certification_manifest.json"


def reserve_specs() -> dict[str, dict[str, Any]]:
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
        "nlp4lp_000033",
        ("scooter", "scooters", "I", None, "vehicle", "either by scooter or rickshaw"),
        ("rickshaw", "rickshaws", "I", None, "vehicle", "either by scooter or rickshaw"),
        "min",
        (1, 0, "minimize_scooters", "scooter", "minimize the total number of scooters used"),
        [
            core.con("visitor_floor", {"scooter": 2, "rickshaw": 3}, ">=", 300, "transport at least 300 visitors", "transport at least 300 visitors", "visitor"),
            core.con("rickshaw_share", {"rickshaw": 0.6, "scooter": -0.4}, "<=", 0, "rickshaws at most 40%", "at most 40% of the vehicles ... rickshaws", "vehicle"),
        ],
        {"capacity": [2, 3], "visitor_floor": 300, "rickshaw_share_cap": 0.4},
        ["Vehicle counts are integer. The objective intentionally counts scooters only."],
    )
    add(
        "nlp4lp_000080",
        ("chair", "chairs", "I", None, "item", "chair produced"),
        ("dresser", "dressers", "I", None, "item", "every dresser"),
        "max",
        (43, 52, "maximize_profit", "USD", "Determine the maximum profit"),
        [
            core.con("stain_cap", {"chair": 1.4, "dresser": 1.1}, "<=", 17, "stain limit", "17 gallons of stain", "gallon"),
            core.con("wood_cap", {"chair": 2, "dresser": 3}, "<=", 11, "wood limit", "11 lengths of oak wood", "wood_length"),
        ],
        {"profit": [43, 52], "stain": [1.4, 1.1], "wood": [2, 3], "caps": [17, 11]},
        ["Finished furniture counts are integer."],
    )
    add(
        "nlp4lp_000009",
        ("bike", "bikes", "I", None, "vehicle", "bike transportation"),
        ("car", "cars", "I", None, "vehicle", "car transportation"),
        "min",
        (1, 0, "minimize_bikes", "bike", "minimize the total number of bikes needed"),
        [
            core.con("people_floor", {"bike": 3, "car": 5}, ">=", 500, "transport 500 people", "transport at least 500 people", "person"),
            core.con("car_share", {"car": 0.6, "bike": -0.4}, "<=", 0, "cars at most 40%", "at most 40% of the vehicles can be cars", "vehicle"),
        ],
        {"capacity": [3, 5], "people_floor": 500, "car_share_cap": 0.4},
        ["Vehicle counts are integer. The objective intentionally counts bikes only."],
    )
    add(
        "nlp4lp_000014",
        ("small", "small jars", "I", None, "jar", "small jars"),
        ("large", "large jars", "I", None, "jar", "large jars"),
        "min",
        (1, 1, "minimize_jars", "jar", "minimum number of jars"),
        [
            core.con("jam_floor", {"small": 50, "large": 200}, ">=", 100000, "ship 100000 ml", "ship at least 100000 ml of jam", "ml"),
            core.con("large_not_more", {"large": 1, "small": -1}, "<=", 0, "large jars no more than small", "large jars cannot exceed ... small jars", "jar"),
        ],
        {"capacity_ml": [50, 200], "jam_floor": 100000},
        ["Jar counts are integer."],
    )
    add(
        "nlp4lp_000038",
        ("large", "large-plane trips", "I", None, "trip", "large planes"),
        ("small", "small-plane trips", "I", None, "trip", "small planes"),
        "min",
        (1, 1, "minimize_planes", "trip", "minimum number of planes"),
        [
            core.con("car_floor", {"large": 30, "small": 10}, ">=", 300, "deliver 300 cars", "deliver at least 300 cars", "car"),
            core.con("strict_plane_order", {"large": 1, "small": -1}, "<=", -1, "large trips strictly fewer than small", "large planes must be less than ... small planes", "trip"),
        ],
        {"capacity": [30, 10], "car_floor": 300},
        ["Trip counts are integer, converting the strict inequality to large <= small - 1."],
    )
    add(
        "nlp4lp_000035",
        ("tractor", "tractor trips", "I", None, "trip", "by either tractor or car"),
        ("car", "car trips", "I", None, "trip", "by either tractor or car"),
        "min",
        (1, 1, "minimize_trips", "trip", "minimize the total number of tractors and cars"),
        [
            core.con("corn_floor", {"tractor": 40, "car": 20}, ">=", 500, "transport 500 kg corn", "at least 500 kg of corn", "kg"),
            core.con("car_ratio", {"car": 1, "tractor": -2}, ">=", 0, "cars at least twice tractors", "cars ... at least twice ... tractors", "trip"),
        ],
        {"capacity_kg": [40, 20], "corn_floor": 500, "car_ratio_floor": 2},
        ["Trip counts are integer."],
    )
    add(
        "nlp4lp_000100",
        ("van", "vans", "I", None, "vehicle", "vans"),
        ("car", "cars", "I", None, "vehicle", "cars"),
        "min",
        (0, 1, "minimize_cars", "car", "minimize the total number of cars used"),
        [
            core.con("voter_floor", {"van": 6, "car": 3}, ">=", 200, "transport 200 voters", "transport at least 200 voters", "voter"),
            core.con("van_share", {"van": 0.7, "car": -0.3}, "<=", 0, "vans at most 30%", "at most 30% of the vehicles can be vans", "vehicle"),
        ],
        {"capacity": [6, 3], "voter_floor": 200, "van_share_cap": 0.3},
        ["Vehicle counts are integer. The objective intentionally counts cars only."],
    )
    add(
        "nlp4lp_000216",
        ("van", "vans", "I", None, "vehicle", "via vans and trucks"),
        ("truck", "trucks", "I", None, "vehicle", "via vans and trucks"),
        "min",
        (1, 0, "minimize_vans", "van", "minimum number of vans"),
        [
            core.con("shoe_floor", {"van": 50, "truck": 100}, ">=", 2000, "transport 2000 pairs", "minimum of 2000 pairs", "shoe_pair"),
            core.con("truck_not_more", {"truck": 1, "van": -1}, "<=", 0, "trucks no more than vans", "trucks used cannot exceed ... vans", "vehicle"),
        ],
        {"capacity": [50, 100], "shoe_floor": 2000},
        ["Vehicle counts are integer. The objective intentionally counts vans only."],
    )
    add(
        "nlp4lp_000225",
        ("staff", "staff teachers", "I", None, "teacher", "staff teachers"),
        ("substitute", "substitute teachers", "I", None, "teacher", "substitute teachers"),
        "min",
        (1, 1, "minimize_teachers", "teacher", "minimize the total number of teachers"),
        [
            core.con("hours_floor", {"staff": 6, "substitute": 3}, ">=", 1000, "teaching-hour floor", "requires 1000 hours", "hour"),
            core.con("budget_cap", {"staff": 300, "substitute": 100}, "<=", 40000, "budget limit", "budget of $40000", "USD"),
        ],
        {"hours": [6, 3], "wage": [300, 100], "hours_floor": 1000, "budget": 40000},
        ["Teacher counts are integer."],
    )
    add(
        "nlp4lp_000119",
        ("a", "process-A executions", "I", None, "process_run", "process A"),
        ("b", "process-B executions", "I", None, "process_run", "process B"),
        "max",
        (5, 7, "maximize_coins", "coin", "maximize the total number of coins"),
        [
            core.con("gold_cap", {"a": 3, "b": 5}, "<=", 500, "gold limit", "500 units of gold", "gold_unit"),
            core.con("wire_cap", {"a": 2, "b": 3}, "<=", 300, "wire limit", "300 wires", "wire"),
        ],
        {"gold": [3, 5], "wire": [2, 3], "coins": [5, 7], "caps": [500, 300]},
        ["Process executions are integer batches."],
    )
    add(
        "nlp4lp_000040",
        ("limo", "limousines", "I", None, "vehicle", "limousine"),
        ("bus", "buses", "I", None, "vehicle", "bus"),
        "min",
        (1, 1, "minimize_vehicles", "vehicle", "minimize the total number"),
        [
            core.con("people_floor", {"limo": 12, "bus": 18}, ">=", 400, "transport 400 people", "transport at least 400 people", "person"),
            core.con("limo_share", {"limo": 0.3, "bus": -0.7}, ">=", 0, "limousines at least 70%", "at least 70% ... limousines", "vehicle"),
        ],
        {"capacity": [12, 18], "people_floor": 400, "limo_share_floor": 0.7},
        ["Vehicle counts are integer."],
    )
    add(
        "nlp4lp_000210",
        ("car", "car-pool cars", "I", None, "vehicle", "car-pooling"),
        ("bus", "company buses", "I", 4, "vehicle", "company bus"),
        "min",
        (10, 30, "minimize_pollution", "pollution_unit", "minimize the total pollution"),
        [core.con("employee_floor", {"car": 4, "bus": 20}, ">=", 300, "transport 300 employees", "At least 300 employees", "employee")],
        {"capacity": [4, 20], "pollution": [10, 30], "employee_floor": 300, "bus_cap": 4},
        ["Vehicle counts are integer; the bus cap is a variable bound."],
    )
    add(
        "nlp4lp_000127",
        ("vegetable", "servings of vegetables", "C", None, "serving", "serving of vegetables"),
        ("fruit", "servings of fruit", "C", None, "serving", "serving of fruit"),
        "min",
        (3, 5, "minimize_cost", "USD", "minimize his cost"),
        [
            core.con("vitamin_floor", {"vegetable": 2, "fruit": 4}, ">=", 20, "vitamin floor", "at least 20 units of vitamins", "vitamin_unit"),
            core.con("mineral_floor", {"vegetable": 3, "fruit": 1}, ">=", 30, "mineral floor", "30 units of minerals", "mineral_unit"),
        ],
        {"vitamins": [2, 4], "minerals": [3, 1], "cost": [3, 5], "floors": [20, 30]},
        ["Nutritional servings are divisible continuous amounts."],
    )
    add(
        "nlp4lp_000209",
        ("ferry", "ferry trips", "I", None, "trip", "ferry trip"),
        ("rail", "light-rail trips", "I", None, "trip", "light rail trip"),
        "min",
        (1, 1, "minimize_trips", "trip", "minimize the total number of trips"),
        [
            core.con("box_floor", {"ferry": 20, "rail": 15}, ">=", 500, "transport 500 boxes", "at least 500 boxes", "box"),
            core.con("rail_ratio", {"rail": 1, "ferry": -4}, ">=", 0, "rail trips at least four times ferry", "at least 4 times ... ferry trips", "trip"),
        ],
        {"capacity": [20, 15], "box_floor": 500, "rail_ratio_floor": 4},
        ["Trip counts are integer."],
    )
    add(
        "nlp4lp_000233",
        ("elephant", "wooden elephants", "I", None, "item", "wooden elephants"),
        ("tiger", "wooden tigers", "I", None, "item", "tigers"),
        "max",
        (5, 4, "maximize_profit", "USD", "maximize profit"),
        [
            core.con("wood_cap", {"elephant": 50, "tiger": 40}, "<=", 5000, "wood limit", "5000 grams of wood", "gram"),
            core.con("plastic_cap", {"elephant": 20, "tiger": 30}, "<=", 4000, "plastic limit", "4000 grams of plastic", "gram"),
        ],
        {"wood": [50, 40], "plastic": [20, 30], "profit": [5, 4], "caps": [5000, 4000]},
        ["Finished souvenir counts are integer."],
    )
    add(
        "nlp4lp_000234",
        ("senior", "senior-citizen workers", "C", None, "worker_equivalent", "senior citizens"),
        ("young", "young-adult workers", "C", None, "worker_equivalent", "young adults"),
        "min",
        (500, 750, "minimize_wage", "USD/week", "Formulate a LP to minimize the wage bill"),
        [
            core.con("worker_floor", {"senior": 1, "young": 1}, ">=", 50, "at least 50 workers", "requires at least 50 workers", "worker_equivalent"),
            core.con("young_floor", {"young": 1}, ">=", 10, "at least 10 young adults", "at least 10 must be young adults", "worker_equivalent"),
            core.con("young_ratio", {"young": 3, "senior": -1}, ">=", 0, "young adults at least one third seniors", "young adults ... at least a third", "worker_equivalent"),
            core.con("wage_cap", {"senior": 500, "young": 750}, "<=", 30000, "weekly wage cap", "below $30000", "USD/week"),
        ],
        {"wage": [500, 750], "worker_floor": 50, "young_floor": 10, "wage_cap": 30000},
        ["The prompt explicitly requests an LP, so worker variables are continuous equivalents."],
    )
    add(
        "nlp4lp_000212",
        ("long", "long desks", "I", None, "desk", "long desks"),
        ("short", "short desks", "I", None, "desk", "short desks"),
        "max",
        (6, 2, "maximize_seating", "seat", "maximize the seating availability"),
        [
            core.con("budget_cap", {"long": 300, "short": 100}, "<=", 2000, "budget", "spend at most $2000", "USD"),
            core.con("space_cap", {"long": 10, "short": 4}, "<=", 200, "space", "at most 200 square feet", "square_foot"),
        ],
        {"cost": [300, 100], "space": [10, 4], "seats": [6, 2], "caps": [2000, 200]},
        ["Desk counts are integer."],
    )
    add(
        "nlp4lp_000084",
        ("spit", "spit tests", "I", None, "test", "spit tests"),
        ("swab", "swab tests", "I", None, "test", "swabs"),
        "max",
        (1, 1, "maximize_tests", "test", "maximize the number of tests"),
        [
            core.con("time_cap", {"spit": 10, "swab": 15}, "<=", 8000, "clinic time", "operates for 8000 minutes", "minute"),
            core.con("spit_ratio", {"spit": 1, "swab": -2}, ">=", 0, "spit tests at least twice swabs", "at least twice as many spit tests", "test"),
            core.con("swab_floor", {"swab": 1}, ">=", 20, "at least 20 swabs", "at least 20 swabs", "test"),
        ],
        {"minutes": [10, 15], "time_cap": 8000, "ratio": 2, "swab_floor": 20},
        ["Test counts are integer."],
    )
    add(
        "nlp4lp_000105",
        ("large", "large ships", "I", None, "ship", "large ships"),
        ("small", "small ships", "I", None, "ship", "small ships"),
        "min",
        (1, 1, "minimize_ships", "ship", "minimum number of ships"),
        [
            core.con("container_floor", {"large": 500, "small": 200}, ">=", 3000, "transport 3000 containers", "transport at least 3000 containers", "container"),
            core.con("large_not_more", {"large": 1, "small": -1}, "<=", 0, "large ships no more than small", "large ships cannot exceed ... small ships", "ship"),
        ],
        {"capacity": [500, 200], "container_floor": 3000},
        ["Ship counts are integer."],
    )
    add(
        "nlp4lp_000222",
        ("medium", "medium factories", "I", None, "factory", "medium sized factory"),
        ("small", "small factories", "I", None, "factory", "small factory"),
        "min",
        (1, 1, "minimize_factories", "factory", "minimize the total number of factories"),
        [
            core.con("toy_floor", {"medium": 50, "small": 35}, ">=", 250, "toy production floor", "at least 250 toys per day", "toy/day"),
            core.con("operator_cap", {"medium": 3, "small": 2}, "<=", 16, "operator limit", "available 16 operators", "operator"),
        ],
        {"capacity": [50, 35], "operators": [3, 2], "toy_floor": 250, "operator_cap": 16},
        ["Factory counts are integer."],
    )
    add(
        "nlp4lp_000124",
        ("helicopter", "helicopter trips", "I", None, "trip", "helicopters"),
        ("truck", "truck trips", "I", 8, "trip", "trucks"),
        "min",
        (5, 10, "minimize_pollution", "pollution_unit", "minimize the total amount of pollution"),
        [core.con("cow_floor", {"helicopter": 3, "truck": 7}, ">=", 80, "transport 80 cows", "transport 80 cows", "cow")],
        {"capacity": [3, 7], "pollution": [5, 10], "cow_floor": 80, "truck_cap": 8},
        ["Trip counts are integer; minimizing pollution makes oversupply irrelevant."],
    )
    add(
        "nlp4lp_000116",
        ("small", "small butcher shops", "I", None, "shop", "small shop"),
        ("large", "large butcher shops", "I", None, "shop", "large shop"),
        "min",
        (1, 1, "minimize_shops", "shop", "minimize the total number of butcher shops"),
        [
            core.con("hotdog_floor", {"small": 30, "large": 70}, ">=", 500, "hot-dog production floor", "at least 500 hot dogs per day", "hotdog/day"),
            core.con("worker_cap", {"small": 2, "large": 4}, "<=", 30, "worker limit", "available 30 workers", "worker"),
        ],
        {"capacity": [30, 70], "workers": [2, 4], "hotdog_floor": 500, "worker_cap": 30},
        ["Shop counts are integer."],
    )
    add(
        "nlp4lp_000203",
        ("glass", "glass jars", "I", None, "jar", "glass jars"),
        ("plastic", "plastic jars", "I", None, "jar", "plastic jars"),
        "max",
        (1, 1, "maximize_jars", "jar", "maximize the total number of bottles filled"),
        [
            core.con("honey_cap", {"glass": 250, "plastic": 300}, "<=", 20000, "honey availability", "has 20000 ml of honey", "ml"),
            core.con("plastic_ratio", {"plastic": 1, "glass": -2}, ">=", 0, "plastic jars at least twice glass", "at least twice as many plastic jars", "jar"),
            core.con("glass_floor", {"glass": 1}, ">=", 20, "at least 20 glass jars", "at least 20 glass jars", "jar"),
        ],
        {"capacity_ml": [250, 300], "honey_cap": 20000, "plastic_ratio_floor": 2, "glass_floor": 20},
        ["Jar counts are integer; 'bottles' in the final sentence refers to the same filled containers."],
    )
    add(
        "nlp4lp_000078",
        ("bread", "loaves of bread", "I", None, "batch", "loaf of bread"),
        ("cookie", "batches of cookies", "I", None, "batch", "batch of cookies"),
        "max",
        (5, 3, "maximize_profit", "USD", "maximize total profit"),
        [
            core.con("mixer_cap", {"bread": 1, "cookie": 0.5}, "<=", 3000, "mixer time", "stand-mixer ... at most 3000 hours", "hour"),
            core.con("oven_cap", {"bread": 3, "cookie": 1}, "<=", 3000, "oven time", "oven ... at most 3000 hours", "hour"),
        ],
        {"mixer_hours": [1, 0.5], "oven_hours": [3, 1], "profit": [5, 3], "caps": [3000, 3000]},
        ["Loaves and cookie batches are integer production units."],
    )
    add(
        "nlp4lp_000137",
        ("small", "small branches", "I", None, "branch", "small branches"),
        ("large", "large branches", "I", None, "branch", "large branches"),
        "min",
        (1, 1, "minimize_branches", "branch", "minimize the total number of branches"),
        [
            core.con("customer_floor", {"small": 50, "large": 100}, ">=", 1200, "serve 1200 customers", "serve at least 1200 customers per day", "customer/day"),
            core.con("teller_cap", {"small": 10, "large": 15}, "<=", 200, "teller availability", "available 200 bank tellers", "teller"),
        ],
        {"capacity": [50, 100], "tellers": [10, 15], "customer_floor": 1200, "teller_cap": 200},
        ["Branch counts are integer."],
    )
    add(
        "nlp4lp_000010",
        ("small", "small wagons", "I", None, "wagon", "small wagons"),
        ("large", "large wagons", "I", None, "wagon", "large wagons"),
        "min",
        (1, 1, "minimize_wagons", "wagon", "minimize the total number of wagons"),
        [
            core.con("ore_floor", {"small": 20, "large": 50}, ">=", 2000, "transport 2000 ore units", "2000 units of ore", "ore_unit"),
            core.con("small_ratio", {"small": 1, "large": -2}, ">=", 0, "small wagons at least twice large", "small wagons ... at least twice", "wagon"),
            core.con("large_floor", {"large": 1}, ">=", 10, "at least 10 large wagons", "at least 10 large wagons", "wagon"),
        ],
        {"capacity": [20, 50], "ore_floor": 2000, "small_ratio_floor": 2, "large_floor": 10},
        ["Wagon counts are integer."],
    )
    add(
        "nlp4lp_000028",
        ("nurse", "nurses", "I", None, "worker", "nurses"),
        ("pharmacist", "pharmacists", "I", None, "worker", "pharmacists"),
        "min",
        (1, 1, "minimize_workers", "worker", "minimize the total number of workers"),
        [
            core.con("labor_floor", {"nurse": 5, "pharmacist": 7}, ">=", 200, "healthcare labor floor", "needs 200 hours", "hour"),
            core.con("budget_cap", {"nurse": 250, "pharmacist": 300}, "<=", 9000, "budget", "budget of $9000", "USD"),
        ],
        {"hours": [5, 7], "wage": [250, 300], "hours_floor": 200, "budget": 9000},
        ["Worker counts are integer."],
    )
    add(
        "nlp4lp_000114",
        ("throat", "throat swabs", "I", None, "test", "throat swab"),
        ("nasal", "nasal swabs", "I", None, "test", "nasal swab"),
        "max",
        (1, 1, "maximize_patients", "patient", "maximize the number of patients seen"),
        [
            core.con("time_cap", {"throat": 5, "nasal": 3}, "<=", 20000, "clinic time", "operational for 20000 minutes", "minute"),
            core.con("nasal_floor", {"nasal": 1}, ">=", 30, "at least 30 nasal swabs", "at least 30 nasal swabs", "test"),
            core.con("throat_ratio", {"throat": 1, "nasal": -4}, ">=", 0, "throat swabs at least four times nasal", "at least 4 times as many throat swabs", "test"),
        ],
        {"minutes": [5, 3], "time_cap": 20000, "nasal_floor": 30, "throat_ratio_floor": 4},
        ["Each swab serves one patient, and test counts are integer."],
    )
    add(
        "nlp4lp_000150",
        ("van", "vans", "I", None, "vehicle", "van"),
        ("minibus", "minibuses", "I", 10, "vehicle", "minibus"),
        "min",
        (7, 10, "minimize_pollution", "pollution_unit", "minimize the total amount of pollution"),
        [
            core.con("kid_floor", {"van": 6, "minibus": 10}, ">=", 150, "transport 150 children", "at least 150 kids", "kid"),
            core.con("strict_van_order", {"van": 1, "minibus": -1}, ">=", 1, "vans strictly exceed minibuses", "vans used must exceed ... minibuses", "vehicle"),
        ],
        {"capacity": [6, 10], "pollution": [7, 10], "kid_floor": 150, "minibus_cap": 10},
        ["Vehicle counts are integer, so vans > minibuses becomes vans >= minibuses + 1."],
    )
    add(
        "nlp4lp_000186",
        ("blood", "blood tests", "I", None, "test", "blood test"),
        ("ear", "ear tests", "I", None, "test", "ear test"),
        "max",
        (1, 1, "maximize_tests", "test", "maximize the number of tests"),
        [
            core.con("time_cap", {"blood": 30, "ear": 5}, "<=", 7525, "clinic time", "operates for 7525 minutes", "minute"),
            core.con("blood_ratio", {"blood": 1, "ear": -3}, ">=", 0, "blood tests at least three times ear", "at least three times as many blood tests", "test"),
            core.con("ear_floor", {"ear": 1}, ">=", 12, "at least 12 ear tests", "at least 12 ear tests", "test"),
        ],
        {"minutes": [30, 5], "time_cap": 7525, "blood_ratio_floor": 3, "ear_floor": 12},
        ["Test counts are integer."],
    )
    add(
        "nlp4lp_000231",
        ("regular", "regular sandwiches", "I", None, "sandwich", "regular sandwich"),
        ("special", "special sandwiches", "I", None, "sandwich", "special sandwich"),
        "max",
        (3, 4, "maximize_profit", "USD", "maximize profit"),
        [
            core.con("egg_cap", {"regular": 2, "special": 3}, "<=", 40, "egg limit", "40 eggs", "egg"),
            core.con("bacon_cap", {"regular": 3, "special": 5}, "<=", 70, "bacon limit", "70 slices of bacon", "bacon_slice"),
        ],
        {"eggs": [2, 3], "bacon": [3, 5], "profit": [3, 4], "caps": [40, 70]},
        ["Sandwich counts are integer."],
    )
    add(
        "nlp4lp_000230",
        ("container", "oil containers", "I", None, "shipment", "containers"),
        ("truck", "oil trucks", "I", None, "shipment", "trucks"),
        "min",
        (1, 1, "minimize_shipments", "shipment", "minimize the total number"),
        [
            core.con("oil_floor", {"container": 30, "truck": 40}, ">=", 2000, "transport 2000 oil units", "at least 2000 units", "oil_unit"),
            core.con("truck_ratio", {"truck": 2, "container": -1}, "<=", 0, "trucks at most half containers", "trucks ... at most half ... containers", "shipment"),
            core.con("container_floor", {"container": 1}, ">=", 15, "at least 15 containers", "at least 15 containers", "shipment"),
        ],
        {"capacity": [30, 40], "oil_floor": 2000, "truck_ratio_cap": 0.5, "container_floor": 15},
        ["Shipment/container and truck counts are integer."],
    )
    add(
        "nlp4lp_000110",
        ("premium", "premium desktops", "I", None, "desktop", "premium desktops"),
        ("regular", "regular desktops", "I", None, "desktop", "regular desktops"),
        "max",
        (500, 300, "maximize_profit", "USD", "maximize profit"),
        [
            core.con("count_cap", {"premium": 1, "regular": 1}, "<=", 200, "desktop sales cap", "at most 200 desktops", "desktop"),
            core.con("budget_cap", {"premium": 2000, "regular": 1000}, "<=", 300000, "manufacturing budget", "at most $300000", "USD"),
        ],
        {"cost": [2000, 1000], "profit": [500, 300], "count_cap": 200, "budget": 300000},
        ["Desktop counts are integer."],
    )
    add(
        "nlp4lp_000065",
        ("a", "supplement-A pills", "I", None, "pill", "pill of supplement A"),
        ("b", "supplement-B pills", "I", None, "pill", "pill of supplement B"),
        "min",
        (2, 3, "minimize_cost", "USD", "minimize costs"),
        [
            core.con("iron_floor", {"a": 5, "b": 4}, ">=", 40, "iron floor", "minimum of 40 units of iron", "iron_unit"),
            core.con("calcium_floor", {"a": 10, "b": 15}, ">=", 50, "calcium floor", "50 units of calcium", "calcium_unit"),
        ],
        {"iron": [5, 4], "calcium": [10, 15], "cost": [2, 3], "floors": [40, 50]},
        ["Pill counts are integer."],
    )
    add(
        "nlp4lp_000204",
        ("regular", "regular firefighters", "I", None, "firefighter", "regular fire fighter"),
        ("emergency", "emergency firefighters", "I", None, "firefighter", "emergency fire fighter"),
        "min",
        (1, 1, "minimize_firefighters", "firefighter", "minimize the total number"),
        [
            core.con("hour_floor", {"regular": 10, "emergency": 6}, ">=", 300, "firefighter-hour floor", "at least 300 hours", "hour"),
            core.con("budget_cap", {"regular": 300, "emergency": 100}, "<=", 7000, "budget", "budget of $7000", "USD"),
        ],
        {"hours": [10, 6], "wage": [300, 100], "hour_floor": 300, "budget": 7000},
        ["Firefighter counts are integer."],
    )
    add(
        "nlp4lp_000072",
        ("canoe", "canoe trips", "I", None, "trip", "small canoes"),
        ("diesel", "diesel-boat trips", "I", None, "trip", "diesel boats"),
        "min",
        (1, 1, "minimize_trips", "trip", "minimize the total number"),
        [
            core.con("fish_floor", {"canoe": 10, "diesel": 15}, ">=", 1000, "transport 1000 fish", "at least 1000 fish", "fish"),
            core.con("canoe_ratio", {"canoe": 1, "diesel": -3}, ">=", 0, "canoes at least three times diesel", "canoes ... at least 3 times", "trip"),
        ],
        {"capacity": [10, 15], "fish_floor": 1000, "canoe_ratio_floor": 3},
        ["Trip counts are integer."],
    )
    add(
        "nlp4lp_000215",
        ("apartment", "dollars invested in apartments", "C", 200000, "USD", "money invested in apartments"),
        ("townhouse", "dollars invested in townhouses", "C", None, "USD", "money invested in townhouses"),
        "max",
        (0.10, 0.15, "maximize_profit", "USD", "maximize profit"),
        [
            core.con("budget_cap", {"apartment": 1, "townhouse": 1}, "<=", 600000, "investment budget", "$600,000 to invest", "USD"),
            core.con("apartment_ratio", {"apartment": 1, "townhouse": -0.5}, ">=", 0, "apartment investment at least half townhouse", "apartments ... at least a half as much", "USD"),
        ],
        {"budget": 600000, "apartment_cap": 200000, "returns": [0.10, 0.15], "apartment_ratio_floor": 0.5},
        ["Investment amounts are continuous dollars; the apartment cap is a variable bound."],
    )
    add(
        "nlp4lp_000098",
        ("old", "old vans", "I", None, "van", "old vans"),
        ("new", "new vans", "I", 30, "van", "new vans"),
        "min",
        (50, 30, "minimize_pollution", "pollution_unit", "minimize the total amount of pollution"),
        [core.con("bottle_floor", {"old": 100, "new": 80}, ">=", 5000, "transport 5000 bottles", "at least 5000 bottles", "bottle")],
        {"capacity": [100, 80], "pollution": [50, 30], "bottle_floor": 5000, "new_van_cap": 30},
        ["Van counts are integer; the new-van cap is a variable bound."],
    )
    add(
        "nlp4lp_000056",
        ("runner", "runner deliveries", "I", None, "delivery", "runners"),
        ("canoe", "canoe deliveries", "I", None, "delivery", "canoers"),
        "max",
        (3, 10, "maximize_mail", "mail_bag", "maximize the total amount of mail"),
        [
            core.con("canoe_share", {"canoe": 0.67, "runner": -0.33}, "<=", 0, "canoe deliveries at most 33%", "At most 33% of deliveries can be by canoe", "delivery"),
            core.con("hour_cap", {"runner": 4, "canoe": 2}, "<=", 200, "delivery-hour limit", "at most 200 total hours", "hour"),
            core.con("runner_floor", {"runner": 1}, ">=", 4, "at least 4 runners", "at least 4 runners", "delivery"),
        ],
        {"capacity": [3, 10], "hours": [4, 2], "canoe_share_cap": 0.33, "hour_cap": 200, "runner_floor": 4},
        ["Delivery counts are integer. The stated 33% is used literally as 0.33, not silently replaced by one third."],
    )
    add(
        "nlp4lp_000208",
        ("c", "kilograms of fertilizer C", "C", None, "kg", "Fertilizer C"),
        ("y", "kilograms of fertilizer Y", "C", None, "kg", "Fertilizer Y"),
        "min",
        (2, 3, "minimize_cost", "USD", "minimum cost"),
        [
            core.con("nitrous_floor", {"c": 1.5, "y": 5}, ">=", 5, "nitrous-oxide floor", "at least 5 units of nitrous oxide", "nitrous_unit"),
            core.con("vitamin_floor", {"c": 3, "y": 1}, ">=", 8, "vitamin-mix floor", "8 units of vitamin mix", "vitamin_unit"),
        ],
        {"nitrous": [1.5, 5], "vitamin": [3, 1], "cost_per_kg": [2, 3], "floors": [5, 8]},
        ["Fertilizer amounts are continuous kilograms."],
    )
    return specs


def eligible_unselected_rows() -> dict[str, dict[str, Any]]:
    rows = base_builder.read_jsonl(base_builder.SOURCE_PATHS["NLP4LP"])
    id_counts = base_builder.source_id_counts(rows, "NLP4LP")
    hash_groups = base_builder.problem_hash_groups(rows, "NLP4LP")
    selected = {
        row["source_id"]
        for row in core.read_jsonl(STAGING_ROOT / "base_candidates.jsonl")
    }
    result = {}
    for row in rows:
        passed, _screen = base_builder.supplement_screen(row)
        digest = base_builder.source_hash(str(row.get("problem") or ""))
        source_id = str(row["id"])
        passed = (
            passed
            and len(hash_groups[digest]) == 1
            and id_counts[source_id] == 1
            and source_id not in selected
        )
        if passed:
            result[source_id] = row
    return result


def main() -> int:
    specs = reserve_specs()
    eligible = eligible_unselected_rows()
    if not set(specs) <= set(eligible):
        raise RuntimeError(
            f"Reserve specs outside eligible/unselected pool: {sorted(set(specs) - set(eligible))}"
        )
    audit_rows = []
    replacement_rows = []
    for rank, source_id in enumerate(specs, start=1):
        row = eligible[source_id]
        text = str(row["problem"])
        candidate = {
            "candidate_id": f"RESERVE-NLP4LP-{source_id.rsplit('_', 1)[-1]}",
            "source_dataset": "NLP4LP",
            "source_id": source_id,
            "source_hash": base_builder.source_hash(text),
            "problem_zh_or_en": text,
        }
        spec = specs[source_id]
        output_dir = OUTPUT_ROOT / source_id
        snapshot = {
            "candidate_id": candidate["candidate_id"],
            "source_dataset": "NLP4LP",
            "source_id": source_id,
            "source_hash": candidate["source_hash"],
            "problem_text": text,
            "raw_text_sha256": core.sha256_text(text),
            "normalized_source_sha256_recomputed": core.normalized_source_sha256(text),
            "normalized_source_sha256_matches_candidate": True,
            "selection_policy": "eligible_unselected_then_short_clear_single_objective_manual_priority",
            "reserve_rank": rank,
            "legacy_answer_excluded_from_snapshot": True,
            "legacy_code_excluded": True,
        }
        ir = core.build_ir(candidate, spec)
        mapping = core.semantic_mapping(candidate, spec)
        certificate = core.certify(ir)
        comparison = core.compare_legacy(row.get("answer"), certificate["gurobi"].get("objective", float("nan")))
        passed = certificate["checks"]["passed"]
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
            "gurobi_version": certificate["gurobi"].get("version"),
            "copt_version": certificate["copt"].get("version"),
            "certified_objective": certificate["gurobi"].get("objective"),
            "legacy_answer_comparison": comparison,
            "legacy_code_used": False,
            "legacy_answer_used_as_gold": False,
            "files": {
                "canonical_ir": f"certified_sources/supplemental_reserve/{source_id}/canonical_ir.json",
                "semantic_mapping": f"certified_sources/supplemental_reserve/{source_id}/semantic_mapping.json",
                "solver_certificate": f"certified_sources/supplemental_reserve/{source_id}/solver_certificate.json",
                "source_snapshot": f"certified_sources/supplemental_reserve/{source_id}/source_snapshot.json",
            },
        }
        core.write_json(output_dir / "source_snapshot.json", snapshot)
        core.write_json(output_dir / "canonical_ir.json", ir)
        core.write_json(output_dir / "semantic_mapping.json", mapping)
        core.write_json(output_dir / "solver_certificate.json", certificate)
        core.write_json(output_dir / "audit.json", audit)
        audit_rows.append(audit)
        if passed:
            replacement_rows.append({
                "replacement_rank": len(replacement_rows) + 1,
                "reserve_candidate_id": candidate["candidate_id"],
                "source_dataset": "NLP4LP",
                "source_id": source_id,
                "canonical_ir_sha256": audit["canonical_ir_sha256"],
                "certified_objective": audit["certified_objective"],
                "gurobi_status": certificate["gurobi"]["status"],
                "copt_status": certificate["copt"]["status"],
                "eligible_to_replace_failed_base": True,
            })

    core.write_jsonl(AUDIT_PATH, audit_rows)
    core.write_jsonl(REPLACEMENT_PATH, replacement_rows)
    summary = {
        "reserve_candidates_audited": len(audit_rows),
        "reserve_pass_count": len(replacement_rows),
        "reserve_reject_count": len(audit_rows) - len(replacement_rows),
        "minimum_required_pass_count": 40,
        "minimum_met": len(replacement_rows) >= 40,
        "all_from_eligible_unselected_nlp4lp": True,
        "all_pass_rows_dual_solver_certified": all(
            row["solver_certificate_passed"]
            for row in audit_rows
            if row["status"] == "unchanged_pass"
        ),
        "legacy_answer_mismatch_count": sum(
            row["legacy_answer_comparison"]["status"] == "mismatch"
            for row in audit_rows
        ),
        "selection_policy": "same static screen; unselected only; shortest, clear, single-objective rows manually prioritized",
    }
    core.write_json(SUMMARY_PATH, summary)
    artifact_paths = sorted(
        [
            path
            for path in OUTPUT_ROOT.rglob("*")
            if path.is_file()
        ]
        + [
            AUDIT_PATH,
            SUMMARY_PATH,
            REPLACEMENT_PATH,
            Path(__file__).resolve(),
        ]
    )
    manifest = {
        "schema_version": "1.0",
        "hash_algorithm": "sha256",
        "self_excluded": True,
        "inputs": {
            str((STAGING_ROOT / "base_candidates.jsonl").relative_to(DATASET_ROOT)).replace("\\", "/"):
                core.sha256_file(STAGING_ROOT / "base_candidates.jsonl"),
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
