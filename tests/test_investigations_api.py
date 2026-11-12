from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import text
from botkernel.api import app
from botkernel.core import engine


def test_persistence_idempotency_concurrency_and_readonly():
    with engine.begin() as c:
        c.execute(text("INSERT INTO resources VALUES('invest-api',4,0)"))
        c.execute(text("INSERT INTO external_resources VALUES('invest-api',4)"))
        incident=c.execute(text("INSERT INTO incidents(resource,score,evidence) VALUES('invest-api',0.8,CAST('{}' AS jsonb)) RETURNING id")).scalar_one()
        before=c.execute(text("SELECT * FROM incidents WHERE id=:id"),{'id':incident}).one()
    client=TestClient(app)
    def post(): return client.post(f'/incidents/{incident}/investigations',json={'idempotency_key':'same-key'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:post(),range(2)))
    assert all(r.status_code==200 for r in responses)
    ids={r.json()['id'] for r in responses}; assert len(ids)==1
    ident=ids.pop(); final=client.get('/investigations/'+ident)
    assert final.status_code==200
    assert final.json()['status']=='INSUFFICIENT_EVIDENCE'
    assert client.post(f'/incidents/{incident}/investigations',json={'idempotency_key':'same-key'}).json()['id']==ident
    assert client.get(f'/incidents/{incident}/investigations').json()[0]['id']==ident
    assert client.get('/investigations/00000000-0000-0000-0000-000000000000').status_code==404
    assert client.post('/incidents/999999999/investigations',json={'idempotency_key':'x'}).status_code==404
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM investigation_reports WHERE incident_id=:id'),{'id':incident}).scalar_one()==1
        assert c.execute(text('SELECT * FROM incidents WHERE id=:id'),{'id':incident}).one()==before
        assert c.execute(text("SELECT capacity,version FROM resources WHERE id='invest-api'")).one()==(4,0)


def test_expired_lease_is_failed_without_rerunning():
    import uuid, hashlib, json
    key='expired'; fingerprint=hashlib.sha256(json.dumps({'provider':'deterministic_mock'},sort_keys=True).encode()).hexdigest()
    with engine.begin() as c:
        c.execute(text("INSERT INTO resources VALUES('invest-expired',4,0)"))
        incident=c.execute(text("INSERT INTO incidents(resource,score,evidence) VALUES('invest-expired',0.8,CAST('{}' AS jsonb)) RETURNING id")).scalar_one()
        ident=str(uuid.uuid4())
        c.execute(text("INSERT INTO investigation_reports(id,incident_id,idempotency_key,request_fingerprint,status,provider,lease_token,lease_until) VALUES(:id,:incident,:key,:fingerprint,'RUNNING','deterministic_mock',:token,now()-interval '1 second')"),dict(id=ident,incident=incident,key=key,fingerprint=fingerprint,token=str(uuid.uuid4())))
    client=TestClient(app)
    r=client.post(f'/incidents/{incident}/investigations',json={'idempotency_key':key})
    assert r.status_code==200
    assert r.json()['id']==ident
    assert r.json()['status']=='FAILED'
    assert r.json()['error_category']=='lease_expired'
    assert client.post(f'/incidents/{incident}/investigations',json={'idempotency_key':key}).json()['status']=='FAILED'


def test_key_conflict_is_explicit():
    from botkernel.investigation_service import start, Conflict
    import pytest, uuid
    with engine.begin() as c:
        c.execute(text("INSERT INTO resources VALUES('invest-conflict',4,0)"))
        incident=c.execute(text("INSERT INTO incidents(resource,score,evidence) VALUES('invest-conflict',0.8,CAST('{}' AS jsonb)) RETURNING id")).scalar_one()
        c.execute(text("INSERT INTO investigation_reports(id,incident_id,idempotency_key,request_fingerprint,status,provider,lease_token,lease_until) VALUES(:id,:incident,'key',:fingerprint,'RUNNING','deterministic_mock',:token,now()+interval '1 minute')"),dict(id=str(uuid.uuid4()),incident=incident,fingerprint='0'*64,token=str(uuid.uuid4())))
    with pytest.raises(Conflict): start(incident,'key','deterministic_mock')


