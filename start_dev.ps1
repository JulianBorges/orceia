# Script para iniciar Frontend e Backend do OrceIA V3
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Iniciando OrceIA V3 - Dev Server      " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$rootDir = Get-Location

# Inicia o Backend em uma nova janela
Write-Host "-> Subindo Backend (FastAPI) na porta 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; uvicorn main:app --reload --port 8000" -WindowStyle Normal

# Aguarda 2 segundos para o backend respirar
Start-Sleep -Seconds 2

# Inicia o Frontend em uma nova janela
Write-Host "-> Subindo Frontend (Next.js) na porta 3000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev" -WindowStyle Normal

Write-Host ""
Write-Host "✅ Servidores iniciados com sucesso!" -ForegroundColor Green
Write-Host "As janelas do terminal abriram separadamente para você acompanhar os logs." -ForegroundColor White
Write-Host "Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "Backend:  http://localhost:8000" -ForegroundColor White
