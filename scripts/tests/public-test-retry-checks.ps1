$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
. (Join-Path $root 'scripts/public-test-retry.ps1')
$script:delays = @()
function Start-Sleep { param([int]$Seconds) $script:delays += $Seconds }
function Assert($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }

$script:calls = 0
$answer = Invoke-PublicTestRetry -Label 'Simulated DNS' -Operation {
    $script:calls++
    if ($script:calls -le 7) { throw [System.Net.WebException]::new('Simulated name resolution failure') }
    'connected'
}
Assert ($answer -eq 'connected' -and $script:calls -eq 8) 'DNS retry stopped before connection.'
Assert (($script:delays -join ',') -eq '2,4,8,16,30,30,30') 'Retry delay must be bounded.'

$script:calls = 0
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    $script:calls++
    if ($script:calls -le 2) { throw [System.Net.WebException]::new('Simulated temporary DNS failure') }
    if ($script:calls -eq 3) { return @{status='starting'} }
    return @{status='ok'}
}
$alive = [PSCustomObject]@{HasExited=$false}
$alive | Add-Member ScriptMethod Refresh { }
Wait-PublicTestHealth -Address 'https://fixture.invalid' -Process $alive
Assert ($script:calls -eq 4) 'Health must wait through DNS and backend initialization.'
$dead = [PSCustomObject]@{HasExited=$true}
$dead | Add-Member ScriptMethod Refresh { }
$caught = $false
try { Wait-PublicTestHealth -Address 'http://fixture.invalid' -Process $dead } catch [System.InvalidOperationException] { $caught = $true }
Assert ($caught -and $script:calls -eq 4) 'Exited backend must fail instead of retrying forever.'

$script:ghCalls = 0
function Fake-GitHub {
    $script:ghCalls++
    if ($script:ghCalls -lt 3) { $global:LASTEXITCODE=1; 'lookup api.github.com: no such host'; return }
    $global:LASTEXITCODE=0
}
Invoke-PublicTestGitHub -Executable 'Fake-GitHub' -Arguments @('auth','status') -Label 'GitHub fixture'
Assert ($script:ghCalls -eq 3) 'GitHub DNS failures were not retried.'
function Fake-InvalidLogin { $global:LASTEXITCODE=1; 'HTTP 401 invalid credentials SECRET-MUST-NOT-LEAK' }
$caught = $false
try { Invoke-PublicTestGitHub -Executable 'Fake-InvalidLogin' -Arguments @('auth','status') -Label 'GitHub fixture' } catch [System.InvalidOperationException] { $caught = $true }
Assert $caught 'Invalid credentials must fail immediately.'

# Extract only the tunnel factory; never execute the actual public starter.
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $root 'scripts/start-public-test.ps1'), [ref]$null, [ref]$parseErrors)
Assert (-not $parseErrors) 'Public starter contains invalid PowerShell.'
$factory = $ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'New-TestTunnel'}, $true)
Invoke-Expression $factory.Extent.Text
$runtime = Join-Path $root ('artifacts/public-test-retry-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runtime | Out-Null
$stateFile = Join-Path $runtime 'tunnel.json'
$cloudflared = 'fixture-only-never-executed.exe'
$script:tunnelCalls = 0
$script:kills = 0
function Start-Process {
    param($FilePath, $ArgumentList, $WindowStyle, $WorkingDirectory, $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)
    Assert ($WindowStyle -eq 'Hidden') 'Tunnel must start without visible windows.'
    $script:tunnelCalls++
    $fake = [PSCustomObject]@{Id=(1000+$script:tunnelCalls); HasExited=($script:tunnelCalls -eq 1); StartTime=[datetime]::UtcNow}
    $fake | Add-Member ScriptMethod Refresh { }
    $fake | Add-Member ScriptMethod Kill { $script:kills++; $this.HasExited=$true }
    if ($script:tunnelCalls -eq 3) {
        'https://fixture-success.trycloudflare.com' | Set-Content -LiteralPath $ArgumentList[-1].Trim('"')
    }
    return $fake
}
# Use unique log names even though simulated waits take no wall time.
$script:stamp = 0
function Get-Date { param($Format) $script:stamp++; return ('fixture-' + $script:stamp) }
$state = New-TestTunnel
Assert ($script:tunnelCalls -eq 3) 'Tunnel must recover after exit and missing URL.'
Assert ($script:kills -eq 1) 'Only the still-running failed tunnel attempt should be stopped.'
Assert ($state.url -eq 'https://fixture-success.trycloudflare.com' -and $state.tunnel_pid -eq 1003) 'Incorrect tunnel state.'
$saved = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
Assert ($saved.tunnel_pid -eq 1003) 'Only the successfully acquired tunnel should be persisted.'

# Simulate a tunnel dying after URL acquisition, then DNS failure on CORS.
$publicLoop = $ast.Find({param($node) $node -is [System.Management.Automation.Language.WhileStatementAst] -and $node.Extent.Text.Contains('Wait-PublicTestHealth -Address $state.url')}, $true)
Assert ($null -ne $publicLoop) 'Public connection recovery loop is missing.'
$script:processChecks=0; $script:replacements=0; $script:configures=0; $script:preflights=0
$python='Fake-Configure'
$frontend='https://fixture.invalid/'
function Fake-Configure { $script:configures++; $global:LASTEXITCODE=0 }
function New-TestTunnel { $script:replacements++; return $state }
function Get-Process {
    param($Id, $ErrorAction)
    $script:processChecks++
    $fake=[PSCustomObject]@{HasExited=($script:processChecks -eq 1); Path=$cloudflared; StartTime=[datetime]::Parse($state.started_utc)}
    $fake | Add-Member ScriptMethod Refresh { }
    return $fake
}
# Match the switch parameter of the real Invoke-WebRequest cmdlet.
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, $Uri, $Method, $Headers, $TimeoutSec)
    $script:preflights++
    if ($script:preflights -eq 1) { throw [System.Net.WebException]::new('Simulated CORS DNS failure') }
    return @{Headers=@{'Access-Control-Allow-Origin'='https://samdavid93.github.io'}}
}
Invoke-Expression $publicLoop.Extent.Text
Assert ($script:replacements -eq 1 -and $script:configures -eq 1) 'Lost tunnel was not replaced and reconfigured.'
Assert ($script:preflights -eq 2) 'CORS DNS failure must retry without replacing a healthy tunnel.'
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, $Uri, $Method, $Headers, $TimeoutSec)
    return @{Headers=@{'Access-Control-Allow-Origin'='https://wrong.invalid'}}
}
$caught=$false
try { Invoke-Expression $publicLoop.Extent.Text } catch { $caught=$_.Exception.Message -eq 'CORS-Pruefung fehlgeschlagen.' }
Assert ($caught -and $script:replacements -eq 1) 'Incorrect CORS must stop before publication.'
Write-Output 'PUBLIC_TEST_RETRY_CHECKS_PASSED'
