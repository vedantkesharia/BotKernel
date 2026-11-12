import uuid

from sqlalchemy import text

from botkernel.core import engine, admit, execute
from botkernel.api import Action
from botkernel.stability import graph, latency, score, tick
import pytest


def _operator_incident(resource, status):
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO resources VALUES(:id,6,0)"), {"id": resource})
        connection.execute(text("INSERT INTO external_resources VALUES(:id,6)"), {"id": resource})
        return connection.execute(
            text(
                "INSERT INTO incidents(resource,score,last_score,evidence,status,monitor_started_at) "
                "VALUES(:resource,.9,.9,'{\"lifecycle\":[]}'::jsonb,:status,now()-interval '10 seconds') "
                "RETURNING id"
            ),
            {"resource": resource, "status": status},
        ).scalar_one()


def _oscillate(resource, targets=(3, 4, 3, 4)):
    with engine.begin() as connection:
        connection.execute(text("UPDATE quota SET capacity=200 WHERE id=1"))
        for agent in ("cost-graph", "performance-graph"):
            connection.execute(text("INSERT INTO agents(id) VALUES(:id) ON CONFLICT DO NOTHING"), {"id": agent})
        version = connection.execute(
            text("SELECT version FROM resources WHERE id=:resource"), {"resource": resource}
        ).scalar_one()
    for offset, target in enumerate(targets):
        aid = admit(
            Action(
                agent="cost-graph" if target == 3 else "performance-graph",
                workflow="graph",
                idempotency_key=f"{resource}-{uuid.uuid4()}",
                resource=resource,
                expected_version=version + offset,
                capacity=target,
            )
        )
        execute(aid)
        execute(aid)


def _incident(resource):
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT * FROM incidents WHERE resource=:resource"), {"resource": resource}
        ).mappings().one()


def _scale_up(resource):
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT version FROM resources WHERE id=:resource"), {"resource": resource}
        ).scalar_one()
    aid = admit(
        Action(
            agent="performance-graph",
            workflow="recovery",
            idempotency_key=f"{resource}-scale-up-{uuid.uuid4()}",
            resource=resource,
            expected_version=version,
            capacity=6,
        )
    )
    execute(aid)


def test_repeated_oscillation_creates_one_selective_hold_and_replay_stays_idempotent():
    with engine.begin() as c:
        c.execute(text("UPDATE quota SET capacity=40 WHERE id=1"))
        c.execute(text("INSERT INTO resources VALUES('graph-service',4,0)"))
        c.execute(text("INSERT INTO external_resources VALUES('graph-service',4)"))
    _oscillate("graph-service")
    evidence = graph(resource="graph-service")["evidence"]
    assert len(evidence) == 4
    assert sum(edge["inferred"] for edge in graph(resource="graph-service")["edges"]) == 3
    tick()
    tick()
    incident = _incident("graph-service")
    assert incident["status"] == "HOLD"
    assert incident["intervention_count"] == 1
    with engine.connect() as connection:
        transitions = dict(connection.execute(
            text("SELECT transition,count(*) FROM incident_transitions WHERE incident_id=:id GROUP BY transition"),
            {"id": incident["id"]},
        ).all())
    assert transitions == {"detected": 1, "hold_applied": 1}
    with pytest.raises(ValueError, match="scale-down restricted"):
        admit(Action(agent="cost-graph", workflow="graph", idempotency_key="held", resource="graph-service", expected_version=4, capacity=3))
    aid = admit(Action(agent="performance-graph", workflow="graph", idempotency_key="healthy", resource="graph-service", expected_version=4, capacity=6))
    execute(aid)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM effects WHERE resource='graph-service'")).scalar_one() == 5


