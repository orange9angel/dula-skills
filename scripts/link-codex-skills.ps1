[CmdletBinding()]
param(
    [string]$SkillRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Destination,
    [switch]$StartupGuide
)
$ErrorActionPreference = 'Stop'
$skillSource = (Resolve-Path -LiteralPath $SkillRoot).Path
$codexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
if (-not $Destination) {
    # This installed client already discovers ~/.codex/skills. Preserve that
    # registry when present; fresh installations use the documented user path.
    $legacy = Join-Path $codexDir 'skills'
    $Destination = if (Test-Path -LiteralPath $legacy) { $legacy } else { Join-Path $env:USERPROFILE '.agents\skills' }
}
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$destinationRoot = (Resolve-Path -LiteralPath $Destination).Path
$skills = @(Get-ChildItem -LiteralPath $skillSource -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') })
$rows = @()
# Preflight every collision before creating any links. Never replace copies or
# retarget another checkout implicitly.
foreach ($skill in $skills) {
    $target = Join-Path $destinationRoot $skill.Name
    $existing = Get-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
    if ($existing) {
        if (-not $existing.LinkType -or @($existing.Target).Count -ne 1 -or
            [IO.Path]::GetFullPath($existing.Target[0]).TrimEnd('\') -ne $skill.FullName.TrimEnd('\')) {
            throw "Existing skill conflicts with this checkout: $target"
        }
    }
}
foreach ($skill in $skills) {
    $target = Join-Path $destinationRoot $skill.Name
    $created = -not (Test-Path -LiteralPath $target)
    if ($created) { New-Item -ItemType Junction -Path $target -Target $skill.FullName | Out-Null }
    $sourceHash = (Get-FileHash -LiteralPath (Join-Path $skill.FullName 'SKILL.md')).Hash
    $linkHash = (Get-FileHash -LiteralPath (Join-Path $target 'SKILL.md')).Hash
    if ($sourceHash -ne $linkHash) { throw "Linked content differs: $target" }
    $rows += [pscustomobject]@{ Name=$skill.Name; Created=$created; Path=$target; Source=$skill.FullName; Verified=$true }
}
if ($StartupGuide) {
    New-Item -ItemType Directory -Path $codexDir -Force | Out-Null
    $guide = Join-Path $codexDir 'AGENTS.md'
    $override = Join-Path $codexDir 'AGENTS.override.md'
    if ((Test-Path -LiteralPath $override) -and (Get-Item -LiteralPath $override).Length -gt 0) {
        throw 'AGENTS.override.md shadows the global guide; links are installed, but startup guidance needs reconciliation.'
    }
    $text = if (Test-Path -LiteralPath $guide) { [IO.File]::ReadAllText($guide) } else { '' }
    $begin = '<!-- dula-skills:start -->'; $end = '<!-- dula-skills:end -->'
    $block = @"
$begin
## Dula animation workspace

- For this user, animation production is a primary workflow. Use the checked-out
  Dula skills as the source of truth; do not infer production state from memory.
- Before Dula animation work, read ``$skillSource\AGENTS.md`` and the relevant
  ``SKILL.md`` files. Prefer an explicitly provided current checkout over this
  machine's saved path. After compaction, recover the active task from episode
  evidence and the relevant skills before modifying it.
- Audio routing requested by the user: ambience/Foley -> build-ambience-foley and
  Volcano Seed-Audio; dialogue -> build-character-voice and volc-voice-casting;
  score -> episode-scoring and suno-driver. Preserve accepted music unless a
  change is requested; do not silently choose a different generation backend.
- Skill directories in the user registry are links to the repository. Edit the
  repository original and commit lessons there. Load detailed references as
  needed; the discovery catalog does not mean every skill has been read.
$end
"@
    $pattern = '(?s)' + [regex]::Escape($begin) + '.*?' + [regex]::Escape($end)
    if ($text.Contains($begin) -xor $text.Contains($end)) { throw 'Incomplete Dula guide block; preserve file for manual reconciliation.' }
    $updated = if ($text.Contains($begin)) { [regex]::Replace($text,$pattern,[System.Text.RegularExpressions.MatchEvaluator]{ param($m) $block }) } else { $text.TrimEnd()+"`r`n`r`n"+$block+"`r`n" }
    if ($updated -ne $text) { [IO.File]::WriteAllText($guide,$updated.TrimStart(),[Text.UTF8Encoding]::new($false)) }
}
$rows | ConvertTo-Json -Depth 3
