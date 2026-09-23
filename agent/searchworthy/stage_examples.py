"""Small fictional format examples; no experiment cases or answer information."""
import json
from searchworthy.case_state import source_attributes


def _rule_example(kind):
    """One complete fictional FUSE example for a supported rule form."""
    supported = {'each', 'unknown', 'exception', 'aggregate', 'threshold', 'indicator'}
    if kind not in supported:
        raise ValueError('Unknown fictional rule form: ' + kind)
    def refs(document): return [{'document': document}]
    def truth(value, document=None):
        return {'value': value, 'citations': refs(document) if document else []}
    actions = [{'id': 'demo_x', 'type': 'BINARY'}, {'id': 'demo_y', 'type': 'BINARY'}]
    if kind == 'threshold':
        actions = [{'id': 'demo_q', 'type': 'CONTINUOUS'}, {'id': 'demo_x', 'type': 'BINARY'}]
    if kind == 'indicator':
        actions.append({'id': 'demo_z', 'type': 'BINARY'})
    variables = [{'id': a['id'], 'type': a['type'], 'lb': 0,
                  'ub': 10 if a['id'] == 'demo_q' else 1} for a in actions]
    ids = [a['id'] for a in actions]
    clauses = [
        {'id': 'T001', 'text': 'Minimize total credits: each listed variable has coefficient 1. '
                              'All lower bounds are 0; binary variables have upper bound 1; '
                              'demo_q, if present, is continuous with upper bound 10.'},
        {'id': 'T002', 'text': 'The listed objects are regulated demonstration facilities. '
                              'Their operating requirements are not supplied.'}]
    if kind == 'exception':
        clauses.append({'id': 'T003', 'text': 'demo_y has a documented maintenance exemption; demo_x does not.'})
    sources = {
        'each': 'Each regulated facility must activate its own safety module. No exemption applies.',
        'unknown': 'Each regulated facility must activate its own safety module, except certified test facilities. '
                   'Whether demo_y is a certified test facility is not documented.',
        'exception': 'Each regulated facility must activate its own safety module, except facilities with a maintenance exemption.',
        'aggregate': 'The facilities must activate at least one module in total. This is a total requirement, not one for each facility.',
        'threshold': 'If throughput demo_q exceeds 4, monitoring module demo_x is required. Throughput above 4 is permitted with monitoring.',
        'indicator': 'If operating switch demo_z equals 1, at least one of demo_x and demo_y must be active. No such duty applies when demo_z equals 0.'}
    source = sources[kind]
    window = 'P001@0-' + str(len(source))
    model = {'variables': variables, 'objective': {'direction': 'min',
             'terms': {a: 1 for a in ids}, 'unit': 'credits', 'citations': refs('T001')},
             'constraints': []}
    plan = {'model': model, 'attribute_checks': [], 'task_map': [
        {'clause_id': c['id'], 'role': 'MODEL' if c['id'] == 'T001' else 'EXTERNAL' if c['id'] == 'T002' else 'CONTEXT',
         'elements': ['objective'] if c['id'] == 'T001' else []} for c in clauses],
        'facts': [{'subject': 'GLOBAL', 'key': 'subject_type', 'value': 'regulated demonstration facility',
                   'citations': refs('T002')}],
        'needs': [{'question': 'Which operating requirements apply to the listed decision objects?',
                   'action_ids': ids, 'anchor_clauses': ['T002'], 'task_supplied': truth('UNKNOWN'),
                   'excluded': truth('UNKNOWN'), 'query': 'regulated facility operating requirements',
                   'search_terms': ['facility', 'operating requirement']}]}
    relation = {'need_id': 'R002', 'relation': plan['needs'][0]['question'],
                'action_ids': ids, 'anchor_clauses': ['T002']}
    def condition(action, exceptions=None):
        return {'action_id': action, 'required': [truth('YES', 'T002')],
                'exceptions': exceptions or [], 'action_matches': truth('YES', window)}
    rule = {'modality': 'MUST', 'kind': 'lower_bound', 'bound': 1, 'citations': refs(window),
            'conditions': [condition('demo_x'), condition('demo_y')],
            'expression_check': truth('YES', window)}
    unresolved = []
    if kind == 'unknown':
        rule['conditions'][1]['exceptions'] = [truth('UNKNOWN')]
        unresolved = ['Whether the object controlled by demo_y is a certified test facility.']
    elif kind == 'exception':
        rule['conditions'][0]['exceptions'] = [truth('NO', 'T003')]
        rule['conditions'][1]['exceptions'] = [truth('YES', 'T003')]
    elif kind == 'aggregate':
        rule.pop('bound')
        rule.update(kind='linear', terms={'demo_x': 1, 'demo_y': 1}, sense='>=', rhs=1,
                    conditions=[condition('GLOBAL')], quantity_basis={
                        'kind': 'TOTAL', 'citations': refs(window),
                        'independent_requirement': truth('YES', window),
                        'decomposition_only': truth('NO', window)})
    elif kind == 'threshold':
        rule.pop('bound')
        rule.update(kind='threshold', quantity='demo_q', required='demo_x', threshold=4,
                    conditions=[condition('GLOBAL')])
    elif kind == 'indicator':
        rule.pop('bound')
        rule.update(kind='indicator', trigger='demo_z', active_value=1,
                    terms={'demo_x': 1, 'demo_y': 1}, sense='>=', rhs=1,
                    conditions=[condition('GLOBAL')])
    public = {'id': 'fictional-format-example', 'prompt': '\n'.join(c['text'] for c in clauses),
              'output_schema': {'actions': actions, 'objective': {'canonical_unit': 'credits'}}}
    inputs = {'task': public['prompt'], 'output_schema': public['output_schema'], 'clauses': clauses,
              'time_policy': 'Use only the supplied facts and rule text.',
              'relation_id': relation['need_id'], 'relation': relation,
              'available_facts': [{'id': 'F001', 'meaning': 'GLOBAL.subject_type',
                                  'value': 'regulated demonstration facility', 'citations': refs('T002')}],
              'model': model, 'model_targets': ['var:' + a for a in ids],
              'reference_documents': [c['id'] for c in clauses] + ['schema', window],
              'sources': [{'document': 'P001', 'url': 'https://example.invalid/fictional-rule',
                           'title': 'Fictional rule', 'full_text_chars': len(source), 'complete': True,
                           'windows': [{'reference': window, 'start': 0, 'end': len(source), 'text': source}]}]}
    return {'input': inputs, 'output': {'fact_refs': ['F001'], 'rules': [rule],
            'task_supplied': truth('NO', 'T002'), 'evidence_supplied': truth('YES', window),
            'excluded': truth('NO', window), 'unresolved_conditions': unresolved},
            'note': 'Only this selected relation is processed. The program owns identifiers, mathematical '
                    'destinations, template compilation and closure; this output does not decide the next step.',
            'setup': {'public': public, 'plan': plan}}


