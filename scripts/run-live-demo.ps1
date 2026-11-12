$ErrorActionPreference = "Stop"
if (-not $env:BOTKERNEL_OPERATOR_TOKEN) { throw "Set BOTKERNEL_OPERATOR_TOKEN to a strong random credential before starting." }
$project = if ($env:BOTKERNEL_LIVE_DEMO_PROJECT) {
    $env:BOTKERNEL_LIVE_DEMO_PROJECT
} else {
    "botkernel-live-demo-" + [guid]::NewGuid().ToString("N").Substring(0, 8)
}
$apiPort = $env:BOTKERNEL_API_PORT
if (-not $apiPort) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $apiPort = $listener.LocalEndpoint.Port.ToString()
    $listener.Stop()
}
$env:BOTKERNEL_API_PORT = $apiPort
$env:DEMO_TIMEOUT_SECONDS = "180"
$apiUrl = "http://127.0.0.1:$apiPort"

& docker compose -p $project --profile stability --profile demo up -d --build postgres redis kafka init api publisher worker recovery controller live-demo
if ($LASTEXITCODE -ne 0) {
    throw "Unable to start the local demo stack."
}

$ready = $false
$lastReadinessError = "No response from the API."
$readyDeadline = (Get-Date).AddSeconds(180)
while (-not $ready -and (Get-Date) -lt $readyDeadline) {
    try {
        Invoke-RestMethod -Uri "$apiUrl/ready" -TimeoutSec 3 | Out-Null
        $ready = $true
    } catch {
        $lastReadinessError = $_.Exception.Message
        Start-Sleep -Seconds 2
    }
}
if (-not $ready) {
    throw "Local API did not become ready: $lastReadinessError"
}

$demoContainer = (& docker compose -p $project --profile stability --profile demo ps --all -q live-demo).Trim()
if (-not $demoContainer) {
    throw "The bounded live-demo container was not created."
}

$demoDone = $false
$demoDeadline = (Get-Date).AddSeconds(240)
while (-not $demoDone -and (Get-Date) -lt $demoDeadline) {
    $state = (& docker inspect --format '{{.State.Status}}|{{.State.ExitCode}}' $demoContainer).Trim() -split "\|"
    if ($state[0] -eq "exited") {
        if ($state[1] -ne "0") {
            & docker compose -p $project --profile stability --profile demo logs --no-color live-demo
            throw "The live demo exited with code $($state[1])."
        }
        $demoDone = $true
    } else {
        Start-Sleep -Seconds 2
    }
}
if (-not $demoDone) {
    throw "The live demo did not finish within the 240-second process bound."
}

$demoOutput = & docker compose -p $project --profile stability --profile demo logs --no-color live-demo
Write-Host $demoOutput
$incidents = Invoke-RestMethod -Uri "$apiUrl/incidents" -TimeoutSec 10 -Headers @{ Authorization = "Bearer $env:BOTKERNEL_OPERATOR_TOKEN" }
Write-Host "Persisted incidents: $($incidents.Count)"
Write-Host "API: $apiUrl"
Write-Host "Start the dashboard with BOTKERNEL_API_TARGET=$apiUrl."
Write-Host "Cleanup (preserves local volumes): docker compose -p $project down"
