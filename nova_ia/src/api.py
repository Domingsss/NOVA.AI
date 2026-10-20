import os
import sys
import json
import time
import base64
import datetime
import getpass
import platform
import shutil
import signal
import socket
import ssl
import subprocess
import tempfile
import threading
import wave
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from helpers import carregar_key, salvar_key, chamar_gemini, chamar_gemini_multimodal, chamar_gemini_simples, chamar_gemini_stream
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
from integrations import list_integrations, save_integration, delete_integration
import local_chat


class API:

    def __init__(self):
        self._gravacao_lock = threading.Lock()
        self._gravacao = None

    # utilitários

    def _ok(self, data=None):
        return json.dumps({"ok": True, "data": data})

    def _erro(self, msg):
        return json.dumps({"ok": False, "erro": str(msg)})

    # dashboard

    @staticmethod
    def _get_json(url: str):
        headers = {"User-Agent": "NOVA-Desktop/1.0", "Accept": "application/json"}
        erros = []
        # httpx costuma lidar melhor com proxy/certificados em builds Windows.
        try:
            import httpx
            with httpx.Client(timeout=7, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
        except ImportError:
            pass
        except Exception as erro:
            erros.append(f"httpx: {erro}")

        req = urllib.request.Request(url, headers=headers)
        contexto = ssl.create_default_context()
        # pyInstaller nem sempre encontra os certificados do sistema no Windows.
        try:
            import certifi
            contexto = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass
        ultimo_erro = None
        for tentativa in range(2):
            try:
                with urllib.request.urlopen(req, timeout=7, context=contexto) as response:
                    return json.load(response)
            except Exception as erro:
                ultimo_erro = erro
                if tentativa == 0:
                    time.sleep(0.5)
        erros.append(f"urllib: {ultimo_erro}")
        raise RuntimeError(" | ".join(erros))

    @staticmethod
    def _formatar_bytes(valor):
        valor = float(valor)
        for unidade in ("B", "KB", "MB", "GB", "TB"):
            if valor < 1024 or unidade == "TB":
                return f"{valor:.1f} {unidade}"
            valor /= 1024

    def _info_computador(self):
        disco = shutil.disk_usage(os.path.abspath(os.sep))
        info = {
            "usuario": getpass.getuser(),
            "hostname": socket.gethostname(),
            "sistema": f"{platform.system()} {platform.release()}",
            "arquitetura": platform.machine() or "desconhecida",
            "processador": platform.processor() or "Processador não identificado",
            "nucleos": os.cpu_count() or 0,
            "python": platform.python_version(),
            "disco_usado": self._formatar_bytes(disco.used),
            "disco_total": self._formatar_bytes(disco.total),
            "disco_percentual": round(disco.used / disco.total * 100),
        }
        try:
            import psutil
            memoria = psutil.virtual_memory()
            info.update({
                "cpu_percentual": round(psutil.cpu_percent(interval=0.15)),
                "ram_usada": self._formatar_bytes(memoria.used),
                "ram_total": self._formatar_bytes(memoria.total),
                "ram_percentual": round(memoria.percent),
                "uptime_segundos": max(0, int(time.time() - psutil.boot_time())),
            })
        except ImportError:
            info.update({"cpu_percentual": None, "ram_usada": None,
                         "ram_total": None, "ram_percentual": None,
                         "uptime_segundos": None})
        return info

    def _info_clima(self, cidade):
        busca = urllib.parse.urlencode({"name": cidade, "count": 1, "language": "pt", "format": "json"})
        geo = self._get_json(f"https://geocoding-api.open-meteo.com/v1/search?{busca}")
        resultados = geo.get("results") or []
        if not resultados:
            raise ValueError(f"Cidade não encontrada: {cidade}")
        local = resultados[0]
        params = urllib.parse.urlencode({
            "latitude": local["latitude"], "longitude": local["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": 1,
        })
        previsao = self._get_json(f"https://api.open-meteo.com/v1/forecast?{params}")
        atual, diario = previsao["current"], previsao["daily"]
        descricoes = {
            0: "Céu limpo", 1: "Predominantemente limpo", 2: "Parcialmente nublado",
            3: "Nublado", 45: "Neblina", 48: "Neblina com geada",
            51: "Garoa leve", 53: "Garoa", 55: "Garoa forte", 61: "Chuva leve",
            63: "Chuva", 65: "Chuva forte", 71: "Neve leve", 73: "Neve",
            75: "Neve forte", 80: "Pancadas leves", 81: "Pancadas de chuva",
            82: "Pancadas fortes", 95: "Trovoadas", 96: "Trovoadas com granizo",
            99: "Trovoadas fortes",
        }
        return {
            "cidade": local["name"], "regiao": local.get("admin1", ""),
            "temperatura": round(atual["temperature_2m"]),
            "sensacao": round(atual["apparent_temperature"]),
            "umidade": atual["relative_humidity_2m"], "vento": round(atual["wind_speed_10m"]),
            "codigo": atual["weather_code"],
            "descricao": descricoes.get(atual["weather_code"], "Condição variável"),
            "maxima": round(diario["temperature_2m_max"][0]),
            "minima": round(diario["temperature_2m_min"][0]),
            "chuva": diario["precipitation_probability_max"][0],
        }

    def _info_financas(self):
        resultado = {"dolar": None, "euro": None, "bitcoin": None, "bitcoin_variacao": None}
        erros = []
        try:
            cambio = self._get_json("https://api.frankfurter.dev/v1/latest?base=USD&symbols=BRL,EUR")
            resultado["dolar"] = cambio.get("rates", {}).get("BRL")
            eur_por_usd = cambio.get("rates", {}).get("EUR")
            if resultado["dolar"] and eur_por_usd:
                resultado["euro"] = resultado["dolar"] / eur_por_usd
        except Exception as erro:
            erros.append(f"câmbio: {erro}")
        try:
            cripto = self._get_json(
                "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl&include_24hr_change=true"
            ).get("bitcoin", {})
            resultado["bitcoin"] = cripto.get("brl")
            resultado["bitcoin_variacao"] = cripto.get("brl_24h_change")
        except Exception as erro:
            erros.append(f"bitcoin: {erro}")
        if all(resultado[chave] is None for chave in ("dolar", "euro", "bitcoin")):
            raise RuntimeError("; ".join(erros) or "Nenhuma cotação disponível")
        resultado["avisos"] = erros
        return resultado

    def get_dashboard(self, cidade: str = "Rio de Janeiro"):
        """Retorna dados independentes; uma fonte fora do ar não derruba o painel."""
        cidade = (cidade or "Rio de Janeiro").strip()[:80]
        dados = {"computador": self._info_computador(), "clima": None, "financas": None,
                 "erros": {}, "atualizado_em": datetime.datetime.now().isoformat(timespec="minutes")}
        with ThreadPoolExecutor(max_workers=2) as executor:
            tarefas = {"clima": executor.submit(self._info_clima, cidade),
                       "financas": executor.submit(self._info_financas)}
            for nome, tarefa in tarefas.items():
                try:
                    dados[nome] = tarefa.result()
                except Exception as erro:
                    dados["erros"][nome] = str(erro)
        if dados["erros"]:
            print(f"[NOVA] Dashboard com falhas: {dados['erros']}")
        return self._ok(dados)

    def consultar_agente(self, agente_id: str, pergunta: str, cidade: str = "Rio de Janeiro"):
        """Consulta um especialista com dados atuais apenas de sua área."""
        try:
            from solar_agents import consultar
            return self._ok(consultar(self, agente_id, pergunta, cidade))
        except Exception as erro:
            return self._erro(erro)

    def get_info_computador(self):
        """Leitura local e leve para o monitor ao vivo do System Fetch."""
        try:
            return self._ok(self._info_computador())
        except Exception as erro:
            return self._erro(erro)

    # aPI Key

    def get_chat_local(self):
        try:
            return self._ok(local_chat.settings())
        except Exception as erro:
            return self._erro(erro)

    def configurar_chat_local(self, enabled, model):
        try:
            local_chat.configure(enabled, model)
            return self._ok()
        except Exception as erro:
            return self._erro(erro)

    def listar_modelos_locais(self):
        try:
            return self._ok(local_chat.models())
        except Exception as erro:
            return self._erro(erro)

    def listar_integracoes(self):
        try:
            return self._ok(list_integrations())
        except Exception:
            return self._erro("Não foi possível ler o cadastro de APIs.")

    def salvar_integracao(self, data):
        try:
            save_integration(data)
            return self._ok()
        except ValueError as erro:
            return self._erro(erro)
        except Exception:
            return self._erro("Não foi possível salvar a API.")

    def excluir_integracao(self, identifier):
        try:
            delete_integration(identifier)
            return self._ok()
        except Exception:
            return self._erro("Não foi possível excluir a API.")

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

    # chat

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
            if not api_key and not local_chat.settings()['enabled']:
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

            # nOVA agente: tenta executar uma ação (criar tarefa/lembrete, etc)
            # antes de responder. Se executou, adiciona contexto pro modelo.
            try:
                ctx_agente = self._tentar_acao_agente(sessao_id, mensagem or "")
                if ctx_agente:
                    historico.append({"role": "system", "content": ctx_agente})
            except Exception:
                pass  # best-effort: não deixa o agente quebrar o chat

            # web search: se a pergunta precisa de informação atual, busca
            # no DuckDuckGo e adiciona os resultados como contexto.
            try:
                ctx_web = self._tentar_web_search(mensagem or "")
                if ctx_web:
                    historico.append({"role": "system", "content": ctx_web})
            except Exception:
                pass  # best-effort: não deixa a busca quebrar o chat

            try:
                resposta = chamar_gemini(api_key, historico)
            except Exception as e:
                # erro da API: não salva uma "resposta" de erro no banco,
                # pois poluiria o histórico e confundiria a IA nas próximas
                # mensagens. A mensagem do usuário já foi salva e é válida
                # como contexto.
                return self._erro(f"Falha ao contatar a IA: {e}")

            salvar_mensagem(sessao_id, "assistant", resposta)

            # renomeia a sessão se ainda tiver o título padrão (só na 1ª troca)
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
            if not api_key and not local_chat.settings()['enabled']:
                emit("window.__novaErro && window.__novaErro('API key não configurada.')")
                return self._erro("API key não configurada.")

            historico = carregar_historico(sessao_id)
            historico.append({"role": "user", "content": mensagem})
            salvar_mensagem(sessao_id, "user", mensagem)

            # nOVA agente: tenta executar uma ação (criar tarefa/lembrete, etc)
            # antes de responder. Se executou, adiciona contexto pro modelo.
            # iMPORTANTE: a ação roda antes do streaming começar, pra que a
            # confirmação já venha no stream.
            try:
                ctx_agente = self._tentar_acao_agente(sessao_id, mensagem)
                if ctx_agente:
                    historico.append({"role": "system", "content": ctx_agente})
            except Exception:
                pass  # best-effort: não deixa o agente quebrar o chat

            # web search: se a pergunta precisa de informação atual, busca
            # no DuckDuckGo e adiciona os resultados como contexto.
            try:
                ctx_web = self._tentar_web_search(mensagem)
                if ctx_web:
                    historico.append({"role": "system", "content": ctx_web})
            except Exception:
                pass  # best-effort: não deixa a busca quebrar o chat

            resposta_completa = ""
            try:
                for chunk in chamar_gemini_stream(api_key, historico):
                    resposta_completa += chunk
                    emit(f"window.__novaChunk && window.__novaChunk({json.dumps(chunk)});")
            except Exception as e:
                emit(f"window.__novaErro && window.__novaErro({json.dumps(str(e))});")
                # não salva resposta parcial no banco, poluiria o histórico
                return self._erro(f"Falha ao contatar a IA: {e}")

            salvar_mensagem(sessao_id, "assistant", resposta_completa)
            self._tentar_renomear_sessao(sessao_id, mensagem)

            emit("window.__novaFim && window.__novaFim();")
            return self._ok({"resposta": resposta_completa})
        except Exception as e:
            return self._erro(e)

    def _transcrever_audio(self, api_key: str, audio_b64: str, mime_type: str = "audio/wav") -> str:
        """Converte a gravação em texto para alimentar o chat e ações do agente."""
        historico = [{
            "role": "user",
            "content": [
                {"type": "audio_data", "mime_type": mime_type, "data": audio_b64},
                {
                    "type": "text",
                    "text": (
                        "Transcreva exatamente o que a pessoa falou neste áudio, em português brasileiro. "
                        "Responda somente com a transcrição literal, sem aspas, explicações ou pontuação extra."
                    ),
                },
            ],
        }]
        texto = chamar_gemini_multimodal(api_key, historico, max_tokens=256)
        return " ".join(texto.split()).strip()

    def enviar_audio(self, sessao_id: int, audio_b64: str, mime_type: str = "audio/wav"):
        """Recebe uma gravação curta, transcreve, executa ações do agente e responde em texto."""
        try:
            api_key = carregar_key()
            if not api_key:
                return self._erro("API key do Gemini não configurada.")
            if not audio_b64:
                return self._erro("Nenhum áudio recebido.")
            if "," in audio_b64:
                cabecalho, audio_b64 = audio_b64.split(",", 1)
                if ":" in cabecalho:
                    mime_type = cabecalho.split(":", 1)[1].split(";", 1)[0]
            tamanho = len(base64.b64decode(audio_b64, validate=True))
            if tamanho > 15 * 1024 * 1024:
                return self._erro("A gravação passou de 15 MB. Grave uma mensagem mais curta.")

            transcricao = self._transcrever_audio(api_key, audio_b64, mime_type)
            if not transcricao or len(transcricao) < 2:
                return self._erro("Não consegui entender o áudio. Fale mais perto do microfone e tente de novo.")

            historico = carregar_historico(sessao_id)
            historico.append({"role": "user", "content": transcricao})
            salvar_mensagem(sessao_id, "user", f" {transcricao}")

            try:
                ctx_agente = self._tentar_acao_agente(sessao_id, transcricao)
                if ctx_agente:
                    historico.append({"role": "system", "content": ctx_agente})
            except Exception:
                pass

            try:
                ctx_web = self._tentar_web_search(transcricao)
                if ctx_web:
                    historico.append({"role": "system", "content": ctx_web})
            except Exception:
                pass

            resposta = chamar_gemini(api_key, historico)
            salvar_mensagem(sessao_id, "assistant", resposta)
            self._tentar_renomear_sessao(sessao_id, transcricao)
            return self._ok({"tipo": "texto", "resposta": resposta, "transcricao": transcricao})
        except Exception as e:
            return self._erro(f"Falha na conversa por voz: {e}")

    def _iniciar_gravacao_sounddevice(self):
        import sounddevice as sd
        frames = []

        def callback(indata, frame_count, time_info, status):
            if status:
                print(f"[NOVA] Microfone: {status}")
            frames.append(bytes(indata))

        stream = sd.RawInputStream(
            samplerate=16000, channels=1, dtype="int16",
            blocksize=2048, callback=callback,
        )
        stream.start()
        self._gravacao = {
            "tipo": "sounddevice", "stream": stream,
            "frames": frames, "inicio": time.time(),
        }
        return self._ok({"backend": "sounddevice"})

    def _iniciar_gravacao_arecord(self):
        if not (sys.platform.startswith("linux") and shutil.which("arecord")):
            raise RuntimeError("arecord não está disponível neste sistema.")
        arquivo = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        caminho = arquivo.name
        arquivo.close()
        processo = subprocess.Popen(
            ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "wav", caminho],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        time.sleep(0.15)
        if processo.poll() is not None:
            erro = processo.stderr.read().decode("utf-8", errors="replace").strip()
            try:
                os.unlink(caminho)
            except OSError:
                pass
            raise RuntimeError(erro or "Nenhum microfone foi encontrado pelo sistema.")
        self._gravacao = {
            "tipo": "arecord", "processo": processo,
            "caminho": caminho, "inicio": time.time(),
        }
        return self._ok({"backend": "arecord"})

    def _parar_processo_arecord(self, processo):
        if sys.platform == "win32":
            processo.terminate()
        else:
            processo.send_signal(signal.SIGINT)
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait()

    def iniciar_gravacao_nativa(self):
        """Inicia captura pelo sistema, sem depender das permissões do WebView."""
        with self._gravacao_lock:
            if self._gravacao:
                return self._erro("Já existe uma gravação em andamento.")
            erros = []
            for iniciar in (self._iniciar_gravacao_sounddevice, self._iniciar_gravacao_arecord):
                try:
                    return iniciar()
                except ImportError:
                    erros.append("sounddevice não instalado")
                except Exception as e:
                    erros.append(str(e))
                    self._gravacao = None
            dica = "Instale com: pip install sounddevice"
            if sys.platform.startswith("linux"):
                dica += " (ou verifique se o microfone está conectado e o arecord funciona)"
            return self._erro(f"Não foi possível abrir o microfone. {' | '.join(erros)}. {dica}")

    def parar_gravacao_nativa(self, sessao_id: int):
        with self._gravacao_lock:
            gravacao = self._gravacao
            self._gravacao = None
        if not gravacao:
            return self._erro("Nenhuma gravação em andamento.")
        try:
            duracao = time.time() - gravacao["inicio"]
            if gravacao["tipo"] == "sounddevice":
                stream = gravacao["stream"]
                stream.stop(); stream.close()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as arquivo:
                    caminho = arquivo.name
                with wave.open(caminho, "wb") as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
                    wav.writeframes(b"".join(gravacao["frames"]))
            else:
                processo = gravacao["processo"]
                self._parar_processo_arecord(processo)
                caminho = gravacao["caminho"]
                if processo.returncode not in (0, -2, -15) and not os.path.exists(caminho):
                    erro = processo.stderr.read().decode("utf-8", errors="replace").strip()
                    raise RuntimeError(erro or "O gravador do sistema falhou.")
            if duracao < 0.5 or not os.path.exists(caminho) or os.path.getsize(caminho) < 100:
                raise RuntimeError("A gravação ficou vazia ou curta demais.")
            with open(caminho, "rb") as arquivo:
                audio_b64 = base64.b64encode(arquivo.read()).decode("ascii")
            return self.enviar_audio(sessao_id, audio_b64, "audio/wav")
        except Exception as e:
            return self._erro(f"Falha ao finalizar a gravação: {e}")
        finally:
            if "caminho" in locals() and os.path.exists(caminho):
                try:
                    os.unlink(caminho)
                except OSError:
                    pass

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

            resposta = chamar_gemini_simples(system, mensagem)
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

            # executa a ação
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
                return f"[SISTEMA, Ação executada automaticamente: criei a tarefa #{tid} '{titulo}' com prioridade {prioridade}{prazo_txt}. Confirme ao usuário de forma natural, mencionando a tarefa.]"

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
                return f"[SISTEMA, Ação executada automaticamente: criei o lembrete #{lid} '{titulo}' para {data_hora}{rep_txt}. Confirme ao usuário de forma natural, mencionando o lembrete.]"

            if acao == "listar_tarefas":
                tarefas = listar_tarefas(status="pendente")
                if not tarefas:
                    return "[SISTEMA, Ação executada: o usuário pediu suas tarefas pendentes. Não há nenhuma. Avise.]"
                lista = "; ".join(f"{t['titulo']} ({t['prioridade']})" for t in tarefas[:10])
                return f"[SISTEMA, Ação executada: o usuário pediu suas tarefas pendentes. Encontrei {len(tarefas)}: {lista}. Apresente ao usuário de forma organizada.]"

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
            # 1. Classifica + extrai query de busca (1 chamada LLM)
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
- Pedido de ação (criar tarefa/lembrete), outro sistema cuida disso
- Conhecimento histórico, ciência, matemática

Responda APENAS com um JSON válido, sem markdown:
{"buscar": true, "query": "search query curta em inglês"}
ou
{"buscar": false, "query": ""}"""

            resposta = chamar_gemini_simples(system, mensagem)
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

            # 2. Faz a busca no DuckDuckGo
            # prioriza o pacote novo 'ddgs' (o antigo 'duckduckgo_search' v8
            # está deprecated e retorna 0 resultados).
            DDGS = None
            try:
                from ddgs import DDGS
            except ImportError:
                try:
                    from duckduckgo_search import DDGS
                except ImportError:
                    return None  # busca não disponível, ignora silenciosamente

            # aPI nova (ddgs / duckduckgo_search v6+): sem context manager
            raw = None
            try:
                ddgs = DDGS()
                raw = list(ddgs.text(query, max_results=4))
            except Exception:
                # fallback: context manager (v5 e anteriores)
                try:
                    with DDGS() as ddgs:
                        raw = list(ddgs.text(query, max_results=4))
                except Exception:
                    return None

            if not raw:
                return None

            # 3. Formata os resultados
            # o campo pode ser 'body', 'snippet' ou 'content' dependendo da versão
            linhas = []
            for i, r in enumerate(raw[:4], 1):
                titulo = r.get("title", "Sem título")
                corpo = r.get("body") or r.get("snippet") or r.get("content") or ""
                url = r.get("href") or r.get("url") or r.get("link") or ""
                linhas.append(f"[{i}] {titulo}\n{corpo}\nFonte: {url}")

            formatado = "\n\n".join(linhas)

            return (
                f"[SISTEMA, Resultados de busca web para '{query}':\n\n"
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
        simplesmente continua com o nome padrão, não derruba o chat.
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
            titulo = chamar_gemini_simples(system, primeira_msg[:500]).strip()
            # limpa aspas e eventuais aspas envolvendo o título
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
                    resposta_texto = " Prontinho! Editei a imagem como você pediu."
                else:
                    resposta_texto = f" Prontinho! Apliquei: {operacao.replace('_', ' ')}."

                salvar_mensagem(sessao_id, "user", mensagem or "[imagem enviada]")
                salvar_mensagem(sessao_id, "assistant", resposta_texto)

                return self._ok({
                    "tipo": "imagem",
                    "resposta": resposta_texto,
                    "imagem_base64": resultado["data"]["base64"],
                    "caminho": resultado["data"]["caminho"]
                })
            else:
                # não foi reconhecido como pedido de edição, conversa normal com visão
                return self.enviar_mensagem(sessao_id, mensagem, imagem_b64)

        except Exception as e:
            return self._erro(e)

    def get_resumo_matinal(self):
        try:
            return self._ok({"resumo": gerar_resumo_matinal()})
        except Exception as e:
            return self._erro(e)

    # tarefas

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

    # projetos

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

    # lembretes

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

    # hábitos

    def get_habitos(self):
        try:
            return self._ok(listar_habitos())
        except Exception as e:
            return self._erro(e)

    def criar_habito(self, nome: str, icone: str = "", cor: str = "#7c6fff"):
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

    # foco

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

    # resumo

    def get_resumo(self):
        try:
            return self._ok(resumo_matinal())
        except Exception as e:
            return self._erro(e)

    # imagens

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
- instagram: redimensiona para um formato do Instagram. params: {{"formato": "..."}}, exatamente uma destas: {formatos}
- gerar_ia: QUALQUER OUTRO pedido de edição que não se encaixe acima, trocar cenário/fundo por algo específico, adicionar ou remover objetos, mudar roupas, mudar estilo artístico, mudar clima/iluminação, transformações criativas em geral.
  params: {{"prompt": "...", "forca": 0.55}}
  - "prompt": traduza e reescreva o pedido do usuário como um prompt CURTO e DESCRITIVO em INGLÊS, no estilo usado para Stable Diffusion (ex: "a photo of a person wearing a formal business suit, professional lighting").
  - "forca": de 0.3 a 0.8, use valores baixos (0.3-0.4) para mudanças sutis (cor, iluminação, pequenos ajustes) e valores altos (0.6-0.8) para mudanças grandes (trocar cenário inteiro, trocar roupa, mudar estilo).

Responda APENAS com um JSON válido, sem texto antes ou depois, sem markdown."""

            resposta = chamar_gemini_simples(system, instrucao or "melhore essa imagem")

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

            prompt_en = chamar_gemini_simples(system, prompt).strip()

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
        
            # tema (salvar/carregar)
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
