"""Stage-boundary formatting only. No evidence, scoring or retrieval decisions."""
from copy import deepcopy
import re


class FormatError(ValueError):
    def __init__(self, document, errors):
        self.document = deepcopy(document)
        self.errors = errors
        super().__init__('; '.join(f'{path}: {message}' for path, message in errors))


def normalize_stage(document, purpose, public, model, table, available):
    from searchworthy.table_loop import compile_checked, patch_model
    d = deepcopy(document)
    edits, errors = [], []

    def fail(path, message):
        errors.append((path, message))

    def required(obj, key, path, kind):
        if key not in obj or not isinstance(obj[key], kind):
            fail(path + '.' + key, f'required {kind.__name__}')
            return False
        return True

    def constraint(row, path):
        if not isinstance(row, dict):
            fail(path, 'required constraint object')
            return
        aliases = {'=': '==', '≤': '<=', '≥': '>='}
        if row.get('sense') in ('<', '>'):
            raise ValueError('Strict inequality requires mathematical interpretation, not format repair')
        if isinstance(row.get('sense'), str) and row['sense'] in aliases:
            row['sense'] = aliases[row['sense']]
            edits.append(path + '.sense')
        if row.get('sense') not in ('<=', '>=', '=='):
            fail(path + '.sense', 'required <=, >= or ==; strict inequalities cannot be guessed')

    def objective(row, path):
        if not isinstance(row, dict):
            fail(path, 'required objective object')
            return
        spec = public['output_schema']['objective']
        canonical = spec['canonical_unit']
        unit = row.get('unit')
        # Only explicitly declared scale-one unit aliases; never change numbers.
        if isinstance(unit, str) and (unit.strip() == canonical or spec.get('accepted_units', {}).get(unit.strip()) == 1):
            if unit != canonical:
                row['unit'] = canonical
                edits.append(path + '.unit')
        if row.get('unit') != canonical:
            fail(path + '.unit', 'required canonical unit ' + canonical + '; do not rescale coefficients')

    if not isinstance(d, dict):
        raise FormatError(d, [('$', 'required JSON object; cannot safely infer a stage')])
    if purpose == 'PLAN_LITE':
        bare = set(d) == {'variables', 'objective', 'constraints'}
        m, prefix = (d, '$') if bare else (d.get('model'), '$.model')
        if not isinstance(m, dict):
            raise FormatError(d, [('$.model', 'required mathematical model object')])
        if required(m, 'variables', prefix, list):
            expected = {v['id'] for v in public['output_schema']['actions']}
            observed = [v.get('id') for v in m['variables'] if isinstance(v, dict) and isinstance(v.get('id'), str)]
            if len(observed) != len(m['variables']) or len(observed) != len(set(observed)) or set(observed) != expected:
                fail(prefix + '.variables', 'Public variable coverage mismatch; use each supplied action ID exactly once; no new IDs')
        objective(m.get('objective'), prefix + '.objective')
        if required(m, 'constraints', prefix, list):
            for i, row in enumerate(m['constraints']):
                constraint(row, f'{prefix}.constraints.{i}')
        if not errors:
            compile_checked(m, public, available)  # Retain original maths/citation validation.
    elif purpose in ('UPDATE', 'UPDATE_FINAL'):
        for key in ('model_patch', 'table_updates'):
            if isinstance(d.get(key), dict) and d[key]:
                d[key] = [d[key]]  # Exactly one explicit object, never invent or drop a row.
                edits.append('$.' + key)
            required(d, key, '$', list)
        targets = {c['name'] for c in model['constraints']}
        for i, patch in enumerate(d.get('model_patch') if isinstance(d.get('model_patch'), list) else []):
            path = f'$.model_patch.{i}'
            if not isinstance(patch, dict):
                fail(path, 'required patch object')
                continue
            op = patch.get('operation')
            if op not in {'add_constraint', 'replace_constraint', 'remove_constraint', 'replace_objective'}:
                fail(path + '.operation', 'unknown patch operation')
                continue
            if op in {'replace_constraint', 'remove_constraint'}:
                if not isinstance(patch.get('target'), str) or patch['target'] not in targets:
                    fail(path + '.target', 'required existing constraint target: ' + ', '.join(sorted(targets)))
                elif op == 'remove_constraint':
                    targets.remove(patch['target'])
            elif op == 'add_constraint':
                n = 1
                while f'C{n:03}' in targets:
                    n += 1
                targets.add(f'C{n:03}')
            if op == 'replace_objective':
                objective(patch.get('objective'), path + '.objective')
            elif op != 'remove_constraint':
                constraint(patch.get('constraint'), path + '.constraint')
        questions = {r['id']: r['question'] for r in table}
        for i, row in enumerate(d.get('table_updates') if isinstance(d.get('table_updates'), list) else []):
            path = f'$.table_updates.{i}'
            if not isinstance(row, dict):
                fail(path, 'required question object')
                continue
            if row.get('id') is None:
                if not isinstance(row.get('question'), str) or not row['question'].strip():
                    fail(path + '.question', 'new row requires an explicit question')
                elif not any(q.casefold() == row['question'].strip().casefold() for q in questions.values()):
                    questions[f'Q{len(questions)+1}'] = row['question'].strip()
            elif not isinstance(row['id'], str) or row['id'] not in questions:
                fail(path + '.id', 'unknown existing question ID; do not guess')
            elif row.get('question', questions[row['id']]) != questions[row['id']]:
                fail(path + '.question', 'existing question must remain exactly: ' + questions[row['id']])
        step = d.get('next')
        if not isinstance(step, dict):
            fail('$.next', 'required next action object')
        elif step.get('action') not in ('acquire', 'finish'):
            fail('$.next.action', 'required acquire or finish')
        elif step['action'] == 'acquire' and purpose != 'UPDATE_FINAL':
            qid = step.get('question_id')
            if qid is not None:
                if not isinstance(qid, str) or qid not in questions:
                    fail('$.next.question_id', 'unknown question ID')
                elif step.get('question') not in (None, questions[qid]):
                    fail('$.next.question', 'existing question must remain exactly: ' + questions[qid])
            elif not isinstance(step.get('question'), str) or not step['question'].strip():
                fail('$.next.question', 'acquisition must identify its missing question')
            query = step.get('query')
            if not isinstance(query, str) or not query.strip() or len(query) > 320 or re.search(r'[\u3400-\u9fff]|\bSWOR|SearchWorthy|benchmark.{0,15}answer|gold.{0,8}answer', query, re.I):
                fail('$.next.query', 'required one English domain query, 1..320 characters, no benchmark IDs or answers')
        if not errors:
            patch_model(model, d['model_patch'], public, available)
    if errors:
        raise FormatError(d, errors)
    return d, edits