def _aggregate_scope_example(kind):
    """Two existing FUSE uses: register a wider relation, then interpret that relation."""
    def refs(*documents): return [{'document': d} for d in documents]
    def truth(value, *documents): return {'value': value, 'citations': refs(*documents)}
    ids = ['demo_x', 'demo_y', 'demo_p']
    actions = [{'id': a, 'type': 'BINARY', 'meaning': meaning} for a, meaning in zip(ids,
        ['Select the 6-tonne batch x', 'Select the 4-tonne batch y', 'Enable annual handling measure p'])]
    clauses = [
        {'id': 'T001', 'text': 'All decisions are binary. Maximize 3*demo_x + 2*demo_y - demo_p credits.'},
        {'id': 'T002', 'text': 'One warehouse considers only batches x (6 tonnes) and y (4 tonnes) in one year. Operating duties are not supplied.'},
        {'id': 'T003', 'text': 'demo_p enables the handling measure for that warehouse and year. Its duties and emergency-exemption status are not supplied.'}]
    def need(question, targets, anchors):
        return {'question': question, 'action_ids': targets, 'anchor_clauses': anchors,
                'task_supplied': truth('UNKNOWN'), 'excluded': truth('UNKNOWN')}
    plan = {'model': {'variables': [{'id': a, 'type': 'BINARY', 'lb': 0, 'ub': 1} for a in ids],
            'objective': {'direction': 'max', 'terms': dict(zip(ids, [3, 2, -1])),
                          'unit': 'credits', 'citations': refs('T001')}, 'constraints': []},
        'task_map': [{'clause_id': 'T001', 'role': 'MODEL', 'elements': ['objective']},
                     {'clause_id': 'T002', 'role': 'EXTERNAL'}, {'clause_id': 'T003', 'role': 'EXTERNAL'}],
        'facts': [], 'needs': [need('Does x have a separate batch-specific duty?', ['demo_x'], ['T002']),
                               need('Does y have a separate batch-specific duty?', ['demo_y'], ['T002']),
                               need('Does p have a separate licensing duty?', ['demo_p'], ['T003'])],
        'attribute_checks': [{'attribute_id': 'AQ001', 'key': 'mass', 'purpose': 'ATTRIBUTE', 'needs_index': 0},
                             {'attribute_id': 'AQ002', 'key': 'mass', 'purpose': 'ATTRIBUTE', 'needs_index': 1}]}
    public = {'id': 'fictional-aggregate-format', 'prompt': '\n'.join(c['text'] for c in clauses),
              'output_schema': {'actions': actions, 'objective': {'canonical_unit': 'credits'}}}
    bodies = [('P001', 'For this warehouse activity, total annual selected shipment mass is the sum of '
        'each batch mass times its selection. If that total exceeds 6 tonnes, handling measure p is '
        'required. Greater totals are permitted with p. A certified emergency exemption removes '
        'this annual requirement. Separate batch-specific and licensing duties are not addressed.')]
    if kind == 'weighted_indicator':
        bodies.append(('P002', 'The registry confirms this warehouse has no certified emergency exemption.'))
    sources = [{'document': d, 'url': 'https://example.invalid/' + d, 'title': 'Fictional supplied source',
        'full_text_chars': len(text), 'complete': True,
        'windows': [{'reference': f'{d}@0-{len(text)}', 'start': 0, 'end': len(text), 'text': text}]}
        for d, text in bodies]
    window = sources[0]['windows'][0]['reference']
    question = 'Does the combined annual mass of x and y require p, subject to the documented emergency exemption?'
    relation = {'need_id': 'R002', 'relation': plan['needs'][0]['question'], 'action_ids': ['demo_x']}
    output = {'fact_refs': [], 'rules': [], 'task_supplied': truth('NO', 'T002'),
              'evidence_supplied': truth('YES', window), 'excluded': truth('UNKNOWN'),
              'needs': [{'question': question, 'action_ids': ids, 'anchor_clauses': ['T002', 'T003', window],
                         'task_supplied': truth('NO', 'T002', 'T003'), 'excluded': truth('UNKNOWN')}],
              'unresolved_conditions': ['A separate batch-specific duty for x remains unverified.']}
    note = ('The source establishes an independent annual relationship beyond the selected x-only question. '
            'Register it using needs without relation_id, with its actual objects and observed source anchor. '
            'Do not attach wider mathematics to the current relation or change its scope. The program assigns '
            'the new ID and may select it in a later existing FUSE stage. Earlier narrow questions remain open. '
            'A paraphrase or refinement of the current question must retain its existing relation_id.')
    if kind == 'weighted_indicator':
        certificate = sources[1]['windows'][0]['reference']
        relation = {'need_id': 'R005', 'relation': question, 'action_ids': ids}
        output = {'fact_refs': [], 'task_supplied': truth('NO', 'T002', 'T003'),
            'evidence_supplied': truth('YES', window), 'excluded': truth('NO', certificate),
            'rules': [{'modality': 'MUST', 'kind': 'indicator', 'trigger': 'demo_p', 'active_value': 0,
                'terms': {'demo_x': 6, 'demo_y': 4}, 'sense': '<=', 'rhs': 6,
                'citations': refs(window, 'T002'), 'conditions': [{'action_id': 'GLOBAL',
                    'required': [truth('YES', 'T002')], 'exceptions': [truth('NO', certificate)],
                    'action_matches': truth('YES', window, 'T002', 'T003')}],
                'expression_check': truth('YES', window, 'T002')}]}
        note = ('The program has now selected the registered wider relation R005. Weighted sum > 6 requires '
                'p=1 is equivalent to p=0 implying weighted sum <=6. Use indicator with active_value=0; '
                'no separate quantity variable or LLM-chosen big-M is needed. The program derives M from '
                'the existing variable bounds. Equality needs no p, and p=1 allows greater totals. The '
                'NO exception judgment uses the observed registry, never missing evidence. Without that '
                'evidence return UNKNOWN for the exception and excluded; no constraint may activate. '
                'This rule does not certify earlier narrow questions or overall completeness.')
    inputs = {'task': public['prompt'], 'output_schema': public['output_schema'], 'clauses': clauses,
              'relation_id': relation['need_id'], 'relation': relation, 'available_facts': [],
              'model': plan['model'], 'model_targets': ['var:' + a for a in ids], 'sources': sources,
              'reference_documents': [c['id'] for c in clauses] + ['schema'] +
                  [s['windows'][0]['reference'] for s in sources],
              'time_policy': 'Only the supplied fictional facts and sources apply.'}
    return {'input': inputs, 'output': output, 'note': note, 'setup': {'public': public, 'plan': plan}}


