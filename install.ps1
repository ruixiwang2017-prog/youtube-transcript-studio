$ErrorActionPreference = 'Stop'
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Push-Location frontend
npm install
Pop-Location
Write-Host 'Installed. Run .\start.ps1'

