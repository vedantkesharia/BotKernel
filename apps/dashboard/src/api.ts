export async function get<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Backend returned ${response.status}: ${await response.text()}`);
  return response.json();
}

export type Agent = {
  id: string; heartbeat: string; healthy: boolean;
  latest_decision?: {
    idempotency_key: string; provider: string; model_id: string | null;
    decision: "PROPOSE" | "NO_OP" | "ERROR"; resource: string; proposed_delta: number;
    reason: string; evidence_references: string[]; uncertainties: string[];
    input_tokens: number | null; output_tokens: number | null; invocation_count: number;
    error_category: string | null; gateway_approved: boolean; action_id: string | null;
    action_status?: string | null; effect_committed?: boolean | null;
  };
};
export type RuntimeHealth = {
  status: string;
  mode?: string;
  deployment_target?: string;
  cloud_mode?: string;
  resource_source?: string;
  real_infrastructure_remediation?: boolean;
};
export type Action = { id: string; agent: string; resource: string; state: string; created_at: string };
export type Resource = { id: string; capacity: number; version: number };
export type Graph = { nodes: { id: string; kind: string; label: string }[]; edges: { id: string; source: string; target: string; kind: string; inferred: boolean }[]; evidence: Effect[]; truncated: boolean };
export type Effect = { action_id: string; agent: string; resource: string; before_capacity: number; after_capacity: number; latency: number; observed_at: string };
export type Incident = {
  id: number;
  resource: string;
  score: number;
  status: "HOLD" | "VERIFYING" | "VERIFIED" | "ESCALATED" | "RESOLVED";
  opened_at: string;
  hold_until: string;
  verified_at?: string;
  resolved_at?: string;
  intervention_count: number;
  recurrence_count: number;
  healthy_samples: number;
  evidence: {
    latest?: { actions?: string[]; agents?: string[]; reversal_pairs?: string[][]; reason?: string; score?: number };
    origin?: { actions?: string[]; agents?: string[]; reversal_pairs?: string[][]; reason?: string; score?: number };
    last_detection?: { actions?: string[]; agents?: string[]; reversal_pairs?: string[][]; reason?: string; score?: number };
    lifecycle?: { transition: string; score: number }[];
  };
  operator_actions?: { id: number; action: "ACKNOWLEDGE" | "RESOLVE"; reason: string; actor: string; created_at: string }[];
};
export type EvaluationMetric = { mean: number | null; ci95_low: number | null; ci95_high: number | null; n: number };
export type EvaluationSummary = {
  scenario: string;
  mode: string;
  mode_label: string;
  seed_count: number;
  precision: EvaluationMetric;
  recall: EvaluationMetric;
  f1: EvaluationMetric;
  false_positive_rate: EvaluationMetric;
  mean_detection_delay_ticks: EvaluationMetric;
  oscillating_resource_changes: EvaluationMetric;
  intervention_count: EvaluationMetric;
  unnecessary_interventions: EvaluationMetric;
  incident_recurrences: EvaluationMetric;
  sustained_stabilization_success: EvaluationMetric;
  time_to_recovery_or_escalation_ticks: EvaluationMetric;
  application_latency_p95_ms: EvaluationMetric;
  completed_actions: EvaluationMetric;
  logical_actions_per_virtual_second: EvaluationMetric;
};
export type EvaluationPoint = { mode: string; tick: number; application_latency_ms: number; capacity_a: number; capacity_b: number; alarm_rate: number; ground_truth_harmful: boolean };
export type Evaluation = {
  run_id: string;
  created_at: string;
  scenario: string;
  scenarios: string[];
  seeds: number[];
  duration_ticks: number;
  summaries: EvaluationSummary[];
  time_series?: EvaluationPoint[];
  artifacts: Record<string, string>;
};

export type InvestigationFinding = { classification: "VERIFIED_FACT" | "DETERMINISTIC_INFERENCE" | "HYPOTHESIS"; description: string; supporting_actions: string[]; contradicting_actions: string[] };
export type InvestigationResult = { id: string; incident_id: number; status: "RUNNING" | "COMPLETE" | "INSUFFICIENT_EVIDENCE" | "FAILED"; provider: string; created_at: string; error_category: string | null; report: null | { conclusion: string; resource: string; contributing_agents: string[]; uncertainty: string; recommendation: string; human_approval_required: boolean; evidence_warnings: string[]; missing_references: string[]; findings: InvestigationFinding[]; model_id?: string | null; usage?: Record<string, number | string | null>; ai_analysis?: null | { status: string; explanation: string; hypotheses: string[]; cross_agent_analysis: string; instability_mechanism: string; supporting_references: string[]; contradictory_or_missing_evidence: string[]; preventive_actions: string[]; confidence_caveats: string[] }; effects: { action_id: string; agent: string; version: number; before_capacity: number; after_capacity: number; observed_at: string }[] } };
