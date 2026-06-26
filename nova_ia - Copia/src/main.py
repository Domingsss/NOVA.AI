# src/main.py
from webview_api import Api
import os
import sys

# Adiciona a pasta src no caminho para conseguir importar o api.py
sys.path.append(os.path.dirname(__file__))
from api import Api

def main():
    api = Api()
    
    # Pega o caminho absoluto do index.html que está na pasta ui
    caminho_html = os.path.join(os.path.dirname(__file__), '..', 'ui', 'index.html')
    
    # Cria a janela do pywebview
    window = webview.create_window(
        title="NOVA — Assistente Pessoal",
        url=caminho_html,
        js_api=api,       # Liga o JS no Python
        width=1100,
        height=700,
        min_size=(800, 500),
        text_select=False   
    )
    
    webview.start(debug=True) # Mude debug para False quando for distribuir

if __name__ == "__main__":
    # Garante que as pastas de dados existam
    base_dir = os.path.dirname(os.path.dirname(__file__))
    os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'assets', 'imagens_editadas'), exist_ok=True)
    
    main()