# Shared by the public starter and its isolated tests. No processes start here.
function Invoke-PublicTestRetry {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][scriptblock]$Operation,
        [scriptblock]$RetryWhen = { param($failure) $true }
    )
    $delay = 2
    $attempt = 0
    while ($true) {
        $attempt++
        try { return (& $Operation) }
        catch {
            if ($_.Exception -is [System.Management.Automation.PipelineStoppedException] -or $_.Exception -is [System.OperationCanceledException]) { throw }
            if (-not (& $RetryWhen $_)) { throw }
            Write-Host "$Label noch nicht erreichbar (Versuch $attempt). Neuer Versuch in $delay Sekunden. Abbrechen mit Strg+C."
            Start-Sleep -Seconds $delay
            $delay = [Math]::Min(30, $delay * 2)
        }
    }
}

function Wait-PublicTestHealth {
    param([Parameter(Mandatory)][string]$Address, [object]$Process)
    Invoke-PublicTestRetry -Label "Verbindung zu $Address" -Operation {
        if ($Process) {
            $Process.Refresh()
            if ($Process.HasExited) {
                throw [System.InvalidOperationException]::new("Prozess wurde beendet: $Address")
            }
        }
        $response = Invoke-RestMethod -Uri ($Address + '/api/health') -TimeoutSec 5
        if ($response.status -ne 'ok') { throw [System.Net.WebException]::new('Health noch nicht bereit.') }
    } -RetryWhen { param($failure) $failure.Exception.GetType() -ne [System.InvalidOperationException] }
}

function Invoke-PublicTestGitHub {
    param([string]$Executable, [string[]]$Arguments, [string]$Label)
    Invoke-PublicTestRetry -Label $Label -Operation {
        # Native stderr is captured for classification, never printed with tokens.
        $ErrorActionPreference = 'Continue'
        $output = & $Executable @Arguments 2>&1
        $succeeded = $?
        $code = $LASTEXITCODE
        if (-not $succeeded -or $code -ne 0) {
            $network = ($output | Out-String) -match '(?i)could not resolve|no such host|dial tcp|lookup |timeout|timed out|connection.*(refused|reset|closed)|network is unreachable|net/http|\bEOF\b|HTTP 5\d\d|HTTP 429|temporary failure|TLS handshake'
            if ($network) { throw [System.Net.WebException]::new('GitHub-Netzwerkverbindung unterbrochen.') }
            throw [System.InvalidOperationException]::new("$Label fehlgeschlagen. GitHub-Anmeldung und Berechtigungen pruefen.")
        }
    } -RetryWhen { param($failure) $failure.Exception -is [System.Net.WebException] }
}
