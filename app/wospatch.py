"""Reparo em memória do Spider-Man: Web of Shadows (versão 1.1.1.11540, carimbo 0x562b3227).

Bug do jogo: o renderizador monta um objeto que consulta o "registro global" em [0x10FC5C0] antes de a inicialização
ter criado esse registro. Quando o renderizador é mais rápido, o ponteiro ainda é nulo e o jogo cai (endereço 0x63CE51).
Reparo: antes de o WinMain começar, cria o registro com as MESMAS rotinas do jogo. A inicialização original depois vê
que ele já existe e não cria de novo (ela confere "se não for nulo, pula")."""
import struct

IMAGE_BASE = 0x400000
HOOK_SITE = 0xADE9F8                       # no código de partida: call WinMain
HOOK_ORIG = bytes.fromhex("e883d1eeff")    # call 0x9cbb80
WINMAIN = 0x9CBB80
GLOBAL_REGISTRY = 0x10FC5C0
NEW_FN = 0x5FBDD0                          # operator new do jogo (cdecl, se auto-inicializa)
CTOR_FN = 0x7661D0                         # construtor do registro (thiscall, devolve this em eax)
CAVE_SIZE = 48


def rel32(src_next, dst):
    """Deslocamento de 4 bytes de um call/jmp que termina em src_next e vai para dst."""
    return struct.pack("<I", (dst - src_next) & 0xFFFFFFFF)


def build_cave(cave):
    """Devolve os bytes do trecho que cria o registro e depois salta para o WinMain."""
    b = bytearray()
    b += bytes.fromhex("833dc0c50f0100")        # cmp dword ptr [0x10fc5c0], 0
    b += b"\x75\x00"; jne_at = len(b) - 1       # jne feito  (distância preenchida depois)
    b += b"\x6a\x18"                            # push 0x18
    b += b"\xe8" + rel32(cave + len(b) + 5, NEW_FN)
    b += b"\x83\xc4\x04"                        # add esp, 4
    b += b"\x85\xc0"                            # test eax, eax
    b += b"\x74\x00"; je_at = len(b) - 1        # je feito
    b += b"\x8b\xc8"                            # mov ecx, eax
    b += b"\xe8" + rel32(cave + len(b) + 5, CTOR_FN)
    b += b"\xa3" + struct.pack("<I", GLOBAL_REGISTRY)   # mov [0x10fc5c0], eax
    done = len(b)
    b[jne_at] = done - (jne_at + 1)
    b[je_at] = done - (je_at + 1)
    b += b"\xe9" + rel32(cave + len(b) + 5, WINMAIN)    # jmp WinMain
    assert len(b) <= CAVE_SIZE
    return bytes(b)


def hook_bytes(cave):
    """Novo conteúdo de 5 bytes no ponto da chamada ao WinMain."""
    return b"\xe8" + rel32(HOOK_SITE + 5, cave)


# ---- pular os vídeos de abertura ----
# O jogo abre todos os vídeos em UM só lugar: call [BinkOpen] em MOVIE_SITE. Se a abertura falha, ele marca o vídeo como
# encerrado e segue (o mesmo caminho de "vídeo não encontrado"). O ajudante (crashcatch, que é um depurador) põe um int3 ali;
# a cada vídeo ele lê o NOME pedido e decide: os da abertura (INTRO_MOVIES) devolvem "não abriu"; os outros abrem normalmente.
# Nomes tirados do código: a sequência de abertura chama a função de tocar vídeo (0x76BA90) com "intro" (0x76BBB4) e
# "aspyr" (0x76BBA4). Os outros vídeos do jogo são "credits", "attract"/"attract_2" (menu parado) e os das cenas (por script).
# (Antes era uma regra de tempo — pular enquanto os vídeos vinham a menos de 20 s um do outro — que falhava quando o jogo
#  demorava a carregar entre um vídeo e outro, por exemplo com o Modo 60 FPS usando menos núcleos.)
MOVIE_SITE = 0x6C75D4
MOVIE_ORIG = bytes.fromhex("ff159894b700")   # call dword ptr [0xb79498]  (BinkOpen, stdcall com 2 argumentos)
BINKOPEN_IAT = 0xB79498
INTRO_MOVIES = ("intro", "aspyr")


def movie_name(path):
    """'movies\\intro.bik' -> 'intro'."""
    return path.replace("/", "\\").rsplit("\\", 1)[-1].rsplit(".", 1)[0].lower()


def movie_bp(esp, read32, readstr, write32, skip_enabled=True):
    """O jogo parou no int3 de MOVIE_SITE (antes do call [BinkOpen]; os 2 argumentos já estão na pilha).
    Devolve (caminho do vídeo, pulou?, registradores a mudar). Pular = "BinkOpen devolveu 0" (eax=0, tira os 2 argumentos,
    segue depois do call). Tocar = faz o call de verdade (empilha o retorno e vai para o BinkOpen)."""
    path = readstr(read32(esp))
    if skip_enabled and movie_name(path) in INTRO_MOVIES:
        return path, True, {"eax": 0, "esp": esp + 8, "eip": MOVIE_SITE + 6}
    write32(esp - 4, MOVIE_SITE + 6)
    return path, False, {"esp": esp - 4, "eip": read32(BINKOPEN_IAT)}