def test_graph_does_not_infer_reversals_across_filtered_version_gaps():
    resource = "gap-" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO resources VALUES(:id,4,0)"), {"id": resource})
        connection.execute(text("INSERT INTO external_resources VALUES(:id,4)"), {"id": resource})
    _oscillate(resource)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE effects SET observed_at=now()-interval '2 hours' WHERE resource=:resource AND version=2"),
            {"resource": resource},
        )
        connection.execute(
            text("UPDATE effects SET observed_at=now()-interval '10 seconds' WHERE resource=:resource AND version=3"),
            {"resource": resource},
        )
    result = graph(window=3600, resource=resource)
    assert [row["version"] for row in result["evidence"]] == [1, 3, 4]
    reversals = [edge for edge in result["edges"] if edge["inferred"]]
    assert len(reversals) == 1
    assert reversals[0]["source"] == f"action:{result['evidence'][1]['action_id']}"
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE effects SET before_capacity=2 WHERE resource=:resource AND version=4"),
            {"resource": resource},
        )
    assert not any(edge["inferred"] for edge in graph(window=3600, resource=resource)["edges"])


def test_sustained_recovery_requires_window_and_multiple_samples():
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO resources VALUES('recovery-service',4,0)"))
        connection.execute(text("INSERT INTO external_resources VALUES('recovery-service',4)"))
    _oscillate("recovery-service")
    tick()
    _scale_up("recovery-service")
    with engine.begin() as c:
        c.execute(text("UPDATE incidents SET hold_until=now() WHERE resource='recovery-service'"))
    tick()
    assert _incident("recovery-service")["status"] == "VERIFYING"
    with pytest.raises(ValueError, match="scale-down restricted"):
        admit(Action(agent="cost-graph", workflow="recovery", idempotency_key="verify-downscale", resource="recovery-service", expected_version=5, capacity=5))
    with engine.begin() as c:
        c.execute(text("UPDATE incidents SET verification_started_at=now()-interval '21 seconds' WHERE resource='recovery-service'"))
    tick()
    assert _incident("recovery-service")["status"] == "VERIFYING"
    tick()
    incident = _incident("recovery-service")
    assert incident["status"] == "VERIFIED"
    assert incident["healthy_samples"] >= 3
    assert incident["evidence"]["origin"]["actions"]
    assert incident["evidence"]["last_detection"]["reversal_pairs"]
    with engine.connect() as connection:
        transitions = dict(connection.execute(
            text("SELECT transition,count(*) FROM incident_transitions WHERE incident_id=:id GROUP BY transition"),
            {"id": incident["id"]},
        ).all())
    assert transitions["verification_started"] == 1
    assert transitions["verified"] == 1


def test_verified_incident_reopens_on_new_cross_agent_oscillation():
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO resources VALUES('recurrence-service',4,0)"))
        connection.execute(text("INSERT INTO external_resources VALUES('recurrence-service',4)"))
    _oscillate("recurrence-service")
    tick()
    _scale_up("recurrence-service")
    with engine.begin() as connection:
        connection.execute(text("UPDATE incidents SET hold_until=now() WHERE resource='recurrence-service'"))
    tick()
    with engine.begin() as connection:
        connection.execute(text("UPDATE incidents SET verification_started_at=now()-interval '21 seconds' WHERE resource='recurrence-service'"))
    tick()
    tick()
    assert _incident("recurrence-service")["status"] == "VERIFIED"
    _oscillate("recurrence-service", targets=(3, 6, 3, 6))
    tick()
    incident = _incident("recurrence-service")
    assert incident["status"] == "HOLD"
    assert incident["recurrence_count"] == 1
    assert incident["intervention_count"] == 2
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM incident_transitions WHERE incident_id=:id AND transition='recurrence'"),
            {"id": incident["id"]},
        ).scalar_one() == 1


