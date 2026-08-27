from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
LOCAL_DEPS = ROOT / ".deps"
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))

from llm_compat import (  # noqa: E402
    LLMProvider,
    create_llm_provider,
    provider_config_from_env,
)


ARXIV_API_URL = "https://export.arxiv.org/api/query"


@dataclass(frozen=True)
class ORRecord:
    record_id: str
    source: str
    group: str
    problem_en: str
    problem_type: str
    domain: str


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    status: int | str | None
    objective: float | None
    stdout: str
    stderr: str
    returncode: int | None
    error: str | None = None


@dataclass(frozen=True)
class AgentAction:
    kind: str
    content: str
    parse_error: str = ""


DISALLOWED_PATTERNS = [
    r"\bimport\s+os\b",
    r"\bimport\s+subprocess\b",
    r"\bimport\s+pathlib\b",
    r"\bimport\s+shutil\b",
    r"\bimport\s+socket\b",
    r"\bimport\s+requests\b",
    r"\bimport\s+urllib\b",
    r"\bopen\s*\(",
    r"\beval\s*\(",
    r"\bexec\s*\(",
]


def extract_code(text: str) -> str:
    fence = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    return fence.group(1).strip() if fence else text.strip()


def safety_check(code: str) -> None:
    lowered = code.lower()
    for pattern in DISALLOWED_PATTERNS:
        if re.search(pattern, lowered):
            raise ValueError(f"Disallowed generated-code pattern: {pattern}")


