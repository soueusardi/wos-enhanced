import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)   # rodando como .exe único (PyInstaller)?
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))   # arquivos do programa (dentro do .exe, se empacotado)


def _user_dir():
    """Onde ficam os dados do usuário (config, log, cache, skins). No .exe: %LOCALAPPDATA%\\Web of Shadows Launcher,
    para a pasta do .exe ficar só com o .exe. Pelo código-fonte: a própria pasta do projeto."""
    if not FROZEN:
        return Path(__file__).resolve().parent
    root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(root) / "Web of Shadows Launcher"


HOME = _user_dir()
HOME.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE / "app"))


def self_cmd(tool, *args):
    """O mesmo programa em outro papel (--worker / --crashcatch): no .exe é o próprio .exe; no código-fonte, python launcher.py."""
    head = [sys.executable] if FROZEN else [sys.executable, str(Path(__file__).resolve())]
    return head + ["--" + tool] + [str(a) for a in args]


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("--worker", "--crashcatch"):
    # papéis auxiliares: rodam sem abrir janela nem carregar a interface
    _tool = sys.argv[1][2:]
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    os.environ.setdefault("WOS_LOG", str(HOME / "launcher.log"))
    _mod = __import__(_tool)
    sys.exit(getattr(_mod, "run", _mod.main)())

import webview

import gameassets
import gamecfg
import wospatch
import i18n
import preview
import tpf
from i18n import T
from umod_server import UModServer

CONFIG = HOME / "config.json"
APP_VERSION = "0.1.0"
INFO_FILE = BASE / "info" / "credits.json"
MODEL_DIR = HOME / "models" / "spiderman"          # alternativa manual (arquivos copiados à mão)
GAME_ASSETS = HOME / "cache" / "gameassets"        # modelo e texturas lidos da cópia do jogo do usuário
SKINS = HOME / "skins"
CACHE = HOME / "cache"
LOG = HOME / "launcher.log"
UMOD_DIRS = list(dict.fromkeys([HOME / "umod", BASE / "umod"]))   # o d3d9.dll do uMod vem embutido (GPL v3, veja umod/README.txt)
DEFAULT_GAME_DIR = r"E:\Games\Spider Man Web of Shadows"
GAME_EXE = "Spider-Man Web of Shadows.exe"
WINDOW = None  # fica fora do Api de propósito (o pywebview varre os atributos do Api)


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except Exception:
        pass


SERVER = UModServer(log)


def find_exe(game_dir):
    """Acha o exe do JOGO (nunca o launcher original) sem varrer packs, vídeos e sons."""
    for rel in ("image/pc", "pc", "."):
        p = game_dir / rel / GAME_EXE
        if p.is_file():
            return str(p)
    skip = {"packs", "movies", "sound", "en", "saves"}
    base = len(game_dir.parts)
    for d, dirs, files in os.walk(game_dir):
        if len(Path(d).parts) - base >= 3:
            dirs[:] = []
        else:
            dirs[:] = [x for x in dirs if x.lower() not in skip]
        if GAME_EXE in files:
            return os.path.join(d, GAME_EXE)
    return ""


NO_WINDOW = 0x08000000


def launch_game(exe, cwd, skip_intro=False, pad_hex=""):
    """Abre o jogo pelo ajudante (crashcatch.py), que aplica o reparo da queda e registra qualquer erro."""
    if sys.platform == "win32":
        return subprocess.Popen(self_cmd("crashcatch", exe, cwd, "0", "1", "1" if skip_intro else "0", f"{time.time():.3f}", pad_hex or "-"),
                                cwd=str(HOME), creationflags=NO_WINDOW, env={**os.environ, "WOS_LOG": str(LOG)})
    return subprocess.Popen([exe], cwd=cwd)


# ---------- controle (XInput) ----------
class _XGamepad(ctypes.Structure):
    _fields_ = [("wButtons", ctypes.c_ushort), ("bLeftTrigger", ctypes.c_ubyte), ("bRightTrigger", ctypes.c_ubyte),
                ("sThumbLX", ctypes.c_short), ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short)]


class _XState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_uint), ("Gamepad", _XGamepad)]


_XI = []


def _xinput():
    if not _XI:
        lib = None
        if sys.platform == "win32":
            for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
                try:
                    lib = ctypes.WinDLL(name)
                    break
                except OSError:
                    continue
        _XI.append(lib)
    return _XI[0]


