$ErrorActionPreference = 'Stop'
if (-not (Test-Path .venv\Scripts\python.exe)) { throw 'Run .\install.ps1 first.' }
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

