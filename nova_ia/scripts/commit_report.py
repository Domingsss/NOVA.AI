#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# NOVA — commit_report.py (v2.0 - Premium Obsidian formatting)
# Gera relatório de commit no Obsidian após cada git commit
# ═══════════════════════════════════════════════════════════════════════════════

import os
import re
import sys
import json
import subprocess
import datetime
from pathlib import Path

def load_config():
    script_dir = Path(__file__).parent
    config_path = script_dir / "commit_config.json"
    if not config_path.exists():
        return {
            "vault_path": "", "commits_folder": "Commits", "project_name": "Projeto",
            "api_key_paths": ["src/APICHV.json", "APICHV.json"],
            "groq_model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "max_diff_chars": 8000, "default_tags": ["commit", "desenvolvimento"],
            "include_diff": True, "max_diff_in_markdown": 3000,
        }
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_git(args):
    try:
        result = subprocess.run(["git"] + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return result.stdout.strip()
    except Exception:
        return ""

def get_commit_info():
    raw = run_git(["log", "-1", "--pretty=format:%H|%s|%an|%ai"])
    if not raw: return None
    parts = raw.split("|", 3)
    if len(parts) < 4: return None
    return {"hash": parts[0], "message": parts[1], "author": parts[2], "date_raw": parts[3]}

def get_commit_stats():
    raw = run_git(["show", "--numstat", "--format=", "HEAD"])
    if not raw: return []
    stats = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line: continue
        parts = line.split("\t")
        if len(parts) >= 3:
            ins, dels, fname = parts[0], parts[1], parts[2]
            try:
                ins = int(ins) if ins != "-" else 0
                dels = int(dels) if dels != "-" else 0
            except ValueError:
                ins, dels = 0, 0
            stats.append({"file": fname, "insertions": ins, "deletions": dels})
    return stats

def get_commit_diff(max_chars=8000):
    raw = run_git(["show", "--format=", "--no-color", "HEAD"])
    if not raw: return ""
    if len(raw) > max_chars:
        return raw[:max_chars] + f"\n\n... (diff truncado — {len(raw)} chars total)"
    return raw

def get_api_key(config):
    repo_root = Path(__file__).parent.parent
    for rel_path in config.get("api_key_paths", []):
        key_file = repo_root / rel_path
        if key_file.exists():
            try:
                with open(key_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    key = data.get("api_key", "")
                    if key: return key
            except Exception:
                continue
    return ""

def generate_summary(diff, commit_msg, config):
    api_key = get_api_key(config)
    if not api_key:
        return "API key não encontrada — resumo IA indisponível. Configure em src/APICHV.json"
    try:
        from groq import Groq
    except ImportError:
        return "pacote groq não instalado — rode: pip install groq"
    
    model = config.get("groq_model", "meta-llama/llama-4-scout-17b-16e-instruct")
    system = """Você é um assistente que analisa commits de código e gera resumos claros e concisos em português brasileiro.
Gere um resumo que explique:
1. O QUE foi feito (em linguagem simples)
2. POR QUE foi feito (se dá pra inferir)
3. Pontos importantes (arquivos principais, mudanças de comportamento)
Formato:
- 2 a 4 parágrafos curtos
- Sem markdown (será inserido em bloco já formatado)
- Seja direto, sem "Este commit..." — fique direto na ação
- Em português brasileiro informal"""
    
    user_msg = f"Mensagem do commit: {commit_msg}\n\nDiff:\n```\n{diff}\n```"
    
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model, max_tokens=500,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"erro ao gerar resumo: {e}"

def slugify(text, max_len=50):
    text = text.lower().strip()
    text = re.sub(r"[áàâãä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[íìîï]", "i", text)
    text = re.sub(r"[óòôõö]", "o", text)
    text = re.sub(r"[úùûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:max_len].strip("-")

def build_markdown(commit_info, stats, summary, diff, config):
    try:
        dt = datetime.datetime.fromisoformat(commit_info["date_raw"].replace("Z", "+00:00"))
        dt = dt.astimezone()
        data_str = dt.strftime("%Y-%m-%d")
        hora_str = dt.strftime("%H:%M")
        hora_file = dt.strftime("%H%M")
    except Exception:
        data_str = datetime.datetime.now().strftime("%Y-%m-%d")
        hora_str = datetime.datetime.now().strftime("%H:%M")
        hora_file = datetime.datetime.now().strftime("%H%M")

    hash_short = commit_info["hash"][:7]
    total_ins = sum(s["insertions"] for s in stats)
    total_del = sum(s["deletions"] for s in stats)
    total_files = len(stats)

    tags = config.get("default_tags", ["commit"])
    tags_yaml = ", ".join(f'"{t}"' for t in tags)

    # Tabela de arquivos formatada
    tabela = "| Arquivo | Mudanças |\n|---|---|\n"
    for s in stats[:20]:
        changes = []
        if s["insertions"] > 0: changes.append(f"<span style='color:#10b981'>+{s['insertions']}</span>")
        if s["deletions"] > 0: changes.append(f"<span style='color:#e11d48'>-{s['deletions']}</span>")
        tabela += f"| `{s['file']}` | {' · '.join(changes) if changes else '0'} |\n"
    if len(stats) > 20:
        tabela += f"| _...e mais {len(stats) - 20} arquivo(s)_ | |\n"

    # Diff colapsável
    diff_section = ""
    if config.get("include_diff", True) and diff:
        max_diff = config.get("max_diff_in_markdown", 3000)
        diff_trunc = diff[:max_diff]
        if len(diff) > max_diff:
            diff_trunc += f"\n... (truncado — {len(diff)} chars total)"
        # Callout colapsável do Obsidian
        diff_section = f"""
> [!info]- 📝 Diff Completo (clique para expandir)
> ```diff
> {diff_trunc.replace('\n', '\n> ')}
> ```
"""

    md = f"""---
data: {data_str}
hora: "{hora_str}"
commit: {hash_short}
commit_full: {commit_info['hash']}
autor: "{commit_info['author']}"
projeto: "{config.get('project_name', 'Projeto')}"
arquivos: {total_files}
insercoes: {total_ins}
delecoes: {total_del}
tags: [{tags_yaml}]
---

# {commit_info['message']}

> [!summary] Estatísticas do Commit
> 📁 **{total_files}** arquivos alterados · 🟢 **+{total_ins}** inserções · 🔴 **-{total_del}** deleções
> 👤 **Autor:** {commit_info['author']} · 🕒 **Data:** {data_str} às {hora_str} · 🔗 **Hash:** `{hash_short}`

> [!example]- 📁 Arquivos Modificados
> {tabela.replace('\n', '\n> ')}

> [!ai]+ 🤖 Resumo Inteligente
> {summary.replace('\n', '\n> ')}
{diff_section}
---

> [!quote] Informações do Sistema
> Gerado automaticamente por `commit_report.py` no projeto **{config.get('project_name', 'Projeto')}** em {datetime.datetime.now().strftime('%d/%m/%Y às %H:%M')}.
"""

    return md, data_str, hora_file

def save_report(markdown, data_str, hora_file, slug, config):
    vault = config.get("vault_path", "")
    if not vault:
        print("ERRO: vault_path não configurado em commit_config.json")
        return False
    commits_folder = config.get("commits_folder", "Commits")
    base = Path(vault) / commits_folder
    base.mkdir(parents=True, exist_ok=True)
    filename = f"{data_str}-{hora_file}-{slug}.md"
    filename = re.sub(r'[<>:"/\\|?*]', "", filename)
    filepath = base / filename
    i = 1
    while filepath.exists():
        filepath = base / f"{data_str}-{hora_file}-{slug}-{i}.md"
        i += 1
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)
        return True
    except Exception as e:
        print(f"ERRO ao salvar: {e}")
        return False

def main():
    config = load_config()
    commit_info = get_commit_info()
    if not commit_info:
        print("ERRO: não foi possível ler o último commit")
        return
    stats = get_commit_stats()
    diff = get_commit_diff(config.get("max_diff_chars", 8000))
    summary = generate_summary(diff, commit_info["message"], config)
    markdown, data_str, hora_file = build_markdown(commit_info, stats, summary, diff, config)
    slug = slugify(commit_info["message"])
    ok = save_report(markdown, data_str, hora_file, slug, config)
    if ok:
        print(f"✅ Relatório salvo no Obsidian: {data_str}-{hora_file}-{slug}.md")
    else:
        print("❌ Falha ao salvar relatório")

if __name__ == "__main__":
    main()