def pad_state():
    """Estado do primeiro controle XInput conectado (ou None)."""
    lib = _xinput()
    if lib is None:
        return None
    st = _XState()
    for i in range(4):
        if lib.XInputGetState(i, ctypes.byref(st)) == 0:
            return st
    return None


def pad_pressed(st):
    g = st.Gamepad
    out = [n for n, bit in wospatch.PAD_BITS.items() if bit < 16 and g.wButtons & (1 << bit)]
    if g.bLeftTrigger > 30:
        out.append("LT")
    if g.bRightTrigger > 30:
        out.append("RT")
    return out


def run_worker(task, src, out, on_msg=None):
    """Roda app/worker.py num processo separado e espera. Devolve o JSON final ({"ok": ...})."""
    cmd = self_cmd("worker", task, src, out)
    flags = NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(cmd, cwd=str(HOME), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", creationflags=flags)
    final = {"ok": False, "error": "o processo de trabalho terminou sem resposta"}
    for line in proc.stdout:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if "ok" in msg:
            final = msg
        elif on_msg:
            on_msg(msg)
    err = proc.stderr.read()
    proc.wait()
    if not final.get("ok") and err.strip():
        final["error"] = final.get("error", "") + " | " + err.strip()[-300:]
    return final


def log_crash_event():
    """Anota o relatório de falha do Windows (qual módulo e endereço causaram a queda)."""
    if sys.platform != "win32":
        return
    try:
        time.sleep(2)  # o Windows demora um pouco para registrar o evento
        q = "*[System[Provider[@Name='Application Error'] and (EventID=1000)]]"
        out = subprocess.run(["wevtutil", "qe", "Application", f"/q:{q}", "/c:1", "/rd:true", "/f:text"],
                             capture_output=True, text=True, errors="ignore", timeout=15, creationflags=NO_WINDOW).stdout
        keep = [ln.strip() for ln in out.splitlines()
                if re.search(r"Date|Data|módulo|module|exce|Exception|offset|deslocamento|Faulting|falha", ln, re.I)]
        log("evento de falha do Windows: " + " | ".join(keep[:10]))
    except Exception as e:
        log(f"wevtutil erro: {e!r}")


def find_umod_dll():
    for d in UMOD_DIRS:
        p = d / "d3d9.dll"
        if p.is_file():
            return p
    return None


def load_config():
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"game_dir": DEFAULT_GAME_DIR}


def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


LITE = CACHE / "lite"        # previews leves (só as texturas dos trajes)
THUMBS = CACHE / "thumbs"    # miniaturas dos quadradinhos (PNG)
API = None                   # o mesmo motivo do WINDOW: fica fora do Api

# (id, pasta). O jogador não precisa abrir essas pastas: o launcher separa as skins sozinho ao importar.
GROUPS = (
    ("vermelho", "red suit"),
    ("preto", "black suit"),
    ("dual", "2 in 1"),
    ("outros", "other"),
)
FOLDERS = dict(GROUPS)
SUIT_GROUPS = {"Clássico": ("vermelho", "dual"), "Negro": ("preto", "dual")}


def group_dir(gid):
    return SKINS / FOLDERS[gid]


def group_files(gid):
    d = group_dir(gid)
    d.mkdir(parents=True, exist_ok=True)
    return sorted(d.glob("*.tpf"), key=lambda p: p.name.lower())


LEGACY_FOLDERS = {"vermelho": "roupa vermelha", "preto": "roupa preta", "dual": "dois em um", "outros": "outros"}   # nomes até a 0.1.0


def make_skin_folders():
    for gid, _f in GROUPS:
        new, old = group_dir(gid), SKINS / LEGACY_FOLDERS[gid]
        if old.is_dir() and old != new:          # pastas antigas (em português) viram as novas (em inglês)
            try:
                if not new.exists():
                    old.rename(new)
                else:
                    for f in old.glob("*.tpf"):
                        if not (new / f.name).exists():
                            shutil.move(str(f), str(new / f.name))
                    if not any(old.iterdir()):
                        old.rmdir()
            except Exception as e:
                log(f"não consegui renomear a pasta {old.name}: {e!r}")
        new.mkdir(parents=True, exist_ok=True)
    readme = SKINS / "README.txt"
    if not readme.exists():
        readme.write_text(
            "You don't need to touch these folders.\n"
            "In the launcher, open the Suits tab and drag a .tpf file onto the window (or use the Add skin button).\n"
            "The launcher works out whether the skin is for the red suit, the black suit, both (2 in 1) or another model\n"
            "and keeps it here. To delete a skin, use the X on its thumbnail.\n\n"
            "Voce nao precisa mexer nestas pastas.\n"
            "No launcher, abra a aba Trajes e arraste o arquivo .tpf para a janela (ou use o botao Adicionar skin).\n"
            "O launcher descobre sozinho se a skin e do traje vermelho, do preto, dos dois (2 em 1) ou de outro modelo\n"
            "e guarda aqui. Para apagar uma skin, use o X no quadradinho dela.\n", encoding="utf-8")
    old_readme = SKINS / "LEIA-ME.txt"
    if old_readme.is_file():
        old_readme.unlink(missing_ok=True)


