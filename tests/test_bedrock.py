import json

import pytest
from botkernel.bedrock import (
    AgentDecision, BedrockAgentReasoner, BedrockConverse, BedrockProviderError,
    BedrockSettings, InvestigationAnalysis, classify_bedrock_error,
)


class FakeConverseClient:
    def __init__(self, response=None, error=None):
        self.response=response
        self.error=error
        self.calls=[]

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def _response(value, stop="end_turn"):
    return {
        "stopReason":stop,
        "output":{"message":{"content":[{"text":json.dumps(value)}]}},
        "usage":{"inputTokens":123,"outputTokens":45},
    }


def _settings(**changes):
    values={"model_id":"example-model","region":"us-east-1","max_output_tokens":256,
            "max_calls_per_run":1,"timeout_seconds":3,"max_calls_per_day":10,
            "max_tokens_per_day":20_000,"profile":None}
    values.update(changes)
    return BedrockSettings(**values)

def _sdk(client, settings=None, *, budget_reserver=None):
    sdk=BedrockConverse(settings or _settings(),session_factory=lambda **kwargs: None,
                        budget_reserver=budget_reserver or (lambda run_id, tokens: None))
    sdk._client=client
    return sdk


def test_converse_request_is_bounded_and_parses_usage():
    client=FakeConverseClient(_response({"decision":"NO_OP","resource":"service-a","proposed_delta":0,
        "reason":"No observed need.","evidence_references":["resource:service-a"],"uncertainties":[]}))
    sdk=_sdk(client)
    result,usage=sdk.invoke_json(run_id="run-1",system="advisory only",payload={"capacity":4},response_type=AgentDecision)
    assert result.decision=="NO_OP"
    assert usage=={"provider":"bedrock","model_id":"example-model","input_tokens":123,"output_tokens":45,"invocations":1}
    request=client.calls[0]
    assert request["modelId"]=="example-model"
    assert request["inferenceConfig"]["maxTokens"]==256
    assert request["messages"][0]["content"][0]["text"]=='{"capacity":4}'
    assert "toolConfig" not in request


@pytest.mark.parametrize("body",[
    {"decision":"EXECUTE","resource":"service-a","proposed_delta":99,"reason":"x","evidence_references":[],"uncertainties":[]},
    {"decision":"PROPOSE","resource":"service-a","proposed_delta":0,"reason":"x","evidence_references":[],"uncertainties":[]},
])
def test_invalid_agent_decisions_rejected(body):
    client=FakeConverseClient(_response(body))
    sdk=_sdk(client)
    with pytest.raises(BedrockProviderError,match="invalid_model_response"):
        sdk.invoke_json(run_id="r",system="s",payload={},response_type=AgentDecision)


def test_invalid_json_and_refusal_are_explicit():
    client=FakeConverseClient({"stopReason":"end_turn","output":{"message":{"content":[{"text":"not json"}]}}})
    sdk=_sdk(client)
    with pytest.raises(BedrockProviderError,match="invalid_model_response"):
        sdk.invoke_json(run_id="r",system="s",payload={},response_type=AgentDecision)
    refused=_sdk(FakeConverseClient({"stopReason":"guardrail_intervened"}))
    with pytest.raises(BedrockProviderError,match="model_refusal"):
        refused.invoke_json(run_id="r",system="s",payload={},response_type=AgentDecision)


def test_call_limit_and_input_limit_are_enforced():
    client=FakeConverseClient(_response({"decision":"NO_OP","resource":"x","proposed_delta":0,
        "reason":"No change.","evidence_references":["resource:x"],"uncertainties":[]}))
    sdk=_sdk(client)
    sdk.invoke_json(run_id="r",system="s",payload={},response_type=AgentDecision)
    with pytest.raises(BedrockProviderError,match="call_limit_exceeded"):
        sdk.invoke_json(run_id="r",system="s",payload={},response_type=AgentDecision)
    oversized=_sdk(client)
    with pytest.raises(BedrockProviderError,match="input_too_large"):
        oversized.invoke_json(run_id="r2",system="s",payload={"x":"x"*17_000},response_type=AgentDecision)


def test_provider_settings_default_closed_and_reject_invalid_limits(monkeypatch):
    monkeypatch.setenv("BEDROCK_ENABLED","false")
    with pytest.raises(BedrockProviderError,match="bedrock_disabled"):
        BedrockSettings.from_env()
    monkeypatch.setenv("BEDROCK_ENABLED","true")
    monkeypatch.setenv("BEDROCK_SPEND_AUTHORIZED","true")
    monkeypatch.setenv("BEDROCK_MODEL_ID","example-model")
    monkeypatch.setenv("BEDROCK_REGION","not-a-region")
    with pytest.raises(BedrockProviderError,match="invalid_region_configuration"):
        BedrockSettings.from_env()
    monkeypatch.setenv("BEDROCK_REGION","us-east-1")
    monkeypatch.setenv("BEDROCK_MAX_OUTPUT_TOKENS","9000")
    with pytest.raises(BedrockProviderError,match="invalid_inference_limits"):
        BedrockSettings.from_env()


