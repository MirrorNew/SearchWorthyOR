"""One isolated public case. No scorer, Gold, history, or other case access."""
import json
import os
from pathlib import Path
import sys
import time


def main():
    source = Path(__file__).resolve().parent
    frozen = source.parent
    eid, admitted = sys.argv[1], float(sys.argv[2])
    own_input = frozen / 'inputs' / (eid + '.json')
    own_output = frozen / ('isolation' if '--isolation-check' in sys.argv else 'cases') / eid
    own_output.mkdir(parents=True, exist_ok=False)
    credential = Path(json.loads((source / 'configs/local_runtime.json').read_text(encoding='utf-8-sig'))['credential_file']).resolve()
    meta = json.loads((frozen / 'manifest.json').read_text(encoding='utf-8'))
    project = Path(meta['project_root']).resolve()
    audit = (own_output / 'access.jsonl').open('a', encoding='utf-8')

    def guard(event, args):
        if event not in {'open', 'os.listdir', 'os.scandir'} or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(args[0])).resolve()
        if p.is_relative_to(project):
            ok = p == own_input or p == credential or p.is_relative_to(source) or p.is_relative_to(own_output)
            audit.write(json.dumps({'event': event, 'path': str(p), 'allowed': ok}) + '\n')
            audit.flush()
            if not ok:
                raise PermissionError('Worker data isolation blocked: ' + str(p))

    sys.addaudithook(guard)
    sys.path = [str(source)] + [p for p in sys.path if p and not Path(p).resolve().is_relative_to(project)]
    from searchworthy.runtime import RunContext, write
    from searchworthy.table_loop import TableLoopAgent
    from searchworthy.api_lite import ShubiaobiaoTransport
    public = json.loads(own_input.read_text(encoding='utf-8'))
    if '--isolation-check' in sys.argv:
        for forbidden in (frozen / 'batch.json', project / 'outputs/baseline_validity_20260911/final_instance_audit.jsonl'):
            try:
                forbidden.read_bytes()
            except PermissionError:
                pass
            else:
                raise AssertionError('Isolation failed')
        print('ISOLATION_PASS_NO_API')
        return
    config = json.loads((source / 'configs/i01_lite_runtime.json').read_text(encoding='utf-8'))
    assert config['mode'] == 'LIVE' and config['model'] == {'name':'gpt-5.6-luna','reasoning_effort':'xhigh','temperature':1}
    ctx = RunContext(own_output, config, meta['version'], eid, live=True)
    ctx.started = time.monotonic() - max(0, time.time() - admitted)
    agent = TableLoopAgent(ctx, public, None)
    agent.transport = ShubiaobiaoTransport(ctx, lambda: agent.revision)
    write(own_output / 'version.json', {'version':meta['version'], 'source_id':meta['source_id'], 'admitted_at':admitted})
    agent.run()


if __name__ == '__main__':
    main()
