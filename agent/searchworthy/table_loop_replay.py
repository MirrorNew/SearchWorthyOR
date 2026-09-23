"""Offline runnable entry. No live transport, credentials, or API option."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from searchworthy.runtime import RunContext, write
from searchworthy.table_loop import TableLoopAgent, VERSION


class ReplayTransport:
    def __init__(self, responses):
        self.responses = deepcopy(responses)
        self.calls = []

    def take(self, purpose, data):
        if not self.responses:
            raise ValueError('Offline fixture exhausted')
        row = self.responses.pop(0)
        if row['purpose'] != purpose:
            raise ValueError(f'Offline fixture expected {row["purpose"]}, got {purpose}')
        self.calls.append({'purpose': purpose, 'input': deepcopy(data)})
        if row.get('error'):
            raise RuntimeError(row['error'])
        return deepcopy(row['response'])

    def model(self, messages, purpose, output_schema=None):
        value = self.take(purpose, messages)
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    def search(self, query):
        return self.take('SEARCH', query)

    def read(self, candidate):
        return self.take('READ', candidate)

    def usage_summary(self):
        return {'mode': 'OFFLINE_HANDWRITTEN_RESPONSES', 'actual_api_calls': 0,
                'total_tokens': None, 'replayed_operations': len(self.calls)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--responses', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    public = json.loads(Path(args.case).read_text(encoding='utf-8-sig'))
    public = {k: public[k] for k in ('id', 'prompt', 'output_schema')}
    transport = ReplayTransport(json.loads(Path(args.responses).read_text(encoding='utf-8-sig')))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads((Path(__file__).resolve().parents[1] / 'configs' / 'i01_lite_runtime.json').read_text(encoding='utf-8'))
    config['mode'] = 'OFFLINE_ONLY'
    ctx = RunContext(output, config, VERSION, public['id'], live=False)
    ctx.network_allowed = False
    write(output / 'version.json', {'version': VERSION, 'api_calls': 0, 'fixture': args.responses})
    result = TableLoopAgent(ctx, public, transport).run()
    write(output / 'replay_calls.json', transport.calls)
    print(json.dumps({'stop_reason': result['stop_reason'], 'decision': result['decision'],
                      'resources': result['resources'], 'api_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
