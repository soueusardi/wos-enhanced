"""Lê o modelo e as texturas do Spider-Man direto da cópia do jogo do usuário (MEGACITY.PCPACK).

Engenharia reversa própria, feita só a partir dos arquivos do jogo (formato descrito em docs/formato_pcpack.md).
Sem dependências: só a biblioteca padrão do Python. Nada é gravado na pasta do jogo; o resultado vai para cache/gameassets.
"""
import json
import math
import struct
import zlib
from pathlib import Path

FORMAT_VERSION = 4          # mude se o conteúdo do cache mudar (força extrair de novo). 4 = poses das animações do jogo (poses.json)
PACK_NAME = "MEGACITY.PCPACK"
VIEWER_HEIGHT = 1.9437      # o visualizador (web/pose.js) foi medido num boneco com esta altura
MESH_NAME = "ch_spiderman_rvb000"
SKEL_NAME = "ch_spiderman_rvbskeleton_ch_spiderman_rvb000"
TEXTURES = {                # nome no jogo -> arquivo no cache ( _n = mapa de relevo )
    "spiderman_redsuit_tex1_dif": "upperbody",
    "spiderman_redsuit_tex2_dif": "lowerbody",
    "spiderman_redsuit_tex1_nor": "upperbody_n",
    "spiderman_redsuit_tex2_nor": "lowerbody_n",
    "spiderman_blacksuit1_tex1_dif": "bsuit_upperbody",
    "spiderman_blacksuit1_tex2_dif": "bsuit_lowerbody",
    "spiderman_blacksuit1_tex1_nor": "bsuit_upperbody_n",
    "spiderman_blacksuit1_tex2_nor": "bsuit_lowerbody_n",
}
OUT_FILES = ["spiderman.obj", "skeleton.json", "poses.json"] + [f"{v}.png" for v in TEXTURES.values()]
# poses do visualizador tiradas das animações originais do jogo: nome da pose -> (animação, quadro)
GAME_ANIM_POSES = {"crossed": ("smrvictoryarmscrossed", 35), "hanging": ("smrhang", 0)}


class FormatError(Exception):
    pass


# ---------------------------------------------------------------- LZO1X (descompressão)
def lzo1x_decompress(src, start, out):
    """Descomprime um fluxo LZO1X a partir de src[start] acrescentando em `out` (bytearray).
    A janela continua a partir do que já está em `out` (os blocos do .PCPACK são encadeados). Devolve a posição final."""
    ip = start
    n = len(src)

    def copy_match(dist, length):
        mpos = len(out) - dist
        if mpos < 0:
            raise FormatError("referência LZO fora da janela")
        if dist >= length:
            out.extend(out[mpos:mpos + length])
        else:
            for i in range(length):
                out.append(out[mpos + i])

    t = src[ip]
    state = 0                       # 0 = ler instrução; 1 = depois de literais longos; 2 = copiar t literais e ler match
    if t > 17:
        ip += 1
        t -= 17
        if t < 4:
            state = 2
        else:
            out.extend(src[ip:ip + t]); ip += t
            state = 1
    while True:
        if ip >= n:
            raise FormatError("fluxo LZO terminou sem marcador de fim")
        if state == 2:              # t literais (1..3) e depois um match
            out.extend(src[ip:ip + t]); ip += t
            t = src[ip]; ip += 1
        else:
            t = src[ip]; ip += 1
            if state == 0 and t < 16:          # sequência de literais
                if t == 0:
                    while src[ip] == 0:
                        t += 255; ip += 1
                    t += 15 + src[ip]; ip += 1
                t += 3
                out.extend(src[ip:ip + t]); ip += t
                state = 1
                continue
            if state == 1 and t < 16:          # match curto logo depois de literais
                dist = 1 + 0x0800 + (t >> 2) + (src[ip] << 2); ip += 1
                copy_match(dist, 3)
                t = src[ip - 2] & 3
                state = 2 if t else 0
                continue
        # match
        if t >= 64:
            dist = 1 + ((t >> 2) & 7) + (src[ip] << 3); ip += 1
            length = (t >> 5) + 1
        elif t >= 32:
            length = t & 31
            if length == 0:
                while src[ip] == 0:
                    length += 255; ip += 1
                length += 31 + src[ip]; ip += 1
            v = src[ip] | (src[ip + 1] << 8); ip += 2
            dist = 1 + (v >> 2)
            length += 2
        elif t >= 16:
            dist = (t & 8) << 11
            length = t & 7
            if length == 0:
                while src[ip] == 0:
                    length += 255; ip += 1
                length += 7 + src[ip]; ip += 1
            v = src[ip] | (src[ip + 1] << 8); ip += 2
            dist += v >> 2
            if dist == 0:
                return ip                       # fim do fluxo
            dist += 0x4000
            length += 2
        else:
            dist = 1 + (t >> 2) + (src[ip] << 2); ip += 1
            length = 2
        copy_match(dist, length)
        t = src[ip - 2] & 3
        state = 2 if t else 0


