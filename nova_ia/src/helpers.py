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
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + historico
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[Erro: {str(e)}]"
 
def chamar_groq_simples(system_prompt: str, mensagem: str) -> str:
    """Chamada simples ao Groq sem histórico, usada para classificação/interpretação."""
    api_key = carregar_key()
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
 