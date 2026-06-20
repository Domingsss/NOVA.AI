import os
from groq import Groq
from config import API_KEY_FILE, SYSTEM_PROMPT, MODEL
from colors import PURPLE, TEAL
import json

def salvar_key(key: str):
    with open(API_KEY_FILE, "w") as f:
        f.write(key.strip())

def carregar_key() -> str:
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r") as f:
            return f.read().strip()
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

def configurar_key() -> str:
    print(f"\n  Onde pegar sua key grátis:")
    print(f"  1. Acesse console.groq.com")
    print(f"  2. Faça login (só precisa de e-mail)")
    print(f"  3. Vá em API Keys → Create API Key\n")
    key = input(f"  Cole sua Groq API key: ").strip()
    if key:
        salvar_key(key)
        print(f"\n  ✓ Key salva! Não precisa digitar de novo.\n")
    return keys