def unique_dest(folder, name):
    dest = folder / name
    n = 2
    while dest.exists():
        dest = folder / f"{Path(name).stem} ({n}){Path(name).suffix}"
        n += 1
    return dest


def kind_of(path):
    z, defs = tpf.read_defs(path)
    return preview.classify([h for h, _ in defs])


class Api:
    def __init__(self):
        self._cfg = load_config()
        self._prep = {}  # chave do cache -> "preparando" | "erro: ..."
        self._lock = threading.Lock()
        self._msg = ""
        self._busy = False
        self._model = None
        self._ga = {"state": "idle", "pct": 0, "error": ""}
        self._lite_locks = {}
        self._game_running = False   # extração do modelo da cópia do jogo
        i18n.set_lang(self._cfg.get("lang", "pt"))
        make_skin_folders()
        self._cfg.setdefault("active", {})
        self._migrate()

    def _migrate(self):
        """Skins soltas na pasta skins (versões antigas) vão para a pasta certa; o grupo antigo 'geral' some."""
        act = self._cfg["active"]
        old_geral = act.pop("geral", None)
        for name in self._cfg.pop("skins", None) or []:       # formato antigo: lista de nomes marcados
            if (SKINS / f"{name}.tpf").is_file():
                old_geral = old_geral or f"{name}.tpf"
        moved = {}
        for f in sorted(SKINS.glob("*.tpf")):
            try:
                kind = kind_of(f)
                dest = unique_dest(group_dir(kind), f.name)
                shutil.move(str(f), str(dest))
                moved[f.name] = (kind, dest.name)
                log(f"skin solta organizada: {f.name} -> {kind}")
            except Exception as e:
                log(f"não consegui organizar {f.name}: {e!r}")
        if old_geral and old_geral in moved:
            kind, name = moved[old_geral]
            act[kind] = name
            if kind == "dual":
                act["vermelho"] = act["preto"] = None
        self._cfg.pop("bad", None)  # restos do antigo teste de skins
        save_config(self._cfg)

    # ---------- jogo ----------
    def get_state(self):
        game_dir = Path(self._cfg["game_dir"])
        exe = ""
        try:
            t0 = time.time()
            exe = find_exe(game_dir)
            log(f"get_state: exe='{exe}' em {time.time() - t0:.2f}s")
        except Exception as e:
            log(f"get_state erro: {e!r}")
        self._cfg["exe"] = exe
        if exe:
            self._start_gameassets(game_dir, exe)
        return {"game_dir": str(game_dir), "found": bool(exe), "exe": exe, "umod": find_umod_dll() is not None,
                "lang": self._cfg.get("lang", "pt"), "version": APP_VERSION,
                "skip_intro": self._cfg.get("skip_intro", True), "cpu_cores": gamecfg.read_cores(), "pose": self._cfg.get("pose", "crossed")}

    def choose_folder(self):
        res = WINDOW.create_file_dialog(webview.FileDialog.FOLDER if hasattr(webview, "FileDialog") else webview.FOLDER_DIALOG)
        if res:
            self._cfg["game_dir"] = res[0]
            save_config(self._cfg)
        return self.get_state()

    # ---------- launcher: idioma, créditos e licenças ----------
    def set_language(self, lang):
        lang = "en" if lang == "en" else "pt"
        self._cfg["lang"] = lang
        save_config(self._cfg)
        i18n.set_lang(lang)
        return True

    def set_flag(self, name, value):
        if name == "skip_intro":
            self._cfg["skip_intro"] = bool(value)
            save_config(self._cfg)
        elif name == "pose" and value in ("crossed", "hanging"):
            self._cfg["pose"] = value
            save_config(self._cfg)
        return True

    def set_cpu_cores(self, n):
        """Modo 60 FPS estável (experimental): limita quantos núcleos de CPU o jogo usa, via MaxCpuCount no Config.xml."""
        try:
            n = max(0, min(int(n), 16))
            gamecfg.write_cores(n)
            return {"ok": True, "cores": n}
        except Exception as e:
            log(f"não consegui gravar MaxCpuCount: {e!r}")
            return {"ok": False, "cores": gamecfg.read_cores()}

    def get_license(self, kind):
        """Texto completo da licença do launcher ("launcher") ou dos componentes de terceiros ("third")."""
        try:
            if kind == "launcher":
                return {"ok": True, "text": (BASE / "LICENSE").read_text(encoding="utf-8")}
            if kind == "third":
                built = BASE / "licenses" / "THIRD_PARTY_NOTICES.txt"   # gerado no build do .exe
                if built.is_file():
                    return {"ok": True, "text": built.read_text(encoding="utf-8")}
                import licencas
                return {"ok": True, "text": licencas.notices_text(BASE)}
        except Exception as e:
            log(f"não consegui abrir a licença ({kind}): {e!r}")
        return {"ok": False, "text": ""}

    def get_pad(self):
        """Controle conectado? E qual botão faz cada ação (padrão do jogo + trocas salvas)."""
        try:
            connected = pad_state() is not None
        except Exception as e:
            log(f"não consegui ler o controle: {e!r}")
            connected = False
        return {"connected": connected, "defaults": wospatch.PAD_DEFAULTS,
                "map": {**wospatch.PAD_DEFAULTS, **self._cfg.get("pad_map", {})}}

    def poll_pad(self):
        """Botões apertados agora (para a tela de troca)."""
        try:
            st = pad_state()
        except Exception:
            st = None
        return {"connected": st is not None, "pressed": pad_pressed(st) if st else []}

    def set_pad_map(self, m):
        clean = {a: b for a, b in (m or {}).items() if a in wospatch.PAD_DEFAULTS and b in wospatch.PAD_BITS and b != "START"}
        full = {**wospatch.PAD_DEFAULTS, **clean}
        if len(set(full.values())) != len(full):           # cada botão para uma ação só
            return {"ok": False, "msg": T("pad_bad")}
        self._cfg["pad_map"] = {a: b for a, b in full.items() if wospatch.PAD_DEFAULTS[a] != b}
        save_config(self._cfg)
        return {"ok": True, "msg": T("opts_saved")}

    def get_info(self):
        """Versão, créditos e licenças (lidos de info/credits.json, que você pode editar)."""
        try:
            data = json.loads(INFO_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"não consegui ler {INFO_FILE.name}: {e!r}")
            data = {}
        return {"version": APP_VERSION, "repo": data.get("repo", ""), "credits": data.get("credits", [])}

    def open_url(self, url):
        if isinstance(url, str) and url.startswith("https://"):
            webbrowser.open(url)
            return True
        return False

    # ---------- opções ----------
    def get_options(self):
        return {"values": gamecfg.read(), "defaults": gamecfg.DEFAULTS, "resolutions": gamecfg.resolutions()}

    def save_options(self, values):
        try:
            gamecfg.write(values)
            return {"ok": True, "msg": T("opts_saved")}
        except Exception as e:
            return {"ok": False, "msg": T("opts_fail", e=e)}

    # ---------- skins (.tpf) ----------
    def _dual_on(self):
        return self._active_path("dual") is not None

    def _active_path(self, gid):
        name = self._cfg.get("active", {}).get(gid)
        if not name:
            return None
        p = group_dir(gid) / name
        return p if p.is_file() else None

    def _start_prepare(self, path):
        key = tpf.cache_key(path)
        with self._lock:
            if key in self._prep:
                return
            self._prep[key] = "preparando"

        def work():
            try:
                log(f"preparando skin {path.name}")
                res = run_worker("prepare", path, CACHE)
                if not res.get("ok"):
                    raise RuntimeError(res.get("error"))
                log(f"skin {path.name} pronta: " + " ".join(res["hashes"]))
                with self._lock:
                    self._prep.pop(key, None)
            except Exception as e:
                log(f"erro ao preparar {path.name}: {e!r}")
                with self._lock:
                    self._prep[key] = f"erro: {e}"

        threading.Thread(target=work, daemon=True).start()

    def _thumb_uri(self, path):
        f = THUMBS / f"{tpf.cache_key(path)}.png"
        return preview.png_file_uri(f) if f.is_file() else None

    def get_skins(self):
        """Grupos com as skins de cada um, qual está em uso e se o grupo está travado (por uma skin '2 em 1')."""
        out, dual_on = [], self._dual_on()
        for gid, _folder in GROUPS:
            files = group_files(gid)
            if gid in ("dual", "outros") and not files:
                continue
            locked = dual_on and gid in ("vermelho", "preto")
            active = None if locked else self._active_path(gid)
            skins = []
            for p in files:
                is_active = active is not None and p.name == active.name
                ready = tpf.cached_items(p, CACHE) is not None
                if is_active and not ready:
                    self._start_prepare(p)
                with self._lock:
                    st = self._prep.get(tpf.cache_key(p))
                skins.append({"file": p.name, "name": p.stem, "active": is_active, "thumb": self._thumb_uri(p),
                              "status": st or ("pronto" if ready else "pendente")})
            out.append({"id": gid, "skins": skins, "locked": locked})
        return out

    def set_active(self, gid, file):
        if gid not in FOLDERS:
            return self.get_skins()
        act = self._cfg.setdefault("active", {})
        if gid in ("vermelho", "preto") and self._dual_on():
            return self.get_skins()          # travado: escolha "Original" em 2 em 1 para liberar
        act[gid] = file or None
        if gid == "dual" and file:           # uma skin 2 em 1 já cuida dos dois trajes
            act["vermelho"] = act["preto"] = None
        save_config(self._cfg)
        return self.get_skins()

    def open_skins_folder(self):
        make_skin_folders()
        try:
            if sys.platform == "win32":
                os.startfile(str(SKINS))
        except Exception as e:
            log(f"não abriu a pasta de skins: {e!r}")
        return True

    def import_skins(self, paths):
        """Copia os .tpf para a biblioteca, na pasta certa (descoberta pelo conteúdo)."""
        res = []
        for raw in paths or []:
            p = Path(raw)
            if p.suffix.lower() != ".tpf" or not p.is_file():
                res.append({"ok": False, "msg": T("import_not_tpf", name=p.name)})
                continue
            try:
                kind = kind_of(p)
            except Exception as e:
                log(f"skin ilegível {p.name}: {e!r}")
                res.append({"ok": False, "msg": T("import_bad", name=p.stem)})
                continue
            dest = group_dir(kind) / p.name
            try:
                same = dest.exists() and dest.stat().st_size == p.stat().st_size
                if same or (dest.exists() and dest.samefile(p)):
                    res.append({"ok": True, "group": kind, "file": dest.name, "msg": T("import_dup", name=p.stem, group=T("grp_" + kind))})
                    continue
                dest = unique_dest(group_dir(kind), p.name)
                shutil.copy2(p, dest)
            except Exception as e:
                log(f"não consegui copiar {p.name}: {e!r}")
                res.append({"ok": False, "msg": T("import_bad", name=p.stem)})
                continue
            log(f"skin importada: {p.name} -> {kind}")
            res.append({"ok": True, "group": kind, "file": dest.name, "msg": T("import_ok", name=dest.stem, group=T("grp_" + kind))})
        return {"results": res, "skins": self.get_skins()}

    def add_skin_dialog(self):
        try:
            kind = webview.FileDialog.OPEN if hasattr(webview, "FileDialog") else webview.OPEN_DIALOG
            sel = WINDOW.create_file_dialog(kind, allow_multiple=True, file_types=("Skins (*.tpf)",))
        except Exception as e:
            log(f"diálogo de arquivos falhou: {e!r}")
            sel = None
        return self.import_skins(list(sel)) if sel else {"results": [], "skins": self.get_skins()}

    def remove_skin(self, gid, file):
        if gid not in FOLDERS:
            return self.get_skins()
        p = group_dir(gid) / file
        try:
            key = tpf.cache_key(p)
            if self._cfg.get("active", {}).get(gid) == file:
                self._cfg["active"][gid] = None
                save_config(self._cfg)
            p.unlink()
            for d in (CACHE / key, LITE / key):
                shutil.rmtree(d, ignore_errors=True)
            (THUMBS / f"{key}.png").unlink(missing_ok=True)
            log(f"skin removida: {file}")
        except Exception as e:
            log(f"não consegui remover {file}: {e!r}")
        return self.get_skins()

    def _lite(self, path):
        """Preview leve: do cache se já existe; senão calcula num processo separado (não trava a janela)."""
        data = preview.lite_cached(path, LITE)
        if data is not None:
            return data
        key = tpf.cache_key(path)
        with self._lock:
            lk = self._lite_locks.setdefault(key, threading.Lock())
        with lk:                              # duas perguntas ao mesmo tempo pela mesma skin: calcula uma vez só
            data = preview.lite_cached(path, LITE)
            if data is None:
                res = run_worker("lite", path, LITE)
                if not res.get("ok"):
                    raise RuntimeError(res.get("error"))
                data = preview.lite_cached(path, LITE)
        if data is None:
            raise RuntimeError("preview não gerado")
        return data

    def get_skin_preview(self, gid, file):
        """Texturas de uma skin para desenhar a miniatura (versão leve: não precisa da preparação completa)."""
        try:
            data = self._lite(group_dir(gid) / file)
        except Exception as e:
            log(f"erro no preview de {file}: {e!r}")
            return None
        return {"kind": data["kind"], "suits": data["suits"], "extras": data["extras"]}

    def save_thumb(self, gid, file, data_url):
        return self._save_png(THUMBS / f"{tpf.cache_key(group_dir(gid) / file)}.png", data_url)

    def get_original_thumbs(self):
        return {s: (preview.png_file_uri(THUMBS / f"original_{s}.png") if (THUMBS / f"original_{s}.png").is_file() else None)
                for s in ("Clássico", "Negro")}

    def save_original_thumb(self, suit, data_url):
        return self._save_png(THUMBS / f"original_{suit}.png", data_url)

    def _save_png(self, dest, data_url):
        try:
            import base64
            raw = base64.b64decode(str(data_url).split(",", 1)[1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            return True
        except Exception as e:
            log(f"não consegui salvar a miniatura: {e!r}")
            return False

    # ---------- modelo 3D lido da cópia do jogo ----------
    def _start_gameassets(self, game_dir, exe):
        """Se o cache do modelo não existe (ou o jogo mudou), extrai em segundo plano. Nunca grava na pasta do jogo."""
        with self._lock:
            if self._ga["state"] == "working":
                return
            pack = gameassets.pack_path(game_dir, exe)
            if pack is None:
                self._ga = {"state": "nopack", "pct": 0, "error": ""}
                log("gameassets: MEGACITY.PCPACK não encontrado")
                return
            if gameassets.is_ready(GAME_ASSETS, pack):
                self._ga = {"state": "done", "pct": 100, "error": ""}
                return
            self._ga = {"state": "working", "pct": 0, "error": ""}

        def work():
            t0 = time.time()
            try:
                log(f"gameassets: extraindo de {pack}")

                def prog(frac, stage):
                    self._ga["pct"] = int(frac * 100)
                def on_msg(m):
                    if "pct" in m:
                        prog(m["pct"] / 100, None)
                    elif "log" in m:
                        log(m["log"])
                res = run_worker("gameassets", pack, GAME_ASSETS, on_msg)
                if not res.get("ok"):
                    raise RuntimeError(res.get("error"))
                crcs = res["crcs"]
                log(f"gameassets: pronto em {time.time() - t0:.1f}s; hashes {crcs}")
                for s in ("Clássico", "Negro"):             # miniaturas antigas foram feitas com o modelo anterior
                    (THUMBS / f"original_{s}.png").unlink(missing_ok=True)
                with self._lock:
                    self._model = None
                    self._ga = {"state": "done", "pct": 100, "error": ""}
            except Exception as e:
                log(f"gameassets: falhou: {e!r}")
                with self._lock:
                    self._ga = {"state": "error", "pct": 0, "error": str(e)}
        threading.Thread(target=work, daemon=True).start()

    def get_model_status(self):
        return dict(self._ga)

    def get_model(self):
        """Modelo 3D (OBJ) e as texturas originais dos dois trajes: primeiro o que foi lido da cópia do jogo
        (cache/gameassets); se não houver, a pasta models/spiderman copiada à mão; senão, nada (visualizador vazio)."""
        if self._model is None:
            if self._ga["state"] == "working":
                return None  # ainda lendo da cópia do jogo: a interface mostra o progresso e pede de novo no fim
            if gameassets.is_ready(GAME_ASSETS):
                src, obj_name, from_game = GAME_ASSETS, "spiderman.obj", True
            elif (MODEL_DIR / "blacksuit.obj").is_file():
                src, obj_name, from_game = MODEL_DIR, "blacksuit.obj", False
            else:
                return None  # sem modelo (o launcher não distribui os arquivos do jogo): o visualizador fica vazio
            try:
                obj = (src / obj_name).read_text(encoding="utf-8", errors="ignore")
                orig = {
                    "Clássico": {"upper": preview.file_uri(src / "upperbody.png"),
                                 "lower": preview.file_uri(src / "lowerbody.png")},
                    "Negro": {"upper": preview.file_uri(src / "bsuit_upperbody.png"),
                              "lower": preview.file_uri(src / "bsuit_lowerbody.png")},
                }
                # só o traje vermelho usa relevo no visualizador (como nas versões anteriores). O relevo certo do traje
                # preto também é extraído (bsuit_*_n.png) e fica no cache; testado no visualizador, quase não muda nada
                normals = {"Clássico": {"upper": preview.file_png_uri(src / "upperbody_n.png"),
                                        "lower": preview.file_png_uri(src / "lowerbody_n.png")}}
                skel = None   # esqueleto + pesos do jogo (poses com os ossos reais); sem ele, o pose.js usa o automático
                if from_game:
                    try:
                        skel = json.loads((src / "skeleton.json").read_text(encoding="utf-8"))
                    except Exception as e:
                        log(f"esqueleto do jogo não carregou (uso o automático): {e!r}")
                game_poses = None   # poses tiradas das animações originais (braços cruzados, pendurado)
                if from_game and skel:
                    try:
                        game_poses = json.loads((src / "poses.json").read_text(encoding="utf-8")) or None
                    except Exception as e:
                        log(f"poses do jogo não carregaram (uso as feitas à mão): {e!r}")
                self._model = {"obj": obj, "original": orig, "normals": normals, "skel": skel, "game_poses": game_poses,
                               "source": "game" if from_game else "manual"}
                log(f"modelo carregado de {src}" + (f" (esqueleto do jogo: {len(skel['bones'])} ossos)" if skel else ""))
            except Exception as e:
                log(f"erro ao carregar o modelo de {src}: {e!r}")
                return None
        return self._model

    def get_previews(self):
        """Para cada traje, a skin escolhida (se houver) com as texturas para o boneco 3D; sem skin = original.
        'extras' traz miniaturas das texturas da skin que são de outro modelo (sem preview 3D)."""
        out = {"suits": {}, "extras": {}}
        for suit, gids in SUIT_GROUPS.items():
            for gid in gids:
                if gid in ("vermelho", "preto") and self._dual_on():
                    continue
                p = self._active_path(gid)
                if p is None:
                    continue
                try:
                    data = self._lite(p)
                except Exception as e:
                    log(f"erro no preview de {p.name}: {e!r}")
                    continue
                entry = next((x for x in data["suits"] if x["suit"] == suit), None)
                if entry:
                    out["suits"][suit] = {"skin": p.stem, **{k: entry[k] for k in ("upper", "lower", "nupper", "nlower")}}
                if data["extras"] and suit not in out["extras"]:
                    out["extras"][suit] = {"skin": p.stem, "items": data["extras"]}
                if entry:
                    break
        return out

    # ---------- jogar ----------
    def get_msg(self):
        return {"msg": self._msg, "busy": self._busy}

    def play(self):
        if self._busy:
            return {"ok": False, "msg": T("already_opening")}
        exe = self._cfg.get("exe")
        if not exe or not os.path.isfile(exe):
            return {"ok": False, "msg": T("game_not_found")}

        items, seen = [], set()
        dual_on = self._dual_on()
        for gid, _folder in GROUPS:  # vermelho e preto primeiro: o primeiro a trocar uma textura vence
            if dual_on and gid in ("vermelho", "preto"):
                continue                     # uma skin 2 em 1 ativa: nunca mistura com skins individuais
            p = self._active_path(gid)
            if p is None:
                continue
            got = tpf.cached_items(p, CACHE)
            if got is None:
                self._start_prepare(p)
                return {"ok": False, "msg": T("skin_preparing", name=p.stem)}
            for h, path in preview.filter_items(got, gid):
                if h not in seen:
                    seen.add(h)
                    items.append((h, path))

        self._busy = True
        self._msg = T("opening")
        threading.Thread(target=self._play_worker, args=(exe, items), daemon=True).start()
        return {"ok": True, "msg": T("opening")}

    def _play_worker(self, exe, items):
        copied = None
        try:
            exe_dir = os.path.dirname(exe)
            if items:
                src = find_umod_dll()
                if src is None:
                    self._msg = T("umod_missing")
                    return
                dst = Path(exe_dir) / "d3d9.dll"
                if dst.exists():
                    if dst.stat().st_size != src.stat().st_size:
                        self._msg = T("dll_exists")
                        return
                    for _ in range(6):  # sobra da abertura anterior: o Windows pode demorar a soltar o arquivo
                        try:
                            dst.unlink()
                            break
                        except PermissionError:
                            time.sleep(0.5)
                if not dst.exists():
                    shutil.copy2(src, dst)
                copied = dst
            cores = gamecfg.read_cores()
            log(f"play: {len(items)} texturas; d3d9.dll {'copiado' if copied else 'não usado'}; "
                f"núcleos do jogo: {cores or 'todos'}; exe={exe}")
            SERVER.set_textures(items)
            SERVER.start()
            if sys.platform == "win32":
                log(f"servidor uMod pronto: {SERVER.wait_ready(5.0)}")
            table = wospatch.pad_table(self._cfg.get("pad_map", {}))
            pad_hex = "" if wospatch.pad_is_identity(table) else table.hex()
            if pad_hex:
                log("controle: botões trocados " + ", ".join(f"{a[6:]}={b}" for a, b in self._cfg.get("pad_map", {}).items()))
            proc = launch_game(exe, exe_dir, self._cfg.get("skip_intro", True), pad_hex)
            self._game_running = True
            notify_js("window.onGameRunning && window.onGameRunning(true)")
            t_start = time.time()
            threading.Thread(target=self._monitor, args=(proc, t_start, copied), daemon=True).start()
            copied = None  # a limpeza passa para o monitor
            self._msg = T("started_n", n=len(items)) if items else T("started")
        except Exception as e:
            log(f"erro ao iniciar: {e!r}")
            self._msg = T("start_fail", e=e)
            if copied:
                try:
                    copied.unlink(missing_ok=True)
                except Exception:
                    pass
        finally:
            self._busy = False

    def _monitor(self, proc, t_start, copied):
        code = proc.wait()
        self._game_running = False
        notify_js("window.onGameRunning && window.onGameRunning(false)")
        up = time.time() - t_start
        log(f"jogo fechou: código de saída {code} após {up:.1f}s")
        if copied:
            for i in range(6):  # o Windows pode demorar um instante para soltar o arquivo
                try:
                    copied.unlink(missing_ok=True)
                    break
                except Exception as e:
                    if i == 5:
                        log(f"não consegui remover o d3d9.dll: {e!r}")
                    time.sleep(0.5)
        if code not in (0, None) and up < 25:
            log_crash_event()
            self._msg = T("crashed")


def notify_js(code):
    try:
        if WINDOW is not None:
            WINDOW.evaluate_js(code)
    except Exception:
        pass


def _bind_drop(window):
    """Arrastar um .tpf para a janela do launcher: o pywebview entrega o caminho completo do arquivo."""
    try:
        from webview.dom import DOMEventHandler

        def on_drop(e):
            try:
                files = (e.get("dataTransfer") or {}).get("files") or []
                paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
                if not paths:
                    return
                res = API.import_skins(paths)
                window.evaluate_js("window.onSkinsImported && window.onSkinsImported(" + json.dumps(res) + ")")
            except Exception as ex:
                log(f"erro ao soltar arquivo: {ex!r}")

        window.dom.document.events.drop += DOMEventHandler(on_drop, True, False)   # sem parar a propagação
        log("arrastar e soltar ativado")
    except Exception as ex:
        log(f"arrastar e soltar indisponível (use o botão Adicionar skin): {ex!r}")


def main():
    global WINDOW, API
    api = API = Api()
    WINDOW = webview.create_window(
        "Web of Shadows Launcher",
        url=str(BASE / "web" / "index.html"),
        js_api=api,
        width=1100,
        height=780,
        min_size=(960, 640),
        background_color="#08060a",
    )
    try:
        from importlib.metadata import version
        log("pywebview " + version("pywebview"))
    except Exception:
        pass
    WINDOW.events.loaded += lambda: log("página carregada")
    log("iniciando janela")
    webview.start(_bind_drop, WINDOW)
    log("janela fechada")


if __name__ == "__main__":
    main()
