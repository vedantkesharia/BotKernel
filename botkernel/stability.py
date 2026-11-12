"""Deterministic observed-effect graph and bounded collective controller."""
import json
import logging
import os

from sqlalchemy import text

from botkernel.core import engine
from botkernel.effect_relationships import is_contiguous_reversal

WINDOW_SECONDS = int(os.getenv("STABILITY_WINDOW_SECONDS", "60"))
HOLD_SECONDS = int(os.getenv("STABILITY_HOLD_SECONDS", "20"))
VERIFICATION_SECONDS = int(os.getenv("STABILITY_VERIFICATION_SECONDS", "20"))
VERIFICATION_SAMPLES = int(os.getenv("STABILITY_VERIFICATION_SAMPLES", "3"))
MAX_INTERVENTIONS = int(os.getenv("STABILITY_MAX_INTERVENTIONS", "2"))
HEALTHY_LATENCY = 80
HARMFUL_LATENCY = 100


def latency(capacity, workload=6):
    return round(40 + 160 * max(0, workload / capacity - 1), 2)


def analysis(events):
    """Return bounded, interpretable evidence from committed resource effects."""
    changes = [event for event in events if event["after_capacity"] != event["before_capacity"]]
    inverses = [
        (before, after)
        for before, after in zip(changes, changes[1:])
        if (before["after_capacity"] - before["before_capacity"])
        * (after["after_capacity"] - after["before_capacity"]) < 0
        and before["agent"] != after["agent"]
    ]
    agents = {event["agent"] for event in changes}
    degraded = any(event["latency"] > HARMFUL_LATENCY for event in changes)
    value = round(.7 * min(1, len(inverses) / 3) + .3 * int(degraded), 3)
    detected = (
        len(changes) >= 4
        and len(agents) >= 2
        and len(inverses) >= 3
        and degraded
        and value >= .8
    )
    return {
        "score": value,
        "detected": detected,
        "reversals": inverses,
        "changes": changes,
        "agents": sorted(agents),
    }


def score(events):
    result = analysis(events)
    return result["score"], result["detected"], result["reversals"]


def graph(window=60, resource=None):
    with engine.connect() as c:
        events=[dict(e) for e in c.execute(text("SELECT * FROM effects WHERE observed_at>now()-(:w*interval '1 second') AND (CAST(:r AS text) IS NULL OR resource=CAST(:r AS text)) ORDER BY resource,version LIMIT 1000"),{'w':window,'r':resource}).mappings()]
    nodes={};edges=[];previous={}
    def node(key,kind,label):
        nodes[key]={'id':key,'kind':kind,'label':label}
    for e in events:
        a='action:'+str(e['action_id']);ag='agent:'+e['agent'];r='resource:'+e['resource']
        node(a,'action',f"v{e['version']}: {e['before_capacity']} -> {e['after_capacity']}");node(ag,'agent',e['agent']);node(r,'resource',e['resource'])
        edges.extend([{'id':a+':agent','source':ag,'target':a,'kind':'EXECUTED','inferred':False},{'id':a+':resource','source':a,'target':r,'kind':'MODIFIED','inferred':False}])
        old=previous.get(r)
        if old and is_contiguous_reversal(old, e):
            edges.append({'id':a+':reverse','source':'action:'+str(old['action_id']),'target':a,'kind':'REVERSED_DIRECTION','inferred':True})
        previous[r]=e
    return {'nodes':list(nodes.values()),'edges':edges,'evidence':events,'truncated':len(events)==1000}


def _evidence(result, reason):
    return {
        "actions": [str(event["action_id"]) for event in result["changes"]],
        "agents": result["agents"],
        "reversal_pairs": [
            [str(before["action_id"]), str(after["action_id"])]
            for before, after in result["reversals"]
        ],
        "reason": reason,
        "score": result["score"],
        "correlation_notice": "Cross-agent reversal is evidence, not causal proof.",
    }


def _append_lifecycle(evidence, transition, result):
    evidence = evidence or {}
    lifecycle = evidence.get("lifecycle", [])
    lifecycle.append({"transition": transition, "score": result["score"]})
    evidence["lifecycle"] = lifecycle[-20:]
    snapshot = _evidence(result, transition)
    evidence["latest"] = snapshot
    # Healthy verification samples often have no contributing actions. Preserve
    # the committed evidence that caused the incident for operator review.
    if result["detected"]:
        evidence.setdefault("origin", snapshot)
        evidence["last_detection"] = snapshot
    return evidence


