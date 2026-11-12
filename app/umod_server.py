"""Servidor compatível com o uMod v1: entrega ao jogo (d3d9.dll do uMod) os caminhos das texturas."""
import ctypes
import struct
import sys
import threading
import time

PIPE_IN = r"\\.\pipe\Game2uMod"    # o jogo escreve aqui (o nome dele)
PIPE_OUT = r"\\.\pipe\uMod2Game"   # nós escrevemos aqui (comandos)
BIG = 1 << 24
CONTROL_ADD_TEXTURE = 1
ERROR_PIPE_CONNECTED = 535


def build_messages(items):
    """items = [(hash, caminho)] -> bytes no formato MsgStruct{Control, Value, Hash} + caminho UTF-16."""
    parts, seen = [], set()
    for h, path in items:
        if h in seen:
            continue  # o primeiro pacote que trocou a textura vence
        seen.add(h)
        data = (path + "\0").encode("utf-16le")
        parts.append(struct.pack("<III", CONTROL_ADD_TEXTURE, len(data), h))
        parts.append(data)
    return b"".join(parts)


class UModServer:
    def __init__(self, log=print):
        self.log = log
        self.items = []
        self.thread = None
        self.lock = threading.Lock()
        self.delay = 0  # segundos de espera antes de enviar as texturas
        self.connected = 0  # quantas vezes um jogo já conectou (para o launcher conferir)
        self.ready = threading.Event()  # fica ligado quando os canais já existem

    def set_textures(self, items):
        with self.lock:
            self.items = list(items)

    def wait_ready(self, timeout=5.0):
        return self.ready.wait(timeout)

    def start(self):
        if sys.platform != "win32":
            return
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    # ---- interno (só roda no Windows) ----
    def _api(self):
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        H, D, P = wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p
        k.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, D, D, D, D, D, D, P]
        k.CreateNamedPipeW.restype = H
        k.ConnectNamedPipe.argtypes = [H, P]
        k.ConnectNamedPipe.restype = wintypes.BOOL
        k.ReadFile.argtypes = [H, P, D, ctypes.POINTER(D), P]
        k.ReadFile.restype = wintypes.BOOL
        k.WriteFile.argtypes = [H, P, D, ctypes.POINTER(D), P]
        k.WriteFile.restype = wintypes.BOOL
        k.DisconnectNamedPipe.argtypes = [H]
        k.CloseHandle.argtypes = [H]
        return k, D

    def _run(self):
        k, D = self._api()
        invalid = ctypes.c_void_p(-1).value
        while True:
            pin = pout = None
            self.ready.clear()
            try:
                pin = k.CreateNamedPipeW(PIPE_IN, 1, 0, 255, 1024, 1024, 0, None)       # entrada (INBOUND)
                pout = k.CreateNamedPipeW(PIPE_OUT, 2, 0, 255, BIG, BIG, 0, None)       # saída (OUTBOUND)
                if pin in (None, invalid) or pout in (None, invalid):
                    raise OSError("não consegui criar os canais (erro %d)" % ctypes.get_last_error())
                self.ready.set()
                self.log("uMod: canais criados, aguardando o jogo conectar")
                ok = k.ConnectNamedPipe(pin, None) or ctypes.get_last_error() == ERROR_PIPE_CONNECTED
                if not ok:
                    raise OSError("falha ao esperar o jogo")
                buf = ctypes.create_string_buffer(1024)
                n = D(0)
                k.ReadFile(pin, buf, 1024, ctypes.byref(n), None)  # nome do jogo
                name = buf.raw[:n.value].decode("utf-16le", "ignore").rstrip("\0")
                ok = k.ConnectNamedPipe(pout, None) or ctypes.get_last_error() == ERROR_PIPE_CONNECTED
                if not ok:
                    raise OSError("falha ao abrir o canal de saída")
                self.connected += 1
                if self.delay:
                    self.log(f"uMod: esperando {self.delay}s antes de enviar")
                    time.sleep(self.delay)
                with self.lock:
                    payload = build_messages(self.items)
                self.log(f"uMod: jogo conectado ({name}); enviando {len(payload)} bytes")
                if payload:
                    raw = ctypes.create_string_buffer(payload, len(payload))
                    sent = D(0)
                    if not k.WriteFile(pout, raw, len(payload), ctypes.byref(sent), None):
                        raise OSError("falha ao enviar texturas (erro %d)" % ctypes.get_last_error())
                    self.log(f"uMod: texturas enviadas ({sent.value} bytes)")
                # fica aqui até o jogo fechar o canal
                while k.ReadFile(pin, buf, 1024, ctypes.byref(n), None):
                    pass
                self.log("uMod: jogo desconectou")
            except Exception as e:
                self.log(f"uMod erro: {e!r}")
                time.sleep(1)
            finally:
                for h in (pin, pout):
                    if h not in (None, invalid):
                        try:
                            k.DisconnectNamedPipe(h)
                            k.CloseHandle(h)
                        except Exception:
                            pass
