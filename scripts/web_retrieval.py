"""Hosted search, public-page retrieval, and verbatim quote verification."""

from __future__ import annotations

import argparse
import io
import ipaddress
import json
import re
import socket
import sys
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import certifi
import requests
from bs4 import BeautifulSoup


BLOCKED_MARKERS = ("searchworthyor", "mirrornew", "/private/", "\\private\\", "gold.json", "oracle")
REDIRECT_CODES = {301, 302, 303, 307, 308}
RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "msclkid"}
AUTHORITY_HOST_SUFFIXES = (
    ".gov",
    ".gov.uk",
    ".gov.au",
    ".gov.cn",
    ".gov.sg",
    ".gc.ca",
    ".go.jp",
    ".gouv.fr",
    ".europa.eu",
    ".int",
)
AUTHORITY_HOSTS = {
    "canada.ca",
    "eur-lex.europa.eu",
    "legislation.gov.uk",
    "officialgazette.gov.ph",
    "admin.ch",
}


@dataclass
class RetrievalFailure(RuntimeError):
    failure_type: str
    detail: str
    status: int | None = None
    final_url: str | None = None
    content_type: str | None = None
    retry_events: list[dict[str, Any]] | None = None
    context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, f"{self.failure_type}: {self.detail}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "failure_type": self.failure_type,
            "failure_detail": self.detail,
            "status": self.status,
            "final_url": self.final_url,
            "content_type": self.content_type,
            "retry_events": self.retry_events or [],
            **(self.context or {}),
        }


