# Local setup

Use a new Compose project and unused loopback ports. Check Docker memory and existing project ownership first; never stop another project or delete its volumes to make room. The simulator requires no AWS account or model.

## Configure credentials (PowerShell)

From a fresh clone, create an ignored local environment without printing credentials:

```powershell
if (Test-Path .env) { throw 'Existing .env preserved: review it instead of overwriting.' }
$settings = Get-Content .env.example -Raw
foreach ($key in @('BOTKERNEL_OPERATOR_TOKEN','BOTKERNEL_AGENT_TOKEN','BOTKERNEL_METRICS_TOKEN')) {
    $credential = python -c "import secrets; print(secrets.token_urlsafe(48))"
    $settings = [regex]::Replace($settings, "(?m)^${key}=.*$", "${key}=$credential")
}
[IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $settings)
```

Keep `.env` private. Operator, agent and metrics credentials are distinct. On shared computers restrict the file ACL to its owner. Do not paste credentials into issues, logs or recordings. API authentication fails closed when configuration is missing or unsafe.

The example API port is 18019 and `BOTKERNEL_API_TARGET=http://127.0.0.1:18019`. If occupied, choose another unused loopback port and update BOTH values. Vite reads the root environment; it will not silently guess an API target.

## Start the local application

```powershell
docker compose -p botkernel-demo --profile stability up --build -d postgres redis kafka init api publisher worker recovery controller
Invoke-RestMethod http://127.0.0.1:18019/health
Invoke-RestMethod http://127.0.0.1:18019/ready
npm --prefix apps/dashboard ci
npm --prefix apps/dashboard run dev
```

Use the printed Vite URL. Sign in with the private operator credential before recording; the browser keeps it in memory only, so reload requires sign-in again. Navigate through `/app`, `/app/agents`, `/app/graph`, `/app/incidents` and `/app/experiments`.

LangGraph agents are a separate opt-in profile. Set a bounded `AGENT_MAX_RUNS`, review their resource targets and keep providers deterministic unless a separately authorized experiment requires otherwise. An existing terminal checkpoint can be pending or review-required: inspect it rather than deleting it to get a new action.

See [demo guide](DEMO_GUIDE.md), [observability](OBSERVABILITY.md) and [dashboard details](../apps/dashboard/README.md). Optional monitoring needs its own protected metrics-token file; the core startup above does not enable monitoring or paid inference.

## Tests and safe shutdown

Use a separate validation project with its own PostgreSQL/Kafka volumes. The fixture creates a unique database/topic and cleans only those test-owned records:

```powershell
docker compose -p bk-validation up --build -d postgres redis kafka init
docker compose -p bk-validation --profile test run --build --rm tests
npm --prefix apps/dashboard test
npm --prefix apps/dashboard run build
```

Do not run heavy tests and benchmarks concurrently on a constrained Docker engine. In low-memory Linux containers, `MALLOC_ARENA_MAX=2` can bound glibc allocator arenas; record any environment changes rather than presenting different environments as matched measurements.

```powershell
docker compose -p botkernel-demo --profile stability stop
docker compose -p bk-validation stop
```

These commands retain volumes. No AWS resources or Bedrock calls are created by this local procedure. Do not use volume deletion, Docker pruning, factory reset or schema resets as routine recovery.
