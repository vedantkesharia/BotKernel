import pytest

from botkernel.lang_agents import MockReasoner, Proposal


def test_cost_graph_observes_then_proposes_bounded_downscale():
    result = MockReasoner().propose("cost", {"capacity": 6, "latency_p95": 40})
    assert result.capacity == 5
    assert "observed" in result.rationale


def test_performance_graph_uses_observed_latency():
    provider = MockReasoner()
    assert provider.propose("performance", {"capacity": 4, "latency_p95": 90}).capacity == 5
    assert provider.propose("performance", {"capacity": 4, "latency_p95": 50}).capacity == 4


def test_typed_provider_rejects_unsafe_capacity():
    import pytest
    with pytest.raises(Exception):
        Proposal(capacity=100, rationale="bad")


def test_graph_runs_nodes_and_persists_checkpoint(tmp_path, monkeypatch):
    import httpx
    from botkernel.lang_agents import build_agent
    from langgraph.checkpoint.sqlite import SqliteSaver
    import sqlite3
    nodes=[]
    class Response:
        status_code=202
        def __init__(self, payload=None): self.payload=payload
        def json(self): return self.payload or {'id':'action-1'}
        text=''
        def raise_for_status(self): return self
    class Client:
        def __init__(self,*a,**k): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def post(self,*a,**k):
            nodes.append(a[0])
            return Response()
        def get(self,*a,**k):
            class Telemetry(Response):
                def json(self): return [{'id':'service-a','capacity':4,'version':0,'latency_p95':90}]
            return Telemetry()
    monkeypatch.setattr(httpx,'Client',Client)
    def direct_post(*a,**k):
        nodes.append(a[0])
        return Response()
    monkeypatch.setattr(httpx,'post',direct_post)
    graph=build_agent('performance','http://gateway',checkpoint_path=str(tmp_path/'agent.sqlite'))
    from botkernel.lang_agents import checkpoint_owner
    with checkpoint_owner(str(tmp_path/'agent.sqlite')) as token:
        out=graph.invoke({'agent':'langgraph-performance','run_id':'stable-1'},config={'configurable':{'thread_id':'test-thread','ownership_token':token}})
    assert out['outcome']['decision']=='accepted'
    assert out['outcome']['action_id']=='action-1'
    assert (tmp_path/'agent.sqlite').is_file()
    assert nodes == ['/agents/langgraph-performance', 'http://gateway/actions']
    connection=sqlite3.connect(str(tmp_path/'agent.sqlite'),check_same_thread=False)
    restored=build_agent('performance','http://gateway',checkpoint_path=str(tmp_path/'agent.sqlite'))
    state=restored.get_state({'configurable':{'thread_id':'test-thread'}})
    assert state.values['outcome']['action_id']=='action-1'
    assert state.values['proposal']['capacity']==5
    connection.close()


def test_lost_gateway_response_replays_same_checkpointed_proposal(tmp_path,monkeypatch):
    import httpx,pytest
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from botkernel.api import app
    from botkernel.core import engine,execute
    from botkernel.lang_agents import run_once
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',str(tmp_path/'agent.sqlite'))
    monkeypatch.setenv('AGENT_RETRY_BASE_SECONDS','0')
    with engine.begin() as c:
        c.execute(text('UPDATE quota SET capacity=1000 WHERE id=1'))
        resource=dict(c.execute(text("SELECT * FROM resources WHERE id='service-a'")).mappings().one())
    role='cost' if resource['capacity']>=12 else 'performance'
    client=TestClient(app)
    class Session:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,path,**kwargs): return client.post(path,**kwargs)
        def get(self,path,**kwargs):
            class Telemetry:
                def raise_for_status(self): return self
                def json(self): return [{**resource,'latency_p95':120}]
            return Telemetry()
    attempts=[]
    def post(url,**kwargs):
        response=client.post('/actions',json=kwargs['json'])
        attempts.append(kwargs['json'].copy())
        if len(attempts)==1:
            assert response.status_code==202
            raise httpx.ReadTimeout('response lost')
        return response
    monkeypatch.setattr(httpx,'Client',Session)
    monkeypatch.setattr(httpx,'post',post)
    with pytest.raises(httpx.ReadTimeout): run_once(role,'http://gateway',run_id='stable-test-proposal')
    result=run_once(role,'http://gateway',run_id='should-not-be-used')
    assert result['run_id']=='stable-test-proposal'
    assert attempts[0]==attempts[1]
    action=result['outcome']['action_id']
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM actions WHERE idempotency_key='stable-test-proposal'")).scalar_one()==1
        assert c.execute(text('SELECT count(*) FROM outbox WHERE action_id=:id'),{'id':action}).scalar_one()==1
    execute(action); execute(action)
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM receipts WHERE action_id=:id'),{'id':action}).scalar_one()==1
        assert c.execute(text('SELECT count(*) FROM effects WHERE action_id=:id'),{'id':action}).scalar_one()==1
        assert c.execute(text("SELECT version FROM resources WHERE id='service-a'")).scalar_one()==resource['version']+1


