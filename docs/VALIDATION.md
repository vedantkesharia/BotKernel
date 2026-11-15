# Validation and evidence

Implementation, local test execution and historical cloud acceptance are separate claims. No AWS calls or model requests were made during this local engineering pass on 2026-11-14.

## Current-source local checks

| Check | Executed result |
|---|---|
| Complete isolated PostgreSQL/Kafka backend suite | **255 passed, 1 skipped**, 0 failed; 145.87 seconds |
| Earlier focused benchmark/provider regression | **45 passed**, 46.89 seconds; followed by the complete final-source run above |
| Frontend production build | Passed, 3,057 modules; existing 605 KB main-chunk warning remains |
| Frontend Vitest | **6 passed** in one test file |
| Python compilation | Passed for backend, tests and new orchestration/export scripts |
| Compose configuration | Local and AWS-demo configuration passed; AWS used `infra/deploy/runtime.env.example`, no services started |
| Terraform | `fmt -check -recursive` and `validate -no-color` passed; no plan/apply or AWS access |
| Helm 3.21.0 | Strict lint passed; default/agents/observability renders parsed as **20/22/34 objects**, all Services ClusterIP |
| Publication checks | Local Markdown links resolve; SVG parses/renders; all **90** curated SHA-256 entries verified; `git diff --check` passed |
| Distributed benchmark | 18 runs; **912 measured actions + 78 warmups**, all confirmed with consistent versions and unique effects |
| Fault matrix | **5/5** recovered logical actions; receipt crash/duplicate delivery, publisher ACK-before-commit crash, publisher pause |
| Controller evaluation | 10 seeds, 8 scenarios, 3 policies: **240 virtual scenario-policy runs** |

Backend command, from the repository root after the named isolated dependencies were ready:

```powershell
docker compose -p bk-final-regression run --rm --no-deps `
  -e MALLOC_ARENA_MAX=2 `
  -v "${PWD}/botkernel:/app/botkernel:ro" `
  -v "${PWD}/tests:/app/tests:ro" `
  tests pytest -q -ra -p no:cacheprovider
npm --prefix apps/dashboard run build
npm --prefix apps/dashboard test
```

The source mounts test the current working tree, not merely the previously built test image. Performance measurements preceded the final private-target URL guard; a byte-for-byte reverse-delta check confirmed only that guard differs in two benchmark modules. Worker/core/API/observability hashes still match the measured source. See [source provenance](BENCHMARK_AUDIT.md#measured-source-versus-final-source-provenance). Tests use unique fixture databases/topics on isolated infrastructure. The allocator setting bounds glibc arenas on this memory-constrained Docker engine; it does not skip assertions. The skipped live Prometheus test requires a local Prometheus binary. One LangGraph deprecation warning remains. Do not present older failures under memory pressure as if they never happened.

The new benchmark containers were removed after their bounded workloads. Their new databases, Kafka topics and raw evidence were retained; existing development data and unrelated projects were preserved. [Measured results and raw distributions](ENGINEERING_RESULTS.md).

## Historical AWS acceptance

The bounded 2026-11-14 EC2/Compose run verified authenticated application access, an eight-action driver plus one preparatory action, one outbox/receipt/effect per logical action, 24 total effects and controller incident verification with two interventions and one recurrence. Genuine Nova Micro Cost and Performance calls returned advisory NO_OP decisions. A genuine model-backed Investigator report was persisted after one retained validation failure and a tested prompt correction. Four new requests were required for the three successful workflows; failed attempts and original Redis reservations were preserved.

Five Prometheus scrape targets, three Grafana dashboards, a 14-span correlated API/publisher/worker trace, CloudWatch logs and all six browser routes were verified during that run. Two separate deterministic LangGraph processes were also exercised; they are not the same thing as the deterministic oscillation driver or the sequential Bedrock harness.

The instance was verified stopped afterward. Current cloud state was not queried in this local pass. Old graph windows and ephemeral traces are not fresh telemetry. Sanitized aggregates are public; operator-specific evidence manifests remain private. No remote CI success is inferred from local results.

## Remaining acceptance limits

- Local kind Kubernetes runtime is now verified separately: 7 logical effects, quota/idempotency contention, worker restart, PostgreSQL persistence and Helm upgrades. Docker Desktop's built-in Kubernetes remains disabled. EKS, optional Kubernetes agents/observability and multi-node behavior were not tested. [Runtime evidence](KUBERNETES_ACCEPTANCE.md).
- No disaster-recovery restore drill, HA/failover validation or sustained production load test has passed.
- Frontend browser coverage was historically verified on AWS; it was not rerun against the stopped cloud deployment in this local pass. No frontend behavior changed here.
- Local SVG rendering/XML/geometry checks do not establish GitHub-hosted rendering; publication and remote CI remain owner actions.

Static validation commands and publication review are in [the publication checklist](PUBLICATION_CHECKLIST.md). Benchmark CPU/RAM observations are sampled shared-host measurements, not full host peaks or a service capacity guarantee.

## Subsequent Kubernetes acceptance

Core local kind runtime passed: seven effects, 32 HTTP submissions, concurrent quota/idempotency and controller holds, two explicit duplicate events, worker recovery, PostgreSQL PVC restart and Helm upgrades. Browser authentication/proxy checks and five routes passed after retaining a transient readiness-503 run. The Kafka probe and optional-claim corrections are documented with failures in [Kubernetes acceptance](KUBERNETES_ACCEPTANCE.md).

No backend application source changed in this task; the 255-pass/1-skip full regression above remains historical. New backend verification is the real Kubernetes admission/transport/persistence dataset, not a claimed full-suite rerun. Strict Helm/YAML checks and current frontend build/unit results are recorded with this acceptance. No AWS services were provisioned.

Current closure checks executed: frontend TypeScript/Vite production build passed (existing 605 KB chunk warning), 6 Vitest tests passed, authenticated Chromium checks passed on the Kubernetes deployment, strict Helm lint passed and default/agents/observability YAML rendered as 18/22/32 objects. Assertions checked conditional checkpoint claims, bounded Kafka readiness heap, TCP liveness and private Services. Compose configurations, Terraform fmt/validate, Python compilation and local Markdown links passed. The initial sandbox esbuild launch failed with EPERM before a permitted rerun passed. No full backend suite was repeated for these chart-only changes; all new correctness claims come from the recorded Kubernetes runtime cases.
