"""Prepara as texturas de uma skin para o visualizador 3D (modelo real do jogo)."""
import base64
import io
import json
from pathlib import Path

from PIL import Image, ImageChops

Image.MAX_IMAGE_PIXELS = None

# ---- texturas do jogo (os códigos são iguais em qualquer skin) ----
RED = {"upper": "1D51ED58", "lower": "6C03F0A0"}
BLACK = {"upper": "C46B23D2", "lower": "76B70474"}
# camadas de detalhe do traje preto (costelas, tentáculos): somadas à cor. Pretas = sem detalhe (ex.: Anti Venom)
BLACK_DETAIL = {"upper": "E0A1AD7C", "lower": "FC5F7F83"}
# mapas de relevo das skins (1327B796, A893AD3A, D9F1DCAE, B4A6F6A4) NÃO são usados: o formato deles varia de skin para skin
# e gerava relevo falso (manchas escuras e uma emenda no meio do corpo)
SUIT_TEXTURES = {"Clássico": RED, "Negro": BLACK}
# traje vermelho tem um 2º conjunto (FBFCE874/4728B4B4); o preto tem também brilho (E0A1AD7C, FC5F7F83) e tentáculos
RED_HASHES = {*RED.values(), "FBFCE874", "4728B4B4", "1327B796", "A893AD3A"}
BLACK_HASHES = {*BLACK.values(), *BLACK_DETAIL.values(), "D9F1DCAE", "B4A6F6A4", "83F269DD", "D1B0C849"}
UI_HASHES = {"E1EEE8B7", "1C8A1F9A", "9E668755", "B897DFC8", "D4D3DB7B", "964E5053", "4121B33D"}


def _png_uri(im):
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=False)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _jpg_uri(im, quality=88):
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _diffuse_uri(path, size=1024):
    im = Image.open(path).convert("RGB")
    if im.size != (size, size):
        im = im.resize((size, size), Image.LANCZOS)
    return _jpg_uri(im)


def _diffuse_plus_detail(path, detail, size=1024):
    """Cor da skin + camada de detalhe somada (como o jogo faz no traje preto)."""
    a = Image.open(path).convert("RGB").resize((size, size), Image.LANCZOS)
    if detail:
        b = Image.open(detail).convert("RGB").resize((size, size), Image.LANCZOS)
        a = ImageChops.add(a, b)
    return _jpg_uri(a)


def _small(path, n=32):
    return list(Image.open(path).convert("L").resize((n, n), Image.BILINEAR).getdata())


def _corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def _black_upper_by_content(items, ref):
    """Plano B: a textura grande que mais se parece com a parte de cima do traje preto original."""
    refv, best, best_p = _small(ref), 0.5, None
    known = RED_HASHES | BLACK_HASHES | UI_HASHES
    for h, path in items:
        if f"{h:08X}" in known:
            continue
        try:
            im = Image.open(path)
            if min(im.size) < 1024 or im.size[0] != im.size[1]:
                continue
            c = _corr(refv, _small(path))
        except Exception:
            continue
        if c > best:
            best, best_p = c, path
    return best_p


def build(items, ref=None):
    """items = [(hash, caminho)] ->
    {'suits': [{'suit', 'upper', 'lower', 'nupper', 'nlower'}], 'extras': [{'hash','size','uri'}]}"""
    by = {f"{h:08X}": p for h, p in items}
    suits = []
    for suit, tex in SUIT_TEXTURES.items():
        entry = {"suit": suit, "nupper": None, "nlower": None}
        for part, h in tex.items():
            p = by.get(h)
            if p is None and suit == "Negro" and part == "upper" and ref:
                p = _black_upper_by_content(items, ref)
            try:
                if not p:
                    entry[part] = None
                elif suit == "Negro":
                    entry[part] = _diffuse_plus_detail(p, by.get(BLACK_DETAIL[part]))
                else:
                    entry[part] = _diffuse_uri(p)
            except Exception:
                entry[part] = None
        if entry["upper"] or entry["lower"]:
            suits.append(entry)
    extras, seen = [], set()  # texturas de outros modelos (sem preview 3D): só miniaturas
    known = RED_HASHES | BLACK_HASHES | UI_HASHES
    for h, p in items:
        if f"{h:08X}" in known or f"{h:08X}" in seen or len(extras) >= 8:
            continue
        seen.add(f"{h:08X}")
        try:
            im = Image.open(p)
            size = im.size
            if min(size) < 256:
                continue
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (40, 44, 66, 255))
            bg.alpha_composite(im)
            bg.thumbnail((192, 192))
            extras.append({"hash": f"{h:08X}", "size": f"{size[0]}x{size[1]}", "uri": _jpg_uri(bg, 80)})
        except Exception:
            continue
    return {"suits": suits, "extras": extras}


