$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$desktop = [System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "TradeOS Console.lnk")
$startBat = Join-Path $PSScriptRoot "start.bat"

Write-Host "Creating shortcut..."
Write-Host "Target: $startBat"
Write-Host "Output: $desktop"

if (Test-Path $desktop) {
    Remove-Item $desktop -Force
    Write-Host "Removed old shortcut."
}

$sc = $shell.CreateShortcut($desktop)
$sc.TargetPath = $startBat
$sc.WorkingDirectory = $PSScriptRoot
$sc.Description = "TradeOS Console"
$sc.IconLocation = "python,0"
$sc.Save()

Write-Host "Saved."

# Verify
$sc2 = $shell.CreateShortcut($desktop)
Write-Host "Verified TargetPath: $($sc2.TargetPath)"
Write-Host "Verified WorkingDir: $($sc2.WorkingDirectory)"
Write-Host "Done."
