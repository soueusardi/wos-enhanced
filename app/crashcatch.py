"""Abre o jogo sob um depurador mínimo e anota no launcher.log o ponto exato da queda (só Windows).
Uso: python crashcatch.py <exe> <pasta> [mascara_de_nucleos]   -> sai com o mesmo código de saída do jogo."""
import ctypes
import os
import struct
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wospatch

LOG = Path(os.environ.get("WOS_LOG") or (Path(__file__).resolve().parent.parent / "launcher.log"))
IS64 = struct.calcsize("P") == 8
U = 16 if IS64 else 12            # onde começa a união de dados do evento
P = 8 if IS64 else 4              # tamanho de um ponteiro
PCH = "Q" if IS64 else "I"
PFMT = "<" + PCH
TEXT_LO, TEXT_HI = 0x401000, 0xB78000   # código (.text) do jogo


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + "[captura] " + msg + "\n")
    except Exception:
        pass


def parse_event(raw):
    """Lê um DEBUG_EVENT cru (estrutura do tamanho do ponteiro do Python)."""
    code, pid, tid = struct.unpack_from("<III", raw, 0)
    ev = {"code": code, "pid": pid, "tid": tid}
    if code == 1:  # EXCEPTION_DEBUG_EVENT
        addr_off = U + 8 + P
        np_off = addr_off + P
        info_off = np_off + (8 if IS64 else 4)
        ev["ecode"] = struct.unpack_from("<I", raw, U)[0]
        ev["eaddr"] = struct.unpack_from(PFMT, raw, addr_off)[0]
        ev["info"] = struct.unpack_from("<" + PCH * 2, raw, info_off)
        ev["first"] = struct.unpack_from("<I", raw, U + (152 if IS64 else 80))[0]
    elif code in (3, 6):  # CREATE_PROCESS / LOAD_DLL: handle do arquivo + base (da imagem ou da DLL)
        ev["hfile"] = struct.unpack_from(PFMT, raw, U)[0]
        ev["base"] = struct.unpack_from(PFMT, raw, U + (3 * P if code == 3 else P))[0]
    elif code == 5:  # EXIT_PROCESS
        ev["exit"] = struct.unpack_from("<I", raw, U)[0]
    elif code == 8:  # OUTPUT_DEBUG_STRING
        ev["ptr"] = struct.unpack_from(PFMT, raw, U)[0]
        ev["uni"], ev["len"] = struct.unpack_from("<HH", raw, U + P)
    return ev


def parse_context(buf):
    """CONTEXT x86 (o mesmo layout no WOW64)."""
    names = {"edi": 156, "esi": 160, "ebx": 164, "edx": 168, "ecx": 172, "eax": 176, "ebp": 180, "eip": 184, "esp": 196}
    return {n: struct.unpack_from("<I", buf, o)[0] for n, o in names.items()}


