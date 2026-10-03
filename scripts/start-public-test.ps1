$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$cloudflared = Join-Path $root 'artifacts\tools\cloudflared\cloudflared.exe'
$gh = Join-Path $root 'artifacts\tools\github-cli\gh.exe'
$runtime = Join-Path $root 'artifacts\public-test'
$stateFile = Join-Path $runtime 'tunnel.json'
$repository = 'SamDavid93/SDOYCC'
$frontend = 'https://samdavid93.github.io/SDOYCC/'
$env:PYTHONPATH = Join-Path $root 'backend'
$newTunnel = $null
$state = $null

function Wait-Health([string]$address) {
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            $response = Invoke-RestMethod -Uri ($address + '/api/health') -TimeoutSec 5
            if ($response.status -eq 'ok') { return }
        } catch { }
        Start-Sleep -Seconds 2
    }
    throw "Health-Pruefung fehlgeschlagen: $address"
}

try {
    foreach ($path in @($python, $cloudflared, $gh, (Join-Path $root '.env'))) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Voraussetzung fehlt: $path. Siehe docs/PUBLISHING.md." }
    }
    & $gh auth status *> $null
    if ($LASTEXITCODE -ne 0) { throw 'GitHub-Anmeldung fehlt. Zuerst gh auth login ausfuehren.' }
    & $python backend/scripts/release_check.py
    if ($LASTEXITCODE -ne 0) { throw 'Lokale Systempruefung fehlgeschlagen; Start abgebrochen.' }
    New-Item -ItemType Directory -Force -Path $runtime | Out-Null

    # Stop only the verified backend for THIS workspace before exposing a tunnel.
    $listeners = @(Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $listener"
        if (-not $process -or -not $process.CommandLine -or
            $process.CommandLine.IndexOf($python, [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
            $process.CommandLine -notmatch '-m uvicorn app\.main:app' -or
            $process.CommandLine -notmatch '--port 8002(?:\s|$)') {
            throw 'Port 8002 wird von einem anderen Prozess verwendet. Es wurde kein fremder Prozess beendet.'
        }
    }
    foreach ($listener in $listeners) { Stop-Process -Id $listener -ErrorAction Stop }
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not (Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8002 ist noch belegt.' }

    $state = $null
    if (Test-Path -LiteralPath $stateFile) {
        $candidate = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        $tunnel = Get-Process -Id $candidate.tunnel_pid -ErrorAction SilentlyContinue
        if ($tunnel -and $tunnel.Path -eq $cloudflared -and
            $tunnel.StartTime.ToUniversalTime().ToString('o') -eq $candidate.started_utc -and
            $candidate.url -match '^https://[a-z0-9-]+\.trycloudflare\.com$') { $state = $candidate }
    }
    if (-not $state) {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
        $stderr = Join-Path $runtime "tunnel-$stamp.log"
        $stdout = Join-Path $runtime "tunnel-$stamp-out.log"
        $errors = Join-Path $runtime "tunnel-$stamp-stderr.log"
        $tunnel = Start-Process -FilePath $cloudflared -ArgumentList @('tunnel', '--no-autoupdate', '--protocol', 'http2', '--url', 'http://127.0.0.1:8002', '--logfile', ('"' + $stderr + '"')) -WindowStyle Hidden -WorkingDirectory $root -RedirectStandardOutput $stdout -RedirectStandardError $errors -PassThru
        $newTunnel = $tunnel
        $url = $null
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            $tunnel.Refresh()
            if ($tunnel.HasExited) { throw "Tunnel konnte nicht starten. Log: $stderr" }
            if (Test-Path -LiteralPath $stderr) {
                $stream = [System.IO.File]::Open($stderr, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
                $reader = [System.IO.StreamReader]::new($stream)
                try { $logText = $reader.ReadToEnd() } finally { $reader.Dispose() }
                $match = [regex]::Match($logText, 'https://[a-z0-9-]+\.trycloudflare\.com')
                if ($match.Success) { $url = $match.Value; break }
            }
            Start-Sleep -Seconds 1
        }
        if (-not $url) {
            Stop-Process -Id $tunnel.Id -ErrorAction SilentlyContinue
            throw "Keine Tunnel-Adresse erhalten. Log: $stderr"
        }
        $state = [PSCustomObject]@{ tunnel_pid = $tunnel.Id; started_utc = $tunnel.StartTime.ToUniversalTime().ToString('o'); url = $url }
        $state | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
    }
    Write-Host "Test-Tunnel: $($state.url)"
    & $python backend/scripts/configure_public.py --frontend-url $frontend --backend-url $state.url --apply
    if ($LASTEXITCODE -ne 0) { throw 'Oeffentliche Konfiguration fehlgeschlagen.' }
    & $python backend/scripts/release_check.py --public
    if ($LASTEXITCODE -ne 0) { throw 'Produktionspruefung fehlgeschlagen; Backend bleibt gestoppt.' }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8002', '--no-access-log') -WindowStyle Hidden -WorkingDirectory $root -RedirectStandardOutput (Join-Path $runtime "backend-$stamp-out.log") -RedirectStandardError (Join-Path $runtime "backend-$stamp.log") | Out-Null
    Wait-Health 'http://127.0.0.1:8002'
    Wait-Health $state.url
    $preflight = Invoke-WebRequest -UseBasicParsing -Uri ($state.url + '/api/auth/login') -Method Options -Headers @{ Origin = 'https://samdavid93.github.io'; 'Access-Control-Request-Method' = 'POST'; 'Access-Control-Request-Headers' = 'content-type' } -TimeoutSec 15
    if ($preflight.Headers['Access-Control-Allow-Origin'] -ne 'https://samdavid93.github.io') { throw 'CORS-Pruefung fehlgeschlagen.' }

    & $gh variable set VITE_API_BASE_URL --repo $repository --body ($state.url + '/api')
    if ($LASTEXITCODE -ne 0) { throw 'GitHub-Variable konnte nicht gesetzt werden.' }
    & $gh workflow run deploy-pages.yml --repo $repository --ref main
    if ($LASTEXITCODE -ne 0) { throw 'Pages-Workflow konnte nicht gestartet werden.' }
    Write-Host "Backend und Tunnel laufen im Hintergrund. Pages-Build gestartet: https://github.com/$repository/actions"
    Write-Host "Website nach erfolgreichem Build: $frontend"
    Write-Host 'PC eingeschaltet lassen. stop-public-test.bat beendet nur den Tunnel. Nach einem PC-Neustart diese BAT erneut ausfuehren.'
    exit 0
} catch {
    if ($newTunnel -and -not $state) { $newTunnel.Refresh(); if (-not $newTunnel.HasExited) { $newTunnel.Kill() } }
    Write-Host ('Start nicht abgeschlossen: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Der Pages-Stand wurde nur bei erfolgreicher Backend-Pruefung aktualisiert. Logs: artifacts/public-test/'
    exit 1
}
