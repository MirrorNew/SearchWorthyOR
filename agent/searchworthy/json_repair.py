"""Bounded JSON punctuation repair; semantic tokens are never regenerated."""
from dataclasses import dataclass, replace
from heapq import heappop, heappush
from itertools import count
import json
import re

from jsonschema import Draft202012Validator

PUNCTUATION = '{}[]:,'
IDENTIFIER_FIELDS = {'id', 'action_id', 'subject', 'fact_refs', 'model_targets',
                     'quantity', 'required', 'trigger', 'replaces_rule', 'attribute_id'}


class StageJSONError(ValueError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


def schema_validate(value, schema):
    """Structural errors only; source references and mathematics remain State's job."""
    return [{'path': list(e.absolute_path), 'message': e.message}
            for e in Draft202012Validator(schema).iter_errors(value)]


def normalize_known_keys(value, schema, path=()):
    """Normalize named fields and enum-backed ID edges; never prose/math content."""
    if not isinstance(schema, dict):
        return value, []
    field = next((part for part in reversed(path) if isinstance(part, str)), None)
    if isinstance(value, str) and field in IDENTIFIER_FIELDS:
        allowed = schema.get('enum', [])
        canonical = value.strip()
        if value not in allowed and canonical in allowed:
            return canonical, [{'path': list(path), 'before': value, 'after': canonical,
                                'kind': 'known_identifier_outer_whitespace'}]
    if isinstance(value, (dict, list)):
        schema = _container_schema(schema, 'object' if isinstance(value, dict) else 'array')
    if isinstance(value, list):
        result, edits, identities = [], [], {}
        for index, item in enumerate(value):
            child, changes = normalize_known_keys(item, schema.get('items', {}), path + (index,))
            identity = child.get('id') if isinstance(child, dict) else child if field in IDENTIFIER_FIELDS else None
            original = item.get('id') if isinstance(item, dict) else item
            if isinstance(identity, str):
                if identity in identities and identities[identity] != original:
                    raise ValueError('identifier normalization collision at ' + repr(path + (identity,)))
                identities[identity] = original
            result.append(child)
            edits.extend(changes)
        return result, edits
    if not isinstance(value, dict) or not isinstance(schema, dict):
        return value, []
    result, edits, known = {}, [], schema.get('properties', {})
    for original, item in value.items():
        key = original.strip() if original.strip() in known else original
        if key in result:
            raise ValueError('field-name normalization collision at ' + repr(path + (key,)))
        child_schema = known.get(key, schema.get('additionalProperties', {}))
        result[key], changes = normalize_known_keys(item, child_schema, path + (key,))
        edits.extend(changes)
        if key != original:
            edits.append({'path': list(path), 'before': original, 'after': key, 'kind': 'known_field_outer_whitespace'})
    return result, edits


def _unwrap(raw):
    if not isinstance(raw, str):
        raise TypeError('JSON response must be text')
    text = raw.strip().removeprefix('\ufeff').strip()
    if text.startswith('```'):
        match = re.fullmatch(r'```(?:json)?[ \t]*(?:\r\n|\r|\n)(.*)(?:\r\n|\r|\n)[ \t]*```',
                             text, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            raise ValueError('JSON response requires a complete standalone json fence')
        text = match.group(1).strip().removeprefix('\ufeff').strip()
    return text


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field: ' + key)
        result[key] = value
    return result


def _loads(text):
    return json.loads(text, object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON number: ' + value)))


def _tokens(text):
    """Quoted strings are indivisible, including escaped quotes/backslashes."""
    result, i = [], 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        start = i
        if text[i] == '"':
            i += 1
            escaped = False
            while i < len(text):
                char = text[i]
                i += 1
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    break
            else:
                raise ValueError('unterminated string; punctuation repair cannot alter strings')
        elif text[i] in PUNCTUATION:
            i += 1
        else:
            while i < len(text) and not text[i].isspace() and text[i] not in PUNCTUATION + '"':
                i += 1
        token = text[start:i]
        if token not in PUNCTUATION:
            _loads(token)  # invalid escapes/numbers cannot be repaired as punctuation
        result.append((token, start, i))
    return result


def _semantic_tokens(text):
    return tuple(t[0] for t in _tokens(text) if t[0] not in PUNCTUATION)


@dataclass(frozen=True)
class _Frame:
    kind: str
    schema: dict
    state: str
    data: tuple = ()
    key: str = ''


def _child(frame):
    if frame.kind == 'array':
        return frame.schema.get('items', {})
    known = frame.schema.get('properties', {})
    return known.get(frame.key.strip(), frame.schema.get('additionalProperties', {}))


def _compatible(schema, kind):
    if schema is False:
        return False
    if schema is True:
        return True
    types = schema.get('type')
    return not types or kind in ([types] if isinstance(types, str) else types)


def _container_schema(schema, kind):
    if not isinstance(schema, dict):
        return {}
    alternatives = schema.get('anyOf', schema.get('oneOf', []))
    candidates = [item for item in alternatives if _compatible(item, kind)]
    return candidates[0] if len(candidates) == 1 else schema


def _attach(stack, value):
    frame = stack[-1]
    if frame.kind == 'root':
        return (replace(frame, state='done', data=(value,)),)
    item = (frame.key, value) if frame.kind == 'object' else value
    return stack[:-1] + (replace(frame, state='comma', data=frame.data + (item,)),)


def _feed(stack, token):
    """A strict JSON grammar transition, with early schema pruning."""
    frame = stack[-1]
    if frame.state == 'done':
        return None
    closing = '}' if frame.kind == 'object' else ']'
    if frame.kind != 'root' and token == closing and frame.state in ('first', 'comma'):
        value = dict(frame.data) if frame.kind == 'object' else list(frame.data)
        try:
            normalized, _ = normalize_known_keys(value, frame.schema, tuple(f.key for f in stack if f.key))
        except ValueError:
            return None
        if schema_validate(normalized, frame.schema):
            return None
        return _attach(stack[:-1], value)
    if frame.state == 'comma':
        return stack[:-1] + (replace(frame, state='next'),) if token == ',' else None
    if frame.kind == 'object' and frame.state in ('first', 'next'):
        if not token.startswith('"'):
            return None
        key = _loads(token)
        if any(k == key for k, _ in frame.data):
            return None
        if frame.schema.get('additionalProperties') is False and key.strip() not in frame.schema.get('properties', {}):
            return None
        return stack[:-1] + (replace(frame, state='colon', key=key),)
    if frame.state == 'colon':
        return stack[:-1] + (replace(frame, state='value'),) if token == ':' else None
    schema = frame.schema if frame.kind == 'root' else _child(frame)
    if token in ('{', '['):
        kind = 'object' if token == '{' else 'array'
        if not _compatible(schema, kind):
            return None
        return stack + (_Frame(kind, _container_schema(schema, kind), 'first'),)
    if token in PUNCTUATION:
        return None
    value = _loads(token)
    normalized, _ = normalize_known_keys(value, schema, tuple(f.key for f in stack if f.key))
    if schema_validate(normalized, schema):
        return None
    return _attach(stack, value)


def _repair(text, schema, max_edits, max_states):
    """Uniform-cost grammar search; exhausting the bound NEVER certifies uniqueness."""
    tokens = _tokens(text)
    balance = [(0, 0)] * (len(tokens) + 1)
    for i in range(len(tokens) - 1, -1, -1):
        token = tokens[i][0]
        a, b = balance[i + 1]
        balance[i] = (a + (token == '{') - (token == '}'), b + (token == '[') - (token == ']'))
    def lower_bound(index, stack):
        a, b = balance[index]
        a += sum(f.kind == 'object' for f in stack)
        b += sum(f.kind == 'array' for f in stack)
        # One replacement can change a bracket balance by two ("{" -> "}").
        return (abs(a) + abs(b) + 1) // 2
    serial, queue, seen = count(), [], {}
    def push(cost, index, stack, edits):
        estimate = cost + lower_bound(index, stack)
        if estimate <= max_edits:
            heappush(queue, (estimate, cost, next(serial), index, stack, edits))
    push(0, 0, (_Frame('root', schema, 'value'),), ())
    solutions, best, expanded = {}, None, 0
    while queue:
        estimate, cost, _, index, stack, edits = heappop(queue)
        if best is not None and estimate > best:
            break
        signature = (index, tuple((f.kind, f.state, f.key, repr(f.data), id(f.schema)) for f in stack))
        if signature in seen and seen[signature] <= cost:
            continue
        seen[signature] = cost
        expanded += 1
        if expanded > max_states:
            return [], {'search_complete': False, 'states': expanded, 'reason': 'structural candidate limit'}
        if index == len(tokens) and stack[-1].state == 'done':
            value = stack[0].data[0]
            normalized, _ = normalize_known_keys(value, schema)
            if isinstance(value, dict) and not schema_validate(normalized, schema):
                key = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
                solutions[key] = (value, edits)
                best = cost
                if len(solutions) > 1:
                    return list(solutions.values()), {'search_complete': True, 'states': expanded, 'minimum_edits': cost}
            continue
        if index < len(tokens):
            actual, start, end = tokens[index]
            following = _feed(stack, actual)
            if following is not None:
                push(cost, index + 1, following, edits)
        else:
            actual, start, end = '', len(text), len(text)
        if cost >= max_edits or (best is not None and cost >= best):
            continue
        if actual in PUNCTUATION and actual:
            push(cost + 1, index + 1, stack, edits + ((start, end, ''),))
        for symbol in PUNCTUATION:
            following = _feed(stack, symbol)
            if following is None:
                continue
            push(cost + 1, index, following, edits + ((start, start, symbol),))
            if actual in PUNCTUATION and actual and symbol != actual:
                push(cost + 1, index + 1, following, edits + ((start, end, symbol),))
    return list(solutions.values()), {'search_complete': True, 'states': expanded, 'minimum_edits': best}


def _apply(text, edits):
    cursor, parts = 0, []
    for start, end, inserted in edits:
        parts.extend((text[cursor:start], inserted))
        cursor = end
    parts.append(text[cursor:])
    return ''.join(parts)


def _fragment(text, position, schema):
    try:
        tokens = _tokens(text)
    except ValueError:
        tokens = []
    stack, structures, grammar = [], [], (_Frame('root', schema, 'value'),)
    for token, start, end in tokens:
        if start >= position:
            break
        following = _feed(grammar, token)
        if following is not None:
            grammar = following
        if token in ('{', '['):
            stack.append({'symbol': token, 'position': start})
        elif token in ('}', ']') and stack and stack[-1]['symbol'] == {'}': '{', ']': '['}[token]:
            stack.pop()
        if token in PUNCTUATION:
            structures.append((token, start))
    start, end = max(0, position - 180), min(len(text), position + 180)
    for _, left, right in tokens:
        if left < start < right:
            start = left
        if left < end < right:
            end = right
    return {'start': start, 'end': end, 'text': text[start:end], 'error_offset': position - start,
            'bracket_stack': stack, 'adjacent_structure': structures[-8:], 'schema': grammar[-1].schema,
            'parent_schema': grammar[-2].schema if len(grammar) > 1 else None,
            'allowed_changes': 'Only punctuation outside quoted strings; preserve every semantic token.'}


def _value_span(text, path):
    """Locate a value in already parsed JSON without rewriting its string/number tokens."""
    decoder = json.JSONDecoder()
    def space(index):
        while index < len(text) and text[index].isspace():
            index += 1
        return index
    start = space(0)
    for part in path:
        opening = '{' if isinstance(part, str) else '['
        if text[start] != opening:
            return None
        index, item = space(start + 1), 0
        found = False
        while text[index] != ('}' if opening == '{' else ']'):
            if opening == '{':
                key, index = decoder.raw_decode(text, index)
                index = space(space(index) + 1)  # Skip the already validated colon.
                matches = key == part or key.strip() == part
            else:
                matches = item == part
            _, end = decoder.raw_decode(text, index)
            if matches:
                start, found = index, True
                break
            index = space(end)
            if text[index] == ',':
                index = space(index + 1)
            item += 1
        if not found:
            return None
    return start, decoder.raw_decode(text, start)[1]


def _singleton_predicate(value, schema, text, errors, remaining_edits):
    """Only a complete predicate in one required/exceptions array may gain brackets."""
    if remaining_edits < 2 or len(errors) != 1:
        return None
    path = errors[0]['path']
    if not (len(path) == 5 and path[0] == 'rules' and type(path[1]) is int
            and path[2] == 'conditions' and type(path[3]) is int
            and path[4] in {'required', 'exceptions'}):
        return None
    item, spec = value, schema
    for part in path:
        item = item[part]
        spec = spec.get('items', {}) if isinstance(part, int) else spec.get('properties', {}).get(part, {})
    if (spec.get('type') != 'array' or not isinstance(item, dict)
            or set(item) != {'value', 'citations'} or not isinstance(item['value'], str)
            or item['value'] not in {'YES', 'NO', 'UNKNOWN'}
            or not isinstance(item['citations'], list) or schema_validate(item, spec.get('items', {}))):
        return None
    span = _value_span(text, path)
    if span is None:
        return None
    start, end = span
    edits = [(start, start, '['), (end, end, ']')]
    repaired = _apply(text, edits)
    candidate, _ = normalize_known_keys(_loads(repaired), schema)
    if _semantic_tokens(text) != _semantic_tokens(repaired) or schema_validate(candidate, schema):
        return None
    return candidate, repaired, edits, {'path': path, 'before': item, 'after': [item],
                                        'kind': 'singleton_predicate_array'}


def parse_stage(raw, schema, *, max_edits=6, max_states=50000):
    """Return one complete object + audit, or StageJSONError carrying a local repair request.

    Schema success is explicitly separate from business validation and answer correctness.
    """
    record = {'raw': raw, 'status': 'REJECTED', 'syntax_valid': False, 'schema_valid': False,
              'business_valid': None, 'answer_correct': None, 'edits': [], 'coordinate_system': 'unwrapped_text'}
    try:
        text = _unwrap(raw)
        record['unwrapped'] = text
        value = _loads(text)
    except json.JSONDecodeError as error:
        record['parser_error'] = {'message': error.msg, 'position': error.pos,
                                  'line': error.lineno, 'column': error.colno}
        record['local_fragment'] = _fragment(text, error.pos, schema)
        try:
            candidates, search = _repair(text, schema, max_edits, max_states)
        except (ValueError, RecursionError) as failure:
            record['repair_error'] = str(failure)
            raise StageJSONError('JSON needs a bounded local correction', record) from error
        record.update(search)
        record['candidate_objects'] = len(candidates)
        if len(candidates) != 1 or not search['search_complete']:
            raise StageJSONError('JSON repair is ambiguous or unproven within its bound', record) from error
        value, edits = candidates[0]
        repaired = _apply(text, edits)
        if _semantic_tokens(text) != _semantic_tokens(repaired) or _loads(repaired) != value:
            raise StageJSONError('JSON repair did not preserve semantic tokens', record)
        record.update(status='STRUCTURE_REPAIRED', repaired=repaired,
                      edits=[{'start': a, 'end': b, 'before': text[a:b], 'after': c} for a, b, c in edits])
    except (ValueError, TypeError) as error:
        record['parser_error'] = {'message': str(error)}
        raise StageJSONError(str(error), record) from error
    try:
        value, field_edits = normalize_known_keys(value, schema)
    except ValueError as error:
        record.update(syntax_valid=True, schema_errors=[{'path': [], 'message': str(error)}])
        raise StageJSONError(str(error), record) from error
    record['field_edits'] = field_edits
    errors = schema_validate(value, schema)
    candidate = _singleton_predicate(value, schema, record.get('repaired', text), errors,
                                     max_edits - len(record['edits']))
    if candidate is not None:
        value, repaired, edits, change = candidate
        record.update(status='STRUCTURE_REPAIRED', repaired=repaired)
        record['edits'].extend({'start': a, 'end': b, 'before': '', 'after': c} for a, b, c in edits)
        record['field_edits'].append(change)
        errors = schema_validate(value, schema)
    if not isinstance(value, dict):
        errors.append({'path': [], 'message': 'stage response must be one complete object'})
    record.update(syntax_valid=True, schema_errors=errors, schema_valid=not errors)
    if errors:
        raise StageJSONError('JSON parses but fails the output field definition', record)
    if record['status'] == 'REJECTED':
        record.update(status='PARSED', repaired=text)
    return value, record


def apply_local_patch(raw, start, end, replacement, schema):
    """Apply ONLY the requested fragment; never accept regenerated models or edited facts."""
    text = _unwrap(raw)
    if not isinstance(replacement, str) or not 0 <= start <= end <= len(text):
        raise ValueError('invalid local repair range')
    patched = text[:start] + replacement + text[end:]
    if _semantic_tokens(text) != _semantic_tokens(patched):
        raise ValueError('local correction changed strings, names, numbers or mathematical tokens')
    value, record = parse_stage(patched, schema, max_edits=0)
    record.update(raw=raw, status='LOCAL_FRAGMENT_REPAIRED', repaired=patched,
                  edits=[{'start': start, 'end': end, 'before': text[start:end], 'after': replacement}])
    return value, record
