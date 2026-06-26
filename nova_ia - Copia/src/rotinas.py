import os
import sys
import time
import threading
import datetime
import subprocess
from database import (
    listar_lembretes, marcar_lembrete_disparado,
    salvar_sessao_foco, stats_foco_hoje,
    listar_habitos, resumo_matinal,
    listar_tarefas
)

# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICAÇÕES WINDOWS
# ═══════════════════════════════════════════════════════════════════════════════

def notificar(titulo: str, mensagem: str):
    """Exibe uma notificação nativa do Windows."""
    try:
        from plyer import notification
        notification.notify(
            title=titulo,
            message=mensagem,
            app_name="NOVA",
            timeout=8
        )
    except Exception:
        # Fallback via PowerShell se plyer não estiver instalado
        script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        $notify = New-Object System.Windows.Forms.NotifyIcon
        $notify.Icon = [System.Drawing.SystemIcons]::Information
        $notify.Visible = $true
        $notify.ShowBalloonTip(8000, '{titulo}', '{mensagem}', [System.Windows.Forms.ToolTipIcon]::Info)
        Start-Sleep -Seconds 9
        $notify.Dispose()
        """
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )

# ═══════════════════════════════════════════════════════════════════════════════
# MONITOR DE LEMBRETES
# ═══════════════════════════════════════════════════════════════════════════════

class MonitorLembretes:
    """Roda em background e dispara notificações nos horários configurados."""

    def __init__(self):
        self._ativo = False
        self._thread = None

    def iniciar(self):
        if self._ativo:
            return
        self._ativo = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def parar(self):
        self._ativo = False

    def _loop(self):
        while self._ativo:
            try:
                agora = datetime.datetime.now()
                lembretes = listar_lembretes(apenas_ativos=True)
                for lembrete in lembretes:
                    if lembrete["disparado"]:
                        continue
                    try:
                        data_hora = datetime.datetime.fromisoformat(lembrete["data_hora"])
                    except Exception:
                        continue

                    if data_hora <= agora:
                        notificar(
                            f"⏰ {lembrete['titulo']}",
                            lembrete["descricao"] or "Lembrete da NOVA"
                        )
                        marcar_lembrete_disparado(lembrete["id"])

                        # Repetição
                        if lembrete["repetir"] == "diario":
                            nova_data = data_hora + datetime.timedelta(days=1)
                            from database import criar_lembrete, deletar_lembrete
                            criar_lembrete(
                                lembrete["titulo"],
                                nova_data.isoformat(),
                                lembrete["descricao"],
                                "diario"
                            )
                            deletar_lembrete(lembrete["id"])

                        elif lembrete["repetir"] == "semanal":
                            nova_data = data_hora + datetime.timedelta(weeks=1)
                            from database import criar_lembrete, deletar_lembrete
                            criar_lembrete(
                                lembrete["titulo"],
                                nova_data.isoformat(),
                                lembrete["descricao"],
                                "semanal"
                            )
                            deletar_lembrete(lembrete["id"])

            except Exception as e:
                pass

            time.sleep(30)  # verifica a cada 30 segundos


# ═══════════════════════════════════════════════════════════════════════════════
# TIMER POMODORO / MODO FOCO
# ═══════════════════════════════════════════════════════════════════════════════

class TimerFoco:
    """Gerencia sessões de foco com callback de atualização para a UI."""

    def __init__(self, on_tick=None, on_fim=None, on_pausa=None):
        self.on_tick   = on_tick    # callback(segundos_restantes, fase)
        self.on_fim    = on_fim     # callback(concluido: bool)
        self.on_pausa  = on_pausa   # callback()
        self._thread   = None
        self._pausado  = False
        self._parar    = False
        self.duracao   = 25
        self.pausa     = 5
        self.fase      = "foco"     # "foco" ou "pausa"

    def iniciar(self, duracao_min: int = 25, pausa_min: int = 5):
        self.duracao  = duracao_min
        self.pausa    = pausa_min
        self._pausado = False
        self._parar   = False
        self.fase     = "foco"
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def pausar_retomar(self):
        self._pausado = not self._pausado
        if self.on_pausa:
            self.on_pausa()

    def cancelar(self):
        self._parar = True
        salvar_sessao_foco(self.duracao, self.pausa, concluido=False)
        if self.on_fim:
            self.on_fim(False)

    def _loop(self):
        # Fase de foco
        segundos = self.duracao * 60
        while segundos > 0 and not self._parar:
            if not self._pausado:
                if self.on_tick:
                    self.on_tick(segundos, "foco")
                time.sleep(1)
                segundos -= 1
            else:
                time.sleep(0.5)

        if self._parar:
            return

        notificar("🎯 NOVA — Foco concluído!", f"Pausa de {self.pausa} min começando.")

        # Fase de pausa
        self.fase = "pausa"
        segundos = self.pausa * 60
        while segundos > 0 and not self._parar:
            if not self._pausado:
                if self.on_tick:
                    self.on_tick(segundos, "pausa")
                time.sleep(1)
                segundos -= 1
            else:
                time.sleep(0.5)

        if not self._parar:
            salvar_sessao_foco(self.duracao, self.pausa, concluido=True)
            notificar("✅ NOVA — Sessão completa!", "Pomodoro finalizado. Bom trabalho!")
            if self.on_fim:
                self.on_fim(True)


# ═══════════════════════════════════════════════════════════════════════════════
# RESUMO MATINAL
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_resumo_matinal() -> str:
    """Gera um resumo textual do dia para exibir na abertura."""
    dados = resumo_matinal()
    agora = datetime.datetime.now()
    hora  = agora.hour

    if hora < 12:
        saudacao = "Bom dia"
    elif hora < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"

    linhas = [f"☀️  {saudacao}! Aqui está seu resumo de hoje:\n"]

    if dados["tarefas_hoje"] > 0:
        linhas.append(f"📌 {dados['tarefas_hoje']} tarefa(s) com prazo para hoje")
    if dados["tarefas_pendentes"] > 0:
        linhas.append(f"📋 {dados['tarefas_pendentes']} tarefa(s) pendentes no total")
    if dados["lembretes_hoje"] > 0:
        linhas.append(f"⏰ {dados['lembretes_hoje']} lembrete(s) para hoje")
    if dados["total_habitos"] > 0:
        linhas.append(f"🎯 Hábitos: {dados['habitos_feitos']}/{dados['total_habitos']} feitos hoje")

    stats = stats_foco_hoje()
    if stats["sessoes"] > 0:
        linhas.append(f"🔥 {stats['sessoes']} sessão(ões) de foco hoje ({stats['minutos']} min)")

    if len(linhas) == 1:
        linhas.append("Nenhuma tarefa ou lembrete pendente. Dia livre, chefe! 😎")

    # Tarefas urgentes
    tarefas_hoje = listar_tarefas(status="pendente")
    urgentes = [
        t for t in tarefas_hoje
        if t["prazo"] and t["prazo"][:10] == agora.strftime("%Y-%m-%d")
    ]
    if urgentes:
        linhas.append("\n📍 Tarefas para hoje:")
        for t in urgentes[:5]:
            prioridade = {"alta": "🔴", "media": "🟡", "baixa": "🟢"}.get(t["prioridade"], "⚪")
            linhas.append(f"   {prioridade} {t['titulo']}")

    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════════════════════
# ABRIR PROGRAMAS / ARQUIVOS
# ═══════════════════════════════════════════════════════════════════════════════

def abrir_arquivo(caminho: str) -> bool:
    """Abre um arquivo ou programa pelo caminho."""
    try:
        os.startfile(caminho)
        return True
    except Exception as e:
        return False

def abrir_url(url: str) -> bool:
    """Abre uma URL no navegador padrão."""
    try:
        import webbrowser
        webbrowser.open(url)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# INSTÂNCIA GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

monitor_lembretes = MonitorLembretes()

def iniciar_rotinas():
    """Inicia todos os serviços em background. Chamar no main.py."""
    monitor_lembretes.iniciar()