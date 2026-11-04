# Start ClosedTabs on this computer (Windows).
# Usage:  powershell -ExecutionPolicy Bypass -File .\start.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "deploy")

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"; exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "Docker isn't running. Open Docker Desktop, wait for 'Engine running', then try again."; exit 1 }

if ((Test-Path .env) -and (Select-String -Path .env -Pattern "NEXTAUTH_SECRET" -Quiet)) {
  $old = (Select-String -Path .env -Pattern '^OPENAI_API_KEY=(sk-ant-.*)$').Matches | ForEach-Object { $_.Groups[1].Value }
  Move-Item .env .env.karakeep-old -Force
  $lines = Get-Content .env.example
  if ($old) { $lines = $lines -replace '^ANTHROPIC_API_KEY=.*', "ANTHROPIC_API_KEY=$old" }
  $lines | Set-Content .env -Encoding utf8
  Write-Host "Replaced the old Karakeep settings (saved as deploy\.env.karakeep-old)."
}
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Write-Host "Starting ClosedTabs (the first time takes a few minutes)..."
docker compose up -d --build --remove-orphans

for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-WebRequest http://localhost:3000/health -UseBasicParsing -TimeoutSec 2 *> $null
        Write-Host "ClosedTabs is running at http://localhost:3000"
        Start-Process "http://localhost:3000"; exit 0 } catch { Start-Sleep 2 }
}
Write-Host "Still starting. Open http://localhost:3000 in a minute, or run: docker compose logs"