def execute_code(code: str, workdir: Path, timeout_s: int = 60) -> ExecutionResult:
    safety_check(code)
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    script = workdir / "candidate.py"
    script.write_text(code, encoding="utf-8")
    try:
        env = os.environ.copy()
        deps_path = str((ROOT / ".deps").resolve())
        env["PYTHONPATH"] = deps_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(workdir),
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecutionResult(
            ok=False,
            status=None,
            objective=None,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            returncode=None,
            error="timeout",
        )

    objective = None
    status = None
    ok = False
    error = None
    try:
        last_line = [line for line in proc.stdout.splitlines() if line.strip()][-1]
        obj = json.loads(last_line)
        objective_raw = obj["objective"]
        objective = None if objective_raw is None else float(objective_raw)
        status = parse_solver_status(obj["status"])
        if isinstance(obj.get("error"), str):
            error = obj["error"]
        ok = proc.returncode == 0 and not error
    except Exception as exc:  # noqa: BLE001
        error = f"parse_error: {exc}"

    return ExecutionResult(
        ok=ok,
        status=status,
        objective=objective,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
        error=error,
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_config_file_to_env(path: Path) -> None:
    if not path.exists():
        return
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a JSON object: {path}")
    mapping = {
        "llm_provider": "OPENOR_LLM_PROVIDER",
        "api_key": "OPENOR_API_KEY",
        "base_url": "OPENOR_BASE_URL",
        "model": "OPENOR_MODEL",
        "temperature": "OPENOR_TEMPERATURE",
        "top_p": "OPENOR_TOP_P",
        "top_k": "OPENOR_TOP_K",
        "reasoning_effort": "OPENOR_REASONING_EFFORT",
        "timeout_s": "OPENOR_TIMEOUT_S",
        "summary_model": "OPENOR_SUMMARY_MODEL",
        "document_extractor": "OPENOR_DOCUMENT_EXTRACTOR",
        "mineru_api_token": "OPENOR_MINERU_API_TOKEN",
        "mineru_api_base_url": "OPENOR_MINERU_API_BASE_URL",
        "mineru_extract_endpoint": "OPENOR_MINERU_EXTRACT_ENDPOINT",
        "mineru_batch_endpoint": "OPENOR_MINERU_BATCH_ENDPOINT",
        "mineru_batch_result_endpoint": "OPENOR_MINERU_BATCH_RESULT_ENDPOINT",
        "mineru_model_version": "OPENOR_MINERU_MODEL_VERSION",
    }
    for key, env_name in mapping.items():
        value = config.get(key)
        if value is not None and str(value).strip() and not is_placeholder_secret(str(value)):
            os.environ[env_name] = str(value)


def is_placeholder_secret(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("your_") or lowered in {"placeholder", "changeme", "change_me", "none", "null"}


def rel_text(path: Path) -> str:
    return str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path).replace("\\", "/")


def objective_matches(found: object, expected: object, rel_tol: float = 0.01) -> bool:
    try:
        found_f = float(found)
        expected_f = float(expected)
    except (TypeError, ValueError):
        return False
    return abs(found_f - expected_f) / max(1.0, abs(expected_f)) <= rel_tol


def strict_objective_matches(found: object, expected: object, rtol: float = 1e-4, atol: float = 1e-6) -> bool:
    try:
        found_f = float(found)
        expected_f = float(expected)
    except (TypeError, ValueError):
        return False
    return abs(found_f - expected_f) <= max(atol, rtol * abs(expected_f))


def solver_status_acceptable(status: object, solver_name: str) -> bool:
    if status is None:
        return False
    text = str(status).strip().lower()
    if text in {"optimal", "acceptable", "status_optimal"}:
        return True
    # Numeric status 2 is the Gurobi OPTIMAL code. COPT values vary by version,
    # so COPT-generated scripts should print explicit optimal/acceptable text.
    return solver_name.lower() == "gurobi" and text == "2"


def load_benchmark(path: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    packet_rows: list[dict[str, str]] = []
    key: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            expansion_id = benchmark_expansion_id(item.get("id"), len(packet_rows) + 1)
            record_id = f"optminer_bench_{expansion_id[-3:].lower()}"
            source = str(item.get("source") or "OptMiner-Bench")
            problem_type = str(item.get("type") or "")
            domain = str(item.get("scenario") or "")
            problem = item.get("problem")
            if not isinstance(problem, str) or not problem.strip():
                raise ValueError(f"Missing problem text in {path} line {line_no}")
            if "answer" not in item:
                raise ValueError(f"Missing answer in {path} line {line_no}")
            packet_rows.append(
                {
                    "expansion_id": expansion_id,
                    "record_id": record_id,
                    "source": source,
                    "group": "optminer_bench",
                    "problem_type": problem_type,
                    "domain": domain,
                    "problem_en": problem,
                }
            )
            key[expansion_id] = {
                "expansion_id": expansion_id,
                "record_id": record_id,
                "source": source,
                "group": "optminer_bench",
                "route_stratum": f"{problem_type}_{domain}".strip("_"),
                "expected_objective": str(item["answer"]),
            }
    return packet_rows, key


def benchmark_expansion_id(raw_id: object, fallback_idx: int) -> str:
    text = str(raw_id or "").strip()
    if re.fullmatch(r"OMB\d{3}", text, flags=re.IGNORECASE):
        return text.upper()
    try:
        idx = int(text)
    except ValueError:
        idx = fallback_idx
    return f"OMB{idx:03d}"


def record_from_packet(row: dict[str, str]) -> ORRecord:
    return ORRecord(
        record_id=row["record_id"],
        source=row["source"],
        group=row["group"],
        problem_en=row["problem_en"],
        problem_type=row.get("problem_type", ""),
        domain=row.get("domain", ""),
    )


def strip_search_tags(query: str) -> str:
    match = re.search(r"<search>(.*?)</search>", query, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return " ".join(match.group(1).split())
    return " ".join(query.split())


def arxiv_search(query: str, max_results: int, timeout_s: int, retries: int) -> dict[str, Any]:
    clean_query = strip_search_tags(query)
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{clean_query}",
            "start": 0,
            "max_results": max_results,
        }
    )
    url = f"{ARXIV_API_URL}?{params}"
    last_error = ""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OptMiner training-free benchmark evaluator"})
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                raw = response.read()
            return {
                "query": clean_query,
                "url": url,
                "ok": True,
                "error": "",
                "results": parse_arxiv_feed(raw),
            }
        except (TimeoutError, urllib.error.URLError, ET.ParseError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.0)
    return {"query": clean_query, "url": url, "ok": False, "error": last_error, "results": []}


def parse_arxiv_feed(raw: bytes) -> list[dict[str, str]]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(raw)
    results = []
    for entry in root.findall("atom:entry", ns):
        title = text_of(entry.find("atom:title", ns))
        summary = text_of(entry.find("atom:summary", ns))
        link = ""
        for link_el in entry.findall("atom:link", ns):
            if link_el.attrib.get("href"):
                link = link_el.attrib["href"]
                break
        results.append(
            {
                "title": " ".join(title.split()),
                "summary": " ".join(summary.split())[:900],
                "url": link,
            }
        )
    return results


def text_of(node: ET.Element | None) -> str:
    return "" if node is None or node.text is None else node.text


def solver_name_for_record(record: ORRecord) -> str:
    if record.record_id.endswith("_093"):
        return "copt"
    return "gurobi"


def solver_instruction_for_name(solver_name: str) -> str:
    if solver_name == "copt":
        return (
            "Solver requirement: use coptpy/COPT for this row-level override. "
            "This is an engineering adaptation for OMB093 and deviates from the paper's default Gurobi solver."
        )
    return "Solver requirement: use gurobipy/Gurobi, matching the paper's default inference-time solver target."


def build_solver_system_prompt(solver_name: str) -> str:
    solver_import = "gurobipy / Gurobi"
    status_hint = "For Gurobi, OPTIMAL status is numeric code 2."
    template_hint = (
        "Use the standard Gurobi Python pattern when possible: import gurobipy as gp; "
        "from gurobipy import GRB; build variables, objective, and constraints; call model.optimize()."
    )
    if solver_name == "copt":
        solver_import = "coptpy / COPT"
        status_hint = "Print a status value that is explicitly optimal/acceptable when the solver proves optimality."
        template_hint = (
            "Use the COPT Python API for this row-level solver override; this is an engineering adaptation "
            "for the benchmark row and is marked in the artifacts."
        )
    return f"""You are an operations research expert agent. Your task is to formulate the given optimization problem and solve it with Python.

You have two tools, exposed through XML-style tags:
<search>optimization problem or formulation name</search>
<python>complete executable Python solver script</python>

Arxiv search tool:
- Use <search> when relevant optimization-modeling knowledge is missing.
- The query must be the name of an optimization problem, model family, or formulation technique.
- Do not search for the full benchmark statement, scenario names, company-like names, or local numeric data.
- After each <result>, continue in the same context and decide whether another search is needed.

Python interpreter tool:
- When enough information is available, return <python>...</python> with a complete executable script using {solver_import}.
- {template_hint}
- If a previous Python execution result reports an error, invalid JSON, missing objective, or non-optimal status, debug the code and return a corrected <python> script.
- The final printed line must be exactly one JSON object:
{{"objective": <number_or_null>, "status": <solver_status>, "error": ""}}
- {status_hint}

Rules:
- Return at most one executable action tag per response: either one <search>...</search> or one <python>...</python>.
- You may include very brief reasoning, but the controller only executes the action tag.
- Use only local problem facts as instance data.
- External documents may provide modeling patterns, variable/constraint ideas, and solver API hints only.
- Never use hidden scoring values or any information outside the local problem statement and returned <result> observations.
- Do not invent missing numeric data.
- Keep the script self-contained.
- Do not read or write files.
- Do not import os, subprocess, pathlib, shutil, socket, requests, or urllib.
"""


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


class SearchBackend:
    name = "base"

    def search(
        self,
        query: str,
        args: argparse.Namespace,
        provider: LLMProvider,
        summary_provider: LLMProvider,
        run_dir: Path,
    ) -> dict[str, Any]:
        raise NotImplementedError


class DocumentExtractor:
    name = "base"

    def extract(self, urls: list[str], args: argparse.Namespace, run_dir: Path) -> list[dict[str, Any]]:
        raise NotImplementedError


class LocalPDFExtractor(DocumentExtractor):
    def __init__(self, name: str = "local_pdf") -> None:
        self.name = name

    def extract(self, urls: list[str], args: argparse.Namespace, run_dir: Path) -> list[dict[str, Any]]:
        cache_dir = run_dir / "documents" / self.name
        cache_dir.mkdir(parents=True, exist_ok=True)
        documents = []
        for url in urls:
            pdf_result = fetch_arxiv_pdf_text(url, cache_dir, args.search_timeout_s, args.search_retries)
            text = str(pdf_result.pop("text", "") or "")
            arxiv_id = (extract_arxiv_id(url) or "paper").replace("/", "_")
            text_path = cache_dir / f"{arxiv_id}.txt"
            documents.append(
                {
                    "pdf_url": url,
                    "ok": bool(text.strip()),
                    "extractor": self.name,
                    "local_extractor": pdf_result.get("extractor", ""),
                    "fetch_status": pdf_result.get("fetch_status", ""),
                    "extract_status": pdf_result.get("extract_status", ""),
                    "extract_error": pdf_result.get("extract_error", ""),
                    "cache_hit": pdf_result.get("cache_hit", False),
                    "retry_count": pdf_result.get("retry_count", args.search_retries),
                    "text": text,
                    "text_path": pdf_result.get("text_path", rel_text(text_path) if text_path.exists() else ""),
                }
            )
        return documents


class MinerUPreciseExtractor(DocumentExtractor):
    name = "mineru_precise"

    def extract(self, urls: list[str], args: argparse.Namespace, run_dir: Path) -> list[dict[str, Any]]:
        artifact_dir = run_dir / "documents" / self.name
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if not urls:
            return []
        token = str(args.mineru_api_token or "").strip()
        base_url = str(args.mineru_api_base_url or "").rstrip("/")
        if not token or not base_url:
            return [
                self._empty_document(url, "mineru_config_missing", "OPENOR_MINERU_API_TOKEN or OPENOR_MINERU_API_BASE_URL missing")
                for url in urls
            ]
        try:
            submit_response = submit_mineru_batch(urls, args, artifact_dir)
            zip_urls = collect_mineru_download_urls(submit_response)
            poll_payloads = []
            if not zip_urls:
                task_refs = collect_mineru_task_refs(submit_response)
                for attempt in range(args.mineru_poll_attempts):
                    for ref in task_refs:
                        poll_response = poll_mineru_task(ref, args, artifact_dir, attempt)
                        poll_payloads.append(poll_response)
                        zip_urls.extend(collect_mineru_download_urls(poll_response))
                    if zip_urls:
                        break
                    time.sleep(args.mineru_poll_interval_s)
            zip_paths = []
            for idx, zip_url in enumerate(dict.fromkeys(zip_urls), start=1):
                zip_paths.append(download_mineru_zip(zip_url, artifact_dir / f"mineru_result_{idx:03d}.zip", args))
            extracted_payloads = [read_mineru_zip_text(path, artifact_dir / path.stem) for path in zip_paths]
            write_json(artifact_dir / "poll_payloads.json", poll_payloads)
            return self._documents_from_payloads(urls, extracted_payloads, zip_urls)
        except Exception as exc:  # noqa: BLE001
            write_json(artifact_dir / "mineru_error.json", {"error": str(exc), "extractor": self.name})
            return [self._empty_document(url, "mineru_api_failed", str(exc)) for url in urls]

    def _empty_document(self, url: str, status: str, error: str) -> dict[str, Any]:
        return {
            "pdf_url": url,
            "ok": False,
            "extractor": self.name,
            "fetch_status": status,
            "extract_status": status,
            "extract_error": error,
            "cache_hit": False,
            "retry_count": 0,
            "text": "",
            "text_path": "",
            "mineru_zip_url": "",
        }

    def _documents_from_payloads(
        self,
        urls: list[str],
        payloads: list[dict[str, Any]],
        zip_urls: list[str],
    ) -> list[dict[str, Any]]:
        if not payloads:
            return [self._empty_document(url, "mineru_empty_result", "MinerU returned no downloadable text archive") for url in urls]
        documents = []
        for idx, url in enumerate(urls):
            payload = payloads[min(idx, len(payloads) - 1)]
            text = str(payload.get("text") or "")
            shared = len(payloads) == 1 and len(urls) > 1
            status = "ok_batch_zip_shared" if shared and text.strip() else "ok" if text.strip() else "mineru_empty_text"
            documents.append(
                {
                    "pdf_url": url,
                    "ok": bool(text.strip()),
                    "extractor": self.name,
                    "fetch_status": "mineru_zip_downloaded" if text.strip() else status,
                    "extract_status": status,
                    "extract_error": "" if text.strip() else "MinerU archive contained no Markdown/JSON/TXT text",
                    "cache_hit": False,
                    "retry_count": 0,
                    "text": text,
                    "text_path": payload.get("text_path", ""),
                    "mineru_zip_url": zip_urls[min(idx, len(zip_urls) - 1)] if zip_urls else "",
                    "source_files": payload.get("source_files", []),
                }
            )
        return documents


class MockSearchBackend(SearchBackend):
    name = "mock"

    def search(
        self,
        query: str,
        args: argparse.Namespace,
        provider: LLMProvider,
        summary_provider: LLMProvider,
        run_dir: Path,
    ) -> dict[str, Any]:
        result = {
            "backend": self.name,
            "query": query,
            "top_k": args.search_results,
            "ok": True,
            "error": "",
            "results": [
                {
                    "id": "Q001",
                    "arxiv_id": "mock",
                    "title": f"Mock evidence for {query}",
                    "url": "mock://search-result",
                    "pdf_url": "",
                    "fetch_status": "mock",
                    "extract_status": "mock",
                    "extractor": "mock",
                    "summary_status": "mock",
                    "summary": f"Use {query} as a formulation hint. Do not add instance data beyond the local problem.",
                    "retry_count": 0,
                    "timeout_s": 0,
                    "cache_hit": False,
                }
            ],
        }
        return result


class ArxivMetadataSearchBackend(SearchBackend):
    name = "arxiv_metadata"

    def search(
        self,
        query: str,
        args: argparse.Namespace,
        provider: LLMProvider,
        summary_provider: LLMProvider,
        run_dir: Path,
    ) -> dict[str, Any]:
        raw = arxiv_search(query, args.search_results, args.search_timeout_s, args.search_retries)
        evidence = []
        for idx, item in enumerate(raw.get("results") or [], start=1):
            evidence.append(
                {
                    "id": f"Q{idx:03d}",
                    "arxiv_id": extract_arxiv_id(str(item.get("url", ""))),
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "pdf_url": arxiv_pdf_url(str(item.get("url", ""))),
                    "fetch_status": "metadata_only",
                    "extract_status": "not_attempted",
                    "extractor": "arxiv_atom",
                    "summary_status": "abstract_only",
                    "summary": item.get("summary", ""),
                    "retry_count": args.search_retries,
                    "timeout_s": args.search_timeout_s,
                    "cache_hit": False,
                }
            )
        result = {
            "backend": self.name,
            "query": raw.get("query", query),
            "top_k": args.search_results,
            "ok": raw.get("ok", False),
            "error": raw.get("error", ""),
            "url": raw.get("url", ""),
            "results": evidence,
        }
        return result


class ArxivDocumentSearchBackend(ArxivMetadataSearchBackend):
    name = "arxiv_document"

    def search(
        self,
        query: str,
        args: argparse.Namespace,
        provider: LLMProvider,
        summary_provider: LLMProvider,
        run_dir: Path,
    ) -> dict[str, Any]:
        result = super().search(query, args, provider, summary_provider, run_dir)
        pdf_urls = [str(item.get("pdf_url") or "") for item in result.get("results") or [] if item.get("pdf_url")]
        extracted_by_url: dict[str, dict[str, Any]] = {}
        if args.fetch_documents and pdf_urls:
            primary_extractor = make_document_extractor(args.document_extractor)
            primary_docs = primary_extractor.extract(pdf_urls, args, run_dir)
            extracted_by_url = {str(doc.get("pdf_url")): doc for doc in primary_docs}
            fallback_urls = [
                url
                for url in pdf_urls
                if not str(extracted_by_url.get(url, {}).get("text") or "").strip()
                and args.document_extractor == "mineru_precise"
            ]
            if fallback_urls:
                fallback_docs = LocalPDFExtractor("local_pdf_fallback").extract(fallback_urls, args, run_dir)
                for doc in fallback_docs:
                    primary = extracted_by_url.get(str(doc.get("pdf_url"))) or {}
                    doc["primary_extractor"] = primary.get("extractor", "mineru_precise")
                    doc["primary_extract_status"] = primary.get("extract_status", "")
                    doc["primary_extract_error"] = primary.get("extract_error", "")
                    extracted_by_url[str(doc.get("pdf_url"))] = doc
        for item in result.get("results") or []:
            doc = extracted_by_url.get(str(item.get("pdf_url") or ""))
            if not doc:
                item["fetch_status"] = "abstract_available"
                item["extract_status"] = "abstract_fallback"
                item["extractor"] = "arxiv_atom"
                item["summary_status"] = "abstract_fallback"
                item["summary"] = abstract_fallback_summary(query, item, "document extraction was not requested or no PDF URL was extracted")
                continue
            text = str(doc.get("text") or "")
            for key, value in doc.items():
                if key != "text":
                    item[key] = value
            if text.strip():
                summary = summarize_document_with_provider(summary_provider, query, text[:6000])
                if summary.get("summary"):
                    item["summary"] = summary["summary"]
                else:
                    item["summary"] = abstract_fallback_summary(
                        query,
                        item,
                        f"document summary unavailable: {summary.get('summary_status', 'summary_failed')}",
                    )
                item["summary_status"] = summary.get("summary_status", "summary_failed")
            else:
                item["summary_status"] = "abstract_fallback"
                item["summary"] = abstract_fallback_summary(
                    query,
                    item,
                    f"document text unavailable: {doc.get('extract_status', 'empty_text')}",
                )
        return result


def make_document_extractor(name: str) -> DocumentExtractor:
    if name == "mineru_precise":
        return MinerUPreciseExtractor()
    if name == "local_pdf":
        return LocalPDFExtractor("local_pdf")
    raise ValueError(f"Unsupported document extractor: {name}")


def make_search_backend(name: str) -> SearchBackend:
    if name == "mock":
        return MockSearchBackend()
    if name == "arxiv_metadata":
        return ArxivMetadataSearchBackend()
    if name == "arxiv_document":
        return ArxivDocumentSearchBackend()
    raise ValueError(f"Unsupported search backend: {name}")


def extract_arxiv_id(url: str) -> str:
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", url)
    return match.group(1).replace(".pdf", "") if match else ""


def arxiv_pdf_url(url: str) -> str:
    arxiv_id = extract_arxiv_id(url)
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else ""


def extract_pdf_text(pdf_path: Path, text_path: Path, timeout_s: int) -> dict[str, Any]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(pdf_path))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            text_path.write_text(text, encoding="utf-8")
            return {"ok": True, "extractor": "pypdf", "extract_status": "ok", "error": ""}
    except Exception as exc:  # noqa: BLE001
        pypdf_error = str(exc)
    else:
        pypdf_error = "pypdf_extracted_empty_text"

    env = os.environ.copy()
    env.setdefault("MIKTEX_LOG_DIR", str(pdf_path.parent))
    try:
        proc = subprocess.run(
            ["pdftotext", str(pdf_path), str(text_path)],
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env=env,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "extractor": "pypdf|pdftotext",
            "extract_status": "failed",
            "error": f"pypdf_failed: {pypdf_error}; pdftotext_failed: {exc}",
        }
    if proc.returncode != 0:
        return {
            "ok": False,
            "extractor": "pypdf|pdftotext",
            "extract_status": f"pdftotext_failed: {proc.stderr[:200]}",
            "error": f"pypdf_failed: {pypdf_error}; pdftotext_failed: {proc.stderr[:200]}",
        }
    return {"ok": True, "extractor": "pdftotext", "extract_status": "ok", "error": ""}