def _is_special(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


PROXY_FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")


def _is_proxy_fake_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Recognize the RFC 2544 range used by the workstation TUN proxy.

    Literal URLs in this range remain blocked by is_allowed_public_url.  This
    exception applies only after a syntactically valid public hostname has
    resolved, and only when every returned address is in the fake-IP range.
    """
    return isinstance(address, ipaddress.IPv4Address) and address in PROXY_FAKE_IP_NETWORK


def is_allowed_public_url(url: str) -> bool:
    decoded = url
    for _ in range(6):
        updated = urllib.parse.unquote(decoded)
        if updated == decoded:
            break
        decoded = updated
    parsed = urllib.parse.urlsplit(decoded)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        return False
    if any(marker in decoded.lower() for marker in BLOCKED_MARKERS):
        return False
    try:
        return not _is_special(ipaddress.ip_address(parsed.hostname.strip("[]")))
    except ValueError:
        return True


def _assert_public(url: str) -> None:
    if not is_allowed_public_url(url):
        raise ValueError("URL is not an allowed public HTTPS URL")
    host = urllib.parse.urlsplit(url).hostname
    if host is None:
        raise ValueError("URL has no host")
    addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses:
        raise ValueError("URL host has no resolved address")
    if all(address.is_global for address in addresses):
        return
    hostname_is_literal = False
    try:
        ipaddress.ip_address(host.strip("[]"))
        hostname_is_literal = True
    except ValueError:
        pass
    proxy_fake_ip_resolution = (
        not hostname_is_literal
        and "." in host
        and all(_is_proxy_fake_ip(address) for address in addresses)
    )
    if not proxy_fake_ip_resolution:
        raise ValueError("URL resolves to a non-public address")


def canonicalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    host = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = f"{host}:{port}" if port and port != 443 else host
    path = parsed.path or "/"
    query = urllib.parse.urlencode(
        [
            (key, value)
            for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith("utm_")
        ],
        doseq=True,
    )
    return urllib.parse.urlunsplit((parsed.scheme.lower(), netloc, path, query, ""))


def site_operators(query: str) -> list[str]:
    return sorted({match.lower().strip(".") for match in re.findall(r"(?i)(?:^|\s)site:([A-Za-z0-9.-]+)", query)})


def operator_compliant(url: str, domains: list[str]) -> bool:
    if not domains:
        return True
    host = (urllib.parse.urlsplit(url).hostname or "").lower().removeprefix("www.")
    return any(host == domain.removeprefix("www.") or host.endswith("." + domain.removeprefix("www.")) for domain in domains)


def is_official_candidate(url: str) -> bool:
    host = (urllib.parse.urlsplit(url).hostname or "").lower().removeprefix("www.")
    return host in AUTHORITY_HOSTS or any(
        host == suffix.removeprefix(".") or host.endswith(suffix)
        for suffix in AUTHORITY_HOST_SUFFIXES
    )


def _query_terms(query: str) -> set[str]:
    generic = {
        "official",
        "government",
        "authority",
        "regulator",
        "statutory",
        "standard",
        "guidance",
        "site",
        "current",
    }
    terms = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9.-]{2,}", query.lower())
        if token not in generic and not token.isdigit() and not token.startswith("site:")
    }
    cjk_generic = ("官方", "政府", "权威", "监管", "机构", "法规", "规则", "规定", "条例", "标准", "指南", "最新")
    for sequence in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]{2,}", query):
        content = sequence
        for marker in cjk_generic:
            content = content.replace(marker, " ")
        for chunk in content.split():
            if len(chunk) <= 6:
                terms.add(chunk)
            else:
                terms.add(chunk)
                terms.update(chunk[index:index + 3] for index in range(len(chunk) - 2))
    return terms


def result_relevance(query: str, title: str, snippet: str, url: str) -> tuple[bool, int]:
    terms = _query_terms(query)
    haystack = f"{title} {snippet} {urllib.parse.urlsplit(url).path}".lower()
    matches = sum(term in haystack for term in terms)
    threshold = 1 if len(terms) <= 2 else 2
    return matches >= threshold, matches


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_search_text(value: str) -> str:
    cleaned = "".join(
        " " if unicodedata.category(character) in {"Cc", "Cf", "Co", "Cs"} else character
        for character in value
    )
    return collapse_whitespace(cleaned)


def verify_quote(page_text: str, quote: str) -> bool:
    normalized_quote = collapse_whitespace(quote)
    return bool(normalized_quote) and len(normalized_quote) <= 2000 and normalized_quote in collapse_whitespace(page_text)


def _retry_after_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return min(30.0, max(0.0, float(value.strip())))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return min(30.0, max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return 0.0


def _exception_chain(exc: BaseException) -> str:
    values: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        values.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__
    return " | ".join(values)


class PublicWebRetriever:
    def __init__(
        self,
        connect_timeout_seconds: int = 10,
        read_timeout_seconds: int = 30,
        max_results: int = 6,
        max_open: int = 3,
        byte_limit: int = 8_000_000,
        search_client: Any | None = None,
    ):
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.max_results = max_results
        self.max_open = max_open
        self.byte_limit = byte_limit
        self.search_client = search_client
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 SearchWorthyOR/1.6.1",
                "Accept": "text/html,application/xhtml+xml,application/pdf,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en-US,en;q=0.8,zh-CN;q=0.6",
            }
        )

    def _request_once(self, url: str) -> dict[str, Any]:
        current = url
        redirects: list[dict[str, Any]] = []
        for _ in range(6):
            _assert_public(current)
            response = self.session.get(
                current,
                allow_redirects=False,
                timeout=(self.connect_timeout_seconds, self.read_timeout_seconds),
                verify=certifi.where(),
                stream=True,
            )
            if response.status_code in REDIRECT_CODES:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise requests.exceptions.TooManyRedirects("redirect response has no Location")
                target = urllib.parse.urljoin(current, location)
                _assert_public(target)
                redirects.append({"status": response.status_code, "from_url": current, "to_url": target})
                current = target
                continue
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.byte_limit:
                    response.close()
                    raise ValueError("response exceeds retrieval byte limit")
                chunks.append(chunk)
            data = b"".join(chunks)
            result = {
                "status": response.status_code,
                "content_type": response.headers.get("Content-Type", ""),
                "data": data,
                "final_url": canonicalize_url(response.url),
                "headers": dict(response.headers),
                "redirects": redirects,
            }
            response.close()
            return result
        raise requests.exceptions.TooManyRedirects("redirect limit exceeded")

    def _classify_exception(self, exc: BaseException, stage: str) -> str:
        chain = _exception_chain(exc).lower()
        if isinstance(exc, requests.exceptions.SSLError) or "ssl" in chain or "tls" in chain:
            return f"{stage}_TLS_FAILURE"
        if isinstance(exc, (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, TimeoutError)):
            return f"{stage}_TIMEOUT"
        if isinstance(exc, requests.exceptions.TooManyRedirects):
            return f"{stage}_REDIRECT_FAILURE" if stage == "PAGE" else f"{stage}_REMOTE_DISCONNECT"
        if "gaierror" in chain or "name or service not known" in chain or "getaddrinfo failed" in chain:
            return f"{stage}_DNS_FAILURE"
        if isinstance(exc, (requests.exceptions.ConnectionError, ConnectionResetError, ConnectionAbortedError)):
            return f"{stage}_REMOTE_DISCONNECT"
        if isinstance(exc, ValueError):
            return f"{stage}_NOT_READABLE" if stage == "PAGE" else f"{stage}_PARSE_FAILURE"
        return f"{stage}_REMOTE_DISCONNECT"

    def _get(self, url: str, stage: str) -> dict[str, Any]:
        retry_events: list[dict[str, Any]] = []
        for attempt in (1, 2):
            try:
                result = self._request_once(url)
                status = int(result["status"])
                if status < 400:
                    result["retry_events"] = retry_events
                    return result
                if status == 403:
                    failure_type = f"{stage}_HTTP_403"
                elif status == 404:
                    failure_type = f"{stage}_HTTP_404"
                elif status == 429:
                    failure_type = f"{stage}_HTTP_429"
                elif status >= 500:
                    failure_type = f"{stage}_HTTP_5XX"
                else:
                    failure_type = f"{stage}_HTTP_{status}"
                retryable = status in RETRYABLE_HTTP_CODES
                wait_seconds = _retry_after_seconds(result["headers"].get("Retry-After")) if status == 429 else 1.0
                failure = RetrievalFailure(
                    failure_type,
                    f"HTTP {status}",
                    status=status,
                    final_url=result["final_url"],
                    content_type=result["content_type"],
                    retry_events=retry_events,
                )
            except (requests.RequestException, socket.gaierror, TimeoutError, ValueError) as exc:
                failure_type = self._classify_exception(exc, stage)
                retryable = failure_type in {
                    f"{stage}_TLS_FAILURE",
                    f"{stage}_TIMEOUT",
                    f"{stage}_REMOTE_DISCONNECT",
                    f"{stage}_DNS_FAILURE",
                }
                wait_seconds = 1.0
                failure = RetrievalFailure(
                    failure_type,
                    _exception_chain(exc)[:1000],
                    retry_events=retry_events,
                )
            if retryable and attempt == 1:
                retry_events.append(
                    {
                        "attempt": attempt,
                        "failure_type": failure.failure_type,
                        "wait_seconds": wait_seconds,
                    }
                )
                if wait_seconds:
                    time.sleep(wait_seconds)
                continue
            failure.retry_events = retry_events
            raise failure
        raise AssertionError("unreachable")

    def _normalize_results(
        self,
        planned_query: str,
        executed_query: str,
        rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        domains = site_operators(planned_query)
        raw_results: list[dict[str, Any]] = []
        accepted: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rank, source in enumerate(rows, start=1):
            if not isinstance(source, dict):
                continue
            raw_url = source.get("url")
            title = normalize_search_text(str(source.get("title") or ""))
            snippet = normalize_search_text(str(source.get("snippet") or ""))
            if not isinstance(raw_url, str):
                continue
            url = canonicalize_url(raw_url) if is_allowed_public_url(raw_url) else None
            if not url or url in seen:
                continue
            seen.add(url)
            compliant = operator_compliant(url, domains)
            relevant, relevance_matches = result_relevance(planned_query, title, snippet, url)
            result = {
                "rank": rank,
                "title": title,
                "url": url,
                "snippet": snippet,
                "backend": "shubiaobiao_responses_web_search",
                "planned_query": planned_query,
                "executed_query": executed_query,
                "operator_compliant": compliant,
                "relevant": relevant,
                "relevance_matches": relevance_matches,
                "official_candidate": is_official_candidate(url),
            }
            raw_results.append(result)
            if compliant and relevant and len(accepted) < self.max_results:
                accepted.append(result)
        return accepted, raw_results

    def search(self, query: str) -> dict[str, Any]:
        if not query.strip() or any(marker in query.lower() for marker in ("searchworthyor", "swor-r", "gold", "oracle")):
            raise RetrievalFailure("SEARCH_PARSE_FAILURE", "query is empty or contains a benchmark/private marker")
        if self.search_client is None or not hasattr(self.search_client, "web_search"):
            raise RetrievalFailure("SEARCH_BACKEND_FAILURE", "Responses web search client is absent")
        started = time.perf_counter()
        try:
            response = self.search_client.web_search(query, "responses_web_search")
        except Exception as exc:
            from common import StrictAPIRequestError

            if isinstance(exc, StrictAPIRequestError):
                detail = str(exc)
                failure_type = exc.failure_type or "SEARCH_BACKEND_FAILURE"
                raise RetrievalFailure(failure_type, detail, status=exc.status) from exc
            raise
        executed_query = str(response["executed_query"])
        executed_queries = list(response["executed_queries"])
        results, raw_results = self._normalize_results(query, executed_query, response["raw_results"])
        backend_raw_results = response["raw_results"]
        if not results:
            failure_type = "SEARCH_OPERATOR_VIOLATION" if site_operators(query) and raw_results else "SEARCH_EMPTY_RESULTS"
            raise RetrievalFailure(
                failure_type,
                "Responses search returned no operator-compliant result"
                if failure_type == "SEARCH_OPERATOR_VIOLATION"
                else "Responses search returned no relevant allowed result",
                status=200,
                final_url="https://api.shubiaobiao.cn/v1/responses",
                content_type="application/json",
                retry_events=response["retry_events"],
                context={
                    "raw_results": raw_results,
                    "backend_raw_results": backend_raw_results,
                    "backend": "shubiaobiao_responses_web_search",
                    "planned_query": query,
                    "executed_query": executed_query,
                    "executed_queries": executed_queries,
                    "executed_query_count": len(executed_queries),
                    "query_budget_consumed": 1,
                    "provider_query_expanded": len(executed_queries) > 1,
                    "results_discarded": False,
                    "backend_raw_result_count": len(backend_raw_results),
                    "normalized_raw_result_count": len(raw_results),
                    "web_search_call_count": response["tool_call_count"],
                    "actual_model": response["actual_model"],
                },
            )
        return {
            "query": query,
            "planned_query": query,
            "executed_query": executed_query,
            "executed_queries": executed_queries,
            "executed_query_count": len(executed_queries),
            "query_budget_consumed": 1,
            "provider_query_expanded": len(executed_queries) > 1,
            "results_discarded": False,
            "query_rewritten": executed_query != query,
            "status": 200,
            "results": results,
            "raw_results": raw_results,
            "backend_raw_results": backend_raw_results,
            "backend_raw_result_count": len(backend_raw_results),
            "normalized_raw_result_count": len(raw_results),
            "exposed_result_count": len(results),
            "web_search_call_count": response["tool_call_count"],
            "actual_model": response["actual_model"],
            "raw_response": response["raw"],
            "backend": "shubiaobiao_responses_web_search",
            "final_url": "https://api.shubiaobiao.cn/v1/responses",
            "retry_events": response["retry_events"],
            "wall_seconds": time.perf_counter() - started,
        }

    @staticmethod
    def _decode_html(data: bytes, content_type: str) -> str:
        match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
        encodings = [match.group(1).strip("\"'")] if match else []
        encodings.extend(["utf-8", "windows-1252"])
        for encoding in encodings:
            try:
                return data.decode(encoding, errors="strict")
            except (LookupError, UnicodeDecodeError):
                continue
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _html_main_text(raw_html: str) -> tuple[str, str]:
        soup = BeautifulSoup(raw_html, "html.parser")
        title = collapse_whitespace(soup.title.get_text(" ", strip=True)) if soup.title else ""
        for node in soup.select("script,style,noscript,svg,canvas,form,nav,header,footer,aside"):
            node.decompose()
        source = soup.select_one("main") or soup.select_one("article") or soup.select_one('[role="main"]') or soup.body or soup
        text = collapse_whitespace(source.get_text(" ", strip=True))[:100_000]
        lowered = f"{title} {text[:1200]}".lower()
        blocked_markers = (
            "access denied",
            "sign in to continue",
            "log in to continue",
            "enable javascript",
            "javascript is required",
            "just a moment",
            "captcha",
            "page not found",
            "error 404",
        )
        if len(text) < 200:
            raise RetrievalFailure("PAGE_EMPTY_CONTENT", "HTML contains less than 200 readable characters")
        if any(marker in lowered for marker in blocked_markers) and len(text) < 1800:
            raise RetrievalFailure("PAGE_NOT_READABLE", "HTML is an access, login, JavaScript, CAPTCHA, or error page")
        return title, text

    @staticmethod
    def _pdf_text(data: bytes, fallback_title: str) -> tuple[str, str]:
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            text = collapse_whitespace(" ".join((page.extract_text() or "") for page in reader.pages[:60]))[:100_000]
            metadata_title = getattr(reader.metadata, "title", None) if reader.metadata else None
        except Exception as exc:
            raise RetrievalFailure("PAGE_NOT_READABLE", f"PDF extraction failed: {type(exc).__name__}") from exc
        if len(text) < 100:
            raise RetrievalFailure("PAGE_EMPTY_CONTENT", "PDF contains no usable extracted text")
        return collapse_whitespace(str(metadata_title or fallback_title)), text

    def open_top(self, results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        pages: list[dict[str, Any]] = []
        attempts: list[dict[str, Any]] = []
        # Failed page opens do not consume the readable-page budget.  The
        # caller supplies at most six accepted results; stop after three
        # successful readable pages or after every accepted result was tried.
        for result in results:
            if len(pages) >= self.max_open:
                break
            requested_url = str(result["url"])
            started = time.perf_counter()
            try:
                response = self._get(requested_url, "PAGE")
                content_type = str(response["content_type"])
                lowered = content_type.lower()
                final_url = str(response["final_url"])
                if "pdf" in lowered or final_url.lower().endswith(".pdf"):
                    page_title, visible_text = self._pdf_text(response["data"], str(result.get("title") or ""))
                    extraction_backend = "pypdf"
                elif "html" in lowered or lowered.startswith("text/"):
                    page_title, visible_text = self._html_main_text(self._decode_html(response["data"], content_type))
                    extraction_backend = "beautifulsoup_html"
                else:
                    raise RetrievalFailure(
                        "PAGE_UNSUPPORTED_CONTENT",
                        f"unsupported content type {content_type!r}",
                        status=response["status"],
                        final_url=final_url,
                        content_type=content_type,
                        retry_events=response["retry_events"],
                    )
                pages.append(
                    {
                        "requested_url": requested_url,
                        "final_url": final_url,
                        "rank": result.get("rank"),
                        "title": page_title or str(result.get("title") or ""),
                        "publisher": (urllib.parse.urlsplit(final_url).hostname or "").lower(),
                        "content_type": content_type,
                        "backend": extraction_backend,
                        "visible_text": visible_text,
                    }
                )
                attempts.append(
                    {
                        "requested_url": requested_url,
                        "final_url": final_url,
                        "status": response["status"],
                        "content_type": content_type,
                        "backend": "requests",
                        "readable": True,
                        "failure_type": None,
                        "failure_detail": None,
                        "wall_seconds": time.perf_counter() - started,
                        "retry_events": response["retry_events"],
                        "redirects": response["redirects"],
                    }
                )
            except RetrievalFailure as exc:
                attempts.append(
                    {
                        "requested_url": requested_url,
                        "final_url": exc.final_url,
                        "status": exc.status,
                        "content_type": exc.content_type,
                        "backend": "requests",
                        "readable": False,
                        "failure_type": exc.failure_type,
                        "failure_detail": exc.detail,
                        "wall_seconds": time.perf_counter() - started,
                        "retry_events": exc.retry_events or [],
                        "redirects": [],
                    }
                )
            except Exception as exc:
                failure_type = self._classify_exception(exc, "PAGE")
                attempts.append(
                    {
                        "requested_url": requested_url,
                        "final_url": None,
                        "status": None,
                        "content_type": None,
                        "backend": "requests",
                        "readable": False,
                        "failure_type": failure_type,
                        "failure_detail": _exception_chain(exc)[:1000],
                        "wall_seconds": time.perf_counter() - started,
                        "retry_events": [],
                        "redirects": [],
                    }
                )
        return pages, attempts


def network_test(output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"network-test output already exists: {output_path}")
    from common import MODEL, REASONING_EFFORT, TEMPERATURE, StrictAPIClient

    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = StrictAPIClient.from_environment(
        output_path.parent,
        method="Direct-WebSearch-Small-Smoke",
        task_id="NO_FORMAL_TASK",
        timeout_seconds=180,
    )
    retriever = PublicWebRetriever(max_results=6, max_open=3, search_client=client)
    queries = (
        "site:irs.gov taxpayer rights publication 1 official",
        "UK government national minimum wage rates official",
    )
    result: dict[str, Any] = {
        "schema_version": "searchworthyor.direct_functional.responses_network_smoke.v1",
        "formal_task_executed": False,
        "benchmark_task_executed": False,
        "backend": "shubiaobiao_responses_web_search",
        "requested_model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "temperature": TEMPERATURE,
        "queries": list(queries),
        "connect_timeout_seconds": retriever.connect_timeout_seconds,
        "read_timeout_seconds": retriever.read_timeout_seconds,
    }
    try:
        searches = [retriever.search(query) for query in queries]
        pages, attempts = retriever.open_top(
            [
                {"rank": 1, "title": "Internal Revenue Service", "url": "https://irs.gov/"},
                {"rank": 2, "title": "Your Rights as a Taxpayer", "url": "https://www.irs.gov/pub/irs-pdf/p1.pdf"},
            ]
        )
        mime_types = {str(page.get("content_type") or "").lower() for page in pages}
        search_summaries = [
            {
                "planned_query": search["planned_query"],
                "executed_query": search["executed_query"],
                "query_rewritten": search["query_rewritten"],
                "actual_model": search["actual_model"],
                "web_search_call_count": search["web_search_call_count"],
                "backend_raw_result_count": search["backend_raw_result_count"],
                "normalized_raw_result_count": search["normalized_raw_result_count"],
                "exposed_result_count": search["exposed_result_count"],
                "official_candidate_count": sum(bool(row.get("official_candidate")) for row in search["results"]),
                "results": search["results"],
                "retry_events": search["retry_events"],
                "wall_seconds": search["wall_seconds"],
            }
            for search in searches
        ]
        result.update(
            {
                "searches": search_summaries,
                "page_attempts": attempts,
                "html_readable": any("html" in mime for mime in mime_types),
                "pdf_readable": any("pdf" in mime for mime in mime_types),
                "redirect_observed": any(bool(row.get("redirects")) for row in attempts),
                "timeout_classification": retriever._classify_exception(requests.exceptions.ReadTimeout("probe"), "PAGE"),
                "tls_classification": retriever._classify_exception(requests.exceptions.SSLError("probe"), "SEARCH"),
            }
        )
        result["status"] = "PASS" if (
            len(search_summaries) == len(queries)
            and all(row["actual_model"] == MODEL for row in search_summaries)
            and all(row["web_search_call_count"] == 1 for row in search_summaries)
            and all(0 < row["exposed_result_count"] <= retriever.max_results for row in search_summaries)
            and all(row["backend_raw_result_count"] >= row["normalized_raw_result_count"] >= row["exposed_result_count"] for row in search_summaries)
            and all(row["official_candidate_count"] > 0 for row in search_summaries)
            and result["html_readable"]
            and result["pdf_readable"]
            and result["redirect_observed"]
            and result["timeout_classification"] == "PAGE_TIMEOUT"
            and result["tls_classification"] == "SEARCH_TLS_FAILURE"
        ) else "FAIL"
    except RetrievalFailure as exc:
        result.update({"status": "FAIL", "failure": exc.as_dict()})
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="SearchWorthyOR deterministic web retrieval checks")
    parser.add_argument("--network-test-output", type=Path, required=True)
    args = parser.parse_args()
    result = network_test(args.network_test_output)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