def test_process_crash_after_gateway_acceptance_replays_through_kafka(tmp_path):
    import os,sys,subprocess,time,socket,json,httpx,select,sqlite3,redis
    from sqlalchemy import text
    from botkernel.core import engine
    with engine.begin() as c:
        c.execute(text('UPDATE quota SET capacity=1000 WHERE id=1'))
        c.execute(text("UPDATE resources SET capacity=6 WHERE id='service-a'"))
        c.execute(text("UPDATE external_resources SET capacity=6 WHERE id='service-a'"))
        resource=c.execute(text("SELECT capacity,version FROM resources WHERE id='service-a'")).one()
    assert resource.capacity>3
    sock=socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]; sock.close()
    url=f'http://127.0.0.1:{port}'
    env={**os.environ,'BOTKERNEL_AGENT_CHECKPOINTS':str(tmp_path/'cost.sqlite'),'BOTKERNEL_API_URL':url,'AGENT_CRASH_AFTER_ACCEPT':'true'}
    api=subprocess.Popen([sys.executable,'-m','uvicorn','botkernel.api:app','--host','127.0.0.1','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    publisher=worker=performance=None
    try:
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            try:
                if httpx.get(url+'/health',timeout=1).status_code==200: break
            except httpx.HTTPError: pass
            time.sleep(.2)
        else: pytest.fail('test API failed to start')
        perf_code="from botkernel.lang_agents import run_once; import json,sys; x=run_once('performance',run_id='performance-cycle'); print('READY '+json.dumps(x),flush=True); sys.stdin.readline(); print('AFTER '+json.dumps(run_once('performance')),flush=True)"
        perf_env={**env,'BOTKERNEL_AGENT_CHECKPOINTS':str(tmp_path/'performance.sqlite'),'AGENT_CRASH_AFTER_ACCEPT':'false'}
        performance=subprocess.Popen([sys.executable,'-c',perf_code],env=perf_env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        assert select.select([performance.stdout],[],[],30)[0], 'performance agent did not start'
        perf_line=performance.stdout.readline().strip(); assert perf_line.startswith('READY '),perf_line
        perf_state=json.loads(perf_line[6:]); assert perf_state['outcome']['decision']=='no_change'
        agent_code="from botkernel.lang_agents import run_once; import json; print(json.dumps(run_once('cost',run_id='crash-boundary-key')),flush=True)"
        crashed=subprocess.run([sys.executable,'-c',agent_code],env=env,timeout=30,capture_output=True,text=True)
        assert crashed.returncode==23,crashed.stderr
        assert performance.poll() is None
        with engine.connect() as c:
            row=c.execute(text("SELECT id,state,payload FROM actions WHERE idempotency_key='crash-boundary-key'")).mappings().one()
            action=str(row['id']); assert row['state']=='RESERVED'
            assert c.execute(text("SELECT count(*) FROM agents WHERE id IN ('langgraph-cost','langgraph-performance') AND heartbeat > now()-interval '30 seconds'")).scalar_one()==2
        cache=redis.Redis.from_url(os.environ['REDIS_URL'],socket_timeout=2,socket_connect_timeout=2)
        assert cache.get('heartbeat:langgraph-cost')==b'alive'
        assert cache.get('heartbeat:langgraph-performance')==b'alive'
        with sqlite3.connect(str(tmp_path/'cost.sqlite')) as c:
            assert c.execute("SELECT count(*) FROM checkpoints WHERE thread_id='agent-cost'").fetchone()[0]>0
            saved_body=json.loads(c.execute("SELECT payload FROM agent_proposals WHERE id='crash-boundary-key'").fetchone()[0])
        assert all(row['payload'][key]==value for key,value in saved_body.items())
        publisher=subprocess.Popen([sys.executable,'-m','botkernel.worker'],env={**env,'ROLE':'publisher'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        worker=subprocess.Popen([sys.executable,'-m','botkernel.worker'],env={**env,'ROLE':'worker'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            with engine.connect() as c: status=c.execute(text('SELECT state FROM actions WHERE id=:id'),{'id':action}).scalar_one()
            if status=='SUCCEEDED': break
            time.sleep(.2)
        assert status=='SUCCEEDED'
        resumed=subprocess.run([sys.executable,'-c',agent_code],env={**env,'AGENT_CRASH_AFTER_ACCEPT':'false'},timeout=30,capture_output=True,text=True)
        assert resumed.returncode==0,resumed.stderr
        result=json.loads(resumed.stdout.strip().splitlines()[-1]); assert result['run_id']=='crash-boundary-key'; assert result['outcome']['action_id']==action
        with engine.connect() as c:
            assert c.execute(text("SELECT count(*) FROM actions WHERE idempotency_key='crash-boundary-key'")).scalar_one()==1
            assert c.execute(text('SELECT count(*) FROM outbox WHERE action_id=:id AND published'),{'id':action}).scalar_one()==1
            assert c.execute(text('SELECT count(*) FROM receipts WHERE action_id=:id'),{'id':action}).scalar_one()==1
            assert c.execute(text('SELECT count(*) FROM effects WHERE action_id=:id'),{'id':action}).scalar_one()==1
            assert c.execute(text("SELECT version FROM resources WHERE id='service-a'")).scalar_one()==resource.version+1
            assert c.execute(text("SELECT count(*) FROM agents WHERE id IN ('langgraph-cost','langgraph-performance')")).scalar_one()==2
        reconciled=subprocess.run([sys.executable,'-c',agent_code],env={**env,'AGENT_CRASH_AFTER_ACCEPT':'false'},timeout=30,capture_output=True,text=True)
        assert reconciled.returncode==0,reconciled.stderr
        reconciled_state=json.loads(reconciled.stdout.strip().splitlines()[-1])
        assert reconciled_state['run_id']=='crash-boundary-key'
        assert reconciled_state['outcome']=={'decision':'succeeded','action_id':action}
        with sqlite3.connect(str(tmp_path/'cost.sqlite')) as c:
            stored=c.execute('SELECT id,action_id,action_status,status,attempts FROM agent_proposals').fetchone()
        assert stored[:4]==('crash-boundary-key',action,'SUCCEEDED','SUCCEEDED')
        print('RECOVERY_EVIDENCE',json.dumps({'agents':['langgraph-cost','langgraph-performance'],'threads':['agent-cost','agent-performance'],'proposal':'crash-boundary-key','action_id':action,'attempts':stored[4],'state':'SUCCEEDED','receipts':1,'effects':1,'before_version':resource.version,'after_version':resource.version+1}),flush=True)
        performance.stdin.write('continue\n'); performance.stdin.flush()
        assert select.select([performance.stdout],[],[],30)[0], 'performance agent did not continue'
        line=performance.stdout.readline().strip(); assert line.startswith('AFTER '),line
        assert json.loads(line[6:])['outcome']['decision']=='no_change'
        performance.wait(timeout=10); assert performance.returncode==0
        next_code="from botkernel.lang_agents import run_once; import json; print(json.dumps(run_once('cost',run_id='next-cost-cycle')),flush=True)"
        next_run=subprocess.run([sys.executable,'-c',next_code],env={**env,'AGENT_CRASH_AFTER_ACCEPT':'false'},timeout=30,capture_output=True,text=True)
        assert next_run.returncode==0,next_run.stderr
        next_state=json.loads(next_run.stdout.strip().splitlines()[-1])
        assert next_state['run_id']=='next-cost-cycle'
        assert next_state['outcome']['decision']=='accepted'
        assert next_state['outcome']['action_id']!=action
        next_id=next_state['outcome']['action_id']; deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            with engine.connect() as c: next_status=c.execute(text('SELECT state FROM actions WHERE id=:id'),{'id':next_id}).scalar_one()
            if next_status=='SUCCEEDED': break
            time.sleep(.2)
        assert next_status=='SUCCEEDED'
        print('NEXT_CYCLE',json.dumps({'proposal':'next-cost-cycle','action_id':next_id,'state':next_status}),flush=True)
        with sqlite3.connect(str(tmp_path/'performance.sqlite')) as c:
            assert c.execute("SELECT count(*) FROM checkpoints WHERE thread_id='agent-performance'").fetchone()[0]>0
    finally:
        for proc in (performance,worker,publisher,api):
            if proc and proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=5)


def test_escalated_checkpoint_does_not_start_new_cycle(tmp_path,monkeypatch):
    import httpx
    from botkernel.lang_agents import build_agent,run_once
    path=str(tmp_path/'escalated.sqlite')
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',path)
    graph=build_agent('cost','http://gateway',checkpoint_path=path)
    config={'configurable':{'thread_id':'agent-cost'}}
    graph.update_state(config,{'agent':'langgraph-cost','run_id':'held-cycle','outcome':{'decision':'escalated','action_id':'existing'}},as_node='submit')
    graph.checkpointer.conn.close()
    def forbidden(*args,**kwargs): raise AssertionError('escalated agent must not call gateway')
    monkeypatch.setattr(httpx,'Client',forbidden);monkeypatch.setattr(httpx,'get',forbidden);monkeypatch.setattr(httpx,'post',forbidden)
    result=run_once('cost','http://gateway')
    assert result['run_id']=='held-cycle'
    assert result['outcome']['decision']=='escalated'


def test_proposal_attempt_limit_and_immutable_payload(tmp_path,monkeypatch):
    import pytest,sqlite3
    from botkernel.lang_agents import reserve_attempt
    path=str(tmp_path/'proposals.sqlite')
    body={'idempotency_key':'cycle-1','capacity':3}
    monkeypatch.setenv('AGENT_MAX_SUBMISSION_ATTEMPTS','2')
    assert reserve_attempt(path,body) is True
    assert reserve_attempt(path,body) is True
    assert reserve_attempt(path,body) is False
    with pytest.raises(ValueError,match='payload mismatch'):
        reserve_attempt(path,{'idempotency_key':'cycle-1','capacity':4})
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT attempts,status FROM agent_proposals').fetchone()==(2,'REVIEW_REQUIRED')


def test_checkpoint_owner_excludes_second_process_and_releases(tmp_path):
    import subprocess,sys,select,os
    path=str(tmp_path/'lock.sqlite')
    code="from botkernel.lang_agents import checkpoint_owner; import sys; p=checkpoint_owner(sys.argv[1]); p.__enter__(); print('ready',flush=True); sys.stdin.readline(); p.__exit__(None,None,None)"
    owner=subprocess.Popen([sys.executable,'-c',code,path],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=os.environ.copy())
    try:
        assert select.select([owner.stdout],[],[],20)[0] and owner.stdout.readline().strip()=='ready'
        from botkernel.lang_agents import checkpoint_owner
        import pytest
        with pytest.raises(RuntimeError,match='already owned'):
            with checkpoint_owner(path): pass
        owner.terminate(); owner.wait(timeout=10)
        with checkpoint_owner(path): pass
    finally:
        if owner.poll() is None: owner.terminate();owner.wait(timeout=10)


def test_retry_deadline_persists_and_payload_is_immutable(tmp_path, monkeypatch):
    import sqlite3, pytest
    from botkernel.lang_agents import reserve_attempt, schedule_retry, retry_due
    path=str(tmp_path/'retry.sqlite')
    body={'idempotency_key':'retry-key','agent':'langgraph-cost','capacity':3}
    monkeypatch.setenv('AGENT_RETRY_BASE_SECONDS','30')
    assert reserve_attempt(path,body)
    schedule_retry(path,'retry-key','rate_limited','40')
    assert not retry_due(path,'retry-key')
    with sqlite3.connect(path) as c:
        status,error,deadline=c.execute('SELECT status,last_error,next_retry_at FROM agent_proposals').fetchone()
    assert (status,error)==('OUTCOME_UNKNOWN','rate_limited') and deadline
    with pytest.raises(ValueError,match='payload mismatch'):
        reserve_attempt(path,{**body,'capacity':4})


def test_direct_graph_cannot_submit_without_owner(tmp_path, monkeypatch):
    import pytest, httpx
    from botkernel.lang_agents import build_agent
    graph=build_agent('cost','http://gateway',checkpoint_path=str(tmp_path/'guard.sqlite'))
    monkeypatch.setattr(httpx,'post',lambda *a,**k: pytest.fail('must not submit'))
    try:
        with pytest.raises(RuntimeError,match='requires checkpoint ownership'):
            graph.nodes['submit'].invoke({'agent':'langgraph-cost','run_id':'key','telemetry':{'id':'service-a','capacity':4,'version':0},'proposal':{'capacity':3,'rationale':'test'}},config={'configurable':{'thread_id':'test'}})
    finally:
        graph.checkpointer.conn.close()


def test_reconciliation_failure_is_bounded_and_persisted(tmp_path, monkeypatch):
    import sqlite3
    from botkernel.lang_agents import reserve_attempt, proposal_status, reconciliation_failure, retry_due
    path=str(tmp_path/'lookup.sqlite')
    monkeypatch.setenv('AGENT_MAX_RECONCILIATION_ATTEMPTS','2')
    monkeypatch.setenv('AGENT_RETRY_BASE_SECONDS','30')
    assert reserve_attempt(path,{'idempotency_key':'lookup-key','agent':'langgraph-cost','capacity':3})
    proposal_status(path,'lookup-key','ACCEPTED',action_id='action-1')
    assert not reconciliation_failure(path,'lookup-key','transport')
    assert not retry_due(path,'lookup-key')
    assert reconciliation_failure(path,'lookup-key','action_not_found')
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT status,reconciliations,action_id,last_error FROM agent_proposals').fetchone()==('REVIEW_REQUIRED',2,'action-1','action_not_found')


def test_review_record_fences_interrupted_submission_checkpoint(tmp_path, monkeypatch):
    import httpx, json, sqlite3, subprocess, sys, pytest
    from sqlalchemy import text
    from botkernel.core import engine
    from botkernel.lang_agents import build_agent, checkpoint_owner, proposal_status, reserve_attempt, run_once

    path=str(tmp_path/'review.sqlite')
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',path)
    body={'agent':'langgraph-cost','workflow':'langgraph-cost','idempotency_key':'review-crash',
          'resource':'service-a','expected_version':0,'capacity':3,'risk':'low'}
    from botkernel.bedrock import AgentDecision
    state={'agent':'langgraph-cost','run_id':body['idempotency_key'],
           'telemetry':{'id':'service-a','capacity':4,'version':0},
           'proposal':{'capacity':3,'rationale':'test'},'outcome':None,
           'reasoning_provider':'deterministic_mock',
           'ai_provenance':{'provider':'deterministic_mock','model_id':None,'input_tokens':None,'output_tokens':None,'invocations':0},
           'ai_decision':AgentDecision(decision='PROPOSE',resource='service-a',proposed_delta=-1,reason='test',evidence_references=['resource:service-a'],uncertainties=[]).model_dump()}
    config={'configurable':{'thread_id':'agent-cost'}}
    graph=build_agent('cost','http://gateway',checkpoint_path=path)
    graph.update_state(config,state,as_node='analyze')
    assert graph.get_state(config).next==('submit',)
    graph.checkpointer.conn.close()
    assert reserve_attempt(path,body)
    proposal_status(path,body['idempotency_key'],'REVIEW_REQUIRED',error='authorization')
    with sqlite3.connect(path) as c:
        original=c.execute('SELECT id,payload,fingerprint,attempts,status FROM agent_proposals').fetchall()
    assert json.loads(original[0][1])==body
    with engine.connect() as c:
        before=c.execute(text("SELECT count(*) FROM effects e JOIN actions a ON e.action_id=a.id WHERE a.idempotency_key=:key"),{'key':body['idempotency_key']}).scalar_one()
    def forbidden(*args,**kwargs): pytest.fail('reviewed proposal must not contact gateway')
    monkeypatch.setattr(httpx,'Client',forbidden)
    monkeypatch.setattr(httpx,'get',forbidden)
    monkeypatch.setattr(httpx,'post',forbidden)
    code=("import httpx,json; from botkernel.lang_agents import run_once; "
          "httpx.get=httpx.post=httpx.Client=lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected gateway call')); "
          "print(json.dumps(run_once('cost','http://gateway',run_id='must-not-start')))")
    restarted=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=30)
    assert restarted.returncode==0,restarted.stderr
    result=json.loads(restarted.stdout.strip().splitlines()[-1])
    assert result['run_id']==body['idempotency_key']
    assert result['outcome']['decision']=='review_required'
    assert result['outcome']['reason']=='authorization'
    with checkpoint_owner(path) as token:
        graph=build_agent('cost','http://gateway',checkpoint_path=path)
        try:
            direct=graph.nodes['submit'].invoke(state,config={'configurable':{'ownership_token':token}})
            assert direct['outcome']['decision']=='review_required'
        finally:
            graph.checkpointer.conn.close()
    with pytest.raises(RuntimeError,match='requires review'):
        proposal_status(path,body['idempotency_key'],'SUCCEEDED',action_id='unexpected')
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT id,payload,fingerprint,attempts,status FROM agent_proposals').fetchall()==original
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM effects e JOIN actions a ON e.action_id=a.id WHERE a.idempotency_key=:key"),{'key':body['idempotency_key']}).scalar_one()==before


def _accepted_checkpoint(path, key='accepted-key'):
    from botkernel.lang_agents import build_agent, proposal_status, reserve_attempt
    body={'idempotency_key':key,'agent':'langgraph-cost','capacity':3}
    assert reserve_attempt(path,body)
    proposal_status(path,key,'ACCEPTED',action_id='action-1')
    graph=build_agent('cost','http://gateway',checkpoint_path=path)
    graph.update_state({'configurable':{'thread_id':'agent-cost'}},
                       {'agent':'langgraph-cost','run_id':key,
                        'outcome':{'decision':'accepted','action_id':'action-1'}},as_node='submit')
    graph.checkpointer.conn.close()


def test_reconciliation_backoff_survives_restart_and_persists_success(tmp_path, monkeypatch):
    import httpx, json, sqlite3, subprocess, sys, pytest
    from botkernel.lang_agents import run_once
    path=str(tmp_path/'accepted.sqlite')
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',path)
    monkeypatch.setenv('AGENT_RETRY_BASE_SECONDS','30')
    _accepted_checkpoint(path)
    requests=[]
    class Response:
        def __init__(self,status,body=None): self.status_code=status; self.body=body
        def json(self): return self.body
    def lookup(*args,**kwargs):
        requests.append(1)
        if len(requests)==1: raise httpx.ReadTimeout('lookup timed out')
        if len(requests)==2: return Response(503)
        if len(requests)==3: return Response(200,{'id':'action-1','state':'DISPATCHED'})
        return Response(200,{'id':'action-1','state':'SUCCEEDED'})
    monkeypatch.setattr(httpx,'get',lookup)
    monkeypatch.setattr(httpx,'post',lambda *a,**k: pytest.fail('must not resubmit accepted proposal'))
    monkeypatch.setattr(httpx,'Client',lambda *a,**k: pytest.fail('must not start another cycle'))
    for expected in ('transport','gateway_unavailable'):
        result=run_once('cost','http://gateway',run_id='new-cycle')
        assert result['outcome']=={'decision':'pending','action_id':'action-1','reason':expected}
        with sqlite3.connect(path) as c:
            status,count,deadline=c.execute('SELECT status,reconciliations,next_retry_at FROM agent_proposals').fetchone()
        assert status=='ACCEPTED' and count==len(requests) and deadline
        assert run_once('cost','http://gateway')['outcome']['reason']=='reconciliation backoff'
        assert len(requests)==count
        if count==1:
            code=("import httpx,json; from botkernel.lang_agents import run_once; "
                  "httpx.get=httpx.post=httpx.Client=lambda *a,**k: (_ for _ in ()).throw(AssertionError('premature gateway call')); "
                  "print(json.dumps(run_once('cost','http://gateway')))")
            restarted=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=30)
            assert restarted.returncode==0,restarted.stderr
            assert json.loads(restarted.stdout.strip().splitlines()[-1])['outcome']['reason']=='reconciliation backoff'
        with sqlite3.connect(path) as c:
            c.execute("UPDATE agent_proposals SET next_retry_at='2000-01-01T00:00:00+00:00'")
    assert run_once('cost','http://gateway')['outcome']=={'decision':'pending','action_id':'action-1','state':'DISPATCHED'}
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT status,reconciliations,action_status FROM agent_proposals').fetchone()==('ACCEPTED',2,'DISPATCHED')
    assert run_once('cost','http://gateway')['outcome']=={'decision':'succeeded','action_id':'action-1'}
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT id,status,action_id,action_status,attempts,reconciliations FROM agent_proposals').fetchall()==[('accepted-key','SUCCEEDED','action-1','SUCCEEDED',1,2)]
    assert len(requests)==4


def test_reconciliation_exhaustion_stays_in_review_across_restart(tmp_path, monkeypatch):
    import httpx, sqlite3, pytest
    from botkernel.lang_agents import run_once
    path=str(tmp_path/'exhausted.sqlite')
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',path)
    monkeypatch.setenv('AGENT_MAX_RECONCILIATION_ATTEMPTS','2')
    monkeypatch.setenv('AGENT_RETRY_BASE_SECONDS','0')
    _accepted_checkpoint(path)
    calls=[]
    def lookup(*args,**kwargs):
        calls.append(1)
        raise httpx.ReadTimeout('lookup timed out')
    monkeypatch.setattr(httpx,'get',lookup)
    monkeypatch.setattr(httpx,'post',lambda *a,**k: pytest.fail('must not resubmit'))
    monkeypatch.setattr(httpx,'Client',lambda *a,**k: pytest.fail('must not create a new cycle'))
    assert run_once('cost','http://gateway')['outcome']['decision']=='pending'
    assert run_once('cost','http://gateway')['outcome']['decision']=='review_required'
    assert run_once('cost','http://gateway',run_id='new-cycle')['outcome']['decision']=='review_required'
    assert len(calls)==2
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT status,reconciliations,action_id,action_status,last_error FROM agent_proposals').fetchall()==[('REVIEW_REQUIRED',2,'action-1',None,'transport')]


def test_sqlite_failure_and_lost_ownership_fail_closed(tmp_path, monkeypatch):
    import httpx, sqlite3, pytest
    from botkernel.lang_agents import build_agent, checkpoint_owner, run_once
    path=str(tmp_path/'closed.sqlite')
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',path)
    graph=build_agent('cost','http://gateway',checkpoint_path=path)
    from botkernel.bedrock import AgentDecision
    state={'agent':'langgraph-cost','run_id':'key','telemetry':{'id':'service-a','capacity':4,'version':0},
           'proposal':{'capacity':3,'rationale':'test'},'reasoning_provider':'deterministic_mock',
           'ai_provenance':{'provider':'deterministic_mock','model_id':None,'input_tokens':None,'output_tokens':None,'invocations':0},
           'ai_decision':AgentDecision(decision='PROPOSE',resource='service-a',proposed_delta=-1,reason='test',evidence_references=['resource:service-a'],uncertainties=[]).model_dump()}
    with checkpoint_owner(path) as token: pass
    monkeypatch.setattr(httpx,'post',lambda *a,**k: pytest.fail('must not submit'))
    with pytest.raises(RuntimeError,match='requires checkpoint ownership'):
        graph.nodes['submit'].invoke(state,config={'configurable':{'ownership_token':token}})
    graph.checkpointer.conn.close()
    def broken(*args,**kwargs): raise sqlite3.OperationalError('injected SQLite failure')
    monkeypatch.setattr(sqlite3,'connect',broken)
    with pytest.raises(sqlite3.OperationalError,match='injected SQLite failure'):
        run_once('cost','http://gateway')


def test_proposal_store_write_failure_does_not_submit(tmp_path, monkeypatch):
    import httpx, sqlite3, pytest
    from botkernel.lang_agents import build_agent, checkpoint_owner, initialize_proposals
    path=str(tmp_path/'write-failure.sqlite')
    initialize_proposals(path)
    with sqlite3.connect(path) as c:
        c.execute("CREATE TRIGGER reject_proposals BEFORE INSERT ON agent_proposals BEGIN SELECT RAISE(ABORT,'injected proposal write failure'); END")
    graph=build_agent('cost','http://gateway',checkpoint_path=path)
    from botkernel.bedrock import AgentDecision
    state={'agent':'langgraph-cost','run_id':'key','telemetry':{'id':'service-a','capacity':4,'version':0},
           'proposal':{'capacity':3,'rationale':'test'},'reasoning_provider':'deterministic_mock',
           'ai_provenance':{'provider':'deterministic_mock','model_id':None,'input_tokens':None,'output_tokens':None,'invocations':0},
           'ai_decision':AgentDecision(decision='PROPOSE',resource='service-a',proposed_delta=-1,reason='test',evidence_references=['resource:service-a'],uncertainties=[]).model_dump()}
    monkeypatch.setattr(httpx,'post',lambda *a,**k: pytest.fail('must not submit after SQLite failure'))
    try:
        with checkpoint_owner(path) as token:
            with pytest.raises(sqlite3.IntegrityError,match='injected proposal write failure'):
                graph.nodes['submit'].invoke(state,config={'configurable':{'ownership_token':token}})
    finally:
        graph.checkpointer.conn.close()


def test_proposal_store_lookup_error_does_not_contact_gateway(tmp_path, monkeypatch):
    import httpx, sqlite3, pytest
    from botkernel.lang_agents import run_once
    path=str(tmp_path/'read-failure.sqlite')
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',path)
    _accepted_checkpoint(path)
    with sqlite3.connect(path) as c:
        c.execute('ALTER TABLE agent_proposals RENAME COLUMN status TO broken_status')
    def forbidden(*args,**kwargs): pytest.fail('must not contact gateway after SQLite lookup failure')
    monkeypatch.setattr(httpx,'Client',forbidden)
    monkeypatch.setattr(httpx,'get',forbidden)
    monkeypatch.setattr(httpx,'post',forbidden)
    with pytest.raises(sqlite3.OperationalError,match='no such column: status'):
        run_once('cost','http://gateway')


def test_different_roles_can_own_checkpoints_concurrently(tmp_path):
    import subprocess,sys,select,os,pytest
    from botkernel.lang_agents import checkpoint_owner
    cost=str(tmp_path/'cost.sqlite')
    performance=str(tmp_path/'performance.sqlite')
    code="from botkernel.lang_agents import checkpoint_owner; import sys; p=checkpoint_owner(sys.argv[1]); p.__enter__(); print('ready',flush=True); sys.stdin.readline(); p.__exit__(None,None,None)"
    processes=[]
    try:
        for path in (cost,performance):
            proc=subprocess.Popen([sys.executable,'-c',code,path],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=os.environ.copy())
            processes.append(proc)
            assert select.select([proc.stdout],[],[],20)[0] and proc.stdout.readline().strip()=='ready'
        assert all(proc.poll() is None for proc in processes)
        with pytest.raises(RuntimeError,match='already owned'):
            with checkpoint_owner(cost): pass
        with pytest.raises(RuntimeError,match='already owned'):
            with checkpoint_owner(performance): pass
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate(); proc.wait(timeout=10)


def test_studio_checkpoint_is_in_memory_and_cannot_submit(tmp_path, monkeypatch):
    import httpx, sqlite3, pytest
    from langgraph.checkpoint.memory import MemorySaver
    from botkernel.lang_agents import build_agent
    path=str(tmp_path/'running.sqlite')
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE sentinel (value TEXT)')
        c.execute("INSERT INTO sentinel VALUES ('unchanged')")
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',path)
    studio=build_agent('cost','http://gateway',studio=True)
    assert isinstance(studio.checkpointer,MemorySaver)
    class Response:
        def raise_for_status(self): return self
        def json(self): return [{'id':'service-a','capacity':4,'version':0,'latency_p95':40}]
    class Client:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,*args,**kwargs): return Response()
        def get(self,*args,**kwargs): return Response()
    monkeypatch.setattr(httpx,'Client',Client)
    monkeypatch.setattr(httpx,'post',lambda *a,**k: pytest.fail('studio must not submit'))
    with pytest.raises(RuntimeError,match='requires checkpoint ownership'):
        studio.invoke({'agent':'langgraph-cost','run_id':'studio'},config={'configurable':{'thread_id':'studio'}})
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT value FROM sentinel').fetchall()==[('unchanged',)]
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[('sentinel',)]


def test_bedrock_decision_is_checkpointed_before_ambiguous_gateway_retry(tmp_path,monkeypatch):
    import httpx,pytest
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from botkernel.api import app
    from botkernel.core import engine
    from botkernel.bedrock import AgentDecision
    from botkernel.lang_agents import run_once

    path=str(tmp_path/'bedrock-agent.sqlite')
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',path)
    monkeypatch.setenv('AI_ACTION_EXECUTION_ENABLED','true')
    monkeypatch.setenv('CLOUD_MODE','mock')
    monkeypatch.setenv('AWS_DEPLOY_ALLOWED','false')
    monkeypatch.setenv('AGENT_RETRY_BASE_SECONDS','0')
    with engine.begin() as c:
        c.execute(text('UPDATE quota SET capacity=1000 WHERE id=1'))
        c.execute(text("UPDATE resources SET capacity=6 WHERE id='service-a'"))
        c.execute(text("UPDATE external_resources SET capacity=6 WHERE id='service-a'"))
        resource=c.execute(text("SELECT capacity,version FROM resources WHERE id='service-a'")).one()
    client=TestClient(app)
    class HttpClient:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,path,**kwargs): return client.post(path,**kwargs)
        def get(self,path,**kwargs):
            class Response:
                def raise_for_status(self): return self
                def json(self): return [{**dict(id='service-a',capacity=resource.capacity,version=resource.version,latency_p95=50,simulated=True,controller_hold=False,pending_action=False,recent_effects=[])}]
            return Response()
    class Reasoner:
        name='bedrock'; model_id='offline-test-model'
        def __init__(self): self.calls=0
        def decide(self,role,telemetry,run_id):
            self.calls+=1
            return AgentDecision(decision='PROPOSE',resource='service-a',proposed_delta=-1,reason='Reduce unused allocation.',
                evidence_references=['resource:service-a'],uncertainties=['Utilization is not measured.']),{
                    'provider':'bedrock','model_id':self.model_id,'input_tokens':100,'output_tokens':20,'invocations':1}
    reasoner=Reasoner(); posts=[]
    monkeypatch.setattr(httpx,'Client',HttpClient)
    def post(url,**kwargs):
        response=client.post('/actions',json=kwargs['json']); posts.append(kwargs['json'].copy())
        if len(posts)==1:
            assert response.status_code==202
            raise httpx.ReadTimeout('simulated response loss')
        return response
    monkeypatch.setattr(httpx,'post',post)
    with pytest.raises(httpx.ReadTimeout):
        run_once('cost','http://gateway',reasoner=reasoner,run_id='bedrock-cycle')
    result=run_once('cost','http://gateway',reasoner=reasoner,run_id='different-cycle')
    assert result['run_id']=='bedrock-cycle'
    assert result['outcome']['decision']=='accepted'
    assert reasoner.calls==1 and posts[0]==posts[1]
    with engine.connect() as c:
        action=c.execute(text("SELECT id,state FROM actions WHERE idempotency_key='bedrock-cycle'")).one()
        assert c.execute(text("SELECT count(*) FROM actions WHERE idempotency_key='bedrock-cycle'")).scalar_one()==1
        assert action.state=='RESERVED'
        assert c.execute(text('SELECT count(*) FROM effects WHERE action_id=:id'),{'id':action.id}).scalar_one()==0
        assert c.execute(text("SELECT count(*) FROM outbox WHERE action_id=:id"),{'id':action.id}).scalar_one()==1
        assert c.execute(text("SELECT capacity,version FROM resources WHERE id='service-a'")).one()==resource
    latest=client.get('/agents').json()
    decision=next(row for row in latest if row['id']=='langgraph-cost')['latest_decision']
    assert decision['provider']=='bedrock' and decision['model_id']=='offline-test-model'
    assert decision['gateway_approved'] is True and decision['action_id']==str(action.id)
    assert decision['input_tokens']==100 and decision['output_tokens']==20


def test_bedrock_advisory_and_noop_never_submit(tmp_path,monkeypatch):
    import httpx,pytest
    from botkernel.bedrock import AgentDecision
    from botkernel.lang_agents import build_agent,checkpoint_owner
    path=str(tmp_path/'advisory.sqlite')
    class Response:
        status_code=200
        text=''
        def json(self): return [{'id':'service-a','capacity':5,'version':0,'latency_p95':50,'controller_hold':False,'pending_action':False,'recent_effects':[]}]
        def raise_for_status(self): return self
    class Client:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,*args,**kwargs): return Response()
        def get(self,*args,**kwargs): return Response()
    class Reasoner:
        name='bedrock'; model_id='offline-test-model'
        def __init__(self,decision): self.decision=decision; self.calls=0
        def decide(self,role,telemetry,run_id):
            self.calls+=1
            return self.decision,{'provider':'bedrock','model_id':self.model_id,'invocations':1}
    telemetry={'id':'service-a','capacity':5,'version':0,'latency_p95':50,'controller_hold':False,'pending_action':False,'recent_effects':[]}
    state={'agent':'langgraph-cost','run_id':'advisory-cycle','telemetry':telemetry}
    monkeypatch.setenv('AI_ACTION_EXECUTION_ENABLED','false')
    monkeypatch.setattr(httpx,'Client',Client)
    monkeypatch.setattr(httpx,'post',lambda *a,**k: pytest.fail('advisory/no-op must not submit'))
    reasoner=Reasoner(AgentDecision(decision='PROPOSE',resource='service-a',proposed_delta=-1,reason='Advisory only.',evidence_references=['resource:service-a'],uncertainties=[]))
    graph=build_agent('cost','http://gateway',reasoner,checkpoint_path=path)
    with checkpoint_owner(path) as token:
        result=graph.invoke(state,config={'configurable':{'thread_id':'advisory','ownership_token':token}})
    graph.checkpointer.conn.close()
    assert result['outcome']['decision']=='advisory' and reasoner.calls==1

    noop_path=str(tmp_path/'noop.sqlite')
    noop=Reasoner(AgentDecision(decision='NO_OP',resource='service-a',proposed_delta=0,reason='No change justified.',evidence_references=['resource:service-a'],uncertainties=[]))
    noop_graph=build_agent('cost','http://gateway',noop,checkpoint_path=noop_path)
    with checkpoint_owner(noop_path) as token:
        result=noop_graph.invoke({**state,'run_id':'noop-cycle'},config={'configurable':{'thread_id':'noop','ownership_token':token}})
    noop_graph.checkpointer.conn.close()
    assert result['outcome']['decision']=='no_change' and noop.calls==1


def test_unresolved_bedrock_invocation_is_not_replayed(tmp_path):
    import pytest
    from botkernel.bedrock import BedrockProviderError
    from botkernel.lang_agents import begin_reasoning,initialize_proposals
    path=str(tmp_path/'unknown-inference.sqlite')
    initialize_proposals(path)
    assert begin_reasoning(path,'ambiguous-run') is None
    with pytest.raises(BedrockProviderError,match='invocation_outcome_unknown'):
        begin_reasoning(path,'ambiguous-run')


def _provider_policy_state(role, provider='ollama_local', delta=-1, **changes):
    capacity=5
    resource='service-a'
    if role=='performance' and delta<0: capacity=5
    proposal={'capacity':capacity+delta,'rationale':'offline policy test','resource':resource,
              'evidence_references':[f'resource:{resource}'],'uncertainties':['offline test data']}
    decision={'decision':'PROPOSE' if delta else 'NO_OP','resource':resource,'proposed_delta':delta,
        'reason':'offline policy test','evidence_references':[f'resource:{resource}'],'uncertainties':['offline test data']}
    state={'agent':f'langgraph-{role}','run_id':'provider-policy-test','telemetry':{
        'id':resource,'capacity':capacity,'version':0,'recent_effects':[],
        'controller_hold':False,'controller_status':'NORMAL','pending_action':False},
        'proposal':proposal,'ai_decision':decision,
        'ai_provenance':{'provider':provider,'model_id':'offline-model','input_tokens':None,'output_tokens':None,'invocations':1},
        'reasoning_provider':provider}
    state.update(changes)
    return state


@pytest.mark.parametrize(('provider','role'),[('bedrock','cost'),('bedrock','performance'),('ollama_local','cost'),('ollama_local','performance')])
def test_model_actions_disabled_are_durable_advisories_without_operational_mutation(tmp_path,monkeypatch,provider,role):
    import json,sqlite3,httpx,pytest
    from sqlalchemy import text
    from botkernel.core import engine
    from botkernel.lang_agents import run_once
    from botkernel.bedrock import AgentDecision

    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',str(tmp_path/f'{provider}.sqlite'))
    monkeypatch.setenv('AI_ACTION_EXECUTION_ENABLED','false')
    monkeypatch.setenv('CLOUD_MODE','mock')
    monkeypatch.setenv('AWS_DEPLOY_ALLOWED','false')
    telemetry={'id':'service-a','capacity':5,'version':7,'latency_p95':60,'recent_effects':[],
               'controller_hold':False,'controller_status':'NORMAL','pending_action':False}
    with engine.connect() as c:
        before_resource=c.execute(text("SELECT capacity,version FROM resources WHERE id='service-a'")).one()
    class Response:
        status_code=200
        def raise_for_status(self): return self
        def json(self): return [telemetry]
    class Session:
        def __init__(self,*a,**kw): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def post(self,*a,**kw): return Response()
        def get(self,*a,**kw): return Response()
    class Reasoner:
        def __init__(self):
            self.name=provider
            self.model_id='offline-model'
            self.model='offline-model'
            self.calls=0
        def decide(self,role,observed,run_id):
            self.calls+=1
            delta=-1 if role=='cost' else 1
            return AgentDecision(decision='PROPOSE',resource='service-a',proposed_delta=delta,reason='advisory only',
                evidence_references=['resource:service-a'],uncertainties=['offline test']),{
                    'provider':provider,'model_id':'offline-model','input_tokens':None,'output_tokens':None,'invocations':1}
        def propose(self,role,observed):
            self.calls+=1
            delta=-1 if role=='cost' else 1
            return Proposal(capacity=observed['capacity']+delta,rationale='advisory only',resource='service-a',
                            evidence_references=['resource:service-a'],uncertainties=['offline test'])
    reasoner=Reasoner()
    monkeypatch.setattr(httpx,'Client',Session)
    monkeypatch.setattr(httpx,'post',lambda *a,**kw: pytest.fail('disabled model decision must not POST'))
    key=f'disabled-{provider}-{role}'
    result=run_once(role,'http://gateway',reasoner=reasoner,run_id=key)
    assert result['outcome']['decision']=='advisory'
    assert 'disabled' in result['outcome']['reason']
    assert reasoner.calls==1
    path=str(tmp_path/f'{provider}.sqlite')
    with sqlite3.connect(path) as c:
        row=c.execute('SELECT status,attempts,provider,last_error,payload FROM agent_proposals WHERE id=?',(key,)).fetchone()
    assert row[:4]==('ADVISORY_ONLY',0,provider,'ai_action_execution_disabled')
    body=json.loads(row[4]); assert body['idempotency_key']==key
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM actions WHERE idempotency_key=:k'),{'k':key}).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM outbox WHERE action_id IN (SELECT id FROM actions WHERE idempotency_key=:k)'),{'k':key}).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM effects WHERE action_id IN (SELECT id FROM actions WHERE idempotency_key=:k)'),{'k':key}).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM receipts WHERE action_id IN (SELECT id FROM actions WHERE idempotency_key=:k)'),{'k':key}).scalar_one()==0
        assert c.execute(text("SELECT capacity,version FROM resources WHERE id='service-a'")).one()==before_resource

    # Reopening the same checkpoint and explicitly replaying the same logical key
    # cannot turn the terminal advisory record into a submission after a flag change.
    monkeypatch.setenv('AI_ACTION_EXECUTION_ENABLED','true')
    monkeypatch.setattr(httpx,'post',lambda *a,**kw: pytest.fail('persisted advisory must never be resubmitted'))
    resumed=run_once(role,'http://gateway',reasoner=reasoner,run_id=key)
    assert resumed['outcome']['decision']=='advisory'
    assert reasoner.calls==1