def main():
    exe, cwd = sys.argv[1], sys.argv[2]
    mask = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    do_patch = (sys.argv[4] != "0") if len(sys.argv) > 4 else True
    skip_movies = (sys.argv[5] == "1") if len(sys.argv) > 5 else False
    t_launch = float(sys.argv[6]) if len(sys.argv) > 6 else time.time()
    pad_hex = sys.argv[7] if len(sys.argv) > 7 and sys.argv[7] != "-" else ""
    log(f"ajudante iniciou {time.time() - t_launch:.1f}s depois de o launcher pedir")
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    H, D, V = ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p
    k.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, V, V, wintypes.BOOL, D, V, wintypes.LPCWSTR, V, V]
    k.CreateProcessW.restype = wintypes.BOOL
    k.WaitForDebugEvent.argtypes = [V, D]
    k.WaitForDebugEvent.restype = wintypes.BOOL
    k.ContinueDebugEvent.argtypes = [D, D, D]
    k.OpenThread.argtypes = [D, wintypes.BOOL, D]
    k.OpenThread.restype = H
    k.ReadProcessMemory.argtypes = [H, V, V, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    k.CloseHandle.argtypes = [H]
    k.SetProcessAffinityMask.argtypes = [H, ctypes.c_size_t]
    k.GetFinalPathNameByHandleW.argtypes = [H, wintypes.LPWSTR, D, D]
    k.WaitForSingleObject.argtypes = [H, D]
    k.VirtualAllocEx.argtypes = [H, V, ctypes.c_size_t, D, D]
    k.VirtualAllocEx.restype = V
    k.VirtualProtectEx.argtypes = [H, V, ctypes.c_size_t, D, ctypes.POINTER(D)]
    k.VirtualProtectEx.restype = wintypes.BOOL
    k.WriteProcessMemory.argtypes = [H, V, V, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    k.WriteProcessMemory.restype = wintypes.BOOL
    k.FlushInstructionCache.argtypes = [H, V, ctypes.c_size_t]
    getctx = getattr(k, "Wow64GetThreadContext", None) or k.GetThreadContext
    getctx.argtypes = [H, V]
    setctx = getattr(k, "Wow64SetThreadContext", None) or k.SetThreadContext
    setctx.argtypes = [H, V]

    os.environ["_NO_DEBUG_HEAP"] = "1"  # sem o "heap de depuração", que mudaria o comportamento do jogo
    si = ctypes.create_string_buffer(104 if IS64 else 68)
    struct.pack_into("<I", si, 0, len(si))
    pi = ctypes.create_string_buffer(24 if IS64 else 16)
    cmd = ctypes.create_unicode_buffer(f'"{exe}"')
    if not k.CreateProcessW(exe, cmd, None, None, False, 0x2, None, cwd, si, pi):  # DEBUG_ONLY_THIS_PROCESS
        log(f"não consegui abrir o jogo (erro {ctypes.get_last_error()})")
        sys.exit(1)
    hproc = struct.unpack_from(PFMT, pi.raw, 0)[0]
    if mask:
        k.SetProcessAffinityMask(hproc, mask)
    try:
        k.DebugSetProcessKillOnExit(False)
    except Exception:
        pass

    def rpm(addr, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        k.ReadProcessMemory(hproc, addr, buf, n, ctypes.byref(got))
        return buf.raw[:got.value]

    dlls, strings, av_count, exit_code = deque(maxlen=25), deque(maxlen=8), 0, 1
    ev = ctypes.create_string_buffer(256)

    movie = {"on": False}

    def write_code(addr, data):
        """Escreve bytes de código no jogo (troca a proteção da página só por um instante)."""
        old, done = D(0), ctypes.c_size_t(0)
        ok = k.VirtualProtectEx(hproc, addr, len(data), 0x40, ctypes.byref(old))
        ok = ok and k.WriteProcessMemory(hproc, addr, data, len(data), ctypes.byref(done))
        if ok:
            k.VirtualProtectEx(hproc, addr, len(data), old.value, ctypes.byref(old))
            k.FlushInstructionCache(hproc, addr, len(data))
        return bool(ok)

    def skip_movies_on():
        """Põe uma parada (int3) onde o jogo abre vídeos; on_movie_bp decide pelo nome (veja wospatch.movie_bp)."""
        if rpm(wospatch.MOVIE_SITE, 6) != wospatch.MOVIE_ORIG:
            log("vídeos de abertura NÃO pulados: este não parece ser o executável 1.1.1.11540 esperado")
            return
        if write_code(wospatch.MOVIE_SITE, b"\xcc"):
            movie["on"] = True
            log("vídeos de abertura serão pulados: " + ", ".join(wospatch.INTRO_MOVIES))
        else:
            log(f"não consegui pular os vídeos (erro {ctypes.get_last_error()})")

    def on_movie_bp(e):
        th = k.OpenThread(0x1FFFFF, False, e["tid"])
        ctx = ctypes.create_string_buffer(716 + 16)
        struct.pack_into("<I", ctx, 0, 0x10007)
        try:
            if not getctx(th, ctx):
                log(f"vídeo: não consegui ler os registradores (erro {ctypes.get_last_error()})")
                return
            esp = struct.unpack_from("<I", ctx, 196)[0]
            rd = lambda a: struct.unpack("<I", rpm(a, 4).ljust(4, b"\0"))[0]
            rs = lambda a: rpm(a, 260).split(b"\0")[0].decode("latin1", "replace")

            def wr(a, v):
                done = ctypes.c_size_t(0)
                k.WriteProcessMemory(hproc, a, struct.pack("<I", v), 4, ctypes.byref(done))

            path, skipped, regs = wospatch.movie_bp(esp, rd, rs, wr, True)
            for name, off in (("eax", 176), ("eip", 184), ("esp", 196)):
                if name in regs:
                    struct.pack_into("<I", ctx, off, regs[name] & 0xFFFFFFFF)
            if not setctx(th, ctx):
                log(f"vídeo: não consegui ajustar os registradores (erro {ctypes.get_last_error()})")
                return
            log(f"vídeo {path}: {'pulado' if skipped else 'tocando'}")
        finally:
            k.CloseHandle(th)

    def pad_on(table):
        """Troca de botões do controle (trecho nosso no trampolim do XInputGetState; veja wospatch.build_pad_cave)."""
        if rpm(wospatch.XINPUT_THUNK, 6) != wospatch.XINPUT_THUNK_ORIG:
            log("botões do controle NÃO trocados: este não parece ser o executável 1.1.1.11540 esperado")
            return
        cave = k.VirtualAllocEx(hproc, None, 4096, 0x3000, 0x40)
        done = ctypes.c_size_t(0)
        code = wospatch.build_pad_cave(cave, table) if cave else b""
        if cave and k.WriteProcessMemory(hproc, cave, code, len(code), ctypes.byref(done)) and \
                write_code(wospatch.XINPUT_THUNK, wospatch.pad_hook_bytes(cave)):
            k.FlushInstructionCache(hproc, cave, len(code))
            log("botões do controle trocados conforme as Opções")
        else:
            log(f"não consegui trocar os botões do controle (erro {ctypes.get_last_error()})")

    def apply_patch(base):
        """Reparo em memória (veja wospatch.py): cria o registro global do jogo antes do WinMain."""
        if base != wospatch.IMAGE_BASE:
            log(f"reparo NÃO aplicado: o jogo carregou em {base:#x}, não em {wospatch.IMAGE_BASE:#x}")
            return
        if rpm(wospatch.HOOK_SITE, 5) != wospatch.HOOK_ORIG:
            log("reparo NÃO aplicado: este não parece ser o executável 1.1.1.11540 esperado")
            return
        cave = k.VirtualAllocEx(hproc, None, 4096, 0x3000, 0x40)  # MEM_COMMIT|MEM_RESERVE, EXECUTE_READWRITE
        if not cave:
            log(f"reparo NÃO aplicado: sem memória para o código (erro {ctypes.get_last_error()})")
            return
        code = wospatch.build_cave(cave)
        done = ctypes.c_size_t(0)
        ok = k.WriteProcessMemory(hproc, cave, code, len(code), ctypes.byref(done))
        old = D(0)
        ok = ok and k.VirtualProtectEx(hproc, wospatch.HOOK_SITE, 5, 0x40, ctypes.byref(old))
        hook = wospatch.hook_bytes(cave)
        ok = ok and k.WriteProcessMemory(hproc, wospatch.HOOK_SITE, hook, 5, ctypes.byref(done))
        if ok:
            k.VirtualProtectEx(hproc, wospatch.HOOK_SITE, 5, old.value, ctypes.byref(old))
            k.FlushInstructionCache(hproc, wospatch.HOOK_SITE, 5)
            k.FlushInstructionCache(hproc, cave, len(code))
            log(f"reparo aplicado (código novo em {cave:#x})")
        else:
            log(f"reparo FALHOU (erro {ctypes.get_last_error()})")

    def report_av(e):
        nonlocal av_count
        av_count += 1
        if e["first"] and av_count > 12:
            return
        th = k.OpenThread(0x1FFFFF, False, e["tid"])
        ctx = ctypes.create_string_buffer(716 + 16)
        struct.pack_into("<I", ctx, 0, 0x10007)
        r = parse_context(ctx.raw) if getctx(th, ctx) else {}
        k.CloseHandle(th)
        kind = {0: "leitura", 1: "escrita", 8: "execução"}.get(e["info"][0], "?")
        head = ("1ª chance" if e["first"] else "FATAL") + f" violação de acesso em {e['eaddr']:#x}: {kind} do endereço {e['info'][1]:#x}"
        if r:
            head += " | " + " ".join(f"{n}={v:#x}" for n, v in r.items())
            stack = rpm(r["esp"], 128)
            words = struct.unpack("<%dI" % (len(stack) // 4), stack[:len(stack) // 4 * 4])
            rets = [f"{w:#x}" for w in words if TEXT_LO <= w < TEXT_HI]
            head += " | pilha: " + " ".join(f"{w:#x}" for w in words[:12]) + " | endereços de código na pilha: " + " ".join(rets[:10])
            mem = rpm(r["ecx"], 16) if r["ecx"] > 0x10000 else b""
            if mem:
                head += " | bytes em ecx: " + mem.hex()
        log(head)
        if not e["first"]:
            log("últimas DLLs carregadas: " + ", ".join(dlls))
            log("últimas mensagens de depuração: " + " / ".join(strings))

    t0 = time.time()
    while True:
        if not k.WaitForDebugEvent(ev, 1000):
            if k.WaitForSingleObject(hproc, 0) == 0:
                break
            continue
        e = parse_event(ev.raw)
        cont = 0x00010002  # DBG_CONTINUE
        try:
            if e["code"] == 1:
                if e["ecode"] in (0x80000003, 0x4000001F) and movie["on"] and e["eaddr"] == wospatch.MOVIE_SITE:
                    on_movie_bp(e)          # o jogo vai abrir um vídeo: decide pelo nome
                elif e["ecode"] not in (0x80000003, 0x4000001F):
                    cont = 0x80010001  # DBG_EXCEPTION_NOT_HANDLED: o jogo trata como trataria sem depurador
                    if e["ecode"] == 0xC0000005:
                        report_av(e)
            elif e["code"] in (3, 6):
                name = ""
                if e["hfile"]:
                    buf = ctypes.create_unicode_buffer(520)
                    if k.GetFinalPathNameByHandleW(e["hfile"], buf, 520, 0):
                        name = os.path.basename(buf.value)
                    k.CloseHandle(e["hfile"])
                if e["code"] == 3:
                    log(f"jogo criado {time.time() - t_launch:.1f}s depois de o launcher pedir")
                if e["code"] == 3 and do_patch:
                    apply_patch(e["base"])
                    if skip_movies:
                        skip_movies_on()
                    if pad_hex:
                        pad_on(bytes.fromhex(pad_hex))
                if e["code"] == 6:
                    dlls.append(name or hex(e["base"]))
            elif e["code"] == 8 and e["ptr"]:
                raw = rpm(e["ptr"], min(e["len"], 200) * (2 if e["uni"] else 1))
                strings.append(raw.decode("utf-16le" if e["uni"] else "latin1", "ignore").strip("\0\r\n ")[:120])
            elif e["code"] == 5:
                exit_code = e["exit"]
        except Exception as ex:
            log(f"erro ao tratar evento {e.get('code')}: {ex!r}")
        k.ContinueDebugEvent(e["pid"], e["tid"], cont)
        if e["code"] == 5:
            break
    log(f"jogo terminou com código {exit_code:#x}")
    sys.exit(exit_code & 0xFFFFFFFF)


def run():
    try:
        main()
    except SystemExit:
        raise
    except Exception as ex:
        log(f"erro no depurador: {ex!r}")
        sys.exit(1)


if __name__ == "__main__":
    run()
