param(
  [Parameter(Mandatory = $true)]
  [string]$RepoRoot,

  [string]$ServiceName = 'SVOD-Backend'
)

$ErrorActionPreference = 'Stop'

$hooksDir = Join-Path $RepoRoot '.git\hooks'
if (-not (Test-Path $hooksDir)) { throw "Not a git repo (hooks dir missing): $hooksDir" }

$templateDir = Join-Path $RepoRoot 'scripts\server\windows\git-hooks'
if (-not (Test-Path $templateDir)) { throw "Template dir missing: $templateDir" }

$targets = @('post-merge', 'post-checkout', 'post-rewrite')
foreach ($name in $targets) {
  $src = Join-Path $templateDir $name
  $dst = Join-Path $hooksDir $name

  $content = (Get-Content -LiteralPath $src -Raw) -replace '\{\{SERVICE_NAME\}\}', $ServiceName
  Set-Content -LiteralPath $dst -Value $content -Encoding ASCII
}

Write-Host "Installed git hooks into .git/hooks (service: $ServiceName)" -ForegroundColor Green
Write-Host "Now every git pull/checkout that changes HEAD will try to restart the service." -ForegroundColor Gray
