"""Two bounded, source-bound constructors over registered finite variables."""
from copy import deepcopy
from dataclasses import replace
from itertools import combinations
from math import comb
from searchworthy.contracts import identity

MAX_ROWS = 5000

CONTRACT = '''Use kind:"construction" for quantified finite families rather than manually
enumerating rows. The usual key/citations/dependencies/replaces envelope is unchanged.
payload for all subsets: {operator:"subsets",members:[{var:"public action",coef:NUMBER_OR_EXPRESSION}],
sizes:[1,2],sense:"<=|>=|==",rhs_by_size:{"1":EXPRESSION,"2":EXPRESSION},unit:"canonical unit",
mapping_citations:[task/source quotes for the complete collection and coefficient/threshold mapping]}.
Use every quantified size and every member stated by the source; the program enumerates all
subsets and registers row IDs. For per-member limits use sizes:[1]. No arbitrary code/strings.
payload for a source-supported bound on finite actions: {operator:"finite_actions",
members:[{var:"binary action",value:NUMBER_OR_EXPRESSION}],comparison:"<=|>=|==|<|>",
bound:NUMBER_OR_EXPRESSION,unit:"comparison unit",mapping_citations:[...]}. The program forbids
exactly the actions whose mapped values fail the comparison, leaving permitted actions free.
Use the exact source comparison, scope and exceptions; do not turn a latest time into equality.
Members enumerate the source-governed action class; explain excluded exception classes with
citations. Application conditions bind exogenous truth as before, never as optimization variables.
SELECTED application scope is program-bound to each expanded row. GLOBAL/JOINT remain unchanged.
Changing a family requires replacing the whole construction; never edit stale expanded rows.
'''


def expand(c, variables, parameters):
    from searchworthy.compiler import expression, CompilationError, unit
    p = c.payload
    members = p.get('members', [])
    registry = {v['id']: v for v in variables}
    names = [m.get('var') for m in members]
    if not names or len(names) != len(set(names)) or any(n not in registry for n in names):
        raise CompilationError('construction needs a unique nonempty registered variable collection')
    if not p.get('mapping_citations'):
        raise CompilationError('construction needs sourced collection/value mapping')
    rows, detail = [], {}
    if p.get('operator') == 'subsets':
        sizes = p.get('sizes', [])
        if not sizes or len(sizes) != len(set(sizes)) or any(type(k) is not int or not 1 <= k <= len(names) for k in sizes):
            raise CompilationError('invalid quantified subset sizes')
        count = sum(comb(len(names), k) for k in sizes)
        if count > MAX_ROWS:
            raise CompilationError('construction expansion exceeds resource limit')
        if set(p.get('rhs_by_size', {})) != {str(k) for k in sizes}:
            raise CompilationError('each quantified size needs exactly one sourced bound')
        for k in sorted(sizes):
            for group in combinations(sorted(members, key=lambda m:m['var']), k):
                rows.append({'terms':[{'var':m['var'], 'coef':deepcopy(m['coef'])} for m in group],
                    'sense':p['sense'], 'rhs':deepcopy(p['rhs_by_size'][str(k)]), 'unit':p.get('unit', '1')})
        detail = {'sizes':sorted(sizes), 'members':sorted(names)}
    elif p.get('operator') == 'finite_actions':
        if len(names) > MAX_ROWS or any(registry[n]['type'] != 'BINARY' for n in names):
            raise CompilationError('finite action comparison needs bounded binary choices')
        bound, dims = expression(p['bound'], parameters, p.get('unit','1'))
        operators = {'<=':lambda a,b:a<=b, '>=':lambda a,b:a>=b, '==':lambda a,b:a==b,
                     '<':lambda a,b:a<b, '>':lambda a,b:a>b}
        if p.get('comparison') not in operators:
            raise CompilationError('unsupported finite action comparison')
        allowed, forbidden = [], []
        for m in members:
            val, vdims = expression(m['value'], parameters, p.get('unit','1'))
            if vdims != dims:
                raise CompilationError('finite action mapping unit mismatch')
            (allowed if operators[p['comparison']](val,bound) else forbidden).append(m['var'])
        # One exact exclusion row also records an all-permitted family without adding restrictions.
        rows = [{'terms':[{'var':n,'coef':1} for n in sorted(forbidden)],'sense':'==','rhs':0,'unit':'1'}]
        detail = {'allowed':sorted(allowed),'forbidden':sorted(forbidden),'comparison':p['comparison'],'bound':bound}
    else:
        raise CompilationError('unsupported finite construction operator')
    result=[]
    for i,row in enumerate(rows):
        if 'trigger' in p:
            row.update(trigger=p['trigger'], active_value=p.get('active_value',1))
        result.append(replace(c, id=identity('expanded-row',[c.id,i]),
            kind='indicator' if 'trigger' in p else 'constraint', payload=row))
    return result, {'contribution':c.id,'template':'construction','construction':deepcopy(p),
                    'row_count':len(result),'row_ids':[r.id for r in result],**detail}


def accepts(ir, point):
    """Check a complete finite witness without using the generator's expansion algorithm."""
    if set(point) != {v['id'] for v in ir['variables']}:
        raise ValueError('counterexample must assign every registered variable')
    for v in ir['variables']:
        x=point[v['id']]
        if type(x) not in (int,float) or not v['lb']<=x<=v['ub'] or (v['type']!='CONTINUOUS' and x!=int(x)):
            return False
    for r in ir['constraints']:
        lhs=sum(a*point[n] for n,a in r['terms'].items())
        if not ({'<=':lhs<=r['rhs']+1e-8,'>=':lhs>=r['rhs']-1e-8,'==':abs(lhs-r['rhs'])<=1e-8}[r['sense']]):return False
    return True
