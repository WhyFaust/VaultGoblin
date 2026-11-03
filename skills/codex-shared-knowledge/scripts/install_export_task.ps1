param(
    [string]$PythonPath = (Get-Command python.exe -ErrorAction Stop).Source
)

$ErrorActionPreference = 'Stop'
$pythonExecutable = (Resolve-Path -LiteralPath $PythonPath).ProviderPath
$pythonWindowless = Join-Path (Split-Path -Parent $pythonExecutable) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonWindowless -PathType Leaf)) {
    throw "Windowless Python not found: $pythonWindowless"
}
$exportScript = Join-Path $PSScriptRoot 'export_background.py'
if (-not (Test-Path -LiteralPath $exportScript -PathType Leaf)) {
    throw 'Update codex-shared-knowledge before installing its task.'
}
$codexDirectory = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$codexDirectory = (Resolve-Path -LiteralPath $codexDirectory).ProviderPath
if (-not (Test-Path -LiteralPath (Join-Path $codexDirectory 'shared-knowledge.json'))) {
    throw 'Install codex-shared-knowledge and configure the vault first.'
}

$action = New-ScheduledTaskAction -Execute $pythonWindowless `
    -Argument ('-B "' + $exportScript + '" "' + $codexDirectory + '" --wait')
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
