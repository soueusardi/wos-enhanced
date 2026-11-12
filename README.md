# Web of Shadows Launcher

Launcher de fã, **não oficial e gratuito**, para a versão de PC de **Spider-Man: Web of Shadows** (versão 1.1.1.11540).
*English below.*

> Versão **0.1.0**: primeira versão pública, ainda em desenvolvimento.

## O que ele faz
- **Skins**: arraste um `.tpf` (TexMod) para a janela. O launcher descobre se é do traje vermelho, do preto ou dos dois (2 em 1) e aplica no jogo pelo uMod, que vai embutido.
- **Visualizador 3D** com o modelo, as texturas e as animações lidos **da sua própria cópia do jogo**, miniaturas das skins e poses (braços cruzados, pendurado na teia).
- **Opções do jogo**: teclado e mouse, **controle com troca de botões**, vídeo.
- **Correções**: a queda ao abrir o jogo, pular os vídeos de abertura (que ficam verdes com skins) e um modo experimental para 60 FPS.

## Requisitos
- Windows 10 ou 11 com o WebView2 (já vem no Windows 11).
- Uma cópia própria do jogo, adquirida legalmente. **Nenhum arquivo do jogo é distribuído.**

## Como usar
1. Baixe o `.zip` da página [**Releases**](https://github.com/soueusardi/wos-enhanced/releases): ele contém só o `Web of Shadows Launcher.exe`.
2. Abra o `.exe` (pode ficar em qualquer pasta). As configurações, o cache e as skins ficam em `%LOCALAPPDATA%\Web of Shadows Launcher`.
3. Se ele não achar o jogo sozinho, use **Mudar pasta**.
4. Para conferir o download, compare o SHA-256 com o das notas do release (`docs/RELEASE_NOTES_v0.1.0.md`):
   `Get-FileHash .\WebOfShadowsLauncher-v0.1.0.zip -Algorithm SHA256` no PowerShell.

Pelo código-fonte (desenvolvimento): instale o Python 3 e rode `run_from_source.bat`. Para gerar o `.exe`: `build_exe.bat` (o resultado fica em `dist/`).

## Avisos
- O `.exe` é novo e **não tem assinatura digital**: o Windows pode mostrar o aviso do **SmartScreen** ("O Windows protegeu
  o computador"). Clique em **Mais informações** → **Executar assim mesmo**.
- Para aplicar as correções, o launcher abre o jogo como um **depurador** e altera a memória do jogo (nunca o `.exe` em disco), e copia um `d3d9.dll` para a pasta do jogo enquanto ele roda. Alguns antivírus podem desconfiar disso.
- Não é afiliado, endossado nem patrocinado pela Activision, Marvel, Disney ou qualquer detentor dos direitos do jogo. Todas as marcas pertencem aos seus donos.
- Skins são criações de terceiros e pertencem aos seus autores.
- Problema conhecido: com uma skin ativa, o vídeo de demonstração que o jogo toca depois de ~1,5 min parado na tela inicial
  (`attract.bik`) aparece verde. Aperte uma tecla para voltar ao menu.

## Licença e créditos
GNU GPL v3 ou posterior (veja `LICENSE`). Inclui o `d3d9.dll` do uMod (GPL v3, código em `umod/source`). Componentes de terceiros: veja `THIRD_PARTY_NOTICES.md`.
Inspirado no [SM2 Enhanced](https://github.com/JohnSwingMods/sm2-enhanced), de JohnSwingMods. Troca de texturas pelo [uMod](https://github.com/mathewwi/texmod). As licenças completas podem ser abertas na aba **Sobre** do launcher.

---

## English
Unofficial, free fan launcher for the PC version of **Spider-Man: Web of Shadows** (1.1.1.11540). Version **0.1.0**, first public development release.

- **Skins**: drag a TexMod `.tpf` onto the window; it is sorted into red suit, black suit or both (2 in 1) and applied in-game through the bundled uMod.
- **3D viewer** using the model, textures and animations read **from your own copy of the game**; suit thumbnails and poses.
- **Game options**: keyboard/mouse, **controller button remapping**, video.
- **Fixes**: startup crash, skipping the intro videos (green with skins), experimental 60 FPS mode.

Requirements: Windows 10/11 with WebView2 and your own legally obtained copy of the game. **No game files are distributed.**
Download the `.zip` from [**Releases**](https://github.com/soueusardi/wos-enhanced/releases) (it contains only `Web of Shadows Launcher.exe`) and run it. Settings, cache and skins are stored in `%LOCALAPPDATA%\Web of Shadows Launcher`. From source: Python 3 + `run_from_source.bat`; build the `.exe` with `build_exe.bat`.
The `.exe` is new and **not digitally signed**, so Windows SmartScreen may warn about it ("Windows protected your PC"): click **More info** → **Run anyway**. Verify the download with the SHA-256 in the release notes (`Get-FileHash .\WebOfShadowsLauncher-v0.1.0.zip -Algorithm SHA256`).
The launcher starts the game as a debugger to patch it in memory and temporarily copies a `d3d9.dll` into the game folder; some antivirus programs may flag this.
Known issue: with a skin active, the demo video the game plays after ~1.5 minutes idle on the title screen (`attract.bik`) shows up green; press a key to return to the menu.
Not affiliated with Activision, Marvel or Disney. License: GPL-3.0-or-later.
