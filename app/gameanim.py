"""Animações originais do Web of Shadows (formato NAL2) aplicadas ao esqueleto do Spider-Man.

Engenharia reversa própria, a partir do comportamento do jogo (formato em docs/formato_pcpack.md, seção 8). O decodificador
foi conferido número por número contra o código do próprio jogo rodando num emulador: 1812 animações, 111 mil quadros
iguais. Só biblioteca padrão. Nada é gravado na pasta do jogo.
"""
import math
import struct

ASKL_NAME = "ch_spiderman"
ANIM_VERSION = 0x20203
WIDTH = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 20, 30)   # larguras de bits do formato
STORED = (3, 4, 1, 3, 0, 1, 6, 1, 3, 4, 9)                       # componentes guardados por tipo de campo


class AnimError(Exception):
    pass


# ------------------------------------------------------------------ leitura de bits
class _Bits32:
    def __init__(self, d, pos, bit=0):
        self.d, self.w, self.b = d, pos, bit

    def read(self, n):
        if n == 0:
            return 0
        lo = struct.unpack_from("<I", self.d, self.w)[0] >> self.b
        if self.b + n > 32:
            lo |= struct.unpack_from("<I", self.d, self.w + 4)[0] << (32 - self.b)
        b = self.b + n
        self.w += 4 * (b >> 5)
        self.b = b & 31
        return lo & ((1 << n) - 1)


class _Bits16:
    def __init__(self, d, pos, bit):
        self.d, self.w, self.b = d, pos, bit

    def read(self, n):
        if n == 0:
            return 0
        lo = struct.unpack_from("<H", self.d, self.w)[0] >> self.b
        if self.b + n > 16:
            lo |= struct.unpack_from("<H", self.d, self.w + 2)[0] << (16 - self.b)
        b = self.b + n
        self.w += 2 * (b >> 4)
        self.b = b & 15
        return lo & ((1 << n) - 1)


def _value32(br, code):
    """valor de tamanho variável do fluxo de 32 bits (código de 6 bits: tamanho e base)"""
    if not (code & 0xFFFC) or not br.read(1):
        return 0
    t = br.read(1)
    val = br.read((WIDTH[code >> 2] if t else (code & 3) + 2) + 1)
    m = (val >> 1) + 1 + ((1 << ((code & 3) + 2)) if t else 0)
    return -m if val & 1 else m