def cached_build(items, cache_file, tpf_size, ref=None):
    cache_file = Path(cache_file)
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        if data.get("tpf_size") == tpf_size and data.get("v") == 5:
            return {"suits": data["suits"], "extras": data["extras"]}
    except Exception:
        pass
    out = build(items, ref)
    cache_file.write_text(json.dumps({"v": 5, "tpf_size": tpf_size, **out}), encoding="utf-8")
    return out


def classify(hashes):
    """De que traje é uma skin, pelos códigos das texturas: 'vermelho', 'preto', 'dual' (os dois em um arquivo) ou 'outros'."""
    hs = {f"{h:08X}" if isinstance(h, int) else str(h).upper() for h in hashes}
    red, black = bool(hs & RED_HASHES), bool(hs & BLACK_HASHES)
    return "dual" if red and black else "vermelho" if red else "preto" if black else "outros"


LITE_VERSION = 6


def lite_cached(path, cache_root):
    """O preview leve já calculado (ou None, se ainda não existe ou ficou velho)."""
    from tpf import cache_key
    path = Path(path)
    try:
        data = json.loads((Path(cache_root) / cache_key(path) / "preview.json").read_text(encoding="utf-8"))
        if data.get("v") == LITE_VERSION and data.get("tpf_size") == path.stat().st_size:
            return data
    except Exception:
        pass
    return None


def lite(path, cache_root):
    """Preview 'leve' de uma skin: lê só as texturas dos trajes (e algumas de outro modelo) direto do .tpf.
    Não depende da preparação completa. Devolve {'kind', 'suits', 'extras'} (e guarda em cache)."""
    from tpf import cache_key, read_defs, extract_some  # import local: preview.py e tpf.py não dependem um do outro no topo
    path = Path(path)
    d = Path(cache_root) / cache_key(path)
    pj = d / "preview.json"
    size = path.stat().st_size
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
        if data.get("v") == LITE_VERSION and data.get("tpf_size") == size:
            return data
    except Exception:
        pass
    z, defs = read_defs(path)
    first = {}
    for h, n in defs:
        first.setdefault(h, n)
    kind = classify(first.keys())
    suit_h = {int(x, 16) for x in [*RED.values(), *BLACK.values(), *BLACK_DETAIL.values()]}
    need = [(h, n) for h, n in first.items() if h in suit_h]
    known = RED_HASHES | BLACK_HASHES | UI_HASHES
    unknown = []
    for h, n in first.items():  # texturas grandes que não são dos trajes conhecidos (galeria de "outro modelo")
        if f"{h:08X}" in known:
            continue
        try:
            sz = z.getinfo(n).file_size
            if sz >= 30_000:   # PNG comprimido é bem menor que a imagem: 30 KB já descarta ícones minúsculos
                unknown.append((sz, h, n))
        except KeyError:
            pass
    unknown = [(h, n) for _, h, n in sorted(unknown, reverse=True)[:6]]   # as 6 maiores
    items = extract_some(z, need + unknown, d / "files")
    out = build(items, None)
    out.update({"v": LITE_VERSION, "tpf_size": size, "kind": kind})
    d.mkdir(parents=True, exist_ok=True)
    pj.write_text(json.dumps(out), encoding="utf-8")
    return out


def file_uri(path):
    """Textura original do jogo (arquivo do modelo) como JPEG em data-URI."""
    return _jpg_uri(Image.open(path), 92)


def png_file_uri(path):
    """PNG já pronto em disco (miniatura) como data-URI, sem recodificar."""
    import base64
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def file_png_uri(path):
    return _png_uri(Image.open(path).convert("RGB"))


# ---- a que traje cada textura pertence (para separar as skins por traje) ----
def suit_of(h, path):
    """'red', 'black' ou None (textura que não é de um traje específico, como ícones de menu)."""
    hs = f"{h:08X}"
    if hs in RED_HASHES:
        return "red"
    if hs in BLACK_HASHES or "black" in Path(path).name.lower():
        return "black"
    return None


def filter_items(items, group):
    """Na pasta da roupa vermelha só vale o que não é do traje preto, e vice-versa. 'geral' não filtra."""
    drop = {"vermelho": "black", "preto": "red"}.get(group)
    return [(h, p) for h, p in items if suit_of(h, p) != drop] if drop else list(items)
