"""Read-only provenance check for existing initial-FAIL/final-PASS records.

No runtime imports, network, solving, or feasible-set enumeration. Output stores
safe hashes, file paths and matching status; no API credentials or raw payloads.
"""
from pathlib import Path
import collections
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / "analysis/rebuttal_dqz1_evidence_20261114"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rel(path):
    return path.relative_to(ROOT).as_posix()


def parsed_response(raw):
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


rows = [json.loads(line) for line in (SOURCE / "model_full_equivalence_records.jsonl").read_text(encoding="utf-8").splitlines()]
selected = [r for r in rows if r["method"] == "SWAgent-online" and r.get("initial_full_model_status") == "FAIL" and r["full_model_status"] == "PASS"]
results = []
for row in selected:
    case = (ROOT / row["model_file"]).parent
    trace = read(case / "trace.json")
    requests = []
    for path in sorted((case / "api").glob("*/request.json")):
        request = read(path)
        payload = request.get("payload", {})
        messages = payload.get("input", payload.get("messages", []))
        if not isinstance(messages, list):
            continue
        contents = [m["content"] for m in messages if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str)]
        requests.append((path, request, contents))
    matches = []
    for semantic_path in sorted((case / "semantic").glob("*.json")):
        semantic = read(semantic_path)
        for message in semantic.get("messages", []):
            if message.get("role") != "user" or not isinstance(message.get("content"), str):
                continue
            content = message["content"]
            try:
                data = json.loads(content)
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            windows = []
            for source in data.get("sources", []):
                if not isinstance(source, dict) or not str(source.get("url", "")).startswith(("http://", "https://")):
                    continue
                for window in source.get("windows", []):
                    body = window.get("text", window.get("content", ""))
                    if isinstance(body, str) and body.strip():
                        windows.append({"document": source.get("document"), "reference": window.get("reference"), "start": window.get("start"), "end": window.get("end"), "characters": len(body), "text_sha256": digest(body)})
            if not windows:
                continue
            parsed = parsed_response(semantic.get("raw"))
            events = [{"trace_index_zero_based": i, "patch_accepted": event.get("patch_accepted"), "nonempty_patch": bool(event.get("proposal", {}).get("model_patch")), "table_errors": event.get("table_errors")} for i, event in enumerate(trace) if parsed is not None and event.get("kind") == "UPDATE" and event.get("proposal") == parsed]
            for request_path, request, contents in requests:
                if content not in contents:
                    continue
                response_path = request_path.parent / "response.json"
                response = read(response_path) if response_path.exists() else {}
                response_equal = bool(response_path.exists() and isinstance(semantic.get("raw"), str) and semantic["raw"].strip() and response.get("content") == semantic["raw"])
                matches.append({
                    "semantic_file": rel(semantic_path), "semantic_sha256": sha(semantic_path),
                    "request_file": rel(request_path), "request_sha256": sha(request_path),
                    "stage": request.get("stage"), "user_content_sha256": digest(content),
                    "actual_payload_user_message_exact_match": True,
                    "response_file": rel(response_path) if response_path.exists() else None,
                    "response_sha256": sha(response_path) if response_path.exists() else None,
                    "response_request_id_matches": response.get("request_id") == request.get("request_id") if response_path.exists() else False,
                    "nonempty_response_exactly_matches_consumed_semantic_raw": response_equal,
                    "parsed_response_equals_trace_update_proposal": bool(events),
                    "trace_updates": events,
                    "accepted_trace_update_with_nonempty_patch": any(e["patch_accepted"] and e["nonempty_patch"] for e in events),
                    "body_window_count": len(windows), "body_windows": windows,
                })
    consumed = [m for m in matches if m["response_request_id_matches"] and m["nonempty_response_exactly_matches_consumed_semantic_raw"] and m["parsed_response_equals_trace_update_proposal"]]
    accepted = [m for m in consumed if m["accepted_trace_update_with_nonempty_patch"]]
    results.append({"source_task_id": row["source_task_id"], "eval_id": row["eval_id"], "run_id": row["run_id"], "initial_full_model_status": "FAIL", "final_full_model_status": "PASS", "actual_body_request_and_consumed_update": "PASS" if consumed else "UNRESOLVED", "actual_body_request_consumed_accepted_nonempty_patch": "PASS" if accepted else "UNRESOLVED", "matching_requests": matches})

output = {
    "scope": "All saved SWAgent-online C2 initial-FAIL/final-PASS transitions; no score-based selection within this transition set",
    "source_records_file": rel(SOURCE / "model_full_equivalence_records.jsonl"),
    "source_records_sha256": sha(SOURCE / "model_full_equivalence_records.jsonl"),
    "script_sha256": sha(Path(__file__)),
    "checks": "Exact semantic user-content match to actual API payload user message containing nonempty HTTP(S) source body windows; matching received response ID and response text equals saved semantic raw; parsed response equals UPDATE proposal in trace. Accepted nonempty patch is reported separately.",
    "boundaries": ["Mechanical provenance only; does not establish relevance, correctness, authority or temporal applicability of source content", "Source-containing request precedes the recorded corresponding UPDATE, but this does not isolate retrieval as the causal reason for the final model", "Initial request without body sources is not necessarily before internet use: PLAN may already include search snippets", "A saved request without a received matching response and consumed trace proposal is insufficient"],
    "n": len(results),
    "actual_body_request_and_consumed_update": dict(collections.Counter(r["actual_body_request_and_consumed_update"] for r in results)),
    "actual_body_request_consumed_accepted_nonempty_patch": dict(collections.Counter(r["actual_body_request_consumed_accepted_nonempty_patch"] for r in results)),
    "records": results,
}
path = OUT / "model_payload_validation.json"
path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: output[k] for k in ["n", "actual_body_request_and_consumed_update", "actual_body_request_consumed_accepted_nonempty_patch"]}, ensure_ascii=False))
print("unresolved", [(r["source_task_id"], r["run_id"]) for r in results if r["actual_body_request_and_consumed_update"] != "PASS"])
