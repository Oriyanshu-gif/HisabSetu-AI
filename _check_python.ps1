Get-ChildItem 'C:\Users\priya\AppData\Local\Programs\Python' -Recurse -Filter 'python.exe' | Select-Object FullName, Length | Format-Table -AutoSize