def test_independent_process_slots_return_busy_and_release():
    import os, subprocess, sys
    with engine.begin() as c:
        c.execute(text("INSERT INTO resources VALUES('invest-slots',4,0)"))
        incident=c.execute(text("INSERT INTO incidents(resource,score,evidence) VALUES('invest-slots',0.8,CAST('{}' AS jsonb)) RETURNING id")).scalar_one()
    code="from botkernel.core import engine; from sqlalchemy import text; import sys; c=engine.connect(); c.execute(text('select pg_advisory_lock(781239,0),pg_advisory_lock(781239,1)')); c.commit(); print('ready',flush=True); sys.stdin.readline(); c.close()"
    owner=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=os.environ.copy())
    try:
        assert owner.stdout.readline().strip()=='ready'
        client=TestClient(app)
        busy=client.post(f'/incidents/{incident}/investigations',json={'idempotency_key':'slots-busy'})
        assert busy.status_code==503
        with engine.connect() as c: assert c.execute(text('SELECT count(*) FROM investigation_reports WHERE incident_id=:id'),{'id':incident}).scalar_one()==0
        owner.terminate(); owner.wait(timeout=10)
        result=client.post(f'/incidents/{incident}/investigations',json={'idempotency_key':'slots-busy'})
        assert result.status_code==200
        assert result.json()['status']=='INSUFFICIENT_EVIDENCE'
    finally:
        if owner.poll() is None: owner.terminate(); owner.wait(timeout=10)


