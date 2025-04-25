<#.SYNOPSIS
Run recipes.#>
[CmdletBinding()]
Param([Parameter(ValueFromRemainingArguments)][string[]]$RemainingArgs)

#? Source common shell config
. ./scripts/pre.ps1
#? Set verbosity and CI-specific environment variables
$Verbose = $Env:CI -or ($DebugPreference -ne 'SilentlyContinue') -or ($VerbosePreference -ne 'SilentlyContinue')
$Env:DEV_VERBOSE = $Verbose ? 'true' : $null
$Env:JUST_VERBOSE = $Verbose ? '1' : $null
#? Set environment variables and uv version
Sync-DevEnv
Sync-Uv
#? Pass arguments to Just
if ($RemainingArgs) { ./uvx --from "rust-just@$Env:JUST_VERSION" just @RemainingArgs }
else { ./uvx --from "rust-just@$Env:JUST_VERSION" just list }
