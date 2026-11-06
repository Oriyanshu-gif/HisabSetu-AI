$files = Get-ChildItem 'C:\Users\priya\AppData\Local\Programs\Python' -Recurse -Filter 'python.exe'
foreach ($f in $files) {
    Write-Output "$($f.FullName)  $([math]::Round($f.Length/1MB,1))MB"
}
if ($files.Count -eq 0) { Write-Output "no python.exe found" }