def _events(resource, window):
    with engine.connect() as connection:
        return [
            dict(event)
            for event in connection.execute(
                text(
                    "SELECT e.*,o.trace_context FROM effects e "
                    "LEFT JOIN outbox o ON o.action_id=e.action_id "
                    "WHERE e.resource=:r AND e.observed_at>now()-(:w*interval '1 second') "
                    "ORDER BY e.version LIMIT 1000"
                ),
                {"r": resource, "w": window},
            ).mappings()
        ]


def _record_transition(connection, incident_id, transition, score, pending_transitions):
    connection.execute(
        text(
            "INSERT INTO incident_transitions(incident_id,transition,score) "
            "VALUES(:incident,:transition,:score)"
        ),
        {"incident": incident_id, "transition": transition, "score": score},
    )
    pending_transitions.append((incident_id, transition, score))


def _apply_intervention(connection, incident, result, transition, pending_transitions):
    evidence = _append_lifecycle(incident["evidence"], transition, result)
    connection.execute(
        text(
            "UPDATE incidents SET status='HOLD', hold_until=now()+(:hold * interval '1 second'), "
            "intervention_count=intervention_count+1, recurrence_count=recurrence_count+1, "
            "monitor_started_at=now(), verification_started_at=NULL, healthy_samples=0, "
            "last_score=:score, last_observed_at=now(), reopened_at=now(), "
            "evidence=CAST(:evidence AS jsonb) WHERE id=:id"
        ),
        {
            "hold": HOLD_SECONDS,
            "score": result["score"],
            "evidence": json.dumps(evidence),
            "id": incident["id"],
        },
    )
    _record_transition(connection, incident["id"], "recurrence", result["score"], pending_transitions)
    _record_transition(connection, incident["id"], "hold_applied", result["score"], pending_transitions)


def _escalate(connection, incident, result, transition, pending_transitions):
    connection.execute(
        text(
            "UPDATE incidents SET status='ESCALATED', escalated_at=now(), "
            "last_score=:score, last_observed_at=now(), "
            "evidence=CAST(:evidence AS jsonb) WHERE id=:id"
        ),
        {
            "score": result["score"],
            "evidence": json.dumps(_append_lifecycle(incident["evidence"], transition, result)),
            "id": incident["id"],
        },
    )
    _record_transition(connection, incident["id"], "escalated", result["score"], pending_transitions)


