# Push GoldAI_Project to https://github.com/golfyyy/My_MiniProject
# Run in PowerShell:  cd C:\Users\USER\GoldAI_Project
#                     .\push_to_github.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Gold AI -> GitHub (golfyyy/My_MiniProject) ===" -ForegroundColor Cyan

# Safety: refuse if secrets would be committed
$forbidden = @(".env", "config\settings.json")
foreach ($f in $forbidden) {
    if (Test-Path $f) {
        $tracked = git ls-files --error-unmatch $f 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "ERROR: $f is tracked by git. Fix .gitignore before pushing." -ForegroundColor Red
            exit 1
        }
    }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: git is not installed. Install from https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path .git)) {
    git init
    Write-Host "Initialized git repository." -ForegroundColor Green
}

git add .
Write-Host "`n--- Staged files (verify no .env or settings.json) ---" -ForegroundColor Yellow
git status

$stagedSecrets = git diff --cached --name-only | Where-Object {
    $_ -eq ".env" -or $_ -eq "config/settings.json" -or $_ -match "\.env$|settings\.json$"
}
if ($stagedSecrets) {
    Write-Host "ERROR: Refusing to commit sensitive files:" -ForegroundColor Red
    $stagedSecrets | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    git reset HEAD
    exit 1
}

$hasCommits = git rev-parse HEAD 2>$null
if (-not $hasCommits) {
    git commit -m "Initial commit: Gold AI signal-only bot (XAUUSD)"
    Write-Host "Created initial commit." -ForegroundColor Green
} else {
    $dirty = git status --porcelain
    if ($dirty) {
        git commit -m "Update Gold AI project"
        Write-Host "Committed changes." -ForegroundColor Green
    } else {
        Write-Host "Nothing new to commit." -ForegroundColor Gray
    }
}

git branch -M main

$remoteUrl = "https://github.com/golfyyy/My_MiniProject.git"
$existing = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    git remote add origin $remoteUrl
    Write-Host "Added remote origin." -ForegroundColor Green
} elseif ($existing -ne $remoteUrl) {
    git remote set-url origin $remoteUrl
    Write-Host "Updated remote origin URL." -ForegroundColor Green
}

Write-Host "`nPushing to $remoteUrl ..." -ForegroundColor Cyan
Write-Host "If prompted: use GitHub username 'golfyyy' and a Personal Access Token as password." -ForegroundColor Gray
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nDone! Repo: https://github.com/golfyyy/My_MiniProject" -ForegroundColor Green
} else {
    Write-Host "`nPush failed. Common fixes:" -ForegroundColor Red
    Write-Host "  1. Create empty repo at https://github.com/new named My_MiniProject (no README)"
    Write-Host "  2. Log in: gh auth login   OR use PAT when git asks for password"
    Write-Host "  3. Run this script again"
    exit 1
}
