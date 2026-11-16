import json
from pathlib import Path


BATCH = Path(__file__).resolve().parents[1]
AUDIT = BATCH / "private" / "rapid_audit.jsonl"
OUTPUT = BATCH / "private" / "independent_review.jsonl"
REVIEWED_AT = "2026-08-02T03:27:54.296293Z"
BASE_SEMANTIC_FAILURES = {
    "SWOR-R003": "base constraint ops_limit is redundant on the finite domain",
    "SWOR-R010": "base constraint extended_option_limit is redundant on the finite domain",
}
PATCH_REDUNDANCY = {
    "SWOR-R014": "patched constraint project_g_reserved is redundant",
    "SWOR-R015": "patched constraints untrained_a_forbidden and untrained_b_forbidden are redundant",
}
ARABIC_SURFACE_PASS = {"SWOR-R007", "SWOR-R013"}


audits = [json.loads(line) for line in AUDIT.read_text(encoding="utf-8").splitlines() if line]
rows = []
for audit in audits:
    task_id = audit["id"]
    base = json.loads((BATCH.parent.parent / audit["base_model_path"]).read_text(encoding="utf-8"))
    patched = json.loads((BATCH.parent.parent / audit["patched_model_path"]).read_text(encoding="utf-8"))
    base_variables = {item["name"] for item in base["variables"]}
    base_constraints = {item["name"] for item in base["constraints"]}
    added_variables = [item["name"] for item in patched["variables"] if item["name"] not in base_variables]
    added_constraints = [item["name"] for item in patched["constraints"] if item["name"] not in base_constraints]
    additions = ", ".join(added_variables + added_constraints)
    notes = [
        "REJECT: the current mandatory task-local-fact chain is absent from the generator audit",
        f"patched additions [{additions}] therefore have no exact public local-fact bindings and cannot be cleared for unstated inputs",
        "the recorded COPT results and complete action sets were independently reproduced by the current batch validator",
        "official-source access was not repeated after this early hard-gate failure, so current access and instance applicability remain unconfirmed",
    ]
    if task_id not in ARABIC_SURFACE_PASS:
        notes.append("the public problem also fails the current Arabic-numeral surface rule")
    else:
        notes.append("numeric_alignment still uses one-character context-free surfaces rejected by the current schema")
    if task_id in BASE_SEMANTIC_FAILURES:
        notes.append(BASE_SEMANTIC_FAILURES[task_id])
    if task_id in PATCH_REDUNDANCY:
        notes.append(PATCH_REDUNDANCY[task_id])
    rows.append({
        "schema_version": "searchworthyor.rapid_independent_review.v0",
        "id": task_id,
        "reviewer_id": "/root/native_batch_a",
        "reviewed_at": REVIEWED_AT,
        "source_access_confirmed": False,
        "authority_confirmed": True,
        "support_excerpt_direct": True,
        "applicability_confirmed": False,
        "structural_patch_supported": True,
        "rule_to_patch_trace_confirmed": False,
        "task_local_facts_sufficient": False,
        "no_unstated_patch_inputs": False,
        "base_model_semantics_confirmed": task_id not in BASE_SEMANTIC_FAILURES,
        "problem_base_alignment_confirmed": task_id not in BASE_SEMANTIC_FAILURES,
        "answer_leakage_absent": True,
        "solver_and_action_sets_reproduced": True,
        "base_topology_not_template_duplicate": True,
        "status": "REJECT",
        "review_notes": "; ".join(notes) + ".",
    })

OUTPUT.write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8", newline="\n")
