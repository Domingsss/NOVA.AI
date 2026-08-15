import base64
import json
import os
import random
import time
import urllib.error
import urllib.request

from config import API_KEY_FILE, AUDIO_MODELS, FALLBACK_MODEL, GEMINI_API_URL, MODEL, SYSTEM_PROMPT


def salvar_key(key: str):
    with open(API_KEY_FILE, "w", encoding="utf-8") as arquivo:
        json.dump({"api_key": key}, arquivo)


def carregar_key() -> str:
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r", encoding="utf-8") as arquivo:
            data = json.load(arquivo)
            return data.get("api_key", "")
    return ""


def _parte_gemini(parte):
    """Converte uma parte no formato OpenAI usado pela interface para Gemini."""
    if isinstance(parte, str):
        return {"text": parte}

    tipo = parte.get("type")
    if tipo == "text":
        return {"text": parte.get("text", "")}

    if tipo == "image_url":
        url = parte.get("image_url", {}).get("url", "")
        if not url.startswith("data:") or "," not in url:
            raise ValueError("A imagem precisa estar em formato base64.")
        cabecalho, dados = url.split(",", 1)
        mime_type = cabecalho[5:].split(";", 1)[0] or "image/jpeg"
        # Valida o base64 antes de enviá-lo e normaliza sua representação.
        dados = base64.b64encode(base64.b64decode(dados, validate=True)).decode("ascii")
        return {"inlineData": {"mimeType": mime_type, "data": dados}}

    if tipo == "audio_data":
        mime_type = parte.get("mime_type", "audio/wav")
        dados = parte.get("data", "")
        dados = base64.b64encode(base64.b64decode(dados, validate=True)).decode("ascii")
        return {"inlineData": {"mimeType": mime_type, "data": dados}}

    raise ValueError(f"Tipo de conteúdo não suportado: {tipo}")


def _preparar_conversa(historico: list, system_prompt: str = SYSTEM_PROMPT):
    instrucoes = [system_prompt]
    contents = []

    for mensagem in historico:
        role = mensagem.get("role", "user")
        conteudo = mensagem.get("content", "")

        # O Gemini recebe instruções de sistema separadamente do histórico.
        if role == "system":
            if isinstance(conteudo, str) and conteudo.strip():
                instrucoes.append(conteudo)
            continue

        partes_originais = conteudo if isinstance(conteudo, list) else [conteudo]
        partes = [_parte_gemini(parte) for parte in partes_originais]
        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": partes,
        })

    return contents, "\n\n".join(instrucoes)


