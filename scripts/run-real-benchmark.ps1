param(
    [ValidateRange(1,1000)][int]$Actions = 25,
    [ValidateRange(1,10)][int]$Concurrency = 1,
    [ValidateRange(0,10)][int]$Warmup = 1,
    [switch]$Recovery
)
$ErrorActionPreference = "Stop"
if ($Concurrency -gt $Actions) { throw "Concurrency cannot exceed action count." }
$root = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $root "benchmarks\compose.real-system.yaml"
$project = "bkbench-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
Write-Host "Dedicated project: $project"
Write-Host "This project creates new PostgreSQL and Kafka volumes and retains them."
& docker compose -p $project -f $compose --profile benchmark up --build -d postgres redis kafka init api publisher worker
if ($LASTEXITCODE -ne 0) { throw "Benchmark stack startup failed; inspect project $project." }
$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    $ErrorActionPreference = "Continue"
    & docker compose -p $project -f $compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=3).close()" 2>$null
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($exitCode -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw "Benchmark API was not ready; inspect project $project." }
& docker compose -p $project -f $compose --profile benchmark run --build --rm --no-deps benchmark python -m botkernel.real_benchmark --actions $Actions --concurrency $Concurrency --warmup $Warmup
if ($LASTEXITCODE -ne 0) { throw "Benchmark failed; inspect project $project and its artifacts." }
if ($Recovery) {
    & docker compose -p $project -f $compose stop worker
    if ($LASTEXITCODE -ne 0) { throw "Could not stop the benchmark-owned worker." }
    & docker compose -p $project -f $compose --profile benchmark run --rm --no-deps benchmark python -m botkernel.real_benchmark_recovery
    if ($LASTEXITCODE -ne 0) { throw "Recovery benchmark failed; inspect project $project and its artifacts." }
}
Write-Host "Stop only this benchmark's containers with:"
Write-Host "docker compose -p $project -f `"$compose`" stop"
Write-Host "Do not use down -v; database and Kafka volumes are retained."
