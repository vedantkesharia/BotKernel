param([Parameter(Mandatory=$true)][string]$Name, [int]$Timeout=120)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$script = [IO.File]::ReadAllText((Join-Path $root "$Name.sh"))
$request = @{DocumentName='AWS-RunShellScript';InstanceIds=@('i-0b30b3106988f698e');Comment="Approved BotKernel $Name";Parameters=@{commands=@($script);executionTimeout=@("$Timeout")}}
$path = Join-Path $root "$Name-request.json"
[IO.File]::WriteAllText($path, ($request | ConvertTo-Json -Depth 6), (New-Object Text.UTF8Encoding($false)))
aws ssm send-command --cli-input-json "file://$path" --profile botkernel-dev --region us-east-2 --query Command.CommandId --output text
if ($LASTEXITCODE -ne 0) { throw 'SSM submission failed; do not assume remote execution' }
