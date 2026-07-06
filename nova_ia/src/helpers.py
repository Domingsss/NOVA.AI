import os
import json
from groq import Groq
from config import API_KEY_FILE, SYSTEM_PROMPT, MODEL
from colors import PURPLE, TEAL


def salvar_key(key: str):
    with open(API_KEY_FILE, "w") as f:
        json.dump({"api_key": key}, f)


def carregar_key() -> str:
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r") as f:
            data = json.load(f)
            return data.get("api_key", "")
    return ""


def chamar_groq(api_key: str, historico: list) -> str:
    """Chama o Groq com histórico.

    Levanta exceção em caso de erro — NÃO retorna string de erro.
    Quem chama é responsável por tratar.
    """
    if not api_key:
        raise RuntimeError("API key não configurada.")
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + historico
    )
    return response.choices[0].message.content


def chamar_groq_stream(api_key: str, historico: list):
    """Chama o Groq com streaming. Gera (yield) cada pedaço de texto conforme
    chega da API, em vez de esperar a resposta completa.

    Levanta exceção em caso de erro — NÃO retorna string de erro.
    """
    if not api_key:
        raise RuntimeError("API key não configurada.")
    client = Groq(api_key=api_key)
    stream = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + historico,
        stream=True
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        texto = getattr(delta, "content", None)
        if texto:
            yield texto


def chamar_groq_simples(system_prompt: str, mensagem: str) -> str:
    """Chamada simples ao Groq sem histórico, usada para classificação/interpretação.

    Levanta exceção em caso de erro — NÃO retorna string de erro.
    """
    api_key = carregar_key()
    if not api_key:
        raise RuntimeError("API key não configurada.")
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=300,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": mensagem}
        ]
    )
    return response.choices[0].message.content


def configurar_key() -> str:
    key = input("  Cole sua Groq API key: ").strip()
    if key:
        salvar_key(key)
        print(f"\n  ✓ Key salva!\n")
    return key