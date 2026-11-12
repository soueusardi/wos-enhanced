# Web of Shadows Launcher v0.1.0

**Português** · [English](#english)

Launcher de fã, **não oficial e gratuito**, para a versão de PC de **Spider-Man: Web of Shadows** (versão 1.1.1.11540).
Esta é a **primeira versão pública** e ainda está em desenvolvimento.

## O que é
- **Skins**: arraste um `.tpf` (TexMod) para a janela. O launcher descobre se é do traje vermelho, do preto ou dos dois
  (2 em 1) e aplica no jogo pelo uMod, que vai embutido.
- **Visualizador 3D** com o modelo, as texturas e as animações lidos **da sua própria cópia do jogo**, com miniaturas das
  skins e poses (braços cruzados, pendurado na teia).
- **Opções do jogo**: teclado e mouse, **controle com troca de botões** e vídeo.
- **Correções**: a queda ao abrir o jogo, pular os vídeos de abertura (que ficam verdes com skins) e um modo experimental
  para 60 FPS estável.

## Requisitos
- Windows 10 ou 11 (64 bits) com o **WebView2** (já vem no Windows 11 e nas versões atualizadas do Windows 10).
- Uma cópia própria do jogo, **versão 1.1.1.11540**, adquirida legalmente. **Nenhum arquivo do jogo é distribuído.**

## Como usar
1. Baixe `WebOfShadowsLauncher-v0.1.0.zip` e extraia. Ele contém só o `Web of Shadows Launcher.exe`.
2. Coloque o `.exe` em qualquer pasta e abra com dois cliques. Não precisa instalar.
3. Se ele não achar o jogo sozinho, use **Mudar pasta**. Na primeira vez, ele leva uns 10 segundos para ler o modelo do jogo.

## Onde ficam os dados
Configurações, log (`launcher.log`), cache e skins ficam em:
`%LOCALAPPDATA%\Web of Shadows Launcher`
(cole esse caminho na barra de endereço do Explorador de Arquivos). A pasta do `.exe` continua só com o `.exe`.
Para desinstalar, apague o `.exe` e essa pasta.

## Aviso: SmartScreen e antivírus
O `.exe` é novo e **não tem assinatura digital**. Por isso, o Windows pode mostrar o aviso do **SmartScreen**
("O Windows protegeu o computador"): clique em **Mais informações** → **Executar assim mesmo**.
Alguns antivírus também podem alertar porque, para aplicar as correções, o launcher abre o jogo como um **depurador**,
altera a memória do jogo (nunca o `.exe` em disco) e copia um `d3d9.dll` (uMod) para a pasta do jogo enquanto ele roda,
apagando-o quando o jogo fecha. O código-fonte completo está neste repositório e você pode conferir o arquivo pelo SHA-256 abaixo.

## Problema conhecido
- Se você deixar o jogo parado na tela inicial por cerca de 1 minuto e meio, o vídeo de demonstração (`attract.bik`)
  aparece **verde** com uma skin ativa. Aperte uma tecla para voltar ao menu.

## Licença
GNU GPL v3 ou posterior. Inclui o `d3d9.dll` do uMod (GPL v3). As licenças completas, inclusive dos componentes de
terceiros, podem ser abertas em **Opções → Sobre**. Não é afiliado à Activision, Marvel ou Disney.

## Verificação (SHA-256)
| Arquivo | SHA-256 |
|---|---|
| `WebOfShadowsLauncher-v0.1.0.zip` | `ED0E79871F2DE27CFF1C5F854F4AED4C482F40857746978F1471245C87E45223` |
| `Web of Shadows Launcher.exe` | `56DBEF30FA9831D47BEFBABC6F775E9CC0D13F3B02F28B7CC7A1C9455BCB85E7` |

No PowerShell: `Get-FileHash .\WebOfShadowsLauncher-v0.1.0.zip -Algorithm SHA256`

---

## English

Unofficial, **free fan launcher** for the PC version of **Spider-Man: Web of Shadows** (version 1.1.1.11540).
This is the **first public release** and it is still in development.

### What it is
- **Skins**: drag a TexMod `.tpf` onto the window. The launcher detects whether it is for the red suit, the black suit or
  both (2 in 1) and applies it in-game through the bundled uMod.
- **3D viewer** using the model, textures and animations read **from your own copy of the game**, with skin thumbnails
  and poses (arms crossed, hanging from a web).
- **Game options**: keyboard and mouse, **controller button remapping** and video.
- **Fixes**: the startup crash, skipping the intro videos (which turn green with skins) and an experimental stable 60 FPS mode.

### Requirements
- Windows 10 or 11 (64-bit) with **WebView2** (included in Windows 11 and in up-to-date Windows 10).
- Your own legally obtained copy of the game, **version 1.1.1.11540**. **No game files are distributed.**

### How to use
1. Download `WebOfShadowsLauncher-v0.1.0.zip` and extract it. It contains only `Web of Shadows Launcher.exe`.
2. Put the `.exe` in any folder and double-click it. No installation needed.
3. If it does not find the game automatically, use **Change folder**. The first time, it takes about 10 seconds to read
   the model from the game.

### Where your data is stored
Settings, log (`launcher.log`), cache and skins are stored in:
`%LOCALAPPDATA%\Web of Shadows Launcher`
(paste that path into File Explorer's address bar). The `.exe` folder keeps only the `.exe`.
To uninstall, delete the `.exe` and that folder.

### Warning: SmartScreen and antivirus
The `.exe` is new and **not digitally signed**, so Windows may show a **SmartScreen** warning
("Windows protected your PC"): click **More info** → **Run anyway**.
Some antivirus programs may also flag it because, to apply its fixes, the launcher starts the game as a **debugger**,
patches the game's memory (never the `.exe` on disk) and copies a `d3d9.dll` (uMod) into the game folder while it runs,
deleting it when the game closes. The full source code is in this repository, and you can verify the file with the SHA-256 below.

### Known issue
- If you leave the game idle on the title screen for about a minute and a half, the demo video (`attract.bik`) shows up
  **green** while a skin is active. Press a key to return to the menu.

### License
GNU GPL v3 or later. Includes uMod's `d3d9.dll` (GPL v3). Full license texts, including third-party components, are
available under **Options → About**. Not affiliated with Activision, Marvel or Disney.

### Checksums (SHA-256)
| File | SHA-256 |
|---|---|
| `WebOfShadowsLauncher-v0.1.0.zip` | `ED0E79871F2DE27CFF1C5F854F4AED4C482F40857746978F1471245C87E45223` |
| `Web of Shadows Launcher.exe` | `56DBEF30FA9831D47BEFBABC6F775E9CC0D13F3B02F28B7CC7A1C9455BCB85E7` |
