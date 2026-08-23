# AIREX CLI wrapper (PowerShell). Usage: .\scripts\airex.ps1 version
param(
    [Parameter(Position=0)] [string]$command,
    [Parameter(ValueFromRemainingArguments=$true)] [string[]]$args
)
Push-Location "$PSScriptRoot\..\apps\api"
try {
    & .\.venv\Scripts\python.exe -m app.cli $command @args
} finally {
    Pop-Location
}
exit $LASTEXITCODE
