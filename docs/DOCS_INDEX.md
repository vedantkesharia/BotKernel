# Documentation index

Start with the [project README](../README.md), [architecture](ARCHITECTURE.md), [engineering results](ENGINEERING_RESULTS.md), [validation](VALIDATION.md), [demo guide](DEMO_GUIDE.md) and [roadmap](ROADMAP.md). This small public structure separates design, measurements, executed checks, usage and remaining work. Component contracts and deployment runbooks remain linked below rather than duplicated.

Canonical evidence belongs in `ENGINEERING_RESULTS.md` and `VALIDATION.md`; operating instructions belong in `DEMO_GUIDE.md`. Inclusion in this index does not certify additional runs.

## A/B/C/D/E audit

Inventory: **25 tracked Markdown files** observed on November 14, 2026, in the original publication inventory. Categories are publication dispositions, not implementation grades:

- **A - Public developer/user documentation.**
- **B - Public architecture/design/benchmark documentation.**
- **C - Private handoff/history.**
- **D - Internal operational/sensitive documentation.**
- **E - Redundant/outdated documentation.**

| Tracked path | Class | Disposition |
|---|---|---|
| `README.md` | A | Public entry and canonical navigation |
| `apps/dashboard/README.md` | A | Six routes, private auth and local usage |
| `benchmarks/results/88b0aa07-e4bb-40b9-9bab-e11d9fdf33f0/report.md` | B | Preserve historical virtual evaluation; not service performance |
| `benchmarks/results/real-system/0d481657-cf8c-4c4a-89fc-36ec0f2f86af/report.md` | B | Preserve original measured run and workload limits |
| `benchmarks/results/real-system/65a08540-fb16-4637-b2e9-95bd314a909a/report.md` | B | Preserve original measured run and workload limits |
| `benchmarks/results/real-system/ad2c84bc-3c6a-4dae-bc5d-4072e9367038/report.md` | B | Preserve original measured run and workload limits |
| `docs/ARCHITECTURE.md` | B | Current topology and correctness boundaries |
| `docs/AWS_COST_SAFETY.md` | A | Cloud safety contract; current recorded status belongs in validation |
| `docs/AWS_DEMO_READY.md` | E | Original archived; sanitized redirect to demo/validation |
| `docs/BEDROCK_ACCEPTANCE.md` | A | Provider contracts and actual November 14 usage |
| `docs/BENCHMARKS.md` | B | Definitions, measured/model distinction and limitations |
| `docs/BENCHMARK_AUDIT.md` | B | Historical methodology audit; preserve unfavorable findings |
| `docs/COLLECTIVE_STABILITY_ALGORITHM.md` | B | Implemented controller, sustained verification and auth |
| `docs/DEMO_RECORDING_GUIDE.md` | E | Original archived; sanitized redirect to demo guide |
| `docs/DEMO_WALKTHROUGH.md` | E | Original archived; sanitized redirect to demo guide |
| `docs/DESIGN_DECISIONS.md` | E | Original archived; sanitized redirect to architecture |
| `docs/FAILURE_RECOVERY.md` | A | Failure/reconciliation contract; retain caveats |
| `docs/IMPLEMENTATION_WALKTHROUGH.md` | E | Original archived; sanitized redirect to architecture/demo |
| `docs/LANGGRAPH.md` | B | Strict provider gate and durable lifecycle |
| `docs/OBSERVABILITY.md` | A | Signal semantics and historical stopped AWS proof |
| `docs/PHASE2_DESIGN.md` | E | Historical proposal differs from implemented controller; redirect to architecture/controller |
| `docs/PORTFOLIO.md` | E | Original archived; sanitized redirect to results |
| `docs/ROADMAP.md` | A | Actual status and remaining acceptance |
| `infra/kubernetes/README.md` | A | Local kind core runtime verified; optional modes and EKS untested |
| `infra/terraform/README.md` | A | Private single-host deployment, not HA |

## Separately observed private material

`docs/PROJECT_HANDOFF.md` is **C (private handoff/history)**. `git ls-files -- docs/PROJECT_HANDOFF.md` returned no tracked path, and `git check-ignore` confirmed it is ignored. It is excluded from the 25-file tracked inventory. The archived one-off deployment scripts are **D (internal operational/sensitive)** and are outside this Markdown inventory. Historical public benchmark reports remain B; age alone does not make evidence private history.

## Publication boundaries

New canonical results must identify what actually ran, the source/artifacts used and unresolved limitations. Only executed workloads with recorded artifacts support benchmark claims. Historical reports are preserved rather than rewritten to match later source. Backend suite and browser/model acceptance do not, by themselves, validate later benchmark changes.

Legacy paths above are inventory labels, not recommended public links. The seven legacy guides have been archived and replaced by sanitized redirects. The 23 one-off deployment scripts have also been archived; optional manual index removal has not been performed. See [publication checklist](PUBLICATION_CHECKLIST.md). Canonical additions, this index/checklist and asset audits are outside the original 25-file count. Private handoffs and operating archives are not public navigation.

Current additions: [Kubernetes runtime acceptance](KUBERNETES_ACCEPTANCE.md) (public runtime evidence) and [resume evidence](RESUME_EVIDENCE.md) (public, qualified achievements).
