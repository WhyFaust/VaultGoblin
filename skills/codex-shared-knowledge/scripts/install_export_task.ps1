param(
    [string]$PythonPath,
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$codexDirectory = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$codexDirectory = (Resolve-Path -LiteralPath $codexDirectory).ProviderPath
$hash = [System.Security.Cryptography.SHA256]::Create()
try {
    $profileBytes = [System.Text.Encoding]::UTF8.GetBytes($codexDirectory.ToLowerInvariant())
    $profileHash = ([System.BitConverter]::ToString($hash.ComputeHash($profileBytes))).Replace('-', '').Substring(0, 12)
} finally {
    $hash.Dispose()
}
$taskName = 'Codex Shared Knowledge Export-' + $profileHash
$quotedHome = [regex]::Escape('"' + $codexDirectory + '"')
$legacy = Get-ScheduledTask -TaskName 'Codex Shared Knowledge Export' -ErrorAction SilentlyContinue
$ownedLegacy = $legacy -and @($legacy.Actions | Where-Object { $_.Arguments -match $quotedHome }).Count -gt 0
if ($Remove) {
    $current = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($current -and @($current.Actions | Where-Object { $_.Arguments -match $quotedHome }).Count -gt 0) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    if ($ownedLegacy) {
        Unregister-ScheduledTask -TaskName 'Codex Shared Knowledge Export' -Confirm:$false
    }
    return
}
if (-not (Test-Path -LiteralPath (Join-Path $codexDirectory 'shared-knowledge.json'))) {
    throw 'Install codex-shared-knowledge and configure the vault first.'
}
$exportScript = Join-Path $codexDirectory 'vaultgoblin\runtime\export_background.py'
if (-not (Test-Path -LiteralPath $exportScript -PathType Leaf)) {
    throw 'Run VaultGoblin setup or reinstall codex-shared-knowledge before installing its task.'
}
if (-not $PythonPath) {
    $PythonPath = (Get-Command python.exe -ErrorAction Stop).Source
}
$pythonExecutable = (Resolve-Path -LiteralPath $PythonPath).ProviderPath
$pythonWindowless = Join-Path (Split-Path -Parent $pythonExecutable) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonWindowless -PathType Leaf)) {
    throw "Windowless Python not found: $pythonWindowless"
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
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers `
    -Principal $principal -Settings $settings `
    -Description 'Export delayed Codex memory updates to the configured Obsidian vault every 5 minutes; no LLM.' `
    -Force | Select-Object TaskName, State
if ($ownedLegacy) {
    Unregister-ScheduledTask -TaskName 'Codex Shared Knowledge Export' -Confirm:$false
}