def fetch_arxiv_pdf_text(pdf_url: str, cache_dir: Path, timeout_s: int, retries: int) -> dict[str, Any]:
    pdf_path = cache_dir / (extract_arxiv_id(pdf_url) or "paper").replace("/", "_")
    pdf_path = pdf_path.with_suffix(".pdf")
    text_path = pdf_path.with_suffix(".txt")
    cache_hit = text_path.exists()
    last_error = ""
    for attempt in range(retries + 1):
        try:
            if not pdf_path.exists():
                req = urllib.request.Request(pdf_url, headers={"User-Agent": "OptMiner training-free document retrieval"})
                with urllib.request.urlopen(req, timeout=timeout_s) as response:
                    pdf_path.write_bytes(response.read())
            if not text_path.exists():
                extraction = extract_pdf_text(pdf_path, text_path, timeout_s)
                if not extraction["ok"]:
                    return {
                        "fetch_status": "pdf_fetched",
                        "extract_status": extraction["extract_status"],
                        "extractor": extraction["extractor"],
                        "extract_error": extraction["error"],
                        "cache_hit": cache_hit,
                        "retry_count": attempt,
                        "text": "",
                    }
                extractor = extraction["extractor"]
            else:
                extractor = "cache"
            return {
                "fetch_status": "pdf_fetched",
                "extract_status": "ok",
                "extractor": extractor,
                "cache_hit": cache_hit,
                "retry_count": attempt,
                "text_path": rel_text(text_path),
                "text": text_path.read_text(encoding="utf-8", errors="replace"),
            }
        except (TimeoutError, urllib.error.URLError, subprocess.TimeoutExpired) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.0)
                continue
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            break
    return {
        "fetch_status": f"pdf_fetch_or_extract_failed: {last_error}",
        "extract_status": "failed",
        "extractor": "pdftotext",
        "cache_hit": cache_hit,
        "retry_count": retries,
        "text": "",
    }


def submit_mineru_batch(urls: list[str], args: argparse.Namespace, artifact_dir: Path) -> dict[str, Any]:
    endpoint = mineru_url(args, args.mineru_batch_endpoint)
    payload = {
        "files": [
            {
                "url": url,
                "data_id": (extract_arxiv_id(url) or f"doc_{idx:03d}").replace("/", "_"),
            }
            for idx, url in enumerate(urls, start=1)
        ],
        "model_version": args.mineru_model_version,
    }
    write_json(artifact_dir / "submit_request.json", {"endpoint": endpoint, "payload": payload})
    response = mineru_json_request("POST", endpoint, args, payload)
    write_json(artifact_dir / "submit_response.json", response)
    return response


def poll_mineru_task(task_ref: str, args: argparse.Namespace, artifact_dir: Path, attempt: int) -> dict[str, Any]:
    if task_ref.startswith("http://") or task_ref.startswith("https://"):
        endpoint = task_ref
    elif task_ref.startswith("batch:"):
        batch_id = task_ref.split(":", 1)[1]
        endpoint = mineru_url(args, f"{args.mineru_batch_result_endpoint.rstrip('/')}/{urllib.parse.quote(batch_id)}")
    elif task_ref.startswith("task:"):
        task_id = task_ref.split(":", 1)[1]
        endpoint = mineru_url(args, f"{args.mineru_extract_endpoint.rstrip('/')}/{urllib.parse.quote(task_id)}")
    else:
        endpoint = mineru_url(args, f"{args.mineru_extract_endpoint.rstrip('/')}/{urllib.parse.quote(task_ref)}")
    response = mineru_json_request("GET", endpoint, args, None)
    write_json(artifact_dir / f"poll_{attempt:03d}_{safe_stem(task_ref)}.json", response)
    return response