@pytest.mark.parametrize(('role','delta'),[('cost',1),('performance',-1),('cost',-4),('performance',4)])
def test_common_policy_rejects_model_direction_and_delta_violations(role,delta):
    import pytest
    from botkernel.lang_agents import validate_submission_policy
    with pytest.raises(Exception):
        validate_submission_policy(role,_provider_policy_state(role,delta=delta),'ollama_local')


@pytest.mark.parametrize('changes',[
    {'proposal':{'capacity':4,'rationale':'wrong resource','resource':'service-b','evidence_references':['resource:service-b']}},
    {'ai_decision':{'decision':'PROPOSE','resource':'service-a','proposed_delta':-1,'reason':'forged','evidence_references':['invented-action'],'uncertainties':[]}},
    {'reasoning_provider':'spoofed'},
    {'ai_provenance':{'provider':'bedrock','model_id':'offline-model','invocations':1}},
    {'telemetry':{'id':'service-a','capacity':5,'version':float('nan'),'recent_effects':[]}},
])
def test_common_policy_rejects_unsupported_resource_evidence_and_provenance(changes):
    import pytest
    from botkernel.lang_agents import validate_submission_policy
    state=_provider_policy_state('cost',**changes)
    with pytest.raises(Exception):
        validate_submission_policy('cost',state,'ollama_local')


