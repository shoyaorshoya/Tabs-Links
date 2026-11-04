# One-step local start for Windows (PowerShell).  Usage:  .\start.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "deploy")

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"; exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "Docker is not running. Open Docker Desktop, wait for it to start, then re-run."; exit 1 }

if (-not (Test-Path .env)) {
  Write-Host "Creating deploy\.env with fresh random secrets..."
  function Rand { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ }) }
  (Get-Content .env.example) `
    -replace '^NEXTAUTH_SECRET=.*', "NEXTAUTH_SECRET=$(Rand)" `
    -replace '^MEILI_MASTER_KEY=.*', "MEILI_MASTER_KEY=$(Rand)" |
    Set-Content .env -Encoding utf8
  Write-Host "Done. Add your Claude API key later in deploy\.env (OPENAI_API_KEY=...) to switch on AI labels."
}

Write-Host "Starting Karakeep (first run downloads ~1-2 GB, give it a few minutes)..."
docker compose up -d

for ($i = 0; $i -lt 90; $i++) {
  try { Invoke-WebRequest http://localhost:3000 -UseBasicParsing -TimeoutSec 2 *> $null
        Write-Host "Running at http://localhost:3000. Sign up there to create your account."
        Start-Process "http://localhost:3000"; exit 0 } catch { Start-Sleep 2 }
}
Write-Host "Still starting. Check http://localhost:3000 in a minute, or run: docker compose logs web"