def test_failed_interventions_escalate_without_an_endless_hold_loop():
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO resources VALUES('escalation-service',4,0)"))
        connection.execute(text("INSERT INTO external_resources VALUES('escalation-service',4)"))
    _oscillate("escalation-service")
    tick()
    with engine.begin() as connection:
        connection.execute(text("UPDATE resources SET capacity=3 WHERE id='escalation-service'"))
        connection.execute(text("UPDATE incidents SET hold_until=now() WHERE resource='escalation-service'"))
    tick()
    assert _incident("escalation-service")["intervention_count"] == 2
    with engine.begin() as connection:
        connection.execute(text("UPDATE incidents SET hold_until=now() WHERE resource='escalation-service'"))
    tick()
    assert _incident("escalation-service")["status"] == "ESCALATED"
    with engine.connect() as connection:
        escalated = connection.execute(
            text("SELECT id FROM incidents WHERE resource='escalation-service'")
        ).scalar_one()
        assert connection.execute(
            text("SELECT count(*) FROM incident_transitions WHERE incident_id=:id AND transition='escalated'"),
            {"id": escalated},
        ).scalar_one() == 1
    with pytest.raises(ValueError, match="scale-down restricted"):
        admit(Action(agent="cost-graph", workflow="review", idempotency_key="escalated-downscale", resource="escalation-service", expected_version=4, capacity=2))


def test_unrelated_agent_actions_continue_during_a_resource_hold():
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO agents(id) VALUES('unrelated-agent')"))
        connection.execute(text("INSERT INTO resources VALUES('contained-service',4,0)"))
        connection.execute(text("INSERT INTO external_resources VALUES('contained-service',4)"))
        connection.execute(text("INSERT INTO resources VALUES('isolated-service',4,0)"))
        connection.execute(text("INSERT INTO external_resources VALUES('isolated-service',4)"))
    _oscillate("contained-service")
    tick()
    aid = admit(
        Action(
            agent="unrelated-agent",
            workflow="independent",
            idempotency_key="isolated-downscale",
            resource="isolated-service",
            expected_version=0,
            capacity=3,
        )
    )
    execute(aid)
    assert _incident("contained-service")["status"] == "HOLD"


def test_healthy_scaling_not_detected():
    events = [dict(agent="performance", before_capacity=i, after_capacity=i + 1, latency=latency(i + 1)) for i in range(2, 8)]
    assert not score(events)[1]


