"""Single-case information table and deterministic compilation; no network or LLM."""
from copy import deepcopy
import json
import math
import re

from searchworthy.compiler import compile_model
from searchworthy.evidence import _text_span
from searchworthy.contracts import ModelContribution

LOCATORS = ('jurisdiction', 'as_of', 'subject_type', 'actor_role', 'action_meaning')
TRUTHS = {'YES', 'NO', 'UNKNOWN'}


class PlanCoverageError(ValueError):
    def __init__(self, missing):
        self.missing = missing
        super().__init__('EXTERNAL clauses lack a relation or cited constraint: '
                         + ', '.join(row['clause_id'] for row in missing))


def missing_plan_relations(proposal, clauses):
    """Check declared or explicit source dependencies for a destination, never infer a duty."""
    texts = {c['id']: c['text'] for c in clauses}
    process = re.compile(
        r'监管(?:制度|流程|程序)|(?:行政|政府|监管)许可(?:流程|程序|制度)?|资费(?:流程|程序|制度)|'
        r'\bregulatory\s+(?:process|framework|regime)\b|\bstatutory\s+(?:process|scheme)\b|'
        r'\bgovernment\s+(?:permit|licen[cs]e)\b|\bpermitting\s+(?:process|regime)\b|'
        r'\btariff\s+(?:process|procedure|regime)\b', re.I)
    law = re.compile(r'法规|法律|监管(?:规定|要求)|\bregulations?\b', re.I)
    binding = re.compile(
        r'适用|受[^。；\n]{0,20}(?:约束|管辖)|纳入|豁免|排除适用|'
        r'\bsubject\s+to\b|\bbound\s+by\b|\bgoverned\s+by\b|\bexempt(?:ed)?\b|'
        r'\b(?:within|outside)\s+[^.;\n]{0,20}scope\b|\b(?:do|does)\s+not\s+apply\b|'
        r'\bappl(?:ies|icable)\s+to\b|\bregulations\s+apply\s+to\b', re.I)
    participant = re.compile(r'参与方|参与者|参与身份|\bparticipants?\b', re.I)
    # Plain dates, places, internal agreements or tariff prices are not dependencies.
    # Retain negatives: a cited exclusion is a destination, not a reason to skip coverage.
    explicit = {c['id'] for c in clauses if not c.get('topic_label') and (
        process.search(c['text']) and (binding.search(c['text']) or participant.search(c['text']))
        or law.search(c['text']) and binding.search(c['text']))}
    def linked(identifier, refs):
        return any(str(ref.get('submitted_document', ref.get('document'))).strip().removeprefix('task:').strip() == identifier
                   or ref.get('document') == 'task' and ref.get('quote', '').strip() == texts[identifier].strip()
                   and sum(text.strip() == ref.get('quote', '').strip() for text in texts.values()) == 1
                   for ref in refs)
    missing = []
    for mapped in proposal.get('task_map', []):
        identifier = mapped.get('clause_id')
        if identifier not in texts or mapped.get('role') != 'EXTERNAL' and identifier not in explicit:
            continue
        if re.fullmatch(r'【[^】]+】', texts[identifier].strip()):
            continue  # Standalone headings are normalized to CONTEXT by accept_plan.
        needs = proposal.get('needs', [])
        registered = any(identifier in [v.strip() for v in n.get('anchor_clauses', []) if isinstance(v, str)] or any(
            linked(identifier, n.get(field, {}).get('citations', []))
            for field in ('task_supplied', 'excluded')) for n in needs)
        encoded = any(linked(identifier, c.get('citations', []))
                      for c in proposal['model'].get('constraints', []))
        if not registered and not encoded:
            missing.append({'clause_id': identifier, 'text': texts[identifier]})
    return missing


def source_attributes(public):
    """Enumerate source numbers and explicit installation capabilities, never duties."""
    result = []
    capabilities = []
    numeric = re.compile(r'(?<![A-Za-z0-9_.])[-+−]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?(?![0-9_.])')
    installation = re.compile(r'^\s*(?:配置|安装|部署|配备|提供|(?:configure|install|deploy|equip|provide)\b)\s*\S', re.I)
    for action in public['output_schema']['actions']:
        text = action.get('meaning', '')
        if not isinstance(text, str):
            continue
        matches = list(numeric.finditer(text))
        for match in matches:
            raw = match.group()
            canonical = raw.replace(',', '').replace('−', '-')
            value = float(canonical) if re.search(r'[.eE]', canonical) else int(canonical)
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError('source attribute quantity exceeds finite numeric representation')
            result.append({'id': f'AQ{len(result)+1:03}', 'action_id': action['id'],
                           'raw': raw, 'start': match.start(), 'end': match.end(),
                            'text': text, 'value': value, 'document': 'schema'})
        if not matches and installation.search(text):
            capabilities.append({'action_id': action['id'], 'kind': 'CAPABILITY',
                                 'raw': text, 'start': 0, 'end': len(text),
                                 'text': text, 'value': text, 'document': 'schema'})
    # Preserve all existing numeric IDs when a mixed action list gains capability checks.
    for capability in capabilities:
        result.append({'id': f'AQ{len(result)+1:03}', **capability})
    return result


