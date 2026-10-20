[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [ValidateRange(5, 180)]
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BackendUrl = "http://127.0.0.1:8000/api/health"
$FrontendUrl = "http://127.0.0.1:5173/"
$LogDirectory = Join-Path $ProjectRoot ".tmp\runtime-logs"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FrontendDirectory = Join-Path $ProjectRoot "frontend"
$NodeModules = Join-Path $FrontendDirectory "node_modules"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

function Test-HttpReady {
    param(
        [Parameter(Mandatory)] [string]$Url,
        [string]$RequiredText = ""
    )
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ne 200) { return $false }
        return -not $RequiredText -or $response.Content.Contains($RequiredText)
    } catch {
        return $false
    }
}

function Get-ListenerProcessId {
    param([Parameter(Mandatory)] [int]$Port)
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @("127.0.0.1", "::1") } |
        Select-Object -First 1
    if ($listener) { return [int]$listener.OwningProcess }
    return $null
}

function Assert-PortAvailable {
    param(
        [Parameter(Mandatory)] [int]$Port,
        [Parameter(Mandatory)] [string]$ServiceName
    )
    $owner = Get-ListenerProcessId -Port $Port
    if ($owner) {
        throw "$ServiceName is not healthy, but localhost port $Port is already occupied by process $owner. Stop that process or configure a different port, then run Start-NeuroVista.cmd again."
    }
}

function Wait-ForService {
    param(
        [Parameter(Mandatory)] [string]$ServiceName,
        [Parameter(Mandatory)] [string]$Url,
        [Parameter(Mandatory)] [string]$RequiredText,
        [Parameter(Mandatory)] [System.Diagnostics.Process]$Process,
        [Parameter(Mandatory)] [string]$StandardOutputLog,
        [Parameter(Mandatory)] [string]$StandardErrorLog
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpReady -Url $Url -RequiredText $RequiredText) { return }
        if ($Process.HasExited) {
            $details = @()
            if (Test-Path $StandardErrorLog) { $details += Get-Content $StandardErrorLog -Tail 20 }
            if (Test-Path $StandardOutputLog) { $details += Get-Content $StandardOutputLog -Tail 20 }
            throw "$ServiceName exited before becoming ready (exit code $($Process.ExitCode)).`n$($details -join [Environment]::NewLine)`nLogs: $StandardOutputLog and $StandardErrorLog"
        }
        Start-Sleep -Milliseconds 500
    }
    throw "$ServiceName did not become ready within $TimeoutSeconds seconds. Review $StandardOutputLog and $StandardErrorLog."
}

try {
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "The existing Python environment was not found at $Python. Follow the README setup steps, then retry."
    }
    if (-not (Test-Path -LiteralPath $NodeModules -PathType Container)) {
        throw "Frontend dependencies were not found at $NodeModules. Run 'npm install' in the frontend folder, then retry."
    }
    $Npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $Npm) {
        throw "npm.cmd was not found on PATH. Install Node.js 20 LTS or newer, then retry."
    }
    New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null

    $backendReady = Test-HttpReady -Url $BackendUrl -RequiredText '"service":"NeuroVista"'
    if ($backendReady) {
        $backendPid = Get-ListenerProcessId -Port 8000
        Write-Host "[NeuroVista] Reusing healthy backend on port 8000 (PID $backendPid)." -ForegroundColor Green
    } else {
        Assert-PortAvailable -Port 8000 -ServiceName "NeuroVista backend"
        $backendOut = Join-Path $LogDirectory "backend-$Timestamp.stdout.log"
        $backendErr = Join-Path $LogDirectory "backend-$Timestamp.stderr.log"
        $backend = Start-Process -FilePath $Python -ArgumentList @(
            "-m", "uvicorn", "app.main:app", "--app-dir", "backend",
            "--host", "127.0.0.1", "--port", "8000"
        ) -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru
        Wait-ForService -ServiceName "NeuroVista backend" -Url $BackendUrl -RequiredText '"service":"NeuroVista"' -Process $backend -StandardOutputLog $backendOut -StandardErrorLog $backendErr
        $backendPid = Get-ListenerProcessId -Port 8000
        Write-Host "[NeuroVista] Backend ready on port 8000 (PID $backendPid)." -ForegroundColor Green
    }

    $frontendReady = Test-HttpReady -Url $FrontendUrl -RequiredText '<div id="root"></div>'
    if ($frontendReady) {
        $frontendPid = Get-ListenerProcessId -Port 5173
        Write-Host "[NeuroVista] Reusing healthy frontend on port 5173 (PID $frontendPid)." -ForegroundColor Green
    } else {
        Assert-PortAvailable -Port 5173 -ServiceName "NeuroVista frontend"
        $frontendOut = Join-Path $LogDirectory "frontend-$Timestamp.stdout.log"
        $frontendErr = Join-Path $LogDirectory "frontend-$Timestamp.stderr.log"
        $frontend = Start-Process -FilePath $Npm -ArgumentList @("run", "dev") -WorkingDirectory $FrontendDirectory -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru
        Wait-ForService -ServiceName "NeuroVista frontend" -Url $FrontendUrl -RequiredText '<div id="root"></div>' -Process $frontend -StandardOutputLog $frontendOut -StandardErrorLog $frontendErr
        $frontendPid = Get-ListenerProcessId -Port 5173
        Write-Host "[NeuroVista] Frontend ready on port 5173 (PID $frontendPid)." -ForegroundColor Green
    }

    Write-Host "[NeuroVista] Ready: $FrontendUrl" -ForegroundColor Cyan
    Write-Host "[NeuroVista] Logs: $LogDirectory"
    if (-not $NoBrowser) {
        Start-Process $FrontendUrl
    }
    exit 0
} catch {
    Write-Host "[NeuroVista] STARTUP FAILED" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Logs, when available: $LogDirectory" -ForegroundColor Yellow
    exit 1
}
