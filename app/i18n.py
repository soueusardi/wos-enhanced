"""Textos do launcher que vêm do Python (mensagens), em português e inglês."""
LANG = "pt"

STR = {
    "pt": {
        "opts_saved": "Opções salvas.",
        "opts_fail": "Não foi possível salvar: {e}",
        "game_not_found": "Jogo não encontrado. Confira a pasta do jogo.",
        "umod_missing": "uMod não encontrado. Coloque o d3d9.dll do uMod na pasta umod.",
        "dll_exists": "Já existe um d3d9.dll diferente na pasta do jogo. Não vou sobrescrever.",
        "already_opening": "O jogo já está sendo aberto.",
        "skin_preparing": "A skin {name} ainda está sendo preparada. Aguarde um pouco (só na primeira vez).",
        "opening": "Abrindo o jogo…",
        "started_n": "Jogo iniciado com {n} texturas trocadas.",
        "started": "Jogo iniciado.",
        "start_fail": "Não foi possível abrir o jogo: {e}",
        "crashed": "O jogo fechou com erro ao abrir. Veja o launcher.log.",
        "pad_bad": "Cada botão do controle só pode ter uma ação.",
        "grp_vermelho": "Traje Vermelho", "grp_preto": "Traje Preto",
        "grp_dual": "2 em 1 (vermelho + preto)", "grp_outros": "Outras skins",
        "import_ok": "\"{name}\" adicionada em {group}.",
        "import_dup": "\"{name}\" já estava em {group}.",
        "import_bad": "Não consegui ler \"{name}\". Esse arquivo é um .tpf válido?",
        "import_not_tpf": "\"{name}\" não é um arquivo .tpf.",
    },
    "en": {
        "opts_saved": "Options saved.",
        "opts_fail": "Could not save: {e}",
        "game_not_found": "Game not found. Check the game folder.",
        "umod_missing": "uMod not found. Put uMod's d3d9.dll in the umod folder.",
        "dll_exists": "A different d3d9.dll already exists in the game folder. I will not overwrite it.",
        "already_opening": "The game is already being opened.",
        "skin_preparing": "The skin {name} is still being prepared. Please wait a moment (first time only).",
        "opening": "Opening the game…",
        "started_n": "Game started with {n} textures replaced.",
        "started": "Game started.",
        "start_fail": "Could not open the game: {e}",
        "crashed": "The game closed with an error on startup. See launcher.log.",
        "pad_bad": "Each controller button can only have one action.",
        "grp_vermelho": "Red Suit", "grp_preto": "Black Suit",
        "grp_dual": "2 in 1 (red + black)", "grp_outros": "Other skins",
        "import_ok": "\"{name}\" added to {group}.",
        "import_dup": "\"{name}\" was already in {group}.",
        "import_bad": "Could not read \"{name}\". Is it a valid .tpf file?",
        "import_not_tpf": "\"{name}\" is not a .tpf file.",
    },
}


def set_lang(lang):
    global LANG
    LANG = "en" if lang == "en" else "pt"


def T(key, **kw):
    s = STR.get(LANG, STR["pt"]).get(key) or STR["pt"].get(key, key)
    return s.format(**kw)