def test_two_real_graphs_across_processes_busy_and_duplicate():
    import os,sys,subprocess,select,json
    with engine.begin() as c:
        ids=[]
        for i in range(3):
            resource=f'invest-real-slots-{i}'
            c.execute(text('INSERT INTO resources(id,capacity,version) VALUES(:r,4,0)'),{'r':resource})
            ids.append(c.execute(text("INSERT INTO incidents(resource,score,evidence) VALUES(:r,0.8,CAST('{}' AS jsonb)) RETURNING id"),{'r':resource}).scalar_one())
    code="""import sys,json
import botkernel.investigation_service as service
from langchain_core.callbacks import BaseCallbackHandler
real=service.investigation_graph
class NodeBarrier(BaseCallbackHandler):
 def on_chain_start(self,serialized,inputs,*,name=None,**kwargs):
  if name=='load_incident':
   print('READY',flush=True)
   sys.stdin.readline()
class Barrier:
 def invoke(self,state):
  return real.invoke(state,config={'callbacks':[NodeBarrier()]})
service.investigation_graph=Barrier()
r=service.start(int(sys.argv[1]),sys.argv[2],'deterministic_mock')
print('DONE '+json.dumps({'id':str(r['id']),'status':r['status']}),flush=True)
"""
    processes=[subprocess.Popen([sys.executable,'-c',code,str(ids[i]),f'key-{i}'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=os.environ.copy()) for i in range(2)]
    def line(proc):
        assert select.select([proc.stdout],[],[],20)[0], 'graph barrier timed out'
        return proc.stdout.readline().strip()
    try:
        assert [line(p) for p in processes]==['READY','READY']
        client=TestClient(app)
        duplicate=client.post(f'/incidents/{ids[0]}/investigations',json={'idempotency_key':'key-0'})
        assert duplicate.status_code==200 and duplicate.json()['status']=='RUNNING'
        third=client.post(f'/incidents/{ids[2]}/investigations',json={'idempotency_key':'key-2'})
        assert third.status_code==503 and third.headers['retry-after']=='2'
        with engine.connect() as c:
            assert c.execute(text("SELECT count(*) FROM investigation_reports WHERE incident_id=ANY(:ids) AND status='RUNNING'"),{'ids':ids}).scalar_one()==2
            assert c.execute(text("SELECT count(*) FROM investigation_reports WHERE incident_id=:id"),{'id':ids[2]}).scalar_one()==0
        processes[0].stdin.write('continue\n'); processes[0].stdin.flush()
        first=json.loads(line(processes[0]).removeprefix('DONE '))
        assert first['id']==duplicate.json()['id'] and first['status']=='INSUFFICIENT_EVIDENCE'
        admitted=client.post(f'/incidents/{ids[2]}/investigations',json={'idempotency_key':'key-2'})
        assert admitted.status_code==200 and admitted.json()['status']=='INSUFFICIENT_EVIDENCE'
        processes[1].stdin.write('continue\n'); processes[1].stdin.flush()
        second=json.loads(line(processes[1]).removeprefix('DONE '))
        assert second['status']=='INSUFFICIENT_EVIDENCE' and second['id']!=first['id']
        for p in processes: assert p.wait(timeout=10)==0
    finally:
        for p in processes:
            if p.poll() is None: p.terminate(); p.wait(timeout=10)


def test_lost_slot_session_and_expired_lease_fence_old_graph():
    import os,sys,subprocess,select,json
    with engine.begin() as c:
        ids=[]
        for i in range(2):
            resource=f'invest-session-loss-{i}'
            c.execute(text('INSERT INTO resources(id,capacity,version) VALUES(:r,4,0)'),{'r':resource})
            ids.append(c.execute(text("INSERT INTO incidents(resource,score,evidence) VALUES(:r,0.8,CAST('{}' AS jsonb)) RETURNING id"),{'r':resource}).scalar_one())
    code="""import sys,json
import botkernel.investigation_service as service
from langchain_core.callbacks import BaseCallbackHandler
real=service.investigation_graph
class NodeBarrier(BaseCallbackHandler):
 def on_chain_start(self,serialized,inputs,*,name=None,**kwargs):
  if name=='load_incident':
   print('READY',flush=True); sys.stdin.readline()
class Barrier:
 def invoke(self,state): return real.invoke(state,config={'callbacks':[NodeBarrier()]})
service.investigation_graph=Barrier()
r=service.start(int(sys.argv[1]),'lost-session','deterministic_mock')
print('DONE '+json.dumps({'id':str(r['id']),'status':r['status']}),flush=True)
"""
    proc=subprocess.Popen([sys.executable,'-c',code,str(ids[0])],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=os.environ.copy())
    try:
        assert select.select([proc.stdout],[],[],20)[0] and proc.stdout.readline().strip()=='READY'
        with engine.begin() as c:
            pid=c.execute(text("SELECT pid FROM pg_locks WHERE locktype='advisory' AND classid=781239 AND database=(SELECT oid FROM pg_database WHERE datname=current_database()) AND granted")).scalar_one()
            assert c.execute(text('SELECT pg_terminate_backend(:pid)'),{'pid':pid}).scalar_one()
            c.execute(text("UPDATE investigation_reports SET lease_until=now()-interval '1 second' WHERE incident_id=:id"),{'id':ids[0]})
        client=TestClient(app)
        old=client.post(f'/incidents/{ids[0]}/investigations',json={'idempotency_key':'lost-session'})
        assert old.json()['status']=='FAILED' and old.json()['error_category']=='lease_expired'
        newer=client.post(f'/incidents/{ids[1]}/investigations',json={'idempotency_key':'other'})
        assert newer.status_code==200 and newer.json()['status']=='INSUFFICIENT_EVIDENCE'
        proc.stdin.write('continue\n');proc.stdin.flush()
        assert select.select([proc.stdout],[],[],20)[0]
        finished=json.loads(proc.stdout.readline().strip().removeprefix('DONE '))
        assert finished['id']==old.json()['id'] and finished['status']=='FAILED'
        assert proc.wait(timeout=10)==0
        assert client.get('/investigations/'+finished['id']).json()['status']=='FAILED'
    finally:
        if proc.poll() is None: proc.terminate();proc.wait(timeout=10)


def test_bedrock_investigation_mock_uses_controller_evidence_and_persists_readonly_report(monkeypatch):
    import uuid
    from botkernel.api import Action, app
    from botkernel.bedrock import InvestigationAnalysis
    from botkernel.core import admit, execute
    from botkernel.stability import tick

    resource='bedrock-offline-'+uuid.uuid4().hex[:12]
    monkeypatch.setenv('BEDROCK_ENABLED','false')
    monkeypatch.setenv('BEDROCK_SPEND_AUTHORIZED','false')
    monkeypatch.setenv('AI_ACTION_EXECUTION_ENABLED','false')
    monkeypatch.setenv('CLOUD_MODE','mock')
    monkeypatch.setenv('AWS_DEPLOY_ALLOWED','false')
    with engine.begin() as c:
        c.execute(text('UPDATE quota SET capacity=200 WHERE id=1'))
        c.execute(text('INSERT INTO resources(id,capacity,version) VALUES(:r,4,0)'),{'r':resource})
        c.execute(text('INSERT INTO external_resources(id,capacity) VALUES(:r,4)'),{'r':resource})
        for agent in ('cost-graph','performance-graph'):
            c.execute(text('INSERT INTO agents(id) VALUES(:id) ON CONFLICT(id) DO NOTHING'),{'id':agent})
    for index,target in enumerate((3,4,3,4)):
        action_id=admit(Action(
            agent='cost-graph' if target==3 else 'performance-graph',
            workflow='offline-bedrock-investigation-test',
            idempotency_key=f'{resource}-{index}',resource=resource,
            expected_version=index,capacity=target,risk='low'))
        execute(action_id)
        execute(action_id)
    tick()
    with engine.connect() as c:
        incident=c.execute(text("SELECT id FROM incidents WHERE resource=:r ORDER BY opened_at DESC LIMIT 1"),{'r':resource}).scalar_one()

    from botkernel.core import engine as db_engine
    def operational_snapshot():
        queries={
            'resources':("SELECT row_to_json(t)::text FROM resources t WHERE id=:r ORDER BY id",{'r':resource}),
            'actions':("SELECT row_to_json(t)::text FROM actions t WHERE resource=:r ORDER BY id",{'r':resource}),
            'effects':("SELECT row_to_json(t)::text FROM effects t WHERE resource=:r ORDER BY version",{'r':resource}),
            'outbox':("SELECT row_to_json(t)::text FROM outbox t WHERE action_id IN (SELECT id FROM actions WHERE resource=:r) ORDER BY id",{'r':resource}),
            'receipts':("SELECT row_to_json(t)::text FROM receipts t WHERE action_id IN (SELECT id FROM actions WHERE resource=:r) ORDER BY action_id",{'r':resource}),
            'incidents':("SELECT row_to_json(t)::text FROM incidents t WHERE id=:id",{'id':incident}),
            'transitions':("SELECT row_to_json(t)::text FROM incident_transitions t WHERE incident_id=:id ORDER BY id",{'id':incident}),
            'operator_actions':("SELECT row_to_json(t)::text FROM incident_operator_actions t WHERE incident_id=:id ORDER BY id",{'id':incident}),
            'quota':("SELECT row_to_json(t)::text FROM quota t WHERE id=1",{}),
        }
        with db_engine.connect() as c:
            return {name:c.execute(text(sql),params).scalars().all() for name,(sql,params) in queries.items()}

    before=operational_snapshot()
    class MockConverse:
        def __init__(self): self.calls=[]
        def invoke_json(self,**kwargs):
            self.calls.append(kwargs)
            supplied=kwargs['payload']
            effect_ids=[effect['action_id'] for effect in supplied['effects']]
            assert len(effect_ids)>=4
            analysis=InvestigationAnalysis(
                explanation='Committed capacity changes from both agents are present in the supplied record.',
                hypotheses=['Independent optimization goals may have contributed; causation is not established.'],
                cross_agent_analysis='The evidence includes changes by both contributing agents.',
                instability_mechanism='Adjacent opposite changes can indicate a reversal pattern.',
                supporting_references=[effect_ids[0],f"incident:{supplied['incident']['id']}"],
                contradictory_or_missing_evidence=[],
                preventive_actions=['Review the existing controller hold before operator action.'],
                confidence_caveats=['This analysis is an offline provider contract test; temporal sequence does not prove causation.'])
            return analysis,{'provider':'bedrock','model_id':'offline-test-nova-micro',
                            'input_tokens':321,'output_tokens':88,'invocations':1}

    fake=MockConverse()
    monkeypatch.setattr('botkernel.bedrock.BedrockConverse',lambda:fake)
    client=TestClient(app)
    request={'idempotency_key':f'offline-bedrock-report-{uuid.uuid4()}','provider':'bedrock'}
    response=client.post(f'/incidents/{incident}/investigations',json=request)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['status']=='COMPLETE'
    assert result['provider']=='bedrock'
    assert result['report']['model_id']=='offline-test-nova-micro'
    assert result['report']['usage']['input_tokens']==321
    assert result['report']['usage']['output_tokens']==88
    assert result['report']['usage']['invocations']==1
    assert result['report']['ai_analysis']['hypotheses']
    assert result['report']['findings'][-1]['classification']=='HYPOTHESIS'
    expected_refs={effect['action_id'] for effect in result['report']['effects']}
    assert all(ref in expected_refs or ref==f'incident:{incident}'
               for ref in result['report']['ai_analysis']['supporting_references'])
    assert len(fake.calls)==1
    assert client.get('/investigations/'+result['id']).json()==result

    replay=client.post(f'/incidents/{incident}/investigations',json=request)
    assert replay.status_code==200 and replay.json()==result
    assert len(fake.calls)==1
    assert operational_snapshot()==before