def test_ollama_contract_rejects_malformed_and_oversized_responses(monkeypatch):
    import httpx,pytest
    from botkernel.lang_agents import OllamaReasoner
    class Response:
        status_code=200
        content=b'x'*16001
        def raise_for_status(self): return self
        def json(self): return {'response':'{}'}
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:Response())
    with pytest.raises(ValueError,match='16 KB'):
        OllamaReasoner('http://offline','model').propose('cost',{'id':'service-a','capacity':5,'recent_effects':[]})
    class Malformed(Response):
        content=b'{}'
        def json(self): return {'unexpected':'value'}
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:Malformed())
    with pytest.raises(ValueError,match='malformed or oversized'):
        OllamaReasoner('http://offline','model').propose('cost',{'id':'service-a','capacity':5,'recent_effects':[]})


def test_enabled_ollama_proposal_still_uses_real_gateway_and_is_bounded(tmp_path,monkeypatch):
    import uuid,httpx
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from botkernel.api import app
    from botkernel.core import engine
    from botkernel.lang_agents import build_agent,checkpoint_owner

    monkeypatch.setenv('AI_ACTION_EXECUTION_ENABLED','true')
    monkeypatch.setenv('CLOUD_MODE','mock')
    monkeypatch.setenv('AWS_DEPLOY_ALLOWED','false')
    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',str(tmp_path/'ollama-enabled.sqlite'))
    resource='provider-test-'+uuid.uuid4().hex[:12]
    with engine.begin() as c:
        c.execute(text('INSERT INTO resources(id,capacity,version) VALUES(:id,4,0)'),{'id':resource})
        c.execute(text('INSERT INTO external_resources(id,capacity) VALUES(:id,4)'),{'id':resource})
        c.execute(text('UPDATE quota SET capacity=100000 WHERE id=1'))
    client=TestClient(app)
    assert client.post('/agents/langgraph-performance').status_code==200
    state={'agent':'langgraph-performance','run_id':'ollama-enabled-cycle','telemetry':{
        'id':resource,'capacity':4,'version':0,'recent_effects':[],'controller_hold':False,
        'controller_status':'NORMAL','pending_action':False},
        'proposal':{'capacity':5,'rationale':'offline mock','resource':resource,
                    'evidence_references':[f'resource:{resource}'],'uncertainties':[]},
        'ai_decision':{'decision':'PROPOSE','resource':resource,'proposed_delta':1,'reason':'offline mock',
                       'evidence_references':[f'resource:{resource}'],'uncertainties':[]},
        'ai_provenance':{'provider':'ollama_local','model_id':'offline-model','input_tokens':None,'output_tokens':None,'invocations':1},
        'reasoning_provider':'ollama_local'}
    monkeypatch.setattr(httpx,'post',lambda url,**kwargs:client.post('/actions',json=kwargs['json']))
    class OfflineOllamaReasoner:
        name='ollama_local'
        model='offline-model'
    graph=build_agent('performance','http://gateway',reasoner=OfflineOllamaReasoner(),checkpoint_path=str(tmp_path/'ollama-enabled.sqlite'))
    try:
        with checkpoint_owner(str(tmp_path/'ollama-enabled.sqlite')) as token:
            result=graph.nodes['submit'].invoke(state,config={'configurable':{'thread_id':'agent-performance','ownership_token':token}})
    finally:
        graph.checkpointer.conn.close()
    assert result['outcome']['decision']=='accepted'
    action_id=result['outcome']['action_id']
    with engine.connect() as c:
        row=c.execute(text('SELECT agent,state,idempotency_key FROM actions WHERE id=:id'),{'id':action_id}).one()
        assert row.agent=='langgraph-performance' and row.state=='RESERVED' and row.idempotency_key=='ollama-enabled-cycle'
        assert c.execute(text('SELECT count(*) FROM outbox WHERE action_id=:id'),{'id':action_id}).scalar_one()==1
        assert c.execute(text('SELECT count(*) FROM effects WHERE action_id=:id'),{'id':action_id}).scalar_one()==0
        assert c.execute(text('SELECT capacity,version FROM resources WHERE id=:id'),{'id':resource}).one()==(4,0)