def mineru_json_request(method: str, url: str, args: argparse.Namespace, payload: dict[str, Any] | None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "User-Agent": "OptMiner inference workflow document extraction",
        "Authorization": f"Bearer {args.mineru_api_token}",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=args.search_timeout_s) as response:
        raw = response.read()
    try:
        parsed = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        parsed = {"raw_text": raw.decode("utf-8", errors="replace")}
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def mineru_url(args: argparse.Namespace, endpoint: str) -> str:
    base = str(args.mineru_api_base_url or "").rstrip("/")
    endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{base}{endpoint}"


def collect_mineru_download_urls(obj: Any) -> list[str]:
    urls = []
    for key, value in walk_json(obj):
        text = str(value) if isinstance(value, str) else ""
        lowered_key = key.lower()
        if text.startswith(("http://", "https://")) and (
            text.lower().split("?")[0].endswith(".zip") or "download" in lowered_key or "result" in lowered_key
        ):
            urls.append(text)
    return urls


def collect_mineru_task_refs(obj: Any) -> list[str]:
    refs = []
    for key, value in walk_json(obj):
        lowered = key.lower()
        last_key = lowered.split(".")[-1]
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if last_key in {"batch_id", "batchid"} and len(text) <= 128:
            refs.append(f"batch:{text}")
        elif last_key in {"task_id", "taskid", "task"} and len(text) <= 128:
            refs.append(f"task:{text}")
        elif lowered.endswith("url") and text.startswith(("http://", "https://")) and "task" in lowered:
            refs.append(text)
    return list(dict.fromkeys(refs))


def walk_json(obj: Any, key: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for child_key, value in obj.items():
            compound = f"{key}.{child_key}" if key else str(child_key)
            items.append((compound, value))
            items.extend(walk_json(value, compound))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            compound = f"{key}[{idx}]"
            items.append((compound, value))
            items.extend(walk_json(value, compound))
    return items


def download_mineru_zip(url: str, target: Path, args: argparse.Namespace) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return target
    headers = {
        "User-Agent": "OptMiner inference workflow document extraction",
        "Authorization": f"Bearer {args.mineru_api_token}",
    }
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=args.search_timeout_s) as response:
        target.write_bytes(response.read())
    return target


def read_mineru_zip_text(zip_path: Path, unpack_dir: Path) -> dict[str, Any]:
    unpack_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        safe_extract_zip(archive, unpack_dir)
    candidates = []
    for path in sorted(unpack_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".md", ".markdown", ".json", ".txt"}:
            continue
        text = read_extracted_text_file(path)
        if text.strip():
            candidates.append((mineru_text_priority(path), path, text))
    candidates.sort(key=lambda item: (item[0], str(item[1])))
    selected = candidates[:8]
    text = "\n\n".join(item[2] for item in selected)[:80000]
    merged_path = unpack_dir / "merged_text.txt"
    if text.strip():
        merged_path.write_text(text, encoding="utf-8")
    return {
        "text": text,
        "text_path": rel_text(merged_path) if merged_path.exists() else "",
        "source_files": [rel_text(item[1]) for item in selected],
    }


def read_extracted_text_file(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() != ".json":
        return raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    chunks = []
    for key, value in walk_json(parsed):
        if isinstance(value, str) and key.lower().split(".")[-1] in {"text", "content", "markdown", "md", "body"}:
            chunks.append(value)
    return "\n\n".join(chunks) if chunks else raw


def mineru_text_priority(path: Path) -> int:
    name = path.name.lower()
    if path.suffix.lower() in {".md", ".markdown"} and "content" in name:
        return 0
    if path.suffix.lower() in {".md", ".markdown"}:
        return 1
    if path.suffix.lower() == ".json":
        return 2
    return 3


def safe_extract_zip(archive: zipfile.ZipFile, target_dir: Path) -> None:
    root = target_dir.resolve()
    for member in archive.infolist():
        target = (root / member.filename).resolve()
        if not target.is_relative_to(root):
            continue
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as src:
            target.write_bytes(src.read())


def safe_stem(text: str) -> str:
    stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)[:80]
    return stem.strip("_") or "task"


def summarize_document_with_provider(provider: LLMProvider, query: str, text: str) -> dict[str, str]:
    messages = [
        {
            "role": "system",
            "content": (
                "Summarize retrieved operations-research papers as structured modeling evidence only. "
                "Do not infer benchmark instance data or final answers."
            ),
        },
        {
            "role": "user",
            "content": f"""Search query: {query}

Paper text excerpt:
{text}

Return exactly this structure. Use "not specified" for fields that are not directly supported by the excerpt.

Related optimization model:
- Scenario:
- Decision variables:
- Objective:
- Constraints:
- Solver or modeling technique:
- Relevance to current problem:
- Limitations:
""",
        },
    ]
    response = provider.complete(messages, purpose="document_summary")
    if response.error:
        return {"summary_status": response.error, "summary": ""}
    return {"summary_status": "provider_summary", "summary": coerce_related_model_summary(query, response.content.strip())}


def coerce_related_model_summary(query: str, summary: str) -> str:
    if "Related optimization model:" in summary:
        return summary
    source = summary.strip() or "not specified"
    return "\n".join(
        [
            "Related optimization model:",
            "- Scenario: not specified",
            "- Decision variables: not specified",
            "- Objective: not specified",
            "- Constraints: not specified",
            "- Solver or modeling technique: not specified",
            f"- Relevance to current problem: provider returned an unstructured modeling hint for query '{query}'. Hint: {source[:900]}",
            "- Limitations: provider summary did not follow the requested structure; fields above are not directly specified.",
        ]
    )


def abstract_fallback_summary(query: str, item: dict[str, Any], reason: str) -> str:
    abstract = str(item.get("summary") or "").strip()
    title = str(item.get("title") or "").strip()
    source = abstract or title or "not specified"
    return "\n".join(
        [
            "Related optimization model:",
            "- Scenario: not specified",
            "- Decision variables: not specified",
            "- Objective: not specified",
            "- Constraints: not specified",
            "- Solver or modeling technique: not specified",
            f"- Relevance to current problem: low-confidence abstract fallback for query '{query}'. Source text: {source[:900]}",
            f"- Limitations: {reason}; full document summary was not available.",
        ]
    )


def search_result_to_result_tag(search_result: dict[str, Any]) -> str:
    lines = [f"<result type=\"search\" backend=\"{search_result.get('backend', '')}\">"]
    lines.append(f"query: {search_result.get('query', '')}")
    if not search_result.get("ok", False):
        lines.append(f"error: {search_result.get('error', '')}")
    for idx, item in enumerate(search_result.get("results") or [], start=1):
        lines.append("")
        lines.append(f"[{idx}] arxiv_id={item.get('arxiv_id', '')} evidence_id={item.get('id', '')}")
        lines.append(f"title: {item.get('title', '')}")
        lines.append(f"url: {item.get('url', '')}")
        lines.append(f"pdf_url: {item.get('pdf_url', '')}")
        lines.append(
            "document_status: "
            f"extractor={item.get('extractor', '')}; "
            f"fetch={item.get('fetch_status', '')}; "
            f"extract={item.get('extract_status', '')}; "
            f"summary={item.get('summary_status', '')}"
        )
        summary = str(item.get("summary", "") or "")
        lines.append(summary[:1800])
    lines.append("</result>")
    return "\n".join(lines)


def parse_agent_action(content: str) -> AgentAction:
    searches = list(re.finditer(r"<search>(.*?)</search>", content, flags=re.IGNORECASE | re.DOTALL))
    pythons = list(re.finditer(r"<python>(.*?)</python>", content, flags=re.IGNORECASE | re.DOTALL))
    if len(searches) + len(pythons) > 1:
        return AgentAction("parse_error", "", "multiple_action_tags")
    search = searches[0] if searches else None
    python = pythons[0] if pythons else None
    if search and (not python or search.start() < python.start()):
        return AgentAction("search", " ".join(search.group(1).split()))
    if python:
        return AgentAction("python", python.group(1).strip())
    return AgentAction("parse_error", "", "missing_search_or_python_tag")


def validate_search_query(query: str) -> list[str]:
    flags = []
    if len(query.split()) > 12:
        flags.append("search_query_too_long_or_problem_like")
    if re.search(r"\b(company|syndicate|city|platform|administrator|conglomerate)\b", query, flags=re.IGNORECASE):
        flags.append("search_query_may_be_scenario_specific")
    if not re.search(r"\b(formulation|programming|optimization|assignment|routing|scheduling|network|knapsack|flow|integer|linear|quadratic|constraint)\b", query, flags=re.IGNORECASE):
        flags.append("search_query_may_not_be_formulation_name")
    return flags


