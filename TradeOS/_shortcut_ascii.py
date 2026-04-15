# -*- coding: utf-8 -*-
import subprocess, os

BAT = r"C:\TradeOS\TradeOS.bat"
PROJ = r"C:\Users\hutia\.qclaw\workspace\ai交易项目-TradeOS"
DESKTOP = os.path.join(os.environ["USERPROFILE"], "Desktop")
LNK = os.path.join(DESKTOP, "TradeOS Console.lnk")
PY = r"C:\Users\hutia\AppData\Local\Programs\Python\Python312\python.exe"

if os.path.exists(LNK):
    os.remove(LNK)

ps = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{LNK}')
$Shortcut.TargetPath = '{BAT}'
$Shortcut.WorkingDirectory = '{PROJ}'
$Shortcut.Description = 'TradeOS Console'
$Shortcut.IconLocation = '{PY},0'
$Shortcut.Save()
Write-Host 'TARGET: ' + $Shortcut.TargetPath
Write-Host 'WORKDIR: ' + $Shortcut.WorkingDirectory
Write-Host 'DESC: ' + $Shortcut.Description
Write-Host 'ICON: ' + $Shortcut.IconLocation
Write-Host 'OK'
"""

tmp = os.path.join(os.environ["TEMP"], "_mklnk.ps1")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(ps)

r = subprocess.run(
    ["powershell", "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", tmp],
    capture_output=True, encoding="utf-8", errors="replace", timeout=15
)
print(r.stdout.strip())
if r.returncode != 0:
    print("ERR:", r.stderr.strip()[:200])

# Verify
if os.path.exists(LNK):
    print(f"[OK] Shortcut: {os.path.getsize(LNK)} bytes")
else:
    print("[FAIL] Shortcut not created!")
