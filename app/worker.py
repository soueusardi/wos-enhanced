"""Trabalhos pesados do launcher num processo separado, para a janela nunca travar enquanto eles rodam.
Uso: python worker.py <tarefa> <arquivo> <pasta de saída>. Cada linha da saída é um JSON:
{"pct": n} (progresso), {"log": "..."} (mensagem para o launcher.log) e, no fim, {"ok": true, ...} ou {"ok": false, "error": "..."}."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def say(**kw):
    # só ASCII: a saída do processo usa a codificação do Windows (cp1252) e o launcher lê como UTF-8;
    # com os acentos escapados (é) a mensagem chega certa nos dois lados
    print(json.dumps(kw, ensure_ascii=True), flush=True)


def main():
    task, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    try:
        if task == "prepare":
            import tpf
            got = tpf.prepare(src, out)
            say(ok=True, hashes=[f"{h:08X}" for h, _ in got])
        elif task == "lite":
            import preview
            preview.lite(src, out)
            say(ok=True)
        elif task == "gameassets":
            import gameassets
            crcs = gameassets.extract(src, out, lambda frac, stage=None: say(pct=int(frac * 100)), lambda m: say(log=str(m)))
            say(ok=True, crcs=crcs)
        else:
            say(ok=False, error=f"tarefa desconhecida: {task}")
            return 2
    except Exception as e:
        say(ok=False, error=repr(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
