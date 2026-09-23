"""Real Gurobi execution of compiler output; no LLM-generated executable code."""
import gurobipy as gp
from gurobipy import GRB


def solve(ir, timeout=90):
    with gp.Env(empty=True) as env:
        env.setParam('OutputFlag', 0)
        env.start()
        with gp.Model('searchworthy_rebuild', env=env) as model:
            model.Params.Threads = 1
            model.Params.TimeLimit = max(.001, timeout)
            variables = {v['id']: model.addVar(lb=v['lb'], ub=v['ub'], name=v['id'],
                         vtype={'BINARY': GRB.BINARY, 'INTEGER': GRB.INTEGER, 'CONTINUOUS': GRB.CONTINUOUS}[v['type']])
                         for v in ir['variables']}
            for row in ir['constraints']:
                expr = gp.quicksum(coef * variables[name] for name, coef in row['terms'].items())
                rhs = row['rhs']
                model.addConstr(expr <= rhs if row['sense'] == '<=' else expr >= rhs if row['sense'] == '>=' else expr == rhs,
                                name=row['name'])
            obj = ir['objective']
            model.setObjective(gp.quicksum(coef * variables[name] for name, coef in obj['terms'].items()) + obj['constant'],
                               GRB.MINIMIZE if obj['direction'] == 'min' else GRB.MAXIMIZE)
            model.optimize()
            if model.Status == GRB.INF_OR_UNBD:
                model.Params.DualReductions = 0
                model.optimize()
            status = {GRB.OPTIMAL: 'OPTIMAL', GRB.INFEASIBLE: 'INFEASIBLE', GRB.TIME_LIMIT: 'TIME_LIMIT',
                      GRB.UNBOUNDED: 'UNBOUNDED'}.get(model.Status, 'UNKNOWN')
            result = {'status': status, 'solver_status': int(model.Status), 'feasible': bool(model.SolCount),
                      'actions': None, 'objective': None, 'conflict_constraints': []}
            if model.SolCount:
                result['actions'] = {v['id']: float(variables[v['id']].X) if v['type'] == 'CONTINUOUS'
                                     else int(round(variables[v['id']].X)) for v in ir['variables']
                                     if v.get('visibility', 'public') == 'public'}
                result['objective'] = {'value': float(model.ObjVal), 'unit': obj['unit'], 'direction': obj['direction']}
            if status == 'INFEASIBLE':
                model.computeIIS()
                result['conflict_constraints'] = [c.ConstrName for c in model.getConstrs() if c.IISConstr]
            return result