def initial_agent_messages(record: ORRecord, solver_name: str, args: argparse.Namespace) -> list[dict[str, str]]:
    user = f"""Problem ID: {record.record_id}
Source: {record.source}
Problem type: {record.problem_type}
Scenario: {record.domain}
Max research turns: {args.max_research_turns}

Problem:
{record.problem_en}

{solver_instruction_for_name(solver_name)}

If the formulation is not immediately clear, first invoke the Arxiv search tool with one concise <search>...</search> query naming the relevant optimization problem or formulation. After each <result>, continue reasoning in the same context. When enough information is available, invoke the Python interpreter with one complete <python>...</python> solver script. If Python execution fails, debug using the returned execution <result> and provide corrected code.

Return exactly one next action now: <search>...</search> or <python>...</python>.
"""
    return [
        {"role": "system", "content": build_solver_system_prompt(solver_name)},
        {"role": "user", "content": user},
    ]


def execution_result_to_result_tag(exec_result: ExecutionResult, attempt: int, repair_reasons: list[str] | None = None) -> str:
    payload = {
        "attempt": attempt,
        "ok": exec_result.ok,
        "status": exec_result.status,
        "objective": exec_result.objective,
        "returncode": exec_result.returncode,
        "error": exec_result.error or "",
        "repair_reasons": repair_reasons or [],
        "stdout_tail": exec_result.stdout[-2000:],
        "stderr_tail": exec_result.stderr[-2000:],
    }
    return f"<result type=\"python_execution\">\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n</result>"


def safe_execute_code(code: str, run_dir: Path, attempt: int, timeout_s: int) -> ExecutionResult:
    try:
        exec_result = recover_execution_result(execute_code(code, run_dir, timeout_s=timeout_s))
    except ValueError as exc:
        exec_result = ExecutionResult(
            ok=False,
            status=None,
            objective=None,
            stdout="",
            stderr="",
            returncode=None,
            error=f"unsafe_code: {exc}",
        )
    write_execution_artifacts(run_dir, attempt, exec_result)
    return exec_result


def classify_run_status(
    exec_result: ExecutionResult | None,
    strict_match: bool,
    audit_flags: dict[str, Any],
    llm_error: str = "",
) -> str:
    if llm_error == "manual_response_missing":
        return "manual_response_missing"
    if llm_error == "missing_api_key":
        return "missing_api_key"
    if llm_error:
        return "execution_error" if exec_result else "parse_error"
    if exec_result is None:
        return "parse_error"
    if exec_result.error and "unsafe_code" in exec_result.error:
        return "unsafe_code"
    if exec_result.error == "timeout":
        return "timeout"
    if exec_result.error and "import" in exec_result.error.lower():
        return "import_error"
    if exec_result.error and "parse_error" in exec_result.error:
        return "parse_error"
    if audit_flags.get("possible_hardcoded_answer"):
        return "possible_hardcoded_answer"
    if exec_result.status is not None and str(exec_result.status).strip() in {"3", "4", "5"}:
        return "infeasible"
    if not solver_status_acceptable(exec_result.status, str(audit_flags.get("solver_name", ""))):
        return "non_optimal"
    if not strict_match:
        return "objective_mismatch"
    return "optimal"


def audit_hardcoding(code: str, expected_objective: str, solver_name: str) -> dict[str, Any]:
    findings = []
    lowered = code.lower()
    has_solver_import = ("gurobipy" in lowered or "coptpy" in lowered or "gp.model" in lowered or "cp.envr" in lowered)
    if not has_solver_import and re.search(r"print\s*\(.*objective", lowered, flags=re.DOTALL):
        findings.append("no_solver_import_and_direct_objective_print")
    try:
        expected = float(expected_objective)
    except (TypeError, ValueError):
        expected = None
    if expected is not None:
        for match in re.finditer(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])", code):
            try:
                value = float(match.group(0))
            except ValueError:
                continue
            if abs(value - expected) <= max(1e-6, abs(expected) * 1e-6):
                context = code[max(0, match.start() - 120) : min(len(code), match.end() + 120)].lower()
                suspicious_context = re.search(
                    r"\b(objective|objval|json\.dumps|print|return|answer|expected|hardcoded)\b",
                    context,
                )
                if not has_solver_import or suspicious_context:
                    findings.append(f"expected_objective_literal_or_near_literal:{match.group(0)}")
                    break
    if re.search(r"json\.dumps\s*\(\s*\{[^}]*objective", lowered, flags=re.DOTALL) and not has_solver_import:
        findings.append("json_objective_output_without_solver_model")
    return {
        "solver_name": solver_name,
        "possible_hardcoded_answer": bool(findings),
        "hardcoding_findings": findings,
    }


def audit_answer_leakage(run_dir: Path, expected_objective: str) -> dict[str, Any]:
    checked = []
    findings = []
    objective_variants = [item for item in objective_string_variants(expected_objective) if len(item) >= 4]
    allowed_names = {"score.json", "audit_flags.json"}
    paths = [
        run_dir / "agent_trajectory.jsonl",
        run_dir / "search_results.json",
    ]
    if (run_dir / "tool_calls").exists():
        paths.extend(sorted((run_dir / "tool_calls").glob("*.json")))
    if (run_dir / "llm_calls").exists():
        paths.extend(sorted((run_dir / "llm_calls").glob("*_request.json")))
        paths.extend(sorted((run_dir / "llm_calls").glob("*_request.md")))
    for path in paths:
        if not path.exists() or path.name in allowed_names:
            continue
        checked.append(rel_text(path))
        text = path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()
        if "expected_objective" in lowered or '"answer"' in lowered or "reference objective" in lowered:
            findings.append({"path": rel_text(path), "issue": "forbidden_field_name"})
            continue
        if path.name != "agent_trajectory.jsonl":
            for variant in objective_variants:
                if objective_variant_present(text, variant):
                    findings.append(
                        {
                            "path": rel_text(path),
                            "issue": "expected_objective_value_present_potential",
                            "value_variant": variant,
                        }
                    )
                    break
    return {
        "answer_leakage_checked": True,
        "answer_leakage_files_checked": checked,
        "answer_leakage_found": bool(findings),
        "answer_leakage_findings": findings,
    }


def objective_variant_present(text: str, variant: str) -> bool:
    if not variant:
        return False
    try:
        float(variant)
    except ValueError:
        return variant in text
    pattern = rf"(?<![A-Za-z0-9_.+-]){re.escape(variant)}(?![A-Za-z0-9_.+-])"
    return re.search(pattern, text) is not None


def objective_string_variants(value: str) -> list[str]:
    variants = [str(value)]
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return [item for item in variants if item]
    variants.extend([str(numeric), f"{numeric:.1f}", f"{numeric:.3f}", f"{numeric:.6f}"])
    if numeric.is_integer():
        variants.append(str(int(numeric)))
    return sorted({item for item in variants if item}, key=len, reverse=True)


def execution_repair_reasons(exec_result: ExecutionResult, solver_name: str) -> list[str]:
    reasons = []
    numeric_status = exec_result.status if isinstance(exec_result.status, int) and not isinstance(exec_result.status, bool) else None
    if numeric_status is not None and numeric_status < 0:
        reasons.append("negative_solver_status")
    if exec_result.error:
        reasons.append("execution_or_parse_error")
    if exec_result.returncode not in {0, None}:
        reasons.append("nonzero_returncode")
    if exec_result.objective is None:
        reasons.append("missing_objective")
    if exec_result.status is None:
        reasons.append("missing_solver_status")
    if not solver_status_acceptable(exec_result.status, solver_name):
        reasons.append("non_optimal_solver_status")
    if not exec_result.ok:
        reasons.append("execution_not_ok")
    return sorted(set(reasons))


def should_repair_after_execution(exec_result: ExecutionResult, solver_name: str) -> bool:
    return bool(execution_repair_reasons(exec_result, solver_name))


def recover_execution_result(exec_result: ExecutionResult) -> ExecutionResult:
    if exec_result.status is not None or exec_result.objective is not None:
        return exec_result
    if not (exec_result.error or "").startswith("parse_error:"):
        return exec_result
    lines = [line.strip() for line in exec_result.stdout.splitlines() if line.strip()]
    if not lines:
        return exec_result
    try:
        parsed = ast.literal_eval(lines[-1])
    except (SyntaxError, ValueError):
        return exec_result
    if not isinstance(parsed, dict):
        return exec_result
    try:
        objective_raw = parsed.get("objective")
        objective = None if objective_raw is None else float(objective_raw)
        status = parse_solver_status(parsed.get("status"))
    except (TypeError, ValueError):
        return exec_result
    error = parsed.get("error")
    error_text = error if isinstance(error, str) else ""
    return ExecutionResult(
        ok=exec_result.returncode == 0 and not error_text,
        status=status,
        objective=objective,
        stdout=exec_result.stdout,
        stderr=exec_result.stderr,
        returncode=exec_result.returncode,
        error=error_text,
    )


