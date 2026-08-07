import threading
import datetime
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, ttk
from colors import BG, SURFACE, SURFACE2, PURPLE, TEAL, TEXT, MUTED, WHITE
from helpers import salvar_key, carregar_key, chamar_gemini
from database import (
    criar_sessao, listar_sessoes, renomear_sessao, deletar_sessao,
    salvar_mensagem, carregar_historico, limpar_historico,
    criar_tarefa, listar_tarefas, concluir_tarefa, deletar_tarefa,
    listar_projetos, criar_projeto,
    criar_lembrete, listar_lembretes, deletar_lembrete,
    criar_habito, listar_habitos, registrar_habito, deletar_habito,
    stats_foco_hoje
)
from rotinas import TimerFoco, gerar_resumo_matinal, iniciar_rotinas

# ═══════════════════════════════════════════════════════════════════════════════
# ESTILOS GLOBAIS
# ═══════════════════════════════════════════════════════════════════════════════

FONT_TITLE  = ("Courier", 18, "bold")
FONT_LABEL  = ("Courier", 11, "bold")
FONT_BODY   = ("Courier", 11)
FONT_SMALL  = ("Courier", 9)
FONT_MONO   = ("Courier", 12)

GRAD_START  = "#7c6fff"
GRAD_END    = "#1de9b6"
DANGER      = "#ff5f5f"
WARNING     = "#ffb347"
SUCCESS     = "#1de9b6"

PRIORIDADE_COR = {"alta": "#ff5f5f", "media": "#ffb347", "baixa": "#1de9b6"}

# ═══════════════════════════════════════════════════════════════════════════════
# WIDGET HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def btn(parent, text, cmd, bg=PURPLE, fg=WHITE, font=FONT_SMALL, **kw):
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     font=font, relief="flat", cursor="hand2",
                     activebackground=bg, activeforeground=fg, **kw)

def label(parent, text, fg=TEXT, font=FONT_BODY, **kw):
    return tk.Label(parent, text=text, fg=fg, font=font,
                    bg=kw.pop("bg", SURFACE), **kw)

def entry(parent, **kw):
    return tk.Entry(parent, bg=SURFACE2, fg=TEXT, font=FONT_BODY,
                    insertbackground=WHITE, relief="flat",
                    highlightthickness=1, highlightcolor=PURPLE,
                    highlightbackground=SURFACE2, **kw)

def sep(parent):
    tk.Frame(parent, bg=SURFACE2, height=1).pack(fill="x", pady=4)

# ═══════════════════════════════════════════════════════════════════════════════
# PAINEL: CHAT
# ═══════════════════════════════════════════════════════════════════════════════