def _shared_scope_example():
    """Shared exception scope does not turn an unknown exemption into a fact."""
    data = _rule_example('each')
    inputs, output, setup = data['input'], data['output'], data['setup']
    def refs(document): return [{'document': document}]
    def truth(value, document=None):
        return {'value': value, 'citations': refs(document) if document else []}
    inputs['clauses'][1]['text'] = ('Inspection and repair are planned at the same warehouse. '
        'Its emergency-exemption status and permit duties are not supplied.')
    setup['public']['prompt'] = '\n'.join(c['text'] for c in inputs['clauses'])
    inputs['task'] = setup['public']['prompt']
    for action, meaning in zip(inputs['output_schema']['actions'],
            ['Obtain an inspection permit', 'Obtain a repair permit']):
        action['meaning'] = meaning
    setup['plan']['facts'][0]['value'] = 'warehouse'
    inputs['available_facts'][0]['value'] = 'warehouse'
    parent_question = 'Does the facility emergency exemption apply to this warehouse?'
    child_question = 'Do the planned inspection and repair operations require maintenance permits?'
    parent = setup['plan']['needs'][0]
    parent.update(question=parent_question, query='warehouse emergency exemption maintenance permits',
                  search_terms=['warehouse', 'emergency exemption', 'maintenance permits'])
    child = json.loads(json.dumps(parent))
    child['question'] = child_question
    setup['plan']['needs'].append(child)
    inputs['relation_id'] = 'R003'
    inputs['relation'] = {'need_id': 'R003', 'relation': child_question,
                          'action_ids': ['demo_x', 'demo_y'], 'anchor_clauses': ['T002']}
    source = ('Warehouse inspection and repair operations each require a maintenance permit. '
              'The same facility emergency exemption applies to both permit duties. '
              'Whether this warehouse qualifies for that exemption is not established by this excerpt.')
    window = 'P001@0-' + str(len(source))
    inputs['reference_documents'] = ['T001', 'T002', 'schema', window]
    inputs['sources'] = [{'document': 'P001', 'url': 'https://example.invalid/warehouse-permits',
        'title': 'Fictional warehouse permit rule', 'full_text_chars': len(source), 'complete': True,
        'windows': [{'reference': window, 'start': 0, 'end': len(source), 'text': source}]}]
    unresolved = ['Whether this warehouse qualifies for the facility emergency exemption.']
    inputs['related_scope_context'] = [{'relation_id': 'R002', 'relation': parent_question,
        'action_ids': ['demo_x', 'demo_y'], 'excluded': truth('UNKNOWN', window),
        'unresolved_conditions': unresolved}]
    setup['relation_updates'] = [{'need_id': 'R002', 'excluded': truth('UNKNOWN', window),
                                  'unresolved_conditions': unresolved}]
    rule = output['rules'][0]
    rule['citations'] = refs(window)
    rule['expression_check'] = truth('YES', window)
    for condition in rule['conditions']:
        condition['action_matches'] = truth('YES', window)
    rule['scope_checks'] = [{'relation_id': 'R002',
                            'shared_exception_scope': truth('YES', window)}]
    output['evidence_supplied'] = truth('YES', window)
    output['excluded'] = truth('UNKNOWN', window)
    data['note'] = ('Only the supplied R002 may be referenced by scope_checks. YES states that '
        'the cited exception has the same applicability scope; it does not say the warehouse '
        'qualifies. The program retrieves R002.excluded=UNKNOWN and blocks both permit bounds. '
        'The exemption and child relation remain unresolved, with no mathematical effect. '
        'Do not infer shared scope merely from two operations using the same warehouse. '
        'Return NO when source evidence establishes different scopes, or UNKNOWN when it '
        'does not establish the scope relationship. The program owns IDs and compilation.')
    return data


