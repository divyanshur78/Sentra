# Sentra AI - Start both backend and frontend
# Run from project root: .\start.ps1

Write-Host "Starting Sentra AI..." -ForegroundColor Cyan
Write-Host ""

# Check if .env exists, create from example if not
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

# Start backend in a new PowerShell window
Write-Host "Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$PWD';
    Write-Host 'Sentra Backend starting...' -ForegroundColor Cyan;
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"

# Wait for backend to start
Write-Host "Waiting for backend to boot (5s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Start frontend in a new PowerShell window
Write-Host "Starting Vite frontend on http://localhost:5173 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$PWD\Sentrafrnt';
    Write-Host 'Sentra Frontend starting...' -ForegroundColor Cyan;
    npm run dev
"

Write-Host ""
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  Sentra AI is starting up!" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Demo credentials:" -ForegroundColor Yellow
Write-Host "  Employee: emp-001 or emp-002 (any password)" -ForegroundColor White
Write-Host "  Manager:  mgr-001 or mgr-002 (any password)" -ForegroundColor White
Write-Host "  Owner:    O1001 / Own@123" -ForegroundColor White
Write-Host ""
Write-Host "Opening frontend in browser..." -ForegroundColor Green
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"

