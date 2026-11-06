$ErrorActionPreference = 'Stop'
$installer = 'C:\Users\priya\.config\freebuff-desktop\local-projects\d13b6a98-36c1-45e2-bd64-4f78b22143bd\threads\3409accc5912919b005dd5a26438c251778e47bffb063754c1c0fa825da78f6e\python-3.14.2-amd64.exe'
$outPath = 'C:\Users\priya\.config\freebuff-desktop\local-projects\d13b6a98-36c1-45e2-bd64-4f78b22143bd\threads\3409accc5912919b005dd5a26438c251778e47bffb063754c1c0fa825da78f6e\install_out.log'
$errPath = 'C:\Users\priya\.config\freebuff-desktop\local-projects\d13b6a98-36c1-45e2-bd64-4f78b22143bd\threads\3409accc5912919b005dd5a26438c251778e47bffb063754c1c0fa825da78f6e\install_err.log'
$exe = Resolve-Path $installer -ErrorAction Stop
Write-Output "installer=$exe"
if (-not (Test-Path $exe)) { throw "installer missing: $exe" }
$proc = Start-Process -FilePath $exe -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_test_tools=0' -Wait -NoNewWindow -PassThru -RedirectStandardOutput $outPath -RedirectStandardError $errPath
Write-Output "exit=$($proc.ExitCode)"
Write-Output '--- stdout (first 200 lines) ---'
Get-Content $outPath -ErrorAction SilentlyContinue | Select-Object -First 200
Write-Output '--- stderr (first 200 lines) ---'
Get-Content $errPath -ErrorAction SilentlyContinue | Select-Object -First 200
$target = 'C:\Users\priya\AppData\Local\Programs\Python\Python314\python.exe'
Write-Output 'target_exit_and_version='
if (Test-Path $target) {
    & $target --version 2>&1
} else {
    Write-Output 'NOT_INSTALLED'
}