def _quantity_example(unknown=False):
    """A total minimum and a subtype minimum do not impose a remainder minimum."""
    def refs(document): return [{'document': document}]
    def truth(value, document=None):
        return {'value': value, 'citations': refs(document) if document else []}
    actions = [{'id': 'demo_ordinary', 'type': 'INTEGER', 'meaning': 'Number of ordinary modules'},
               {'id': 'demo_special', 'type': 'INTEGER', 'meaning': 'Number of special modules'}]
    clauses = [{'id': 'T001', 'text': 'Choose ordinary and special module counts, each integer from 0 to 10. Minimize their total cost, one credit per module.'},
               {'id': 'T002', 'text': 'The device is a Demo_F facility. Its module requirement is not supplied.'}]
    public = {'id': 'fictional-total-and-component-format', 'prompt': '\n'.join(c['text'] for c in clauses),
              'output_schema': {'actions': actions, 'objective': {'canonical_unit': 'credits'}}}
    model = {'variables': [{'id': a['id'], 'type': 'INTEGER', 'lb': 0, 'ub': 10} for a in actions],
             'objective': {'direction': 'min', 'terms': {a['id']: 1 for a in actions},
                           'unit': 'credits', 'citations': refs('T001')}, 'constraints': []}
    plan = {'model': model, 'attribute_checks': [],
            'task_map': [{'clause_id': 'T001', 'role': 'MODEL', 'elements': ['objective']},
                         {'clause_id': 'T002', 'role': 'EXTERNAL', 'elements': []}],
            'facts': [{'subject': 'GLOBAL', 'key': 'subject_type', 'value': 'Demo_F', 'citations': refs('T002')}],
            'needs': [{'question': 'Does the device need a standalone minimum number of ordinary modules?',
                       'action_ids': [a['id'] for a in actions], 'anchor_clauses': ['T002'],
                       'task_supplied': truth('UNKNOWN'), 'excluded': truth('UNKNOWN'),
                       'query': 'facility module count requirements', 'search_terms': ['facility', 'module count']}]}
    source = ('Each Demo_F facility must have at least 5 modules in total, including at least 2 special modules. '
              'Special modules count toward the total. There is no separate minimum for ordinary modules. '
              'Three ordinary plus two special is an example allocation, not an ordinary-module minimum. '
              'Two ordinary plus three special also satisfies both requirements.')
    if unknown:
        source = ('Each Demo_F facility must have at least 5 qualifying modules. This excerpt does '
                  'not define which module categories qualify or whether special modules are included.')
    window = 'P001@0-' + str(len(source))
    def rule(kind, terms, rhs):
        basis = {'kind': kind, 'citations': refs(window),
                 'independent_requirement': truth('YES', window), 'decomposition_only': truth('NO', window)}
        if kind == 'COMPONENT':
            basis['component_counts_toward_total'] = truth('YES', window)
        return {'modality': 'NUMERIC', 'kind': 'linear', 'terms': terms, 'sense': '>=', 'rhs': rhs,
                'citations': refs(window), 'quantity_basis': basis,
                'conditions': [{'action_id': 'GLOBAL', 'required': [truth('YES', 'T002')],
                                'exceptions': [], 'action_matches': truth('YES', window)}],
                'expression_check': truth('YES', window)}
    inputs = {'task': public['prompt'], 'output_schema': public['output_schema'], 'clauses': clauses,
              'time_policy': 'Use the supplied facts and observed requirement text.',
              'relation_id': 'R002', 'relation': {'need_id': 'R002', 'relation': plan['needs'][0]['question'],
                                                'action_ids': [a['id'] for a in actions]},
              'available_facts': [{'id': 'F001', 'meaning': 'GLOBAL.subject_type', 'value': 'Demo_F', 'citations': refs('T002')}],
              'model': model, 'model_targets': ['var:' + a['id'] for a in actions],
              'reference_documents': ['T001', 'T002', 'schema', window],
              'sources': [{'document': 'P001', 'url': 'https://example.invalid/module-requirement',
                           'title': 'Fictional module rule', 'full_text_chars': len(source), 'complete': True,
                           'windows': [{'reference': window, 'start': 0, 'end': len(source), 'text': source}]}]}
    rules = [rule('TOTAL', {'demo_ordinary': 1, 'demo_special': 1}, 5),
             rule('COMPONENT', {'demo_ordinary': 0, 'demo_special': 1}, 2)]
    unresolved = []
    if unknown:
        rules = rules[:1]
        rules[0]['quantity_basis'] = {'kind': 'UNKNOWN', 'citations': [],
                                     'independent_requirement': truth('UNKNOWN'),
                                     'decomposition_only': truth('UNKNOWN')}
        rules[0]['expression_check'] = truth('UNKNOWN')
        unresolved = ['Which observed module categories are included in the qualifying quantity?']
    return {'input': inputs, 'output': {'fact_refs': ['F001'], 'rules': rules,
                'task_supplied': truth('NO', 'T002'), 'evidence_supplied': truth('YES', window),
                'excluded': truth('NO', window), 'unresolved_conditions': unresolved},
            'note': ('The source does not identify the qualifying categories. The proposed quantity '
                    'cannot be certified; UNKNOWN blocks its mathematical effect and preserves the '
                    'concrete missing definition for later interpretation. No field is guessed.' if unknown else
                    'The PLAN question is a hypothesis, not evidence for an ordinary-module minimum. '
                    'The observed source instead requires total >= 5 and special >= 2. '
                    'Ordinary=2 and special=3 remains feasible. Do not generate ordinary >= 3 '
                    'by subtraction or turn the source allocation example into an independent rule. '
                    'Classification and predicates must cite the actual source, not the PLAN question.') +
                    ' Other relationship types: a weighted sum > L requiring binary p=1 can use '
                    'indicator(trigger=p, active_value=0, terms={x_i:w_i}, sense=<=, rhs=L); no '
                    'standalone quantity variable is required. If observed text establishes an independent '
                    'aggregate outside the current objects, register source-backed needs without relation_id '
                    'and let the program select that new relation in a later FUSE. Do not write an '
                    'out-of-scope rule now, close earlier narrow questions, or treat an unknown exception as NO. '
                    'A refinement of the same question retains its existing relation_id.',
            'setup': {'public': public, 'plan': plan}}


