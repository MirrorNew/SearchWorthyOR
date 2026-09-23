"""shubiaobiao model/search calls and Baseline-style direct page reading."""
import json
import math
from email.utils import parsedate_to_datetime
import http.client
import os
import re
from pathlib import Path
import time
from urllib.parse import urlsplit
import urllib.error
import urllib.request
from uuid import uuid4

from searchworthy.codex_handoff import HandoffFailure, _usage
from searchworthy.runtime import write, BudgetExhausted
from searchworthy.page_read import read_page, CHANNEL as READ_CHANNEL

CHANNEL = 'SHUBIAOBIAO_API'
WEB_CHANNEL = 'SHUBIAOBIAO_WEB'
BASE_URL = 'https://api.shubiaobiao.cn/v1'


class ResponseProtocolError(ValueError):
    """No complete, internally consistent provider response was received."""


class SearchToolDeliveryError(ValueError):
    """Completed tool envelope explicitly says no tool response was delivered.

    Not automatically retryable: invalid arguments versus service failure is unknown.
    """


class MissingSearchToolCall(ValueError):
    """Search delivery contains prose but no observable search tool action."""


def _text_only_search_delivery(parsed):
    if parsed.get('status') != 'completed' or parsed.get('error') or parsed.get('incomplete_details'):
        return False
    output = parsed.get('output', [])
    if not isinstance(output, list) or any(not isinstance(x, dict) or
            x.get('type') not in {'message', 'reasoning'} for x in output):
        return False
    messages = [x for x in output if x.get('type') == 'message']
    if not messages:
        return False
    return all(x.get('role') == 'assistant' and x.get('status') == 'completed'
        and isinstance(x.get('content'), list) and x['content']
        and all(isinstance(part, dict) and part.get('type') == 'output_text'
                and isinstance(part.get('text'), str) and part['text'].strip()
                and not part.get('refusal') for part in x['content']) for x in messages)