def prepare_attributes(prepared, public, clauses=None):
    """Bind a fixed source denominator to facts/needs; never infer a regulatory rule.

    Idempotent for prepare_plan and State.accept_plan: generated items are rebuilt
    from the unchanged checks, so direct callers cannot bypass this guard.
    """
    attributes = source_attributes(public)
    checks = prepared.get('attribute_checks', [])
    _unique(checks, 'attribute_id', [a['id'] for a in attributes])
    prepared['attribute_checks'] = checks
    prepared['facts'] = [f for f in prepared.get('facts', []) if not f.get('_attribute_generated')]
    prepared['needs'] = [n for n in prepared.get('needs', []) if not n.get('_attribute_generated')]
    for need in prepared['needs']:
        need.pop('source_attribute_ids', None)
    known = {a['id']: a for a in attributes}
    base_needs = list(prepared['needs'])
    constraints = prepared['model']['constraints']
    confirmations = {}
    text_by_id = {c['id']: c['text'] for c in clauses or []}
    text_by_id['schema'] = json.dumps(public['output_schema'], ensure_ascii=False)
    action_sources = {a['id']: json.dumps(a, ensure_ascii=False) for a in public['output_schema']['actions']}
    unknown = {'value': 'UNKNOWN', 'citations': []}
    def register_fact(attribute, key, purpose, locations=None):
        # Exact substring of the actual schema serialization, including JSON escapes.
        # The action ID gives a unique source even when two meanings are identical.
        fragment = action_sources[attribute['action_id']]
        ref = {'document': 'schema'}
        if text_by_id['schema'].count(fragment) == 1:
            start = text_by_id['schema'].index(fragment)
            ref['quote'] = text_by_id['schema'][start:start + len(fragment)]
        prepared['facts'].append({'subject': attribute['action_id'], 'key': key,
            'value': attribute['value'], 'citations': [ref],
            '_attribute_generated': True, 'source_attribute': deepcopy(attribute),
            'attribute_purpose': purpose, 'model_locations': list(locations or [])})
    for check in checks:
        attribute = known[check['attribute_id']]
        action = attribute['action_id']
        key, purpose = check.get('key'), check.get('purpose')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', key):
            raise ValueError('attribute key must be a short English field name')
        bindings = [name for name in ('needs_index', 'constraint_indices', 'need') if name in check]
        capability = attribute.get('kind') == 'CAPABILITY'
        if capability and purpose != 'ATTRIBUTE':
            raise ValueError('CAPABILITY requires ATTRIBUTE relationship binding, not an objective or label')
        left = attribute['text'][:attribute['start']]
        if purpose == 'OBJECTIVE':
            label = r'(?:cost|utility|profit|benefit|price|revenue|payoff|成本|费用|价格|净效用|效用|收益|效益)'
            if bindings or not re.search(label + r'\s*(?:is|of|为|是|[:：=])?\s*[$￥€£]?\s*$', left, re.I):
                raise ValueError('OBJECTIVE attribute needs its own explicit cost/utility label')
            if prepared['model']['objective']['terms'].get(action) != attribute['value']:
                raise ValueError('OBJECTIVE attribute differs from its action coefficient')
            register_fact(attribute, key, purpose, ['objective:' + action])
            continue
        if purpose == 'CHOICE_LABEL':
            right = attribute['text'][attribute['end']:]
            boundary = r'\s*(?:$|[,;:!?()\[\]{}，。；：！？（）【】]|\.(?=$|\s)|[号號](?=$|\s|[,;:!?()\[\]{}，。；：！？（）【】]))'
            choice_word = r'(?:\bplan|\boption|\bbatch|\bpath|\broute|\bquarter|方案|批次|路径|路线|季度)'
            # A source number can label an explicitly named entity only when a
            # structural connector or a real right boundary follows it. This
            # positive boundary keeps quantities such as 用户3吨/用户3岁/
            # 订单3kWh out of the label branch without an unbounded unit list.
            label_connector = r'(?:安排在|采用|公开|更新|的|为|是|属于|对应|编号为|型号为)'
            label_tail = r'\s*(?:$|[,;:!?()\[\]{}，。；：！？（）【】]|' + label_connector + r')'
            entity_label = bool(re.search(r'(?:用户|客户|订单)\s*$', left)) \
                and bool(re.match(label_tail, right, re.I))
            # Do not treat 第1期 as a generic label: it is also the common
            # prefix of deadlines/period quantities. For 季/季度, require the
            # same positive boundary after the period word.
            period = re.match(r'\s*(?:季度|季)(?!期)', right)
            chinese_period = bool(re.search(r'第\s*$', left) and period
                                  and re.match(label_tail, right[period.end():], re.I))
            ordinary_label = bool(re.search(choice_word + r'\s*(?:number|no\.?|#|第)?\s*$', left, re.I)
                                  and re.match(boundary, right))
            if bindings or not (entity_label or chinese_period or ordinary_label):
                raise ValueError('CHOICE_LABEL requires an explicit plan or batch number')
            register_fact(attribute, key, purpose)
            continue
        if purpose != 'ATTRIBUTE' or len(bindings) != 1:
            raise ValueError('ATTRIBUTE requires exactly one need or constraint binding')
        if bindings[0] == 'needs_index':
            index = check['needs_index']
            if type(index) is not int or not 0 <= index < len(base_needs):
                raise ValueError('attribute needs_index does not name an existing need')
            need = base_needs[index]
            targets = need.get('objects', {}).get('actions', need.get('action_ids', []))
            if action not in targets and 'GLOBAL' not in need.get('action_ids', []):
                raise ValueError('attribute need does not cover its own action')
            if 'GLOBAL' in need.get('action_ids', []) and targets and 'GLOBAL' not in targets and action not in targets:
                raise ValueError('attribute GLOBAL need objects exclude its own action')
        elif bindings[0] == 'need':
            need = deepcopy(check['need'])
            if not isinstance(need, dict) or not need.get('question'):
                raise ValueError('attribute need must name a concrete relationship')
            if set(need) - {'question', 'task_supplied', 'excluded', 'query', 'search_terms', 'alternative_queries', 'anchor_clauses'}:
                raise ValueError('attribute need has unknown fields; its action is program-owned')
            need.update(action_ids=[action], _attribute_generated=True)
            need.setdefault('anchor_clauses', ['schema'])
            prepared['needs'].append(need)
        else:
            indices = check['constraint_indices']
            if not isinstance(indices, list) or not indices or any(type(i) is not int or not 0 <= i < len(constraints) for i in indices) or len(indices) != len(set(indices)):
                raise ValueError('attribute constraint_indices must name existing constraints')
            refs = check.get('citations', [])
            if not refs or any(not isinstance(r, dict) or not r.get('document') for r in refs):
                raise ValueError('attribute constraint binding requires supporting references')
            cited = {r['document'] for r in refs}
            for index in indices:
                constraint = constraints[index]
                terms = {a: v for a, v in constraint['terms'].items() if v != 0}
                variables = {v['id']: v for v in prepared['model']['variables']}
                if action not in variables or set(constraint['terms']) - (variables.keys() & action_sources.keys()):
                    raise ValueError('attribute constraint must use declared public actions')
                # An omitted term is algebraic zero, not proof about this attribute.
                # Keep the explicit binding pending; preserve the source and model.
                variable = variables[action]
                if capability and action not in terms:
                    raise ValueError('capability constraint must actually involve its own action')
                simple_choice = (all(v == 1 for v in terms.values()) and constraint['rhs'] == 1)
                binary_bound = len(terms) == 1 and variable['type'] == 'BINARY' and constraint['rhs'] in {0, 1}
                if capability and len(terms) == 1 and variable['type'] == 'BINARY':
                    coefficient, rhs = terms[action], constraint['rhs']
                    allowed = [v for v in (0, 1) if {'>=': coefficient*v >= rhs,
                               '<=': coefficient*v <= rhs, '==': coefficient*v == rhs}[constraint['sense']]]
                    if len(allowed) != 1:
                        raise ValueError('variable bounds do not establish a capability requirement')
                elif simple_choice or (binary_bound and not capability):
                    raise ValueError('choice constraints and variable bounds do not consume configuration attributes: '
                                     + str(check['attribute_id']))
                actual_refs = {r.get('submitted_document', r['document']) for r in constraint['citations']}
                if not cited.intersection(actual_refs):
                    raise ValueError('attribute references must come from its actual model constraint')
                # The candidate schema supplies the coefficient; the rule citation
                # can supply only its threshold. They need not repeat each other.
            # Source coverage cannot itself certify mathematical fidelity. Existing FUSE
            # interprets the supplied rule, without registering a new search obligation.
            locations = sorted('constraint:' + constraints[i]['name'] for i in indices)
            group = (tuple(locations), tuple(sorted(cited)))
            need = confirmations.get(group)
            if need is None:
                targets = sorted({a for i in indices for a, value in constraints[i]['terms'].items() if value != 0})
                need = {'question': 'Confirm the source attributes in ' + ', '.join(locations)
                                    + ' against clauses ' + ', '.join(sorted(cited)) + '.',
                        'action_ids': targets, 'anchor_clauses': sorted(cited),
                        'objects': {'actions': targets, 'variables': [],
                                    'constraints': sorted(constraints[i]['name'] for i in indices),
                                    'objective_coefficients': []},
                        'route': 'GIVEN',
                        'task_supplied': {'value': 'YES', 'citations': deepcopy(refs)},
                        'excluded': deepcopy(unknown), 'model_locations': list(locations),
                        'confirmation_locations': list(locations),
                        'expression_check': deepcopy(unknown), '_attribute_generated': True}
                confirmations[group] = need
                prepared['needs'].append(need)
        need.setdefault('route', 'PUBLIC')
        declared_actions = need['action_ids']
        need.setdefault('objects', {'actions': [a['id'] for a in public['output_schema']['actions']]
                                   if 'GLOBAL' in declared_actions else list(declared_actions)})
        need.setdefault('source_attribute_ids', []).append(attribute['id'])
        register_fact(attribute, key, purpose, need.get('model_locations'))
    prepared['_attribute_coverage'] = [len(checks), len(attributes)]
    return prepared


def _truth(value):
    if isinstance(value, bool):
        return 'YES' if value else 'NO'
    return value.strip().upper() if isinstance(value, str) else value


def all_of(values):
    return 'NO' if 'NO' in values else 'UNKNOWN' if 'UNKNOWN' in values else 'YES'


def any_of(values):
    return 'YES' if 'YES' in values else 'UNKNOWN' if 'UNKNOWN' in values else 'NO'


def negate(value):
    return {'YES': 'NO', 'NO': 'YES', 'UNKNOWN': 'UNKNOWN'}[value]


