# 01 - Lancer l'application Streamlit (clone Opus / NVIDIA NIM)
#
# Usage :
#   Clic droit > "Exécuter avec PowerShell"
#   ou en terminal :  powershell -ExecutionPolicy Bypass -File scripts\01-lancer-app.ps1
#
# Le script se place a la racine du projet, verifie les dependances et la cle
# API, puis demarre Streamlit sur http://localhost:8501.

$ErrorActionPreference = "Stop"

# Racine du projet = dossier parent de /scripts
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
Write-Host "Dossier projet : $ProjectRoot" -ForegroundColor Cyan

# 1. Verifier Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "Python detecte : $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "Python introuvable. Installe Python 3.9+ puis reessaie." -ForegroundColor Red
    exit 1
}

# 2. Installer les dependances si Streamlit n'est pas present
$hasStreamlit = python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('streamlit') else 1)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installation des dependances (requirements.txt)..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt
} else {
    Write-Host "Dependances deja installees." -ForegroundColor Green
}

# 3. Verifier la cle API (variable d'env ou fichier .env)
$hasKey = $false
if ($env:NVIDIA_API_KEY) { $hasKey = $true }
if ((Test-Path ".env") -and (Select-String -Path ".env" -Pattern "^NVIDIA_API_KEY=nvapi-" -Quiet)) { $hasKey = $true }

if (-not $hasKey) {
    Write-Host "Aucune cle NVIDIA detectee." -ForegroundColor Yellow
    Write-Host "  -> Cree un fichier .env (voir .env.example) ou definis `$env:NVIDIA_API_KEY" -ForegroundColor Yellow
    Write-Host "  -> Tu peux aussi saisir la cle directement dans la barre laterale de l'app." -ForegroundColor Yellow
}

# 4. Lancer Streamlit
Write-Host "Demarrage de l'application sur http://localhost:8501 ..." -ForegroundColor Cyan
streamlit run app.py
