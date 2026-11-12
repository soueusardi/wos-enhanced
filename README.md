# Web of Shadows Enhanced

An unofficial, free fan-made launcher for the PC version of **Spider-Man: Web of Shadows** (version 1.1.1.11540).

> Version **0.1.0**: first public release, currently under development.

[Português abaixo.]

## Features

- **Skins:** Drag and drop a TexMod `.tpf` file onto the launcher window. The launcher automatically identifies whether it contains the red suit, black suit, or both (2-in-1), and applies the textures in-game through the bundled uMod.
- **3D Viewer:** Displays the original 3D character model, textures and animations extracted **from your own copy of the game**, along with skin thumbnails and custom poses (crossed arms, hanging upside down from a web).
- **Game Options:** Keyboard and mouse settings, **controller button remapping**, and video settings.
- **Fixes:** Startup crash fix, intro video skipping (which otherwise appears green when using custom skins), and an experimental 60 FPS mode.

## Requirements

- Windows 10 or 11 with WebView2 (included with Windows 11).
- Your own legally obtained copy of the game. **No original game files are distributed.**

## Installation and Usage

1. Download the `.zip` file from the [**Releases**](https://github.com/soueusardi/wos-enhanced/releases) page. It contains only `Web of Shadows Launcher.exe`.
2. Run the `.exe` (it can be placed in any folder). Settings, cache and skins are stored in `%LOCALAPPDATA%\Web of Shadows Launcher`.
3. If the launcher does not automatically detect the game, use **Change Folder**.
4. To verify your download, compare its SHA-256 hash with the one provided in the release notes (`docs/RELEASE_NOTES_v0.1.0.md`). Run the following command in PowerShell:

   ```powershell
   Get-FileHash .\WebOfShadowsLauncher-v0.1.0.zip -Algorithm SHA256
   ```

### Running from Source

For development, install Python 3 and run `run_from_source.bat`.

To build the executable, run `build_exe.bat`. The resulting `.exe` will be placed in the `dist/` folder.

## Important Notices

- The executable is new and **not digitally signed**. Windows may display a **SmartScreen** warning ("Windows protected your PC"). Click **More info** → **Run anyway**.
- To apply certain fixes, the launcher starts the game as a **debugger** and modifies the game's memory (the executable file on disk is never modified). It also copies a `d3d9.dll` file into the game folder while the game is running. Some antivirus software may flag this behavior.
- This project is not affiliated with, endorsed by or sponsored by Activision, Marvel, Disney or any other holder of the game's rights. All trademarks belong to their respective owners.
- Custom skins are third-party creations and remain the property of their respective authors.
- **Known issue:** When a custom skin is active, the demonstration video played by the game after approximately 1.5 minutes of inactivity on the title screen (`attract.bik`) appears green. Press any key to return to the menu.

## License and Credits

Licensed under **GNU GPL v3 or later** (see `LICENSE`).

Includes the uMod `d3d9.dll` (GPL v3; source code available in `umod/source`). For third-party components and their licenses, see `THIRD_PARTY_NOTICES.md`.

Inspired by [SM2 Enhanced](https://github.com/JohnSwingMods/sm2-enhanced) by JohnSwingMods. Texture replacement powered by [uMod](https://github.com/mathewwi/texmod).

Full license information is also available in the launcher's **About** tab.

---

# Web of Shadows Enhanced

Launcher de fã, **não oficial e gratuito**, para a versão de PC de **Spider-Man: Web of Shadows** (versão 1.1.1.11540).

> Versão **0.1.0**: primeira versão pública, ainda em desenvolvimento.

## Funcionalidades

- **Trajes:** Arraste um arquivo `.tpf` (TexMod) para a janela do launcher. Ele identifica automaticamente se o arquivo contém o traje vermelho, o preto ou ambos (2 em 1), e aplica as texturas no jogo pelo uMod, que já vem integrado.
- **Visualizador 3D:** Exibe o modelo 3D original, as texturas e as animações extraídas **da sua própria cópia do jogo**, além de miniaturas das skins e poses personalizadas (braços cruzados, pendurado na teia).
- **Opções do jogo:** Configurações de teclado e mouse, **remapeamento dos botões do controle** e opções de vídeo.
- **Correções:** Correção da falha ao abrir o jogo, opção para pular os vídeos de abertura (que ficam verdes ao utilizar skins) e modo experimental de 60 FPS.

## Requisitos

- Windows 10 ou 11 com WebView2 (já incluído no Windows 11).
- Uma cópia própria do jogo, adquirida legalmente. **Nenhum arquivo original do jogo é distribuído.**

## Instalação e uso

1. Baixe o arquivo `.zip` na página de [**Releases**](https://github.com/soueusardi/wos-enhanced/releases). Ele contém apenas o `Web of Shadows Launcher.exe`.
2. Execute o `.exe` (ele pode ficar em qualquer pasta). As configurações, o cache e as skins ficam armazenados em `%LOCALAPPDATA%\Web of Shadows Launcher`.
3. Se o launcher não encontrar o jogo automaticamente, utilize **Mudar pasta**.
4. Para verificar o download, compare o hash SHA-256 com o informado nas notas da versão (`docs/RELEASE_NOTES_v0.1.0.md`). Execute o seguinte comando no PowerShell:

   ```powershell
   Get-FileHash .\WebOfShadowsLauncher-v0.1.0.zip -Algorithm SHA256
   ```

### Executando pelo código-fonte

Para desenvolvimento, instale o Python 3 e execute `run_from_source.bat`.

Para gerar o executável, execute `build_exe.bat`. O resultado será salvo na pasta `dist/`.

## Avisos importantes

- O executável é novo e **não possui assinatura digital**. O Windows pode exibir um aviso do **SmartScreen** ("O Windows protegeu o computador"). Clique em **Mais informações** → **Executar assim mesmo**.
- Para aplicar determinadas correções, o launcher abre o jogo como um **depurador** e modifica sua memória (o arquivo `.exe` em disco nunca é alterado). Ele também copia um arquivo `d3d9.dll` para a pasta do jogo enquanto ele está em execução. Alguns antivírus podem sinalizar esse comportamento.
- Este projeto não possui afiliação, aprovação ou patrocínio da Activision, Marvel, Disney ou qualquer outro detentor dos direitos do jogo. Todas as marcas pertencem aos seus respectivos proprietários.
- As skins personalizadas são criações de terceiros e pertencem aos seus respectivos autores.
- **Problema conhecido:** Com uma skin ativa, o vídeo de demonstração reproduzido pelo jogo após aproximadamente 1,5 minuto de inatividade na tela inicial (`attract.bik`) aparece verde. Pressione qualquer tecla para retornar ao menu.

## Licença e créditos

Licenciado sob **GNU GPL v3 ou posterior** (consulte o arquivo `LICENSE`).

Inclui o `d3d9.dll` do uMod (GPL v3; código-fonte disponível em `umod/source`). Para consultar os componentes de terceiros e suas respectivas licenças, veja `THIRD_PARTY_NOTICES.md`.

Inspirado no [SM2 Enhanced](https://github.com/JohnSwingMods/sm2-enhanced), de JohnSwingMods. A substituição de texturas é realizada pelo [uMod](https://github.com/mathewwi/texmod).

As informações completas sobre as licenças também estão disponíveis na aba **Sobre** do launcher.
