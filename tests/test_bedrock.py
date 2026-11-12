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


def test_missing_sdk_dependency_keeps_initialization_category_and_sanitized_evidence(caplog):
    def missing_dependency(**kwargs):
        raise ModuleNotFoundError("private secret must not appear", name="dateutil")

    reservations = []
    sdk = BedrockConverse(
        _settings(), session_factory=missing_dependency,
        budget_reserver=lambda run_id, tokens: reservations.append((run_id, tokens)),
    )
    with pytest.raises(BedrockProviderError) as caught:
        sdk.invoke_json(run_id="offline", system="private prompt", payload={},
                        response_type=AgentDecision)
    error = caught.value
    assert error.category == "client_configuration"
    assert error.diagnostics["stage"] == "client_initialization"
    assert error.diagnostics["exception_type"] == "ModuleNotFoundError"
    assert error.diagnostics["missing_module"] == "dateutil"
    assert error.diagnostics["response_received"] is False
    assert error.diagnostics["remote_outcome_unknown"] is False
    assert len(reservations) == 1
    assert "private" not in json.dumps(error.diagnostics)
    assert "private" not in caplog.text


def test_client_initialization_uses_configured_region_profile_and_one_sdk_attempt():
    seen = {}
    fake = FakeConverseClient(_response({
        "decision": "NO_OP", "resource": "service-a", "proposed_delta": 0,
        "reason": "No change.", "evidence_references": ["resource:service-a"], "uncertainties": [],
    }))

    class Session:
        def client(self, name, **kwargs):
            seen["service"] = name
            seen["client"] = kwargs
            return fake

    def factory(**kwargs):
        seen["session"] = kwargs
        return Session()

    sdk = BedrockConverse(
        _settings(model_id="us.amazon.nova-micro-v1:0", region="us-east-2", profile="example"),
        session_factory=factory, budget_reserver=lambda *args: None,
    )
    sdk.invoke_json(run_id="offline", system="s", payload={}, response_type=AgentDecision)
    assert seen["session"] == {"profile_name": "example", "region_name": "us-east-2"}
    assert seen["service"] == "bedrock-runtime"
    assert seen["client"]["region_name"] == "us-east-2"
    assert seen["client"]["config"].retries["total_max_attempts"] == 1
    assert fake.calls[0]["modelId"] == "us.amazon.nova-micro-v1:0"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("AccessDeniedException", "access_denied"),
        ("ValidationException", "model_or_request_unavailable"),
        ("ResourceNotFoundException", "model_or_request_unavailable"),
        ("ModelNotReadyException", "model_temporarily_unavailable"),
        ("ModelErrorException", "bedrock_service_error"),
    ],
)
def test_aws_error_details_are_safe_and_reservation_is_not_retried(code, expected, caplog):
    from botocore.exceptions import ClientError
    aws_error = ClientError({
        "Error": {"Code": code, "Message": "private request and credential"},
        "ResponseMetadata": {"HTTPStatusCode": 403, "RequestId": "12345678-1234"},
    }, "Converse")
    client = FakeConverseClient(error=aws_error)
    reservations = []
    sdk = _sdk(client, budget_reserver=lambda run_id, tokens: reservations.append(run_id))
    with pytest.raises(BedrockProviderError) as caught:
        sdk.invoke_json(run_id="offline", system="private prompt", payload={},
                        response_type=AgentDecision)
    error = caught.value
    assert error.category == expected
    assert error.diagnostics["aws_error_code"] == code
    assert error.diagnostics["http_status"] == 403
    assert error.diagnostics["request_id"] == "12345678-1234"
    assert error.diagnostics["stage"] == "converse_request"
    assert error.diagnostics["response_received"] is True
    assert error.diagnostics["remote_outcome_unknown"] is True
    assert "private" not in json.dumps(error.diagnostics)
    assert "private" not in caplog.text
    with pytest.raises(BedrockProviderError, match="call_limit_exceeded"):
        sdk.invoke_json(run_id="offline", system="s", payload={}, response_type=AgentDecision)
    assert reservations == ["offline"] and len(client.calls) == 1


@pytest.mark.parametrize(
    ("error_name", "timeout"),
    [
        ("ReadTimeoutError", "read"),
        ("ConnectTimeoutError", "connect"),
        ("EndpointConnectionError", None),
        ("SSLError", None),
    ],
)
def test_transport_errors_are_classified_without_disclosing_endpoint(error_name, timeout):
    from botocore import exceptions
    cls = getattr(exceptions, error_name)
    kwargs = {"endpoint_url": "https://private.example"}
    if error_name == "SSLError":
        kwargs["error"] = "private certificate"
    client = FakeConverseClient(error=cls(**kwargs))
    sdk = _sdk(client)
    with pytest.raises(BedrockProviderError) as caught:
        sdk.invoke_json(run_id="offline", system="s", payload={}, response_type=AgentDecision)
    assert caught.value.category == "request_timeout_or_endpoint_unavailable"
    assert caught.value.diagnostics["timeout"] == timeout
    assert caught.value.diagnostics["response_received"] is False
    assert caught.value.diagnostics["remote_outcome_unknown"] is True
    assert "private" not in json.dumps(caught.value.diagnostics)


