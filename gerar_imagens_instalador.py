"""Gera as imagens BMP do assistente do Inno Setup a partir de assets/logo.png.

Rodado automaticamente por create_installer.bat quando os BMPs nao existem.
"""
import os

from PIL import Image

_AQUI = os.path.dirname(os.path.abspath(__file__))
_ASSETS = os.path.join(_AQUI, "assets")


def _montar(logo: Image.Image, dest: str, size: tuple[int, int],
            margem: int, ancora: str):
    fundo = Image.new("RGB", size, (255, 255, 255))
    img = logo.copy()
    img.thumbnail((size[0] - margem * 2, size[1] - margem * 2), Image.LANCZOS)
    if ancora == "topo":
        pos = ((size[0] - img.width) // 2, margem * 2)
    else:
        pos = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
    fundo.paste(img, pos, img)
    fundo.save(dest, "BMP")
    print(f"  {os.path.basename(dest)}  {size[0]}x{size[1]}")


def main():
    logo = Image.open(os.path.join(_ASSETS, "logo.png")).convert("RGBA")
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)

    # Painel lateral (Inno: 164x314 base) e icone do cabecalho (55x58 base),
    # cada um com a variante 2x para telas HiDPI
    _montar(logo, os.path.join(_ASSETS, "wizard.bmp"), (164, 314), 14, "topo")
    _montar(logo, os.path.join(_ASSETS, "wizard@2x.bmp"), (328, 628), 28, "topo")
    _montar(logo, os.path.join(_ASSETS, "wizard_small.bmp"), (55, 58), 4, "centro")
    _montar(logo, os.path.join(_ASSETS, "wizard_small@2x.bmp"), (110, 116), 8, "centro")


if __name__ == "__main__":
    main()