# ---- trocar os botões do controle (XInput) ----
# O jogo lê o controle só por um "trampolim" em 0xADE396: jmp [XInputGetState]. Trocamos por jmp para um trecho nosso que
# chama o XInputGetState de verdade e depois troca os bits dos botões segundo uma tabela de 18 posições
# (0..15 = bits de wButtons, 16 = LT, 17 = RT; valor = para qual posição vai; 0xFF = desligado).
# Gatilho como origem conta como apertado acima de 30 (o limiar padrão do XInput); como destino vira 0 ou 255.
XINPUT_THUNK = 0xADE396
XINPUT_THUNK_ORIG = bytes.fromhex("ff258494b700")   # jmp dword ptr [0xb79484]
XINPUT_GETSTATE_IAT = 0xB79484
PAD_CAVE_SIZE = 192
PAD_TABLE = 160                                     # deslocamento da tabela dentro do trecho

# posição de cada botão físico na tabela
PAD_BITS = {"DUP": 0, "DDOWN": 1, "DLEFT": 2, "DRIGHT": 3, "START": 4, "BACK": 5, "LS": 6, "RS": 7,
            "LB": 8, "RB": 9, "A": 12, "B": 13, "X": 14, "Y": 15, "LT": 16, "RT": 17}
# padrão do jogo (tirado do código: dispositivo "keyjoy" em 0x9CAD80 + tabela de controles do XInput em 0x9C9444)
PAD_DEFAULTS = {"ActionWallCrawl": "RB", "ActionWallSprint": "LB", "ActionSwing": "RT", "ActionJump": "A",
                "ActionCenterCamera": "RS", "ActionSuit": "LS", "ActionTarget": "LT", "ActionShoot": "B",
                "ActionAttack": "X", "ActionWebStrike": "Y", "ActionUpgrades": "BACK", "ActionAllyPrev": "DLEFT",
                "ActionAllyNext": "DRIGHT", "ActionAllySummon": "DDOWN", "ActionAllyDismiss": "DUP"}


def pad_table(assign):
    """assign = {ação: botão físico}. Devolve a tabela de 18 bytes (identidade quando nada mudou)."""
    t = list(range(18))
    for b in (10, 11):
        t[b] = 0xFF  # bits que não existem no XInput
    for action, phys in assign.items():
        if action in PAD_DEFAULTS and phys in PAD_BITS:
            t[PAD_BITS[phys]] = PAD_BITS[PAD_DEFAULTS[action]]
    return bytes(t)


def pad_is_identity(table):
    return table == pad_table({})


PAD_ASM = """
    push dword ptr [esp+8]
    push dword ptr [esp+8]
    call dword ptr [{iat}]
    test eax, eax
    jnz done
    push ebx
    push esi
    push edi
    mov esi, dword ptr [esp+0x14]
    movzx ebx, word ptr [esi+4]
    cmp byte ptr [esi+6], 30
    jbe nolt
    or ebx, 0x10000
nolt:
    cmp byte ptr [esi+7], 30
    jbe nort
    or ebx, 0x20000
nort:
    xor edi, edi
    xor ecx, ecx
next:
    bt ebx, ecx
    jnc skip
    movzx edx, byte ptr [ecx+{table}]
    cmp edx, 0xff
    je skip
    bts edi, edx
skip:
    inc ecx
    cmp ecx, 18
    jb next
    mov word ptr [esi+4], di
    xor eax, eax
    bt edi, 16
    jnc wlt
    mov al, 0xff
wlt:
    mov byte ptr [esi+6], al
    xor eax, eax
    bt edi, 17
    jnc wrt
    mov al, 0xff
wrt:
    mov byte ptr [esi+7], al
    pop edi
    pop esi
    pop ebx
    xor eax, eax
done:
    ret 8
"""


# bytes do PAD_ASM já montados (com o keystone, uma vez); só o endereço da tabela muda de um jogo para outro
PAD_CODE = bytes.fromhex("ff742408ff742408ff158494b70085c075675356578b7424140fb75e04807e061e760681cb00000100807e071e760681cb0000020031ff31c90fa3cb73120fb691a000001081faff00000074030fabd74183f91272e366897e0431c00fbae7107302b0ff88460631c00fbae7117302b0ff8846075f5e5b31c0c20800")
PAD_CODE_TABLE_AT = 65                           # onde fica o endereço absoluto da tabela dentro de PAD_CODE


def build_pad_cave(cave, table):
    code = bytearray(PAD_CODE)
    code[PAD_CODE_TABLE_AT:PAD_CODE_TABLE_AT + 4] = struct.pack("<I", cave + PAD_TABLE)
    assert len(code) <= PAD_TABLE and len(table) == 18
    return bytes(code) + bytes(PAD_TABLE - len(code)) + table


def assemble_pad_code():
    """Só para quem for mexer no PAD_ASM: remonta e devolve (bytes, deslocamento da tabela). Precisa do keystone."""
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    base = 0x10000000
    code, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(PAD_ASM.format(iat=hex(XINPUT_GETSTATE_IAT), table=hex(base + PAD_TABLE)), base)
    code = bytes(code)
    return code, code.find(struct.pack("<I", base + PAD_TABLE))


def pad_hook_bytes(cave):
    return b"\xe9" + rel32(XINPUT_THUNK + 5, cave) + b"\x90"
