$ErrorActionPreference = "Stop"
Write-Host "Iniciando Panorama ENEM..." -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
  py -3.12 -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

$backend = Start-Process powershell -PassThru -ArgumentList "-NoExit", "-Command", "& '.\.venv\Scripts\Activate.ps1'; uvicorn app.main:app --app-dir backend --reload --port 8000"

Push-Location frontend
if (-not (Test-Path "node_modules")) { npm install }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; npm run dev"
Pop-Location

Write-Host "API: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Web: http://localhost:5173" -ForegroundColor Green
