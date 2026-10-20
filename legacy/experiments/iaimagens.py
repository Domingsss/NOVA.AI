import os
import time
import threading
from imagens import OUTPUT_DIR, MODELS_DIR

# ═══════════════════════════════════════════════════════════════════════════════
# STABLE DIFFUSION (SD-Turbo) — geração e edição generativa de imagens
# Roda localmente via CPU. Modelo baixa automaticamente na primeira execução.
# ═══════════════════════════════════════════════════════════════════════════════

_txt2img_pipe = None
_img2img_pipe = None
_lock = threading.Lock()


def _carregar_pipelines():
    """Carrega os pipelines de geração uma única vez (lazy loading)."""
    global _txt2img_pipe, _img2img_pipe

    if _txt2img_pipe is not None:
        return _txt2img_pipe, _img2img_pipe

    with _lock:
        if _txt2img_pipe is not None:
            return _txt2img_pipe, _img2img_pipe

        import torch
        from diffusers import AutoPipelineForText2Image, AutoPipelineForImage2Image

        os.makedirs(MODELS_DIR, exist_ok=True)

        _txt2img_pipe = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/sd-turbo",
            torch_dtype=torch.float32,
            cache_dir=MODELS_DIR,
        )
        _txt2img_pipe.to("cpu")

        # Reaproveita os mesmos pesos já carregados para criar o pipeline de img2img
        _img2img_pipe = AutoPipelineForImage2Image.from_pipe(_txt2img_pipe)

    return _txt2img_pipe, _img2img_pipe


def gerar_imagem_ia(prompt: str, caminho_saida: str = None, passos: int = 2) -> str:
    """Gera uma imagem nova a partir de um texto (text-to-image)."""
    txt2img, _ = _carregar_pipelines()

    resultado = txt2img(
        prompt=prompt,
        num_inference_steps=passos,
        guidance_scale=0.0,
    ).images[0]

    if not caminho_saida:
        nome = f"gerada_{int(time.time())}.png"
        caminho_saida = os.path.join(OUTPUT_DIR, nome)

    resultado.save(caminho_saida)
    return caminho_saida


def editar_imagem_ia(caminho_entrada: str, prompt: str, forca: float = 0.55,
                      caminho_saida: str = None, passos: int = 2) -> str:
    """
    Edita uma imagem existente com base em um pedido em texto (image-to-image).
    'forca' (0.0 a 1.0) controla o quanto a imagem original é alterada:
    valores baixos preservam mais a estrutura original, altos mudam mais.
    """
    from PIL import Image

    _, img2img = _carregar_pipelines()

    base = Image.open(caminho_entrada).convert("RGB")
    # Redimensiona para um tamanho que equilibra velocidade e qualidade no CPU
    base.thumbnail((768, 768))

    resultado = img2img(
        prompt=prompt,
        image=base,
        strength=forca,
        num_inference_steps=passos,
        guidance_scale=0.0,
    ).images[0]

    if not caminho_saida:
        nome = os.path.splitext(os.path.basename(caminho_entrada))[0]
        caminho_saida = os.path.join(OUTPUT_DIR, f"{nome}_ia.png")

    resultado.save(caminho_saida)
    return caminho_saida