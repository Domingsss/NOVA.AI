# src/webview_api.py
import os
import json
import base64
import subprocess
import io
import tkinter as tk
from tkinter import filedialog
from PIL import Image

# Importando seus arquivos originais sem modificar nada!
from database import *
from helpers import *
from api import *  # Seu api.py original (onde está a Groq/OpenAI)
from rotinas import gerar_resumo_matinal, iniciar_rotinas

class Api:
    """Esta classe expõe os métodos do Python para o Javascript via pywebview."""
    
    def __init__(self):
        try:
            iniciar_rotinas()
        except Exception as e:
            print(f"Aviso: Não foi possível iniciar as rotinas em background: {e}")

    # ── Utilitário interno ──
    def _response(self, ok=True, data=None, erro=None):
        """Formata a resposta no padrão JSON que o app.js espera."""
        return json.dumps({"ok": ok, "data": data, "erro": erro})

    # ════════════════════════════════════════════════════════════════════════
    # CHAT E SESSÕES
    # ════════════════════════════════════════════════════════════════════════
    def nova_sessao(self):
        try:
            sid = criar_sessao()
            return self._response(data={"sessao_id": sid})
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def get_sessoes(self):
        try:
            sessoes = listar_sessoes()
            return self._response(data=sessoes)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def deletar_sessao(self, sessao_id):
        try:
            deletar_sessao(sessao_id)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def get_historico(self, sessao_id):
        try:
            historico = carregar_historico(sessao_id)
            return self._response(data=historico)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def get_resumo_matinal(self):
        try:
            resumo = gerar_resumo_matinal()
            return self._response(data={"resumo": resumo})
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def enviar_mensagem(self, sessao_id, texto):
        try:
            salvar_mensagem(sessao_id, "user", texto)
            historico = carregar_historico(sessao_id)
            
            api_key = carregar_key()
            if not api_key:
                return self._response(ok=False, erro="API Key não configurada.")
                
            resposta = chamar_groq(api_key, historico)
            salvar_mensagem(sessao_id, "assistant", resposta)
            
            return self._response(data={"tipo": "texto", "resposta": resposta})
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def chat_imagem(self, sessao_id, texto, base64_img):
        # Se você não tiver visão computacional na sua IA, ele apenas ignora a imagem e envia o texto
        return self.enviar_mensagem(sessao_id, texto)

    # ════════════════════════════════════════════════════════════════════════
    # API KEY
    # ════════════════════════════════════════════════════════════════════════
    def salvar_api_key(self, key):
        try:
            salvar_key(key)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    # ════════════════════════════════════════════════════════════════════════
    # TAREFAS
    # ════════════════════════════════════════════════════════════════════════
    def get_tarefas(self):
        try:
            return self._response(data=listar_tarefas())
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def criar_tarefa(self, titulo, desc, projeto, prioridade, prazo):
        try:
            criar_tarefa(titulo, desc, projeto, prioridade, prazo)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def concluir_tarefa(self, tarefa_id):
        try:
            concluir_tarefa(tarefa_id)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def deletar_tarefa(self, tarefa_id):
        try:
            deletar_tarefa(tarefa_id)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    # ════════════════════════════════════════════════════════════════════════
    # LEMBRETES
    # ════════════════════════════════════════════════════════════════════════
    def get_lembretes(self):
        try:
            return self._response(data=listar_lembretes())
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def criar_lembrete(self, titulo, data_hora, desc, repetir):
        try:
            criar_lembrete(titulo, data_hora, desc, repetir)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def deletar_lembrete(self, lembrete_id):
        try:
            deletar_lembrete(lembrete_id)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    # ════════════════════════════════════════════════════════════════════════
    # HÁBITOS
    # ════════════════════════════════════════════════════════════════════════
    def get_habitos(self):
        try:
            return self._response(data=listar_habitos())
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def criar_habito(self, nome, icone, cor):
        try:
            criar_habito(nome, icone, cor)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def registrar_habito(self, habito_id):
        try:
            registrar_habito(habito_id)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def deletar_habito(self, habito_id):
        try:
            deletar_habito(habito_id)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    # ════════════════════════════════════════════════════════════════════════
    # FOCO (POMODORO)
    # ════════════════════════════════════════════════════════════════════════
    def get_stats_foco(self):
        try:
            return self._response(data=stats_foco_hoje())
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def salvar_sessao_foco(self, duracao, pausa, concluido):
        try:
            salvar_sessao_foco(duracao, pausa, concluido)
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    # ════════════════════════════════════════════════════════════════════════
    # IMAGENS
    # ════════════════════════════════════════════════════════════════════════
    def abrir_pasta_editadas(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            pasta = os.path.join(base_dir, "assets", "imagens_editadas")
            if not os.path.exists(pasta):
                os.makedirs(pasta)
            subprocess.Popen(['explorer', pasta])
            return self._response(data=True)
        except Exception as e:
            return self._response(ok=False, erro=str(e))
            
    def abrir_arquivo_dialogo(self):
        try:
            root = tk.Tk()
            root.withdraw()
            caminho = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp")])
            root.destroy()
            
            if not caminho:
                return self._response(data=None)
                
            img = Image.open(caminho)
            largura, altura = img.size
            
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            return self._response(data={
                "caminho": caminho,
                "base64": img_base64,
                "largura": largura,
                "altura": altura,
                "nome": os.path.basename(caminho)
            })
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def processar_imagem(self, caminho, operacao, params):
        try:
            # Aqui você pode plugar suas funções do arquivo imagens.py
            # from imagens import remover_fundo, melhorar_qualidade...
            # if operacao == 'remover_fundo': ...
            
            # Retorno mockado por enquanto
            return self._response(data={
                "caminho": caminho,
                "base64": None 
            })
        except Exception as e:
            return self._response(ok=False, erro=str(e))

    def interpretar_e_processar_imagem(self, caminho, instrucao):
        try:
            # Implementar lógica de interpretar texto com IA e aplicar na imagem
            return self._response(data={
                "caminho": caminho,
                "base64": None
            })
        except Exception as e:
            return self._response(ok=False, erro=str(e))