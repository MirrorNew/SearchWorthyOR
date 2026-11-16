const fs = require('fs');
const path = require('path');
const root = process.cwd();
const readJson = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const readJsonl = p => fs.readFileSync(path.join(root, p), 'utf8').trim().split(/\r?\n/).filter(Boolean).map(s=>JSON.parse(s));
const bad = readJson('analysis/rebuttal_dqz1_evidence_20261114/model_badcases.json');
const tasks = new Map(readJsonl('datasets/SearchWorthyOR-v1.6.3/public/tasks_zh.jsonl').map(x=>[x.id,x]));
const cases = new Map(readJsonl('datasets/SearchWorthyOR-v1.6.3/public/cases_zh.jsonl').map(x=>[x.eval_id,x]));
const gold = new Map(readJsonl('datasets/SearchWorthyOR-v1.6.3/private/gold.jsonl').map(x=>[x.id,x]));
const modelRecords = new Map(readJsonl('analysis/rebuttal_dqz1_evidence_20261114/model_full_equivalence_records.jsonl')
  .filter(x=>x.method==='SWAgent-online')
  .map(x=>[`${x.source_task_id}|${x.run_id}`,x]));
const picks = bad.filter(r=>r.method==='SWAgent-online' && r.answer_correct_existing===true && r.full_model_status==='FAIL');
function modelOf(obj, kind){
  if(kind==='ref') return obj;
  return obj.model;
}
function varsOf(m,kind){ return m.variables.map(v=>({id:kind==='ref'?v.name:v.id,lb:Number(v.lb??0),ub:Number(v.ub??1),type:v.type})); }
function objectiveOf(m,kind){
  const o=m.objective;
  return {sense:kind==='ref'?String(o.sense).toLowerCase():String(o.direction).toLowerCase(),constant:Number(o.constant??0),terms:kind==='ref'?(o.coefficients||{}):(o.terms||{}),unit:o.unit||''};
}
function constraintsOf(m,kind){
  return (m.constraints||[]).map(c=>({terms:kind==='ref'?(c.coefficients||{}):(c.terms||{}),sense:String(c.sense),rhs:Number(c.rhs),when:c.when||null,name:c.name||''}));
}
function satConstraint(c,a){
  if(c.when){ if(a[c.when.variable]!==Number(c.when.equals)) return true; }
  let lhs=0; for(const [v,k] of Object.entries(c.terms)) lhs+=Number(k)*a[v];
  const eps=1e-9;
  if(c.sense==='='||c.sense==='==') return Math.abs(lhs-c.rhs)<=eps;
  if(c.sense==='<='||c.sense==='≤') return lhs<=c.rhs+eps;
  if(c.sense==='>='||c.sense==='≥') return lhs>=c.rhs-eps;
  throw new Error('Unsupported sense '+c.sense+' '+c.name);
}
function enumerate(m,kind,actionIds,publicToPrivate={}){
  const vars=varsOf(m,kind), obj=objectiveOf(m,kind), cons=constraintsOf(m,kind);
  const publicIds=actionIds;
  const projected=new Map(); let feasibleAssignments=0;
  const a={};
  function rec(i){
    if(i===vars.length){
      if(!cons.every(c=>satConstraint(c,a))) return;
      feasibleAssignments++;
      let val=obj.constant; for(const [v,k] of Object.entries(obj.terms)) val+=Number(k)*a[v];
      const key=publicIds.map(pub=>{const variable=kind==='ref'?(publicToPrivate[pub]||pub):pub; return a[variable]??0;}).join(',');
      const old=projected.get(key);
      if(old===undefined || (obj.sense.startsWith('max')?val>old:val<old)) projected.set(key,val);
      return;
    }
    const v=vars[i];
    if(!Number.isInteger(v.lb)||!Number.isInteger(v.ub)||v.ub-v.lb>64) throw new Error('Unsupported var '+v.id+' bounds '+v.lb+','+v.ub);
    for(let x=v.lb;x<=v.ub;x++){a[v.id]=x;rec(i+1);}
    delete a[v.id];
  }
  rec(0);
  if(!projected.size) return {projected, feasibleAssignments, opt:null, optActions:[], obj};
  const vals=[...projected.values()]; const opt=obj.sense.startsWith('max')?Math.max(...vals):Math.min(...vals);
  const optActions=[...projected.entries()].filter(([,v])=>Math.abs(v-opt)<=1e-9).map(([k])=>k).sort();
  return {projected,feasibleAssignments,opt,optActions,obj};
}
function initialPayload(p){
  const saved=readJson(p);
  for(const message of (saved.messages||[])){
    if(message.role!=='user') continue;
    try{const data=JSON.parse(message.content||''); if(data&&data.model) return data;}catch{}
  }
  return null;
}
function counterfactualReference(source,ref,mapping){
  const cf=JSON.parse(JSON.stringify(ref));
  const priv=actionId=>mapping[actionId];
  if(source==='SWOR-R090'){
    cf.constraints.push({name:'semantic_case_removed_hcp_session',sense:'=',rhs:0,coefficients:{[priv('swor_r090_a08')]:1}});
    cf.constraints.push({name:'semantic_case_removed_stock_session',sense:'=',rhs:0,coefficients:{[priv('swor_r090_a09')]:1}});
  }
  if(source==='SWOR-R055'){
    cf.constraints.push({name:'semantic_case_sealed_cannot_be_inspected',sense:'<=',rhs:1,coefficients:{
      [priv('swor_r055_a03')]:1,[priv('swor_r055_a06')]:1,[priv('swor_r055_a07')]:1,[priv('swor_r055_a08')]:1
    }});
  }
  if(source==='SWOR-R023'){
    cf.constraints.push({name:'semantic_case_a_must_be_processed_today',sense:'=',rhs:1,coefficients:{[priv('swor_r023_a01')]:1}});
  }
  return cf;
}
const rows=[];
for(const r of picks){
  const ref=readJson(`datasets/SearchWorthyOR-v1.6.3/models/${r.source_task_id}/full_ir.json`);
  const task=tasks.get(r.source_task_id); if(!task) throw new Error('task missing '+r.source_task_id);
  const mapping=gold.get(r.source_task_id)?.public_to_private_action_map||{};
  const actionIds=Object.keys(mapping).sort();
  if(actionIds.length!==(task.output_schema.actions||[]).length) throw new Error('public map/task action count mismatch '+r.source_task_id);
  const actionMeaning=Object.fromEntries((task.output_schema.actions||[]).map(a=>[a.id,a.meaning]));
  const decodeAction=key=>Object.fromEntries(key.split(',').map((v,i)=>[actionIds[i],Number(v)]));
  const selectedMeanings=key=>{const values=decodeAction(key); return Object.keys(values).filter(id=>values[id]!==0).map(id=>({id,meaning:actionMeaning[id],value:values[id]}));};
  const genWrap=readJson(r.model_file); const gen=modelOf(genWrap,'gen');
  const re=enumerate(ref,'ref',actionIds,mapping), ge=enumerate(gen,'gen',actionIds,mapping);
  const cfModel=counterfactualReference(r.source_task_id,ref,mapping);
  const cfe=enumerate(cfModel,'ref',actionIds,mapping);
  const sourceRecord=modelRecords.get(`${r.source_task_id}|${r.run_id}`);
  const initial=sourceRecord?.initial_model_file?initialPayload(sourceRecord.initial_model_file):null;
  if(!initial?.model) throw new Error(`initial model unavailable ${r.source_task_id} run ${r.run_id}`);
  const ie=enumerate(initial.model,'gen',actionIds,mapping);
  const refSet=new Set(re.projected.keys()), genSet=new Set(ge.projected.keys());
  const cfSet=new Set(cfe.projected.keys());
  const initialSet=new Set(ie.projected.keys());
  const missing=[...refSet].filter(x=>!genSet.has(x)).sort(), extra=[...genSet].filter(x=>!refSet.has(x)).sort();
  const initialMissing=[...refSet].filter(x=>!initialSet.has(x)).sort(), initialExtra=[...initialSet].filter(x=>!refSet.has(x)).sort();
  const removedByUpdate=[...initialSet].filter(x=>!genSet.has(x)).sort(), addedByUpdate=[...genSet].filter(x=>!initialSet.has(x)).sort();
  const refOptSet=new Set(re.optActions), genOptSet=new Set(ge.optActions);
  const initialOptSet=new Set(ie.optActions);
  const shared=[...refSet].filter(x=>genSet.has(x));
  const sharedObjectiveEqual=shared.every(k=>Math.abs(re.projected.get(k)-ge.projected.get(k))<=1e-7);
  const refCoefficients=Object.fromEntries(actionIds.map(pub=>[pub,Number(re.obj.terms[mapping[pub]]??0)]));
  const genCoefficients=Object.fromEntries(actionIds.map(pub=>[pub,Number(ge.obj.terms[pub]??0)]));
  const objectiveCoefficientsEqual=actionIds.every(pub=>Math.abs(refCoefficients[pub]-genCoefficients[pub])<=1e-12) && Math.abs(re.obj.constant-ge.obj.constant)<=1e-12;
  const refOptMissing=[...refOptSet].filter(x=>!genOptSet.has(x));
  const genOptExtra=[...genOptSet].filter(x=>!refOptSet.has(x));
  const initialOptMissing=[...refOptSet].filter(x=>!initialOptSet.has(x));
  const initialOptExtra=[...initialOptSet].filter(x=>!refOptSet.has(x));
  const c=cases.get(r.eval_id);
  rows.push({
    source_task_id:r.source_task_id,eval_id:r.eval_id,run_id:r.run_id,answer_correct_existing:r.answer_correct_existing,
    initial_full_model_status:initialMissing.length===0&&initialExtra.length===0?'PASS':'FAIL',
    initial_feasible_actions:initialSet.size,initial_missing_reference_actions:initialMissing.length,initial_extra_generated_actions:initialExtra.length,
    initial_optimum:ie.opt,initial_optimum_value_equal:ie.opt!==null&&Math.abs(re.opt-ie.opt)<=1e-9,
    initial_same_optimal_action_set:initialOptMissing.length===0&&initialOptExtra.length===0,
    update_removed_from_initial:removedByUpdate.length,update_added_from_initial:addedByUpdate.length,
    initial_model_file:sourceRecord.initial_model_file,initial_model_sha256:sourceRecord.initial_model_sha256,
    initial_request_contains_external_sources:sourceRecord.initial_request_contains_external_sources,
    accepted_nonempty_patch_events:Number(sourceRecord.accepted_nonempty_patch_events||0),accepted_patch_operations:Number(sourceRecord.accepted_patch_operations||0),
    counterfactual_added_constraints:cfModel.constraints.length-ref.constraints.length,
    counterfactual_feasible_actions:cfe.projected.size,
    counterfactual_missing_from_generated:[...cfSet].filter(x=>!genSet.has(x)).length,
    counterfactual_extra_in_generated:[...genSet].filter(x=>!cfSet.has(x)).length,
    counterfactual_optimum:cfe.opt,
    counterfactual_same_optimal_action_set:cfe.opt!==null&&ge.opt!==null&&Math.abs(cfe.opt-ge.opt)<=1e-9&&cfe.optActions.length===ge.optActions.length&&cfe.optActions.every((x,i)=>x===ge.optActions[i]),
    ref_feasible_actions:refSet.size,gen_feasible_actions:genSet.size,missing_reference_actions:missing.length,extra_generated_actions:extra.length,
    ref_optimum:re.opt,gen_optimum:ge.opt,optimum_value_equal:re.opt!==null&&ge.opt!==null&&Math.abs(re.opt-ge.opt)<=1e-9,
    ref_optimal_action_count:re.optActions.length,gen_optimal_action_count:ge.optActions.length,
    objective_coefficients_equal:objectiveCoefficientsEqual,shared_objective_equal:sharedObjectiveEqual,
    same_optimal_action_set:refOptMissing.length===0&&genOptExtra.length===0,
    all_reference_optima_preserved:refOptMissing.length===0,generated_optima_outside_reference:genOptExtra.length,
    ref_optimal_actions:re.optActions,gen_optimal_actions:ge.optActions,missing_reference_optima:refOptMissing,generated_extra_optima:genOptExtra,
    example_missing_action:missing[0]||null,example_extra_action:extra[0]||null,
    example_missing_reference_action_values:missing[0]?decodeAction(missing[0]):null,
    example_missing_reference_selected_meanings:missing[0]?selectedMeanings(missing[0]):null,
    example_missing_reference_objective:missing[0]?re.projected.get(missing[0]):null,
    example_extra_generated_action_values:extra[0]?decodeAction(extra[0]):null,
    example_extra_generated_selected_meanings:extra[0]?selectedMeanings(extra[0]):null,
    example_extra_generated_objective:extra[0]?ge.projected.get(extra[0]):null,
    missing_reference_examples:missing.slice(0,10).map(key=>({values:decodeAction(key),selected_meanings:selectedMeanings(key),objective:re.projected.get(key)})),
    extra_generated_examples:extra.slice(0,10).map(key=>({values:decodeAction(key),selected_meanings:selectedMeanings(key),objective:ge.projected.get(key)})),
    reference_optimal_selected_meanings:re.optActions.map(selectedMeanings),
    ref_unit:re.obj.unit,gen_unit:ge.obj.unit,ref_sense:re.obj.sense,gen_sense:ge.obj.sense,
    case_facts_zh:c?.case_facts_zh||null,rule_information_zh:c?.rule_information_zh||null,
    task_problem_zh:task.problem_zh,task_problem_eval_zh:c?.problem_zh||null,
    model_file:r.model_file,model_sha256:r.model_sha256,reference_file:r.reference_file,reference_sha256:r.reference_sha256,
    original_checker_missing:r.reference_feasible_missing_from_generated,original_checker_extra:r.generated_extra_feasible,original_checker_direction_equal:r.direction_equal,original_checker_unit_equal:r.unit_equal,original_checker_objective_equal:r.objective_equal_on_shared_feasible_actions
  });
}
const out='rebuttal/20261116/full_model_audit/semantic_optima_recompute.json';
fs.writeFileSync(path.join(root,out),JSON.stringify({scope:'All 33 SWAgent-online C2 runs with correct existing answer label and full_model_status FAIL; direct finite enumeration of persisted reference and generated models; no source changes.',count:rows.length,rows},null,2)+'\n','utf8');
const summary={count:rows.length,unique_sources:new Set(rows.map(r=>r.source_task_id)).size,optimum_value_preserved:rows.filter(r=>r.optimum_value_equal).length,all_reference_optima_preserved:rows.filter(r=>r.all_reference_optima_preserved).length,same_optimal_action_set:rows.filter(r=>r.same_optimal_action_set).length,objective_coefficients_equal:rows.filter(r=>r.objective_coefficients_equal).length,shared_objective_equal:rows.filter(r=>r.shared_objective_equal).length,checker_count_matches:rows.filter(r=>r.missing_reference_actions===r.original_checker_missing&&r.extra_generated_actions===r.original_checker_extra).length,checker_objective_all_equal:rows.filter(r=>r.original_checker_objective_equal&&r.original_checker_direction_equal&&r.original_checker_unit_equal).length,generated_optimum_better_than_reference:rows.filter(r=>r.gen_optimum>r.ref_optimum+1e-9).length,generated_optimum_worse_than_reference:rows.filter(r=>r.gen_optimum<r.ref_optimum-1e-9).length,source_changes:[],counterfactuals:[]};
for(const id of [...new Set(rows.map(r=>r.source_task_id))]){const rs=rows.filter(r=>r.source_task_id===id);summary.source_changes.push({source_task_id:id,runs:rs.map(r=>r.run_id),initial_full_model_statuses:[...new Set(rs.map(r=>r.initial_full_model_status))],initial_to_final_only_removes_actions:rs.every(r=>r.update_added_from_initial===0),initial_to_final_unchanged:rs.every(r=>r.update_added_from_initial===0&&r.update_removed_from_initial===0),optimum_value_preserved:rs.every(r=>r.optimum_value_equal),same_optimal_action_set:rs.every(r=>r.same_optimal_action_set),first:{ref:rs[0].ref_optimum,gen:rs[0].gen_optimum,ref_optimal_action_count:rs[0].ref_optimal_action_count,gen_optimal_action_count:rs[0].gen_optimal_action_count,initial_missing:rs[0].initial_missing_reference_actions,initial_extra:rs[0].initial_extra_generated_actions,final_missing:rs[0].missing_reference_actions,final_extra:rs[0].extra_generated_actions,removed_by_update:rs[0].update_removed_from_initial,added_by_update:rs[0].update_added_from_initial}})}
for(const id of ['SWOR-R023','SWOR-R055','SWOR-R090']){const rs=rows.filter(r=>r.source_task_id===id);summary.counterfactuals.push({source_task_id:id,runs:rs.map(r=>r.run_id),all_runs_exact_projected_feasible_set_match:rs.every(r=>r.counterfactual_missing_from_generated===0&&r.counterfactual_extra_in_generated===0),all_runs_optimum_and_argmax_match:rs.every(r=>r.counterfactual_same_optimal_action_set),per_run:rs.map(r=>({run_id:r.run_id,reference_feasible:r.ref_feasible_actions,counterfactual_feasible:r.counterfactual_feasible_actions,generated_feasible:r.gen_feasible_actions,cf_missing:r.counterfactual_missing_from_generated,cf_extra:r.counterfactual_extra_in_generated,cf_optimum:r.counterfactual_optimum,generated_optimum:r.gen_optimum}))})}
fs.writeFileSync(path.join(root,'rebuttal/20261116/full_model_audit/semantic_optima_summary.json'),JSON.stringify(summary,null,2)+'\n','utf8');
console.log(JSON.stringify(summary,null,2));




