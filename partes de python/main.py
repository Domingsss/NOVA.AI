import os
import sys
import webview
from database import inicializar
from rotinas import iniciar_rotinas
from api import API

# ─── CAMINHOS ─────────────────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UI_DIR   = os.path.join(BASE_DIR, "ui")
HTML_FILE = os.path.join(UI_DIR, "index.html")

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    inicializar()
    iniciar_rotinas()

    api = API()

    window = webview.create_window(
        title="NOVA",
        url=HTML_FILE,
        js_api=api,
        width=1200,
        height=750,
        min_size=(800, 550),
        background_color="#0a0a0f",
        text_select=False,
    )

    webview.start(debug=False)