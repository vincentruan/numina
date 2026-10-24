# scripts/dev/dev-all.ps1 — Launch all Numina dev servers (Windows)
#
# Usage:
#   make dev-all                              # default: term on Windows
#   make dev-all MODE=term                    # separate PowerShell windows (default)
#   make dev-all MODE=bg                      # background, log to files
#   make dev-all LOG=1                        # Python services -> log files
#   make dev-all MODE=bg LOG=1               # background + log files
#   make dev-all DB=pgsql                     # use PostgreSQL instead of SQLite
#   make dev-all CACHE=redis                  # use Redis instead of in-memory
#   make dev-all DB=pgsql CACHE=redis         # both
#
# Parameters:
#   MODE   — term | bg  (default: term — separate PowerShell windows)
#   LOG    — 0 (default) | 1 (Python services -> server/.dev-logs/)
#   DB     — sqlite (default) | pgsql
#   CACHE  — memory (default) | redis

$ErrorActionPreference = 'Stop'

# Force UTF-8 output for this PowerShell session
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ServerDir = "server"
$MainApp   = "frontend/apps/main"
$ChildApp  = "frontend/apps/child"
$Ports     = @(8000, 8001, 8002, 5173, 5174)

# ── parameter parsing ─────────────────────────────────────────────

$MODE = if ($env:DEV_MODE) { $env:DEV_MODE } elseif ($env:MODE) { $env:MODE } else { "" }
$LOG  = if ($env:DEV_LOG) { $env:DEV_LOG } elseif ($env:LOG) { $env:LOG } else { "0" }
$DB   = if ($env:DEV_DB) { $env:DEV_DB } elseif ($env:DB) { $env:DB } else { "sqlite" }
$CACHE = if ($env:DEV_CACHE) { $env:DEV_CACHE } elseif ($env:CACHE) { $env:CACHE } else { "memory" }

# Positional args
if ($args.Count -ge 1 -and $args[0] -match '^(tmux|term|bg)$') { $MODE = $args[0] }
if ($args.Count -ge 2 -and $args[1] -match '^[01]$') { $LOG = $args[1] }

# Default mode: term (separate PowerShell windows)
if (-not $MODE) {
    $MODE = "term"
}

# Normalize to lowercase (case-insensitive input)
$MODE = $MODE.ToLower()
$LOG  = $LOG.ToLower()
$DB   = $DB.ToLower()
$CACHE = $CACHE.ToLower()

# Validate
if ($MODE -notin @("term", "bg")) {
    Write-Host "x Unknown MODE: $MODE (options: term | bg)" -ForegroundColor Red
    Write-Host "  (tmux mode is not supported on Windows; use term or bg)" -ForegroundColor Yellow
    exit 1
}
if ($LOG -notin @("0", "1")) {
    Write-Host "x Unknown LOG: $LOG (options: 0 | 1)" -ForegroundColor Red
    exit 1
}
if ($DB -notin @("sqlite", "pgsql")) {
    Write-Host "x Unknown DB: $DB (options: sqlite | pgsql)" -ForegroundColor Red
    exit 1
}
if ($CACHE -notin @("memory", "redis")) {
    Write-Host "x Unknown CACHE: $CACHE (options: memory | redis)" -ForegroundColor Red
    exit 1
}

# ── log directory setup ──────────────────────────────────────────

$RootDir = (Resolve-Path ".").Path
$ServerAbs = Join-Path $RootDir $ServerDir
$MainAbs   = Join-Path $RootDir $MainApp
$ChildAbs  = Join-Path $RootDir $ChildApp

$LogDirAbs = ""
if ($LOG -eq "1") {
    $LogDirAbs = Join-Path $ServerAbs ".dev-logs"
    New-Item -ItemType Directory -Force -Path $LogDirAbs | Out-Null
}

$DevLogDirValue = if ($LOG -eq "1") { $LogDirAbs } else { "0" }

# ── helpers ──────────────────────────────────────────────────────

function Write-LogInfo {
    if ($LOG -eq "1") {
        Write-Host "  Python logs -> $LogDirAbs\{backend,agent,worker}.log"
    }
}

function Test-Port {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return ($null -ne $conn -and $conn.State -eq 'Listen')
}