def load_credentials(config_root):
    root = Path(config_root)
    values = {}
    path = os.environ.get('SEARCHWORTHY_ENV_FILE')
    if not path:
        local = root / 'configs/local_runtime.json'
        if local.is_file():
            path = json.loads(local.read_text(encoding='utf-8-sig'))['credential_file']
    if path:
        path = Path(path).expanduser()
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                name, value = line.split('=', 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                values[name.strip()] = value
    base = (os.environ.get('OPENOR_BASE_URL') or values.get('OPENOR_BASE_URL') or BASE_URL).rstrip('/')
    if base != BASE_URL:
        raise ValueError('Expected the retained shubiaobiao HTTPS endpoint')
    key = os.environ.get('OPENOR_API_KEY') or values.get('OPENOR_API_KEY')
    if not key or not key.strip():
        raise ValueError('OPENOR_API_KEY is unavailable in the retained credential source')
    return base, key.strip()


def parse_response(raw_bytes, *, allow_web=False):
    try:
        text = raw_bytes.decode('utf-8-sig').strip()
    except UnicodeDecodeError as exc:
        raise ResponseProtocolError('Provider response is not valid UTF-8') from exc
    if text.startswith('{'):
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ResponseProtocolError('Provider response envelope is not valid JSON') from exc
        if not isinstance(result, dict):
            raise ResponseProtocolError('Response must be an object')
        return result
    completed = []
    identity = None
    done = False
    for frame in text.replace('\r\n', '\n').replace('\r', '\n').split('\n\n'):
        data = '\n'.join(line[5:].lstrip(' ') for line in frame.splitlines() if line.startswith('data:'))
        if not data:
            continue
        if data == '[DONE]' and not done:
            done = True
            continue
        if done or completed:
            raise ResponseProtocolError('Unexpected SSE data after the terminal response')
        try:
            event = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ResponseProtocolError('Provider SSE event is not valid JSON') from exc
        if not isinstance(event, dict):
            raise ResponseProtocolError('SSE event must be an object')
        if event.get('type') in {'error', 'response.failed', 'response.incomplete'}:
            raise ValueError('Provider reported a failed or incomplete response')
        item = event.get('item')
        permitted_web = allow_web and ('web_search_call' in str(event.get('type', ''))
                                      or isinstance(item, dict) and item.get('type') == 'web_search_call')
        if not permitted_web and ('_call' in str(event.get('type', ''))
                or isinstance(item, dict) and item.get('type') not in {'message', 'reasoning'}):
            raise ValueError('Model stream unexpectedly contains a tool event')
        response = event.get('response')
        if isinstance(response, dict) and response.get('id'):
            if identity is not None and response['id'] != identity:
                raise ResponseProtocolError('SSE response identity changed')
            identity = response['id']
        if event.get('type') == 'response.completed':
            if not isinstance(response, dict):
                raise ResponseProtocolError('Completed SSE event has no Response object')
            completed.append(response)
    if len(completed) != 1:
        raise ResponseProtocolError('Expected exactly one completed Response; incomplete or duplicate stream')
    return completed[0]


def validate_response(parsed, model_config):
    if parsed.get('status') != 'completed' or parsed.get('error') or parsed.get('incomplete_details'):
        raise ValueError('Provider response is not completed')
    reasoning = parsed.get('reasoning')
    if reasoning is not None and not isinstance(reasoning, dict):
        raise ValueError('Invalid provider reasoning metadata')
    if parsed.get('temperature') is not None and type(parsed['temperature']) not in (int, float):
        raise ValueError('Invalid provider temperature metadata')
    observed = {'name': parsed.get('model'), 'temperature': parsed.get('temperature'),
                'reasoning_effort': (reasoning or {}).get('effort')}
    for key, value in observed.items():
        if value is not None and value != model_config.get(key):
            raise ValueError('Provider echoed a different ' + key)


def response_text(parsed, model_config):
    validate_response(parsed, model_config)
    if parsed.get('tools') not in (None, []):
        raise ValueError('Model stage unexpectedly exposed tools')
    output = parsed.get('output')
    if not isinstance(output, list) or not output:
        raise ValueError('Completed response has no output')
    messages = []
    for item in output:
        if not isinstance(item, dict):
            raise ValueError('Invalid response output item')
        if item.get('type') == 'reasoning':
            continue
        if (item.get('type') != 'message' or item.get('role') != 'assistant'
                or item.get('status') not in (None, 'completed')):
            raise ValueError('Model stage contains a tool or incomplete message')
        content = item.get('content')
        if not isinstance(content, list) or not content:
            raise ValueError('Assistant message has no content')
        fragments = []
        for part in content:
            if not isinstance(part, dict) or part.get('type') != 'output_text' or not isinstance(part.get('text'), str):
                raise ValueError('Assistant output is not text')
            if part.get('refusal'):
                raise ValueError('Assistant refused the model stage')
            fragments.append(part['text'])
        messages.append((item.get('phase'), ''.join(fragments)))
    phases = [phase for phase, _ in messages]
    if phases == [None]:
        result = messages[0][1]  # Legacy single assistant message.
    elif phases and phases[-1] == 'final_answer' and all(p == 'commentary' for p in phases[:-1]):
        result = messages[-1][1]  # All messages were validated before selecting the final.
    else:
        raise ValueError('Expected one unambiguous final assistant answer')
    if not result.strip():
        raise ValueError('No complete assistant text')
    return result


def _web_call(parsed, action):
    if any(not isinstance(x, dict) or x.get('type') not in {'web_search_call', 'message', 'reasoning'}
           for x in parsed.get('output', [])):
        raise ValueError('Retrieval response contains an unexpected tool')
    calls = [x for x in parsed.get('output', []) if isinstance(x, dict) and x.get('type') == 'web_search_call']
    if action == 'search' and not calls and _text_only_search_delivery(parsed):
        raise MissingSearchToolCall('Search response has text but no observed search tool action')
    if (len(calls) != 1 or calls[0].get('status') != 'completed'
            or (calls[0].get('action') or {}).get('type') != action):
        raise ValueError('Expected one completed ' + action + ' tool action')
    return calls[0]


def search_results(parsed, query):
    call = _web_call(parsed, 'search')
    action = call['action']
    queries = action.get('queries') or ([action['query']] if action.get('query') else [])
    # A scalar containing exactly the requested query is an unambiguous shape alias.
    # Never trim, rewrite, drop extra searches or accept an incomplete tool call.
    if isinstance(queries, str) and queries == query:
        queries = [queries]
    if (not isinstance(queries, list) or queries != [query]
            or action.get('query') is not None and action['query'] != query):
        raise ValueError('Provider changed or expanded the programmed search query')
    results = []
    for row in call.get('results') or action.get('sources') or []:
        if isinstance(row, dict) and isinstance(row.get('url'), str) and urlsplit(row['url']).scheme == 'https':
            results.append({'url': row['url'], 'title': row.get('title', ''), 'snippet': row.get('snippet', '')})
    # An empty result accompanied by this explicit diagnostic is not a zero-hit search.
    if not results and any(
            part.get('type') == 'output_text'
            and isinstance(part.get('text'), str)
            and 'found no tool response.' in part['text'].casefold()
            for item in parsed.get('output', []) if isinstance(item, dict) and item.get('type') == 'message'
            for part in item.get('content', []) if isinstance(part, dict)):
        raise SearchToolDeliveryError('Search tool returned no response; cause requires review, not a valid zero-hit result')
    return {'query': query, 'executed_queries': queries, 'results': results,
            'backend': WEB_CHANNEL, 'tool_call_count': 1}


def _same_url(left, right):
    def normalized(value):
        p = urlsplit(value.strip())
        return p.scheme.lower(), p.netloc.lower(), p.path or '/', p.query
    return isinstance(left, str) and isinstance(right, str) and normalized(left) == normalized(right)


def read_pages(parsed, row):
    attempt = {'requested_url': row['url'], 'backend': WEB_CHANNEL, 'readable': False}
    try:
        call = _web_call(parsed, 'open_page')
        if not _same_url(call['action'].get('url'), row['url']):
            raise ValueError('Opened URL does not match the programmed target')
    except ValueError as exc:
        return [], [{**attempt, 'failure_type': 'READ_NOT_EXECUTED', 'failure_detail': str(exc)}]
    records = call.get('results') or []
    if isinstance(records, dict):
        records = [records]
    for source in records:
        if not isinstance(source, dict) or not _same_url(source.get('url'), row['url']):
            continue
        # Search snippets and assistant output are never admitted as page text.
        body = next((source[k] for k in ('visible_text', 'text', 'content', 'body')
                     if isinstance(source.get(k), str) and source[k].strip()), None)
        if body:
            page = {'url': row['url'], 'requested_url': row['url'], 'title': source.get('title') or row.get('title', ''),
                    'visible_text': body, 'backend': WEB_CHANNEL, 'source_kind': 'EXTERNAL',
                    'provider_tool_call_id': call.get('id')}
            return [page], [{**attempt, 'final_url': row['url'], 'readable': True, 'visible_text_chars': len(body)}]
    return [], [{**attempt, 'failure_type': 'READ_BODY_UNAVAILABLE',
                 'failure_detail': 'Provider opened the URL but did not expose URL-bound tool page text'}]


def post_response(url, key, payload, deadline, raw_path):
    """First response body byte within 60s; original overall deadline thereafter."""
    if url != BASE_URL + '/responses':
        raise ValueError('Unexpected provider URL')
    first_response_deadline = min(deadline, time.monotonic() + 60.)
    received_data = False
    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError('API request deadline exhausted')
        return seconds
    def response_wait():
        seconds = remaining()
        if not received_data:
            seconds = min(seconds, first_response_deadline - time.monotonic())
            if seconds <= 0:
                raise TimeoutError('No response body data within 60 seconds')
        return seconds
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    # Retain the workstation proxy configuration used by the original API client.
    opener = urllib.request.build_opener(NoRedirect())
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(url, data=body, method='POST',
                                    headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                                             'Accept': 'text/event-stream'})
    try:
        response = opener.open(request, timeout=response_wait())
    except urllib.error.HTTPError as exc:
        response = exc
    try:
        # HTTPError wraps an HTTPResponse; successful opens return it directly.
        reader = response.fp if isinstance(response, urllib.error.HTTPError) else response
        socket = getattr(getattr(reader.fp, 'raw', None), '_sock', None)
        if socket is None:
            raise RuntimeError('Cannot enforce API read deadline')
        with Path(raw_path).open('wb') as stream:
            while True:
                if reader.isclosed():
                    break
                socket.settimeout(response_wait())
                chunk = reader.read1(65536)
                if not chunk:
                    break
                stream.write(chunk)
                stream.flush()
                response_wait()
                received_data = True
        if response.status != 200:
            if isinstance(response, urllib.error.HTTPError) and response.code == 429:
                raise response  # Preserve throttling Retry-After headers; other errors retain their interface.
            raise RuntimeError('Provider HTTP status ' + str(response.status))
        return Path(raw_path).read_bytes()
    finally:
        response.close()


