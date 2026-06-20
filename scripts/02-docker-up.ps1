# 02 - Demarrer la stack complete avec Docker (Streamlit + SearXNG)
#
# Usage :  powershell -ExecutionPolicy Bypass -File scripts\02-docker-up.ps1
#
# Le script verifie Docker, prepare .env et la cle secrete SearXNG, puis lance
# docker compose. App sur http://localhost:8501.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
Write-Host "Dossier projet : $ProjectRoot" -ForegroundColor Cyan

# 1. Verifier Docker
try {
    docker version --format '{{.Server.Version}}' | Out-Null
    Write-Host "Docker detecte." -ForegroundColor Green
} catch {
    Write-Host "Docker introuvable ou non demarre. Installe/lance Docker Desktop." -ForegroundColor Red
    exit 1
}

# 2. Verifier le fichier .env (obligatoire pour la cle NVIDIA)
if (-not (Test-Path ".env")) {
    Write-Host ".env absent : creation a partir de .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "  -> Edite .env et colle ta vraie cle NVIDIA (nvapi-...) avant de continuer." -ForegroundColor Yellow
    Read-Host "Appuie sur Entree une fois .env rempli"
}

# 3. Generer une cle secrete SearXNG si le placeholder est encore present
$settings = "searxng\settings.yml"
if ((Test-Path $settings) -and (Select-String -Path $settings -Pattern "CHANGE_MOI" -Quiet)) {
    $secret = python -c "import secrets; print(secrets.token_hex(32))"
    (Get-Content $settings -Raw) -replace 'CHANGE_MOI[^"]*', $secret | Set-Content $settings -NoNewline
    Write-Host "Cle secrete SearXNG generee." -ForegroundColor Green
}

# 4. Build + up
Write-Host "Construction et demarrage des conteneurs..." -ForegroundColor Cyan
docker compose up --build -d

Write-Host ""
Write-Host "Stack demarree :" -ForegroundColor Green
Write-Host "  App Streamlit : http://localhost:8501"
Write-Host "  SearXNG       : http://localhost:8888"
Write-Host ""
Write-Host "Logs  :  docker compose logs -f"
Write-Host "Arret :  docker compose down"
