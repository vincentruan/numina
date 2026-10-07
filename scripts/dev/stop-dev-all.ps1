# scripts/dev/stop-dev-all.ps1 — Stop all Numina dev servers (Windows)
#
# Stops processes listening on ports 8000/8001/8002/5173/5174.
# Identifies processes by checking command line for expected keywords.

$ErrorActionPreference = 'Continue'

$Ports = @(8000, 8001, 8002, 5173, 5174)
$PortExpect = @{
    8000 = "uvicorn"
    8001 = "uvicorn"
    8002 = "uvicorn"
    5173 = "vite"
    5174 = "vite"
}
$PortVenvPath = @{
    8000 = "numina/server/.venv"
    8001 = "numina/server/.venv"
    8002 = "numina/server/.venv"
    5173 = ""
    5174 = ""
}

Write-Host "Stopping all dev servers (ports 8000/8001/8002/5173/5174)..."

# ── 1. Kill by PID file (background mode) ───────────────────────

$RootDir = (Resolve-Path ".").Path
$PidFile = Join-Path $RootDir ".numina" "dev-pids.json"
if (Test-Path $PidFile) {
    try {
        $pidData = Get-Content $PidFile -Raw | ConvertFrom-Json
        if ($pidData.pids) {
            Write-Host "  Found PID file, stopping background processes..."
            foreach ($procId in $pidData.pids) {
                try {
                    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                    if ($proc) {
                        # Kill the process and its children
                        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $procId" -ErrorAction SilentlyContinue
                        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                        foreach ($child in $children) {
                            Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
                        }
                        Write-Host "  Port $($pidData.services | Where-Object { $true } | Select-Object -First 1): stopped PID $procId"
                    }
                } catch {}
            }
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        }
    } catch {
        # PID file corrupt, ignore and fall through to port scanning
    }
}

# ── 2. Port-based cleanup (covers tmux/term/bg modes) ───────────

$found = $false
$bad = $false
$stale = $false

foreach ($port in $Ports) {
    $expect = $PortExpect[$port]
    $venvPath = $PortVenvPath[$port]

    # Find process listening on this port
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conn) { continue }

    $procId = $conn[0].OwningProcess
    if (-not $procId) { continue }

    try {
        $proc = Get-Process -Id $procId -ErrorAction Stop
        $cmdline = ""
        try {
            $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction Stop
            $cmdline = $cim.CommandLine
        } catch {}

        # Check if this is our expected process
        $matched = $false
        if ($cmdline -and $expect -and $cmdline -match [regex]::Escape($expect)) {
            $matched = $true
        }
        if (-not $matched -and $venvPath -and $cmdline -and $cmdline -match [regex]::Escape($venvPath)) {
            $matched = $true
        }
        # Also match by process name as fallback
        if (-not $matched -and $proc.ProcessName -match "uvicorn|python|node|pwsh") {
            $matched = $true
        }

        if (-not $matched) {
            Write-Host "  ! Port $port cannot be identified (PID $procId):" -ForegroundColor Yellow
            Write-Host "    $cmdline" -ForegroundColor Yellow
            Write-Host "    Expected: $expect (numina dev server)" -ForegroundColor Yellow
            $bad = $true
            continue
        }

        $found = $true

        # Kill process tree
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $procId" -ErrorAction SilentlyContinue
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        foreach ($child in $children) {
            Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Write-Host "  Port $port`: stopped process tree (PID $procId)"
    } catch {
        Write-Host "  Port $port`: process $procId already gone"
    }
}

Start-Sleep -Milliseconds 500

# ── 3. Verify cleanup ───────────────────────────────────────────

foreach ($port in $Ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $procId = $conn[0].OwningProcess
        try {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            # Also kill children
            Get-CimInstance Win32_Process -Filter "ParentProcessId = $procId" -ErrorAction SilentlyContinue |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Write-Host "  Port $port`: force-cleaned residual process (PID $procId)"
            $stale = $true
        } catch {}
    }
}

if ($bad) {
    Write-Host "! Some ports could not be automatically identified" -ForegroundColor Yellow
    exit 1
} elseif ($stale) {
    Write-Host "! Some residual processes were force-cleaned" -ForegroundColor Yellow
    exit 1
} elseif ($found) {
    Write-Host "All dev servers stopped." -ForegroundColor Green
} else {
    Write-Host "No running dev servers found." -ForegroundColor Green
}
