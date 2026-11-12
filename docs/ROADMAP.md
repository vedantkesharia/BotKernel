# Roadmap

## Current release state

BotKernel's local-first reliability platform includes FastAPI, PostgreSQL/Alembic, Kafka publisher/workers, Redis advisory state, a durable action ledger, simulator receipts, recovery, a Collective Stability Controller, independent Cost/Performance LangGraph processes, a read-only investigator and a five-route React dashboard. Bedrock Converse is implemented behind explicit gates and is offline-tested only. The controller and simulator are not production infrastructure telemetry, and no performance/superiority claim should be inferred from the seeded virtual evaluation.

The project includes private AWS deployment templates, but current cloud state and image digests are not asserted. A deterministic incident-to-investigation flow is verified locally. The dashboard/operator API requires an externally configured operator credential; runtime acceptance remains outstanding. Bedrock remains disabled and live inference is unverified. See [BEDROCK_ACCEPTANCE.md](BEDROCK_ACCEPTANCE.md) for the bounded local acceptance runner and approval checkpoint.

The local gateway-to-Kafka-to-controller-to-investigator walkthrough produced eight succeeded effects and a persisted incident/report. A separate isolated real-system benchmark now records actual admission and client-observed completion timings, ledger/effect outcomes and a worker crash/replay case. Five-seed episode-level comparisons complement the original virtual evaluation; neither is evidence of production capacity or accuracy. Final current-source backend tests passed twice (133 each); the dashboard build, 3 Vitest tests and 18 Chromium tests passed, with browser tests using an older isolated API image. See [BENCHMARKS.md](BENCHMARKS.md) for measurements and limitations. Live Bedrock inference, PostgreSQL/EBS backup restore, public operator authentication and hard cancellation of investigator computation remain unverified.

## Release priorities

1. Complete final release validation on current API and dashboard images; address remaining dense-graph navigation and browser coverage gaps.
2. Resolve why the deployed dashboard host-loopback port binding is absent; verify a safe local-only/SSM path without adding public ingress.
3. Run the prepared three-case Nova Micro acceptance only after separate approvals for read-only identity/state/profile/IAM/pricing checks and then paid inference; confirm model-region access, current pricing and credential route. Bedrock remains disabled.
4. Add authentication, authorization, CSRF defenses and audit controls before any public/shared-network operator exposure.
5. Repeat the real-system workloads across more runs and measure internal phase timings, consumer lag and workload CPU/memory where instrumentation supports them; broaden episode-level evaluation without retuning labels or selecting favorable seeds.
6. Back up PostgreSQL and export Kafka/checkpoints/reports/benchmark outputs; test restore before upgrades or teardown. Keep the AWS instance within its manual approved runtime and stop it when finished.

## Functional follow-up

- Close remaining Phase 1 schema-drift, startup/dependency, graceful-shutdown and cross-process reliability acceptance gaps; the correctness authority remains PostgreSQL, not Redis.
- Broaden the episode-level evaluation and investigate detector/hold tradeoffs without altering ground-truth labels to favor the controller.
- Measure internal database/Kafka dispatch phases and workload CPU and memory separately from virtual simulator metrics.
- Expand browser coverage for investigation failure/accessibility states and dense mobile graph behavior.
- Keep operator recovery actions human-approved. No live infrastructure remediation is in scope.

## Explicitly not complete

Cloud access, deployments and paid inference require explicit authorization. Do not infer the current state or cost of any historical deployment. See [the deployment guide](../infra/terraform/README.md), [architecture](ARCHITECTURE.md), [LangGraph/Bedrock procedure](LANGGRAPH.md), and [local demo](DEMO_WALKTHROUGH.md).
