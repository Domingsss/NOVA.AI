# src/main.py
import os
import hashlib
import shutil
import sys
import traceback
import webview

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SRC_DIR)

from api import API
from database import inicializar
from rotinas import iniciar_rotinas


def main():
    print("[NOVA] Iniciando...")

    # Banco de dados
    try:
        inicializar()
        print("[NOVA] Banco OK")
    except Exception as e:
        print(f"[NOVA] Aviso no banco: {e}")
        traceback.print_exc()

    # Rotinas em background (monitor de lembretes, etc.)
    try:
        iniciar_rotinas()
        print("[NOVA] Rotinas OK")
    except Exception as e:
        print(f"[NOVA] Aviso nas rotinas: {e}")
        traceback.print_exc()

    api = API()
    print("[NOVA] API OK")

    # Caminho absoluto do index.html (está em src/ui/index.html)
    caminho_html = os.path.join(SRC_DIR, 'ui', 'index.html')
    print(f"[NOVA] HTML: {caminho_html}")
    print(f"[NOVA] Arquivo existe: {os.path.exists(caminho_html)}")

    # WebView2 keeps the same local origin between launches. Version the entry
    # page so an older cached index cannot hide a newly installed interface.
    with open(caminho_html, 'rb') as pagina:
        versao_ui = hashlib.sha256(pagina.read()).hexdigest()[:16]

    # Cria a janela do pywebview
    webview.create_window(
        title="NOVA — Assistente Pessoal",
        url=f"{caminho_html}?v={versao_ui}",
        js_api=api,       # Liga o JS no Python
        width=1100,
        height=700,
        min_size=(800, 500),
        text_select=False
    )

    print("[NOVA] Abrindo janela...")
    # O microfone via getUserMedia exige um contexto HTTP local e um motor web
    # moderno. No Windows, força WebView2 (Edge Chromium) em vez do MSHTML.
    gui = "edgechromium" if sys.platform == "win32" else None
    storage_dir = os.path.join(os.path.dirname(SRC_DIR), "data", "webview")
    os.makedirs(storage_dir, exist_ok=True)
    # O WebKitGTK pode reutilizar JS/CSS antigos mesmo depois de reiniciar o app.
    # Limpa somente os arquivos temporários de cache; localStorage e preferências
    # da NOVA continuam preservados no restante de storage_dir.
    cache_dir = os.path.join(storage_dir, "cache")
    if os.path.isdir(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print("[NOVA] Cache visual atualizado")
        except OSError as erro:
            print(f"[NOVA] Aviso ao limpar cache visual: {erro}")
    webview.start(
        debug=False,
        gui=gui,
        http_server=True,
        private_mode=False,
        storage_path=storage_dir,
    )
    print("[NOVA] Janela fechada. Fim.")


if __name__ == "__main__":
    # Garante que as pastas de dados existem
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'assets', 'imagens_editadas'), exist_ok=True)

    try:
        main()
    except Exception:
        print("\n" + "=" * 60)
        print("ERRO FATAL NA NOVA:")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        input("\nPressione Enter para fechar...")
