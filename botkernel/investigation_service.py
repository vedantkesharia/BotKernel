"""Idempotent investigation execution; lease ownership fences stale workers."""
import hashlib, json, uuid, os
from sqlalchemy import text
from botkernel.core import engine
from botkernel.investigator import Investigation, investigation_graph
from botkernel.investigation_process import execute, execution_limits, InvestigationTimeout

class MissingIncident(Exception): pass
class Conflict(Exception): pass
class Busy(Exception): pass


def start(incident_id, key, provider):
    deadline, grace = execution_limits()
    fingerprint=hashlib.sha256(json.dumps({'provider':provider},sort_keys=True).encode()).hexdigest()
    token=str(uuid.uuid4()); report_id=str(uuid.uuid4())
    slot_connection=engine.connect()
    slot=None
    try:
      with slot_connection.begin():
        c=slot_connection
        c.execute(text("SET LOCAL lock_timeout='3s'"))
        if not c.execute(text('SELECT 1 FROM incidents WHERE id=:id'),{'id':incident_id}).first(): raise MissingIncident()
        c.execute(text("INSERT INTO investigation_reports(id,incident_id,idempotency_key,request_fingerprint,status,provider,lease_token,lease_until) VALUES(:id,:incident,:key,:fingerprint,'RUNNING',:provider,:token,now()+interval '60 seconds') ON CONFLICT (incident_id,idempotency_key) DO NOTHING"),dict(id=report_id,incident=incident_id,key=key,fingerprint=fingerprint,provider=provider,token=token))
        row=c.execute(text('SELECT *,lease_until<now() AS expired FROM investigation_reports WHERE incident_id=:incident AND idempotency_key=:key FOR UPDATE'),dict(incident=incident_id,key=key)).mappings().one()
        if row['request_fingerprint']!=fingerprint: raise Conflict()
        if str(row['lease_token'])!=token:
            if row['status']=='RUNNING' and row['expired']:
                c.execute(text("UPDATE investigation_reports SET status='FAILED',error_category='lease_expired',completed_at=now(),lease_token=NULL,lease_until=NULL WHERE id=:id"),{'id':row['id']})
                return {**dict(row), 'status':'FAILED','error_category':'lease_expired','completed_at':c.execute(text('SELECT now()')).scalar_one()}
            return dict(row)
        report_id=str(row['id'])
        limit=int(os.getenv('INVESTIGATION_MAX_CONCURRENT','2'))
        if not 1 <= limit <= 16: raise ValueError('INVESTIGATION_MAX_CONCURRENT must be 1..16')
        for index in range(limit):
            if c.execute(text('SELECT pg_try_advisory_lock(781239, :slot)'), {'slot':index}).scalar_one():
                slot=index
                break
        if slot is None: raise Busy()
      result=execute(incident_id,provider,report_id,deadline,grace)
      if 'error_category' in result:
          from botkernel.bedrock import BedrockProviderError
          raise BedrockProviderError(result['error_category'])
      payload=result['report']
      payload=Investigation.model_validate(payload).model_dump(mode='json')
      encoded=json.dumps(payload,ensure_ascii=False)
      if len(encoded.encode('utf-8'))>200000: raise ValueError('report too large')
      with engine.begin() as c:
          c.execute(text("UPDATE investigation_reports SET status=:status,report=CAST(:report AS jsonb),completed_at=now(),lease_token=NULL,lease_until=NULL WHERE id=:id AND lease_token=:token AND status='RUNNING' AND lease_until>now()"),dict(status=payload['outcome'],report=encoded,id=report_id,token=token))
    except (MissingIncident, Conflict, Busy):
        raise
    except Exception as error:
        if slot is None: raise
        from botkernel.bedrock import BedrockProviderError
        error_category=('execution_timeout' if isinstance(error,InvestigationTimeout)
                        else error.category if isinstance(error,BedrockProviderError) else 'execution_error')
        with engine.begin() as c:
            c.execute(text("UPDATE investigation_reports SET status='FAILED',error_category=:category,completed_at=now(),lease_token=NULL,lease_until=NULL WHERE id=:id AND lease_token=:token AND status='RUNNING'"),dict(id=report_id,token=token,category=error_category))
    finally:
        if slot is not None:
            try:
                slot_connection.execute(text('SELECT pg_advisory_unlock(781239, :slot)'), {'slot':slot})
                slot_connection.commit()
            except Exception:
                slot_connection.invalidate()
        slot_connection.close()
    return get(report_id)

def get(report_id):
    with engine.connect() as c:
        row=c.execute(text('SELECT id,incident_id,status,provider,report,error_category,created_at,completed_at FROM investigation_reports WHERE id=:id'),{'id':report_id}).mappings().first()
        return dict(row) if row else None

def list_reports(incident_id):
    with engine.connect() as c:
        return [dict(row) for row in c.execute(text('SELECT id,incident_id,status,provider,report,error_category,created_at,completed_at FROM investigation_reports WHERE incident_id=:id ORDER BY created_at DESC LIMIT 100'),{'id':incident_id}).mappings()]