def _provider_error_codes(raw):
    text = raw.decode('utf-8-sig', errors='replace').strip()
    chunks = [text] if text.startswith('{') else [
        '\n'.join(line[5:].lstrip(' ') for line in frame.splitlines() if line.startswith('data:'))
        for frame in text.replace('\r\n', '\n').replace('\r', '\n').split('\n\n')]
    codes = set()
    for chunk in chunks:
        try:
            item = json.loads(chunk)
        except (ValueError, TypeError):
            continue
        if not isinstance(item, dict):
            continue
        response = item.get('response') if isinstance(item.get('response'), dict) else item
        for record in (item, response):
            detail = record.get('error')
            if isinstance(detail, dict) and isinstance(detail.get('code'), str):
                codes.add(detail['code'])
            if record.get('type') == 'error' and isinstance(record.get('code'), str):
                codes.add(record['code'])
    return codes


def retryable_failure(error, raw_path):
    """Retry failed delivery, never redraw a complete protocol-valid stage response."""
    cause = error.__cause__
    codes = set()
    protocol_error = None
    if raw_path.is_file():
        raw_bytes = raw_path.read_bytes()
        try:
            complete = parse_response(raw_bytes, allow_web=True)
        except ResponseProtocolError as exc:
            protocol_error = exc
        except ValueError:
            pass  # Provider failure/error events are classified by their error code below.
        else:
            if complete.get('status') == 'completed' and not complete.get('error') and not complete.get('incomplete_details'):
                # Do not accept prose as search evidence, or retry any valid model/tool output.
                return isinstance(cause, MissingSearchToolCall) and _text_only_search_delivery(complete)
        codes = _provider_error_codes(raw_bytes)
    if isinstance(cause, ResponseProtocolError) and protocol_error is not None:
        return True
    if isinstance(cause, urllib.error.HTTPError):
        return cause.code == 429 or 500 <= cause.code <= 599
    if isinstance(cause, (TimeoutError, ConnectionError, http.client.IncompleteRead, urllib.error.URLError)):
        return True
    if isinstance(cause, RuntimeError) and re.fullmatch(r'Provider HTTP status (429|5\d\d)', str(cause)):
        return True
    return (isinstance(cause, ValueError) and str(cause) in {
        'Provider reported a failed or incomplete response', 'Provider response is not completed'}
        and bool(codes & {'rate_limit_exceeded', 'server_error', 'service_unavailable',
                         'api_connection_error', 'upstream_unavailable', 'gateway_queue_full'}))