def _semantic(value):
    if isinstance(value, list):
        return sorted((_semantic(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    if isinstance(value, dict):
        return {k: _semantic(v) for k, v in value.items() if k not in {
            'reason', 'explanation', 'notes', 'citations', 'refs', 'quote', 'submitted_quote',
            'submitted_document', 'match_method', 'source_span', 'work'}}
    return value


def _signature(rows, model):
    result = []
    for row in rows:
        item = _semantic(row)
        if row['kind'] == 'FACT':
            item['value'] = deepcopy(row['value'])  # A fact may encode an ordered list.
        result.append(item)
    return {'rows': sorted(result, key=lambda r: r['id']), 'model': _semantic(model)}


def _rule_signature(rule):
    return _semantic({key: value for key, value in rule.items() if key not in {
        'id', 'replaces_rule', 'model_targets', 'trigger_targets', 'field_edits'}})


def _slot_targets(row):
    # GLOBAL is a shared premise/scope marker, never an additional decision object.
    return set(row['action_ids']) - {'GLOBAL'} or set(row['objects']['actions'])


def _pending(row):
    # Missing optional facts lower readiness. Required gaps have SLOT/CONDITION rows.
    return row['status'] in {'OPEN', 'CONFLICT', 'STALE', 'UNSUPPORTED', 'TO_ACQUIRE', 'TO_INTERPRET', 'UNRESOLVED'} and not (row['kind'] == 'FACT' and row['status'] == 'OPEN' and not row.get('required'))


def _unique(rows, key, expected=None):
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError('expected a list of objects: ' + key)
    values = [r[key] for r in rows]
    if any(not isinstance(v, str) or not v for v in values) or len(values) != len(set(values)):
        raise ValueError('duplicate or invalid ' + key)
    if expected is not None and set(values) != set(expected):
        raise ValueError('must cover every registered ' + key)


def _assign_ids(items, rows, kind, prefix):
    """Allocate new identifiers once, after a response has been parsed."""
    used = {r['id'].split(':', 1)[1] for r in rows if r['kind'] == kind}
    if kind == 'SLOT':
        used.update(alias for r in rows if r['kind'] == kind for alias in r.get('aliases', []))
    used.update(item['id'] for item in items if item.get('id'))
    for item in items:
        if 'id' in item:
            continue
        existing = [r for r in rows if kind == 'FACT' and r['kind'] == 'FACT'
                    and r['subject'] == item.get('subject') and r['key'] == item.get('key')]
        if len(existing) == 1 and (existing[0]['value'] is None or existing[0]['value'] == item.get('value')):
            item['id'] = existing[0]['id'].split(':',1)[1]
            item['_program_existing'] = True
            continue
        index = 1
        while f'{prefix}{index:03}' in used:
            index += 1
        item['id'] = f'{prefix}{index:03}'
        used.add(item['id'])


def _contribution(name, kind, payload, refs):
    return ModelContribution(name, name, 'LOCAL', 'task', kind, payload, refs)


def _base(model):
    objective = model['objective']
    rows = [_contribution('base_direction', 'direction', {'direction': objective['direction']}, objective['citations']),
            _contribution('base_objective', 'objective',
                {'terms': [{'var': k, 'coef': v} for k, v in objective['terms'].items()],
                 'constant': objective.get('constant', 0)}, objective['citations'])]
    for row in model['constraints']:
        rows.append(_contribution('base_' + row['name'], 'constraint',
            {'terms': [{'var': k, 'coef': v} for k, v in row['terms'].items()],
             'sense': row['sense'], 'rhs': row['rhs']}, row['citations']))
    return rows


class State:
    def __init__(self, public, text, clauses, store):
        self.public, self.text, self.clauses, self.store = public, text, clauses, store
        self.store.add('public:schema', json.dumps(public['output_schema'],ensure_ascii=False), 'Public action schema', 'LOCAL', alias='schema')
        self.actions = {a['id']: a for a in public['output_schema']['actions']}
        self.rows, self.model, self.mapping = [], None, []
        self.revision, self.derived, self.operations = 0, {}, []

    def _refs(self, refs, local=False, external=False):
        if not isinstance(refs, list) or not refs or any(not isinstance(r, dict) for r in refs):
            raise ValueError('nonempty document/quote citations required')
        clauses = {c['id']: c['text'] for c in self.clauses}
        for ref in refs:
            key = ref.get('document')
            if isinstance(key, str):
                ref['document'] = key = key.strip()
            if key == 'task' and not ref.get('quote'):
                ref['quote'] = self.text
            if key == 'task' and ref.get('quote') and _text_span(self.text,ref['quote']) is None and _text_span(self.store.documents['schema'].text,ref['quote']) is not None:
                ref.update(document='schema',submitted_document='task')
                key = 'schema'
            if key == 'schema' and not ref.get('quote'):
                ref['quote'] = self.store.documents['schema'].text
            if key in self.store.fragments:
                fragment = self.store.fragments[key]
                if not ref.get('quote') or _text_span(fragment['quote'], ref['quote']) is not None:
                    ref.update(document=fragment['document'], quote=ref.get('quote') or fragment['quote'], submitted_document=key)
                    key = ref['document']
            if isinstance(key, str) and key not in self.store.documents:
                clause = key.removeprefix('task:').strip()
                if clause in clauses and (not ref.get('quote') or _text_span(clauses[clause], ref['quote']) is not None):
                    ref.update(document='task', quote=ref.get('quote') or clauses[clause], submitted_document=key)
                elif clause in clauses:
                    raise ValueError('quote does not match the referenced clause: ' + clause)
        self.store.check(refs, local_only=local)
        if external and not any(self.store.documents[r['document']].source_kind not in {'LOCAL', 'SEARCH_SNIPPET'} for r in refs):
            raise ValueError('PUBLIC gap needs observed external body text')
        return refs

    def _condition(self, row):
        if isinstance(row, dict):
            row['value'] = _truth(row.get('value'))
        if not isinstance(row, dict) or row.get('value') not in TRUTHS:
            raise ValueError('condition value must be YES, NO or UNKNOWN')
        if row['value'] != 'UNKNOWN' or row.get('citations'):
            self._refs(row.get('citations', []))
        return row['value']

    def _scope_checks(self, rule, slots):
        """Resolve explicit shared exceptions, never another relation's status."""
        checks = rule.get('scope_checks', [])
        if not isinstance(checks, list):
            raise ValueError('scope_checks must be a list')
        lookup = {alias: row for row in slots for alias in row['aliases']}
        linked = {lookup[n]['need_id'] for n in rule['need_ids'] if n in lookup}
        related = set().union(*(_slot_targets(row) for row in slots if row['need_id'] in linked))
        seen, result = set(), []
        for check in checks:
            if not isinstance(check, dict) or set(check) != {'relation_id', 'shared_exception_scope'}:
                raise ValueError('scope check requires relation_id and shared_exception_scope')
            identity = check['relation_id']
            if not isinstance(identity, str) or identity not in lookup:
                raise ValueError('scope check requires a registered relation_id')
            parent = lookup[identity]
            identity = parent['need_id']
            if identity in linked or identity in seen:
                raise ValueError('scope check cannot reference its own or a repeated relation')
            if not related & _slot_targets(parent):
                raise ValueError('scope check must share a related action object')
            seen.add(identity)
            check['relation_id'] = identity
            shared = self._condition(check['shared_exception_scope'])
            excluded = self._condition(parent['excluded'])
            exception = excluded if shared == 'YES' else 'NO' if shared == 'NO' else 'UNKNOWN'
            result.append((check, parent['excluded'], exception))
        return result

    def _quantity_basis(self, rule):
        """A displayed component split is not an independently required bound."""
        if rule.get('kind') != 'linear':
            return 'YES'
        basis = rule.get('quantity_basis')
        required = {'kind', 'citations', 'independent_requirement', 'decomposition_only'}
        if not isinstance(basis, dict) or required - basis.keys() or set(basis) - (required | {'component_counts_toward_total'}):
            raise ValueError('linear rule requires complete quantity_basis fields')
        kind = basis['kind']
        if kind not in {'TOTAL', 'COMPONENT', 'INDEPENDENT', 'UNKNOWN'}:
            raise ValueError('unsupported quantity_basis kind')
        if not isinstance(basis['citations'], list):
            raise ValueError('quantity_basis citations must be a list')
        if kind != 'UNKNOWN' or basis['citations']:
            self._refs(basis['citations'])
        values = [self._condition(basis[name]) for name in ('independent_requirement', 'decomposition_only')]
        if kind == 'COMPONENT':
            if 'component_counts_toward_total' not in basis:
                raise ValueError('COMPONENT quantity_basis requires its total-membership predicate')
            membership = self._condition(basis['component_counts_toward_total'])
        elif 'component_counts_toward_total' in basis:
            raise ValueError('total-membership predicate belongs only to COMPONENT quantity_basis')
        else:
            membership = 'YES'  # This check is inapplicable, not an inferred source fact.
        if rule.get('modality') != 'MAY' and (values[0] == 'NO' or values[1] == 'YES'):
            raise ValueError('quantity_basis does not support an independent hard bound; a decomposition is not a requirement')
        return 'UNKNOWN' if kind == 'UNKNOWN' or 'UNKNOWN' in [*values, membership] else 'YES'

    def _install(self, rows, model, mapping, ir, metrics):
        if _signature(rows, model) != self.signature():
            self.revision += 1
        self.rows, self.model, self.mapping = deepcopy(rows), deepcopy(model), deepcopy(mapping)
        self.derived = {'revision': self.revision, 'ir': ir, 'metrics': metrics}

    def _register(self, rows, facts, needs, *, local):
        _assign_ids(facts, rows, 'FACT', 'F')
        _assign_ids(needs, rows, 'SLOT', 'R')
        _unique(facts, 'id')
        for fact in facts:
            existing = next((r for r in rows if r['id'] == 'FACT:' + fact['id']), None)
            if existing is not None and (existing['subject'] != fact['subject'] or existing['key'] != fact['key']
                    or (existing['value'] is not None and not (fact.get('_program_existing') and existing['value'] == fact.get('value')))
                    or fact.get('value') is None):
                raise ValueError('FACT id already registered; only an unknown value in the same field may be filled')
            if fact['subject'] not in {*self.actions, 'GLOBAL'} or not isinstance(fact['key'], str):
                raise ValueError('fact requires registered subject and field')
            if fact.get('value') is not None or fact.get('citations'):
                self._refs(fact.get('citations', []), local=local)
            row = existing if existing is not None else {'id': 'FACT:' + fact['id'], 'kind': 'FACT',
                                                        'subject': fact['subject'], 'key': fact['key']}
            row.update(value=fact.get('value'), refs=fact.get('citations', []),
                       status='READY' if fact.get('value') is not None else 'OPEN')
            if fact.get('source_attribute'):
                row['source_attribute'] = deepcopy(fact['source_attribute'])
                row['attribute_purpose'] = fact['attribute_purpose']
                row['model_locations'] = list(fact['model_locations'])
            if fact.get('required') is True:
                row['required'] = True
            if existing is None:
                rows.append(row)
        for row in [r for r in rows if r['kind'] == 'FACT']:
            peers = [r for r in rows if r['kind'] == 'FACT' and r['subject'] == row['subject'] and r['key'] == row['key'] and r['value'] is not None]
            if len({json.dumps(r['value'], sort_keys=True, ensure_ascii=False) for r in peers}) > 1:
                row['status'] = 'CONFLICT'
        _unique(needs, 'id')
        for need in needs:
            identity = need['id'].strip()
            if any(identity in r.get('aliases', [r.get('need_id')]) for r in rows if r['kind'] == 'SLOT'):
                raise ValueError('need id already registered')
            targets = need['action_ids']
            if not isinstance(targets, list) or not targets or set(targets) - {*self.actions, 'GLOBAL'}:
                raise ValueError('need targets must be public actions or GLOBAL')
            if need['route'] not in {'PUBLIC', 'GIVEN', 'LOCAL', 'FUTURE', 'UNSUPPORTED'}:
                raise ValueError('invalid need route')
            supplied_anchors = need['anchor_clauses']
            clause_ids = {c['id'] for c in self.clauses}
            if not isinstance(supplied_anchors, list) or any(not isinstance(a, str) for a in supplied_anchors):
                raise ValueError('need requires registered clause anchors')
            anchors, source_refs = [], deepcopy(need.get('source_citations', []))
            for anchor in supplied_anchors:
                anchor = anchor.strip()
                if anchor in clause_ids or anchor == 'schema':
                    anchors.append(anchor)
                elif anchor in self.store.fragments:
                    source_refs.append({'document': anchor})
                elif anchor in self.store.documents and self.store.documents[anchor].source_kind != 'LOCAL':
                    source_refs.append({'document': anchor, 'quote': self.store.documents[anchor].text})
                else:
                    raise ValueError('unknown need anchor or source reference: ' + anchor)
            anchors = list(dict.fromkeys(anchors))
            if not anchors:
                raise ValueError('need requires registered clause anchors')
            if source_refs:
                self._refs(source_refs, local=local)
            query = need.get('query', '').strip()
            if query and (len(query) > 320 or re.search(r'[\u3400-\u9fff]', query)):
                raise ValueError('PUBLIC need requires an English query of 1..320 characters')
            locator = {}
            for key in LOCATORS:
                value = need.get('locator', {}).get(key)
                if isinstance(value, dict) and value.get('value') is not None:
                    self._refs(value.get('citations', []), local=local)
                    locator[key] = deepcopy(value)
                else:
                    candidates = [r for r in rows if r['kind'] == 'FACT' and r['key'] == key and r['subject'] in {*targets, 'GLOBAL'} and r['status'] == 'READY']
                    values = {json.dumps(r['value'], sort_keys=True) for r in candidates}
                    locator[key] = {'value': candidates[0]['value'], 'citations': candidates[0]['refs']} if len(values) == 1 else None
            defaults = {'actions': sorted(self.actions) if targets == ['GLOBAL'] else [t for t in targets if t != 'GLOBAL'], 'variables': [],
                        'constraints': [], 'objective_coefficients': []}
            objects = defaults | deepcopy(need.get('objects', {}))
            if set(objects) - defaults.keys() or any(not isinstance(v, list) or any(not isinstance(x, str) for x in v) for v in objects.values()):
                raise ValueError('relation objects require actions/variables/constraints/objective_coefficients lists')
            for kind in ('actions', 'variables', 'objective_coefficients'):
                if set(objects[kind]) - self.actions.keys():
                    raise ValueError('relation object is not a public variable: ' + kind)
            if not any(objects.values()):
                raise ValueError('GLOBAL relation must identify an OR object')
            relation = need.get('relation', need['question']).strip()
            if not relation:
                raise ValueError('relation must name a concrete missing comparison or dependency')
            scope = deepcopy(need.get('scope', {}))
            for key, loc in {'jurisdiction':'jurisdiction','subject_type':'subject_type','activity':'action_meaning','as_of':'as_of'}.items():
                scope.setdefault(key, locator[loc]['value'] if locator.get(loc) else None)
            if set(scope) - {'jurisdiction', 'subject_type', 'activity', 'as_of'}:
                raise ValueError('unknown relation scope field')
            judgments = {}
            for key in ('task_supplied', 'evidence_supplied', 'excluded'):
                judgments[key] = deepcopy(need.get(key, {'value': 'UNKNOWN', 'citations': []}))
                self._condition(judgments[key])
                if local and judgments[key]['value'] != 'UNKNOWN':
                    self._refs(judgments[key]['citations'], local=True)
            # Legacy GIVEN identifies available text to interpret, never certifies it complete.
            if 'task_supplied' not in need and need['route'] == 'GIVEN':
                judgments['task_supplied'] = {'value':'YES', 'citations':self._refs([{'document':a} for a in anchors], local=local)}
            row = {'id': 'SLOT:' + identity, 'kind': 'SLOT', 'subject': 'GLOBAL', 'action_ids': sorted(set(targets)),
                'key': relation, 'relation': relation, 'value': None, 'refs': [], 'status': 'UNRESOLVED',
                'need_id': identity, 'aliases': [identity], 'group_id': identity, 'route': need['route'],
                'anchor_clauses': anchors, 'source_citations': source_refs, 'query': query, 'search_terms': need.get('search_terms', []),
                'alternative_queries': need.get('alternative_queries', []), 'locator': locator,
                'scope': scope, 'objects': objects, 'model_locations': need.get('model_locations', []),
                'fact_refs': deepcopy(need.get('fact_refs', [])),
                'expression_check': deepcopy(need.get('expression_check', {'value':'UNKNOWN','citations':[]})),
                'unresolved_conditions': deepcopy(need.get('unresolved_conditions', [])),
                'unsupported_reason': need.get('unsupported_reason', ''), **judgments}
            row['source_attribute_ids'] = list(need.get('source_attribute_ids', []))
            if need.get('_attribute_generated') and need.get('confirmation_locations'):
                row['confirmation_locations'] = deepcopy(need['confirmation_locations'])
            row['fact_refs'] = sorted(set(row['fact_refs'] + [r['id'].split(':', 1)[1]
                for r in rows if r['kind'] == 'FACT' and
                r.get('source_attribute', {}).get('id') in row['source_attribute_ids']]))
            self._condition(row['expression_check'])
            if not isinstance(row['unresolved_conditions'], list) or any(
                    not isinstance(value, str) or not value.strip() for value in row['unresolved_conditions']):
                raise ValueError('unresolved_conditions must list concrete unknown predicates')
            if not isinstance(row['unsupported_reason'], str):
                raise ValueError('unsupported_reason must be text')
            same = next((r for r in rows if r['kind'] == 'SLOT' and r['relation'] == relation and r['scope'] == scope), None)
            # A shared textual rule does not make one object's applicability certify another.
            if same and set(same['action_ids']) != set(row['action_ids']) and any(
                    same[key]['value'] != row[key]['value'] for key in (*judgments, 'expression_check')):
                same = None
            if same:
                for key in (*judgments, 'expression_check'):
                    values = {same[key]['value'], row[key]['value']} - {'UNKNOWN'}
                    if len(values) > 1:
                        raise ValueError('conflicting judgments for the same relation and scope: ' + key)
                    if row[key]['value'] != 'UNKNOWN':
                        same[key] = row[key]
                same['aliases'].append(identity)
                same['action_ids'] = sorted(set(same['action_ids'] + row['action_ids']))
                same['anchor_clauses'] = sorted(set(same['anchor_clauses'] + anchors))
                same['model_locations'] = sorted(set(same['model_locations'] + row['model_locations']))
                same['fact_refs'] = sorted(set(same['fact_refs'] + row['fact_refs']))
                same['source_attribute_ids'] = sorted(set(same.get('source_attribute_ids', []) + row['source_attribute_ids']))
                same['source_citations'].extend(ref for ref in source_refs if ref not in same['source_citations'])
                same['unresolved_conditions'] = sorted(set(same['unresolved_conditions'] + row['unresolved_conditions']))
                for key in objects:
                    same['objects'][key] = sorted(set(same['objects'][key] + objects[key]))
            else:
                rows.append(row)

        return rows

    def _known_rows(self, model, mapped, reserved=()):
        """Record already compiled objects; this is not a semantic certification."""
        rows, used = [], set(reserved)
        elements = [('objective', model['objective'])] + [('constraint:' + c['name'], c) for c in model['constraints']]
        for label, item in elements:
            index = 1
            while f'R{index:03}' in used:
                index += 1
            identity = f'R{index:03}'
            used.add(identity)
            actions = sorted(item['terms'])
            anchors = [r['clause_id'] for r in mapped if label in r.get('elements', [])]
            refs = deepcopy(item['citations'])
            if not anchors:
                anchors = [c['id'] for c in self.clauses if any(r['document'] == 'task' and _text_span(c['text'], r['quote']) is not None for r in refs)]
            locations = ['objective:' + a for a in actions] if label == 'objective' else [label]
            unknown = {'value':'UNKNOWN', 'citations':[]}
            rows.append({'id':'SLOT:' + identity, 'kind':'SLOT', 'need_id':identity, 'aliases':[identity],
                'group_id':identity, 'subject':'GLOBAL', 'action_ids':actions or ['GLOBAL'],
                'relation':'encoded ' + label, 'key':'encoded ' + label, 'value':None,
                'origin':'BASE_MODEL', 'closure_basis':'MECHANICAL_MODEL_MAPPING',
                'semantic_status':'NOT_CERTIFIED', 'status':'WRITTEN', 'route':'GIVEN',
                'anchor_clauses':anchors, 'refs':refs, 'model_locations':locations, 'fact_refs':[],
                'objects':{'actions':actions,'variables':actions,'constraints':[] if label == 'objective' else [item['name']],
                           'objective_coefficients':actions if label == 'objective' else []},
                'scope':{k:None for k in ('jurisdiction','subject_type','activity','as_of')},
                'locator':{},'query':'','search_terms':[],'alternative_queries':[],
                **{k:deepcopy(unknown) for k in ('task_supplied','evidence_supplied','excluded','expression_check')}})
        return rows

    def resolve_relation_ref(self, reference, rows=None):
        """An existing fact may alias one explicitly bound relation, never several."""
        rows = self.rows if rows is None else rows
        reference = reference.strip()
        slots = [r for r in rows if r['kind'] == 'SLOT']
        direct = [r for r in slots if reference in r['aliases']]
        if len(direct) == 1:
            return direct[0]['need_id']
        fact = reference.removeprefix('FACT:')
        if not any(r['id'] == 'FACT:' + fact for r in rows if r['kind'] == 'FACT'):
            raise ValueError('unknown relation or fact reference: ' + reference)
        bound = [r for r in slots if fact in r.get('fact_refs', [])]
        if len(bound) != 1:
            raise ValueError('fact reference has no unique bound relation: ' + reference)
        return bound[0]['need_id']

    def _fact_binding(self, rows, binding):
        identity = self.resolve_relation_ref(binding['relation_id'], rows)
        refs = binding.get('fact_refs', [])
        if not isinstance(refs, list) or any(not isinstance(v, str) for v in refs):
            raise ValueError('fact_refs must be a list of existing fact identifiers')
        refs = [v.strip().removeprefix('FACT:').strip() for v in refs]
        facts = {r['id'].split(':',1)[1]:r for r in rows if r['kind'] == 'FACT'}
        for ref in refs:
            if ref not in facts or facts[ref]['status'] != 'READY':
                raise ValueError('fact binding requires an observed, nonconflicting known fact: ' + ref)
        row = next(r for r in rows if r['kind'] == 'SLOT' and r['need_id'] == identity)
        row['fact_refs'] = sorted(set(row.get('fact_refs', []) + refs))

    def _locations(self, row, model):
        allowed = {'var:' + a for a in self.actions} | {'objective:' + a for a in model['objective']['terms']}
        allowed |= {'constraint:' + c['name'] for c in model['constraints']}
        locations = row.get('model_locations', [])
        if not isinstance(locations, list) or any(not isinstance(v, str) for v in locations):
            raise ValueError('model_locations must be a list of exact model addresses')
        if set(locations) - allowed:
            raise ValueError('unknown model location: ' + str(sorted(set(locations) - allowed)))
        if set(row['objects']['constraints']) - {c['name'] for c in model['constraints']}:
            raise ValueError('relation references an unknown base constraint')
        bound = set(row['objects']['actions'] + row['objects']['variables'] + row['objects']['objective_coefficients'])
        bound.update(v for c in model['constraints'] if c['name'] in row['objects']['constraints'] for v in c['terms'])
        if set(row['action_ids']) - {'GLOBAL'} - bound:
            raise ValueError('relation action_ids must refer to its bound OR objects')
        # Merely citing a variable declaration does not encode its business relationship.
        return bool(locations) and all(not loc.startswith('var:') for loc in locations)

    def _confirmation_span(self, ref):
        """Locate a checked excerpt in its original clause, not a repeated phrase."""
        text = self.store.documents[ref['document']].text
        declared = ref.get('submitted_document', '').removeprefix('task:').strip()
        clauses, cursor = {}, 0
        if ref['document'] == 'task':
            for clause in self.clauses:
                span = _text_span(text[cursor:], clause['text'])
                if span is not None:
                    start, end = cursor + span[0], cursor + span[1]
                    clauses[clause['id']] = (clause['text'], start, end)
                    cursor = end
        matches = [key for key, (body, _, _) in clauses.items()
                   if _text_span(body, ref['quote']) is not None]
        clause_id = declared if declared in clauses else matches[0] if len(matches) == 1 else None
        if clause_id is not None:
            body, start, _ = clauses[clause_id]
            span = _text_span(body, ref['quote'])
            if span is None:
                return None
            span = (start + span[0], start + span[1])
        else:
            span = _text_span(text, ref['quote'])
            if span is None or _text_span(text[span[0] + 1:], ref['quote']) is not None:
                return None  # An unqualified repeated excerpt has no unique source position.
        return clause_id, span

    def _status(self, row, *, written=False, excluded=False):
        if row['excluded']['value'] == 'YES' or excluded:
            row['status'], row['route'] = 'EXCLUDED', 'GIVEN'
        elif row.get('unsupported_reason') and row['route'] == 'UNSUPPORTED':
            row['status'] = 'UNSUPPORTED'
        elif row.get('unresolved_conditions') and written:
            row['status'], row['route'] = 'TO_INTERPRET', 'GIVEN'
        elif written:
            row['status'], row['route'] = 'WRITTEN', 'GIVEN'
        elif row['task_supplied']['value'] == 'YES' or row['evidence_supplied']['value'] == 'YES':
            row['status'], row['route'] = 'TO_INTERPRET', 'GIVEN'
        elif row['route'] in {'FUTURE', 'UNSUPPORTED'}:
            row['status'] = 'UNRESOLVED'
        else:
            row['status'], row['route'] = 'TO_ACQUIRE', 'PUBLIC'
        row['refs'] = [ref for key in ('task_supplied','evidence_supplied','excluded') for ref in row[key]['citations']]
        return row['status']

    @staticmethod
    def _linked(row, identity):
        return identity in row.get('aliases', [row['need_id']])

    def _difference_reference(self, rule, related):
        """Reuse an existing two-object difference, without introducing a new coupling."""
        if rule['kind'] != 'linear':
            return None
        def direction(row):
            terms = {a: v for a, v in row['terms'].items() if v != 0}
            if len(terms) != 2 or row.get('sense') not in {'<=', '>='}:
                return None
            keys = sorted(terms)
            if terms[keys[0]] != -terms[keys[1]]:
                return None
            sign = 1 if row['sense'] == '<=' else -1
            scale = abs(terms[keys[0]])
            return tuple((a, sign * terms[a] / scale) for a in keys)
        comparison = direction(rule)
        if comparison is None:
            return None
        variables = {a for a, _ in comparison}
        if len(variables & related) != 1 or len(variables - related) != 1:
            return None
        sources = [c['name'] for c in self.model['constraints'] if direction(c) == comparison]
        if sources:
            return {'source_constraints': sources, 'reference_actions': sorted(variables - related)}
        return None

    def accept_plan(self, proposal):
        p = prepare_attributes(deepcopy(proposal), self.public, self.clauses)
        model, mapped = p['model'], p['task_map']
        _unique(model['variables'], 'id', self.actions)
        if any(v['type'] != self.actions[v['id']]['type'] for v in model['variables']):
            raise ValueError('public variable type differs from output_schema')
        if model['objective']['unit'] != self.public['output_schema']['objective']['canonical_unit']:
            raise ValueError('objective unit differs from public canonical unit')
        self._refs(model['objective']['citations'], local=True)
        _unique(model['constraints'], 'name')
        for row in model['constraints']:
            self._refs(row['citations'], local=True)
        _unique(mapped, 'clause_id', [c['id'] for c in self.clauses])
        elements = {'objective'} | {'var:' + a for a in self.actions} | {'constraint:' + c['name'] for c in model['constraints']}
        notes = []
        for row in mapped:
            role, labels = row['role'], row.get('elements', [])
            clause = next(c['text'] for c in self.clauses if c['id'] == row['clause_id'])
            if re.fullmatch(r'【[^】]+】', clause.strip()):
                row.update(role='CONTEXT', elements=[])
                role, labels = 'CONTEXT', []
            if role not in {'MODEL', 'CONTEXT', 'EXTERNAL', 'OUTPUT'} or not isinstance(labels, list) or any(not isinstance(x, str) for x in labels):
                raise ValueError('invalid task mapping role or labels')
            if role == 'MODEL':
                aliases = {a:'var:'+a for a in self.actions} | {c['name']:'constraint:'+c['name'] for c in model['constraints']}
                labels = [aliases.get(x, 'objective' if x.startswith(('objective.', 'model.objective')) else x) for x in labels]
                if not labels or set(labels) - elements:
                    clause = next(c['text'] for c in self.clauses if c['id'] == row['clause_id'])
                    recovered = []
                    cited = [('objective',model['objective']['citations'])] + [('constraint:'+c['name'],c['citations']) for c in model['constraints']]
                    for target, refs in cited:
                        if any(r['document'] == 'task' and _text_span(clause,r['quote']) is not None for r in refs):
                            recovered.append(target)
                    if not recovered:
                        raise ValueError('MODEL mapping has no existing element or citation-backed recovery: '+row['clause_id'])
                    notes.append({'clause_id':row['clause_id'],'submitted_elements':labels,'recovered_from_citations':recovered})
                    labels = recovered
                row['elements'] = labels
            allowed = {'actions', 'objective', 'unit'} if role == 'OUTPUT' else elements
            if role != 'MODEL' and set(labels) - allowed:
                notes.append({'clause_id': row['clause_id'], 'role': role, 'unresolved_labels': [x for x in labels if x not in allowed]})
        missing = missing_plan_relations(p, self.clauses)
        if missing:
            raise PlanCoverageError(missing)
        # Legacy fixtures retain their old shape; current PLAN no longer repeats known relations.
        known = self._known_rows(model, mapped, [n['id'] for n in p.get('needs', []) if n.get('id')]) if 'checks' not in p else []
        rows = self._register(known, p.get('facts', []), p.get('needs', []), local=True)
        checks = p.get('checks', [])
        if 'checks' in p:
            _unique(checks, 'action_id', {*self.actions, 'GLOBAL'})
        for check in checks:
            subject = check['action_id']
            check['external_rule'] = _truth(check['external_rule'])
            check['given_rule'] = _truth(check['given_rule'])
            if check['external_rule'] not in TRUTHS or check['given_rule'] not in TRUTHS:
                raise ValueError('checks require YES/NO/UNKNOWN')
            if check.get('citations'):
                self._refs(check['citations'], local=True)
            elif check['external_rule'] != 'NO' or check['given_rule'] != 'NO':
                raise ValueError('a positive rule check requires task references')
            linked = [r for r in rows if r['kind'] == 'SLOT' and
                      (subject == 'GLOBAL' or subject in r['action_ids'] or 'GLOBAL' in r['action_ids'])]
            if check.get('relation_ids') is not None:
                selected = check['relation_ids']
                if not isinstance(selected, list) or not selected or any(not any(self._linked(r, n) for r in linked) for n in selected):
                    raise ValueError('check relation_ids must name a registered slot covering its action')
                linked = [r for r in linked if any(self._linked(r, n) for n in selected)]
            if not linked:
                raise ValueError('each action and GLOBAL require a concrete registered slot; mention NO does not close a gap: ' + subject)
            rows.append({'id': 'CHECK:' + subject, 'kind': 'CHECK', 'subject': subject, 'key': 'explicit_rule_mention',
                'value': {'external_rule': check['external_rule'], 'given_rule': check['given_rule']},
                'relation_ids': [r['need_id'] for r in linked], 'refs': check.get('citations',[]), 'status': 'READY'})
        for row in [r for r in rows if r['kind'] == 'SLOT']:
            if row.get('origin') == 'BASE_MODEL':
                continue
            encoded = self._locations(row, model)
            self._status(row, written=encoded and row['task_supplied']['value'] == 'YES' and row['expression_check']['value'] == 'YES')
        ir = compile_model(model['variables'], _base(model), model['objective']['unit'])
        metrics = {'action_coverage': [len(self.actions), len(self.actions)], 'clause_mapping': [len(mapped), len(self.clauses)],
            'check_coverage': [len(checks), len(self.actions) + 1] if checks else [0,0], 'mapping_notes': notes, 'compiled': True,
            'semantic_fidelity': None, 'unmapped_elements': 0, 'mechanically_registered':sum(r.get('origin') == 'BASE_MODEL' for r in rows),
            'information_scope':'registered_relations_and_numeric_action_attributes',
            'attribute_coverage':p['_attribute_coverage'], 'fact_source_notes':p.get('_fact_source_notes',[])}
        self._install(rows, model, mapped, ir, metrics)
        return ir, metrics

    def signature(self):
        """Business progress only; annotations and citation layout cannot restart work."""
        return _signature(self.rows, self.model)

    def pending(self):
        return deepcopy([r for r in self.rows if _pending(r)])

    def gates(self):
        gates = []
        for row in self.rows:
            if row['kind'] != 'SLOT' or row['status'] in {'WRITTEN', 'EXCLUDED'}:
                continue
            known = sum(bool(row['locator'].get(k)) for k in LOCATORS)
            gates.append({'need_id': row['need_id'], 'group_id': row['group_id'],
                'trigger': row['status'] == 'TO_ACQUIRE', 'status': row['status'],
                'affected_actions': len(row['objects']['actions']), 'query': row['query'], 'search_terms': row['search_terms'],
                'alternative_queries': row['alternative_queries'], 'readiness': known * 20,
                'known_fields': known, 'required_fields': 5, 'route': row['route']})
        return sorted(gates, key=lambda g: (g['readiness'] < 80, -g['affected_actions'], g['group_id']))

    def accept_fusion(self, proposal):
        proposal = deepcopy(proposal)
        references = proposal.get('refinement_references', [])
        if not isinstance(references, list):
            raise ValueError('refinement_references must be a list')
        if references:
            self._refs(references)  # Validate discarded local fields without importing their truth values.
        rows = self._register(deepcopy(self.rows), proposal.get('facts', []), proposal.get('needs', []), local=False)
        if proposal.get('relation_binding') is not None:
            self._fact_binding(rows, proposal['relation_binding'])
        for rule in proposal.get('rules', []):
            rule['need_ids'] = [self.resolve_relation_ref(v, rows) for v in rule['need_ids']]
        replaced = {self.resolve_relation_ref(v, rows) for v in proposal.get('replace_relations', [])}
        for row in [r for r in rows if r['kind'] == 'RULE']:
            linked = set(row['value']['need_ids'])
            if linked & replaced and not linked <= replaced:
                raise ValueError('replacing a shared rule requires all its bound relations')
        rows = [r for r in rows if not (r['kind'] == 'RULE' and set(r['value']['need_ids']) & replaced)]
        # An incremental FUSE changes only an explicitly identified previous rule.
        # Equal variable sets alone do not prove that two business rules are the same.
        replacements = set()
        for rule in proposal.get('rules', []):
            if 'replaces_rule' not in rule:
                continue
            reference = rule['replaces_rule']
            if not isinstance(reference, str):
                raise ValueError('replaces_rule must identify an existing rule')
            reference = reference.strip().removeprefix('RULE:').strip()
            previous = next((row for row in rows if row['kind'] == 'RULE' and row['key'] == reference), None)
            if previous is None or reference in replacements:
                raise ValueError('replaces_rule is unknown or repeated: ' + reference)
            if set(previous['value']['need_ids']) != set(rule['need_ids']):
                raise ValueError('replaces_rule must retain exactly its bound relations')
            replacements.add(reference)
            rule['replaces_rule'] = reference
        rows = [row for row in rows if not (row['kind'] == 'RULE' and row['key'] in replacements)]
        slots = [r for r in rows if r['kind'] == 'SLOT']
        for row in slots:
            if row['need_id'] not in {r['need_id'] for r in self.rows if r['kind'] == 'SLOT'}:
                self._locations(row, self.model)
        lookup = {alias: row for row in slots for alias in row['aliases']}
        updates = proposal.get('relation_updates', [])
        _unique(updates, 'need_id')
        for update in updates:
            if update['need_id'] not in lookup:
                raise ValueError('relation update requires a registered need')
            if set(update) - {'need_id','task_supplied','evidence_supplied','excluded','model_locations','expression_check',
                              'unresolved_conditions','unsupported_reason','query','search_terms','alternative_queries'}:
                raise ValueError('unknown relation update field')
            row = lookup[update['need_id']]
            if 'query' in update:
                if not isinstance(update['query'], str):
                    raise ValueError('relation query must be text')
                row['query'] = update['query'].strip()
            for key in ('search_terms', 'alternative_queries'):
                if key in update:
                    values = update[key]
                    if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
                        raise ValueError('relation ' + key + ' must list nonempty text')
                    row[key] = [value.strip() for value in values]
            if 'unresolved_conditions' in update:
                values = update['unresolved_conditions']
                if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                    raise ValueError('unresolved_conditions must list concrete unknown predicates')
                row['unresolved_conditions'] = deepcopy(values)
            if 'unsupported_reason' in update:
                if not isinstance(update['unsupported_reason'], str):
                    raise ValueError('unsupported_reason must be text')
                row['unsupported_reason'] = update['unsupported_reason']
            for key in ('task_supplied','evidence_supplied','excluded','expression_check'):
                if key in update:
                    self._condition(update[key])
                    if key == 'evidence_supplied' and update[key]['value'] == 'YES':
                        self._refs(update[key]['citations'], external=True)
                    if key == 'task_supplied' and update[key]['value'] != 'UNKNOWN':
                        self._refs(update[key]['citations'], local=True)
                    row[key] = deepcopy(update[key])
            if 'model_locations' in update:
                probe = deepcopy(row)
                probe['model_locations'] = update['model_locations']
                self._locations(probe, self.model)
                if row.get('confirmation_locations') and sorted(update['model_locations']) != sorted(row['confirmation_locations']):
                    raise ValueError('existing-constraint confirmation cannot change its program binding')
                row['model_locations'] = update['model_locations']
            if row.get('confirmation_locations') and 'expression_check' in update and update['expression_check']['value'] != 'UNKNOWN':
                refs = self._refs(update['expression_check']['citations'], local=True)
                def matches_source(a, b):
                    if a['document'] != b['document']:
                        return False
                    left, right = self._confirmation_span(a), self._confirmation_span(b)
                    if left is None or right is None:
                        return False
                    aid, (a0, a1) = left
                    bid, (b0, b1) = right
                    return (aid is None or bid is None or aid == bid) and (
                        a0 <= b0 <= b1 <= a1 or b0 <= a0 <= a1 <= b1)
                for location in row['confirmation_locations']:
                    constraint = next(c for c in self.model['constraints'] if location == 'constraint:' + c['name'])
                    if not any(matches_source(a, b) for a in refs for b in constraint['citations']):
                        raise ValueError('existing-constraint confirmation needs the bound constraint source')
        resolutions, proposed = proposal.get('resolutions', []), proposal.get('rules', [])
        _unique(resolutions, 'need_id')
        _assign_ids(proposed, rows, 'RULE', 'M')
        _unique(proposed, 'id')
        no_effect = set()
        for resolution in resolutions:
            if resolution['need_id'] not in lookup or resolution['status'] not in {'RESOLVED', 'NO_EFFECT', 'UNKNOWN'}:
                raise ValueError('resolution requires a registered need and supported status')
            if resolution['status'] != 'UNKNOWN':
                self._refs(resolution.get('citations', []))
            if resolution['status'] == 'NO_EFFECT':
                no_effect.add(lookup[resolution['need_id']]['need_id'])
            # A model's RESOLVED/NO_EFFECT label never writes the business status.
        for rule in proposed:
            linked_slots = [slot for slot in slots if slot['need_id'] in rule['need_ids']]
            self._refs(rule['citations'], external=any(slot['task_supplied']['value'] != 'YES'
                       and slot['status'] != 'EXCLUDED' for slot in linked_slots))
            self._condition(rule.get('expression_check', {'value': 'UNKNOWN', 'citations': []}))
            self._quantity_basis(rule)
            self._scope_checks(rule, slots)
            for condition in rule.get('conditions', []):
                for predicate in [*condition.get('required', []), *condition.get('exceptions', []),
                                  condition.get('action_matches', {'value': 'UNKNOWN', 'citations': []})]:
                    self._condition(predicate)
            if any(_rule_signature(row['value']) == _rule_signature(rule)
                   for row in rows if row['kind'] == 'RULE'):
                continue
            rows = [r for r in rows if not (r['kind'] == 'RULE' and r['key'] == rule['id'])]
            rows.append({'id': 'RULE:' + rule['id'], 'kind': 'RULE', 'subject': 'GLOBAL', 'key': rule['id'],
                         'value': deepcopy(rule), 'refs': rule.get('citations', []), 'status': 'READY'})
        rows = [r for r in rows if r['kind'] != 'CONDITION']
        cons, effect_count = _base(self.model), 0
        outcomes = {r['need_id']: [] for r in slots}
        for row in slots:
            if row.get('origin') == 'BASE_MODEL':
                continue
            locations = row.get('model_locations', [])
            base_locations = {'constraint:' + c['name'] for c in self.model['constraints']} | {'objective:' + a for a in self.model['objective']['terms']}
            written = bool(locations) and set(locations) <= base_locations and row['task_supplied']['value'] == 'YES' and row['expression_check']['value'] == 'YES'
            self._status(row, written=written)
            if not written:
                row['model_locations'] = list(row.get('confirmation_locations', []))
        for stored in [r for r in rows if r['kind'] == 'RULE']:
            rule = stored['value']
            if not rule.get('need_ids') or any(n not in lookup for n in rule['need_ids']):
                raise ValueError('rule must link to registered needs')
            linked = {lookup[n]['need_id'] for n in rule['need_ids']}
            rule_slots = [r for r in slots if r['need_id'] in linked and r['status'] != 'EXCLUDED']
            if not rule_slots:
                stored['status'] = 'EXCLUDED'
                continue
            external = any(r['task_supplied']['value'] != 'YES' for r in rule_slots)
            self._refs(rule['citations'], external=external)
            expression = deepcopy(rule.get('expression_check', {'value':'UNKNOWN','citations':[]}))
            expression_truth = self._condition(expression)
            quantity_truth = self._quantity_basis(rule)
            if expression_truth == 'NO':
                raise ValueError('mathematical expression contradicts the cited comparison')
            if rule.get('unit') is not None and rule['unit'] != self.model['objective']['unit'] and rule['kind'] == 'objective_adjustment':
                raise ValueError('objective adjustment unit differs from the model unit')
            modality, kind = rule['modality'], rule['kind']
            if modality not in {'MUST', 'MUST_NOT', 'MAY', 'NUMERIC'} or kind not in {
                    'lower_bound', 'upper_bound', 'linear', 'objective_adjustment', 'threshold', 'indicator'}:
                raise ValueError('unsupported modality or mathematical kind')
            if modality == 'MUST_NOT' and kind == 'lower_bound':
                raise ValueError('a prohibition cannot become a positive lower bound')
            aggregate = kind in {'linear', 'objective_adjustment', 'threshold', 'indicator'}
            related = set().union(*(_slot_targets(r) for r in rule_slots))
            _unique(rule['conditions'], 'action_id')
            missing = {c['action_id']:sorted({'required','exceptions','action_matches'} - c.keys())
                       for c in rule['conditions'] if {'required','exceptions','action_matches'} - c.keys()}
            if missing:
                raise ValueError('Every condition requires required, exceptions, action_matches; missing: ' + json.dumps(missing))
            actual = {c['action_id'] for c in rule['conditions']}
            expected = {'GLOBAL'} if aggregate else actual - {'GLOBAL'}
            if not expected or (aggregate and actual != expected) or (not aggregate and expected - related):
                raise ValueError('rule conditions must identify related action_id objects; aggregate rules require GLOBAL')
            if kind in {'linear', 'objective_adjustment', 'indicator'}:
                terms = rule['terms']
                if not terms or set(terms) - self.actions.keys():
                    raise ValueError('aggregate terms must reference public actions')
                # Explicit zero says that this object has no contribution to this
                # comparison. It is represented, while omitted objects remain open.
                # Actual model targets are still derived from nonzero coefficients.
                covered = set(terms) & related
                scope_required = {action for action, coefficient in terms.items() if coefficient != 0}
                if kind == 'indicator':
                    trigger = rule['trigger']
                    if trigger not in self.actions or self.actions[trigger]['type'] != 'BINARY':
                        raise ValueError('indicator trigger must be a public binary action')
                    if type(rule.get('active_value', 1)) is not int or rule.get('active_value', 1) not in {0, 1}:
                        raise ValueError('indicator active_value must be 0 or 1')
                    covered.add(trigger)
                    scope_required.add(trigger)
            elif kind == 'threshold':
                quantity, required = rule['quantity'], rule['required']
                if quantity not in self.actions or required not in self.actions or self.actions[required]['type'] != 'BINARY':
                    raise ValueError('threshold requires public quantity and binary required action')
                if quantity == required or modality == 'MUST_NOT':
                    raise ValueError('threshold requires a distinct quantity and positive required action')
                covered = {quantity, required}
                scope_required = covered
            else:
                covered = set(expected)
                scope_required = covered
            outside = scope_required - related
            if outside:
                binding = self._difference_reference(rule, related)
                if binding and outside == set(binding['reference_actions']):
                    stored['reference_binding'] = binding
                    outside = set()  # Reference objects do not enlarge this slot's coverage.
            if not covered or outside:
                raise ValueError('rule mathematics must reference objects linked to its relation')
            truths, condition_rows = {}, []
            for condition in rule['conditions']:
                required = [self._condition(c) for c in condition['required']]
                exceptions = [self._condition(c) for c in condition['exceptions']]
                matches = self._condition(condition['action_matches'])
                truth = all_of([all_of(required), negate(any_of(exceptions)), matches])
                subject = condition['action_id']
                condition_rows.append({'id': 'CONDITION:' + rule['id'] + ':' + subject, 'kind': 'CONDITION', 'subject': subject,
                    'key': rule['id'], 'value': truth, 'refs': deepcopy(condition), 'status': 'OPEN' if truth == 'UNKNOWN' else 'READY'})
                truths[subject] = truth
            common = truths.get('GLOBAL', 'YES') if not aggregate else 'YES'
            scope_checks = self._scope_checks(rule, slots)
            scope_gate = negate(any_of([value for _, _, value in scope_checks]))
            combined = {subject: all_of([common, truths[subject], scope_gate]) for subject in expected}
            for row in condition_rows:
                truth = combined.get(row['subject'], all_of(list(combined.values())))
                row.update(value=truth, status='OPEN' if truth == 'UNKNOWN' else 'READY')
            rows.extend(condition_rows)
            for check, excluded, exception in scope_checks:
                value = negate(exception)
                relevant = any(truth != 'NO' for truth in combined.values())
                rows.append({'id': 'CONDITION:' + rule['id'] + ':scope:' + check['relation_id'],
                    'kind': 'CONDITION', 'subject': 'GLOBAL', 'key': rule['id'],
                    'relation_id': check['relation_id'], 'value': value,
                    'refs': {'shared_exception_scope': deepcopy(check['shared_exception_scope']),
                             'excluded': deepcopy(excluded)},
                    'status': ('OPEN' if relevant else 'EXCLUDED') if value == 'UNKNOWN' else 'READY'})
            if kind == 'linear':
                relevant_basis = any(value != 'NO' for value in combined.values())
                rows.append({'id': 'CONDITION:' + rule['id'] + ':quantity_basis', 'kind': 'CONDITION',
                    'subject': 'GLOBAL', 'key': rule['id'], 'value': quantity_truth,
                    'refs': deepcopy(rule['quantity_basis']),
                    'status': ('OPEN' if relevant_basis else 'EXCLUDED') if quantity_truth == 'UNKNOWN' else 'READY'})
            active = [subject for subject, truth in combined.items() if truth == 'YES']
            interpretation_ready = expression_truth == 'YES' and quantity_truth == 'YES'
            unknown = 'UNKNOWN' in combined.values() or (bool(active) and not interpretation_ready)
            if expression_truth == 'YES':
                for row in rule_slots:
                    origin = 'evidence_supplied' if external else 'task_supplied'
                    row[origin] = {'value':'YES', 'citations':deepcopy(rule['citations'])}
            locations = []
            if active and modality != 'MAY' and interpretation_ready:
                if linked & no_effect:
                    raise ValueError('NO_EFFECT resolution contradicts an applicable mathematical effect')
                if kind in {'threshold', 'indicator'}:
                    if kind == 'threshold':
                        payload = {key: rule[key] for key in ('quantity', 'required', 'threshold')}
                    else:
                        payload = {'trigger': rule['trigger'], 'active_value': rule.get('active_value', 1),
                                   'terms': [{'var': k, 'coef': v} for k, v in terms.items()],
                                   'sense': rule['sense'], 'rhs': rule['rhs']}
                    cons.append(_contribution('rule_' + rule['id'], kind, payload, rule['citations']))
                    locations.append('constraint:rule_' + rule['id'])
                    effect_count += 1
                elif aggregate:
                    payload = {'terms': [{'var': k, 'coef': v} for k, v in terms.items()]}
                    if kind == 'linear':
                        payload.update(sense=rule['sense'], rhs=rule['rhs'])
                    cons.append(_contribution('rule_' + rule['id'], 'constraint' if kind == 'linear' else 'objective', payload, rule['citations']))
                    locations.append(('constraint:' if kind == 'linear' else 'objective_adjustment:') + 'rule_' + rule['id'])
                    effect_count += 1
                else:
                    for target in active:
                        cons.append(_contribution('rule_' + rule['id'] + '_' + target, 'bound',
                            {'var': target, 'lb' if kind == 'lower_bound' else 'ub': rule['bound']}, rule['citations']))
                        locations.append('bound:' + target + (':lb' if kind == 'lower_bound' else ':ub'))
                        effect_count += 1
            stored['model_locations'] = locations
            stored['status'] = 'TO_INTERPRET' if unknown else 'WRITTEN' if locations else 'EXCLUDED'
            for row in rule_slots:
                row_targets = _slot_targets(row)
                relevant = covered & row_targets
                if not relevant:
                    continue
                linked_locations = locations if aggregate else [
                    loc for loc in locations if loc.split(':')[1] in relevant]
                row['model_locations'] = sorted(set(row['model_locations'] + linked_locations))
                for target in relevant:
                    value = combined['GLOBAL'] if aggregate else combined[target]
                    status = ('TO_INTERPRET' if value == 'UNKNOWN' or (value == 'YES' and not interpretation_ready)
                              else 'EXCLUDED' if value == 'NO' or modality == 'MAY' else 'WRITTEN')
                    outcomes[row['need_id']].append((target, status))
        for row in slots:
            result = outcomes[row['need_id']]
            if result:
                expected = _slot_targets(row)
                covered = {target for target, status in result}
                states = [status for target, status in result]
                if 'TO_INTERPRET' in states or expected - covered or row.get('unresolved_conditions'):
                    self._status(row)
                    if row['status'] != 'UNSUPPORTED':
                        row['status'] = 'TO_INTERPRET'
                else:
                    self._status(row, written='WRITTEN' in states, excluded=all(s == 'EXCLUDED' for s in states))
        ir = compile_model(self.model['variables'], cons, self.model['objective']['unit'])
        unresolved = [r['id'] for r in rows if _pending(r)]
        metrics = {'compiled': True, 'accept': not unresolved, 'unresolved': unresolved,
                   'effect_count': effect_count, 'semantic_entailment': None,
                   'slot_coverage': [sum(r['status'] in {'WRITTEN','EXCLUDED'} for r in slots), len(slots)],
                   'field_edits': deepcopy(proposal.get('field_edits', []))}
        self._install(rows, self.model, self.mapping, ir, metrics)
        return ir, metrics

    def dump(self):
        return deepcopy({'case_id': self.public.get('id'), 'revision': self.revision,
            'input': {'public': self.public, 'text': self.text, 'clauses': self.clauses},
            'rows': self.rows, 'model': self.model, 'task_map': self.mapping,
            'documents': [{'id': d.id, 'url': d.url, 'version': d.version, 'title': d.title} for d in self.store.documents.values()],
            'operations': self.operations, 'derived': self.derived})