class PainelChat(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.historico = []
        self.sessao_id = None
        self._build()

    def _build(self):
        self.chat = scrolledtext.ScrolledText(
            self, bg=BG, fg=TEXT, font=FONT_MONO,
            relief="flat", wrap="word", state="disabled",
            padx=16, pady=12, cursor="arrow",
            selectbackground=PURPLE, insertbackground=WHITE
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_config("nova_name", foreground=TEAL,   font=("Courier", 12, "bold"))
        self.chat.tag_config("nova_text", foreground=TEXT,   font=FONT_MONO)
        self.chat.tag_config("user_name", foreground=PURPLE, font=("Courier", 12, "bold"))
        self.chat.tag_config("user_text", foreground=WHITE,  font=FONT_MONO)
        self.chat.tag_config("muted",     foreground=MUTED,  font=FONT_SMALL)

        footer = tk.Frame(self, bg=SURFACE, pady=10, padx=12)
        footer.pack(fill="x")

        self.entrada = tk.Text(footer, height=2, bg=SURFACE2, fg=TEXT,
                               font=FONT_MONO, relief="flat",
                               insertbackground=WHITE, wrap="word",
                               padx=10, pady=8)
        self.entrada.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entrada.bind("<Return>",       self._enviar_enter)
        self.entrada.bind("<Shift-Return>", lambda e: None)

        self.btn_send = btn(footer, "▲", self._enviar, padx=14, pady=10,
                            font=("Courier", 13, "bold"))
        self.btn_send.pack(side="right")

    def carregar_sessao(self, sessao_id: int):
        self.sessao_id = sessao_id
        self.historico = carregar_historico(sessao_id)
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        for msg in self.historico:
            if msg["role"] == "user":
                self._append("Você", msg["content"], "user_name", "user_text")
            else:
                self._append("NOVA", msg["content"], "nova_name", "nova_text")

    def nova_sessao(self):
        sid = criar_sessao()
        self.sessao_id = sid
        self.historico = []
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self._append("NOVA",
            "Nova conversa iniciada. O que você precisa, chefe?",
            "nova_name", "nova_text")
        return sid

    def _append(self, nome, texto, tag_nome, tag_texto):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"\n{nome}\n", tag_nome)
        self.chat.insert("end", f"{texto}\n", tag_texto)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _append_muted(self, texto):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"\n{texto}\n", "muted")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _enviar_enter(self, event):
        self._enviar()
        return "break"

    def _enviar(self):
        texto = self.entrada.get("1.0", "end").strip()
        if not texto or not self.app.api_key:
            if not self.app.api_key:
                self.app.pedir_key()
            return
        if self.sessao_id is None:
            self.nova_sessao()

        self.entrada.delete("1.0", "end")
        self._append("Você", texto, "user_name", "user_text")
        self.historico.append({"role": "user", "content": texto})
        salvar_mensagem(self.sessao_id, "user", texto)
        self.app.sidebar.atualizar_sessoes()

        self.btn_send.configure(state="disabled", text="...")
        self._append_muted("NOVA está pensando...")
        threading.Thread(target=self._responder, daemon=True).start()

    def _responder(self):
        resposta = chamar_gemini(self.app.api_key, self.historico)
        self.historico.append({"role": "assistant", "content": resposta})
        salvar_mensagem(self.sessao_id, "assistant", resposta)
        self.after(0, self._mostrar_resposta, resposta)

    def _mostrar_resposta(self, resposta):
        self.chat.configure(state="normal")
        idx = self.chat.search("NOVA está pensando...", "1.0", "end")
        if idx:
            line = int(idx.split(".")[0])
            self.chat.delete(f"{line-1}.0", f"{line+1}.0")
        self.chat.configure(state="disabled")
        self._append("NOVA", resposta, "nova_name", "nova_text")
        self.btn_send.configure(state="normal", text="▲")
        self.app.sidebar.atualizar_sessoes()

# ═══════════════════════════════════════════════════════════════════════════════
# PAINEL: TAREFAS
# ═══════════════════════════════════════════════════════════════════════════════

