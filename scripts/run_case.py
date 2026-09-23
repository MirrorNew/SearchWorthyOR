"""Prepare one isolated public case; execute only with --run or --check-isolation."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def prepare(eval_id, output, credential_file):
    public_file = ROOT / 'datasets/SearchWorthyOR-v1.6.2/public/cases_zh.jsonl'
    with public_file.open(encoding='utf-8') as stream:
        matches = [row for row in map(json.loads, stream) if row['eval_id'] == eval_id]
    if len(matches) != 1:
        raise ValueError('Expected one public eval_id: ' + eval_id)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(ROOT / 'agent', output / 'source', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (output / 'inputs').mkdir()
    public = matches[0]
    payload = {'id': eval_id, 'prompt': public['prompt_zh'], 'output_schema': public['output_schema']}
    (output / 'inputs' / (eval_id + '.json')).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    local = {'credential_file': str(credential_file.expanduser().resolve())}
    (output / 'source/configs/local_runtime.json').write_text(json.dumps(local, ensure_ascii=False, indent=2), encoding='utf-8')
    upstream = json.loads((ROOT / 'release_manifest.json').read_text(encoding='utf-8'))
    files = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for part in ['source', 'inputs'] for p in sorted((output / part).rglob('*')) if p.is_file()}
    source_id = hashlib.sha256(json.dumps(files, sort_keys=True).encode('utf-8')).hexdigest()
    manifest = {'version': upstream['agent_version'], 'source_id': source_id,
                'upstream_source_id': upstream['upstream_agent_source_id'],
                'project_root': str(ROOT), 'files': files,
                'scope': 'One new run; local path configuration is not the archived 360-case result.'}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eval-id', required=True)
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing results are never overwritten.')
    parser.add_argument('--env-file', type=Path, default=Path(os.environ.get('SEARCHWORTHY_ENV_FILE', ROOT / '.env')))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--run', action='store_true', help='Make real model/search calls with the frozen configuration.')
    mode.add_argument('--check-isolation', action='store_true', help='Run the worker access check; no model/search/solve calls.')
    args = parser.parse_args()
    if args.check_isolation and not args.output.resolve().is_relative_to(ROOT):
        parser.error('--check-isolation requires --output inside this repository (for the original worker guard).')
    folder = prepare(args.eval_id, args.output, args.env_file)
    print(json.dumps({'prepared': str(folder), 'eval_id': args.eval_id, 'public_input_only': True}, ensure_ascii=False), flush=True)
    if not args.run and not args.check_isolation:
        return 0
    cmd = [sys.executable, '-B', '-X', 'utf8', str(folder / 'source/lite_worker.py'), args.eval_id, str(time.time())]
    if args.check_isolation:
        cmd.append('--isolation-check')
    return subprocess.run(cmd, check=False, timeout=1230, cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
