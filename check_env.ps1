Get-ChildItem 'env:*' | Where-Object { $_.Name -match 'python' -or $_.Value -match 'python' } | Select-Object Name, Value