def test_sdk_parameter_validation_is_reported_without_request_details():
    from botocore.exceptions import ParamValidationError
    sdk = _sdk(FakeConverseClient(error=ParamValidationError(report="private prompt")))
    with pytest.raises(BedrockProviderError) as caught:
        sdk.invoke_json(run_id="offline", system="s", payload={}, response_type=AgentDecision)
    assert caught.value.category == "model_or_request_unavailable"
    assert caught.value.diagnostics["exception_type"] == "ParamValidationError"
    assert "private" not in json.dumps(caught.value.diagnostics)


def _stubbed_runtime():
    import boto3
    from botocore.config import Config
    from botocore.stub import Stubber

    session = boto3.Session(aws_access_key_id="offline", aws_secret_access_key="offline",
                            region_name="us-east-2")
    client = session.client("bedrock-runtime", config=Config(retries={"total_max_attempts": 1}))
    return client, Stubber(client)


def _stub_response(body):
    return {
        **_response(body),
        "output": {"message": {"role": "assistant", "content": [{"text": json.dumps(body)}]}},
        "usage": {"inputTokens": 123, "outputTokens": 45, "totalTokens": 168},
        "metrics": {"latencyMs": 1},
    }


@pytest.mark.parametrize(("role", "delta"), [("cost", -1), ("performance", 1)])
def test_real_sdk_stub_validates_each_agent_and_nova_profile(role, delta):
    from botocore.stub import ANY
    from botocore.validate import validate_parameters
    client, stubber = _stubbed_runtime()
    model = "us.amazon.nova-micro-v1:0"
    body = {"decision": "PROPOSE", "resource": "service-a", "proposed_delta": delta,
            "reason": "Based on the observed simulator resource.",
            "evidence_references": ["resource:service-a"], "uncertainties": []}
    expected = {"modelId": model, "system": ANY, "messages": ANY,
                "inferenceConfig": {"maxTokens": 512, "temperature": 0.1}}
    stubber.add_response("converse", _stub_response(body), expected)
    observed = {}
    client.meta.events.register(
        "before-parameter-build.bedrock-runtime.Converse",
        lambda params, **kwargs: observed.update(params),
    )
    sdk = _sdk(client, _settings(model_id=model, region="us-east-2", max_output_tokens=512))
    with stubber:
        decision, usage = BedrockAgentReasoner(sdk).decide(
            role, {"id": "service-a", "capacity": 5, "recent_effects": []}, "offline"
        )
    assert decision.proposed_delta == delta
    validate_parameters(observed, client.meta.service_model.operation_model("Converse").input_shape)
    assert json.loads(observed["messages"][0]["content"][0]["text"])["agent_role"] == role
    assert usage["model_id"] == model and usage["input_tokens"] == 123 and usage["output_tokens"] == 45
    assert "toolConfig" not in observed
    stubber.assert_no_pending_responses()


def test_real_sdk_stub_validates_investigator_citations_and_usage(monkeypatch):
    import botkernel.bedrock as module
    from botocore.stub import ANY
    from botkernel.investigator import ai_assist

    action = "00000000-0000-0000-0000-000000000001"
    body = {"explanation": "Effects were observed.", "hypotheses": ["A loop may exist."],
            "cross_agent_analysis": "Two agents changed capacity.",
            "instability_mechanism": "Changes reversed.", "supporting_references": [action],
            "contradictory_or_missing_evidence": [], "preventive_actions": [],
            "confidence_caveats": ["Correlation is not causation."]}
    client, stubber = _stubbed_runtime()
    model = "us.amazon.nova-micro-v1:0"
    stubber.add_response("converse", _stub_response(body), {
        "modelId": model, "system": ANY, "messages": ANY,
        "inferenceConfig": {"maxTokens": 512, "temperature": 0.1},
    })
    sdk = _sdk(client, _settings(model_id=model, region="us-east-2", max_output_tokens=512))
    monkeypatch.setattr(module, "BedrockConverse", lambda: sdk)
    with stubber:
        report = ai_assist({**_investigation_state(), "provider": "bedrock", "run_id": "offline"})["report"]
    assert report["ai_analysis"]["supporting_references"] == [action]
    assert report["findings"][-1]["classification"] == "HYPOTHESIS"
    assert report["usage"]["input_tokens"] == 123 and report["usage"]["output_tokens"] == 45
    stubber.assert_no_pending_responses()


def test_malformed_converse_response_has_safe_response_diagnostics():
    sdk = _sdk(FakeConverseClient({"stopReason": "end_turn", "output": {}}))
    with pytest.raises(BedrockProviderError) as caught:
        sdk.invoke_json(run_id="offline", system="s", payload={}, response_type=AgentDecision)
    assert caught.value.category == "invalid_model_response"
    assert caught.value.diagnostics["stage"] == "response_validation"
    assert caught.value.diagnostics["response_received"] is True


def test_investigation_worker_returns_sanitized_provider_diagnostics(monkeypatch, capsys):
    import io
    import botkernel.investigation_worker as worker
    import botkernel.investigator as investigator

    diagnostics = {"category": "client_configuration", "missing_module": "dateutil"}

    class FailedGraph:
        def invoke(self, request):
            raise BedrockProviderError("client_configuration", diagnostics=diagnostics)

    monkeypatch.setattr(worker, "install_parent_death_guard", lambda: None)
    monkeypatch.setattr(investigator, "investigation_graph", FailedGraph())
    monkeypatch.setattr("sys.stdin", io.StringIO('{"incident_id":1,"run_id":"offline"}'))
    worker.main()
    assert json.loads(capsys.readouterr().out) == {
        "error_category": "client_configuration", "error_diagnostics": diagnostics,
    }


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
