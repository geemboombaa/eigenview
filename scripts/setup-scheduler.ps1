# setup-scheduler.ps1 — Register EigenView daily scan as Windows Task Scheduler job
# Run once: powershell -ExecutionPolicy Bypass -File scripts\setup-scheduler.ps1
# Requires: uv installed, EIGENVIEW_ROOT env var set or script run from repo root

param(
    [string]$ScanHour = "08",
    [string]$ScanMinute = "00",
    [string]$TaskName = "EigenView-DailyScan"
)

$RepoRoot = $PSScriptRoot | Split-Path -Parent
$UvExe = (Get-Command uv -ErrorAction SilentlyContinue)?.Source
if (-not $UvExe) {
    Write-Error "uv not found in PATH. Install: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
}

$LogDir = Join-Path $RepoRoot "data\logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

$ScriptBlock = @"
Set-Location '$RepoRoot'
`$LogFile = '$LogDir\scan-' + (Get-Date -Format 'yyyy-MM-dd') + '.log'
'[' + (Get-Date -Format 'HH:mm:ss') + '] EigenView daily scan started' | Out-File -FilePath `$LogFile -Append
& '$UvExe' run eigenview daily-scan 2>&1 | Out-File -FilePath `$LogFile -Append
'[' + (Get-Date -Format 'HH:mm:ss') + '] Scan complete' | Out-File -FilePath `$LogFile -Append
"@

$WrapperPath = Join-Path $RepoRoot "scripts\run-scan.ps1"
$ScriptBlock | Out-File -FilePath $WrapperPath -Encoding utf8 -Force

$Action  = New-ScheduledTaskAction -Execute "powershell.exe" `
           -Argument "-ExecutionPolicy Bypass -NonInteractive -File `"$WrapperPath`""
$Trigger = New-ScheduledTaskTrigger -Daily -At "${ScanHour}:${ScanMinute}"
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "EigenView pre-market daily scan at ${ScanHour}:${ScanMinute} ET" `
    -RunLevel Highest

Write-Host "Task '$TaskName' registered — runs daily at ${ScanHour}:${ScanMinute}" -ForegroundColor Green
Write-Host "Logs: $LogDir" -ForegroundColor Cyan
Write-Host "To run now: Start-ScheduledTask -TaskName '$TaskName'"