def test_model_controller_hold_is_blocked_before_gateway(tmp_path,monkeypatch):
    import httpx,pytest,sqlite3
    from botkernel.lang_agents import build_agent,checkpoint_owner
    monkeypatch.setenv('AI_ACTION_EXECUTION_ENABLED','true')
    monkeypatch.setenv('CLOUD_MODE','mock')
    monkeypatch.setenv('AWS_DEPLOY_ALLOWED','false')
    path=str(tmp_path/'held-model.sqlite')
    state=_provider_policy_state('cost',telemetry={'id':'service-a','capacity':5,'version':0,'recent_effects':[],
        'controller_hold':True,'controller_status':'HOLD','pending_action':False})
    class OfflineOllamaReasoner:
        name='ollama_local'
        model='offline-model'
    graph=build_agent('cost','http://gateway',reasoner=OfflineOllamaReasoner(),checkpoint_path=path)
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:pytest.fail('controller hold must block before POST'))
    try:
        with checkpoint_owner(path) as token:
            result=graph.nodes['submit'].invoke(state,config={'configurable':{'thread_id':'agent-cost','ownership_token':token}})
    finally:
        graph.checkpointer.conn.close()
    assert result['outcome']['decision']=='blocked'
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT status,last_error,attempts FROM agent_proposals').fetchone()==('POLICY_BLOCKED','controller_hold_or_pending_action',0)


