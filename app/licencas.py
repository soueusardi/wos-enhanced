"""Avisos e licenças dos componentes de terceiros que vão dentro do launcher (.exe).

Na hora de gerar o .exe, o WebOfShadowsEnhanced.spec chama build_notices(): os textos completos são lidos dos pacotes
instalados (versões exatas do build) e gravados em licenses/THIRD_PARTY_NOTICES.txt, que vai embutido. Rodando pelo
código-fonte, notices_text() monta o mesmo texto na hora. Os textos que não vêm de pacotes Python ficam em licenses/."""
import sys
import sysconfig
from pathlib import Path

# (nome mostrado, pacote pip ou None, licença, papel no launcher, arquivos de licença próprios em licenses/)
COMPONENTS = [
    ("Python", None, "PSF-2.0", "language runtime and standard library", []),
    ("Expat", None, "MIT", "XML parser inside Python's pyexpat module", ["expat-LICENSE.txt"]),
    ("mpdecimal (libmpdec)", None, "BSD-2-Clause", "decimal arithmetic inside Python's _decimal module", ["mpdecimal-LICENSE.txt"]),
    ("PyInstaller (bootloader)", "pyinstaller", "GPL-2.0-or-later WITH PyInstaller Bootloader exception", "builds the single .exe", []),
    ("pywebview", "pywebview", "BSD-3-Clause", "launcher window", []),
    ("Microsoft WebView2 SDK", None, "BSD-style (Microsoft)", "WebView2 DLLs distributed with pywebview", ["Microsoft.Web.WebView2-LICENSE.txt"]),
    ("pythonnet", "pythonnet", "MIT", "used by pywebview on Windows (includes Python.Runtime.dll)", []),
    ("clr_loader", "clr_loader", "MIT", "used by pythonnet (includes ClrLoader.dll)", []),
    ("cffi", "cffi", "MIT-0", "used by clr_loader", []),
    ("pycparser", "pycparser", "BSD-3-Clause", "used by cffi", []),
    ("bottle", "bottle", "MIT", "used by pywebview", []),
    ("proxy_tools", "proxy_tools", "MIT", "used by pywebview", []),
    ("typing_extensions", "typing_extensions", "PSF-2.0", "used by pywebview", []),
    ("Pillow", "pillow", "MIT-CMU", "image reading and conversion (its license text lists the image libraries it bundles)", []),
    ("three.js r128", None, "MIT", "3D viewer (three.min.js, OrbitControls, OBJLoader)", ["three.js-LICENSE.txt"]),
    ("uMod (Universal Modding Engine) v1 r44", None, "GPL-3.0-or-later", "texture replacement (d3d9.dll); source code in umod/source", []),
]


def _here():
    return Path(__file__).resolve().parent.parent


def _dist_texts(dist_name):
    from importlib import metadata
    try:
        dist = metadata.distribution(dist_name)
    except Exception:
        return None, []
    out = []
    for f in dist.files or []:
        n = f.name.upper()
        if ".dist-info" in str(f) and any(k in n for k in ("LICEN", "COPYING", "NOTICE", "AUTHORS")):
            try:
                out.append((f.name, Path(dist.locate_file(f)).read_text(encoding="utf-8", errors="replace")))
            except Exception:
                pass
    if not out:   # pacote sem arquivo de licença: registra o que ele declara nos metadados (sem inventar texto)
        md = dist.metadata
        info = [f"{k}: {md.get(k)}" for k in ("Name", "Version", "License", "License-Expression", "Author", "Author-email", "Home-page") if md.get(k)]
        out.append(("package metadata", "No license file is shipped with this package. As declared in its metadata:\n" + "\n".join(info)))
    return dist.version, out


def _python_license():
    for p in (Path(sys.base_prefix) / "LICENSE.txt", Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt"):
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    return None


def notices_text(root=None):
    root = Path(root) if root else _here()
    lic_dir = root / "licenses"
    head = ["Web of Shadows Launcher — third-party components / componentes de terceiros",
            "=" * 76,
            "The launcher itself is licensed under the GNU GPL v3 or later (see LICENSE).",
            "Each component below keeps its own license. Full texts follow the list.", ""]
    body = []
    for name, dist, lic, role, files in COMPONENTS:
        version, texts = (None, [])
        if dist:
            version, texts = _dist_texts(dist)
        if name == "Python":
            version = sys.version.split()[0]
            t = _python_license()
            texts = [("LICENSE.txt", t)] if t else []
        for fn in files:
            p = lic_dir / fn
            if p.is_file():
                texts.append((fn, p.read_text(encoding="utf-8", errors="replace")))
        if name.startswith("uMod"):
            gpl = root / "LICENSE"
            texts.append(("LICENSE (GNU GPL v3)", "uMod is licensed under the GNU GPL v3 or later; the full text is the same as the launcher's LICENSE file."
                          if gpl.is_file() else "GNU GPL v3 or later."))
        head.append(f"- {name}{' ' + version if version else ''} — {lic} — {role}")
        body.append("\n" + "#" * 76 + f"\n{name}{' ' + version if version else ''}  ({lic})\n" + "#" * 76)
        if texts:
            for fn, t in texts:
                body.append(f"--- {fn} ---\n{t.strip()}\n")
        else:
            body.append("(license text not found in this environment; see the project's website)\n")
    return "\n".join(head + body) + "\n"


def build_notices(out_dir, root=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "THIRD_PARTY_NOTICES.txt"
    p.write_text(notices_text(root), encoding="utf-8")
    return p


if __name__ == "__main__":
    print(build_notices(sys.argv[1] if len(sys.argv) > 1 else "build/licenses"))