function Invoke-CheckDeps {
    Write-Host "Checking and syncing dependencies..."
    # Call uv/pnpm directly instead of `make install` to avoid MSYS2/make
    # encoding issues (Chinese echo output goes through sh.exe ANSI code page).
    $ServerDirAbs = Join-Path $RootDir $ServerDir
    $FrontendDirAbs = Join-Path $RootDir "frontend"

    Write-Host "Installing server dependencies (uv sync, backend/agent/worker + dev group)..."
    Push-Location $ServerDirAbs
    try {
        & uv sync --extra backend --extra agent --extra worker --all-groups
        if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
    } finally { Pop-Location }

    Write-Host "Installing frontend dependencies (pnpm install)..."
    Push-Location $FrontendDirAbs
    try {
        & pnpm install
        if ($LASTEXITCODE -ne 0) { throw "pnpm install failed" }
    } finally { Pop-Location }

    Write-Host "All dependencies installed."
}

function Invoke-CheckPorts {
    $occupied = $false
    foreach ($port in $Ports) {
        if (Test-Port $port) {
            Write-Host "x Port $port is already in use:" -ForegroundColor Red
            Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
                Where-Object State -eq 'Listen' |
                Format-Table LocalPort, OwningProcess, State -AutoSize
            $occupied = $true
        }
    }
    if ($occupied) {
        Write-Host "Run 'make stop-dev-all' first to free the ports."
        return $false
    }
    return $true
}

# ── infrastructure checks ────────────────────────────────────────

function Test-InfraService {
    param([int]$Port, [string]$Name)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return ($null -ne $conn)
}

function Invoke-CheckInfra {
    $ok = $true

    if ($DB -eq "pgsql") {
        Write-Host "Checking PostgreSQL (port 5432)..."
        if (-not (Test-InfraService -Port 5432 -Name "PostgreSQL")) {
            Write-Host "x PostgreSQL is not running on port 5432." -ForegroundColor Red
            Write-Host "  Start it with: docker compose --profile postgres up -d postgres" -ForegroundColor Yellow
            $ok = $false
        } else {
            Write-Host "  + PostgreSQL :5432 OK" -ForegroundColor Green
        }
    }

    if ($CACHE -eq "redis") {
        Write-Host "Checking Redis (port 6379)..."
        if (-not (Test-InfraService -Port 6379 -Name "Redis")) {
            Write-Host "x Redis is not running on port 6379." -ForegroundColor Red
            Write-Host "  Start it with: docker compose up -d redis" -ForegroundColor Yellow
            $ok = $false
        } else {
            Write-Host "  + Redis :6379 OK" -ForegroundColor Green
        }
    }

    return $ok
}

# ── separate windows mode ────────────────────────────────────────