def write_execution_artifacts(run_dir: Path, attempt: int, exec_result: ExecutionResult) -> None:
    (run_dir / f"stdout_attempt_{attempt}.txt").write_text(exec_result.stdout, encoding="utf-8")
    (run_dir / f"stderr_attempt_{attempt}.txt").write_text(exec_result.stderr, encoding="utf-8")


def parse_solver_status(value: object) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return text


def create_provider_for_run(args: argparse.Namespace, run_dir: Path) -> LLMProvider:
    config = provider_config_from_env(
        provider=args.llm_provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        reasoning_effort=args.reasoning_effort,
        timeout_s=args.llm_timeout_s,
        manual_timeout_s=args.manual_timeout_s,
        resume=args.resume,
        replay_dir=args.replay_dir,
        call_dir=run_dir / "llm_calls",
    )
    return create_llm_provider(config)


def create_summary_provider_for_run(args: argparse.Namespace, run_dir: Path) -> LLMProvider:
    config = provider_config_from_env(
        provider=args.llm_provider,
        model=args.summary_model or args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        reasoning_effort=args.reasoning_effort,
        timeout_s=args.llm_timeout_s,
        manual_timeout_s=args.manual_timeout_s,
        resume=args.resume,
        replay_dir=args.replay_dir,
        call_dir=run_dir / "summary_llm_calls",
    )
    return create_llm_provider(config)


def run_search_only(
    record: ORRecord,
    provider: LLMProvider,
    summary_provider: LLMProvider,
    search_backend: SearchBackend,
    args: argparse.Namespace,
    run_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not str(args.search_query or "").strip():
        raise ValueError("--search-query is required with --search-only.")
    query = strip_search_tags(str(args.search_query))
    query_flags = validate_search_query(query)
    result = search_backend.search(query, args, provider, summary_provider, run_dir)
    search_results = [result]
    write_json(run_dir / "tool_calls" / "0001_search.json", result)
    write_json(run_dir / "search_results.json", search_results)
    return search_results, query_flags


def run_agent_loop(
    record: ORRecord,
    provider: LLMProvider,
    summary_provider: LLMProvider,
    search_backend: SearchBackend,
    args: argparse.Namespace,
    run_dir: Path,
) -> dict[str, Any]:
    solver_name = solver_name_for_record(record)
    messages = initial_agent_messages(record, solver_name, args)
    trajectory_path = run_dir / "agent_trajectory.jsonl"
    trajectory_path.write_text("", encoding="utf-8")

    search_results: list[dict[str, Any]] = []
    query_flags: list[str] = []
    llm_errors: list[str] = []
    parse_repairs = 0
    research_turns = 0
    debug_turns = 0
    attempt = 0
    final_code = ""
    exec_result: ExecutionResult | None = None
    last_action = ""
    run_status = "parse_error"

    if args.search_only:
        search_results, query_flags = run_search_only(record, provider, summary_provider, search_backend, args, run_dir)
        return {
            "solver_name": solver_name,
            "provider": provider.provider_name,
            "model": provider.config.model,
            "search_results": search_results,
            "query_flags": query_flags,
            "parse_repairs": 0,
            "research_turns": len(search_results),
            "debug_turns": 0,
            "exec_result": None,
            "final_code": "",
            "llm_errors": [],
            "last_action": "search_only",
            "run_status": "search_only",
        }

    for step in range(1, args.max_agent_steps + 1):
        response = provider.complete(messages, purpose=f"agent_step_{step:02d}")
        append_jsonl(
            trajectory_path,
            {
                "step": step,
                "event": "llm_response",
                "provider": response.provider,
                "model": response.model,
                "purpose": response.purpose,
                "error": response.error,
                "request_path": response.request_path,
                "response_path": response.response_path,
                "content": response.content,
            },
        )
        if response.error:
            llm_errors.append(response.error)
            run_status = response.error
            break

        action = parse_agent_action(response.content)
        last_action = action.kind
        if action.kind == "parse_error":
            append_jsonl(
                trajectory_path,
                {"step": step, "event": "parse_error", "error": action.parse_error, "raw": response.content[:2000]},
            )
            if parse_repairs >= args.parse_repair_retries:
                run_status = "parse_error"
                break
            parse_repairs += 1
            messages.append({"role": "assistant", "content": response.content})
            messages.append(
                {
                    "role": "user",
                    "content": "Your previous output did not contain a valid <search>...</search> or <python>...</python> tag. Return exactly one next action.",
                }
            )
            continue

        if action.kind == "search":
            flags = validate_search_query(action.content)
            query_flags.extend(flags)
            if research_turns >= args.max_research_turns:
                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {
                        "role": "user",
                        "content": "<result type=\"controller\">max_research_turns_reached; return <python> code next.</result>",
                    }
                )
                append_jsonl(
                    trajectory_path,
                    {"step": step, "event": "search_rejected", "query": action.content, "reason": "max_research_turns"},
                )
                continue
            search_result = search_backend.search(action.content, args, provider, summary_provider, run_dir)
            search_results.append(search_result)
            research_turns += 1
            tool_path = run_dir / "tool_calls" / f"{research_turns:04d}_search.json"
            write_json(tool_path, search_result)
            write_json(run_dir / "search_results.json", search_results)
            result_tag = search_result_to_result_tag(search_result)
            append_jsonl(
                trajectory_path,
                {
                    "step": step,
                    "event": "search",
                    "query": action.content,
                    "query_flags": flags,
                    "tool_path": rel_text(tool_path),
                    "result": search_result,
                },
            )
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": result_tag})
            continue

        if action.kind == "python":
            final_code = action.content
            (run_dir / f"candidate_attempt_{attempt}.py").write_text(final_code, encoding="utf-8")
            (run_dir / "final_candidate.py").write_text(final_code, encoding="utf-8")
            exec_result = safe_execute_code(final_code, run_dir, attempt, args.execution_timeout_s)
            repair_reasons = execution_repair_reasons(exec_result, solver_name)
            append_jsonl(
                trajectory_path,
                {
                    "step": step,
                    "event": "python_execution",
                    "attempt": attempt,
                    "status": exec_result.status,
                    "objective": exec_result.objective,
                    "ok": exec_result.ok,
                    "error": exec_result.error,
                    "repair_reasons": repair_reasons,
                },
            )
            if repair_reasons and debug_turns < args.debug_retries:
                debug_turns += 1
                attempt += 1
                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {
                        "role": "user",
                        "content": execution_result_to_result_tag(exec_result, attempt - 1, repair_reasons),
                    }
                )
                continue
            run_status = "executed"
            break

    if exec_result is None and final_code:
        exec_result = safe_execute_code(final_code, run_dir, attempt, args.execution_timeout_s)
    write_json(run_dir / "search_results.json", search_results)
    return {
        "solver_name": solver_name,
        "provider": provider.provider_name,
        "model": provider.config.model,
        "unsupported_parameters": provider.unsupported_parameters(),
        "search_results": search_results,
        "query_flags": query_flags,
        "parse_repairs": parse_repairs,
        "research_turns": research_turns,
        "debug_turns": debug_turns,
        "exec_result": exec_result,
        "final_code": final_code,
        "llm_errors": llm_errors,
        "last_action": last_action,
        "run_status": run_status,
    }