def test_bedrock_requires_separate_spend_authorization_and_reserves_daily_budget(monkeypatch):
    monkeypatch.setenv("BEDROCK_ENABLED","true")
    monkeypatch.setenv("BEDROCK_SPEND_AUTHORIZED","false")
    monkeypatch.setenv("BEDROCK_MODEL_ID","example-model")
    monkeypatch.setenv("BEDROCK_REGION","us-east-1")
    with pytest.raises(BedrockProviderError,match="spend_not_authorized"):
        BedrockSettings.from_env()
    monkeypatch.setenv("BEDROCK_SPEND_AUTHORIZED","true")
    reservations=[]
    sdk=_sdk(FakeConverseClient(_response({"decision":"NO_OP","resource":"x","proposed_delta":0,
        "reason":"No observed need.","evidence_references":["resource:x"],"uncertainties":[]})),
        budget_reserver=lambda run_id,tokens: reservations.append((run_id,tokens)))
    sdk.invoke_json(run_id="bounded-run",system="advisory",payload={"x":1},response_type=AgentDecision)
    assert reservations and reservations[0][0]=="bounded-run"
    assert reservations[0][1] > sdk.settings.max_output_tokens
    exhausted=_sdk(FakeConverseClient(_response({})),budget_reserver=lambda *args: (_ for _ in ()).throw(BedrockProviderError("inference_budget_exhausted")))
    with pytest.raises(BedrockProviderError,match="inference_budget_exhausted"):
        exhausted.invoke_json(run_id="budget-full",system="advisory",payload={},response_type=AgentDecision)
    assert exhausted._client.calls==[]


def test_redis_budget_reservation_failure_stops_before_converse(monkeypatch):
    import redis

    def unavailable(*args, **kwargs):
        raise redis.ConnectionError("offline test")

    monkeypatch.setattr(redis.Redis, "from_url", unavailable)
    client=FakeConverseClient(_response({}))
    sdk=BedrockConverse(
        _settings(),
        session_factory=lambda **kwargs: None,
    )
    sdk._client=client
    with pytest.raises(BedrockProviderError,match="budget_counter_unavailable"):
        sdk.invoke_json(run_id="redis-unavailable",system="advisory",payload={},
                        response_type=AgentDecision)
    assert client.calls==[]


def test_timeout_access_denied_and_throttling_classification():
    from botocore.exceptions import ClientError, ReadTimeoutError
    assert classify_bedrock_error(ReadTimeoutError(endpoint_url="https://example.invalid"))==("request_timeout_or_endpoint_unavailable",True)
    def client_error(code):
        return ClientError({"Error":{"Code":code,"Message":"redacted"}}, "Converse")
    assert classify_bedrock_error(client_error("AccessDeniedException"))==("access_denied",False)
    assert classify_bedrock_error(client_error("ThrottlingException"))==("throttled",True)


def test_agent_reasoner_rejects_forged_refs_direction_and_bounds():
    class Client:
        settings=_settings()
        def __init__(self,result): self.result=result
        def invoke_json(self,**kwargs): return self.result,{"provider":"bedrock","model_id":"example","invocations":1}
    telemetry={"id":"service-a","capacity":5,"recent_effects":[]}
    good=AgentDecision(decision="PROPOSE",resource="service-a",proposed_delta=-1,reason="Reduce slack.",
                       evidence_references=["resource:service-a"],uncertainties=[])
    result,_=BedrockAgentReasoner(Client(good)).decide("cost",telemetry,"r")
    assert result.proposed_delta==-1
    forged=good.model_copy(update={"evidence_references":["invented-action"]})
    with pytest.raises(BedrockProviderError,match="invalid_evidence_reference"):
        BedrockAgentReasoner(Client(forged)).decide("cost",telemetry,"r")
    with pytest.raises(BedrockProviderError,match="invalid_action_direction"):
        BedrockAgentReasoner(Client(good.model_copy(update={"proposed_delta":1}))).decide("cost",telemetry,"r")
    too_large=good.model_copy(update={"proposed_delta":-3})
    with pytest.raises(BedrockProviderError,match="action_out_of_bounds"):
        BedrockAgentReasoner(Client(too_large)).decide("cost",{"id":"service-a","capacity":2,"recent_effects":[]}, "r")


def test_investigation_schema_is_strict():
    with pytest.raises(Exception):
        InvestigationAnalysis.model_validate({"explanation":"ok","invented":True})


