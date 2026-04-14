# -*- coding: utf-8 -*-
import subprocess, os

lnk = os.path.join(os.environ["USERPROFILE"], "Desktop", "TradeOS Console.lnk")
ps = f"""
$sc = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}')
Write-Host ('TARGET: ' + $sc.TargetPath)
Write-Host ('WORKDIR: ' + $sc.WorkingDirectory)
Write-Host ('DESC: ' + $sc.Description)
Write-Host ('EXISTS: ' + (Test-Path '{lnk}'))
"""

r = subprocess.run(
    ["powershell", "-ExecutionPolicy", "Bypass", "-NoProfile", "-Command", "-"],
    input=ps.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
)
print(r.stdout.decode("utf-8", errors="replace"))
if r.returncode != 0:
    print("ERR:", r.stderr.decode("utf-8", errors="replace")[:200])