class Anim:
    """uma animação: decodifica os quadros como listas de inteiros na ordem dos campos da pose"""

    def __init__(self, d, meta, ptr):
        u32 = lambda o: struct.unpack_from("<I", d, meta + o)[0]
        if u32(0x14) != ANIM_VERSION:
            raise AnimError("versão de animação desconhecida")
        self.d, self.meta = d, meta
        self.nframes, self.ntotal = u32(0x30), u32(0x38)
        self.nconst = struct.unpack_from("<H", d, meta + 0x74)[0]
        self.s32 = ptr(0x44)
        self.s16 = ptr(0x48) if u32(0x48) else None
        self.offs = [u32(0x4C + 4 * k) for k in range(8)]
        self.rem_bit = u32(0x6C)
        self.const_pos = list(struct.unpack_from(f"<{self.nconst}H", d, ptr(0x70))) if self.nconst else []
        self.duration = struct.unpack_from("<f", d, meta + 0x24)[0]
        self.mask = struct.unpack_from("<13I", d, meta + 0x78)
        if not (0 < self.nframes < 100000 and 0 < self.ntotal < 4096):
            raise AnimError("cabeçalho de animação estranho")

    def frames(self):
        d, N = self.d, self.ntotal
        br = _Bits32(d, self.s32)
        prev = [_value32(br, br.read(6)) for _ in range(N)]                     # quadro 0
        cur = [_value32(br, br.read(6)) + prev[i] for i in range(N)]            # quadro 1
        param = [br.read(6) for _ in range(N)]                                  # tamanho dos resíduos por canal
        n = N - self.nconst
        groups, nrem = n >> 3, (n & 7) + self.nconst
        yield self._reorder(prev, groups)
        if self.nframes > 1:
            yield self._reorder(cur, groups)
        streams = [_Bits16(d, self.s16 + (o >> 4) * 2, o & 15) for o in self.offs] if self.s16 is not None else None
        rr = _Bits32(d, self.s32 + (self.rem_bit >> 5) * 4, self.rem_bit & 31)
        for _f in range(2, self.nframes):
            res = [0] * N
            if streams is not None:                       # 8 fluxos de 16 bits intercalados, canal k no fluxo k
                for g in range(groups):
                    for k in range(8):
                        i = g * 8 + k
                        p = param[i]
                        s = streams[k]
                        if p == 0 or not s.read(1):
                            continue
                        t = s.read(1)
                        val = s.read((WIDTH[p >> 2] if t else (p & 3) + 2) + 1)
                        m = ((val >> 1) + 1 + ((1 << ((p & 3) + 2)) if t else 0)) & 0xFFFF
                        v = (-m if val & 1 else m) & 0xFFFF
                        res[i] = v - 0x10000 if v & 0x8000 else v
            for j in range(nrem):                         # canais que sobram: fluxo de 32 bits
                res[groups * 8 + j] = _value32(rr, param[groups * 8 + j])
            prev, cur = cur, [res[i] + 2 * cur[i] - prev[i] for i in range(N)]   # previsão linear + resíduo
            yield self._reorder(cur, groups)

    def frame(self, f):
        for i, fr in enumerate(self.frames()):
            if i == f:
                return fr
        raise AnimError("quadro fora do intervalo")

    def _reorder(self, F, groups):
        N, c = self.ntotal, self.nconst
        n = N - c
        tmp = [F[8 * g + k] for k in range(8) for g in range(groups)] + F[8 * groups:N]
        if c:                                             # constantes entram nas posições listadas (do fim para o início)
            e = n - 1
            for j in range(c - 1, -1, -1):
                pos = self.const_pos[j]
                while e >= pos:
                    tmp[e + j + 1] = tmp[e]
                    e -= 1
                e = pos
                tmp[pos] = F[N - c + j]
        return tmp


def find_anim(ap, name):
    """posição do metadado da animação (procura a assinatura: marca fc.., hash do nome, versão)"""
    h = struct.pack("<I", _hash(name))
    d, lo, hi = ap.d, ap.img_base, ap.phys_base
    q = d.find(h, lo, hi)
    while q >= 0:
        if q % 4 == 0 and d[q - 1] == 0xFC and struct.unpack_from("<I", d, q + 0x10)[0] == ANIM_VERSION:
            return q - 4
        q = d.find(h, q + 1, hi)
    raise AnimError(f"animação {name} não encontrada")


def _hash(name):
    h = 0
    for c in name.lower().encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


# ------------------------------------------------------------------ quaternions (x, y, z, w)
def _qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def _qnorm(q):
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q) if n > 1e-12 else (0.0, 0.0, 0.0, 1.0)


def _qrot(q, v):
    x, y, z, w = q; vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + y * tz - z * ty, vy + w * ty + z * tx - x * tz, vz + w * tz + x * ty - y * tx)


def _qconj(q):
    return (-q[0], -q[1], -q[2], q[3])


def _qaxis(ax, ang):
    n = math.sqrt(sum(c * c for c in ax)) or 1.0
    s = math.sin(ang / 2)
    return (ax[0] / n * s, ax[1] / n * s, ax[2] / n * s, math.cos(ang / 2))


def _mat(q):
    x, y, z, w = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


def _mm(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _mt(a):
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))


def _mv(a, v):
    return tuple(sum(a[i][k] * v[k] for k in range(3)) for i in range(3))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _frame(u, v):
    """base ortonormal (colunas) a partir de dois vetores"""
    e1 = _unit(u)
    d = sum(a * b for a, b in zip(v, e1))
    e2 = _unit(tuple(b - d * a for a, b in zip(e1, v)))
    e3 = _cross(e1, e2)
    return ((e1[0], e2[0], e3[0]), (e1[1], e2[1], e3[1]), (e1[2], e2[2], e3[2]))