def _investigation_state():
    action="00000000-0000-0000-0000-000000000001"
    report={
        "investigation_id":"report-1","incident_id":7,"timestamp":"2026-01-01T00:00:00Z",
        "status":"HOLD","resource":"service-a","provider":"deterministic_mock","outcome":"COMPLETE",
        "contributing_agents":["cost","performance"],"evidence_warnings":[],"effects":[
            {"action_id":action,"agent":"cost","resource":"service-a","version":1,"before_capacity":5,"after_capacity":4,"latency":50,"observed_at":"2026-01-01T00:00:00Z","state":"SUCCEEDED"}],
        "reversals":[[action,action]],"transitions":[],"missing_references":[],"conclusion":"Observed opposing changes.",
        "recommendation":"Review evidence.","findings":[{"classification":"VERIFIED_FACT","description":"Effect committed.","supporting_actions":[action],"contradicting_actions":[]}],
    }
    return {"report":report,"incident":{"score":0.8}}


def test_ai_investigation_citations_are_validated_and_hypotheses_stay_hypotheses(monkeypatch):
    import botkernel.bedrock as module
    valid="00000000-0000-0000-0000-000000000001"
    result=InvestigationAnalysis(explanation="The effects reverse.",hypotheses=["Independent goals may contribute."],
        cross_agent_analysis="Two agents changed capacity in opposite directions.",instability_mechanism="Repeated reversal may cause oscillation.",
        supporting_references=[valid],contradictory_or_missing_evidence=[],preventive_actions=["Review held changes."],
        confidence_caveats=["Correlation is not causation."])
    class Fake:
        def invoke_json(self,**kwargs): return result,{"provider":"bedrock","model_id":"offline-test-model","input_tokens":20,"output_tokens":10,"invocations":1}
    monkeypatch.setattr(module,"BedrockConverse",lambda:Fake())
    from botkernel.investigator import ai_assist
    state=_investigation_state(); output=ai_assist({**state,"provider":"bedrock","run_id":"test-run"})["report"]
    assert output["provider"]=="bedrock" and output["model_id"]=="offline-test-model"
    assert output["usage"]["input_tokens"]==20
    assert output["findings"][0]["classification"]=="VERIFIED_FACT"
    assert output["findings"][-1]["classification"]=="HYPOTHESIS"
    assert output["ai_analysis"]["supporting_references"]==[valid]
    forged=result.model_copy(update={"supporting_references":["invented-action"]})
    class Forged:
        def invoke_json(self,**kwargs): return forged,{"provider":"bedrock","model_id":"offline"}
    monkeypatch.setattr(module,"BedrockConverse",lambda:Forged())
    with pytest.raises(BedrockProviderError,match="invalid_evidence_reference"):
        ai_assist({**_investigation_state(),"provider":"bedrock","run_id":"test-run-2"})


def test_ai_hypotheses_require_at_least_one_committed_effect_citation(monkeypatch):
    import botkernel.bedrock as module
    result=InvestigationAnalysis(
        explanation="The incident was observed.",
        hypotheses=["The agents may have interacted."],
        cross_agent_analysis="Two agent identities are present.",
        instability_mechanism="Opposing changes may be related.",
        supporting_references=["incident:7"],
        contradictory_or_missing_evidence=[],
        preventive_actions=[],
        confidence_caveats=["Causation is unproven."],
    )

    class Fake:
        def invoke_json(self, **kwargs):
            return result, {"provider":"bedrock","model_id":"offline","invocations":1}

    monkeypatch.setattr(module,"BedrockConverse",lambda:Fake())
    from botkernel.investigator import ai_assist
    with pytest.raises(BedrockProviderError,match="invalid_evidence_reference"):
        ai_assist({**_investigation_state(),"provider":"bedrock","run_id":"incident-only"})


def test_ai_investigation_rejects_forged_incident_citation(monkeypatch):
    import botkernel.bedrock as module
    valid=InvestigationAnalysis(
        explanation="Evidence was reviewed.",
        hypotheses=[],
        cross_agent_analysis="The persisted incident links two agents.",
        instability_mechanism="Opposing effects were observed.",
        supporting_references=["incident:999"],
        contradictory_or_missing_evidence=[],
        preventive_actions=[],
        confidence_caveats=["No causal claim is made."],
    )

    class Fake:
        def invoke_json(self, **kwargs):
            return valid, {"provider":"bedrock","model_id":"offline","invocations":1}

    monkeypatch.setattr(module,"BedrockConverse",lambda:Fake())
    from botkernel.investigator import ai_assist
    with pytest.raises(BedrockProviderError,match="invalid_evidence_reference"):
        ai_assist({**_investigation_state(),"provider":"bedrock","run_id":"wrong-incident"})


def test_ai_investigation_abstains_without_complete_evidence():
    from botkernel.investigator import ai_assist
    state=_investigation_state()
    state["report"]["outcome"]="INSUFFICIENT_EVIDENCE"
    state["report"]["evidence_warnings"]=["No transition history"]
    result=ai_assist({**state,"provider":"bedrock","run_id":"no-evidence"})["report"]
    assert result["ai_analysis"]["status"]=="INSUFFICIENT_EVIDENCE"
    assert result["usage"]["invocations"]==0
    assert result["ai_analysis"]["hypotheses"]==[]
