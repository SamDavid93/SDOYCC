$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$stateFile = Join-Path $root 'artifacts\public-test\tunnel.json'
if (-not (Test-Path -LiteralPath $stateFile)) { Write-Host 'Kein gespeicherter Test-Tunnel.'; exit 0 }
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
$tunnel = Get-Process -Id $state.tunnel_pid -ErrorAction SilentlyContinue
if (-not $tunnel) { Write-Host 'Test-Tunnel ist bereits beendet.'; exit 0 }
if ($tunnel.Path -ne (Join-Path $root 'artifacts\tools\cloudflared\cloudflared.exe') -or
    $tunnel.StartTime.ToUniversalTime().ToString('o') -ne $state.started_utc) {
    Write-Host 'Prozess stimmt nicht mit dem gespeicherten Tunnel ueberein; nichts beendet.'
    exit 1
}
Stop-Process -Id $tunnel.Id
Write-Host 'Oeffentlicher Testzugang beendet. Das lokale Backend und Streamer.bot bleiben unveraendert.'
