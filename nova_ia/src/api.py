import os
import sys
import json
import time
import base64
import datetime
from helpers import carregar_key, salvar_key, chamar_groq, chamar_groq_simples, chamar_groq_stream
from database import (
    criar_sessao, listar_sessoes, renomear_sessao, deletar_sessao,
    salvar_mensagem, carregar_historico, limpar_historico,
    criar_tarefa, listar_tarefas, concluir_tarefa, deletar_tarefa,
    listar_projetos, criar_projeto, deletar_projeto,
    criar_lembrete, listar_lembretes, deletar_lembrete,
    criar_habito, listar_habitos, registrar_habito, deletar_habito,
    stats_foco_hoje, salvar_sessao_foco, resumo_matinal
)
from rotinas import gerar_resumo_matinal


class API:

    # ── Utilitários ───────────────────────────────────────────────────────────

    def _ok(self, data=None):
        return json.dumps({"ok": True, "data": data})

    def _erro(self, msg):
        return json.dumps({"ok": False, "erro": str(msg)})

    # ── API Key ───────────────────────────────────────────────────────────────

    def get_api_key(self):
        try:
            key = carregar_key()
            return self._ok({"tem_key": bool(key)})
        except Exception as e:
            return self._erro(e)

    def salvar_api_key(self, key: str):
        try:
            salvar_key(key.strip())
            return self._ok()
        except Exception as e:
            return self._erro(e)

    # ── Chat ──────────────────────────────────────────────────────────────────

    def nova_sessao(self, titulo: str = "Nova conversa"):
        try:
            sid = criar_sessao(titulo)
            return self._ok({"sessao_id": sid})
        except Exception as e:
            return self._erro(e)

    def get_sessoes(self):
        try:
            return self._ok(listar_sessoes())
        except Exception as e:
            return self._erro(e)

    def renomear_sessao(self, sessao_id: int, titulo: str):
        try:
            renomear_sessao(sessao_id, titulo)
            return self._ok()
        except Exception as e:
            return self._erro(e)

    def deletar_sessao(self, sessao_id: int):
        try:
            deletar_sessao(sessao_id)
            return self._ok()
        except Exception as e:
            return self._erro(e)

    def get_historico(self, sessao_id: int):
        try:
            return self._ok(carregar_historico(sessao_id))
        except Exception as e:
            return self._erro(e)

    def enviar_mensagem(self, sessao_id: int, mensagem: str, imagem_b64: str = None):
        try:
            api_key = carregar_key()
            if not api_key:
                return self._erro("API key não configurada.")

            historico = carregar_historico(sessao_id)

            if imagem_b64:
                if "," in imagem_b64:
                    mime, dados = imagem_b64.split(",", 1)
                    media_type = mime.split(":")[1].split(";")[0]
                else:
                    dados = imagem_b64
                    media_type = "image/jpeg"

                conteudo = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{dados}"
                        }
                    },
                    {
                        "type": "text",
                        "text": mensagem or "O que você vê nessa imagem?"
                    }
                ]
            else:
                conteudo = mensagem

            historico.append({"role": "user", "content": conteudo})
            salvar_mensagem(sessao_id, "user", mensagem or "[imagem]")

            # NOVA agente: tenta executar uma ação (criar tarefa/lembrete, etc)
            # antes de responder. Se executou, adiciona contexto pro modelo.
            try:
                ctx_agente = self._tentar_acao_agente(sessao_id, mensagem or "")
                if ctx_agente:
                    historico.append({"role": "system", "content": ctx_agente})
            except Exception:
                pass  # best-effort: não deixa o agente quebrar o chat

            # Web search: se a pergunta precisa de informação atual, busca
            # no DuckDuckGo e adiciona os resultados como contexto.
            try:
                ctx_web = self._tentar_web_search(mensagem or "")
                if ctx_web:
                    historico.append({"role": "system", "content": ctx_web})
            except Exception:
                pass  # best-effort: não deixa a busca quebrar o chat

            try:
                resposta = chamar_groq(api_key, historico)
            except Exception as e:
                # Erro da API: NÃO salva uma "resposta" de erro no banco,
                # pois poluiria o histórico e confundiria a IA nas próximas
                # mensagens. A mensagem do usuário já foi salva e é válida
                # como contexto.
                return self._erro(f"Falha ao contatar a IA: {e}")

            salvar_mensagem(sessao_id, "assistant", resposta)

            # Renomeia a sessão se ainda tiver o título padrão (só na 1ª troca)
            self._tentar_renomear_sessao(sessao_id, mensagem or "Imagem enviada")

            return self._ok({"tipo": "texto", "resposta": resposta})
        except Exception as e:
            return self._erro(e)

    def enviar_mensagem_stream(self, sessao_id: int, mensagem: str):
        """Envia mensagem e faz streaming da resposta, chunk por chunk.

        Cada chunk é injetado no frontend via `window.__novaChunk(texto)`.
        Ao final, chama `window.__novaFim()`. Em caso de erro durante o
        streaming, chama `window.__novaErro(msg)`.

        A resposta completa é salva no banco ao final (só se deu certo).
        """
        try:
            import webview
            janela = webview.windows[0] if webview.windows else None

            def emit(js):
                if janela:
                    try:
                        janela.evaluate_js(js)
                    except Exception:
                        pass

            api_key = carregar_key()
            if not api_key:
                emit("window.__novaErro && window.__novaErro('API key não configurada.')")
                return self._erro("API key não configurada.")

            historico = carregar_historico(sessao_id)
            historico.append({"role": "user", "content": mensagem})
            salvar_mensagem(sessao_id, "user", mensagem)

            # NOVA agente: tenta executar uma ação (criar tarefa/lembrete, etc)
            # antes de responder. Se executou, adiciona contexto pro modelo.
            # IMPORTANTE: a ação roda ANTES do streaming começar, pra que a
            # confirmação já venha no stream.
            try:
                ctx_agente = self._tentar_acao_agente(sessao_id, mensagem)
                if ctx_agente:
                    historico.append({"role": "system", "content": ctx_agente})
            except Exception:
                pass  # best-effort: não deixa o agente quebrar o chat

            # Web search: se a pergunta precisa de informação atual, busca
            # no DuckDuckGo e adiciona os resultados como contexto.
            try:
                ctx_web = self._tentar_web_search(mensagem)
                if ctx_web:
                    historico.append({"role": "system", "content": ctx_web})
            except Exception:
                pass  # best-effort: não deixa a busca quebrar o chat

            resposta_completa = ""
            try:
                for chunk in chamar_groq_stream(api_key, historico):
                    resposta_completa += chunk
                    emit(f"window.__novaChunk && window.__novaChunk({json.dumps(chunk)});")
            except Exception as e:
                emit(f"window.__novaErro && window.__novaErro({json.dumps(str(e))});")
                # Não salva resposta parcial no banco — poluiria o histórico
                return self._erro(f"Falha ao contatar a IA: {e}")

            salvar_mensagem(sessao_id, "assistant", resposta_completa)
            self._tentar_renomear_sessao(sessao_id, mensagem)

            emit("window.__novaFim && window.__novaFim();")
            return self._ok({"resposta": resposta_completa})
        except Exception as e:
            return self._erro(e)

    def _tentar_acao_agente(self, sessao_id: int, mensagem: str):
        """Detecta se a mensagem é um pedido de ação (criar tarefa/lembrete,
        listar tarefas, etc). Se for, executa e retorna um texto de confirmação
        pra NOVA incluir na resposta.

        Roda de forma best-effort: se falhar (rede, IA não retornar JSON, etc),
        retorna None e o fluxo continua normalmente (só conversa).
        """
        try:
            import datetime as _dt

            hoje = _dt.date.today().strftime("%Y-%m-%d")

            system = f"""Você é um classificador de intenções. Analise a mensagem do usuário e decida se é um pedido para executar uma AÇÃO no sistema.

Data de hoje: {hoje}

Ações disponíveis:
- criar_tarefa: criar uma tarefa nova. params: {{"titulo": "...", "prioridade": "alta|media|baixa", "prazo": "YYYY-MM-DD ou null"}}
  - "titulo": obrigatório, curto e descritivo
  - "prioridade": opcional (padrão "media")
  - "prazo": opcional (formato YYYY-MM-DD, ou null se não mencionado). Interprete "hoje", "amanhã", "próxima semana", etc.
- criar_lembrete: criar um lembrete. params: {{"titulo": "...", "data_hora": "YYYY-MM-DDTHH:MM", "repetir": "nunca|diario|semanal"}}
  - "titulo": obrigatório
  - "data_hora": obrigatório (formato YYYY-MM-DDTHH:MM). Se não veio hora, use 09:00.
  - "repetir": opcional (padrão "nunca")
- listar_tarefas: listar tarefas pendentes. params: {{}}
- nenhuma: a mensagem NÃO é um pedido de ação (é conversa, pergunta, etc).

Regras:
- Só classifique como ação se a intenção do usuário for CLARAMENTE executar a ação.
- "me lembra de X amanhã" → criar_lembrete
- "cria uma tarefa de X" / "anota aí: X" / "preciso fazer X até Y" → criar_tarefa
- "quais são minhas tarefas?" / "o que tenho pendente?" → listar_tarefas
- "o que é X?" / "me explica Y" / "oi" → nenhuma

Responda APENAS com um JSON válido, sem markdown, sem texto antes ou depois:
{{"acao": "...", "params": {{...}}}}"""

            resposta = chamar_groq_simples(system, mensagem)
            texto = resposta.strip()
            if texto.startswith("```"):
                texto = texto.strip("`")
                if texto.lower().startswith("json"):
                    texto = texto[4:]
            texto = texto.strip()

            escolha = json.loads(texto)
            acao = escolha.get("acao", "nenhuma")
            params = escolha.get("params", {})

            if acao == "nenhuma" or not acao:
                return None

            # ── Executa a ação ──
            if acao == "criar_tarefa":
                titulo = params.get("titulo", "").strip()
                if not titulo:
                    return None
                prioridade = params.get("prioridade", "media")
                if prioridade not in ("alta", "media", "baixa"):
                    prioridade = "media"
                prazo = params.get("prazo")
                if prazo == "null":
                    prazo = None
                tid = criar_tarefa(titulo, "", None, prioridade, prazo)
                prazo_txt = f" (prazo: {prazo})" if prazo else ""
                return f"[SISTEMA — Ação executada automaticamente: criei a tarefa #{tid} '{titulo}' com prioridade {prioridade}{prazo_txt}. Confirme ao usuário de forma natural, mencionando a tarefa.]"

            if acao == "criar_lembrete":
                titulo = params.get("titulo", "").strip()
                data_hora = params.get("data_hora", "").strip()
                if not titulo or not data_hora:
                    return None
                repetir = params.get("repetir", "nunca")
                if repetir not in ("nunca", "diario", "semanal"):
                    repetir = "nunca"
                lid = criar_lembrete(titulo, data_hora, "", repetir)
                rep_txt = f", repete {repetir}" if repetir != "nunca" else ""
                return f"[SISTEMA — Ação executada automaticamente: criei o lembrete #{lid} '{titulo}' para {data_hora}{rep_txt}. Confirme ao usuário de forma natural, mencionando o lembrete.]"

            if acao == "listar_tarefas":
                tarefas = listar_tarefas(status="pendente")
                if not tarefas:
                    return "[SISTEMA — Ação executada: o usuário pediu suas tarefas pendentes. Não há nenhuma. Avise.]"
                lista = "; ".join(f"{t['titulo']} ({t['prioridade']})" for t in tarefas[:10])
                return f"[SISTEMA — Ação executada: o usuário pediu suas tarefas pendentes. Encontrei {len(tarefas)}: {lista}. Apresente ao usuário de forma organizada.]"

            return None

        except json.JSONDecodeError:
            return None
        except Exception:
            return None
        
    def _tentar_web_search(self, mensagem: str):
        """Decide se a mensagem precisa de busca na web. Se sim, faz a busca
        no DuckDuckGo e retorna os resultados como contexto pro modelo.

        Retorna None se não precisar buscar ou se a busca falhar (best-effort).
        Requer o pacote 'duckduckgo-search' (ou 'ddgs') instalado.
        """
        try:
            # ── 1. Classifica + extrai query de busca (1 chamada LLM) ──
            system = """Analise a mensagem do usuário. Decida se ela precisa de informação ATUAL ou RECENTE que provavelmente NÃO está no seu conhecimento pré-treinado.

Precisa de busca web se a mensagem pergunta sobre:
- Notícias, eventos atuais, "o que aconteceu hoje"
- Preços, cotações (dólar, bitcoin, ações)
- Versões recentes de software, lançamentos
- Documentação nova, regras/mudanças recentes
- Pessoas vivas, fatos recentes
- "Qual o melhor X em 2024/2025"

NÃO precisa de busca se for:
- Pergunta conceitual ("o que é X", "como funciona Y")
- Pedido de opinião, criatividade, escrita
- Conversa genérica, cumprimentos
- Pedido de ação (criar tarefa/lembrete) — outro sistema cuida disso
- Conhecimento histórico, ciência, matemática

Responda APENAS com um JSON válido, sem markdown:
{"buscar": true, "query": "search query curta em inglês"}
ou
{"buscar": false, "query": ""}"""

            resposta = chamar_groq_simples(system, mensagem)
            texto = resposta.strip()
            if texto.startswith("```"):
                texto = texto.strip("`")
                if texto.lower().startswith("json"):
                    texto = texto[4:]
            texto = texto.strip()

            escolha = json.loads(texto)
            if not escolha.get("buscar", False):
                return None

            query = escolha.get("query", "").strip()
            if not query:
                return None

            # ── 2. Faz a busca no DuckDuckGo ──
            # Prioriza o pacote novo 'ddgs' (o antigo 'duckduckgo_search' v8
            # está deprecated e retorna 0 resultados).
            DDGS = None
            try:
                from ddgs import DDGS
            except ImportError:
                try:
                    from duckduckgo_search import DDGS
                except ImportError:
                    return None  # busca não disponível — ignora silenciosamente

            # API nova (ddgs / duckduckgo_search v6+): sem context manager
            raw = None
            try:
                ddgs = DDGS()
                raw = list(ddgs.text(query, max_results=4))
            except Exception:
                # Fallback: context manager (v5 e anteriores)
                try:
                    with DDGS() as ddgs:
                        raw = list(ddgs.text(query, max_results=4))
                except Exception:
                    return None

            if not raw:
                return None

            # ── 3. Formata os resultados ──
            # O campo pode ser 'body', 'snippet' ou 'content' dependendo da versão
            linhas = []
            for i, r in enumerate(raw[:4], 1):
                titulo = r.get("title", "Sem título")
                corpo = r.get("body") or r.get("snippet") or r.get("content") or ""
                url = r.get("href") or r.get("url") or r.get("link") or ""
                linhas.append(f"[{i}] {titulo}\n{corpo}\nFonte: {url}")

            formatado = "\n\n".join(linhas)

            return (
                f"[SISTEMA — Resultados de busca web para '{query}':\n\n"
                f"{formatado}\n\n"
                f"Use estas informações atualizadas para responder ao usuário de "
                f"forma natural. Cite as fontes quando relevante (ex: 'segundo o "
                f"site X...'). Se os resultados não ajudarem, diga que não encontrou "
                f"informação atualizada.]"
            )

        except json.JSONDecodeError:
            return None
        except Exception:
            return None

    def _tentar_renomear_sessao(self, sessao_id: int, primeira_msg: str):
        """Gera um título curto para a sessão se ela ainda tiver o nome padrão.

        Roda de forma best-effort: se falhar (rede, quota, etc), a sessão
        simplesmente continua com o nome padrão — não derruba o chat.
        """
        try:
            sessoes = listar_sessoes()
            sessao = next((s for s in sessoes if s["id"] == sessao_id), None)
            if not sessao:
                return
            if sessao["titulo"] != "Nova conversa":
                return  # já tem nome customizado, não mexe

            system = (
                "Gere um título MUITO curto (máximo 5 palavras) que resuma o tema "
                "da mensagem do usuário. Sem aspas, sem pontuação final, sem "
                "prefixos como 'Título:'. Responda APENAS com o título."
            )
            titulo = chamar_groq_simples(system, primeira_msg[:500]).strip()
            # Limpa aspas e eventuais aspas envolvendo o título
            titulo = titulo.strip("\"'").strip()
            if len(titulo) > 60:
                titulo = titulo[:57] + "..."
            if titulo:
                renomear_sessao(sessao_id, titulo)
        except Exception:
            pass  # best-effort: não deixa o rename quebrar o chat

    def chat_imagem(self, sessao_id: int, mensagem: str, imagem_b64: str):
        """
        Recebe uma imagem enviada no chat. Tenta interpretar o pedido como
        uma EDIÇÃO de imagem (determinística ou generativa via IA local).
        Só cai para conversa de texto normal se o pedido não for um pedido
        de edição (ex: uma pergunta sobre a foto, um cumprimento, etc).
        """
        try:
            from imagens import OUTPUT_DIR

            if "," in imagem_b64:
                mime, dados = imagem_b64.split(",", 1)
                ext = "png" if "png" in mime else "jpg"
            else:
                dados = imagem_b64
                ext = "jpg"

            nome_temp = f"chat_{int(time.time()*1000)}.{ext}"
            caminho_temp = os.path.join(OUTPUT_DIR, nome_temp)
            with open(caminho_temp, "wb") as f:
                f.write(base64.b64decode(dados))

            resultado_raw = self.interpretar_e_processar_imagem(caminho_temp, mensagem)
            resultado = json.loads(resultado_raw)

            if resultado.get("ok"):
                operacao = resultado["data"]["operacao"]
                if operacao == "gerar_ia":
                    resposta_texto = "✅ Prontinho! Editei a imagem como você pediu."
                else:
                    resposta_texto = f"✅ Prontinho! Apliquei: {operacao.replace('_', ' ')}."

                salvar_mensagem(sessao_id, "user", mensagem or "[imagem enviada]")
                salvar_mensagem(sessao_id, "assistant", resposta_texto)

                return self._ok({
                    "tipo": "imagem",
                    "resposta": resposta_texto,
                    "imagem_base64": resultado["data"]["base64"],
                    "caminho": resultado["data"]["caminho"]
                })
            else:
                # Não foi reconhecido como pedido de edição — conversa normal com visão
                return self.enviar_mensagem(sessao_id, mensagem, imagem_b64)

        except Exception as e:
            return self._erro(e)

    def get_resumo_matinal(self):
        try:
            return self._ok({"resumo": gerar_resumo_matinal()})
        except Exception as e:
            return self._erro(e)

    # ── Tarefas ───────────────────────────────────────────────────────────────

    def get_tarefas(self, projeto_id=None, status=None):
        try:
            return self._ok(listar_tarefas(projeto_id, status))
        except Exception as e:
            return self._erro(e)

    def criar_tarefa(self, titulo: str, descricao: str = "",
                     projeto_id=None, prioridade: str = "media", prazo: str = None):
        try:
            tid = criar_tarefa(titulo, descricao, projeto_id, prioridade, prazo)
            return self._ok({"id": tid})
        except Exception as e:
            return self._erro(e)

    def concluir_tarefa(self, tarefa_id: int):
        try:
            concluir_tarefa(tarefa_id)
            return self._ok()
        except Exception as e:
            return self._erro(e)

    def deletar_tarefa(self, tarefa_id: int):
        try:
            deletar_tarefa(tarefa_id)
            return self._ok()
        except Exception as e:
            return self._erro(e)

    # ── Projetos ──────────────────────────────────────────────────────────────

    def get_projetos(self):
        try:
            return self._ok(listar_projetos())
        except Exception as e:
            return self._erro(e)

    def criar_projeto(self, nome: str, cor: str = "#7c6fff"):
        try:
            pid = criar_projeto(nome, cor)
            return self._ok({"id": pid})
        except Exception as e:
            return self._erro(e)

    def deletar_projeto(self, projeto_id: int):
        try:
            deletar_projeto(projeto_id)
            return self._ok()
        except Exception as e:
            return self._erro(e)

    # ── Lembretes ─────────────────────────────────────────────────────────────

    def get_lembretes(self):
        try:
            return self._ok(listar_lembretes())
        except Exception as e:
            return self._erro(e)

    def criar_lembrete(self, titulo: str, data_hora: str,
                       descricao: str = "", repetir: str = "nunca"):
        try:
            lid = criar_lembrete(titulo, data_hora, descricao, repetir)
            return self._ok({"id": lid})
        except Exception as e:
            return self._erro(e)

    def deletar_lembrete(self, lembrete_id: int):
        try:
            deletar_lembrete(lembrete_id)
            return self._ok()
        except Exception as e:
            return self._erro(e)

    # ── Hábitos ───────────────────────────────────────────────────────────────

    def get_habitos(self):
        try:
            return self._ok(listar_habitos())
        except Exception as e:
            return self._erro(e)

    def criar_habito(self, nome: str, icone: str = "⭐", cor: str = "#7c6fff"):
        try:
            hid = criar_habito(nome, icone, cor)
            return self._ok({"id": hid})
        except Exception as e:
            return self._erro(e)

    def registrar_habito(self, habito_id: int):
        try:
            feito = registrar_habito(habito_id)
            return self._ok({"feito": feito})
        except Exception as e:
            return self._erro(e)

    def deletar_habito(self, habito_id: int):
        try:
            deletar_habito(habito_id)
            return self._ok()
        except Exception as e:
            return self._erro(e)

    # ── Foco ──────────────────────────────────────────────────────────────────

    def get_stats_foco(self):
        try:
            return self._ok(stats_foco_hoje())
        except Exception as e:
            return self._erro(e)

    def salvar_sessao_foco(self, duracao_min: int, pausa_min: int, concluido: bool):
        try:
            salvar_sessao_foco(duracao_min, pausa_min, concluido)
            return self._ok()
        except Exception as e:
            return self._erro(e)

    # ── Resumo ────────────────────────────────────────────────────────────────

    def get_resumo(self):
        try:
            return self._ok(resumo_matinal())
        except Exception as e:
            return self._erro(e)

    # ── Imagens ───────────────────────────────────────────────────────────────

    def processar_imagem(self, caminho: str, operacao: str, params: dict = None):
        try:
            from imagens import (remover_fundo, melhorar_qualidade,
                                  aumentar_resolucao, otimizar_instagram,
                                  trocar_fundo_cor)
            params = params or {}

            if operacao == "remover_fundo":
                resultado = remover_fundo(caminho)

            elif operacao == "melhorar":
                resultado = melhorar_qualidade(
                    caminho,
                    nitidez=params.get("nitidez", 2.0),
                    brilho=params.get("brilho", 1.1),
                    contraste=params.get("contraste", 1.2),
                    cor=params.get("cor", 1.1)
                )

            elif operacao == "aumentar":
                resultado = aumentar_resolucao(caminho, params.get("escala", 2))

            elif operacao == "instagram":
                resultado = otimizar_instagram(caminho, params.get("formato", "Feed quadrado (1:1)"))

            elif operacao == "trocar_fundo":
                cor = params.get("cor", [255, 255, 255])
                if isinstance(cor, str):
                    cor = cor.lstrip("#")
                    cor = tuple(int(cor[i:i+2], 16) for i in (0, 2, 4))
                else:
                    cor = tuple(cor)
                resultado = trocar_fundo_cor(caminho, cor)

            elif operacao == "gerar_ia":
                from ia_imagem import editar_imagem_ia
                prompt = params.get("prompt", "uma versão aprimorada desta imagem")
                forca = params.get("forca", 0.55)
                resultado = editar_imagem_ia(caminho, prompt, forca=forca)

            else:
                return self._erro(f"Operação desconhecida: {operacao}")

            with open(resultado, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            ext = os.path.splitext(resultado)[1].lstrip(".")
            mime = "image/png" if ext == "png" else "image/jpeg"

            return self._ok({
                "caminho": resultado,
                "base64": f"data:{mime};base64,{b64}",
                "operacao": operacao
            })
        except Exception as e:
            return self._erro(e)

    def interpretar_e_processar_imagem(self, caminho: str, instrucao: str):
        """
        Recebe um pedido em texto livre e decide o que fazer:
        - Operações determinísticas simples (remover fundo, melhorar, etc) usam
          o pipeline rápido baseado em regras.
        - Qualquer outro pedido de EDIÇÃO (trocar cenário, adicionar algo, mudar
          roupa, estilo, etc) é traduzido para um prompt em inglês e processado
          pela IA generativa local (Stable Diffusion).
        - Só retorna "desconhecida" se não for um pedido de edição (pergunta,
          cumprimento, etc).
        """
        try:
            from imagens import FORMATOS_INSTAGRAM

            formatos = ", ".join(f'"{f}"' for f in FORMATOS_INSTAGRAM.keys())

            system = f"""Você é um classificador e tradutor de pedidos de edição de imagem.

Primeiro, decida se a mensagem do usuário É um pedido para editar/transformar a imagem.
Se NÃO for (ex: pergunta sobre a imagem, cumprimento, conversa genérica), responda:
{{"operacao": "desconhecida", "params": {{}}}}

Se FOR um pedido de edição, escolha a operação mais adequada:

- remover_fundo: remove o fundo da imagem (sem parâmetros)
- trocar_fundo: troca o fundo por uma cor sólida específica. params: {{"cor": "#rrggbb"}}
- melhorar: melhora nitidez, brilho, contraste e saturação. params opcionais (0.5 a 4.0): {{"nitidez": 2.0, "brilho": 1.1, "contraste": 1.2, "cor": 1.1}}
- aumentar: aumenta a resolução. params: {{"escala": 2}} (2, 3 ou 4)
- instagram: redimensiona para um formato do Instagram. params: {{"formato": "..."}} — exatamente uma destas: {formatos}
- gerar_ia: QUALQUER OUTRO pedido de edição que não se encaixe acima — trocar cenário/fundo por algo específico, adicionar ou remover objetos, mudar roupas, mudar estilo artístico, mudar clima/iluminação, transformações criativas em geral.
  params: {{"prompt": "...", "forca": 0.55}}
  - "prompt": traduza e reescreva o pedido do usuário como um prompt CURTO e DESCRITIVO em INGLÊS, no estilo usado para Stable Diffusion (ex: "a photo of a person wearing a formal business suit, professional lighting").
  - "forca": de 0.3 a 0.8 — use valores baixos (0.3-0.4) para mudanças sutis (cor, iluminação, pequenos ajustes) e valores altos (0.6-0.8) para mudanças grandes (trocar cenário inteiro, trocar roupa, mudar estilo).

Responda APENAS com um JSON válido, sem texto antes ou depois, sem markdown."""

            resposta = chamar_groq_simples(system, instrucao or "melhore essa imagem")

            texto = resposta.strip()
            if texto.startswith("```"):
                texto = texto.strip("`")
                if texto.lower().startswith("json"):
                    texto = texto[4:]
            texto = texto.strip()

            escolha = json.loads(texto)
            operacao = escolha.get("operacao")
            params = escolha.get("params", {})

            if operacao == "desconhecida" or not operacao:
                return self._erro("não reconhecido como pedido de edição")

            resultado = self.processar_imagem(caminho, operacao, params)
            return resultado

        except json.JSONDecodeError:
            return self._erro("não foi possível interpretar o pedido")
        except Exception as e:
            return self._erro(e)

    def gerar_imagem_do_zero(self, prompt: str):
        """Gera uma imagem totalmente nova a partir de uma descrição em texto."""
        try:
            from ia_imagem import gerar_imagem_ia

            system = """Traduza e reescreva o pedido do usuário como um prompt CURTO e
DESCRITIVO em INGLÊS, no estilo usado para Stable Diffusion. Responda APENAS
com o prompt em inglês, sem explicações, sem aspas, sem texto adicional."""

            prompt_en = chamar_groq_simples(system, prompt).strip()

            resultado = gerar_imagem_ia(prompt_en)

            with open(resultado, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()

            return self._ok({
                "caminho": resultado,
                "base64": f"data:image/png;base64,{b64}"
            })
        except Exception as e:
            return self._erro(e)

    def abrir_arquivo_dialogo(self):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Selecionar imagem",
                filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp")]
            )
            root.destroy()
            if path:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                from PIL import Image
                img = Image.open(path)
                w, h = img.size
                ext = os.path.splitext(path)[1].lstrip(".")
                mime = "image/png" if ext == "png" else "image/jpeg"
                return self._ok({
                    "caminho": path,
                    "nome": os.path.basename(path),
                    "largura": w,
                    "altura": h,
                    "base64": f"data:{mime};base64,{b64}"
                })
            return self._ok(None)
        except Exception as e:
            return self._erro(e)

    def abrir_pasta_editadas(self):
        try:
            from imagens import OUTPUT_DIR
            os.startfile(OUTPUT_DIR)
            return self._ok()
        except Exception as e:
            return self._erro(e)
        
            # ── Tema (salvar/carregar) ─────────────────────────────────────────────────
    def salvar_tema(self, tema: str):
        try:
            import database
            caminho = os.path.join(database.BASE_DIR, 'theme.json')
            with open(caminho, 'w') as f:
                json.dump({"tema": tema}, f)
            return self._ok()
        except Exception as e:
            return self._erro(e)

    def carregar_tema(self):
        try:
            import database
            caminho = os.path.join(database.BASE_DIR, 'theme.json')
            if os.path.exists(caminho):
                with open(caminho, 'r') as f:
                    data = json.load(f)
                    return self._ok({"tema": data.get("tema", "light")})
            return self._ok({"tema": "light"})
        except Exception as e:
            return self._erro(e)