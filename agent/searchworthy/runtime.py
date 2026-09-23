"""Append-only events, resource reservations and transaction snapshots."""
from pathlib import Path
import time
import json
from searchworthy.contracts import identity, canonical

ROOT = Path(__file__).resolve().parents[1]
FINALIZATION_RESERVE_SECONDS = 2.


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    retry_until = time.monotonic() + .05
    delays = (.01, .03)
    for attempt in range(3):
        try:
            temp.replace(path)
            return
        except PermissionError as exc:
            code = getattr(exc, 'winerror', None)
            # WinError 5 also covers permanent ACL/read-only errors. Restrict
            # its short retry to replacing an existing regular non-read-only file.
            try:
                regular = path.is_file()
                readonly = regular and bool(getattr(path.stat(), 'st_file_attributes', 0) & 1)
            except OSError:
                regular, readonly = False, True
            transient = not readonly and (code in {32, 33} or code == 5 and regular)
            if not transient or attempt == 2 or time.monotonic() + delays[attempt] > retry_until:
                raise
            # This helper has no case context: at most 40 ms of extra sleep.
            # The original case watchdog and its delivery reserve stay unchanged.
            time.sleep(delays[attempt])


class BudgetExhausted(RuntimeError):
    pass


class InfrastructureStopped(RuntimeError):
    pass


class RunContext:
    def __init__(self, directory, config, method='agent', eval_id='offline', live=False):
        self.directory = Path(directory)
        self.config = config
        self.method, self.eval_id, self.live = method, eval_id, live
        self.started = time.monotonic()
        self.resources = {k: 0 for k in ('model', 'search', 'read', 'solve', 'format_repairs', 'schedule')}
        self.events = []

    def elapsed(self):
        return time.monotonic() - self.started

    def remaining(self):
        # Every existing worker timeout shares this work deadline. The original
        # wall limit still includes the final two seconds for durable delivery.
        return max(0., self.config['budgets']['wall_seconds'] - self.elapsed() - FINALIZATION_RESERVE_SECONDS)

    def reserve(self, resource, **detail):
        if not self.remaining():
            raise BudgetExhausted('wall_seconds')
        maximum = self.config['budgets'].get(resource)
        if maximum is not None and self.resources.get(resource, 0) >= maximum:
            raise BudgetExhausted(resource)
        ledger_path=self.config.get('batch_budget_file')
        if ledger_path and resource in {'model','search','read'}:
            # Round4 workers run serially; one durable ledger owns all attempts.
            ledger=json.loads(Path(ledger_path).read_text(encoding='utf-8'))
            batch=self.config['batch_budget_partition']
            if ledger['used'][resource]>=ledger['caps'][resource] or ledger['partitions'][batch]['used'][resource]>=ledger['partitions'][batch]['caps'][resource]:
                raise BudgetExhausted('batch_'+resource)
            ledger['used'][resource]+=1
            ledger['partitions'][batch]['used'][resource]+=1
            ledger['reservations'].append({'run':self.directory.name,'resource':resource,'partition':batch,**detail})
            write(ledger_path,ledger)
        self.resources[resource] = self.resources.get(resource, 0) + 1
        self.event('RESOURCE_RESERVED', resource=resource, **detail)

    def event(self, kind, **detail):
        event = {'kind': kind, 'elapsed': self.elapsed(), **detail}
        self.events.append(event)
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as f:
            f.write(canonical(event) + '\n')

    def solve(self, ir, label):
        from adapters.solver import solve
        self.reserve('solve', label=label)
        result = solve(ir, min(self.remaining(), self.config['budgets']['solve_seconds']))
        self.event('SOLVE', label=label, status=result['status'])
        return result
