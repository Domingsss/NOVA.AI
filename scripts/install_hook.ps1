# ═══════════════════════════════════════════════════════════════════════════════
# NOVA — install_hook.ps1
# Instala o hook post-commit no .git/hooks/ do repositório atual
# ═══════════════════════════════════════════════════════════════════════════════

Write-Host "🔧 Instalando hook post-commit para Obsidian..." -ForegroundColor Cyan

# Encontra a raiz do repo
 $repoRoot = git rev-parse --show-toplevel 2>$null
if (-not $repoRoot) {
    Write-Host "❌ Erro: você não está em um repositório git." -ForegroundColor Red
    Write-Host "   Rode este script de dentro da pasta do projeto NOVA."
    exit 1
}

 $hookDir = Join-Path $repoRoot ".git\hooks"
 $hookFile = Join-Path $hookDir "post-commit"

# Cria a pasta hooks se não existir
if (-not (Test-Path $hookDir)) {
    New-Item -ItemType Directory -Path $hookDir -Force | Out-Null
}

# Conteúdo do hook
 $hookContent = @'
#!/bin/sh
# Hook post-commit — gera relatório no Obsidian
# Instalado por scripts/install_hook.ps1

PYTHON=""
if command -v python >/dev/null 2>&1; then
    PYTHON=python
elif command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v py >/dev/null 2>&1; then
    PYTHON=py
else
    exit 0
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT" || exit 0

 $PYTHON scripts/commit_report.py 2>>scripts/commit_report_errors.log

exit 0
'@

# Escreve o hook
Set-Content -Path $hookFile -Value $hookContent -Encoding UTF8

Write-Host ""
Write-Host "✅ Hook instalado em: $hookFile" -ForegroundColor Green
Write-Host ""
Write-Host "📋 O que vai acontecer agora:" -ForegroundColor Cyan
Write-Host "   Toda vez que você fizer git commit, o script vai:"
Write-Host "   1. Analisar o diff do commit"
Write-Host "   2. Gerar um resumo com a IA (Groq)"
Write-Host "   3. Salvar um .md no seu vault Obsidian"
Write-Host ""
Write-Host "📁 Configuração:" -ForegroundColor Cyan
Write-Host "   Edite scripts/commit_config.json pra mudar:"
Write-Host "   - vault_path (caminho do vault)"
Write-Host "   - project_name (nome do projeto)"
Write-Host "   - default_tags (tags do Obsidian)"
Write-Host ""
Write-Host "🧪 Pra testar sem commitar:" -ForegroundColor Cyan
Write-Host "   python scripts/commit_report.py"
Write-Host ""
Write-Host "🗑️  Pra desinstalar:" -ForegroundColor Cyan
Write-Host "   Remove-Item .git\hooks\post-commit"