def test_provider_change_on_checkpointed_proposal_fails_closed(tmp_path):
    import pytest
    from botkernel.lang_agents import validate_submission_policy
    state=_provider_policy_state('cost')
    with pytest.raises(ValueError,match='provider'):
        validate_submission_policy('cost',state,'bedrock')


def test_zero_invocation_provenance_is_only_valid_for_bedrock_policy_noop():
    import pytest
    from botkernel.lang_agents import validate_submission_policy
    state=_provider_policy_state('cost','bedrock',0)
    state['ai_provenance']={'provider':'bedrock','model_id':'offline-model','input_tokens':0,'output_tokens':0,'invocations':0}
    assert validate_submission_policy('cost',state,'bedrock')[1].decision=='NO_OP'
    ollama=_provider_policy_state('cost','ollama_local',0)
    ollama['ai_provenance']['invocations']=0
    with pytest.raises(ValueError,match='invocation provenance'):
        validate_submission_policy('cost',ollama,'ollama_local')


def test_bedrock_reasoning_failure_is_not_replaced_by_deterministic_policy(tmp_path,monkeypatch):
    import sqlite3
    from botkernel.bedrock import BedrockProviderError
    from botkernel.lang_agents import build_agent

    class FailingReasoner:
        name='bedrock'
        model_id='offline-failure-test'
        def decide(self,*args):
            raise BedrockProviderError('access_denied')

    monkeypatch.setattr('botkernel.lang_agents.MockReasoner',
                        lambda: pytest.fail('must not fall back to deterministic reasoning'))
    path=str(tmp_path/'failed-bedrock.sqlite')
    graph=build_agent('cost',reasoner=FailingReasoner(),checkpoint_path=path)
    try:
        with pytest.raises(BedrockProviderError,match='access_denied'):
            graph.nodes['analyze'].invoke({
                'agent':'langgraph-cost','run_id':'one-shot-failure',
                'telemetry':{'id':'isolated','capacity':5,'version':0,'recent_effects':[]},
            })
    finally:
        graph.checkpointer.conn.close()
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            'SELECT status,error_category FROM agent_reasoning WHERE run_id=?',
            ('one-shot-failure',),
        ).fetchone()==('FAILED','access_denied')


