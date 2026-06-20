# 03 - Commits + push, en retirant tout co-auteur "Cursor"
#
# Usage :
#   powershell -ExecutionPolicy Bypass -File scripts\03-push.ps1 -Message "mon message"
#   powershell -ExecutionPolicy Bypass -File scripts\03-push.ps1 -Message "msg" -Branch branche2
#
# - Stage tous les changements, commit (si besoin) avec ton message.
# - Retire un eventuel trailer "Co-authored-by: Cursor ..." du dernier commit.
# - Pousse sur origin/<branche>.

param(
    [string]$Message = "Mise a jour",
    [string]$Branch = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not $Branch) {
    $Branch = (git branch --show-current).Trim()
}
Write-Host "Branche : $Branch" -ForegroundColor Cyan

# 1. Stage + commit s'il y a des changements
git add -A
$pending = git status --porcelain
if ($pending) {
    git commit -m $Message | Out-Null
    Write-Host "Commit cree." -ForegroundColor Green

    # 2. Securite : retirer un trailer Co-authored-by: Cursor s'il existe
    $body = git log -1 --pretty=%B
    if ($body -match "Co-authored-by:\s*Cursor") {
        $clean = (($body -split "`r?`n") | Where-Object { $_ -notmatch "Co-authored-by:\s*Cursor" }) -join "`n"
        $clean = $clean.TrimEnd()
        git commit --amend -m $clean | Out-Null
        Write-Host "Trailer 'Co-authored-by: Cursor' retire du commit." -ForegroundColor Yellow
    }
} else {
    Write-Host "Aucun changement a committer." -ForegroundColor Yellow
}

# 3. Push
git push -u origin $Branch
Write-Host "Pousse sur origin/$Branch" -ForegroundColor Green