def unpack_pack(path, progress=None):
    """Lê um .PCPACK (blocos "NCH" de 512 KB) e devolve o conteúdo descomprimido."""
    src = Path(path).read_bytes()
    out = bytearray()
    o = 0
    while o + 0x20 <= len(src) and src[o:o + 4] == b"NCH\0":
        _, csz, _, usz, uoff, _, tot, _ = struct.unpack_from("<4s7I", src, o)
        if uoff != len(out):
            raise FormatError("bloco NCH fora de ordem")
        before = len(out)
        end = lzo1x_decompress(src, o + 0x20, out)
        if len(out) - before != usz or end != o + 0x20 + csz:
            raise FormatError("bloco NCH com tamanho inesperado")
        o = (o + tot + 0x7FFFF) & ~0x7FFFF
        if progress:
            progress(min(o, len(src)) / len(src))
    if not out:
        raise FormatError("não é um .PCPACK conhecido")
    return out


# ---------------------------------------------------------------- APKF (índice dos recursos)
def name_hash(name):
    h = 0
    for c in name.lower().encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


class Apkf:
    def __init__(self, d):
        self.d = d
        dirsize = struct.unpack_from("<I", d, 0x18)[0]
        self.base = None
        for o in range(0x30, min(len(d) - 44, 0x20 + dirsize + 0x4000), 4):
            w = struct.unpack_from("<11I", d, o)
            if w[1] == 0x19 and w[3] == w[4] and w[10] == 5 and d[w[2]:w[2] + 4] == b"APKF":
                self.base = w[2]
                break
        if self.base is None:
            raise FormatError("contêiner APKF não encontrado")
        A = self.base
        self.hdr_size = struct.unpack_from("<I", d, A + 0x14)[0]
        self.sections = {}
        for k in range(16):
            ro = A + 0x1C + k * 0x1C
            tag, _a, _b, idx, n, _esz, fl = struct.unpack_from("<4s6I", d, ro)
            if not idx or tag == b"\0\0\0\0":
                break
            st = ro + 12 + idx
            w = 4 if fl == 0x01000004 else 3
            self.sections[tag.rstrip(b"\0").decode("latin1")] = [struct.unpack_from(f"<{w}I", d, st + 4 * w * i) for i in range(n)]
        it = d.find(b"IMG\0", A + self.hdr_size - 0x40, A + self.hdr_size + 0x100)
        if it < 0:
            raise FormatError("tabela IMG/PHYS não encontrada")
        self.img_base = it + 0x30
        self.phys_base = it - 4 + 0x30 + struct.unpack_from("<I", d, it + 0x2C)[0]

    def names(self):
        """hash -> nome, a partir dos textos do cabeçalho do APKF (cada sufixo de cada texto vira um candidato)"""
        if getattr(self, "_names", None) is None:
            import re
            out = {}
            for m in re.finditer(rb"[\x20-\x7e]{2,}", self.d[self.base:self.base + self.hdr_size]):
                txt = m.group().decode("latin1")
                for i in range(len(txt)):
                    out.setdefault(name_hash(txt[i:]), txt[i:])
            self._names = out
        return self._names

    def img(self, ptr):
        return self.img_base + ptr * 4

    def phys(self, addr):
        return self.phys_base + ((addr * 4) & 0x0FFFFFFF)

    def records(self, tag):
        """[(hash, posição do metadado, tamanho do metadado, entrada)] na ordem do índice.
        Os metadados ficam um atrás do outro (às vezes com alguns bytes de alinhamento); o hash fica em +4."""
        ents = self.sections[tag]
        p = self.d.find(struct.pack("<I", ents[0][1]), self.base + self.hdr_size) - 4
        if p < 0:
            raise FormatError(f"seção {tag} não encontrada")
        out = []
        for e in ents:
            if struct.unpack_from("<I", self.d, p + 4)[0] != e[1]:
                q = self.d.find(struct.pack("<I", e[1]), p + 4, p + 4 + 0x40)
                if q < 0:
                    raise FormatError(f"metadado de {tag} fora do lugar")
                p = q - 4
            out.append((e[1], p, e[2], e))
            p += e[2]
        return out