@pytest.mark.parametrize('role',['cost','performance'])
def test_bedrock_agent_uses_local_simulator_telemetry_and_persists_advisory_only(
        tmp_path,monkeypatch,role):
    import json,sqlite3,httpx
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from botkernel.api import app
    from botkernel.core import engine
    from botkernel.bedrock import AgentDecision
    from botkernel.lang_agents import run_once

    monkeypatch.setenv('BOTKERNEL_AGENT_CHECKPOINTS',str(tmp_path/f'{role}.sqlite'))
    monkeypatch.setenv('AI_ACTION_EXECUTION_ENABLED','false')
    monkeypatch.setenv('CLOUD_MODE','mock')
    monkeypatch.setenv('AWS_DEPLOY_ALLOWED','false')
    monkeypatch.setenv('BEDROCK_ENABLED','false')
    monkeypatch.setenv('BEDROCK_SPEND_AUTHORIZED','false')
    client=TestClient(app)
    resource=f'bedrock-local-{role}'
    monkeypatch.setenv('BOTKERNEL_AGENT_RESOURCE',resource)
    with engine.begin() as c:
        c.execute(text('INSERT INTO resources(id,capacity,version) VALUES(:id,3,0)'),{'id':resource})
        c.execute(text('INSERT INTO external_resources(id,capacity) VALUES(:id,3)'),{'id':resource})
    with engine.connect() as c:
        before=c.execute(text('SELECT capacity,version FROM resources WHERE id=:id'),{'id':resource}).one()
    key=f'offline-bedrock-{role}'

    class LocalApiSession:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,path,**kwargs): return client.post(path,**kwargs)
        def get(self,path,**kwargs): return client.get(path,**kwargs)

    class MockBedrockReasoner:
        name='bedrock'
        model_id='offline-contract-test'
        def __init__(self): self.calls=0; self.observed=None
        def decide(self,agent_role,telemetry,run_id):
            self.calls+=1; self.observed=telemetry
            delta=(-1 if telemetry['capacity']>1 else 0) if agent_role=='cost' else (1 if telemetry['latency_p95']>80 and telemetry['capacity']<20 else 0)
            return AgentDecision(
                decision='PROPOSE' if delta else 'NO_OP',resource=telemetry['id'],
                proposed_delta=delta,reason='Offline contract-test decision from simulator telemetry.',
                evidence_references=[f"resource:{telemetry['id']}"],uncertainties=['Mock provider; no model call.']),{
                    'provider':'bedrock','model_id':self.model_id,'input_tokens':117,
                    'output_tokens':23,'invocations':1}

    reasoner=MockBedrockReasoner()
    monkeypatch.setattr(httpx,'Client',LocalApiSession)
    monkeypatch.setattr(httpx,'post',lambda *args,**kwargs: pytest.fail('AI execution is disabled; gateway POST is forbidden'))
    result=run_once(role,'http://local-test-api',reasoner=reasoner,run_id=key)
    assert reasoner.calls==1
    assert reasoner.observed['simulated'] is True
    assert reasoner.observed['id']==resource
    assert result['reasoning_provider']=='bedrock'
    assert result['ai_provenance']['model_id']=='offline-contract-test'
    assert result['ai_provenance']['input_tokens']==117
    assert result['ai_provenance']['output_tokens']==23
    if reasoner.observed['capacity']>1 and (role=='cost' or reasoner.observed['latency_p95']>80):
        assert result['outcome']['decision']=='advisory'
    else:
        assert result['outcome']['decision']=='no_change'

    path=tmp_path/f'{role}.sqlite'
    with sqlite3.connect(path) as c:
        stored=c.execute('SELECT status,result_json,provenance_json FROM agent_reasoning WHERE run_id=?',(key,)).fetchone()
        proposal=c.execute('SELECT status,attempts,last_error FROM agent_proposals WHERE id=?',(key,)).fetchone()
    assert stored[0]=='COMPLETED'
    assert json.loads(stored[2])['model_id']=='offline-contract-test'
    assert json.loads(stored[2])['invocations']==1
    if result['outcome']['decision']=='advisory':
        assert proposal==('ADVISORY_ONLY',0,'ai_action_execution_disabled')
    else:
        assert proposal is None
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM actions WHERE idempotency_key=:k'),{'k':key}).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM outbox WHERE action_id IN (SELECT id FROM actions WHERE idempotency_key=:k)'),{'k':key}).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM effects WHERE action_id IN (SELECT id FROM actions WHERE idempotency_key=:k)'),{'k':key}).scalar_one()==0
        assert c.execute(text('SELECT capacity,version FROM resources WHERE id=:id'),{'id':resource}).one()==before