def _payload(historico: list, system_prompt: str, max_tokens: int):
    contents, instrucao = _preparar_conversa(historico, system_prompt)
    return {
        "systemInstruction": {"parts": [{"text": instrucao}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens},
    }


def _requisicao(api_key: str, sufixo: str, payload: dict, model: str = MODEL):
    if not api_key:
        raise RuntimeError("API key do Gemini não configurada.")

    url = f"{GEMINI_API_URL}/models/{model}:{sufixo}"
    dados = json.dumps(payload).encode("utf-8")
    return urllib.request.urlopen(
        urllib.request.Request(
            url,
            data=dados,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        ),
        timeout=90,
    )


def _requisicao_resiliente(api_key: str, sufixo: str, payload: dict):
    """Repete erros transitórios e troca para o Flash-Lite se faltar capacidade."""
    ultimo_erro = None
    for indice_modelo, model in enumerate(dict.fromkeys((MODEL, FALLBACK_MODEL))):
        # Não prende a interface insistindo num modelo sabidamente congestionado.
        total_tentativas = 1 if indice_modelo == 0 else 3
        if indice_modelo > 0:
            print(f"[NOVA] Gemini principal indisponível; usando {model}.")
        for tentativa in range(total_tentativas):
            try:
                return _requisicao(api_key, sufixo, payload, model)
            except urllib.error.HTTPError as erro:
                ultimo_erro = erro
                if erro.code not in (408, 429, 500, 502, 503, 504):
                    raise
                # 1s, 2s e um pequeno jitter para evitar nova colisão de tráfego.
                if tentativa < total_tentativas - 1:
                    time.sleep((2 ** tentativa) + random.uniform(0.1, 0.5))
            except urllib.error.URLError as erro:
                ultimo_erro = erro
                if tentativa < total_tentativas - 1:
                    time.sleep((2 ** tentativa) + random.uniform(0.1, 0.5))
    if ultimo_erro:
        raise ultimo_erro
    raise RuntimeError("Não foi possível iniciar a requisição ao Gemini.")


def _texto_resposta(resposta: dict) -> str:
    candidatos = resposta.get("candidates") or []
    if not candidatos:
        motivo = resposta.get("promptFeedback", {}).get("blockReason")
        raise RuntimeError(f"O Gemini não retornou uma resposta{f' ({motivo})' if motivo else ''}.")

    partes = candidatos[0].get("content", {}).get("parts", [])
    texto = "".join(parte.get("text", "") for parte in partes if "text" in parte)
    if not texto:
        raise RuntimeError("O Gemini retornou uma resposta vazia.")
    return texto


def _traduzir_erro_api(erro: urllib.error.HTTPError) -> RuntimeError:
    try:
        corpo = json.loads(erro.read().decode("utf-8"))
        mensagem = corpo.get("error", {}).get("message") or str(erro)
    except Exception:
        mensagem = str(erro)
    return RuntimeError(f"Gemini API: {mensagem}")


def chamar_gemini_multimodal(api_key: str, historico: list, max_tokens: int = 512) -> str:
    """Chama o Gemini com conteúdo multimodal (áudio/imagem), tentando modelos compatíveis."""
    payload = _payload(historico, SYSTEM_PROMPT, max_tokens)
    ultimo_erro = None
    modelos = tuple(dict.fromkeys(AUDIO_MODELS))
    for indice, model in enumerate(modelos):
        tentativas = 3 if indice > 0 else 2
        for tentativa in range(tentativas):
            try:
                with _requisicao(api_key, "generateContent", payload, model) as resposta:
                    return _texto_resposta(json.load(resposta))
            except urllib.error.HTTPError as erro:
                ultimo_erro = erro
                # Modelo pode não aceitar áudio — tenta o próximo.
                if erro.code == 400:
                    break
                if erro.code not in (408, 429, 500, 502, 503, 504):
                    raise _traduzir_erro_api(erro) from erro
                if tentativa < tentativas - 1:
                    time.sleep((2 ** tentativa) + random.uniform(0.1, 0.5))
            except urllib.error.URLError as erro:
                ultimo_erro = erro
                if tentativa < tentativas - 1:
                    time.sleep((2 ** tentativa) + random.uniform(0.1, 0.5))
        if indice == 0 and len(modelos) > 1:
            print(f"[NOVA] Modelo principal sem suporte a áudio; tentando {modelos[1]}.")
    if isinstance(ultimo_erro, urllib.error.HTTPError):
        raise _traduzir_erro_api(ultimo_erro) from ultimo_erro
    if ultimo_erro:
        raise RuntimeError(f"Não foi possível conectar ao Gemini: {ultimo_erro}") from ultimo_erro
    raise RuntimeError("Nenhum modelo disponível aceitou o áudio enviado.")


def chamar_gemini(api_key: str, historico: list) -> str:
    """Chama o Gemini com o histórico completo da conversa."""
    try:
        with _requisicao_resiliente(api_key, "generateContent", _payload(historico, SYSTEM_PROMPT, 1024)) as resposta:
            return _texto_resposta(json.load(resposta))
    except urllib.error.HTTPError as erro:
        raise _traduzir_erro_api(erro) from erro
    except urllib.error.URLError as erro:
        raise RuntimeError(f"Não foi possível conectar ao Gemini: {erro.reason}") from erro


def chamar_gemini_stream(api_key: str, historico: list):
    """Gera a resposta do Gemini em streaming, um trecho de texto por vez."""
    try:
        with _requisicao_resiliente(
            api_key,
            "streamGenerateContent?alt=sse",
            _payload(historico, SYSTEM_PROMPT, 1024),
        ) as resposta:
            for linha in resposta:
                linha = linha.decode("utf-8").strip()
                if not linha.startswith("data:"):
                    continue
                evento = json.loads(linha[5:].strip())
                candidatos = evento.get("candidates") or []
                if not candidatos:
                    continue
                for parte in candidatos[0].get("content", {}).get("parts", []):
                    texto = parte.get("text")
                    if texto:
                        yield texto
    except urllib.error.HTTPError as erro:
        raise _traduzir_erro_api(erro) from erro
    except urllib.error.URLError as erro:
        raise RuntimeError(f"Não foi possível conectar ao Gemini: {erro.reason}") from erro


def chamar_gemini_simples(system_prompt: str, mensagem: str) -> str:
    """Faz uma chamada curta usada por classificadores e interpretadores."""
    api_key = carregar_key()
    historico = [{"role": "user", "content": mensagem}]
    try:
        # Classificações internas priorizam latência e usam diretamente o Lite.
        with _requisicao(api_key, "generateContent", _payload(historico, system_prompt, 300), FALLBACK_MODEL) as resposta:
            return _texto_resposta(json.load(resposta))
    except urllib.error.HTTPError as erro:
        raise _traduzir_erro_api(erro) from erro
    except urllib.error.URLError as erro:
        raise RuntimeError(f"Não foi possível conectar ao Gemini: {erro.reason}") from erro


def configurar_key() -> str:
    key = input("  Cole sua Gemini API key: ").strip()
    if key:
        salvar_key(key)
        print("\n  ✓ Key salva!\n")
    return key
