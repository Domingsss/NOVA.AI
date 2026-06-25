import os
import sys
import pathlib
import webview
from database import inicializar
from rotinas import iniciar_rotinas
from api import API

# ─── ENCONTRAR A PASTA "ui" AUTOMATICAMENTE ──────────────────────────────────

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CANDIDATOS = [
    os.path.join(BASE_DIR, "ui", "index.html"),
    os.path.join(BASE_DIR, "..", "ui", "index.html"),
    os.path.join(BASE_DIR, "..", "..", "ui", "index.html"),
]

HTML_FILE = None
for caminho in CANDIDATOS:
    caminho_abs = os.path.abspath(caminho)
    if os.path.exists(caminho_abs):
        HTML_FILE = caminho_abs
        break

if HTML_FILE is None:
    print("\n❌ Não encontrei a pasta 'ui' com o index.html em nenhum desses locais:")
    for c in CANDIDATOS:
        print(f"   - {os.path.abspath(c)}")
    print(f"\nBASE_DIR atual: {BASE_DIR}")
    sys.exit(1)

# Converte para uma URI file:// correta, lidando com espaços e caracteres especiais
HTML_URI = pathlib.Path(HTML_FILE).resolve().as_uri()
print(f"✓ Carregando: {HTML_URI}")

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    inicializar()
    iniciar_rotinas()

    api = API()

    window = webview.create_window(
        title="NOVA — Assistente Pessoal",
        url=HTML_URI,
        js_api=api,
        width=1200,
        height=750,
        min_size=(800, 550),
        background_color="#0a0a0f",
        text_select=False,
    )

    webview.start(debug=False)