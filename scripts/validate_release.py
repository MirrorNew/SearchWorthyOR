"""Offline source/data validation using only the Python standard library."""
from pathlib import Path
import ast
from collections import Counter
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main():
    manifest = json.loads((ROOT / 'release_manifest.json').read_text(encoding='utf-8'))
    errors = []
    def check(ok, msg):
        if not ok:
            errors.append(msg)
    for rel, expected in manifest['files'].items():
        p = ROOT / rel
        check(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == expected, 'Source hash mismatch: ' + rel)
    dataset = ROOT / 'datasets/SearchWorthyOR-v1.6.2'
    public = rows(dataset / 'public/cases_zh.jsonl')
    tasks = rows(dataset / 'public/tasks_zh.jsonl')
    gold = rows(dataset / 'private/case_gold.jsonl')
    identities = rows(dataset / 'private/eval_identity_map.jsonl')
    ids = {r['eval_id'] for r in public}
    check(len(public) == len(gold) == len(identities) == len(ids) == 360, 'Expected 360 unique cases')
    check(len(tasks) == len({r['source_task_id'] for r in identities}) == 120, 'Expected 120 source tasks')
    check(ids == {r['eval_id'] for r in gold} == {r['eval_id'] for r in identities}, 'Public/Gold identity mismatch')
    check(Counter(r['case_role'] for r in identities) == {'C1': 120, 'C2': 120, 'C3': 120}, 'Condition counts differ')
    for r in public:
        check(not {'case_role', 'source_task_id', 'gold', 'final_solution'} & r.keys(), 'Private field in public case')
        check(bool(r.get('prompt_zh')) and isinstance(r.get('output_schema'), dict), 'Missing public prompt/schema')
    for r in gold:
        for field in ['initial_model_path', 'final_model_path']:
            check((dataset / r[field]).is_file(), 'Missing model: ' + r[field])
    syntax = 0
    for base in [ROOT / 'agent', ROOT / 'scripts']:
        for p in base.rglob('*.py'):
            try:
                text = p.read_text(encoding='utf-8-sig')
                ast.parse(text)
                check(not re.search(r"[\"']sk-[A-Za-z0-9_-]{20,}[\"']", text), 'Credential literal in ' + str(p.relative_to(ROOT)))
                check(not re.search(r'\b[A-Z]:[\\/]', text), 'Machine-specific path in ' + str(p.relative_to(ROOT)))
                syntax += 1
            except SyntaxError as exc:
                errors.append(str(exc))
    for name in ['baseline', 'baselines', 'experiments', 'results', 'inputs', 'searchworthy', 'tests']:
        check(not (ROOT / name).exists(), 'Unexpected old/comparison directory: ' + name)
    check(not (ROOT / 'datasets/SearchWorthyOR-v1.6.1-candidate').exists(), 'Old dataset still present')
    check(not (ROOT / 'agent/configs/local_runtime.json').exists(), 'Machine credential config is published')
    report = {'status': 'PASS' if not errors else 'FAIL', 'frozen_files_checked': len(manifest['files']),
              'public_cases': len(public), 'source_tasks': len(tasks), 'python_syntax_checked': syntax,
              'new_model_calls': 0, 'new_search_calls': 0, 'new_solver_calls': 0,
              'scope': 'Integrity and source/data structure; not a live experiment or a new semantic review.', 'errors': errors}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