def check_repair(original, repaired, paths, public):
    """A repair may only fill/change the fields explicitly rejected by validation."""
    allowed = set(paths)
    if '$' in allowed or '$.model' in allowed:
        raise ValueError('Whole-stage/model rewriting is not a format-only repair')

    def visit(a, b, path):
        if path in allowed:
            if path.endswith('.variables') and isinstance(a, list) and isinstance(b, list):
                expected = {v['id'] for v in public['output_schema']['actions']}
                before = {v.get('id'): v for v in a if isinstance(v, dict) and v.get('id') in expected}
                after = {v.get('id'): v for v in b if isinstance(v, dict)}
                if any(after.get(k) != v for k, v in before.items()):
                    raise ValueError('Format repair changed existing variable domains')
            return
        if type(a) is not type(b):
            raise ValueError('Format repair changed protected field ' + path)
        if isinstance(a, dict):
            for k in a.keys() | b.keys():
                child = path + '.' + k
                if child in allowed:
                    visit(a.get(k), b.get(k), child)
                elif k not in a or k not in b:
                    raise ValueError('Format repair added/removed protected field ' + child)
                else:
                    visit(a[k], b[k], child)
        elif isinstance(a, list):
            if len(a) != len(b):
                raise ValueError('Format repair changed protected list ' + path)
            for i, (left, right) in enumerate(zip(a, b)):
                visit(left, right, path + '.' + str(i))
        elif a != b:
            raise ValueError('Format repair changed protected field ' + path)
    visit(original, repaired, '$')