# ---------------------------------------------------------------- texturas (DXT -> PNG)
def _c565(c):
    r = (c >> 11) & 31; g = (c >> 5) & 63; b = c & 31
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def decode_dxt(data, w, h, fmt):
    """Mip 0 de uma textura DXT1/DXT3/DXT5 -> bytes RGBA."""
    out = bytearray(w * h * 4)
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    bs = 8 if fmt == b"DXT1" else 16
    o = 0
    for by in range(bh):
        for bx in range(bw):
            if fmt == b"DXT5":
                a0, a1 = data[o], data[o + 1]
                ab = int.from_bytes(data[o + 2:o + 8], "little")
                if a0 > a1:
                    al = [a0, a1] + [((6 - i) * a0 + (i + 1) * a1) // 7 for i in range(6)]
                else:
                    al = [a0, a1] + [((4 - i) * a0 + (i + 1) * a1) // 5 for i in range(4)] + [0, 255]
                co = o + 8
            elif fmt == b"DXT3":
                ab = int.from_bytes(data[o:o + 8], "little"); co = o + 8
            else:
                co = o
            c0, c1, bits = struct.unpack_from("<HHI", data, co)
            a, b = _c565(c0), _c565(c1)
            if c0 > c1 or fmt != b"DXT1":
                pal = [a, b, tuple((2 * x + y) // 3 for x, y in zip(a, b)), tuple((x + 2 * y) // 3 for x, y in zip(a, b))]
                punch = False
            else:
                pal = [a, b, tuple((x + y) // 2 for x, y in zip(a, b)), (0, 0, 0)]
                punch = True
            for py in range(4):
                y = by * 4 + py
                if y >= h:
                    break
                row = (y * w + bx * 4) * 4
                for px in range(4):
                    if bx * 4 + px >= w:
                        break
                    i = py * 4 + px
                    ci = (bits >> (2 * i)) & 3
                    r, g, bb = pal[ci]
                    if fmt == b"DXT5":
                        al_ = al[(ab >> (3 * i)) & 7]
                    elif fmt == b"DXT3":
                        al_ = ((ab >> (4 * i)) & 15) * 17
                    else:
                        al_ = 0 if (punch and ci == 3) else 255
                    q = row + px * 4
                    out[q] = r; out[q + 1] = g; out[q + 2] = bb; out[q + 3] = al_
            o += bs
    return out


def mip0_size(w, h, fmt):
    return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * (8 if fmt == b"DXT1" else 16)


def normal_to_rgb(rgba):
    """Mapa de relevo "DXT5nm" do jogo (X no alfa, Y no verde) -> RGB comum (Z calculado)."""
    n = len(rgba) // 4
    out = bytearray(n * 4)
    for i in range(n):
        x = rgba[i * 4 + 3]; y = rgba[i * 4 + 1]
        fx = x / 127.5 - 1; fy = y / 127.5 - 1
        z = math.sqrt(max(0.0, 1 - fx * fx - fy * fy))
        out[i * 4] = x; out[i * 4 + 1] = y; out[i * 4 + 2] = min(255, round((z + 1) * 127.5)); out[i * 4 + 3] = 255
    return out


def write_png_rgb(path, w, h, rgba):
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        line = rgba[y * w * 4:(y + 1) * w * 4]
        rows += bytes(line[i] for i in range(len(line)) if i % 4 != 3)

    def chunk(t, data):
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b""))
    Path(path).write_bytes(png)


def umod_crc(data):
    """Mesmo hash que o uMod/TexMod usa para identificar a textura."""
    return zlib.crc32(data) ^ 0xFFFFFFFF


def find_textures(ap, wanted):
    """{nome: (w, h, fmt, bytes do mip 0)} das texturas pedidas."""
    found = {}
    hashes = {name_hash(n): n for n in wanted}
    cum = 0
    for h, p, _hs, e in ap.records("TEX"):
        if h in hashes:
            w, hh = struct.unpack_from("<2I", ap.d, p + 0x10)
            fmt = bytes(ap.d[p + 0x20:p + 0x24])
            if fmt not in (b"DXT1", b"DXT3", b"DXT5"):
                raise FormatError(f"formato de textura não suportado: {fmt!r}")
            off = ap.phys_base + cum
            found[hashes[h]] = (w, hh, fmt, bytes(ap.d[off:off + mip0_size(w, hh, fmt)]))
        cum += e[3]
    return found


# ---------------------------------------------------------------- malha
DECL_SIZE = {0: 4, 1: 8, 2: 12, 3: 16, 4: 4, 5: 4, 6: 4, 7: 8, 8: 4, 9: 4, 10: 8, 11: 4, 12: 8, 15: 4, 16: 8}


def read_mesh(ap, name):
    """Lê a malha `name`: devolve lista de submalhas {material, pos, uv, nrm, tris} em coordenadas do jogo."""
    d = ap.d
    h = name_hash(name)
    meta = next((p for hh, p, _s, _e in ap.records("MESH") if hh == h), None)
    if meta is None:
        raise FormatError(f"malha {name} não encontrada")
    nsub = struct.unpack_from("<I", d, meta + 0x0C)[0]
    cx, cy, cz, _r, hx, hy, hz = struct.unpack_from("<7f", d, meta + 0x20)
    arr = ap.img(struct.unpack_from("<I", d, meta + 0x10)[0])
    mats = {p: hh for hh, p, _s, _e in ap.records("MAT")}
    mat_starts = sorted(mats)
    subs = []
    for i in range(nsub):
        s = ap.img(struct.unpack_from("<I", d, arr + 8 * i + 4)[0])
        mat_ptr, _bp, nbones, vb, _z, nv, _x, ib, _z2, ni, isz, _p2, prim = struct.unpack_from("<13I", d, s + 0x20)
        if isz != 2 or prim not in (4, 5):
            raise FormatError(f"submalha com índices/primitiva desconhecidos ({isz}, {prim})")
        q = (s + 0x58 + 2 * nbones + 3) & ~3
        stride, decl_ptr = struct.unpack_from("<2I", d, q)
        decl = ap.img(decl_ptr)
        el = {}
        for k in range(32):
            st, off, typ, _m, usage, uidx = struct.unpack_from("<HHBBBB", d, decl + 8 * k)
            if st == 0xFF:
                break
            el.setdefault((usage, uidx), (off, typ))
        if (0, 0) not in el or el[(0, 0)][1] != 10 or max(o + DECL_SIZE.get(t, 0) for o, t in el.values()) != stride:
            raise FormatError("declaração de vértices inesperada")
        mp = ap.img(mat_ptr)
        mstart = max((m for m in mat_starts if m <= mp), default=None)
        vbo, ibo = ap.phys(vb), ap.phys(ib)
        pal = struct.unpack_from(f"<{nbones}H", d, s + 0x58)       # ossos usados por esta submalha (índices no SKEL)
        pos, uv, nrm, skin = [], [], [], []
        po = el[(0, 0)][0]
        wo, wt = el.get((1, 0), (None, None))                       # pesos (UBYTE4N)
        io, it = el.get((2, 0), (None, None))                       # índices de osso (UBYTE4, na lista da submalha)
        uo, ut = el.get((5, 0), (None, None))
        no, nt = el.get((3, 0), (None, None))
        for k in range(nv):
            o = vbo + stride * k
            x, y, z = struct.unpack_from("<3h", d, o + po)
            pos.append((cx + x / 32767 * hx, cy + y / 32767 * hy, cz + z / 32767 * hz))
            if uo is not None:
                uv.append(struct.unpack_from("<2e" if ut == 15 else "<2f", d, o + uo))
            if no is not None:
                nrm.append(struct.unpack_from("<3e" if nt == 16 else "<3f", d, o + no))
            if wo is not None and io is not None and wt == 8 and it == 5:
                ws = d[o + wo:o + wo + 4]; ix = d[o + io:o + io + 4]
                skin.append(tuple((pal[ix[j]], ws[j]) for j in range(4) if ws[j]))
        idx = struct.unpack_from(f"<{ni}H", d, ibo)
        if max(idx) >= nv:
            raise FormatError("índices fora do intervalo (endereço errado?)")
        # O Direct3D usa triângulos no sentido horário como "frente"; o OBJ/three.js usa anti-horário.
        # Por isso cada triângulo sai invertido (sem isso o boneco aparece "do avesso", translúcido).
        tris = []
        if prim == 5:
            for k in range(ni - 2):
                a, b, c = idx[k], idx[k + 1], idx[k + 2]
                if a == b or b == c or a == c:
                    continue
                tris.append((a, b, c) if k & 1 else (a, c, b))
        else:
            tris = [(idx[k], idx[k + 2], idx[k + 1]) for k in range(0, ni - 2, 3)]
        subs.append({"material": mats.get(mstart), "pos": pos, "uv": uv, "nrm": nrm, "tris": tris, "skin": skin})
    return subs


def _minv4(m):
    """inversa de uma matriz 4×4 (lista de 16, por linhas)"""
    a = [list(m[4 * i:4 * i + 4]) + [1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    for c in range(4):
        pr = max(range(c, 4), key=lambda r: abs(a[r][c]))
        a[c], a[pr] = a[pr], a[c]
        pv = a[c][c]
        if abs(pv) < 1e-12:
            raise FormatError("matriz de osso sem inversa")
        a[c] = [x / pv for x in a[c]]
        for r in range(4):
            if r != c:
                f = a[r][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return [a[i][4 + j] for i in range(4) for j in range(4)]


def read_skeleton(ap, name=SKEL_NAME):
    """Esqueleto do jogo: [{name, parent, world}] com `world` = matriz de repouso osso->modelo (4x4, por linhas, estilo D3D:
    vetor linha, translação na 4ª linha). O arquivo guarda a INVERSA (modelo->osso); a 4ª coluna dela vem com lixo."""
    d = ap.d
    h = name_hash(name)
    p = next((p for hh, p, _s, _e in ap.records("SKEL") if hh == h), None)
    if p is None:
        raise FormatError(f"esqueleto {name} não encontrado")
    n = struct.unpack_from("<I", d, p + 8)[0]
    if not 1 <= n <= 256:
        raise FormatError("número de ossos estranho")
    names = ap.names()
    bones = []
    for k in range(n):
        r = p + 0x10 + 0x90 * k
        inv = list(struct.unpack_from("<16f", d, r + 0x40))
        inv[3] = inv[7] = inv[11] = 0.0
        inv[15] = 1.0
        _tag, bh, par = struct.unpack_from("<3I", d, r + 0x80)
        bones.append({"name": names.get(bh, f"osso_{bh:08x}"), "parent": -1 if par == 0xFFFFFFFF else par,
                      "world": _minv4(inv)})
    for b in bones:
        if b["parent"] >= n:
            raise FormatError("pai de osso fora do intervalo")
    return bones


def skeleton_json(bones, subs, xf):
    """Esqueleto + pesos no espaço do visualizador (mesma escala/posição do OBJ). Por osso: pai, posição e os 3 eixos
    (normalizados) em coordenadas de repouso. Pesos por vértice do OBJ (mesma ordem das linhas 'v')."""
    k, cx, ly = xf
    out = []
    for b in bones:
        w = b["world"]
        axes = []
        for i in range(3):
            v = w[4 * i:4 * i + 3]
            ln = math.sqrt(sum(c * c for c in v)) or 1.0
            axes.append([round(c / ln, 6) for c in v])
        pos = [round((w[12] - cx) * k, 6), round((w[13] - ly) * k, 6), round(w[14] * k, 6)]
        out.append({"name": b["name"], "parent": b["parent"], "pos": pos, "x": axes[0], "y": axes[1], "z": axes[2]})
    idx, wts = [], []
    for s in subs:
        if len(s["skin"]) != len(s["pos"]):
            raise FormatError("submalha sem pesos de osso")
        for sk in s["skin"]:
            sk = list(sk)[:4] + [(0, 0)] * (4 - len(sk))
            idx += [j for j, _w in sk]
            wts += [w for _j, w in sk]
    return {"bones": out, "skin_index": idx, "skin_weight": wts}


def mesh_to_obj(subs, lower_material):
    """OBJ com 2 materiais na ordem que o visualizador espera: 'upper' (cima + olhos) e depois 'lower'."""
    allpos = [p for s in subs for p in s["pos"]]
    lo = [min(p[j] for p in allpos) for j in range(3)]
    hi = [max(p[j] for p in allpos) for j in range(3)]
    k = VIEWER_HEIGHT / (hi[1] - lo[1])
    cx = (lo[0] + hi[0]) / 2
    lines = ["# Spider-Man (ch_spiderman_rvb000) lido da copia do jogo do usuario pelo Web of Shadows Launcher",
             f"# escala {k:.5f} (altura normalizada para {VIEWER_HEIGHT})"]
    vt, vn = [], []
    base, groups = 0, {"upper": [], "lower": []}
    for s in subs:
        n = len(s["pos"])
        for x, y, z in s["pos"]:
            lines.append(f"v {(x - cx) * k:.6f} {(y - lo[1]) * k:.6f} {z * k:.6f}")
        vmin = math.floor(min((v for _u, v in s["uv"]), default=0))
        for u, v in (s["uv"] or [(0, 0)] * n):
            vt.append(f"vt {u:.6f} {1 - (v - vmin):.6f}")
        for nx, ny, nz in (s["nrm"] or [(0, 1, 0)] * n):
            vn.append(f"vn {nx:.4f} {ny:.4f} {nz:.4f}")
        g = "lower" if s["material"] == lower_material else "upper"
        groups[g] += [(a + base + 1, b + base + 1, c + base + 1) for a, b, c in s["tris"]]
        base += n
    lines += vt + vn
    for g in ("upper", "lower"):
        lines.append(f"usemtl {g}")
        lines += [f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}" for a, b, c in groups[g]]
    return "\n".join(lines) + "\n", sum(len(v) for v in groups.values()), (k, cx, lo[1])


# ---------------------------------------------------------------- extração completa
def pack_path(game_dir, exe=""):
    cands = []
    if exe:
        cands.append(Path(exe).parent / "packs" / PACK_NAME)
    g = Path(game_dir)
    cands += [g / "image" / "pc" / "packs" / PACK_NAME, g / "packs" / PACK_NAME, g / PACK_NAME]
    return next((c for c in cands if c.is_file()), None)


def source_id(pack):
    st = Path(pack).stat()
    return {"pack": str(pack), "size": st.st_size, "mtime": int(st.st_mtime), "format": FORMAT_VERSION}


def is_ready(out_dir, pack=None):
    info = Path(out_dir) / "info.json"
    if not info.is_file() or not all((Path(out_dir) / f).is_file() for f in OUT_FILES):
        return False
    try:
        old = json.loads(info.read_text(encoding="utf-8")).get("source", {})
        if old.get("format") != FORMAT_VERSION:
            return False          # cache de uma versão antiga do leitor
        if pack is None:
            return True
        new = source_id(pack)
        return all(old.get(k) == new[k] for k in ("size", "mtime", "format"))
    except Exception:
        return False


def extract(pack, out_dir, progress=None, log=print):
    """Extrai modelo + texturas para out_dir. progress(fração 0..1, etapa). Grava tudo numa pasta temporária e só
    troca no final, para nunca deixar um cache pela metade."""
    out_dir = Path(out_dir)
    tmp = out_dir.with_name(out_dir.name + ".tmp")
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.iterdir():
        f.unlink()
    say = progress or (lambda f, s: None)
    say(0.0, "unpack")
    d = unpack_pack(pack, lambda f: say(0.70 * f, "unpack"))
    say(0.70, "index")
    ap = Apkf(d)
    subs = read_mesh(ap, MESH_NAME)
    # o material da parte de baixo é o que termina em "tex2" (ch_spiderman_rvbtex2)
    lower = next((s["material"] for s in subs if s["material"] == name_hash("ch_spiderman_rvbtex2")), None)
    if lower is None:
        raise FormatError("material da parte de baixo não encontrado")
    obj, nfaces, xf = mesh_to_obj(subs, lower)
    (tmp / "spiderman.obj").write_text(obj, encoding="utf-8")
    bones = read_skeleton(ap)
    skj = skeleton_json(bones, subs, xf)
    (tmp / "skeleton.json").write_text(json.dumps(skj, separators=(",", ":")), encoding="utf-8")
    log(f"gameassets: esqueleto com {len(bones)} ossos")
    try:   # poses das animações originais; se falhar, o visualizador usa as poses feitas à mão
        import gameanim
        poses = gameanim.extract_poses(ap, bones, skj, GAME_ANIM_POSES, log)
    except Exception as e:
        log(f"gameassets: poses do jogo não extraídas ({e!r}); ficam as poses feitas à mão")
        poses = {}
    (tmp / "poses.json").write_text(json.dumps(poses, separators=(",", ":")), encoding="utf-8")
    log(f"gameassets: malha com {sum(len(s['pos']) for s in subs)} vértices, {nfaces} triângulos, {len(subs)} submalhas")
    say(0.75, "textures")
    tex = find_textures(ap, TEXTURES)
    missing = [n for n in TEXTURES if n not in tex]
    if missing:
        raise FormatError("texturas não encontradas: " + ", ".join(missing))
    crcs = {}
    for i, (gname, fname) in enumerate(TEXTURES.items()):
        w, h, fmt, data = tex[gname]
        crcs[fname] = f"{umod_crc(data):08X}"
        rgba = decode_dxt(data, w, h, fmt)
        if fname.endswith("_n"):
            rgba = normal_to_rgb(rgba)
        write_png_rgb(tmp / f"{fname}.png", w, h, rgba)
        say(0.75 + 0.25 * (i + 1) / len(TEXTURES), "textures")
    (tmp / "info.json").write_text(json.dumps({"source": source_id(pack), "faces": nfaces, "crc": crcs}, indent=1), encoding="utf-8")
    del d, ap
    if out_dir.exists():
        for f in out_dir.iterdir():
            f.unlink()
        out_dir.rmdir()
    tmp.rename(out_dir)
    say(1.0, "done")
    return crcs
