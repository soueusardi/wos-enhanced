"""Lê pacotes .tpf do TexMod: desembaralha, abre o zip e extrai as texturas para uma pasta de cache."""
import io
import json
import struct
import zipfile
from pathlib import Path

KEY = 0x3FA43FA4
PASSWORD = bytes([0x73, 0x2A, 0x63, 0x7D, 0x5F, 0x0A, 0xA6, 0xBD, 0x7D, 0x65, 0x7E, 0x67, 0x61, 0x2A,
                  0x7F, 0x7F, 0x74, 0x61, 0x67, 0x5B, 0x60, 0x70, 0x45, 0x74, 0x5C, 0x22, 0x74, 0x5D,
                  0x6E, 0x6A, 0x73, 0x41, 0x77, 0x6E, 0x46, 0x47, 0x77, 0x49, 0x0C, 0x4B, 0x46, 0x6F])


def _unxor(data):
    n = len(data) // 4
    big = int.from_bytes(data[:n * 4], "little") ^ int.from_bytes(struct.pack("<I", KEY) * n, "little")
    return big.to_bytes(n * 4, "little") + bytes(b ^ (KEY & 0xFF) for b in data[n * 4:])


def open_tpf(path):
    z = zipfile.ZipFile(io.BytesIO(_unxor(Path(path).read_bytes())))
    z.setpassword(PASSWORD)
    return z


def parse_def(z):
    """Devolve [(hash_int, nome_do_arquivo_dentro_do_zip)] a partir do texmod.def."""
    out = []
    text = z.read("texmod.def").decode("latin1")
    for line in text.replace("\x00", "").splitlines():
        if "|" not in line:
            continue
        h, name = line.split("|", 1)
        try:
            out.append((int(h.strip(), 16), name.strip()))
        except ValueError:
            pass
    return out


MAX_DIM = 2048   # o jogo é de 32 bits: texturas maiores que isso (já vi uma de 4096x4096) só gastam memória


def _shrink(dest):
    """Reduz a imagem para no máximo MAX_DIM de lado (só na cópia guardada no cache, nunca no .tpf)."""
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        suffix = Path(dest).suffix.lower()
        fmt = {".png": "PNG", ".tga": "TGA", ".bmp": "BMP"}.get(suffix)
        if not fmt:
            return
        im = Image.open(dest)
        w, h = im.size
        if max(w, h) <= MAX_DIM:
            return
        k = MAX_DIM / max(w, h)
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB").resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
        im.save(dest, fmt)
    except Exception:
        pass


def cache_key(path):
    """Pasta de cache de uma skin: nome + tamanho (o mesmo arquivo em duas pastas usa o mesmo cache)."""
    path = Path(path)
    return f"{path.stem}__{path.stat().st_size}"


def extract(path, cache_root):
    """Extrai as texturas do .tpf para cache_root/<nome do tpf>/ (só na primeira vez).
    Devolve [(hash, caminho_do_arquivo)]."""
    path = Path(path)
    out_dir = Path(cache_root) / cache_key(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    z = open_tpf(path)
    items = []
    for h, name in parse_def(z):
        try:
            info = z.getinfo(name)
        except KeyError:
            continue
        dest = out_dir / Path(name).name
        if not dest.exists() or dest.stat().st_size != info.file_size:
            dest.write_bytes(z.read(info))
            _shrink(dest)
        items.append((h, str(dest)))
    return items


def cached_items(path, cache_root):
    """Se a skin já foi extraída por completo, devolve [(hash, caminho)]; senão None."""
    marker = Path(cache_root) / cache_key(path) / "items.json"
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        if data.get("tpf_size") != Path(path).stat().st_size or data.get("v") != 2:
            return None
        items = [(int(h), p) for h, p in data["items"]]
        return items if all(Path(p).is_file() for _, p in items) else None
    except Exception:
        return None


def prepare(path, cache_root):
    """Extrai (se preciso) e grava o marcador de cache completo."""
    import shutil
    shutil.rmtree(Path(cache_root) / cache_key(path), ignore_errors=True)  # recomeça limpo (cache antigo ou incompleto)
    items = extract(path, cache_root)
    marker = Path(cache_root) / cache_key(path) / "items.json"
    marker.write_text(json.dumps({"v": 2, "tpf_size": Path(path).stat().st_size, "items": items}), encoding="utf-8")
    return items


def read_defs(path):
    """Abre o .tpf e devolve (zip, [(hash, nome)]) — rápido, sem extrair nenhuma textura."""
    z = open_tpf(path)
    return z, parse_def(z)


def extract_some(z, entries, out_dir):
    """Extrai só algumas texturas [(hash, nome)] para out_dir (versão 'leve', só para preview). Devolve [(hash, caminho)]."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for h, name in entries:
        try:
            info = z.getinfo(name)
        except KeyError:
            continue
        dest = out_dir / f"{h:08X}{Path(name).suffix.lower()}"
        dest.write_bytes(z.read(info))
        out.append((h, str(dest)))
    return out
