param(
    [string]$PythonPath = (Get-Command python.exe -ErrorAction Stop).Source
)

$ErrorActionPreference = 'Stop'
$pythonExecutable = (Resolve-Path -LiteralPath $PythonPath).ProviderPath
$exportScript = Join-Path $PSScriptRoot 'shared_knowledge.py'
$codexDirectory = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$codexDirectory = (Resolve-Path -LiteralPath $codexDirectory).ProviderPath
if (-not (Test-Path -LiteralPath (Join-Path $codexDirectory 'shared-knowledge.json'))) {
    throw 'Install codex-shared-knowledge and configure the vault first.'
}

function Quote-TaskLiteral([string]$Value) { "'" + $Value.Replace("'", "''") + "'" }

$taskCommand = '$env:CODEX_HOME = ' + (Quote-TaskLiteral $codexDirectory) + '; & ' +
    (Quote-TaskLiteral $pythonExecutable) + ' -B ' + (Quote-TaskLiteral $exportScript) +
    ' export *> ' + (Quote-TaskLiteral (Join-Path $codexDirectory 'shared-knowledge-export.log')) +
    '; exit $LASTEXITCODE'
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -Command "' + $taskCommand + '"')
$userName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$triggers = @(
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)),
    (New-ScheduledTaskTrigger -AtLogOn -User $userName)
)
$principal = New-ScheduledTaskPrincipal -UserId $userName -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'Codex Shared Knowledge Export' -Action $action -Trigger $triggers `
    -Principal $principal -Settings $settings `
    -Description 'Export delayed Codex memory updates to the configured Obsidian vault every 5 minutes; no LLM.' `
    -Force | Select-Object TaskName, State
