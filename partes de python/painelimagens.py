# ═══════════════════════════════════════════════════════════════════════════════
# PAINEL: IMAGENS
# Cole esse bloco dentro do Interface.py, antes da classe Sidebar
# Adicione "imagens": PainelImagens(self.conteudo, self) no dict self.paineis
# Adicione ("🖼", "Imagens", "imagens") na lista abas da Sidebar
# Importe no topo: from imagens import (remover_fundo, melhorar_qualidade,
#   aumentar_resolucao, otimizar_instagram, trocar_fundo_cor,
#   listar_editadas, abrir_pasta_editadas, FORMATOS_INSTAGRAM)
# ═══════════════════════════════════════════════════════════════════════════════

import threading
import tkinter as tk
from tkinter import filedialog, colorchooser
from PIL import Image, ImageTk

class PainelImagens(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.caminho_atual = None
        self.img_preview   = None
        self._build()

    def _build(self):
        # Topo
        topo = tk.Frame(self, bg=SURFACE, pady=10, padx=14)
        topo.pack(fill="x")
        label(topo, "🖼  Imagens", fg=PURPLE, font=FONT_TITLE, bg=SURFACE).pack(side="left")
        btn(topo, "📂 Abrir editadas", abrir_pasta_editadas,
            bg=SURFACE2, fg=MUTED).pack(side="right", padx=4)

        tk.Frame(self, bg=SURFACE2, height=1).pack(fill="x")

        # Layout principal: preview esquerda + controles direita
        corpo = tk.Frame(self, bg=BG)
        corpo.pack(fill="both", expand=True, padx=14, pady=10)

        # ── Preview ──────────────────────────────────────────────────────────
        frame_preview = tk.Frame(corpo, bg=SURFACE, width=400)
        frame_preview.pack(side="left", fill="both", expand=True, padx=(0, 10))
        frame_preview.pack_propagate(False)

        btn(frame_preview, "📁 Selecionar imagem", self._selecionar,
            padx=16, pady=8).pack(pady=12)

        self.lbl_preview = tk.Label(frame_preview, bg=SURFACE,
                                     text="Nenhuma imagem selecionada",
                                     fg=MUTED, font=FONT_SMALL)
        self.lbl_preview.pack(expand=True)

        self.lbl_info = tk.Label(frame_preview, bg=SURFACE,
                                  fg=MUTED, font=FONT_SMALL, text="")
        self.lbl_info.pack(pady=4)

        # ── Controles ─────────────────────────────────────────────────────────
        frame_ctrl = tk.Frame(corpo, bg=BG, width=280)
        frame_ctrl.pack(side="right", fill="y")
        frame_ctrl.pack_propagate(False)

        # Status
        self.lbl_status = tk.Label(frame_ctrl, bg=BG, fg=TEAL,
                                    font=FONT_SMALL, text="", wraplength=260)
        self.lbl_status.pack(pady=(0, 8))

        # ── Remover fundo ─────────────────────────────────────────────────────
        self._secao(frame_ctrl, "✂️  Remover fundo")
        btn(frame_ctrl, "Remover fundo", self._remover_fundo,
            padx=12, pady=6).pack(fill="x", pady=2)

        # ── Trocar fundo por cor ──────────────────────────────────────────────
        self._secao(frame_ctrl, "🎨  Trocar fundo por cor")
        self.cor_fundo = (255, 255, 255)
        self.btn_cor = tk.Button(frame_ctrl, text="  Branco  ",
                                  bg="#ffffff", fg="#000000",
                                  font=FONT_SMALL, relief="flat",
                                  cursor="hand2", command=self._escolher_cor)
        self.btn_cor.pack(fill="x", pady=2)
        btn(frame_ctrl, "Aplicar fundo colorido", self._trocar_fundo_cor,
            padx=12, pady=6).pack(fill="x", pady=2)

        # ── Melhorar qualidade ────────────────────────────────────────────────
        self._secao(frame_ctrl, "✨  Melhorar qualidade")

        sliders = tk.Frame(frame_ctrl, bg=BG)
        sliders.pack(fill="x")

        self.sl_nitidez   = self._slider(sliders, "Nitidez",   1.0, 4.0, 2.0)
        self.sl_brilho    = self._slider(sliders, "Brilho",    0.5, 2.0, 1.1)
        self.sl_contraste = self._slider(sliders, "Contraste", 0.5, 2.0, 1.2)
        self.sl_cor       = self._slider(sliders, "Saturação", 0.5, 2.0, 1.1)

        btn(frame_ctrl, "Melhorar qualidade", self._melhorar,
            padx=12, pady=6).pack(fill="x", pady=2)

        # ── Aumentar resolução ────────────────────────────────────────────────
        self._secao(frame_ctrl, "🔍  Aumentar resolução")

        escala_frame = tk.Frame(frame_ctrl, bg=BG)
        escala_frame.pack(fill="x", pady=2)
        label(escala_frame, "Escala:", bg=BG, fg=MUTED).pack(side="left")
        self.escala_var = tk.IntVar(value=2)
        for v in [2, 3, 4]:
            tk.Radiobutton(escala_frame, text=f"{v}x", variable=self.escala_var,
                           value=v, bg=BG, fg=TEXT, selectcolor=SURFACE2,
                           activebackground=BG, font=FONT_SMALL).pack(side="left", padx=4)

        btn(frame_ctrl, "Aumentar resolução", self._aumentar,
            padx=12, pady=6).pack(fill="x", pady=2)

        # ── Otimizar Instagram ────────────────────────────────────────────────
        self._secao(frame_ctrl, "📱  Otimizar para Instagram")

        self.formato_var = tk.StringVar(value="Feed quadrado (1:1)")
        fmt_menu = tk.OptionMenu(frame_ctrl, self.formato_var,
                                  *FORMATOS_INSTAGRAM.keys())
        fmt_menu.configure(bg=SURFACE2, fg=TEXT, font=FONT_SMALL,
                            relief="flat", highlightthickness=0,
                            activebackground=SURFACE, activeforeground=WHITE)
        fmt_menu["menu"].configure(bg=SURFACE2, fg=TEXT, font=FONT_SMALL)
        fmt_menu.pack(fill="x", pady=2)

        btn(frame_ctrl, "Otimizar para Instagram", self._otimizar_instagram,
            padx=12, pady=6).pack(fill="x", pady=2)

    def _secao(self, parent, titulo):
        tk.Frame(parent, bg=SURFACE2, height=1).pack(fill="x", pady=(10, 4))
        tk.Label(parent, text=titulo, fg=MUTED, font=FONT_SMALL,
                 bg=BG, anchor="w").pack(fill="x")

    def _slider(self, parent, nome, minv, maxv, default):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=1)
        tk.Label(f, text=f"{nome}:", fg=MUTED, font=FONT_SMALL,
                 bg=BG, width=10, anchor="w").pack(side="left")
        sl = tk.Scale(f, from_=minv, to=maxv, resolution=0.1,
                      orient="horizontal", bg=BG, fg=TEXT,
                      troughcolor=SURFACE2, highlightthickness=0,
                      font=FONT_SMALL, showvalue=True)
        sl.set(default)
        sl.pack(side="left", fill="x", expand=True)
        return sl

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _selecionar(self):
        path = filedialog.askopenfilename(
            title="Selecionar imagem",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp")]
        )
        if not path:
            return
        self.caminho_atual = path
        self._atualizar_preview(path)
        self.lbl_status.configure(text="")

    def _atualizar_preview(self, path):
        try:
            img = Image.open(path)
            w, h = img.size
            self.lbl_info.configure(text=f"{w}×{h}px  •  {os.path.basename(path)}")
            img.thumbnail((380, 380), Image.LANCZOS)
            self.img_preview = ImageTk.PhotoImage(img)
            self.lbl_preview.configure(image=self.img_preview, text="")
        except Exception as e:
            self.lbl_preview.configure(text=f"Erro ao carregar: {e}", image="")

    def _status(self, msg, cor=TEAL):
        self.lbl_status.configure(text=msg, fg=cor)

    def _verificar_imagem(self) -> bool:
        if not self.caminho_atual:
            self._status("⚠ Selecione uma imagem primeiro.", WARNING)
            return False
        return True

    def _rodar_em_thread(self, fn, *args):
        self._status("⏳ Processando...", MUTED)
        def tarefa():
            try:
                resultado = fn(*args)
                self.after(0, self._apos_processar, resultado)
            except Exception as e:
                self.after(0, self._status, f"❌ {e}", DANGER)
        threading.Thread(target=tarefa, daemon=True).start()

    def _apos_processar(self, caminho_saida):
        self._status(f"✅ Salvo em:\n{os.path.basename(caminho_saida)}", SUCCESS)
        self._atualizar_preview(caminho_saida)

    def _remover_fundo(self):
        if not self._verificar_imagem(): return
        self._rodar_em_thread(remover_fundo, self.caminho_atual)

    def _escolher_cor(self):
        cor = colorchooser.askcolor(color=self.cor_fundo, title="Escolher cor do fundo")
        if cor[0]:
            self.cor_fundo = tuple(int(c) for c in cor[0])
            hex_cor = cor[1]
            r, g, b = self.cor_fundo
            luminancia = (0.299*r + 0.587*g + 0.114*b)
            fg = "#000000" if luminancia > 128 else "#ffffff"
            self.btn_cor.configure(bg=hex_cor, fg=fg,
                                    text=f"  {hex_cor}  ")

    def _trocar_fundo_cor(self):
        if not self._verificar_imagem(): return
        self._rodar_em_thread(trocar_fundo_cor, self.caminho_atual, self.cor_fundo)

    def _melhorar(self):
        if not self._verificar_imagem(): return
        self._rodar_em_thread(
            melhorar_qualidade,
            self.caminho_atual,
            None,
            self.sl_nitidez.get(),
            self.sl_brilho.get(),
            self.sl_contraste.get(),
            self.sl_cor.get()
        )

    def _aumentar(self):
        if not self._verificar_imagem(): return
        self._rodar_em_thread(aumentar_resolucao, self.caminho_atual, self.escala_var.get())

    def _otimizar_instagram(self):
        if not self._verificar_imagem(): return
        self._rodar_em_thread(otimizar_instagram, self.caminho_atual, self.formato_var.get())