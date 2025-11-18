param()
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $projectRoot

$distDir = Join-Path $projectRoot 'dist'
$scriptsDir = Join-Path $projectRoot 'scripts'

$installDir = Join-Path $env:LocalAppData 'Workflow'
$startMenuDir = Join-Path $env:AppData 'Microsoft\Windows\Start Menu\Programs\Workflow'
$userWorkDir = Join-Path $env:LocalAppData 'Workflow'

New-Item -ItemType Directory -Force -Path $installDir | Out-Null
New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null
New-Item -ItemType Directory -Force -Path $userWorkDir | Out-Null

Copy-Item (Join-Path $distDir 'workflow-web.exe') -Destination $installDir -Force
Copy-Item (Join-Path $distDir 'workflow-worker.exe') -Destination $installDir -Force
Copy-Item (Join-Path $scriptsDir 'start_all.bat') -Destination $installDir -Force

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut($path, $target, $workdir, $icon) {
  $s = $shell.CreateShortcut($path)
  $s.TargetPath = $target
  $s.WorkingDirectory = $workdir
  if ($icon) { $s.IconLocation = $icon }
  $s.Save()
}

New-Shortcut (Join-Path $startMenuDir 'Start Web.lnk') (Join-Path $installDir 'workflow-web.exe') $userWorkDir (Join-Path $installDir 'workflow-web.exe')
New-Shortcut (Join-Path $startMenuDir 'Start Worker.lnk') (Join-Path $installDir 'workflow-worker.exe') $userWorkDir (Join-Path $installDir 'workflow-worker.exe')
New-Shortcut (Join-Path $startMenuDir 'Start All.lnk') (Join-Path $installDir 'start_all.bat') $userWorkDir (Join-Path $installDir 'workflow-web.exe')
New-Shortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Workflow Start.lnk') (Join-Path $installDir 'start_all.bat') $userWorkDir (Join-Path $installDir 'workflow-web.exe')

Write-Host 'Installed to' $installDir
Write-Host 'Shortcuts in' $startMenuDir