# ------------------------------------------------------------------ esqueleto de animação (ASKL) + pose
class Poser:
    """liga a ASKL `ch_spiderman` (116 nós) ao SKEL de 80 ossos e transforma quadros em matrizes de pose"""

    def __init__(self, ap, skel, skel_json, askl=ASKL_NAME):
        d = ap.d
        h = _hash(askl)
        A = next((p for hh, p, _s, _e in ap.records("ASKL") if hh == h), None)
        if A is None:
            raise AnimError("esqueleto de animação não encontrado")
        self.d, self.ap, self.A = d, ap, A
        names = ap.names()
        self.nodes = []
        for k in range(116):
            f = struct.unpack_from("<12f", d, A + 0xFD0 + 64 * k)
            nh = struct.unpack_from("<I", d, A + 0xFD0 + 64 * k + 56)[0]
            self.nodes.append({"axis": f[0:3], "q": f[4:8], "t": f[8:11], "name": names.get(nh, ""), "hash": nh})
        self.tP = struct.unpack_from("<116h", d, A + 0x2EA0)
        self.tQ = struct.unpack_from("<116h", d, A + 0x2F88)
        self.tH = struct.unpack_from("<116h", d, A + 0x3070)
        self.cnt = struct.unpack_from("<11H", d, A + 0x10C)
        self.base = struct.unpack_from("<11H", d, A + 0x138)
        rel = lambda o: A + struct.unpack_from("<I", d, A + o)[0] * 4 - (A - ap.img_base)
        self.scale = {t: rel(o) for t, o in ((0, 0xE0), (1, 0xE4), (2, 0xE8))}
        if self.cnt[:3] != (33, 63, 32):
            raise AnimError("esqueleto de animação com formato inesperado")
        self.skel, self.sj = skel, skel_json
        idx = {nd["name"]: k for k, nd in enumerate(self.nodes)}
        self.idx = idx
        need = [b["name"] for b in skel] + ["bip01 footsteps", "fakeroot"]
        missing = [n for n in need if n not in idx]
        if missing:
            raise AnimError("ossos sem correspondência na animação: " + ", ".join(missing[:5]))
        bypar = {b["name"]: b["parent"] for b in skel}
        self.par = {}
        for k, nd in enumerate(self.nodes):
            nm = nd["name"]
            if nm == "bip01 pelvis":
                self.par[k] = idx["bip01 footsteps"]
            elif nm == "bip01 footsteps":
                self.par[k] = idx["fakeroot"]
            elif nm == "fakeroot":
                self.par[k] = -1
            elif nm in bypar:
                p = bypar[nm]
                self.par[k] = -1 if p < 0 else idx[skel[p]["name"]]
            else:
                self.par[k] = -2                           # auxiliar fora do modelo: não precisa
        self.restq, self.restp = self._worlds(self._locals(None))
        # rotação global NAL -> SKEL (o repouso da NAL reproduz o SKEL a menos dela): base de 2 vetores em cada lado
        P = lambda nm: self.restp[idx[nm]]
        S = lambda nm: tuple(b["world"][12:15] for b in skel if b["name"] == nm)[0]
        u_n, v_n = _sub(P("bip01 head"), P("bip01 pelvis")), _sub(P("bip01 r hand"), P("bip01 l hand"))
        u_s, v_s = _sub(S("bip01 head"), S("bip01 pelvis")), _sub(S("bip01 r hand"), S("bip01 l hand"))
        self.R = _mm(_frame(u_s, v_s), _mt(_frame(u_n, v_n)))
        err = max(math.dist(_mv(self.R, _sub(self.restp[idx[b["name"]]], P("bip01 pelvis"))),
                            _sub(b["world"][12:15], S("bip01 pelvis"))) for b in skel)
        if err > 1e-3:
            raise AnimError(f"repouso da animação não bate com o modelo (erro {err:.4f})")
        sjb = skel_json["bones"]
        ip, ih = idx["bip01 pelvis"], idx["bip01 head"]
        self.k = math.dist(sjb[0]["pos"], sjb[5]["pos"]) / math.dist(self.restp[ip], self.restp[ih])

    def _locals(self, vals):
        L = {}
        for k, nd in enumerate(self.nodes):
            L[k] = [_qconj(_qnorm(nd["q"])) if any(nd["q"]) else (0.0, 0.0, 0.0, 1.0), tuple(nd["t"])]
        if vals is None:
            return L
        pos, quat, hin = vals
        for k in range(116):
            if self.tP[k] >= 0 and self.tP[k] in pos:
                L[k][1] = pos[self.tP[k]]
            if self.tQ[k] >= 0 and self.tQ[k] in quat:
                L[k][0] = _qconj(_qnorm(quat[self.tQ[k]]))
            if self.tH[k] >= 0 and self.tH[k] in hin:
                L[k][0] = _qmul(L[k][0], _qaxis(self.nodes[k]["axis"], hin[self.tH[k]]))
        return L

    def _worlds(self, L):
        Wq, Wp = {}, {}

        def go(k):
            if k in Wq:
                return
            p = self.par[k]
            q, t = L[k]
            if p < 0:
                Wq[k], Wp[k] = (q, tuple(t)) if p == -1 else ((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
                return
            go(p)
            Wq[k] = _qmul(Wq[p], q)
            Wp[k] = tuple(a + b for a, b in zip(Wp[p], _qrot(Wq[p], t)))
        for k in range(116):
            go(k)
        return Wq, Wp

    def values(self, anim, ints):
        """separa os inteiros do quadro em posições / quaternions / dobradiças (valores reais)"""
        m = anim.mask
        bit = lambda g: (m[g >> 5] >> (g & 31)) & 1
        sc = lambda t, i: struct.unpack_from("<f", self.d, self.scale[t] + 4 * i)[0]
        o, out = 0, ({}, {}, {})
        for t in range(3):
            for i in range(self.cnt[t]):
                if bit(self.base[t] + i):
                    s, n = sc(t, i), STORED[t]
                    v = tuple(x * s for x in ints[o:o + n])
                    out[t][i] = v if n > 1 else v[0]
                    o += n
        return out

    def pose(self, anim, ints):
        """por osso do SKEL: [qx, qy, qz, qw, tx, ty, tz] = rotação e translação que levam o repouso à pose (visualizador)"""
        Wq, Wp = self._worlds(self._locals(self.values(anim, ints)))
        out = []
        for i, b in enumerate(self.skel):
            k = self.idx[b["name"]]
            dq = _qnorm(_qmul(Wq[k], _qconj(self.restq[k])))           # delta no espaço da NAL
            Rd = _mm(_mm(self.R, _mat(dq)), _mt(self.R))                 # ... no espaço do modelo
            p0 = tuple(self.sj["bones"][i]["pos"])
            p1 = tuple(a + self.k * c for a, c in zip(p0, _mv(self.R, _sub(Wp[k], self.restp[k]))))
            T = _sub(p1, _mv(Rd, p0))
            q = _mat_to_quat(Rd)
            out.append([round(c, 5) for c in q] + [round(c, 5) for c in T])
        return out


def _mat_to_quat(m):
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return _qnorm(((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, 0.25 * s))
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        return _qnorm((0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s))
    if m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        return _qnorm(((m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s))
    s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
    return _qnorm(((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s, (m[1][0] - m[0][1]) / s))


def extract_poses(ap, skel, skel_json, wanted, log=print):
    """wanted: {nome_da_pose: (animação, quadro)} -> {nome_da_pose: {anim, frame, frames, bones: [[q..t..] x 80]}}"""
    poser = Poser(ap, skel, skel_json)
    out = {}
    for pname, (aname, fr) in wanted.items():
        meta = find_anim(ap, aname)
        anim = Anim(ap.d, meta, lambda o, meta=meta: ap.img(struct.unpack_from("<I", ap.d, meta + o)[0]))
        f = max(0, min(fr, anim.nframes - 1))
        out[pname] = {"anim": aname, "frame": f, "frames": anim.nframes, "bones": poser.pose(anim, anim.frame(f))}
        log(f"gameanim: pose '{pname}' = {aname} quadro {f}/{anim.nframes - 1}")
    return out