def test_operator_transitions_are_guarded_and_idempotent_under_concurrent_replay():
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from botkernel.api import app

    client = TestClient(app)
    escalated = _operator_incident("operator-escalated", "ESCALATED")
    invalid = client.post(
        f"/incidents/{escalated}/resolve",
        json={"idempotency_key": "invalid-transition", "reason": "Not verified"},
    )
    assert invalid.status_code == 409
    assert client.post(
        f"/incidents/{escalated}/acknowledge",
        json={"idempotency_key": "blank-reason", "reason": "   "},
    ).status_code == 422

    request = {"idempotency_key": "ack-once", "reason": "Human review started"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(
            lambda _: client.post(f"/incidents/{escalated}/acknowledge", json=request),
            range(2),
        ))
    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json()["duplicate"] for response in responses) == [False, True]
    assert client.post(
        f"/incidents/{escalated}/acknowledge",
        json={"idempotency_key": "ack-once", "reason": "Changed payload"},
    ).status_code == 409
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM incident_operator_actions WHERE incident_id=:id"),
            {"id": escalated},
        ).scalar_one() == 1
        assert connection.execute(
            text("SELECT count(*) FROM incident_transitions WHERE incident_id=:id AND transition='acknowledged'"),
            {"id": escalated},
        ).scalar_one() == 1

    verified = _operator_incident("operator-verified", "VERIFIED")
    resolved = client.post(
        f"/incidents/{verified}/resolve",
        json={"idempotency_key": "resolve-once", "reason": "Verified recovery reviewed"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"
    assert client.post(
        f"/incidents/{verified}/resolve",
        json={"idempotency_key": "resolve-once", "reason": "Verified recovery reviewed"},
    ).json()["duplicate"] is True
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM incident_transitions WHERE incident_id=:id AND transition='resolved'"),
            {"id": verified},
        ).scalar_one() == 1
    assert client.post(
        f"/incidents/{verified}/acknowledge",
        json={"idempotency_key": "ack-after-close", "reason": "Too late"},
    ).status_code == 409
    listing = client.get("/incidents")
    assert listing.status_code == 200
    resolved_item = next(item for item in listing.json() if item["id"] == verified)
    assert resolved_item["operator_actions"][0]["reason"] == "Verified recovery reviewed"


def test_controller_and_operator_resolution_serialize_without_losing_recurrence():
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from botkernel.api import app

    incident_id = _operator_incident("operator-race", "VERIFIED")
    _oscillate("operator-race")
    client = TestClient(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        resolution = pool.submit(
            client.post,
            f"/incidents/{incident_id}/resolve",
            json={"idempotency_key": "race-resolution", "reason": "Recovery reviewed"},
        )
        controller = pool.submit(tick)
        controller.result()
        response = resolution.result()

    with engine.connect() as connection:
        status = connection.execute(
            text("SELECT status FROM incidents WHERE id=:id"), {"id": incident_id}
        ).scalar_one()
        statuses = connection.execute(
            text("SELECT status FROM incidents WHERE resource='operator-race' ORDER BY id")
        ).scalars().all()
    assert (response.status_code, status) in {(200, "RESOLVED"), (409, "HOLD")}
    if status == "RESOLVED":
        assert "HOLD" in statuses


def test_investigator_reads_controller_incident_without_mutating_state():
    from botkernel.investigator import investigation_graph
    with engine.begin() as c:
        c.execute(text("UPDATE quota SET capacity=100 WHERE id=1"))
        c.execute(text("INSERT INTO resources VALUES('investigation-test',4,0)"))
        c.execute(text("INSERT INTO external_resources VALUES('investigation-test',4)"))
    _oscillate('investigation-test')
    tick()
    incident=_incident('investigation-test')
    with engine.connect() as c:
        before=tuple(c.execute(text("SELECT (SELECT count(*) FROM actions), (SELECT count(*) FROM effects), (SELECT count(*) FROM incident_transitions), (SELECT version FROM resources WHERE id='investigation-test')")).one())
    result=investigation_graph.invoke({'incident_id':incident['id']})['report']
    assert len(result['effects'])==4
    assert len(result['reversals'])==3
    assert not result['missing_references']
    assert all(e['resource']=='investigation-test' for e in result['effects'])
    assert result['provider']=='deterministic_mock'
    with engine.connect() as c:
        after=tuple(c.execute(text("SELECT (SELECT count(*) FROM actions), (SELECT count(*) FROM effects), (SELECT count(*) FROM incident_transitions), (SELECT version FROM resources WHERE id='investigation-test')")).one())
    assert before==after


def test_investigator_does_not_infer_across_missing_version():
    from botkernel.investigator import correlate, report
    effects=[dict(action_id='a',agent='cost',resource='r',version=1,before_capacity=5,after_capacity=4,state='SUCCEEDED'),dict(action_id='b',agent='performance',resource='r',version=3,before_capacity=4,after_capacity=5,state='SUCCEEDED')]
    state={'incident_id':1,'incident':{'status':'HOLD','resource':'r'},'effects':effects,'missing':[],'warnings':[],'transitions':[]}
    state.update(correlate(state))
    assert state['reversals']==[]
    assert report(state)['report']['outcome']=='INSUFFICIENT_EVIDENCE'


def test_investigator_missing_reference_never_claims_complete():
    from botkernel.investigator import report
    state={'incident_id':1,'incident':{'status':'HOLD','resource':'r'},'effects':[],'missing':['missing-action'],'warnings':[],'transitions':[],'reversals':[]}
    result=report(state)['report']
    assert result['outcome']=='INSUFFICIENT_EVIDENCE'
    assert result['missing_references']==['missing-action']


def test_investigation_persistence_preserves_operational_rows(monkeypatch):
    from fastapi.testclient import TestClient
    with engine.begin() as c:
        c.execute(text("UPDATE quota SET capacity=250 WHERE id=1"))
        c.execute(text("INSERT INTO resources VALUES('investigation-invariance',4,0)"))
        c.execute(text("INSERT INTO external_resources VALUES('investigation-invariance',4)"))
    _oscillate('investigation-invariance')
    tick()
    incident=_incident('investigation-invariance')
    queries={
        'resource':"SELECT row_to_json(t)::text FROM resources t WHERE id='investigation-invariance'",
        'external':"SELECT row_to_json(t)::text FROM external_resources t WHERE id='investigation-invariance'",
        'actions':"SELECT row_to_json(t)::text FROM actions t WHERE resource='investigation-invariance' ORDER BY id",
        'effects':"SELECT row_to_json(t)::text FROM effects t WHERE resource='investigation-invariance' ORDER BY action_id",
        'outbox':"SELECT row_to_json(t)::text FROM outbox t WHERE action_id IN (SELECT id FROM actions WHERE resource='investigation-invariance') ORDER BY id",
        'receipts':"SELECT row_to_json(t)::text FROM receipts t WHERE action_id IN (SELECT id FROM actions WHERE resource='investigation-invariance') ORDER BY action_id",
        'incident':"SELECT row_to_json(t)::text FROM incidents t WHERE id=:id",
        'transitions':"SELECT row_to_json(t)::text FROM incident_transitions t WHERE incident_id=:id ORDER BY id",
        'operators':"SELECT row_to_json(t)::text FROM incident_operator_actions t WHERE incident_id=:id ORDER BY id",
    }
    def snapshot():
        with engine.connect() as c: return {name:c.execute(text(query),{'id':incident['id']}).scalars().all() for name,query in queries.items()}
    before=snapshot()
    response=TestClient(__import__('botkernel.api',fromlist=['app']).app).post(f"/incidents/{incident['id']}/investigations",json={'idempotency_key':'readonly-snapshot'})
    assert response.status_code==200
    assert response.json()['status']=='COMPLETE'
    assert snapshot()==before

    from botkernel.bedrock import BedrockConverse as RealConverse, InvestigationAnalysis
    class OfflineConverse:
        def invoke_json(self,**kwargs):
            action=kwargs['payload']['effects'][0]['action_id']
            return InvestigationAnalysis(
                explanation='The supplied sequence contains cross-agent reversals.',
                hypotheses=['Independent goals may interact.'],
                cross_agent_analysis='The observed agents changed the same resource.',
                instability_mechanism='Repeated reversals can produce oscillation.',
                supporting_references=[action],
                contradictory_or_missing_evidence=[],
                preventive_actions=['Review intervention policy.'],
                confidence_caveats=['Correlation is not causation.'],
            ),{'provider':'bedrock','model_id':'offline-test-model','input_tokens':25,'output_tokens':15,'invocations':1}
    monkeypatch.setattr('botkernel.bedrock.BedrockConverse',lambda:OfflineConverse())
    ai_response=TestClient(__import__('botkernel.api',fromlist=['app']).app).post(
        f"/incidents/{incident['id']}/investigations",
        json={'idempotency_key':'readonly-ai-snapshot','provider':'bedrock'},
    )
    assert ai_response.status_code==200
    assert ai_response.json()['provider']=='bedrock'
    assert ai_response.json()['report']['model_id']=='offline-test-model'
    assert ai_response.json()['report']['ai_analysis']['status']=='COMPLETE'
    assert ai_response.json()['report']['findings'][-1]['classification']=='HYPOTHESIS'
    assert snapshot()==before

    monkeypatch.setattr('botkernel.bedrock.BedrockConverse',RealConverse)
    monkeypatch.setenv('BEDROCK_ENABLED','false')
    disabled=TestClient(__import__('botkernel.api',fromlist=['app']).app).post(
        f"/incidents/{incident['id']}/investigations",
        json={'idempotency_key':'disabled-ai-snapshot','provider':'bedrock'},
    )
    assert disabled.status_code==200
    assert disabled.json()['status']=='FAILED'
    assert disabled.json()['error_category']=='bedrock_disabled'
    assert snapshot()==before
