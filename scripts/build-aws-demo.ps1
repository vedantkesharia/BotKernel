$ErrorActionPreference = "Stop"

$apiImage = if ($env:BOTKERNEL_API_IMAGE) { $env:BOTKERNEL_API_IMAGE } else { "botkernel-api:local" }
$dashboardImage = if ($env:BOTKERNEL_DASHBOARD_IMAGE) { $env:BOTKERNEL_DASHBOARD_IMAGE } else { "botkernel-dashboard:local" }

docker build --file Dockerfile.deploy --tag $apiImage .
if ($LASTEXITCODE -ne 0) {
    throw "Backend image build failed."
}

docker build --file apps\dashboard\Dockerfile.deploy --tag $dashboardImage apps\dashboard
if ($LASTEXITCODE -ne 0) {
    throw "Dashboard image build failed."
}

Write-Host "Built $apiImage and $dashboardImage locally. No registry login or push was performed."
