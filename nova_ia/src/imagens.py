import os
import sys
import threading
import urllib.request
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import io


# caminhos dos modelos


if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

OUTPUT_DIR = os.path.join(BASE_DIR, "imagens_editadas")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# rEMOVER FUNDO (rembg)


def remover_fundo(caminho_entrada: str, caminho_saida: str = None) -> str:
    """Remove o fundo de uma imagem usando rembg."""
    try:
        from rembg import remove

        with open(caminho_entrada, "rb") as f:
            dados = f.read()

        resultado = remove(dados)

        if not caminho_saida:
            nome = os.path.splitext(os.path.basename(caminho_entrada))[0]
            caminho_saida = os.path.join(OUTPUT_DIR, f"{nome}_sem_fundo.png")

        with open(caminho_saida, "wb") as f:
            f.write(resultado)

        return caminho_saida
    except Exception as e:
        raise RuntimeError(f"Erro ao remover fundo: {e}")



# mELHORAR QUALIDADE (PIL, sem modelo pesado)


def melhorar_qualidade(caminho_entrada: str, caminho_saida: str = None,
                        nitidez: float = 2.0, brilho: float = 1.1,
                        contraste: float = 1.2, cor: float = 1.1) -> str:
    """Melhora qualidade da imagem com ajustes de nitidez, brilho, contraste e cor."""
    try:
        img = Image.open(caminho_entrada).convert("RGB")

        img = ImageEnhance.Sharpness(img).enhance(nitidez)
        img = ImageEnhance.Brightness(img).enhance(brilho)
        img = ImageEnhance.Contrast(img).enhance(contraste)
        img = ImageEnhance.Color(img).enhance(cor)

        # leve desfoque pra suavizar ruído antes de nitidez final
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))

        if not caminho_saida:
            nome = os.path.splitext(os.path.basename(caminho_entrada))[0]
            caminho_saida = os.path.join(OUTPUT_DIR, f"{nome}_melhorada.jpg")

        img.save(caminho_saida, quality=95)
        return caminho_saida
    except Exception as e:
        raise RuntimeError(f"Erro ao melhorar qualidade: {e}")



# aUMENTAR RESOLUÇÃO (Real-ESRGAN via onnxruntime)


ESRGAN_URL  = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
ESRGAN_MODEL = os.path.join(MODELS_DIR, "realesrgan.onnx")

# fallback leve: upscale com PIL (Lanczos)
def aumentar_resolucao(caminho_entrada: str, escala: int = 2,
                        caminho_saida: str = None) -> str:
    """Aumenta resolução da imagem. Usa ONNX se disponível, senão PIL Lanczos."""
    try:
        img = Image.open(caminho_entrada).convert("RGB")
        w, h = img.size
        nova_w, nova_h = w * escala, h * escala

        # tenta usar onnxruntime com modelo se disponível
        if os.path.exists(ESRGAN_MODEL):
            try:
                import onnxruntime as ort
                session = ort.InferenceSession(ESRGAN_MODEL,
                    providers=["CPUExecutionProvider"])
                arr = np.array(img).astype(np.float32) / 255.0
                arr = arr.transpose(2, 0, 1)[np.newaxis, :]
                out = session.run(None, {session.get_inputs()[0].name: arr})[0]
                out = (out[0].transpose(1, 2, 0) * 255).clip(0, 255).astype(np.uint8)
                img = Image.fromarray(out)
            except Exception:
                img = img.resize((nova_w, nova_h), Image.LANCZOS)
        else:
            img = img.resize((nova_w, nova_h), Image.LANCZOS)

        if not caminho_saida:
            nome = os.path.splitext(os.path.basename(caminho_entrada))[0]
            caminho_saida = os.path.join(OUTPUT_DIR, f"{nome}_hd.jpg")

        img.save(caminho_saida, quality=95)
        return caminho_saida
    except Exception as e:
        raise RuntimeError(f"Erro ao aumentar resolução: {e}")



# aJUSTES INSTAGRAM (redimensionar + otimizar)


FORMATOS_INSTAGRAM = {
    "Feed quadrado (1:1)":   (1080, 1080),
    "Feed retrato (4:5)":    (1080, 1350),
    "Feed paisagem (1.91:1)":(1080,  566),
    "Stories (9:16)":        (1080, 1920),
    "Reels (9:16)":          (1080, 1920),
}

def otimizar_instagram(caminho_entrada: str, formato: str = "Feed quadrado (1:1)",
                        caminho_saida: str = None) -> str:
    """Redimensiona e otimiza imagem para o Instagram."""
    try:
        img = Image.open(caminho_entrada).convert("RGB")
        alvo_w, alvo_h = FORMATOS_INSTAGRAM.get(formato, (1080, 1080))

        # crop centralizado mantendo proporção
        ratio_alvo = alvo_w / alvo_h
        ratio_img  = img.width / img.height

        if ratio_img > ratio_alvo:
            nova_h = img.height
            nova_w = int(nova_h * ratio_alvo)
        else:
            nova_w = img.width
            nova_h = int(nova_w / ratio_alvo)

        left = (img.width  - nova_w) // 2
        top  = (img.height - nova_h) // 2
        img  = img.crop((left, top, left + nova_w, top + nova_h))
        img  = img.resize((alvo_w, alvo_h), Image.LANCZOS)

        if not caminho_saida:
            nome = os.path.splitext(os.path.basename(caminho_entrada))[0]
            fmt  = formato.split("(")[0].strip().replace(" ", "_").lower()
            caminho_saida = os.path.join(OUTPUT_DIR, f"{nome}_{fmt}.jpg")

        img.save(caminho_saida, quality=92, optimize=True)
        return caminho_saida
    except Exception as e:
        raise RuntimeError(f"Erro ao otimizar para Instagram: {e}")



# trocar cor de fundo


def trocar_fundo_cor(caminho_entrada: str, cor: tuple = (255, 255, 255),
                      caminho_saida: str = None) -> str:
    """Remove o fundo e coloca uma cor sólida no lugar."""
    try:
        from rembg import remove

        with open(caminho_entrada, "rb") as f:
            resultado = remove(f.read())

        img_sem_fundo = Image.open(io.BytesIO(resultado)).convert("RGBA")
        fundo = Image.new("RGBA", img_sem_fundo.size, cor + (255,))
        fundo.paste(img_sem_fundo, mask=img_sem_fundo.split()[3])
        final = fundo.convert("RGB")

        if not caminho_saida:
            nome = os.path.splitext(os.path.basename(caminho_entrada))[0]
            caminho_saida = os.path.join(OUTPUT_DIR, f"{nome}_novo_fundo.jpg")

        final.save(caminho_saida, quality=95)
        return caminho_saida
    except Exception as e:
        raise RuntimeError(f"Erro ao trocar fundo: {e}")



# utilitários


def listar_editadas() -> list:
    """Lista todas as imagens editadas na pasta de saída."""
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    if not os.path.exists(OUTPUT_DIR):
        return []
    return [
        os.path.join(OUTPUT_DIR, f)
        for f in sorted(os.listdir(OUTPUT_DIR), reverse=True)
        if os.path.splitext(f)[1].lower() in exts
    ]

def abrir_pasta_editadas():
    """Abre a pasta de imagens editadas no Explorer."""
    os.startfile(OUTPUT_DIR)