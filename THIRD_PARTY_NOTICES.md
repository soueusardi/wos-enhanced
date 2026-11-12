# Componentes de terceiros / Third-party components

O Web of Shadows Launcher é distribuído sob a **GNU GPL v3 ou posterior** (`LICENSE`).
Os componentes abaixo vão dentro do launcher (`.exe`) e mantêm suas próprias licenças.

*Web of Shadows Launcher is licensed under the GNU GPL v3 or later. The components below are bundled and keep their own licenses.*

| Componente | Licença | Uso no launcher |
|---|---|---|
| [uMod](https://github.com/mathewwi/texmod) v1 r44 (`d3d9.dll`) | GPL-3.0-or-later | troca de texturas; código em `umod/source` |
| [three.js](https://github.com/mrdoob/three.js) r128 | MIT | visualizador 3D |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause | janela do launcher |
| Microsoft WebView2 SDK (DLLs que acompanham o pywebview) | BSD (Microsoft) | WebView2 |
| [pythonnet](https://github.com/pythonnet/pythonnet) · clr_loader | MIT | usados pelo pywebview no Windows |
| cffi | MIT-0 | usado pelo clr_loader |
| pycparser | BSD-3-Clause | usado pelo cffi |
| bottle · proxy_tools | MIT | usados pelo pywebview |
| typing_extensions | PSF-2.0 | usado pelo pywebview |
| [Pillow](https://python-pillow.org) | MIT-CMU (inclui bibliotecas de imagem com licenças próprias) | imagens |
| [Python](https://www.python.org) | PSF-2.0 (inclui OpenSSL, bzip2, libffi e outros com licenças próprias, no mesmo texto) | linguagem |
| [Expat](https://libexpat.github.io) (dentro do `pyexpat` do Python) | MIT | leitura de XML |
| [mpdecimal](https://www.bytereef.org/mpdecimal/) (dentro do `_decimal` do Python) | BSD-2-Clause | aritmética decimal |
| [PyInstaller](https://pyinstaller.org) (bootloader) | GPL-2.0-or-later com exceção do bootloader | monta o `.exe` |

**Textos completos:** a cada build, `app/licencas.py` lê as licenças dos pacotes instalados (versões exatas) e gera
`licenses/THIRD_PARTY_NOTICES.txt`, que vai embutido no `.exe` e pode ser aberto no launcher em **Opções › Sobre ›
Componentes de terceiros**. Os textos que não vêm de pacotes Python estão em `licenses/`.