function Launch-Terminal {
    Write-Host "Launching 5 PowerShell windows..."

    # Use a temp directory for launcher scripts
    $tmpDir = Join-Path $env:TEMP "numina-dev-wt"
    New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

    $services = @(
        @{ Name = "backend";  Port = 8000; Dir = $ServerAbs; IsPython = $true;  Cmd = "uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000" }
        @{ Name = "agent";    Port = 8001; Dir = $ServerAbs; IsPython = $true;  Cmd = "uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001" }
        @{ Name = "worker";   Port = 8002; Dir = $ServerAbs; IsPython = $true;  Cmd = "uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002" }
        @{ Name = "frontend"; Port = 5173; Dir = $MainAbs;   IsPython = $false; Cmd = "pnpm dev --host 0.0.0.0" }
        @{ Name = "child";    Port = 5174; Dir = $ChildAbs;  IsPython = $false; Cmd = "pnpm dev --host 0.0.0.0" }
    )

    $pwshPath = (Get-Command pwsh).Source

    # Write per-service launcher scripts and start them
    foreach ($svc in $services) {
        $scriptPath = Join-Path $tmpDir "$($svc.Name).ps1"
        $scriptLines = @(
            '$ErrorActionPreference = "Continue"'
            '$OutputEncoding = [System.Text.Encoding]::UTF8'
            '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8'
            '$host.UI.RawUI.WindowTitle = "' + $svc.Name + ' :' + $svc.Port + '"'
            "Set-Location '$($svc.Dir)'"
            "Write-Host '=== $($svc.Name) :$($svc.Port) ===' -ForegroundColor Cyan"
        )
        if ($svc.IsPython -and $LOG -eq "1") {
            $scriptLines += "`$env:DEV_LOG_DIR = '$DevLogDirValue'"
        }
        $scriptLines += "& $($svc.Cmd)"
        $scriptLines += "Read-Host 'Press Enter to close'"
        $scriptLines | Set-Content -Path $scriptPath -Encoding UTF8

        # Start each service in its own PowerShell window
        Start-Process -FilePath $pwshPath -ArgumentList "-NoExit", "-File", "`"$scriptPath`"" -WindowStyle Normal
    }

    Write-Host ""
    Write-Host "5 services launched in separate PowerShell windows."
    Write-Host "  Stop: make stop-dev-all"
    Write-LogInfo
    return $true
}

# ── background mode ──────────────────────────────────────────────

function Launch-Background {
    Write-Host "Launching 5 background processes (MODE=bg)..."

    $LogDir = Join-Path $ServerAbs ".dev-logs"
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

    $services = @(
        @{ Name = "backend";  Port = 8000; Dir = $ServerAbs; Cmd = "uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000"; IsPython = $true }
        @{ Name = "agent";    Port = 8001; Dir = $ServerAbs; Cmd = "uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001"; IsPython = $true }
        @{ Name = "worker";   Port = 8002; Dir = $ServerAbs; Cmd = "uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002"; IsPython = $true }
        @{ Name = "frontend"; Port = 5173; Dir = $MainAbs;   Cmd = "pnpm dev --host 0.0.0.0"; IsPython = $false }
        @{ Name = "child";    Port = 5174; Dir = $ChildAbs;  Cmd = "pnpm dev --host 0.0.0.0"; IsPython = $false }
    )

    $procIds = @()
    foreach ($svc in $services) {
        $logFile = Join-Path $LogDir "$($svc.Name).log"
        $pwshScript = @"
Set-Location '$($svc.Dir)'
`$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$(if ($svc.IsPython) { "`$env:DEV_LOG_DIR = '$DevLogDirValue'" })
& $($svc.Cmd)
"@
        $proc = Start-Process pwsh -ArgumentList "-NoProfile", "-Command", $pwshScript `
            -RedirectStandardOutput $logFile `
            -RedirectStandardError (Join-Path $LogDir "$($svc.Name)-err.log") `
            -PassThru -WindowStyle Hidden

        $procIds += $proc.Id
        Write-Host "  + $($svc.Name) :$($svc.Port) (PID $($proc.Id)) -> $logFile"
    }

    # Write PID file for stop-dev-all
    $pidFile = Join-Path $RootDir ".numina" "dev-pids.json"
    New-Item -ItemType Directory -Force -Path (Split-Path $pidFile) | Out-Null
    $pidData = @{
        services = $services | ForEach-Object { @{ name = $_.Name; port = $_.Port } }
        pids = $procIds
        startedAt = (Get-Date -Format "o")
    } | ConvertTo-Json
    Set-Content -Path $pidFile -Value $pidData -Encoding UTF8

    Write-Host ""
    Write-Host "All services running in background."
    if ($LOG -eq "1") {
        Write-Host "  Python logs (via setup_logging): $LogDirAbs\{backend,agent,worker}.log"
    }
    Write-Host "  Shell stdout/stderr: $LogDir\{backend,agent,worker,frontend,child}.log"
    Write-Host ""
    Write-Host "Stop: make stop-dev-all"

    # Keep script alive until Ctrl+C
    try {
        Write-Host "Press Ctrl+C to stop all services..."
        Wait-Process -Id $procIds -ErrorAction SilentlyContinue
    } finally {
        Write-Host "`nStopping all services..."
        foreach ($procId in $procIds) {
            try {
                $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($p) {
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                    # Also kill child processes
                    Get-CimInstance Win32_Process -Filter "ParentProcessId = $procId" -ErrorAction SilentlyContinue |
                        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
                }
            } catch {}
        }
        Write-Host "All services stopped."
    }
}

# ── main ─────────────────────────────────────────────────────────

Write-Host "=== Numina dev-all (Windows) ==="
Write-Host "  MODE=$MODE  LOG=$LOG  DB=$DB  CACHE=$CACHE"

Invoke-CheckDeps
if (-not (Invoke-CheckPorts)) { exit 1 }

# Apply .env overrides for DB and CACHE
Write-Host ""
& python scripts/dev/apply_dev_env.py --db $DB --cache $CACHE
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Host ""

# Check infrastructure services (PostgreSQL, Redis) if needed
if (-not (Invoke-CheckInfra)) { exit 1 }

switch ($MODE) {
    "term" { Launch-Terminal }
    "bg"   { Launch-Background }
}
