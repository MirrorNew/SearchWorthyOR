"""File handoff to fresh Codex subagents and parent-operated native search."""
import json
from pathlib import Path
import time
from uuid import uuid4

from searchworthy.page_read import read_page
from searchworthy.runtime import write, BudgetExhausted


class NativeLiteTransport:
    accounts_read = True

    def __init__(self, ctx, revision_getter):
        self.ctx, self.revision_getter = ctx, revision_getter

    def model(self, messages, purpose, output_schema=None):
        result = self.request('model', purpose, {'messages':messages})
        return result if isinstance(result,str) else json.dumps(result,ensure_ascii=False)

    def search(self, query):
        return self.request('search','SEARCH',{'query':query})

    def read(self, row):
        pages, attempts = read_page(self.ctx,row)
        return {'pages':pages,'attempts':attempts}

    def request(self, kind, purpose, data):
        request_id=uuid4().hex
        folder=self.ctx.directory/'native'/request_id
        folder.mkdir(parents=True)
        deadline=time.time()+min(650,self.ctx.remaining())
        request={'request_id':request_id,'eval_id':self.ctx.eval_id,'kind':kind,'purpose':purpose,
            'model':'gpt-5.6-luna','reasoning_effort':'xhigh','temperature':None,
            'temperature_control':'UNAVAILABLE_NATIVE_SUBAGENT','revision':self.revision_getter(),
            'deadline_unix':deadline,'response_path':str(folder/'response.json'),'input':data}
        write(folder/'request.json',request)
        write(folder/'pending.json',{'state':'PENDING','request_id':request_id})
        started=time.monotonic();status='FAILED';detail=None
        try:
            while not (folder/'response.json').exists():
                if self.ctx.remaining()<=0:raise BudgetExhausted('wall_seconds')
                if time.time()>=deadline:raise TimeoutError('Native stage original deadline exhausted')
                time.sleep(.2)
            response=json.loads((folder/'response.json').read_text(encoding='utf-8-sig'))
            if time.time()>=deadline:raise TimeoutError('Native response arrived after deadline')
            if response['request_id']!=request_id:raise ValueError('Wrong handoff request ID')
            if response.get('error'):raise RuntimeError(response['error'])
            if self.revision_getter()!=request['revision']:raise ValueError('Revision changed')
            status='CONSUMED'
            return response['content']
        except Exception as exc:
            detail=type(exc).__name__+': '+str(exc)
            raise
        finally:
            write(folder/'pending.json',{'state':status,'request_id':request_id,'error':detail})
            row={'request_id':request_id,'kind':kind,'purpose':purpose,'status':status,'error_detail':detail,
                'requested_model':'gpt-5.6-luna' if kind=='model' else None,'reasoning_effort':'xhigh' if kind=='model' else None,
                'actual_model':None,'actual_temperature':None,'usage':{'input_tokens':None,'output_tokens':None,'total_tokens':None},
                'channel':'CODEX_SUBAGENT' if kind=='model' else 'CODEX_NATIVE_WEB','retry_index':0,
                'request_path':str(folder/'request.json'),'response_path':str(folder/'response.json'),
                'wall_seconds':time.monotonic()-started}
            with (self.ctx.directory/'api_calls.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')

    def usage_summary(self):
        path=self.ctx.directory/'api_calls.jsonl'
        rows=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []
        return {'mode':'CODEX_NATIVE_HANDOFF','calls':len(rows),'model_calls':sum(x['kind']=='model' for x in rows),
            'search_calls':sum(x['kind']=='search' for x in rows),'total_tokens':None,'billing_not_evaluated':True,
            'requested_model':'gpt-5.6-luna','requested_reasoning_effort':'xhigh','temperature':None,
            'first_response_body_timeout':'NOT_OBSERVABLE_NATIVE','technical_retry_support':'NO_AUTOMATIC_NATIVE_RETRY'}
