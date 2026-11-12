# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller para gerar o .exe único (rode build_exe.bat no Windows).
# Dentro do .exe vão: o código, a interface (web/), os créditos (info/), o d3d9.dll do uMod e a licença.
# Fora do .exe (criados na primeira vez em %LOCALAPPDATA%\\Web of Shadows Launcher): config.json, launcher.log, cache/, skins/.
# A fonte dos botões (web/fonts/) é tirada de arquivo do jogo e por isso NÃO entra no .exe, a menos que
# a variável WOS_FONTE=1 esteja definida (só para uso pessoal; não publique um .exe com ela).
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)
COM_FONTE = os.environ.get("WOS_FONTE") == "1"

datas = []
for p in sorted((ROOT / "web").rglob("*")):
    if not p.is_file():
        continue
    if p.parent.name == "fonts" and not COM_FONTE:
        continue
    datas.append((str(p), str(p.parent.relative_to(ROOT))))
datas += [
    (str(ROOT / "info" / "credits.json"), "info"),
    (str(ROOT / "umod" / "d3d9.dll"), "umod"),
    (str(ROOT / "umod" / "README.txt"), "umod"),
    (str(ROOT / "LICENSE"), "."),
]
datas += collect_data_files("webview")

# avisos e licenças completas dos componentes de terceiros, lidos dos pacotes instalados neste build (versões exatas)
import sys
sys.path.insert(0, str(ROOT / "app"))
import licencas
notices = licencas.build_notices(ROOT / "build" / "licenses", ROOT)
datas += [(str(notices), "licenses")]

APP = ["crashcatch", "gameanim", "gameassets", "gamecfg", "i18n", "licencas", "preview", "tpf", "umod_server", "worker", "wospatch"]

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT / "app")],
    datas=datas,
    hiddenimports=APP + collect_submodules("webview"),
    # numpy: só o PIL._typing o importa (anotação de tipos); sem isto entrariam ~20 MB (numpy + OpenBLAS) sem aviso de licença.
    # setuptools/pkg_resources: só a parte de compilação do cffi os usa; o clr_loader usa o cffi sem compilar.
    excludes=["tkinter", "unittest", "pydoc_data", "numpy", "setuptools", "pkg_resources", "distutils"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Web of Shadows Launcher",
    icon=str(ROOT / "web" / "img" / "icon.ico"),
    console=False,          # sem janela preta de console
    upx=False,              # UPX costuma disparar falso positivo de antivírus
    debug=False, strip=False, runtime_tmpdir=None,
)