def _given_confirmation_example():
    """Already encoded task rule: verify it locally without inventing external evidence."""
    refs=[{'document':'T002'}]
    unknown={'value':'UNKNOWN','citations':[]}
    clauses=[{'id':'T001','text':'Choose exactly one device. Minimize cost: demo_x costs 2 credits and demo_y costs 3 credits.'},
             {'id':'T002','text':'The chosen device must provide at least 4 sensors.'}]
    actions=[{'id':'demo_x','type':'BINARY','meaning':'Choose a device containing 3 sensors'},
             {'id':'demo_y','type':'BINARY','meaning':'Choose a device containing 5 sensors'}]
    public={'id':'fictional-existing-constraint','prompt':'\n'.join(c['text'] for c in clauses),
            'output_schema':{'actions':actions,'objective':{'canonical_unit':'credits'}}}
    model={'variables':[{'id':a['id'],'type':'BINARY','lb':0,'ub':1} for a in actions],
           'objective':{'direction':'min','terms':{'demo_x':2,'demo_y':3},'unit':'credits','citations':[{'document':'T001'}]},
           'constraints':[{'terms':{'demo_x':1,'demo_y':1},'sense':'==','rhs':1,'citations':[{'document':'T001'}]},
                          {'terms':{'demo_x':3,'demo_y':5},'sense':'>=','rhs':4,'citations':refs}]}
    plan={'model':model,'facts':[],'needs':[],
          'task_map':[{'clause_id':'T001','role':'MODEL','elements':['objective']},
                      {'clause_id':'T002','role':'MODEL','elements':[]}],
          'attribute_checks':[{'attribute_id':f'AQ{i:03}','key':'sensor_count','purpose':'ATTRIBUTE',
                              'constraint_indices':[1],'citations':refs} for i in (1,2)]}
    accepted=json.loads(json.dumps(model))
    for i,c in enumerate(accepted['constraints'],1): c['name']=f'C{i:03}'
    relation={'need_id':'R004','relation':'Confirm existing sensor-count constraint C002.',
              'action_ids':['demo_x','demo_y'],'route':'GIVEN','anchor_clauses':['T002'],
              'model_locations':['constraint:C002'],'confirmation_locations':['constraint:C002']}
    return {'input':{'task':public['prompt'],'clauses':clauses,'output_schema':public['output_schema'],
                     'reference_documents':['T001','T002','schema'],'relation_id':'R004','relation':relation,
                     'available_facts':[],'model':accepted,'model_targets':['var:demo_x','var:demo_y'],
                     'sources':[],'time_policy':'Use the supplied task rule.'},
            'output':{'fact_refs':[],'rules':[],'task_supplied':{'value':'YES','citations':refs},
                      'evidence_supplied':unknown,'excluded':unknown,
                      'expression_check':{'value':'YES','citations':refs+[{'document':'schema'}]},
                      'unresolved_conditions':[]},
            'note':'The existing expression 3*demo_x+5*demo_y>=4 uses the two action properties and the task threshold. '
                   'Its program-bound location is retained. No new rule, fact or external evidence is created. '
                   'If quantity, comparator or threshold disagrees, return expression_check NO and explain the local '
                   'mismatch in unresolved_conditions; missing interpretation returns UNKNOWN. Neither closes the relation.',
            'setup':{'public':public,'plan':plan}}