def retry_delay(error, raw_path, index):
    """Explicit throttling waits at most 20 seconds, under the original deadline."""
    cause = error.__cause__
    rate_limited = (isinstance(cause, urllib.error.HTTPError) and cause.code == 429
                    or isinstance(cause, RuntimeError) and str(cause) == 'Provider HTTP status 429'
                    or raw_path.is_file() and bool({'rate_limit_exceeded', 'gateway_queue_full'}
                                                  & _provider_error_codes(raw_path.read_bytes())))
    if not rate_limited:
        return 2. * (index + 1), 'TECHNICAL_BACKOFF'
    # HTTPError already owns response headers; do not add a parallel metadata layer.
    hint = cause.headers.get('Retry-After') if isinstance(cause, urllib.error.HTTPError) and cause.headers else None
    if isinstance(hint, str):
        try:
            if re.fullmatch(r'\d+', hint.strip()):
                return min(20., int(hint.strip())), 'RATE_LIMIT_RETRY_AFTER'
            else:
                stamp = parsedate_to_datetime(hint)
                if stamp.tzinfo is None:
                    raise ValueError('Retry-After date has no timezone')
                delay = max(0., stamp.timestamp() - time.time())
            if math.isfinite(delay):
                return min(20., delay), 'RATE_LIMIT_RETRY_AFTER'
        except (ValueError, TypeError, OverflowError):
            pass
    return 20., 'RATE_LIMIT_BACKOFF'


