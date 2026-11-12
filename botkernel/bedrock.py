"""Cost-bounded Bedrock Converse client and strict BotKernel AI contracts."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T", bound=BaseModel)


class BedrockProviderError(RuntimeError):
    def __init__(self, category: str, *, retryable: bool = False):
        super().__init__(category)
        self.category = category
        self.retryable = retryable


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decision: str = Field(pattern=r"^(PROPOSE|NO_OP)$")
    resource: str = Field(min_length=1, max_length=100)
    proposed_delta: int = Field(ge=-3, le=3)
    reason: str = Field(min_length=1, max_length=500)
    evidence_references: list[str] = Field(min_length=1, max_length=20)
    uncertainties: list[str] = Field(max_length=10)

    @model_validator(mode="after")
    def validate_delta(self):
        if self.decision == "NO_OP" and self.proposed_delta != 0:
            raise ValueError("NO_OP must have a zero delta")
        if self.decision == "PROPOSE" and self.proposed_delta == 0:
            raise ValueError("PROPOSE requires a nonzero delta")
        return self


class InvestigationAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    explanation: str = Field(min_length=1, max_length=2000)
    hypotheses: list[str] = Field(max_length=10)
    cross_agent_analysis: str = Field(max_length=2000)
    instability_mechanism: str = Field(max_length=1500)
    supporting_references: list[str] = Field(min_length=1, max_length=50)
    contradictory_or_missing_evidence: list[str] = Field(max_length=20)
    preventive_actions: list[str] = Field(max_length=10)
    confidence_caveats: list[str] = Field(max_length=10)


@dataclass(frozen=True)
class BedrockSettings:
    model_id: str
    region: str
    max_output_tokens: int
    max_calls_per_run: int
    timeout_seconds: float
    max_calls_per_day: int
    max_tokens_per_day: int
    profile: str | None = None

    @classmethod
    def from_env(cls) -> "BedrockSettings":
        if os.getenv("BEDROCK_ENABLED", "false").strip().lower() != "true":
            raise BedrockProviderError("bedrock_disabled")
        if os.getenv("BEDROCK_SPEND_AUTHORIZED", "false").strip().lower() != "true":
            raise BedrockProviderError("spend_not_authorized")
        model_id = os.getenv("BEDROCK_MODEL_ID", "").strip()
        region = os.getenv("BEDROCK_REGION", "").strip()
        if not model_id or len(model_id) > 256 or any(ord(char) < 33 for char in model_id):
            raise BedrockProviderError("invalid_model_configuration")
        if not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", region):
            raise BedrockProviderError("invalid_region_configuration")
        try:
            tokens = int(os.getenv("BEDROCK_MAX_OUTPUT_TOKENS", "512"))
            calls = int(os.getenv("BEDROCK_MAX_CALLS_PER_RUN", "1"))
            timeout = float(os.getenv("BEDROCK_REQUEST_TIMEOUT_SECONDS", "10"))
            daily_calls = int(os.getenv("BEDROCK_MAX_CALLS_PER_DAY",os.getenv("MAX_BEDROCK_REQUESTS_PER_DAY","10")))
            daily_tokens = int(os.getenv("MAX_BEDROCK_TOKENS_PER_DAY","20000"))
        except ValueError as error:
            raise BedrockProviderError("invalid_inference_limits") from error
        if not 32 <= tokens <= 2048 or not 1 <= calls <= 4 or not 1 <= timeout <= 30 or not 1 <= daily_calls <= 1000 or not 1 <= daily_tokens <= 2_000_000:
            raise BedrockProviderError("invalid_inference_limits")
        profile = os.getenv("BEDROCK_PROFILE", "").strip() or None
        return cls(model_id, region, tokens, calls, timeout, daily_calls, daily_tokens, profile)


class BedrockConverse:
    """Single-attempt Converse client; never falls back to another provider."""
    def __init__(self, settings: BedrockSettings | None = None, *, session_factory=None, budget_reserver=None):
        self._settings = settings
        self._session_factory = session_factory
        self._budget_reserver = budget_reserver or self._reserve_daily_budget
        self._client = None
        self._calls: dict[str, int] = {}

    @property
    def settings(self):
        if self._settings is None:
            self._settings = BedrockSettings.from_env()
        return self._settings

    @property
    def configured_model_id(self):
        return self._settings.model_id if self._settings else os.getenv("BEDROCK_MODEL_ID") or None

    def _runtime(self):
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
                session = (self._session_factory or boto3.Session)(
                    profile_name=self.settings.profile,
                    region_name=self.settings.region,
                )
                self._client = session.client(
                    "bedrock-runtime",
                    region_name=self.settings.region,
                    config=Config(
                        connect_timeout=self.settings.timeout_seconds,
                        read_timeout=self.settings.timeout_seconds,
                        retries={"total_max_attempts": 1, "mode": "standard"},
                    ),
                )
            except Exception as error:
                raise BedrockProviderError("client_configuration") from error
        return self._client

    def _reserve_daily_budget(self, run_id: str, estimated_tokens: int):
        try:
            import redis
            client=redis.Redis.from_url(os.getenv("REDIS_URL","redis://redis:6379"),socket_timeout=1,socket_connect_timeout=1)
            day=datetime.now(timezone.utc).strftime("%Y%m%d")
            script=(
                "local c=tonumber(redis.call('HGET',KEYS[1],'calls') or '0'); "
                "local t=tonumber(redis.call('HGET',KEYS[1],'reserved_tokens') or '0'); "
                "if c+1>tonumber(ARGV[1]) or t+tonumber(ARGV[2])>tonumber(ARGV[3]) then return 0 end; "
                "redis.call('HINCRBY',KEYS[1],'calls',1); "
                "redis.call('HINCRBY',KEYS[1],'reserved_tokens',ARGV[2]); "
                "redis.call('HSET',KEYS[1],'last_run',ARGV[4]); "
                "if redis.call('TTL',KEYS[1])<0 then redis.call('EXPIRE',KEYS[1],86400) end; return 1"
            )
            accepted=client.eval(script,1,"botkernel:bedrock-budget:"+day,
                self.settings.max_calls_per_day,estimated_tokens,self.settings.max_tokens_per_day,run_id)
        except Exception as error:
            raise BedrockProviderError("budget_counter_unavailable") from error
        if not accepted:
            raise BedrockProviderError("inference_budget_exhausted")

    def invoke_json(self, *, run_id: str, system: str, payload: dict[str, Any], response_type: type[T]) -> tuple[T, dict[str, Any]]:
        settings = self.settings
        count = self._calls.get(run_id, 0)
        if count >= settings.max_calls_per_run:
            raise BedrockProviderError("call_limit_exceeded")
        self._calls[run_id] = count + 1
        encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > 16_000:
            raise BedrockProviderError("input_too_large")
        estimated_tokens=len(system.encode("utf-8"))+len(encoded.encode("utf-8"))+settings.max_output_tokens
        self._budget_reserver(run_id,estimated_tokens)
        try:
            response = self._runtime().converse(
                modelId=self.settings.model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": encoded}]}],
                inferenceConfig={
                    "maxTokens": settings.max_output_tokens,
                    "temperature": 0.1,
                },
            )
        except Exception as error:
            category, retryable = classify_bedrock_error(error)
            raise BedrockProviderError(category, retryable=retryable) from error
        stop = response.get("stopReason")
        if stop in {"guardrail_intervened", "content_filtered"}:
            raise BedrockProviderError("model_refusal")
        if stop == "max_tokens":
            raise BedrockProviderError("response_truncated")
        try:
            blocks = response["output"]["message"]["content"]
            text = "".join(block["text"] for block in blocks if isinstance(block, dict) and isinstance(block.get("text"), str))
            if not text or len(text.encode("utf-8")) > 16_000:
                raise BedrockProviderError("invalid_model_response")
            parsed = response_type.model_validate_json(text)
        except BedrockProviderError:
            raise
        except Exception as error:
            raise BedrockProviderError("invalid_model_response") from error
        usage = response.get("usage") or {}
        provenance = {
            "provider": "bedrock",
            "model_id": self.settings.model_id,
            "input_tokens": usage.get("inputTokens"),
            "output_tokens": usage.get("outputTokens"),
            "invocations": self._calls[run_id],
        }
        return parsed, provenance


class BedrockAgentReasoner:
    name = "bedrock"

    def __init__(self, client: BedrockConverse | None = None):
        self.client = client or BedrockConverse()

    @property
    def model_id(self):
        return self.client.configured_model_id

    def decide(self, role: str, telemetry: dict[str, Any], run_id: str) -> tuple[AgentDecision, dict[str, Any]]:
        system = (
            "You are an advisory capacity-planning analyst for a local simulator. "
            "Use only supplied evidence. Do not invent utilization or other metrics, "
            "and never issue tools or commands. Return exactly one JSON object matching "
            "the requested schema. NO_OP requires proposed_delta 0. PROPOSE requires "
            "a nonzero delta from -3 to 3; cost may only decrease and performance may "
            "only increase. Evidence references must be exact supplied action IDs or "
            "resource references. A proposal is not an authorization."
        )
        decision, provenance = self.client.invoke_json(
            run_id=run_id,
            system=system,
            payload={"agent_role": role, "observations": telemetry,
                     "response_schema": {
                         "decision": "PROPOSE|NO_OP", "resource": "observed resource id",
                         "proposed_delta": "integer -3..3, zero iff NO_OP",
                         "reason": "brief evidence-grounded explanation",
                         "evidence_references": "list of supplied reference IDs",
                         "uncertainties": "list of limitations"}},
            response_type=AgentDecision,
        )
        if decision.resource != telemetry.get("id"):
            raise BedrockProviderError("invalid_resource_reference")
        evidence = {f"resource:{telemetry['id']}"}
        evidence.update(item["action_id"] for item in telemetry.get("recent_effects", []) if isinstance(item, dict) and isinstance(item.get("action_id"), str))
        if any(ref not in evidence for ref in decision.evidence_references):
            raise BedrockProviderError("invalid_evidence_reference")
        if _contains_unrecognized_reference(decision.model_dump(), evidence):
            raise BedrockProviderError("invalid_evidence_reference")
        if role == "cost" and decision.proposed_delta > 0:
            raise BedrockProviderError("invalid_action_direction")
        if role == "performance" and decision.proposed_delta < 0:
            raise BedrockProviderError("invalid_action_direction")
        if decision.decision == "PROPOSE":
            capacity = telemetry.get("capacity")
            if not isinstance(capacity, int) or not 1 <= capacity + decision.proposed_delta <= 20:
                raise BedrockProviderError("action_out_of_bounds")
        if telemetry.get("controller_hold") or telemetry.get("controller_status") in {"HOLD", "VERIFYING", "ESCALATED"} or telemetry.get("pending_action"):
            raise BedrockProviderError("action_blocked_by_local_policy")
        return decision, provenance


def _contains_unrecognized_reference(value: Any, allowed: set[str]) -> bool:
    reference_pattern = re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|"
        r"\bincident:\d+\b",
        re.IGNORECASE,
    )
    if isinstance(value, str):
        return any(match.group(0).lower() not in {item.lower() for item in allowed}
                   for match in reference_pattern.finditer(value))
    if isinstance(value, dict):
        return any(_contains_unrecognized_reference(item, allowed) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unrecognized_reference(item, allowed) for item in value)
    return False


def classify_bedrock_error(error: Exception) -> tuple[str, bool]:
    try:
        from botocore.exceptions import (
            ClientError, ConnectTimeoutError, EndpointConnectionError,
            ReadTimeoutError, NoCredentialsError, PartialCredentialsError,
        )
        if isinstance(error, (NoCredentialsError, PartialCredentialsError)):
            return "credentials_unavailable", False
        if isinstance(error, (ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError)):
            return "request_timeout_or_endpoint_unavailable", True
        if isinstance(error, ClientError):
            code = error.response.get("Error", {}).get("Code", "")
            if code in {"AccessDeniedException", "UnauthorizedException"}:
                return "access_denied", False
            if code in {"ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException"}:
                return "throttled", True
            if code in {"ResourceNotFoundException", "ValidationException"}:
                return "model_or_request_unavailable", False
            if code in {"ModelNotReadyException", "ServiceUnavailableException", "ModelTimeoutException"}:
                return "model_temporarily_unavailable", True
            return "bedrock_service_error", False
    except ImportError:
        pass
    return "bedrock_client_error", False