def example_data(stage, rule_kind=None):
    """Return fresh data so examples can also be checked against the real schemas."""
    if stage == 'FUSE' and rule_kind is not None:
        if rule_kind == 'given_confirmation':
            return _given_confirmation_example()
        if rule_kind == 'shared_scope':
            return _shared_scope_example()
        if rule_kind in {'aggregate_need', 'weighted_indicator'}:
            return _aggregate_scope_example(rule_kind)
        if rule_kind in {'quantity_total', 'quantity_unknown'}:
            return _quantity_example(unknown=rule_kind == 'quantity_unknown')
        return _rule_example(rule_kind)
    def refs(document):
        return [{'document': document}]

    def truth(value, document=None):
        return {'value': value, 'citations': refs(document) if document else []}

    clauses = [
        {'id': 'T001', 'text': 'Choose binary demo_x at cost 2 credits. Minimize cost, with demo_x >= 0.'},
        {'id': 'T002', 'text': 'The facility type is Demo_F. Its activation requirement is not supplied.'}]
    public = {'id': 'fictional-format-example', 'prompt': '\n'.join(c['text'] for c in clauses),
              'output_schema': {'actions': [{'id': 'demo_x', 'type': 'BINARY',
                                            'meaning': 'Activate a device containing 3 safety modules'}],
                                'objective': {'canonical_unit': 'credits'}}}
    inputs = {'task': public['prompt'], 'output_schema': public['output_schema'], 'clauses': clauses,
              'source_attributes': source_attributes(public),
              'reference_documents': ['T001', 'T002', 'schema'],
              'time_policy': 'Use stated scenario facts. A missing relation remains unknown until supported.'}
    plan = {
        'model': {
            'variables': [{'id': 'demo_x', 'type': 'BINARY', 'lb': 0, 'ub': 1}],
            'objective': {'direction': 'min', 'terms': {'demo_x': 2}, 'unit': 'credits', 'citations': refs('T001')},
            'constraints': [{'terms': {'demo_x': 1}, 'sense': '>=', 'rhs': 0, 'citations': refs('T001')}]},
        'task_map': [
            {'clause_id': 'T001', 'role': 'MODEL', 'elements': ['var:demo_x', 'objective']},
            {'clause_id': 'T002', 'role': 'EXTERNAL', 'elements': []}],
        'facts': [{'subject': 'GLOBAL', 'key': 'subject_type', 'value': 'Demo_F', 'citations': refs('T002')}],
        'attribute_checks': [{'attribute_id': 'AQ001', 'key': 'safety_module_count',
                              'purpose': 'ATTRIBUTE', 'needs_index': 0}],
        'needs': [{'question': 'Is activation of demo_x required for Demo_F facilities?',
                   'action_ids': ['demo_x'], 'anchor_clauses': ['T002'],
                   'task_supplied': truth('UNKNOWN'), 'excluded': truth('UNKNOWN'),
                   'query': 'facility activation requirements',
                   'search_terms': ['facility', 'activation requirement'],
                   'alternative_queries': ['facility activation requirement official policy']}]}
    if stage == 'PLAN_LOCAL_NEEDS':
        return {'input': {'missing_clause_destinations': [
                    {'clause_id': 'T002', 'text': clauses[1]['text']}],
                    'output_schema': public['output_schema'], 'existing_facts': plan['facts'],
                    'existing_needs': [], 'reference_documents': clauses},
                'output': {'value': plan['needs']},
                'note': 'Append only the omitted relationship. The existing model, facts and '
                        'other needs are unchanged. Bind a supplied missing clause and public action. '
                        'UNKNOWN registers work; it does not assert an obligation or completeness.'}
    if stage == 'PLAN' and rule_kind == 'capability':
        public['output_schema']['actions'][0]['meaning'] = 'Install an archive module'
        inputs['source_attributes'] = source_attributes(public)
        plan['attribute_checks'][0]['key'] = 'archive_capability'
        return {'input': inputs, 'output': plan,
                'note': 'AQ001 copies the supplied capability, not a quantity or a duty. '
                        'It binds to needs[0], whose requirement is still UNKNOWN. '
                        'Do not infer that the module must be selected just because it is available. '
                        'Several capabilities governed by the same requirement may share needs_index. '
                        'Program-owned numbering and model fields follow the actual input schema.'}
    if stage == 'PLAN':
        return {'input': inputs,
                'output': plan,
                'note': 'The known demo_x >= 0 constraint is only in model, never repeated in needs. '
                        'AQ001 is a source number, not a model or fact identifier. The program copies '
                        'its exact value 3 into an action fact and binds it to needs[0]; the binary '
                        'bound alone cannot consume that device property. Attribute IDs must all '
                        'come from input. For a new unresolved relationship, use a nested need with '
                        'question/task_supplied/excluded/search_terms instead of needs_index; '
                        'the program supplies its action and source. For an already encoded '
                        'property relationship, constraint_indices are zero-based positions and '
                        'citations must be the actual constraint sources. OBJECTIVE and CHOICE_LABEL '
                        'are permitted only for an explicitly labelled cost/utility or plan/batch number. '
                        'The program assigns constraint, fact and relation IDs after acceptance.'}
    if stage == 'FUSE':
        source = 'For Demo_F facilities, a device containing safety modules must be activated. No exception applies.'
        window = 'P001@0-' + str(len(source))
        accepted_model = json.loads(json.dumps(plan['model']))
        accepted_model['constraints'][0]['name'] = 'C001'
        return {'input': {**{k: v for k, v in inputs.items() if k != 'source_attributes'},
            'relation_id': 'R003',
            'relation': {'need_id': 'R003', 'relation': plan['needs'][0]['question'], 'action_ids': ['demo_x']},
            'available_facts': [{'id': 'F001', 'meaning': 'GLOBAL.subject_type', 'value': 'Demo_F', 'citations': refs('T002')}],
            'model': accepted_model, 'model_targets': ['var:demo_x', 'objective:demo_x'],
            'sources': [{'document': 'P001', 'url': 'https://example.invalid/fictional-policy',
                         'title': 'Fictional policy', 'full_text_chars': len(source), 'complete': True,
                         'windows': [{'reference': window, 'start': 0, 'end': len(source), 'text': source}]}],
            'reference_documents': ['T001', 'T002', window, 'schema']},
            'output': {
                'fact_refs': ['F001'],
                'rules': [{'modality': 'MUST', 'kind': 'lower_bound', 'bound': 1,
                           'citations': refs(window),
                           'conditions': [{'action_id': 'demo_x',
                                           'required': [truth('YES', 'T002')], 'exceptions': [],
                                           'action_matches': truth('YES', 'schema')}],
                           'expression_check': truth('YES', window)}],
                'task_supplied': truth('NO', 'T002'),
                'evidence_supplied': truth('YES', window), 'excluded': truth('NO', window)},
            'note': 'R003 is already selected by the program and is not repeated in the output. '
                    'F001 is evidence; the mathematical destination is derived from the expression. '
                    'The source supplies the duty; schema supplies which action implements the function. '
                    'The rule does not need to name demo_x. Use the supplied source-window ID so the program restores the exact observed text. '
                    'The program assigns a new rule ID and combines the local predicates. '
                    'Type guide: EACH -> one bound condition per applicable action; aggregate -> linear; '
                    'quantity > L requires action -> threshold, never hard upper_bound; binary switch '
                    'implies comparison -> indicator; weighted sum > L requires p=1 -> '
                    'indicator(trigger=p, active_value=0, weighted terms, sense=<=, rhs=L). '
                    'If an observed independent aggregate spans more objects than the selected relation, '
                    'register source-backed needs without relation_id and wait for the program to select '
                    'it before proposing its mathematics. Do not widen or certify the earlier relation. '
                    'Permission never forces action. UNKNOWN or an '
                    'unverified exception leaves that part unresolved. A supported exception prevents '
                    'the corresponding effect.'}
    if stage.endswith('LOCAL_FIELD') or stage == 'LOCAL_FIELD':
        def field_case(label, field_schema, inputs, value):
            return {'kind': label, 'input': inputs,
                    'output_schema': {'type': 'object', 'properties': {
                        'value': {'anyOf': [field_schema, {'type': 'null'}]}, 'error': {'type': 'string'}},
                        'required': ['value'], 'additionalProperties': False},
                    'output': {'value': value}}
        document = {'type': 'object', 'properties': {'document': {'enum': ['T001']}},
                    'required': ['document'], 'additionalProperties': False}
        relation = {'need_id': 'R003', 'relation': plan['needs'][0]['question'], 'action_ids': ['demo_x']}
        rule = {'modality': 'NUMERIC', 'kind': 'lower_bound', 'bound': 0,
                'citations': refs('T001'), 'conditions': [{'action_id': 'demo_x',
                    'required': [truth('YES', 'T002')], 'exceptions': [],
                    'action_matches': truth('YES', 'T001')}],
                'expression_check': truth('YES', 'T001'), 'model_targets': ['var:demo_x']}
        return {'examples': [
            field_case('citation object', document,
                       {'path': ['citations', 0], 'allowed_references': [clauses[0]],
                        'current_entry': {'terms': {'demo_x': 1}, 'sense': '>=', 'rhs': 0}},
                       {'document': 'T001'}),
            field_case('fact identifier', {'enum': ['F001']},
                       {'path': ['fact_refs', 0], 'current_value': 'R003',
                        'current_entry': {'relation': relation, 'rules': [rule]},
                        'selected_relation': relation, 'available_facts': [{'id': 'F001', 'meaning': 'facility type Demo_F'}]},
                       'F001'),
            field_case('mathematical destination', {'enum': ['var:demo_x']},
                       {'path': ['rules', 0, 'model_targets', 0], 'current_value': 'F001',
                        'current_entry': {**rule, 'model_targets': ['F001']},
                        'model_targets': ['var:demo_x']}, 'var:demo_x')],
            'note': 'Match the actual field schema: a citation is an object, while a single ID is a string. '
                    'These examples have a unique evidenced binding. Otherwise return the complete object '
                    '{"value":null,"error":"No unique supported binding"}. Change only the requested field.'}
    if stage.endswith('LOCAL_JSON') or stage == 'LOCAL_JSON':
        raw = '{"terms":{"demo_x":1},"sense":">=","rhs":0'
        return {'input': {'raw_fragment': raw, 'start': len(raw), 'end': len(raw),
                          'error': 'Missing final object closing brace', 'requested_fragment': ''},
                'output': {'replacement': '}'},
                'output_schema': {'type': 'object', 'properties': {'replacement': {'type': 'string'}},
                                  'required': ['replacement'], 'additionalProperties': False},
                'repaired_schema': {'type': 'object', 'properties': {
                    'terms': {'type': 'object', 'properties': {'demo_x': {'type': 'number'}},
                              'required': ['demo_x'], 'additionalProperties': False},
                    'sense': {'enum': ['>=', '<=', '==']}, 'rhs': {'type': 'number'}},
                    'required': ['terms', 'sense', 'rhs'], 'additionalProperties': False},
                'note': 'Only the missing structural brace is inserted. All strings, numbers, variables '
                        'and mathematical operators are unchanged. Do not regenerate the model.'}
    raise ValueError('No format example for stage: ' + stage)


