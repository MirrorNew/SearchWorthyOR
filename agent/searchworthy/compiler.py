"""Pure recompilation of source contributions to a finite MILP.

Coefficients are executable expressions, not inert metadata. Every derived M is
computed after intersecting the current domains, including external bounds.
"""
from copy import deepcopy
import math
import re
from searchworthy.contracts import identity


class CompilationError(ValueError):
    pass


UNIT_ALIASES = {'cent': ('USD', .01), 'cents': ('USD', .01), 'USD_cent': ('USD', .01),
                'kUSD': ('USD', 1000), 'minute': ('hour', 1 / 60), 'minutes': ('hour', 1 / 60),
                'kg': ('kg', 1), 'g': ('kg', .001)}


def unit(raw):
    raw = raw or '1'
    parts = raw.replace(' ', '').split('/')
    if len(parts) > 2:
        raise CompilationError('unit supports numerator/denominator products: ' + raw)
    dim, factor = {}, 1.
    for i, side in enumerate(parts):
        power = 1 if i == 0 else -1
        for name in side.split('*'):
            if name in {'', '1', 'count'}:
                continue
            base, scale = UNIT_ALIASES.get(name, (name, 1))
            dim[base] = dim.get(base, 0) + power
            factor *= scale ** power
    return {k: v for k, v in dim.items() if v}, factor


def multiply_dims(a, b):
    result = dict(a)
    for k, v in b.items():
        result[k] = result.get(k, 0) + v
    return {k: v for k, v in result.items() if v}


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise CompilationError('expected finite numeric value')
    return float(value)


def expression(expr, parameters, default_unit='1', stack=()):
    if type(expr) in (int, float):
        dims, factor = unit(default_unit)
        return finite(expr) * factor, dims
    if not isinstance(expr, dict):
        raise CompilationError('expression must be a number or registered expression')
    if 'param' in expr:
        name = expr['param']
        if name in stack:
            raise CompilationError('cyclic parameter dependency: ' + name)
        if name not in parameters:
            raise CompilationError('missing parameter: ' + name)
        p = parameters[name]
        return expression(p['value'], parameters, p.get('unit', '1'), stack + (name,))
    if 'value' in expr:
        return expression(expr['value'], parameters, expr.get('unit', default_unit), stack)
    if 'add' in expr:
        terms = [expression(x, parameters, default_unit, stack) for x in expr['add']]
        if not terms or any(d != terms[0][1] for _, d in terms):
            raise CompilationError('addition has incompatible units')
        return sum(v for v, _ in terms), terms[0][1]
    if 'mul' in expr:
        result, dims = 1., {}
        for x in expr['mul']:
            value, d = expression(x, parameters, '1', stack)
            result *= value
            dims = multiply_dims(dims, d)
        return result, dims
    raise CompilationError('unsupported symbolic expression')


