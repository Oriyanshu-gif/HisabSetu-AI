Set oSh = CreateObject("WScript.Shell")
oSh.Run "powershell -NoProfile -ExecutionPolicy Bypass -Command ""& {
  \$ErrorActionPreference='Continue'
  \$timeout = (Get-Date).(Get-Date).AddSeconds(120)
  \$scriptPath = \"nul\"
  Set oSh = CreateObject("WScript.Shell")
  \$py = \"C:\Program Files\Python314\python.exe\"
  \$code = @'
import sys
from pathlib import Path
root = Path('C:\Users\priya\AppData\Local\Programs\Python\Python314\Lib\site-packages\freebuff-desktop\local-projects\d13b6a98-36c1-45e2-bd64-4f78b22143bd\threads\3409accc5912919b005dd5a26438c26438c251778e47bffb063754c1c0fa825da78f6e\.venv\Lib\site-packages')
'@
}"""