def _local_example(data, field_kind, field_schema):
    """Select one fictional example and preserve the actual field's container shape."""
    index = {'citation': 0, 'fact': 1, 'target': 2}.get(field_kind)
    if index is None:
        return {'output': {'value': None, 'error': 'No supported field shape in this format example'},
                'note': 'The actual correction schema permits null. Do not infer a value from an unrelated example.'}
    example = data['examples'][index]
    if field_schema is None:
        return {**example, 'note': data['note']}
    schema = field_schema if isinstance(field_schema, dict) else {}
    if 'anyOf' in schema:
        options = [s for s in schema['anyOf'] if s.get('type') != 'null']
        schema = options[0] if len(options) == 1 else {}
    is_array = schema.get('type') == 'array'
    element = schema.get('items', {}) if is_array else schema
    element = element if isinstance(element, dict) else {}
    string_id = element.get('type') in {None, 'string'} and (element.get('type') == 'string' or (bool(element.get('enum')) and all(isinstance(v, str) for v in element['enum'])))
    citation = (element.get('type') == 'object' and 'document' in element.get('properties', {})
                and set(element.get('required', [])) <= {'document'})
    supported = citation if field_kind == 'citation' else string_id
    if is_array and (schema.get('minItems', 0) > 1 or schema.get('maxItems', 1) < 1):
        supported = False
    if not supported:
        return {'output': {'value': None, 'error': 'Unsupported field shape; no value is demonstrated'},
                'note': 'Use the actual field definition. This example deliberately returns null instead of a value of the wrong type.'}
    if is_array:
        example['output']['value'] = [example['output']['value']]
        definition = example['output_schema']['properties']['value']['anyOf'][0]
        example['output_schema']['properties']['value']['anyOf'][0] = {'type': 'array', 'items': definition}
        path = example['input']['path']
        if isinstance(path[-1], int):
            example['input']['path'] = path[:-1]
        if 'current_value' in example['input']:
            example['input']['current_value'] = [example['input']['current_value']]
    return {**example, 'note': data['note'] + ' Container shape matches the requested field; all displayed IDs remain fictional.'}


def example_prompt(stage, field_kind=None, field_schema=None, rule_kind=None):
    data = example_data(stage, rule_kind=rule_kind)
    data.pop('setup', None)
    if stage.endswith('LOCAL_FIELD') and (field_kind is not None or field_schema is not None):
        data = _local_example(data, field_kind, field_schema)
    return ('\nFICTITIOUS FORMAT EXAMPLE ONLY. The IDs, facts, numbers and units below are examples, '
            'not evidence for the actual request; never copy them into the actual response. '
            'Use only IDs supplied by the actual input. The program assigns new IDs and restores '
            'original quotations from selected source IDs. Follow the actual output schema.\n'
            + json.dumps(data, ensure_ascii=False, separators=(',', ':')))
