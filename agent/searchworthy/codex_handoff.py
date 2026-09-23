"""Single-use file handoff. Only the Codex parent task dispatches native tools."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

from searchworthy.runtime import InfrastructureStopped

CHANNEL = 'CODEX_LUNA_XHIGH'
MODEL = 'gpt-5.6-luna'
IDENTITY = ('request_id', 'case_id', 'stage', 'model_revision', 'kind')
TERMINAL = {'CONSUMED', 'FAILED', 'TIMED_OUT'}


class HandoffFailure(InfrastructureStopped):
    def __init__(self, status, request_id, message):
        self.status, self.request_id = status, request_id
        super().__init__(f'{status} [{request_id}]: {message}')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _write(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def _append(path, value):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')


@contextmanager
def _lock(folder):
    """Short metadata lock; a crashed owner leaves a visible failure, not a retry loop."""
    path = Path(folder) / '.lock'
    until = time.monotonic() + 2
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= until:
                raise HandoffFailure('FAILED', Path(folder).name, 'handoff metadata lock unavailable')
            time.sleep(.02)
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def _reject(folder, reason, response=None):
    _append(Path(folder) / 'rejections.jsonl', {'time': time.time(), 'reason': reason, 'response': response})
    raise HandoffFailure('REJECTED', Path(folder).name, reason)


def compact_schema(schema):
    """Losslessly share repeated schema nodes; keep the on-disk validation schema intact."""
    if not isinstance(schema, dict):
        return schema
    # Moving an identifier-bearing schema can change relative reference resolution.
    if any(token in json.dumps(schema) for token in ('"$id"', '"$anchor"', '"$dynamicRef"', '"$dynamicAnchor"')):
        return schema
    maps = {'properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas'}
    lists = {'allOf', 'anyOf', 'oneOf', 'prefixItems'}
    singles = {'items', 'additionalItems', 'additionalProperties', 'unevaluatedProperties',
               'unevaluatedItems', 'contains', 'not', 'if', 'then', 'else', 'propertyNames'}
    counts, originals = {}, {}
    def key(node):
        return json.dumps(node, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    def transform(node, visit):
        if not isinstance(node, dict):
            return node
        result = {}
        for name, value in node.items():
            if name in maps and isinstance(value, dict):
                result[name] = {k: visit(v) for k, v in value.items()}
            elif name in lists and isinstance(value, list):
                result[name] = [visit(v) for v in value]
            elif name in singles:
                result[name] = [visit(v) for v in value] if isinstance(value, list) else visit(value)
            else:
                result[name] = value
        return result
    def count(node):
        if isinstance(node, dict):
            encoded = key(node)
            counts[encoded] = counts.get(encoded, 0) + 1
            originals[encoded] = node
            transform(node, count)
        return node
    count(schema)
    existing = set(schema.get('$defs', {}))
    names = {}
    for encoded, n in counts.items():
        if n > 1 and len(encoded) > 100:
            name = '_stage_' + str(len(names))
            while name in existing:
                name += '_'
            names[encoded] = name
    def shorten(node, skip=None):
        if not isinstance(node, dict):
            return node
        encoded = key(node)
        if encoded in names and encoded != skip:
            return {'$ref': '#/$defs/' + names[encoded]}
        return transform(node, shorten)
    result = shorten(schema)
    if names:
        result['$defs'] = {**result.get('$defs', {}),
                           **{name: shorten(originals[encoded], skip=encoded) for encoded, name in names.items()}}
    return result if len(key(result)) < len(key(schema)) else schema


def stage_prompt(request):
    """Only current-stage material; callers must spawn with fork_turns='none'."""
    if request['kind'] != 'model':
        raise ValueError('Search/read requests are executed by the parent with independent tools')
    body = {'request_id': request['request_id'], 'case_id': request['case_id'],
            'stage': request['stage'], 'model_revision': request['model_revision'],
            'output_schema': compact_schema(request['output_schema']), 'input': request['input']}
    return ('Complete exactly this one stage using only the supplied material. Do not use tools, '
            'search, read files, run a solver, modify code, spawn agents, or decide subsequent stages. '
            'Return one complete JSON object only, with no Markdown or commentary. '
            'Request and case IDs are tracing metadata; do not copy them into stage output fields. '
            'Use UNKNOWN when the supplied evidence does not establish a requested judgment.\n'
            + json.dumps(body, ensure_ascii=False, separators=(',', ':')))


def _agent_path(owner):
    """One exact owner identity; a legacy short name means only /root/<name>."""
    if not isinstance(owner, str):
        return None
    if re.fullmatch(r'[A-Za-z0-9_-]+', owner):
        return '/root/' + owner
    return owner if re.fullmatch(r'/root(?:/[A-Za-z0-9_-]+)+', owner) else None


def claim(request_path, owner):
    request_path = Path(request_path)
    folder = request_path.parent
    with _lock(folder):
        request, state = _read(request_path), _read(folder / 'pending.json')
        if state['state'] != 'QUEUED':
            _reject(folder, 'request already claimed or terminal', {'owner': owner})
        if time.time() >= request['case_deadline_unix']:
            _reject(folder, 'request deadline has passed', {'owner': owner})
        if request['kind'] == 'model':
            canonical = _agent_path(owner)
            if canonical is None:
                _reject(folder, 'model claim requires one canonical agent path or exact short name', {'owner': owner})
            owner = canonical
        state.update(state='DISPATCHED', owner=owner, dispatched_at=time.time())
        _write(folder / 'pending.json', state)
    result = {**request, 'owner': owner, 'request_path': str(request_path),
              'prompt': (folder / 'prompt.txt').read_text(encoding='utf-8') if request['kind'] == 'model' else None}
    if request['kind'] == 'model':
        result.pop('input')
        result.pop('output_schema')
    return result


def submit(request_path, content=None, *, status='COMPLETED', error=None, usage=None,
           metadata=None, identity=None):
    """Parent records the complete final text, never a fabricated stand-in response."""
    request_path = Path(request_path)
    folder = request_path.parent
    with _lock(folder):
        request, state = _read(request_path), _read(folder / 'pending.json')
        rejected_response = {'status': status, 'content': content, 'error': error,
                             'usage': usage, 'metadata': metadata}
        if state['state'] != 'DISPATCHED' or (folder / 'response.json').exists():
            _reject(folder, 'response is duplicate, unclaimed, or already terminal', rejected_response)
        if time.time() >= request['case_deadline_unix']:
            _reject(folder, 'late response; original case deadline has passed', rejected_response)
        expected = {key: request[key] for key in IDENTITY}
        if identity is not None and identity != expected:
            _reject(folder, 'response identity does not match current request', identity)
        if status not in {'COMPLETED', 'FAILED', 'TIMED_OUT'}:
            _reject(folder, 'invalid response status')
        if status == 'COMPLETED' and (not isinstance(content, str) or not content.strip()):
            _reject(folder, 'completed response must contain complete nonempty raw text')
        if (request['kind'] == 'model'
                and isinstance(metadata, dict) and metadata.get('agent_id')
                and metadata['agent_id'] != _agent_path(state.get('owner'))):
            _reject(folder, 'response agent_id does not match the exact claimed owner', rejected_response)
        response = {**expected, 'status': status, 'content': content, 'error': error,
                    'usage': usage, 'metadata': metadata or {}, 'received_at': time.time()}
        _write(folder / 'response.json', response)
    return response


def _usage(raw):
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for key, alias in (('input_tokens', 'prompt_tokens'), ('output_tokens', 'completion_tokens'),
                       ('total_tokens', 'total_tokens')):
        value = raw.get(key, raw.get(alias))
        result[key] = value if type(value) is int and value >= 0 else None
    if result['total_tokens'] is None and all(result[k] is not None for k in ('input_tokens', 'output_tokens')):
        result['total_tokens'] = result['input_tokens'] + result['output_tokens']
    return result


class CodexTransport:
    def __init__(self, ctx, revision_getter):
        self.ctx, self.revision_getter = ctx, revision_getter
        self.deadline = time.time() + max(0., min(ctx.remaining(), 1200. - ctx.elapsed()))
        self.folder = ctx.directory / 'handoff'
        self.folder.mkdir(parents=True, exist_ok=True)

    def usage_summary(self):
        path = self.ctx.directory / 'api_calls.jsonl'
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines()
                if line.strip()] if path.exists() else []
        model_rows = [row for row in rows if row.get('kind') == 'model']
        result = {'calls': len(rows), 'model_calls': len(model_rows), 'channel': CHANNEL,
                  'search_calls': sum(row.get('kind') == 'search' for row in rows),
                  'read_calls': sum(row.get('kind') == 'read' for row in rows),
                  'usage_complete': bool(model_rows),
                  'wall_seconds': sum(row['wall_seconds'] for row in rows),
                  'actual_temperature': None, 'strict_token_budget_verified': False,
                  'actual_models': sorted({row['actual_model'] for row in model_rows if row.get('actual_model')})}
        for source, target in (('input_tokens', 'prompt_tokens'), ('output_tokens', 'completion_tokens'),
                               ('total_tokens', 'total_tokens')):
            values = [(row.get('usage') or {}).get(source) for row in model_rows]
            known = [value for value in values if type(value) is int]
            complete = bool(values) and len(known) == len(values)
            result[target] = sum(known) if complete else None
            result['known_' + target] = sum(known) if known else None
            result['usage_complete'] = result['usage_complete'] and complete
        return result

    def _record(self, request, state, response, started):
        usage = _usage((response or {}).get('usage'))
        metadata = (response or {}).get('metadata') or {}
        if not isinstance(metadata, dict):
            metadata = {}
        limits = request['token_limits']
        exceeded = any(usage[key] is not None and limit is not None and usage[key] > limit
                       for key, limit in limits.items())
        if exceeded:
            state.update(state='FAILED', error='observed native token usage exceeds configured limit')
            _write(self.folder / request['request_id'] / 'pending.json', state)
        row = {'request_id': request['request_id'], 'task_id': self.ctx.eval_id,
               'method': self.ctx.method, 'purpose': request['stage'], 'kind': request['kind'],
               'api': 'codex_parent_handoff', 'channel': CHANNEL,
               'requested_model': MODEL if request['kind'] == 'model' else None,
               'actual_model': metadata.get('actual_model'),
               'actual_model_source': 'Codex parent dispatch metadata',
               'actual_reasoning_effort': metadata.get('actual_reasoning_effort'),
               'actual_temperature': None, 'temperature': None,
               'usage': usage, 'observed_usage': usage,
               'usage_unknown': any(value is None for value in usage.values()),
               'token_limits': limits, 'observed_token_limit_exceeded': exceeded,
               'strict_token_budget_verified': False,
               'status': state['state'], 'wall_seconds': time.monotonic() - started,
               'queued_seconds': (state.get('dispatched_at') or time.time()) - request['queued_at'],
               'case_deadline_unix': request['case_deadline_unix'],
               'upstream_attempts': 1 if state.get('dispatched_at') else 0,
               'underlying_model_attempts_unknown': True,
               'request_path': str(self.folder / request['request_id'] / 'request.json'),
               'response_path': str(self.folder / request['request_id'] / 'response.json'),
               'error_detail': state.get('error'), 'metadata': metadata}
        _append(self.ctx.directory / 'api_calls.jsonl', row)
        self.ctx.event('HANDOFF_' + state['state'], request_id=request['request_id'],
                       stage=request['stage'], channel=CHANNEL)
        return exceeded

    def _exchange(self, kind, stage, data, output_schema):
        started = time.monotonic()
        request_id = uuid4().hex
        folder = self.folder / request_id
        folder.mkdir()
        budgets = self.ctx.config.get('budgets', {})
        model_config = self.ctx.config.get('model', {})
        limits = {'input_tokens': budgets.get('input_tokens'),
                  'output_tokens': budgets.get('output_tokens', model_config.get('max_tokens')),
                  'total_tokens': budgets.get('tokens', budgets.get('total_tokens'))}
        request = {'request_id': request_id, 'case_id': self.ctx.eval_id, 'stage': stage,
                   'model_revision': self.revision_getter(), 'kind': kind, 'model': MODEL,
                   'reasoning_effort': 'xhigh', 'channel': CHANNEL, 'temperature': None,
                   'queued_at': time.time(), 'case_elapsed_at_queue': self.ctx.elapsed(),
                   'case_deadline_unix': self.deadline, 'token_limits': limits,
                   'output_schema': output_schema, 'input': data,
                   'response_path': str(folder / 'response.json')}
        _write(folder / 'request.json', request)
        _write(folder / 'pending.json', {'state': 'QUEUED', 'request_id': request_id})
        if kind == 'model':
            (folder / 'prompt.txt').write_text(stage_prompt(request), encoding='utf-8')
        self.ctx.event('HANDOFF_QUEUED', request_id=request_id, stage=stage, kind_requested=kind,
                       request_path=str(folder / 'request.json'), channel=CHANNEL)
        response = None
        while True:
            with _lock(folder):
                state = _read(folder / 'pending.json')
                if not self.ctx.remaining() or time.time() >= self.deadline:
                    state.update(state='TIMED_OUT', error='original case wall-clock budget exhausted')
                elif self.revision_getter() != request['model_revision']:
                    state.update(state='FAILED', error='model revision changed while request was pending')
                elif (folder / 'response.json').exists():
                    try:
                        response = _read(folder / 'response.json')
                        if any(response.get(k) != request[k] for k in IDENTITY):
                            raise ValueError('response identity mismatch')
                        if response.get('received_at', self.deadline) >= self.deadline:
                            raise ValueError('response arrived after case deadline')
                        if state['state'] != 'DISPATCHED':
                            raise ValueError('response has no dispatch claim')
                        metadata = response.get('metadata')
                        if (kind == 'model' and isinstance(metadata, dict) and metadata.get('agent_id')
                                and metadata['agent_id'] != _agent_path(state.get('owner'))):
                            raise ValueError('response agent_id does not match the exact claimed owner')
                        if response.get('status') == 'COMPLETED':
                            if not isinstance(response.get('content'), str) or not response['content'].strip():
                                raise ValueError('response has no complete raw text')
                            state.update(state='CONSUMED', consumed_at=time.time())
                            if kind == 'model' and (not isinstance(metadata, dict)
                                    or metadata.get('actual_model') != MODEL
                                    or metadata.get('actual_reasoning_effort') != 'xhigh'
                                    or metadata.get('fork_turns') != 'none'
                                    or not isinstance(metadata.get('agent_id'), str)
                                    or not metadata['agent_id'].strip()
                                    or metadata.get('tools_used') != []):
                                state.update(state='FAILED', error='native stage dispatch violated model, context, or no-tools requirement')
                        elif response.get('status') in {'FAILED', 'TIMED_OUT'}:
                            state.update(state=response['status'], error=response.get('error') or 'native operation failed')
                        else:
                            raise ValueError('invalid response status')
                    except (ValueError, TypeError) as exc:
                        _append(folder / 'rejections.jsonl', {'time': time.time(), 'reason': str(exc)})
                        (folder / 'response.json').replace(folder / ('rejected_' + uuid4().hex + '.json'))
                        response = None
                if state['state'] in TERMINAL:
                    _write(folder / 'pending.json', state)
                    break
            time.sleep(min(.1, self.ctx.remaining()))
        exceeded = self._record(request, state, response, started)
        if state['state'] != 'CONSUMED':
            raise HandoffFailure(state['state'], request_id, state.get('error', 'operation failed'))
        if exceeded:
            raise HandoffFailure('FAILED', request_id, 'observed native token usage exceeds configured limit')
        return response['content']

    def model(self, messages, purpose, output_schema=None):
        return self._exchange('model', purpose, {'messages': messages}, output_schema or {'type': 'object'})

    def search(self, query):
        if (not isinstance(query, str) or not query.strip() or len(query) > 320
                or re.search(r'[\u3400-\u9fff]|\bSWOR|SearchWorthy|benchmark.{0,15}answer|gold.{0,8}answer', query, re.I)):
            raise ValueError('Search requires an English domain query without benchmark IDs or answer lookup')
        result = json.loads(self._exchange('search', 'SEARCH', {'query': query},
                            {'type': 'object', 'required': ['results'],
                             'properties': {'results': {'type': 'array'}}}))
        if not isinstance(result, dict) or not isinstance(result.get('results'), list):
            raise ValueError('SEARCH response must contain a results list')
        for row in result['results']:
            if not isinstance(row, dict) or not isinstance(row.get('url'), str):
                raise ValueError('SEARCH result requires a URL')
        return result

    def read(self, row):
        self.ctx.reserve('read', url=row['url'], channel='CODEX_WEB')
        result = json.loads(self._exchange('read', 'READ', {'source': row},
                            {'type': 'object', 'required': ['pages', 'attempts'],
                             'properties': {'pages': {'type': 'array'}, 'attempts': {'type': 'array'}}}))
        if not isinstance(result, dict) or any(not isinstance(result.get(k), list) for k in ('pages', 'attempts')):
            raise ValueError('READ response must contain pages and attempts lists')
        return result['pages'], result['attempts']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    take = commands.add_parser('claim')
    take.add_argument('request_path')
    take.add_argument('--owner', required=True)
    send = commands.add_parser('submit')
    send.add_argument('request_path')
    send.add_argument('--content-file')
    send.add_argument('--status', choices=['COMPLETED', 'FAILED', 'TIMED_OUT'], default='COMPLETED')
    send.add_argument('--error')
    send.add_argument('--metadata-file')
    send.add_argument('--usage-file')
    args = parser.parse_args()
    if args.command == 'claim':
        result = claim(args.request_path, args.owner)
    else:
        result = submit(args.request_path,
                        Path(args.content_file).read_text(encoding='utf-8-sig') if args.content_file else None,
                        status=args.status, error=args.error,
                        metadata=_read(args.metadata_file) if args.metadata_file else None,
                        usage=_read(args.usage_file) if args.usage_file else None)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