class ShubiaobiaoTransport:
    """Model/search use the retained API; READ downloads original pages directly."""
    channel = CHANNEL
    accounts_read = True

    def __init__(self, ctx, revision_getter):
        self.ctx, self.revision_getter = ctx, revision_getter
        # Record the original hard case deadline; ctx.remaining() reserves the
        # final two seconds inside it for state/result writes at every work call.
        self.deadline = time.time() + max(0., min(ctx.config['budgets']['wall_seconds'], 1200.) - ctx.elapsed())

    def model(self, messages, purpose, output_schema=None):
        return self._request(messages, purpose, output_schema)

    def search(self, query):
        if (not isinstance(query, str) or not query.strip() or len(query) > 320
                or re.search(r'[\u3400-\u9fff]|\bSWOR|SearchWorthy|benchmark.{0,15}answer|gold.{0,8}answer', query, re.I)):
            raise ValueError('Search requires an English domain query without benchmark IDs or answers')
        return self._request({'query': query}, 'SEARCH', kind='search')

    def read(self, row):
        pages, attempts = read_page(self.ctx, row)
        return {'pages': pages, 'attempts': attempts}

    def usage_summary(self):
        path = self.ctx.directory / 'api_calls.jsonl'
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []
        read_log = self.ctx.directory / 'read_calls.jsonl'
        reads = [json.loads(line) for line in read_log.read_text(encoding='utf-8').splitlines() if line.strip()] if read_log.exists() else []
        temperatures = [r.get('actual_temperature') for r in rows]
        result = {'calls': len(rows), 'model_calls': sum(r['kind'] == 'model' for r in rows),
                  'search_calls': sum(r['kind'] == 'search' for r in rows), 'read_calls': len(reads) + sum(r['kind'] == 'read' for r in rows),
                  'channel': CHANNEL, 'retrieval_channel': WEB_CHANNEL, 'read_channel': READ_CHANNEL,
                  'read_http_requests': sum(r['http_requests'] for r in reads), 'usage_complete': bool(rows or reads),
                  'actual_temperature': temperatures[0] if temperatures and all(v == temperatures[0] for v in temperatures) else None,
                  'strict_token_budget_verified': False, 'wall_seconds': sum(r['wall_seconds'] for r in rows + reads),
                  'actual_models': sorted({r['actual_model'] for r in rows if r.get('actual_model')}),
                  'usage_scope': 'all model/search API operations; direct HTTP READ uses zero LLM tokens'}
        for source, target in (('input_tokens', 'prompt_tokens'), ('output_tokens', 'completion_tokens'), ('total_tokens', 'total_tokens')):
            values = [(r.get('usage') or {}).get(source) for r in rows]
            known = [v for v in values if type(v) is int]
            complete = bool(values or reads) and len(known) == len(values)
            result[target] = sum(known) if complete else None
            result['known_' + target] = sum(known) if known or reads and not rows else None
            result['usage_complete'] = result['usage_complete'] and complete
        return result

    def _request(self, messages, purpose, output_schema=None, *, kind='model'):
        retry_of = None
        maximum = min(2, max(0, self.ctx.config.get('budgets', {}).get('technical_retries', 0)))
        for index in range(maximum + 1):
            try:
                return self._request_once(messages, purpose, output_schema, kind=kind,
                                          retry_of=retry_of, retry_index=index)
            except HandoffFailure as exc:
                raw_path = self.ctx.directory / 'api' / exc.request_id / 'raw_response.txt'
                if index >= maximum or not retryable_failure(exc, raw_path):
                    raise
                cap = self.ctx.config.get('budgets', {}).get(kind)
                if cap is not None and self.ctx.resources.get(kind, 0) >= cap:
                    raise BudgetExhausted(kind) from exc
                delay, policy = retry_delay(exc, raw_path, index)
                if self.ctx.remaining() <= delay or self.deadline - time.time() <= delay:
                    self.ctx.event('API_RETRY_SKIPPED', stage=purpose, kind_of_call=kind,
                                   previous_request_id=exc.request_id, reason='INSUFFICIENT_ORIGINAL_TIME',
                                   delay_seconds=delay, backoff_policy=policy)
                    raise
                retry_of = retry_of or exc.request_id
                self.ctx.event('API_RETRY_SCHEDULED', stage=purpose, kind_of_call=kind,
                               retry_of=retry_of, previous_request_id=exc.request_id,
                               retry_index=index + 1, delay_seconds=delay, backoff_policy=policy)
                time.sleep(delay)
                self.ctx.reserve(kind, purpose=purpose, channel=CHANNEL if kind == 'model' else WEB_CHANNEL,
                                 retry_of=retry_of, retry_index=index + 1)

    def _request_once(self, messages, purpose, output_schema=None, *, kind='model', retry_of=None, retry_index=0):
        started = time.monotonic()
        request_id = uuid4().hex
        folder = self.ctx.directory / 'api' / request_id
        folder.mkdir(parents=True)
        config = self.ctx.config.get('model', {})
        request = {'request_id': request_id, 'case_id': self.ctx.eval_id, 'stage': purpose,
                   'retry_of': retry_of, 'retry_index': retry_index,
                   'model_revision': self.revision_getter(), 'kind': kind, 'channel': CHANNEL if kind == 'model' else WEB_CHANNEL,
                   'case_deadline_unix': self.deadline, 'output_schema': output_schema or {'type': 'object'},
                   'input': {'messages': messages} if kind == 'model' else messages}
        payload = {'model': config.get('name'), 'reasoning': {'effort': config.get('reasoning_effort')},
                   'temperature': config.get('temperature'), 'stream': True}
        if kind == 'model':
            payload['input'] = messages
        else:
            payload.update(tools=[{'type': 'web_search', 'search_context_size': 'high'}],
                           tool_choice='required', include=['web_search_call.results'])
            payload['input'] = (
                'Execute exactly one public web search for the planned English query. Do not change the query, '
                'run other searches, open pages, or answer from memory. Return the observed tool results.\nPLANNED_QUERY_JSON='
                + json.dumps(messages['query'], ensure_ascii=False)) if kind == 'search' else (
                'Use the web tool open_page action exactly once on the specified URL. Do not search or open other URLs. '
                'Expose original page text through the tool result. Do not substitute a generated summary or search snippet.\nTARGET_URL_JSON='
                + json.dumps(messages['url'], ensure_ascii=False))
        budgets = self.ctx.config.get('budgets', {})
        output_limit = budgets.get('output_tokens', config.get('max_tokens'))
        if output_limit is not None:
            payload['max_output_tokens'] = output_limit
        write(folder / 'request.json', {**request, 'payload': payload})
        state = {'request_id': request_id, 'state': 'STARTED'}
        write(folder / 'pending.json', state)
        parsed = None
        attempted = False
        try:
            if self.ctx.remaining() <= 0 or time.time() >= self.deadline:
                raise TimeoutError('Original case deadline exhausted')
            base, key = load_credentials(Path(__file__).resolve().parents[1])
            deadline = time.monotonic() + min(650., self.ctx.remaining(), self.deadline - time.time())
            attempted = True
            raw = post_response(base + '/responses', key, payload, deadline, folder / 'raw_response.txt')
            if time.monotonic() >= deadline or self.ctx.remaining() <= 0 or time.time() >= self.deadline:
                raise TimeoutError('Response arrived after the original request or case deadline')
            if request['model_revision'] != self.revision_getter():
                raise ValueError('Model revision changed while request was pending')
            parsed = parse_response(raw, allow_web=kind != 'model')
            write(folder / 'provider_response.json', parsed)
            validate_response(parsed, config)
            text = response_text(parsed, config) if kind == 'model' else (
                search_results(parsed, messages['query']) if kind == 'search' else read_pages(parsed, messages))
            usage = _usage(parsed.get('usage'))
            limits = {'input_tokens': budgets.get('input_tokens'), 'output_tokens': output_limit,
                      'total_tokens': budgets.get('tokens', budgets.get('total_tokens'))}
            if any(limit is not None and usage[k] is not None and usage[k] > limit for k, limit in limits.items()):
                raise ValueError('Observed token usage exceeds configured limit')
            write(folder / 'response.json', {**{k: request[k] for k in ('request_id', 'case_id', 'stage', 'model_revision')},
                  'content': text, 'provider_response_id': parsed.get('id'), 'received_at': time.time()})
            state.update(state='CONSUMED')
            return text
        except Exception as exc:
            state.update(state='TIMED_OUT' if isinstance(exc, TimeoutError) else 'FAILED',
                         error=type(exc).__name__ + ': ' + str(exc))
            raise HandoffFailure(state['state'], request_id, state['error']) from exc
        finally:
            write(folder / 'pending.json', state)
            observed = parsed if isinstance(parsed, dict) else {}
            usage = _usage(observed.get('usage'))
            reasoning = observed.get('reasoning')
            row = {'request_id': request_id, 'task_id': self.ctx.eval_id, 'method': self.ctx.method,
                   'retry_of': retry_of, 'retry_index': retry_index,
                   'purpose': purpose, 'kind': kind, 'api': 'responses_llm' if kind == 'model' else 'responses_web', 'channel': request['channel'],
                   'requested_model': config.get('name'), 'actual_model': observed.get('model') if isinstance(observed.get('model'), str) else None,
                   'reasoning_effort': config.get('reasoning_effort'),
                   'actual_reasoning_effort': reasoning.get('effort') if isinstance(reasoning, dict) else None,
                   'temperature': config.get('temperature'), 'actual_temperature': observed.get('temperature') if type(observed.get('temperature')) in (int, float) else None,
                   'usage': usage, 'observed_usage': usage, 'usage_unknown': any(v is None for v in usage.values()),
                   'status': state['state'], 'wall_seconds': time.monotonic() - started,
                   'upstream_attempts': int(attempted), 'case_deadline_unix': self.deadline,
                   'request_path': str(folder / 'request.json'), 'response_path': str(folder / 'response.json'),
                   'error_detail': state.get('error')}
            if kind != 'model':
                row['observed_tool_actions'] = [x.get('action') for x in observed.get('output', [])
                                                if isinstance(x, dict) and x.get('type') == 'web_search_call']
            with (self.ctx.directory / 'api_calls.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            self.ctx.event('API_' + state['state'], request_id=request_id, stage=purpose, channel=request['channel'])