class PainelTarefas(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        # Topo
        topo = tk.Frame(self, bg=SURFACE, pady=10, padx=14)
        topo.pack(fill="x")
        label(topo, "✅  Tarefas", fg=PURPLE, font=FONT_TITLE, bg=SURFACE).pack(side="left")
        btn(topo, "+ Nova tarefa", self._nova_tarefa).pack(side="right")

        tk.Frame(self, bg=SURFACE2, height=1).pack(fill="x")

        # Lista
        self.frame_lista = tk.Frame(self, bg=BG)
        self.frame_lista.pack(fill="both", expand=True, padx=14, pady=10)
        self.atualizar()

    def atualizar(self):
        for w in self.frame_lista.winfo_children():
            w.destroy()

        tarefas = listar_tarefas()
        pendentes = [t for t in tarefas if t["status"] == "pendente"]
        concluidas = [t for t in tarefas if t["status"] == "concluida"]

        if not tarefas:
            label(self.frame_lista,
                  "Nenhuma tarefa ainda. Que tal criar uma?",
                  fg=MUTED, bg=BG).pack(pady=40)
            return

        if pendentes:
            label(self.frame_lista, "PENDENTES", fg=MUTED,
                  font=FONT_SMALL, bg=BG).pack(anchor="w", pady=(4, 2))
            for t in pendentes:
                self._card_tarefa(t)

        if concluidas:
            label(self.frame_lista, "CONCLUÍDAS", fg=MUTED,
                  font=FONT_SMALL, bg=BG).pack(anchor="w", pady=(12, 2))
            for t in concluidas[:5]:
                self._card_tarefa(t, concluida=True)

    def _card_tarefa(self, t, concluida=False):
        cor_prio = PRIORIDADE_COR.get(t["prioridade"], MUTED)
        card = tk.Frame(self.frame_lista, bg=SURFACE, pady=8, padx=12)
        card.pack(fill="x", pady=3)

        esq = tk.Frame(card, bg=SURFACE)
        esq.pack(side="left", fill="x", expand=True)

        linha1 = tk.Frame(esq, bg=SURFACE)
        linha1.pack(fill="x")

        tk.Frame(linha1, bg=cor_prio, width=4).pack(side="left", fill="y", padx=(0, 8))

        titulo = t["titulo"]
        if concluida:
            titulo = f"✓ {titulo}"
        label(linha1, titulo, fg=MUTED if concluida else TEXT,
              font=FONT_LABEL, bg=SURFACE).pack(side="left")

        if t["projeto"]:
            label(linha1, f"  [{t['projeto']}]", fg=t["cor_projeto"] or MUTED,
                  font=FONT_SMALL, bg=SURFACE).pack(side="left")

        if t["prazo"]:
            prazo = t["prazo"][:10]
            label(esq, f"📅 {prazo}", fg=MUTED, font=FONT_SMALL, bg=SURFACE).pack(anchor="w")

        dir = tk.Frame(card, bg=SURFACE)
        dir.pack(side="right")

        if not concluida:
            btn(dir, "✓", lambda tid=t["id"]: self._concluir(tid),
                bg=SUCCESS, padx=6, pady=2).pack(side="left", padx=2)
        btn(dir, "✕", lambda tid=t["id"]: self._deletar(tid),
            bg=DANGER, padx=6, pady=2).pack(side="left", padx=2)

    def _concluir(self, tid):
        concluir_tarefa(tid)
        self.atualizar()

    def _deletar(self, tid):
        deletar_tarefa(tid)
        self.atualizar()

    def _nova_tarefa(self):
        win = tk.Toplevel(self)
        win.title("Nova Tarefa")
        win.configure(bg=SURFACE)
        win.geometry("420x320")
        win.grab_set()

        tk.Label(win, text="Nova Tarefa", font=FONT_TITLE,
                 bg=SURFACE, fg=PURPLE).pack(pady=(16, 8))

        campos = tk.Frame(win, bg=SURFACE, padx=20)
        campos.pack(fill="x")

        label(campos, "Título", bg=SURFACE).pack(anchor="w", pady=(8, 2))
        e_titulo = entry(campos)
        e_titulo.pack(fill="x")

        label(campos, "Descrição", bg=SURFACE).pack(anchor="w", pady=(8, 2))
        e_desc = entry(campos)
        e_desc.pack(fill="x")

        label(campos, "Prazo (AAAA-MM-DD)", bg=SURFACE).pack(anchor="w", pady=(8, 2))
        e_prazo = entry(campos)
        e_prazo.pack(fill="x")

        label(campos, "Prioridade", bg=SURFACE).pack(anchor="w", pady=(8, 2))
        prio_var = tk.StringVar(value="media")
        frame_prio = tk.Frame(campos, bg=SURFACE)
        frame_prio.pack(fill="x")
        for val, txt in [("alta", "🔴 Alta"), ("media", "🟡 Média"), ("baixa", "🟢 Baixa")]:
            tk.Radiobutton(frame_prio, text=txt, variable=prio_var, value=val,
                           bg=SURFACE, fg=TEXT, selectcolor=SURFACE2,
                           activebackground=SURFACE, font=FONT_SMALL).pack(side="left", padx=4)

        def salvar():
            titulo = e_titulo.get().strip()
            if not titulo:
                return
            prazo = e_prazo.get().strip() or None
            criar_tarefa(titulo, e_desc.get().strip(), prioridade=prio_var.get(), prazo=prazo)
            self.atualizar()
            win.destroy()

        btn(win, "Criar tarefa", salvar, padx=20, pady=8).pack(pady=16)

# ═══════════════════════════════════════════════════════════════════════════════
# PAINEL: LEMBRETES
# ═══════════════════════════════════════════════════════════════════════════════

class PainelLembretes(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        topo = tk.Frame(self, bg=SURFACE, pady=10, padx=14)
        topo.pack(fill="x")
        label(topo, "⏰  Lembretes", fg=PURPLE, font=FONT_TITLE, bg=SURFACE).pack(side="left")
        btn(topo, "+ Novo lembrete", self._novo_lembrete).pack(side="right")

        tk.Frame(self, bg=SURFACE2, height=1).pack(fill="x")

        self.frame_lista = tk.Frame(self, bg=BG)
        self.frame_lista.pack(fill="both", expand=True, padx=14, pady=10)
        self.atualizar()

    def atualizar(self):
        for w in self.frame_lista.winfo_children():
            w.destroy()

        lembretes = listar_lembretes()
        if not lembretes:
            label(self.frame_lista, "Nenhum lembrete ativo.",
                  fg=MUTED, bg=BG).pack(pady=40)
            return

        for l in lembretes:
            card = tk.Frame(self.frame_lista, bg=SURFACE, pady=8, padx=12)
            card.pack(fill="x", pady=3)

            esq = tk.Frame(card, bg=SURFACE)
            esq.pack(side="left", fill="x", expand=True)

            label(esq, f"⏰ {l['titulo']}", fg=TEXT,
                  font=FONT_LABEL, bg=SURFACE).pack(anchor="w")

            data_fmt = l["data_hora"][:16].replace("T", " ")
            rep = f"  •  repete {l['repetir']}" if l["repetir"] != "nunca" else ""
            label(esq, f"{data_fmt}{rep}", fg=MUTED,
                  font=FONT_SMALL, bg=SURFACE).pack(anchor="w")

            btn(card, "✕", lambda lid=l["id"]: self._deletar(lid),
                bg=DANGER, padx=6, pady=2).pack(side="right")

    def _deletar(self, lid):
        deletar_lembrete(lid)
        self.atualizar()

    def _novo_lembrete(self):
        win = tk.Toplevel(self)
        win.title("Novo Lembrete")
        win.configure(bg=SURFACE)
        win.geometry("400x300")
        win.grab_set()

        tk.Label(win, text="Novo Lembrete", font=FONT_TITLE,
                 bg=SURFACE, fg=PURPLE).pack(pady=(16, 8))

        campos = tk.Frame(win, bg=SURFACE, padx=20)
        campos.pack(fill="x")

        label(campos, "Título", bg=SURFACE).pack(anchor="w", pady=(8, 2))
        e_titulo = entry(campos)
        e_titulo.pack(fill="x")

        label(campos, "Data e hora (AAAA-MM-DD HH:MM)", bg=SURFACE).pack(anchor="w", pady=(8, 2))
        e_data = entry(campos)
        e_data.insert(0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        e_data.pack(fill="x")

        label(campos, "Repetir", bg=SURFACE).pack(anchor="w", pady=(8, 2))
        rep_var = tk.StringVar(value="nunca")
        frame_rep = tk.Frame(campos, bg=SURFACE)
        frame_rep.pack(fill="x")
        for val, txt in [("nunca", "Nunca"), ("diario", "Diário"), ("semanal", "Semanal")]:
            tk.Radiobutton(frame_rep, text=txt, variable=rep_var, value=val,
                           bg=SURFACE, fg=TEXT, selectcolor=SURFACE2,
                           activebackground=SURFACE, font=FONT_SMALL).pack(side="left", padx=4)

        def salvar():
            titulo = e_titulo.get().strip()
            data   = e_data.get().strip().replace(" ", "T")
            if not titulo or not data:
                return
            criar_lembrete(titulo, data, repetir=rep_var.get())
            self.atualizar()
            win.destroy()

        btn(win, "Criar lembrete", salvar, padx=20, pady=8).pack(pady=16)

# ═══════════════════════════════════════════════════════════════════════════════
# PAINEL: FOCO
# ═══════════════════════════════════════════════════════════════════════════════

class PainelFoco(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.timer = TimerFoco(
            on_tick=self._on_tick,
            on_fim=self._on_fim,
            on_pausa=self._on_pausa
        )
        self.rodando = False
        self._build()

    def _build(self):
        topo = tk.Frame(self, bg=SURFACE, pady=10, padx=14)
        topo.pack(fill="x")
        label(topo, "🎯  Modo Foco", fg=PURPLE, font=FONT_TITLE, bg=SURFACE).pack(side="left")

        tk.Frame(self, bg=SURFACE2, height=1).pack(fill="x")

        centro = tk.Frame(self, bg=BG)
        centro.pack(expand=True)

        # Timer display
        self.lbl_fase = label(centro, "FOCO", fg=TEAL,
                               font=("Courier", 14, "bold"), bg=BG)
        self.lbl_fase.pack(pady=(40, 8))

        self.lbl_timer = label(centro, "25:00", fg=WHITE,
                                font=("Courier", 64, "bold"), bg=BG)
        self.lbl_timer.pack()

        # Stats
        stats = stats_foco_hoje()
        self.lbl_stats = label(centro,
            f"Hoje: {stats['sessoes']} sessão(ões) • {stats['minutos']} minutos",
            fg=MUTED, font=FONT_SMALL, bg=BG)
        self.lbl_stats.pack(pady=8)

        # Configuração
        conf = tk.Frame(centro, bg=BG)
        conf.pack(pady=12)

        label(conf, "Foco (min):", bg=BG, fg=MUTED).pack(side="left", padx=4)
        self.e_foco = entry(conf, width=4)
        self.e_foco.insert(0, "25")
        self.e_foco.pack(side="left", padx=4)

        label(conf, "Pausa (min):", bg=BG, fg=MUTED).pack(side="left", padx=8)
        self.e_pausa = entry(conf, width=4)
        self.e_pausa.insert(0, "5")
        self.e_pausa.pack(side="left", padx=4)

        # Botões
        botoes = tk.Frame(centro, bg=BG)
        botoes.pack(pady=16)

        self.btn_iniciar = btn(botoes, "▶  Iniciar", self._iniciar,
                               padx=20, pady=10, font=FONT_LABEL)
        self.btn_iniciar.pack(side="left", padx=6)

        self.btn_pausar = btn(botoes, "⏸  Pausar", self._pausar,
                              bg=SURFACE2, padx=20, pady=10, font=FONT_LABEL)
        self.btn_pausar.pack(side="left", padx=6)
        self.btn_pausar.configure(state="disabled")

        self.btn_cancelar = btn(botoes, "✕  Cancelar", self._cancelar,
                                bg=DANGER, padx=20, pady=10, font=FONT_LABEL)
        self.btn_cancelar.pack(side="left", padx=6)
        self.btn_cancelar.configure(state="disabled")

    def _iniciar(self):
        try:
            foco  = int(self.e_foco.get())
            pausa = int(self.e_pausa.get())
        except ValueError:
            return
        self.rodando = True
        self.btn_iniciar.configure(state="disabled")
        self.btn_pausar.configure(state="normal")
        self.btn_cancelar.configure(state="normal")
        self.timer.iniciar(foco, pausa)

    def _pausar(self):
        self.timer.pausar_retomar()

    def _cancelar(self):
        self.timer.cancelar()

    def _on_tick(self, segundos, fase):
        mins = segundos // 60
        secs = segundos % 60
        self.after(0, self._atualizar_display, f"{mins:02d}:{secs:02d}", fase)

    def _atualizar_display(self, tempo, fase):
        self.lbl_timer.configure(text=tempo)
        if fase == "foco":
            self.lbl_fase.configure(text="🎯 FOCO", fg=TEAL)
        else:
            self.lbl_fase.configure(text="☕ PAUSA", fg=WARNING)

    def _on_fim(self, concluido):
        self.after(0, self._reset_ui, concluido)

    def _reset_ui(self, concluido):
        self.rodando = False
        self.btn_iniciar.configure(state="normal")
        self.btn_pausar.configure(state="disabled")
        self.btn_cancelar.configure(state="disabled")
        self.lbl_timer.configure(text="25:00")
        self.lbl_fase.configure(text="FOCO", fg=TEAL)
        stats = stats_foco_hoje()
        self.lbl_stats.configure(
            text=f"Hoje: {stats['sessoes']} sessão(ões) • {stats['minutos']} minutos")

    def _on_pausa(self):
        estado = "⏸  Pausar" if not self.timer._pausado else "▶  Retomar"
        self.after(0, self.btn_pausar.configure, {"text": estado})

# ═══════════════════════════════════════════════════════════════════════════════
# PAINEL: HÁBITOS
# ═══════════════════════════════════════════════════════════════════════════════

class PainelHabitos(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        topo = tk.Frame(self, bg=SURFACE, pady=10, padx=14)
        topo.pack(fill="x")
        label(topo, "📊  Hábitos", fg=PURPLE, font=FONT_TITLE, bg=SURFACE).pack(side="left")
        btn(topo, "+ Novo hábito", self._novo_habito).pack(side="right")

        tk.Frame(self, bg=SURFACE2, height=1).pack(fill="x")

        self.frame_lista = tk.Frame(self, bg=BG)
        self.frame_lista.pack(fill="both", expand=True, padx=14, pady=10)
        self.atualizar()

    def atualizar(self):
        for w in self.frame_lista.winfo_children():
            w.destroy()

        habitos = listar_habitos()
        if not habitos:
            label(self.frame_lista, "Nenhum hábito ainda. Crie um!",
                  fg=MUTED, bg=BG).pack(pady=40)
            return

        hoje = datetime.date.today().isoformat()
        label(self.frame_lista, f"Hoje — {hoje}", fg=MUTED,
              font=FONT_SMALL, bg=BG).pack(anchor="w", pady=(4, 8))

        for h in habitos:
            card = tk.Frame(self.frame_lista, bg=SURFACE, pady=10, padx=14)
            card.pack(fill="x", pady=3)

            feito = h["feito_hoje"]
            cor_check = SUCCESS if feito else SURFACE2
            check_txt = "✓" if feito else "○"

            esq = tk.Frame(card, bg=SURFACE)
            esq.pack(side="left", fill="x", expand=True)

            tk.Label(esq, text=f"{h['icone']}  {h['nome']}",
                     fg=TEXT if not feito else MUTED,
                     font=FONT_LABEL, bg=SURFACE).pack(anchor="w")
            tk.Label(esq, text=f"🔥 {h['streak']} dias",
                     fg=h["cor"], font=FONT_SMALL, bg=SURFACE).pack(anchor="w")

            dir = tk.Frame(card, bg=SURFACE)
            dir.pack(side="right")

            btn(dir, check_txt, lambda hid=h["id"]: self._toggle(hid),
                bg=cor_check, padx=10, pady=4).pack(side="left", padx=4)
            btn(dir, "✕", lambda hid=h["id"]: self._deletar(hid),
                bg=DANGER, padx=6, pady=4).pack(side="left")

    def _toggle(self, hid):
        registrar_habito(hid)
        self.atualizar()

    def _deletar(self, hid):
        deletar_habito(hid)
        self.atualizar()

    def _novo_habito(self):
        win = tk.Toplevel(self)
        win.title("Novo Hábito")
        win.configure(bg=SURFACE)
        win.geometry("360x220")
        win.grab_set()

        tk.Label(win, text="Novo Hábito", font=FONT_TITLE,
                 bg=SURFACE, fg=PURPLE).pack(pady=(16, 8))

        campos = tk.Frame(win, bg=SURFACE, padx=20)
        campos.pack(fill="x")

        label(campos, "Nome", bg=SURFACE).pack(anchor="w", pady=(8, 2))
        e_nome = entry(campos)
        e_nome.pack(fill="x")

        linha = tk.Frame(campos, bg=SURFACE)
        linha.pack(fill="x", pady=(8, 0))

        label(linha, "Ícone:", bg=SURFACE).pack(side="left")
        e_icone = entry(linha, width=4)
        e_icone.insert(0, "⭐")
        e_icone.pack(side="left", padx=6)

        def salvar():
            nome = e_nome.get().strip()
            if not nome:
                return
            criar_habito(nome, e_icone.get().strip() or "⭐")
            self.atualizar()
            win.destroy()

        btn(win, "Criar hábito", salvar, padx=20, pady=8).pack(pady=16)

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR DE SESSÕES
# ═══════════════════════════════════════════════════════════════════════════════

class Sidebar(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=SURFACE, width=220)
        self.pack_propagate(False)
        self.app = app
        self._build()

    def _build(self):
        # Logo
        topo = tk.Frame(self, bg=SURFACE, pady=14, padx=12)
        topo.pack(fill="x")
        tk.Label(topo, text="NOVA", font=("Courier", 22, "bold"),
                 bg=SURFACE, fg=PURPLE).pack(side="left")
        self.dot = tk.Label(topo, text="●", fg=TEAL,
                             font=("Courier", 10), bg=SURFACE)
        self.dot.pack(side="left", padx=4)

        tk.Frame(self, bg=SURFACE2, height=1).pack(fill="x")

        # Navegação
        nav = tk.Frame(self, bg=SURFACE, pady=8)
        nav.pack(fill="x")

        self.nav_btns = {}
        abas = [
            ("💬", "Chat",      "chat"),
            ("✅", "Tarefas",   "tarefas"),
            ("⏰", "Lembretes", "lembretes"),
            ("🎯", "Foco",      "foco"),
            ("📊", "Hábitos",   "habitos"),
        ]
        for icone, nome, chave in abas:
            b = tk.Button(nav, text=f"  {icone}  {nome}",
                          font=FONT_BODY, bg=SURFACE, fg=TEXT,
                          relief="flat", anchor="w", cursor="hand2",
                          activebackground=SURFACE2, activeforeground=WHITE,
                          command=lambda k=chave: self.app.trocar_aba(k),
                          padx=12, pady=7)
            b.pack(fill="x")
            self.nav_btns[chave] = b

        tk.Frame(self, bg=SURFACE2, height=1).pack(fill="x")

        # Sessões
        tk.Label(self, text="  CONVERSAS", font=FONT_SMALL,
                 fg=MUTED, bg=SURFACE, anchor="w").pack(fill="x", pady=(10, 2))

        btn_nova = tk.Button(self, text="  + Nova conversa",
                             font=FONT_SMALL, bg=SURFACE, fg=TEAL,
                             relief="flat", anchor="w", cursor="hand2",
                             activebackground=SURFACE2,
                             command=self.app.nova_conversa, padx=12, pady=5)
        btn_nova.pack(fill="x")

        self.frame_sessoes = tk.Frame(self, bg=SURFACE)
        self.frame_sessoes.pack(fill="both", expand=True)

        tk.Frame(self, bg=SURFACE2, height=1).pack(fill="x")

        # API Key
        btn(self, "⚙  API Key", self.app.pedir_key,
            bg=SURFACE, fg=MUTED, font=FONT_SMALL,
            padx=12, pady=8).pack(fill="x")

        self.atualizar_sessoes()

    def atualizar_sessoes(self):
        for w in self.frame_sessoes.winfo_children():
            w.destroy()

        sessoes = listar_sessoes()
        for s in sessoes[:30]:
            titulo = s["titulo"][:24] + "…" if len(s["titulo"]) > 24 else s["titulo"]
            f = tk.Frame(self.frame_sessoes, bg=SURFACE)
            f.pack(fill="x")

            b = tk.Button(f, text=f"  💬 {titulo}",
                          font=FONT_SMALL, bg=SURFACE, fg=TEXT,
                          relief="flat", anchor="w", cursor="hand2",
                          activebackground=SURFACE2,
                          command=lambda sid=s["id"]: self.app.abrir_sessao(sid),
                          padx=8, pady=4)
            b.pack(side="left", fill="x", expand=True)

            del_b = tk.Button(f, text="✕", font=FONT_SMALL,
                              bg=SURFACE, fg=MUTED, relief="flat",
                              cursor="hand2", activebackground=DANGER,
                              command=lambda sid=s["id"]: self.app.deletar_sessao(sid),
                              padx=4)
            del_b.pack(side="right")

    def marcar_aba(self, chave):
        for k, b in self.nav_btns.items():
            b.configure(bg=SURFACE2 if k == chave else SURFACE,
                        fg=WHITE if k == chave else TEXT)

# ═══════════════════════════════════════════════════════════════════════════════
# APP PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

class NovaApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NOVA — Assistente Pessoal")
        self.root.configure(bg=BG)
        self.root.geometry("1100x700")
        self.root.minsize(800, 500)

        self.api_key = carregar_key()
        self.aba_atual = "chat"

        self._build()
        iniciar_rotinas()
        self._resumo_matinal()

        if not self.api_key:
            self.root.after(400, self.pedir_key)

    def _build(self):
        # Container principal
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = Sidebar(main, self)
        self.sidebar.pack(side="left", fill="y")

        tk.Frame(main, bg=SURFACE2, width=1).pack(side="left", fill="y")

        # Área de conteúdo
        self.conteudo = tk.Frame(main, bg=BG)
        self.conteudo.pack(side="left", fill="both", expand=True)

        # Painéis
        self.paineis = {
            "chat":      PainelChat(self.conteudo, self),
            "tarefas":   PainelTarefas(self.conteudo, self),
            "lembretes": PainelLembretes(self.conteudo, self),
            "foco":      PainelFoco(self.conteudo, self),
            "habitos":   PainelHabitos(self.conteudo, self),
        }

        # Inicia na aba chat com nova sessão
        sid = self.paineis["chat"].nova_sessao()
        self.sessao_atual = sid
        self.trocar_aba("chat")

    def _resumo_matinal(self):
        resumo = gerar_resumo_matinal()
        self.paineis["chat"]._append("NOVA", resumo, "nova_name", "nova_text")

    def trocar_aba(self, chave: str):
        for p in self.paineis.values():
            p.pack_forget()
        self.paineis[chave].pack(fill="both", expand=True)
        self.sidebar.marcar_aba(chave)
        self.aba_atual = chave

        # Atualiza dados ao trocar aba
        if chave == "tarefas":
            self.paineis["tarefas"].atualizar()
        elif chave == "lembretes":
            self.paineis["lembretes"].atualizar()
        elif chave == "habitos":
            self.paineis["habitos"].atualizar()

    def nova_conversa(self):
        self.trocar_aba("chat")
        sid = self.paineis["chat"].nova_sessao()
        self.sessao_atual = sid
        self.sidebar.atualizar_sessoes()

    def abrir_sessao(self, sessao_id: int):
        self.trocar_aba("chat")
        self.sessao_atual = sessao_id
        self.paineis["chat"].carregar_sessao(sessao_id)

    def deletar_sessao(self, sessao_id: int):
        deletar_sessao(sessao_id)
        self.sidebar.atualizar_sessoes()
        if self.sessao_atual == sessao_id:
            self.nova_conversa()

    def pedir_key(self):
        key = simpledialog.askstring(
            "Gemini API Key",
            "Cole sua Gemini API key:\n(aistudio.google.com → Get API key)",
            show="*", parent=self.root
        )
        if key and key.strip():
            self.api_key = key.strip()
            salvar_key(self.api_key)
            messagebox.showinfo("NOVA", "✓ API key salva!", parent=self.root)