def run_one(
    packet_row: dict[str, str],
    key_row: dict[str, str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    record = record_from_packet(packet_row)
    run_dir = args.run_root / packet_row["expansion_id"] / "optminer_agent_workflow"
    run_dir.mkdir(parents=True, exist_ok=True)

    provider = create_provider_for_run(args, run_dir)
    summary_provider = create_summary_provider_for_run(args, run_dir)
    search_backend = make_search_backend(args.search_backend)
    loop = run_agent_loop(record, provider, summary_provider, search_backend, args, run_dir)
    exec_result: ExecutionResult | None = loop["exec_result"]
    expected_objective = key_row.get("expected_objective", "")
    strict_match = (
        exec_result is not None
        and solver_status_acceptable(exec_result.status, loop["solver_name"])
        and strict_objective_matches(exec_result.objective, expected_objective, args.strict_rtol, args.strict_atol)
    )
    legacy_match = exec_result is not None and objective_matches(exec_result.objective, expected_objective)
    hardcoding_audit = audit_hardcoding(loop.get("final_code", ""), expected_objective, loop["solver_name"])
    leakage_audit = audit_answer_leakage(run_dir, expected_objective)
    audit_flags = {
        **hardcoding_audit,
        **leakage_audit,
        "search_query_flags": loop["query_flags"],
        "unsupported_llm_parameters": loop.get("unsupported_parameters", []),
        "solver_override": loop["solver_name"] != "gurobi",
    }
    run_status = (
        "search_only"
        if args.search_only
        else classify_run_status(exec_result, strict_match, audit_flags, loop["llm_errors"][0] if loop["llm_errors"] else "")
    )
    score = {
        "solver_name": loop["solver_name"],
        "solver_status": exec_result.status if exec_result else None,
        "objective": exec_result.objective if exec_result else None,
        "expected_objective": expected_objective,
        "strict_objective_match": strict_match,
        "legacy_1pct_match": legacy_match,
        "execution_ok": exec_result.ok if exec_result else False,
        "returncode": exec_result.returncode if exec_result else None,
        "run_status": run_status,
        "llm_errors": loop["llm_errors"],
        "search_turns": loop["research_turns"],
        "debug_turns": loop["debug_turns"],
        "parse_repairs": loop["parse_repairs"],
    }
    write_json(run_dir / "score.json", score)
    write_json(run_dir / "audit_flags.json", audit_flags)

    base_row = {
        "expansion_id": packet_row["expansion_id"],
        "record_id": record.record_id,
        "source": record.source,
        "type": record.problem_type,
        "scenario": record.domain,
        "policy": "optminer_inference_time_agent_workflow",
        "workflow_mode": "agent_loop",
        "trace_mode": args.trace_mode,
        "provider": loop["provider"],
        "llm_model": loop["model"],
        "search_backend": args.search_backend,
        "trace_turns": loop["research_turns"] + (1 if loop["last_action"] == "python" else 0),
        "trace_parse_issue": "",
        "trace_error": ";".join(loop["llm_errors"]),
        "search_turns": loop["research_turns"],
        "search_success": any(search.get("ok") for search in loop["search_results"]),
        "search_error_count": sum(1 for search in loop["search_results"] if not search.get("ok")),
        "search_ok": sum(1 for search in loop["search_results"] if search.get("ok")),
        "search_result_count": sum(len(search.get("results") or []) for search in loop["search_results"]),
        "extract_success": any(
            str(item.get("extract_status", "")).startswith("ok")
            or item.get("extract_status") in {"mock", "abstract_fallback"}
            for search in loop["search_results"]
            for item in search.get("results", [])
        ),
        "summary_success": any(
            str(item.get("summary_status", "")).startswith(("mock", "abstract", "provider"))
            for search in loop["search_results"]
            for item in search.get("results", [])
        ),
        "external_urls": "; ".join(
            result.get("url", "")
            for search in loop["search_results"]
            for result in (search.get("results") or [])[: args.search_results]
        ),
        "expected_objective": key_row.get("expected_objective", ""),
        "run_dir": rel_text(run_dir),
    }
    return {
        **base_row,
        "stage": loop["run_status"],
        "format_repair_attempts": loop["parse_repairs"],
        "llm_ok": not bool(loop["llm_errors"]),
        "execution_ok": exec_result.ok if exec_result else False,
        "solver_name": loop["solver_name"],
        "solver_status": exec_result.status if exec_result else None,
        "status": exec_result.status if exec_result else None,
        "objective": exec_result.objective if exec_result else None,
        "strict_objective_match": strict_match,
        "legacy_1pct_match": legacy_match,
        "objective_match": legacy_match,
        "returncode": exec_result.returncode if exec_result else None,
        "run_status": run_status,
        "audit_flags": json.dumps(audit_flags, ensure_ascii=False),
        "possible_hardcoded_answer": audit_flags["possible_hardcoded_answer"],
        "answer_leakage_checked": audit_flags["answer_leakage_checked"],
        "error": (exec_result.error if exec_result else "") or ";".join(loop["llm_errors"]),
    }


def run_one_guarded(
    packet_row: dict[str, str],
    key_row: dict[str, str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    try:
        return run_one(packet_row, key_row, args)
    except Exception as exc:  # noqa: BLE001
        run_dir = args.run_root / packet_row["expansion_id"] / "optminer_agent_workflow"
        return {
            "expansion_id": packet_row["expansion_id"],
            "record_id": packet_row.get("record_id", ""),
            "source": packet_row.get("source", ""),
            "type": packet_row.get("problem_type", ""),
            "scenario": packet_row.get("domain", ""),
            "policy": "optminer_inference_time_agent_workflow",
            "workflow_mode": "agent_loop",
            "trace_mode": args.trace_mode,
            "provider": args.llm_provider,
            "search_backend": args.search_backend,
            "trace_turns": 0,
            "trace_parse_issue": "",
            "trace_error": "",
            "search_turns": 0,
            "search_success": False,
            "search_error_count": 0,
            "search_ok": 0,
            "search_result_count": 0,
            "extract_success": False,
            "summary_success": False,
            "external_urls": "",
            "expected_objective": key_row.get("expected_objective", ""),
            "llm_model": args.model,
            "run_dir": rel_text(run_dir),
            "stage": "unhandled_error",
            "format_repair_attempts": 0,
            "llm_ok": False,
            "execution_ok": False,
            "solver_name": "",
            "solver_status": None,
            "status": None,
            "objective": None,
            "strict_objective_match": False,
            "legacy_1pct_match": False,
            "objective_match": False,
            "returncode": None,
            "run_status": "execution_error",
            "audit_flags": "",
            "possible_hardcoded_answer": False,
            "answer_leakage_checked": False,
            "error": f"unhandled_runner_error: {exc}",
        }


def build_payload(args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": "optminer_inference_time_agent_workflow",
        "status": "search_only" if args.search_only else "codegen_executed",
        "workflow_mode": "agent_loop",
        "trace_mode": args.trace_mode,
        "llm_provider": args.llm_provider,
        "llm_model": args.model,
        "summary_model": args.summary_model,
        "search_backend": args.search_backend,
        "document_extractor": args.document_extractor,
        "max_research_turns": args.max_research_turns,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "strict_rtol": args.strict_rtol,
        "strict_atol": args.strict_atol,
        "workers": args.workers,
        "require_web_search": args.require_web_search,
        "search_timeout_s": args.search_timeout_s,
        "search_retries": args.search_retries,
        "mineru_configured": bool(args.mineru_api_token and args.mineru_api_base_url),
        "format_repair_retries": args.format_repair_retries,
        "rows": rows,
        "summary": {
            "rows": len(rows),
            "search_turns": sum(int(row["search_turns"]) for row in rows),
            "search_ok": sum(int(row.get("search_ok") or 0) for row in rows),
            "search_error_count": sum(int(row.get("search_error_count") or 0) for row in rows),
            "search_result_count": sum(int(row["search_result_count"]) for row in rows),
            "format_repair_attempts": sum(int(row.get("format_repair_attempts") or 0) for row in rows),
            "trace_errors": sum(1 for row in rows if row.get("trace_error")),
            "llm_ok": sum(1 for row in rows if row["llm_ok"]),
            "execution_ok": sum(1 for row in rows if row["execution_ok"]),
            "strict_objective_match": sum(1 for row in rows if row.get("strict_objective_match")),
            "legacy_1pct_match": sum(1 for row in rows if row.get("legacy_1pct_match")),
            "errors": sum(1 for row in rows if row["error"]),
            "manual_response_missing": sum(1 for row in rows if row.get("run_status") == "manual_response_missing"),
            "possible_hardcoded_answer": sum(1 for row in rows if row.get("possible_hardcoded_answer")),
        },
        "type_summary": type_summary(rows),
        "claim_limits": [
            "This is a training-free Opt-Miner inference-time workflow transfer, not the trained R-GRPO Opt-Miner model.",
            "It implements a same-context <search>/<result>/<python> agent loop, document retrieval, local solver execution, and strict scoring.",
            "Provider adapters support reproducible orchestration and audit replay; they are not part of the paper's original method.",
            "Reference objectives are read only by the scorer and are not included in LLM prompts, trajectory, tool calls, or search/document context.",
            "Search observations may guide modeling technique only and must not inject hidden instance facts.",
            "arxiv_metadata is a shallow baseline; arxiv_document uses MinerU precise extraction as the default document path and records local PDF fallback status when needed.",
        ],
    }


def type_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counters: dict[str, Counter[str]] = {}
    for row in rows:
        typ = str(row.get("type", ""))
        counters.setdefault(typ, Counter())
        counters[typ]["rows"] += 1
        counters[typ]["search_turns"] += int(row.get("search_turns") or 0)
        counters[typ]["search_result_count"] += int(row.get("search_result_count") or 0)
        if row.get("objective_match"):
            counters[typ]["objective_match"] += 1
        if row.get("strict_objective_match"):
            counters[typ]["strict_objective_match"] += 1
        if row.get("legacy_1pct_match"):
            counters[typ]["legacy_1pct_match"] += 1
    return [{"type": typ, **dict(counter)} for typ, counter in sorted(counters.items())]


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Opt-Miner Inference-Time Agent Workflow Run",
        "",
        f"Generated at UTC: `{payload['generated_at_utc']}`.",
        f"Status: `{payload['status']}`.",
        f"Workflow mode: `{payload['workflow_mode']}`.",
        f"LLM provider/model: `{payload['llm_provider']}` / `{payload['llm_model']}`.",
        f"Summary model: `{payload['summary_model']}`.",
        f"Search backend: `{payload['search_backend']}`.",
        f"Document extractor: `{payload['document_extractor']}`.",
        f"Max research turns: `{payload['max_research_turns']}`.",
        f"Strict tolerance: `rtol={payload['strict_rtol']}`, `atol={payload['strict_atol']}`.",
        f"Format repair retries: `{payload['format_repair_retries']}`.",
        f"Search timeout/retries: `{payload['search_timeout_s']}s / {payload['search_retries']}`.",
        "",
        "## Summary",
        "",
        "| Rows | Search turns | Search OK | Search errors | Search results | Repairs | LLM OK | Execution OK | Strict match | Legacy 1% | Hardcoding flags | Errors |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    summary = payload["summary"]
    lines.append(
        f"| {summary['rows']} | {summary['search_turns']} | {summary['search_ok']} | {summary['search_error_count']} | {summary['search_result_count']} | {summary['format_repair_attempts']} | {summary['llm_ok']} | {summary['execution_ok']} | {summary['strict_objective_match']} | {summary['legacy_1pct_match']} | {summary['possible_hardcoded_answer']} | {summary['errors']} |"
    )
    lines.extend(["", "## Rows", "", "| ID | Type | Scenario | Provider | Search | Solver | Objective | Expected | Strict | Legacy 1% | Run status | Audit | Error |", "|---|---|---|---|---:|---|---:|---:|---|---|---|---|---|"])
    for row in payload["rows"]:
        error = str(row.get("error", "")).replace("|", "/")
        if len(error) > 120:
            error = error[:117] + "..."
        audit = "hardcoded" if row.get("possible_hardcoded_answer") else ""
        if row.get("answer_leakage_checked") is False:
            audit = (audit + "; " if audit else "") + "leakage_unchecked"
        lines.append(
            f"| `{row['expansion_id']}` | `{row['type']}` | {row['scenario']} | `{row.get('provider', '')}` | {row['search_turns']} | `{row.get('solver_name', '')}` | {row['objective']} | {row['expected_objective']} | {row.get('strict_objective_match')} | {row.get('legacy_1pct_match')} | `{row.get('run_status', '')}` | {audit} | {error} |"
        )
    lines.extend(["", "## Claim Limits", ""])
    lines.extend(f"- {item}" for item in payload["claim_limits"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--benchmark", type=Path, default=ROOT / "benchmark" / "optminer_bench.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--expansion-ids", default="")
    parser.add_argument("--llm-provider", choices=["openai", "manual", "replay", "heuristic"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--summary-model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--llm-timeout-s", type=int, default=None)
    parser.add_argument("--manual-timeout-s", type=float, default=0.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--replay-dir", type=Path, default=None)
    parser.add_argument("--trace-mode", choices=["model", "heuristic"], default="model")
    parser.add_argument("--workflow-mode", choices=["agent_loop"], default="agent_loop")
    parser.add_argument("--max-research-turns", type=int, default=3)
    parser.add_argument("--max-agent-steps", type=int, default=12)
    parser.add_argument("--parse-repair-retries", type=int, default=1)
    parser.add_argument("--debug-retries", type=int, default=3)
    parser.add_argument("--search-results", type=int, default=10)
    parser.add_argument("--search-query", default="")
    parser.add_argument("--search-backend", choices=["mock", "arxiv_metadata", "arxiv_document"], default="arxiv_document")
    parser.add_argument("--document-extractor", choices=["mineru_precise", "local_pdf"], default=None)
    parser.add_argument("--fetch-documents", dest="fetch_documents", action="store_true", default=None)
    parser.add_argument("--no-fetch-documents", dest="fetch_documents", action="store_false")
    parser.add_argument("--require-web-search", action="store_true")
    parser.add_argument("--search-timeout-s", type=int, default=15)
    parser.add_argument("--search-retries", type=int, default=3)
    parser.add_argument("--mineru-api-token", default=None)
    parser.add_argument("--mineru-api-base-url", default=None)
    parser.add_argument("--mineru-extract-endpoint", default=None)
    parser.add_argument("--mineru-batch-endpoint", default=None)
    parser.add_argument("--mineru-batch-result-endpoint", default=None)
    parser.add_argument("--mineru-model-version", default=None)
    parser.add_argument("--mineru-poll-attempts", type=int, default=30)
    parser.add_argument("--mineru-poll-interval-s", type=float, default=2.0)
    parser.add_argument("--llm-retries", type=int, default=1)
    parser.add_argument("--retry-sleep-s", type=float, default=8.0)
    parser.add_argument("--format-repair-retries", type=int, default=1)
    parser.add_argument("--execution-timeout-s", type=int, default=60)
    parser.add_argument("--strict-rtol", type=float, default=1e-4)
    parser.add_argument("--strict-atol", type=float, default=1e-6)
    parser.add_argument("--search-only", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs" / "optminer_training_free_search_runs")
    parser.add_argument("--out-json", type=Path, default=ROOT / "runs" / "optminer_training_free_search_eval.json")
    parser.add_argument("--out-csv", type=Path, default=ROOT / "runs" / "optminer_training_free_search_eval.csv")
    parser.add_argument("--out-md", type=Path, default=ROOT / "runs" / "OPTMINER_TRAINING_FREE_SEARCH_EVAL.md")
    args = parser.parse_args()
    load_config_file_to_env(args.config)
    args.llm_provider = args.llm_provider or os.environ.get("OPENOR_LLM_PROVIDER") or "openai"
    args.model = args.model or os.environ.get("OPENOR_MODEL") or "gpt-5.5"
    args.summary_model = args.summary_model or os.environ.get("OPENOR_SUMMARY_MODEL") or args.model
    args.base_url = args.base_url or os.environ.get("OPENOR_BASE_URL") or "https://api.shubiaobiao.cn/v1"
    args.api_key = args.api_key or os.environ.get("OPENOR_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    args.temperature = float(args.temperature if args.temperature is not None else os.environ.get("OPENOR_TEMPERATURE") or 0.0)
    args.top_p = float(args.top_p if args.top_p is not None else os.environ.get("OPENOR_TOP_P") or 0.8)
    args.top_k = int(args.top_k if args.top_k is not None else os.environ.get("OPENOR_TOP_K") or 20)
    args.llm_timeout_s = int(args.llm_timeout_s if args.llm_timeout_s is not None else os.environ.get("OPENOR_TIMEOUT_S") or 200)
    args.reasoning_effort = args.reasoning_effort or os.environ.get("OPENOR_REASONING_EFFORT") or "high"
    args.document_extractor = args.document_extractor or os.environ.get("OPENOR_DOCUMENT_EXTRACTOR") or "mineru_precise"
    args.mineru_api_token = args.mineru_api_token or os.environ.get("OPENOR_MINERU_API_TOKEN") or ""
    args.mineru_api_base_url = (args.mineru_api_base_url or os.environ.get("OPENOR_MINERU_API_BASE_URL") or "https://mineru.net").rstrip("/")
    args.mineru_extract_endpoint = args.mineru_extract_endpoint or os.environ.get("OPENOR_MINERU_EXTRACT_ENDPOINT") or "/api/v4/extract/task"
    args.mineru_batch_endpoint = args.mineru_batch_endpoint or os.environ.get("OPENOR_MINERU_BATCH_ENDPOINT") or "/api/v4/extract/task/batch"
    args.mineru_batch_result_endpoint = args.mineru_batch_result_endpoint or os.environ.get("OPENOR_MINERU_BATCH_RESULT_ENDPOINT") or "/api/v4/extract-results/batch"
    args.mineru_model_version = args.mineru_model_version or os.environ.get("OPENOR_MINERU_MODEL_VERSION") or "vlm"
    if args.fetch_documents is None:
        args.fetch_documents = args.search_backend == "arxiv_document"
    if args.search_only and not str(args.search_query or "").strip():
        raise SystemExit("--search-query is required with --search-only.")

    packet_rows, key = load_benchmark(args.benchmark)
    if args.expansion_ids:
        wanted = {item.strip() for item in args.expansion_ids.split(",") if item.strip()}
        packet_rows = [row for row in packet_rows if row.get("expansion_id") in wanted]
    if args.skip:
        packet_rows = packet_rows[args.skip :]
    if args.limit is not None:
        packet_rows = packet_rows[: args.limit]
    if not packet_rows:
        raise SystemExit("No packet rows selected.")

    args.run_root.mkdir(parents=True, exist_ok=True)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if args.workers <= 1:
        for packet_row in packet_rows:
            row = run_one_guarded(packet_row, key.get(packet_row["expansion_id"], {}), args)
            rows.append(row)
            payload = build_payload(args, rows)
            args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            write_csv(rows, args.out_csv)
            write_markdown(payload, args.out_md)
    else:
        ordered_ids = [row["expansion_id"] for row in packet_rows]
        completed: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(run_one_guarded, packet_row, key.get(packet_row["expansion_id"], {}), args): packet_row
                for packet_row in packet_rows
            }
            for future in as_completed(futures):
                row = future.result()
                completed[row["expansion_id"]] = row
                rows = [completed[expansion_id] for expansion_id in ordered_ids if expansion_id in completed]
                payload = build_payload(args, rows)
                args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                write_csv(rows, args.out_csv)
                write_markdown(payload, args.out_md)

    payload = build_payload(args, rows)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(rows, args.out_csv)
    write_markdown(payload, args.out_md)
    print(json.dumps({"status": payload["status"], "summary": payload["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
