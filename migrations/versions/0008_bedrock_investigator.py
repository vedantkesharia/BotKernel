from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade():
    op.drop_constraint("investigation_reports_provider_check", "investigation_reports")
    op.create_check_constraint(
        "investigation_reports_provider_check",
        "investigation_reports",
        "provider IN ('deterministic_mock', 'bedrock')",
    )
    op.drop_constraint("investigation_reports_error_category_check", "investigation_reports")
    op.create_check_constraint(
        "investigation_reports_error_category_check",
        "investigation_reports",
        "error_category IS NULL OR error_category IN ("
        "'execution_error', 'lease_expired', 'bedrock_disabled', 'spend_not_authorized', "
        "'invalid_model_configuration', 'invalid_region_configuration', 'invalid_inference_limits', "
        "'client_configuration', 'credentials_unavailable', 'request_timeout_or_endpoint_unavailable', "
        "'access_denied', 'throttled', 'model_or_request_unavailable', 'model_temporarily_unavailable', "
        "'bedrock_service_error', 'bedrock_client_error', 'model_refusal', 'response_truncated', "
        "'invalid_model_response', 'input_too_large', 'call_limit_exceeded', "
        "'budget_counter_unavailable', 'inference_budget_exhausted', 'invalid_evidence_reference', "
        "'invalid_resource_reference', 'invalid_action_direction', 'action_out_of_bounds', "
        "'action_blocked_by_local_policy', 'invocation_outcome_unknown', 'previous_invocation_failed')",
    )


def downgrade():
    raise RuntimeError("Restore backup instead of destructive downgrade")
