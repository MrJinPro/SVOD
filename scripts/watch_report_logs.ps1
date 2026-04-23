param(
  [ValidateSet('report', 'uvicorn', 'both')]
  [string]$Source = 'report',

  [string]$ReportId = '',

  [int]$Tail = 80,

  [switch]$Once
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backendDir = Join-Path $root 'backend'

function Get-Targets {
  param([string]$Kind)

  switch ($Kind) {
    'report' {
      return @(
        [pscustomobject]@{ Name = 'REPORT'; Path = (Join-Path $backendDir 'report_worker.log') }
      )
    }
    'uvicorn' {
      return @(
        [pscustomobject]@{ Name = 'UVICORN'; Path = (Join-Path $backendDir 'uvicorn.log') }
      )
    }
    'both' {
      return @(
        [pscustomobject]@{ Name = 'REPORT'; Path = (Join-Path $backendDir 'report_worker.log') },
        [pscustomobject]@{ Name = 'UVICORN'; Path = (Join-Path $backendDir 'uvicorn.log') }
      )
    }
  }
}

function Test-LineMatch {
  param(
    [string]$Line,
    [string]$Needle
  )

  if ([string]::IsNullOrWhiteSpace($Needle)) {
    return $true
  }

  return $Line -like "*$Needle*"
}

function Write-LogLine {
  param(
    [string]$SourceName,
    [string]$Line
  )

  $prefix = "[$SourceName]"
  $color = 'Gray'
  $lower = ($Line | Out-String).Trim().ToLowerInvariant()

  if ($lower.Contains('failed') -or $lower.Contains('traceback') -or $lower.Contains('error')) {
    $color = 'Red'
  } elseif ($lower.Contains('stored') -or $lower.Contains('finished')) {
    $color = 'Green'
  } elseif ($lower.Contains('queued') -or $lower.Contains('started')) {
    $color = 'Cyan'
  } elseif ($lower.Contains('pcn stage')) {
    $color = 'Yellow'
  }

  Write-Host "$prefix $Line" -ForegroundColor $color
}

function Show-Tail {
  param(
    [pscustomobject]$Target,
    [string]$Needle,
    [int]$Lines
  )

  if (-not (Test-Path $Target.Path)) {
    Write-Host "[$($Target.Name)] Файл пока не найден: $($Target.Path)" -ForegroundColor DarkYellow
    return
  }

  Get-Content -Path $Target.Path -Tail $Lines | ForEach-Object {
    if (Test-LineMatch -Line $_ -Needle $Needle) {
      Write-LogLine -SourceName $Target.Name -Line $_
    }
  }
}

function Read-AppendedLines {
  param(
    [pscustomobject]$Watcher,
    [string]$Needle
  )

  if (-not (Test-Path $Watcher.Path)) {
    return
  }

  $item = Get-Item $Watcher.Path
  if ($item.Length -lt $Watcher.Offset) {
    $Watcher.Offset = 0
  }
  if ($item.Length -eq $Watcher.Offset) {
    return
  }

  $stream = $null
  $reader = $null
  try {
    $stream = [System.IO.File]::Open($Watcher.Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $null = $stream.Seek($Watcher.Offset, [System.IO.SeekOrigin]::Begin)
    $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8, $true, 4096, $true)

    while (($line = $reader.ReadLine()) -ne $null) {
      if (Test-LineMatch -Line $line -Needle $Needle) {
        Write-LogLine -SourceName $Watcher.Name -Line $line
      }
    }

    $Watcher.Offset = $stream.Position
  }
  finally {
    if ($reader) { $reader.Dispose() }
    if ($stream) { $stream.Dispose() }
  }
}

$targets = Get-Targets -Kind $Source

Write-Host "Логи backend: $backendDir" -ForegroundColor DarkGray
if ($ReportId) {
  Write-Host "Фильтр report_id: $ReportId" -ForegroundColor DarkGray
}

foreach ($target in $targets) {
  Show-Tail -Target $target -Needle $ReportId -Lines $Tail
}

if ($Once) {
  exit 0
}

$watchers = @()
foreach ($target in $targets) {
  $offset = 0
  if (Test-Path $target.Path) {
    $offset = (Get-Item $target.Path).Length
  }

  $watchers += [pscustomobject]@{
    Name = $target.Name
    Path = $target.Path
    Offset = $offset
  }
}

Write-Host 'Слежение запущено. Остановить: Ctrl+C' -ForegroundColor Green

while ($true) {
  foreach ($watcher in $watchers) {
    Read-AppendedLines -Watcher $watcher -Needle $ReportId
  }
  [System.Threading.Thread]::Sleep(400)
}