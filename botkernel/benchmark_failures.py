"""Bounded publisher faults; run only when benchmark-owned app workers are stopped."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import httpx
from sqlalchemy import text
from botkernel.core import engine
from botkernel.benchmark_runtime import validate_environment
from botkernel.real_benchmark_recovery import snapshot
from botkernel.security import operator_headers


def run(mode):
    validate_environment(engine.url.database)
    if mode not in ('publisher_crash', 'publisher_pause'):
        raise ValueError('Unsupported bounded fault')
    identity = 'fault-' + uuid.uuid4().hex
    folder = Path('/results') / identity
    folder.mkdir()
    with engine.begin() as c:
        quota = c.execute(text('SELECT capacity FROM quota WHERE id=1 FOR UPDATE')).scalar_one()
        total = c.execute(text('SELECT SUM(capacity) FROM resources')).scalar_one()
        if total + 2 > quota:
            raise RuntimeError('Insufficient fixture capacity; never raise quota to force a fault case')
        c.execute(text('INSERT INTO agents(id) VALUES (:id)'), {'id':identity})
        c.execute(text('INSERT INTO resources(id,capacity) VALUES (:id,1)'), {'id':identity})
        c.execute(text('INSERT INTO external_resources(id,capacity) VALUES (:id,1)'), {'id':identity})
    processes, logs = [], []
    env = {k:v for k,v in os.environ.items() if not k.startswith('CRASH_')}
    env['METRICS_ENABLED'] = 'false'
    def launch(role, fault=False):
        log = (folder / (role + ('-crash' if fault else '-normal') + '.log')).open('w')
        logs.append(log)
        child = subprocess.Popen([sys.executable,'-m','botkernel.worker'],
            env={**env,'ROLE':role, **({'CRASH_AFTER_PUBLISH':'true'} if fault else {})},
            stdout=log,stderr=log)
        processes.append(child)
        return child
    try:
        with httpx.Client(base_url=os.environ['BOTKERNEL_BENCHMARK_API_URL'],
                          headers=operator_headers(),timeout=10) as client:
            response=client.post('/actions',json={'agent':identity,'workflow':'benchmark-'+mode,
                'idempotency_key':identity,'resource':identity,'expected_version':0,'capacity':2})
            response.raise_for_status(); action_id=response.json()['id']
        before=snapshot(action_id,identity)
        assert before['state']=='RESERVED' and before['receipts']==before['effects']==0
        if mode=='publisher_crash':
            crashed=launch('publisher',True)
            code=crashed.wait(timeout=60)
            assert code==18
            before=snapshot(action_id,identity)
            assert not before['published'] and before['effects']==0
        else:
            time.sleep(1)
            assert snapshot(action_id,identity)==before
            code=None
        recovery_started=time.monotonic()
        launch('publisher');launch('worker')
        deadline=time.monotonic()+75
        while time.monotonic()<deadline:
            after=snapshot(action_id,identity)
            if after['state']=='SUCCEEDED' and after['published']: break
            if any(p.poll() is not None for p in processes if p is not processes[0] or mode!='publisher_crash'):
                raise RuntimeError('Normal recovery process exited unexpectedly')
            time.sleep(.1)
        else: raise TimeoutError('Bounded publisher recovery timed out')
        recovered_seconds=time.monotonic()-recovery_started
        minimum_deliveries=2 if mode=='publisher_crash' else 1
        deadline=time.monotonic()+15
        deliveries=0
        while time.monotonic()<deadline:
            deliveries=sum(action_id in line and 'kafka_event_handled' in line
                for line in (folder/'worker-normal.log').read_text().splitlines())
            if deliveries>=minimum_deliveries: break
            time.sleep(.2)
        assert after['receipts']==after['effects']==after['version']==1
        assert deliveries>=minimum_deliveries
        result={'case':mode,'action_id':action_id,'resource':identity,'crash_exit_code':code,
                'before_recovery':before,'after_recovery':after,'handled_log_entries':deliveries,
                'recovery_seconds':round(recovered_seconds,3),
                'timing':'monotonic from restart launch, excludes intentional 1s publisher pause',
                'unresolved':0}
        (folder/'recovery.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result));return result
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
        for log in logs:log.close()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['publisher_crash','publisher_pause'],required=True)
    run(parser.parse_args().mode)
