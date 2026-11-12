"""Lê e grava o Config.xml do Web of Shadows (o mesmo arquivo do launcher original)."""
import ctypes
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULTS = {
    "VideoW": "1920", "VideoH": "1080", "VideoVSync": "1", "VideoShadows": "1",
    "VideoParticles": "1", "VideoPostProcFx": "1", "MouseSens": "50",
    "ActionLeft": "286", "ActionRight": "288", "ActionForward": "273", "ActionBackward": "287",
    "ActionWallCrawl": "272", "ActionWallSprint": "274", "ActionSwing": "525",
    "ActionJump": "313", "ActionCenterCamera": "526",
    "ActionSuit": "314", "ActionTarget": "271", "ActionShoot": "300", "ActionAttack": "524",
    "ActionWebStrike": "302", "ActionUpgrades": "289", "ActionAllyPrev": "459",
    "ActionAllyNext": "461", "ActionAllySummon": "464", "ActionAllyDismiss": "456",
}
TEMPLATE = {"Version": "7", "VideoDesiredW": "0", "VideoDesiredH": "0",
            "MouseMinSens": "0.00075", "MouseMaxSens": "0.005"}


def cfg_path():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Activision" / "Spider-Man Web of Shadows" / "Config.xml"


def read(path=None):
    path = Path(path) if path else cfg_path()
    vals = dict(DEFAULTS)
    if path.exists():
        try:
            for s in ET.parse(path).getroot().iter("s"):
                if s.get("id") in DEFAULTS:
                    vals[s.get("id")] = (s.text or "").strip()
        except ET.ParseError:
            pass
    return vals


def write(values, path=None):
    path = Path(path) if path else cfg_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        bak = path.with_name("Config.xml.original")
        if not bak.exists():
            shutil.copy2(path, bak)  # guarda uma cópia do arquivo do launcher original
        root = ET.parse(path).getroot()
    else:
        root = ET.Element("r")
        for k, v in TEMPLATE.items():
            ET.SubElement(root, "s", id=k).text = v
    existing = {s.get("id"): s for s in root.iter("s")}
    for k, v in values.items():
        v = str(v).strip()
        if k not in DEFAULTS or not re.fullmatch(r"\d+(\.\d+)?", v):
            continue
        if k in existing:
            existing[k].text = v
        else:
            ET.SubElement(root, "s", id=k).text = v
    ET.indent(root, space="\t")
    text = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"
    path.write_text(text, encoding="utf-8")


def read_cores(path=None):
    """MaxCpuCount do Config.xml: quantos núcleos o jogo usa (0 = todos). O jogo usa os N primeiros núcleos."""
    p = Path(path) if path else cfg_path()
    try:
        for s in ET.parse(p).getroot().iter("s"):
            if s.get("id") == "MaxCpuCount":
                return max(0, int(float((s.text or "0").strip())))
    except Exception:
        pass
    return 0


def write_cores(n, path=None):
    """n > 0 grava MaxCpuCount; n == 0 remove a chave (volta ao padrão do jogo: todos os núcleos)."""
    path = Path(path) if path else cfg_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        bak = path.with_name("Config.xml.original")
        if not bak.exists():
            shutil.copy2(path, bak)
        root = ET.parse(path).getroot()
    else:
        root = ET.Element("r")
        for k, v in TEMPLATE.items():
            ET.SubElement(root, "s", id=k).text = v
    for s in [s for s in root.iter("s") if s.get("id") == "MaxCpuCount"]:
        root.remove(s)
    if int(n) > 0:
        ET.SubElement(root, "s", id="MaxCpuCount").text = str(int(n))
    ET.indent(root, space="\t")
    path.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")


class _DEVMODE(ctypes.Structure):
    _fields_ = [("n", ctypes.c_wchar * 32), ("sv", ctypes.c_ushort), ("dv", ctypes.c_ushort),
                ("size", ctypes.c_ushort), ("extra", ctypes.c_ushort), ("fields", ctypes.c_ulong),
                ("px", ctypes.c_long), ("py", ctypes.c_long), ("ori", ctypes.c_ulong),
                ("fo", ctypes.c_ulong), ("color", ctypes.c_short), ("duplex", ctypes.c_short),
                ("yres", ctypes.c_short), ("tt", ctypes.c_short), ("collate", ctypes.c_short),
                ("form", ctypes.c_wchar * 32), ("log", ctypes.c_ushort), ("bpp", ctypes.c_ulong),
                ("w", ctypes.c_ulong), ("h", ctypes.c_ulong), ("flags", ctypes.c_ulong),
                ("freq", ctypes.c_ulong), ("icm", ctypes.c_ulong), ("icmi", ctypes.c_ulong),
                ("media", ctypes.c_ulong), ("dither", ctypes.c_ulong), ("r1", ctypes.c_ulong),
                ("r2", ctypes.c_ulong), ("pw", ctypes.c_ulong), ("ph", ctypes.c_ulong)]


def resolutions():
    found = {(1280, 720), (1280, 1024), (1366, 768), (1600, 900), (1920, 1080)}
    try:
        dm = _DEVMODE()
        dm.size = ctypes.sizeof(_DEVMODE)
        i = 0
        while ctypes.windll.user32.EnumDisplaySettingsW(None, i, ctypes.byref(dm)):
            if dm.w >= 800 and dm.bpp >= 32:
                found.add((dm.w, dm.h))
            i += 1
    except Exception:
        pass
    return [f"{w}x{h}" for w, h in sorted(found)]