def _advance_state(resource, events, span, pending_transitions):
    """Advance one resource lifecycle while holding locks only for state mutation."""
    with engine.begin() as connection:
        # This is the same lock order as admission and execution finalization.
        connection.execute(text("SELECT id FROM quota WHERE id=1 FOR UPDATE"))
        current_resource = connection.execute(
            text("SELECT * FROM resources WHERE id=:resource FOR UPDATE"), {"resource": resource}
        ).mappings().one()
        incident = connection.execute(
            text("SELECT * FROM incidents WHERE resource=:resource ORDER BY opened_at DESC LIMIT 1"),
            {"resource": resource},
        ).mappings().first()
        if not incident or incident["status"] == "RESOLVED":
            result = analysis(events)
            if not result["detected"]:
                return
            evidence = _append_lifecycle({}, "detected and contained", result)
            incident_id = connection.execute(
                text(
                    "INSERT INTO incidents(resource,score,last_score,evidence,monitor_started_at,last_observed_at) "
                    "VALUES(:resource,:score,:score,CAST(:evidence AS jsonb),now(),now()) RETURNING id"
                ),
                {"resource": resource, "score": result["score"], "evidence": json.dumps(evidence)},
            ).scalar_one()
            span.set_attribute("incident.id", incident_id)
            _record_transition(connection, incident_id, "detected", result["score"], pending_transitions)
            _record_transition(connection, incident_id, "hold_applied", result["score"], pending_transitions)
            return
        span.set_attribute("incident.id", incident["id"])

        monitored = [event for event in events if event["observed_at"] > incident["monitor_started_at"]]
        result = analysis(monitored)
        unhealthy = result["detected"] or latency(current_resource["capacity"]) > HARMFUL_LATENCY
        if incident["status"] == "HOLD":
            if incident["hold_until"] > connection.execute(text("SELECT now()")).scalar_one():
                return
            if unhealthy:
                if incident["intervention_count"] >= MAX_INTERVENTIONS:
                    _escalate(connection, incident, result, "intervention limit reached without recovery", pending_transitions)
                else:
                    _apply_intervention(connection, incident, result, "harmful behavior persisted after hold", pending_transitions)
                return
            connection.execute(
                text(
                    "UPDATE incidents SET status='VERIFYING', verification_started_at=now(), "
                    "healthy_samples=1, last_score=:score,last_observed_at=now(), "
                    "evidence=CAST(:evidence AS jsonb) WHERE id=:id"
                ),
                {
                    "score": result["score"],
                    "evidence": json.dumps(_append_lifecycle(incident["evidence"], "hold ended; sustained verification started", result)),
                    "id": incident["id"],
                },
            )
            _record_transition(connection, incident["id"], "verification_started", result["score"], pending_transitions)
            return
        if incident["status"] == "VERIFYING":
            if unhealthy:
                if incident["intervention_count"] >= MAX_INTERVENTIONS:
                    _escalate(connection, incident, result, "verification failed; intervention limit reached", pending_transitions)
                else:
                    _apply_intervention(connection, incident, result, "verification failed; recurrence contained", pending_transitions)
                return
            samples = incident["healthy_samples"] + 1
            verified = (
                samples >= VERIFICATION_SAMPLES
                and incident["verification_started_at"] is not None
                and connection.execute(
                    text("SELECT now()-:started >= (:window * interval '1 second')"),
                    {"started": incident["verification_started_at"], "window": VERIFICATION_SECONDS},
                ).scalar_one()
            )
            if verified:
                connection.execute(
                    text(
                        "UPDATE incidents SET status='VERIFIED', verified_at=now(), monitor_started_at=now(), "
                        "healthy_samples=:samples,last_score=:score,last_observed_at=now(), "
                        "evidence=CAST(:evidence AS jsonb) WHERE id=:id"
                    ),
                    {
                        "samples": samples,
                        "score": result["score"],
                        "evidence": json.dumps(_append_lifecycle(incident["evidence"], "sustained recovery verified", result)),
                        "id": incident["id"],
                    },
                )
                _record_transition(connection, incident["id"], "verified", result["score"], pending_transitions)
            else:
                connection.execute(
                    text("UPDATE incidents SET healthy_samples=:samples,last_score=:score,last_observed_at=now() WHERE id=:id"),
                    {"samples": samples, "score": result["score"], "id": incident["id"]},
                )
            return
        if incident["status"] == "VERIFIED" and result["detected"]:
            if incident["intervention_count"] >= MAX_INTERVENTIONS:
                _escalate(connection, incident, result, "verified incident recurred after intervention limit", pending_transitions)
            else:
                _apply_intervention(connection, incident, result, "verified incident recurred", pending_transitions)


def _advance(resource, events):
    from botkernel.observability import span_links_from_carriers, traced_span

    links = span_links_from_carriers(
        [event.get("trace_context") for event in events if event.get("trace_context")],
    )
    with traced_span(
        "botkernel.stability.resource_evaluation",
        {"botkernel.outcome": "evaluated"},
        links=links,
    ) as span:
        pending_transitions = []
        _advance_state(resource, events, span, pending_transitions)
        for incident_id, transition, score in pending_transitions:
            with traced_span(
                "botkernel.incident.transition",
                {"incident.id": incident_id, "botkernel.outcome": transition},
            ):
                logging.info(
                    "Incident transition committed",
                    extra={
                        "event": "incident_transition_committed",
                        "incident_id": incident_id,
                        "botkernel_outcome": transition,
                        "stability_score": score,
                    },
                )


def tick(window=WINDOW_SECONDS):
    """Analyze committed evidence outside locks, then make small atomic transitions."""
    from botkernel.observability import traced_span

    with traced_span("botkernel.stability.tick"):
        with engine.connect() as connection:
            resources = connection.execute(text("SELECT id FROM resources ORDER BY id")).scalars().all()
        for resource in resources:
            _advance(resource, _events(resource, window))