def compile_model(variables, contributions, objective_unit, overrides=None):
    overrides = overrides or {}
    cons = list(contributions)
    parameters = {}
    for c in cons:
        if c.kind == 'parameter':
            p = deepcopy(c.payload)
            if p['name'] in parameters:
                raise CompilationError('multiple active parameter definitions: ' + p['name'])
            if p['name'] in overrides:
                p['value'] = overrides[p['name']]
            if 'value' not in p:
                raise CompilationError('unresolved parameter: ' + p['name'])
            parameters[p['name']] = p
    var_rows = deepcopy(variables)
    for c in cons:
        if c.kind == 'auxiliary':
            for v in c.payload['variables']:
                if v.get('visibility') != 'internal':
                    raise CompilationError('new public actions are outside the registered scope')
                var_rows.append(deepcopy(v))
    names = [v['id'] for v in var_rows]
    if len(names) != len(set(names)) or not names:
        raise CompilationError('variables must be unique and nonempty')
    variables_by_id = {v['id']: v for v in var_rows}
    for v in var_rows:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,80}', v['id']):
            raise CompilationError('invalid variable ID')
        if v['type'] not in {'BINARY', 'INTEGER', 'CONTINUOUS'}:
            raise CompilationError('unsupported variable type')
        v['unit'] = v.get('unit', '1')
        dim, factor = unit(v['unit'])
        if factor != 1:
            raise CompilationError('variable domains must use canonical units')
        v['lb'], v['ub'] = finite(v['lb']), finite(v['ub'])
        if v['type'] == 'BINARY' and not (0 <= v['lb'] <= v['ub'] <= 1):
            raise CompilationError('binary domain outside [0,1]')
    domain_sources = {v['id']: [] for v in var_rows}
    for c in cons:
        if c.kind == 'bound':
            p = c.payload
            if p['var'] not in variables_by_id:
                raise CompilationError('unknown bound variable: ' + p['var'])
            v = variables_by_id[p['var']]
            for side in ('lb', 'ub'):
                if side in p:
                    value, dims = expression(p[side], parameters, p.get('unit', v['unit']))
                    if dims != unit(v['unit'])[0]:
                        raise CompilationError('bound unit mismatch')
                    v[side] = max(v[side], value) if side == 'lb' else min(v[side], value)
            domain_sources[v['id']].append(c.id)
    construction_derivations, expanded, parents = [], [], {}
    original_ids = [c.id for c in cons]
    for c in cons:
        if c.kind == 'construction':
            from searchworthy.constructions import expand
            children, trace = expand(c, var_rows, parameters)
            expanded.extend(children)
            parents.update({child.id:c.id for child in children})
            construction_derivations.append(trace)
        else:
            expanded.append(c)
    cons = expanded
    obj_dim, obj_factor = unit(objective_unit)
    if obj_factor != 1:
        raise CompilationError('objective must use canonical unit')
    objective = {'direction': None, 'terms': {}, 'constant': 0., 'unit': objective_unit}
    rows, derivations = [], []

    def terms(raw, row_unit):
        result = {}
        expected = unit(row_unit)[0]
        for t in raw:
            name = t['var']
            if name not in variables_by_id:
                raise CompilationError('unknown term variable: ' + name)
            var_unit = variables_by_id[name]['unit']
            inferred = row_unit if unit(var_unit)[0] == {} else row_unit + '/' + var_unit
            value, dims = expression(t['coef'], parameters, t.get('unit', inferred))
            if multiply_dims(dims, unit(var_unit)[0]) != expected:
                raise CompilationError('coefficient unit mismatch: ' + name)
            result[name] = result.get(name, 0.) + value
        return result

    for c in cons:
        p = c.payload
        if c.kind in {'parameter', 'bound', 'auxiliary'}:
            continue
        if c.kind == 'direction':
            if p['direction'] not in {'min', 'max'}:
                raise CompilationError('invalid objective direction')
            if objective['direction'] is not None:
                raise CompilationError('multiple active objective directions')
            objective['direction'] = p['direction']
        elif c.kind == 'objective':
            for name, value in terms(p.get('terms', []), objective_unit).items():
                objective['terms'][name] = objective['terms'].get(name, 0.) + value
            value, dims = expression(p.get('constant', 0), parameters, p.get('unit', objective_unit))
            if dims != obj_dim:
                raise CompilationError('objective constant unit mismatch')
            objective['constant'] += value
        elif c.kind in {'constraint', 'indicator'}:
            row_unit = p.get('unit', '1')
            row_terms = terms(p['terms'], row_unit)
            rhs, dims = expression(p['rhs'], parameters, row_unit)
            if dims != unit(row_unit)[0] or p['sense'] not in {'<=', '>=', '=='}:
                raise CompilationError('constraint RHS/sense mismatch')
            row = {'name': c.id, 'terms': row_terms, 'sense': p['sense'], 'rhs': rhs, 'source': c.id}
            if c.kind == 'constraint':
                rows.append(row)
            else:
                trigger = p['trigger']
                if trigger not in variables_by_id or variables_by_id[trigger]['type'] != 'BINARY':
                    raise CompilationError('indicator trigger must be an existing binary decision')
                if p.get('active_value', 1) not in {0, 1}:
                    raise CompilationError('invalid indicator active value')
                senses = ['<=', '>='] if p['sense'] == '==' else [p['sense']]
                for sense in senses:
                    extremum = sum(coef * variables_by_id[name]['ub' if (coef >= 0) == (sense == '<=') else 'lb']
                                   for name, coef in row_terms.items())
                    M = max(0., extremum - rhs if sense == '<=' else rhs - extremum)
                    sign = 1 if sense == '<=' else -1
                    compiled = deepcopy(row_terms)
                    if p.get('active_value', 1) == 1:
                        compiled[trigger] = compiled.get(trigger, 0.) + sign * M
                        new_rhs = rhs + sign * M
                    else:
                        compiled[trigger] = compiled.get(trigger, 0.) - sign * M
                        new_rhs = rhs
                    rows.append({**row, 'name': c.id + sense, 'sense': sense, 'terms': compiled, 'rhs': new_rhs})
                    derivations.append({'contribution': c.id, 'M': M, 'bounds': deepcopy(variables_by_id),
                                        'domain_sources': domain_sources, 'template': 'indicator'})
        elif c.kind == 'threshold':
            q, g = p['quantity'], p['required']
            if q not in variables_by_id or g not in variables_by_id or variables_by_id[g]['type'] != 'BINARY':
                raise CompilationError('threshold requires quantity and binary required action')
            limit, dims = expression(p['threshold'], parameters, variables_by_id[q]['unit'])
            if dims != unit(variables_by_id[q]['unit'])[0]:
                raise CompilationError('threshold unit mismatch')
            # q > L implies g = 1. Equality remains exempt. The converse is not asserted.
            M = max(0., variables_by_id[q]['ub'] - limit)
            row_terms = {q: 1.}
            row_terms[g] = row_terms.get(g, 0.) - M
            rows.append({'name': c.id, 'terms': row_terms, 'sense': '<=', 'rhs': limit, 'source': c.id})
            derivations.append({'contribution': c.id, 'M': M, 'upper_bound': variables_by_id[q]['ub'],
                                'threshold': limit, 'domain_sources': domain_sources[q], 'template': 'threshold'})
        else:
            raise CompilationError('unsupported contribution kind: ' + c.kind)
    if objective['direction'] is None:
        raise CompilationError('missing objective direction')
    # Empty intersections are mathematical contradictions, not compiler errors.
    for v in var_rows:
        if v['lb'] > v['ub']:
            rows.append({'name': 'empty-domain-' + v['id'], 'terms': {}, 'sense': '<=', 'rhs': -1,
                         'source': domain_sources[v['id']]})
            v['ub'] = v['lb']
    for row in rows:
        if isinstance(row.get('source'),str) and row['source'] in parents:
            row['source'] = parents[row['source']]
    return {'variables': var_rows, 'objective': objective, 'constraints': rows,
            'parameters': parameters, 'derivations': construction_derivations + derivations,
            'contribution_ids': original_ids}
