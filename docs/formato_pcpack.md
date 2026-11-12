# Formato dos .PCPACK do Web of Shadows (PC 1.1.1.11540)

Engenharia reversa "limpa", feita só a partir dos arquivos do próprio jogo (nada copiado de ferramentas da comunidade).
Tudo em little-endian. Status: compressão, índice e texturas **confirmados**; malha/esqueleto **ainda não decifrados**.

## 1. Arquivo .PCPACK = sequência de blocos NCH (comprimidos)
- Um bloco a cada 0x80000 bytes do arquivo (512 KB), resto preenchido com `A1`.
- Cabeçalho de 0x20 bytes: `"NCH\0"`, `u32 tam_comprimido`, `u32 ?hash`, `u32 tam_descomprimido`,
  `u32 posição_no_fluxo_descomprimido`, `u32 ?hash`, `u32 tam_total (=comprimido+0x20)`, `u32 1`.
- Dados: **LZO1X** começando em +0x20. A janela é **contínua entre blocos** (um bloco pode copiar bytes do anterior):
  descomprimir todos em sequência no mesmo buffer.
- Ex.: MEGACITY.PCPACK 72 MB → 134 MB descomprimido (~18 s em Python puro).

## 2. Fluxo descomprimido
- +0x00: `1, 0xBF5, 0xC00, 0xBF5, 0, 0x20, tam_diretório, 0`; +0x20: `0x12345678, 0x10, ...` (contêiner).
- Diretório de recursos: entradas de 0x2C bytes `[hash, tipo, posição, tamanho, tamanho, 0, ?, 0, 0, 0, 5]`.
- O recurso de **tipo 0x19** começa com `"APKF"` e contém quase tudo (malhas, texturas, animações).

## 3. APKF
- +0x00 `"APKF"`, `0x107`, `0`, `0xFFFFFFFF`, `2`, `tam_cabeçalho`, `0`, depois tabela de seções.
- Seções a partir de +0x1C, registros de 0x1C bytes: `tag[4], a, b, idx, n, esz, flags`.
  Início das entradas = (endereço do registro + 12) + idx. Entradas de 12 bytes `[?, hash, tam_meta]`,
  ou 16 bytes quando flags = 0x01000004 (TEX e MESH): `[?, hash, tam_meta, tam_gpu]`. Ordem crescente de hash.
- Ordem das seções (MEGACITY): FX 74, MAT 2390, TEX 965, EFXB 338, MESH 1434, SKEL 3, ASKL 50, ANIM 1870.
- **Hash do nome**: `h = h*33 + byte`, começando em 0, nome em minúsculas, sem extensão.
  Os nomes estão em texto dentro do cabeçalho do APKF (100% dos recursos do MEGACITY ficam nomeados).
- Logo depois do cabeçalho: tabela `IMG` / `PHYS`, registros de 0x18 bytes `tag, 0, alinhamento, 0, tamanho, posição`.
  - IMG = metadados de cada recurso, um atrás do outro na ordem das seções/índice (às vezes com preenchimento entre seções;
    achar o início de cada seção procurando o hash da 1ª entrada em +4).
  - PHYS = dados de GPU: **todos os pixels das texturas (na ordem do índice TEX)**, depois os vértices/índices das malhas.
    Base PHYS = (posição do texto "IMG") − 4 + 0x30 + posição_PHYS. (MEGACITY: 0x25CC5C0 no fluxo descomprimido.)

## 4. Textura (metadado de 0x44 bytes)
- +0x04 hash, +0x10 largura, +0x14 altura, +0x18 profundidade (1), +0x1C nº de mipmaps, +0x20 formato (`DXT1`/`DXT5`/…).
- Pixels no PHYS: mip 0 primeiro, depois os menores (DXT padrão, sem cabeçalho DDS).
- **Validado** com o hash do uMod (CRC32 polinômio 0xEDB88320, início 0xFFFFFFFF, sem inversão final = `zlib.crc32 ^ 0xFFFFFFFF`,
  sobre os bytes do mip 0):

| Nome no jogo | Tamanho | Formato | Hash uMod |
|---|---|---|---|
| spiderman_redsuit_tex1_dif | 1024² | DXT1 | 1D51ED58 (vermelho, parte de cima) |
| spiderman_redsuit_tex2_dif | 512² | DXT1 | 6C03F0A0 (vermelho, parte de baixo) |
| spiderman_blacksuit1_tex1_dif | 512² | DXT1 | C46B23D2 (preto, parte de cima) |
| spiderman_blacksuit1_tex2_dif | 128² | DXT1 | 76B70474 (preto, parte de baixo) |
| spiderman_redsuit_tex1_nor | 512² | DXT5 | 1327B796 |
| spiderman_blacksuit1_tex1_nor | 512² | DXT5 | D9F1DCAE |

Também existem `_spe` (brilho), `tex2_nor/_spe`, `spiderman_suitchange_tex1/2` (256²).
Outros hashes conferidos: `redsuit_tex2_nor` A893AD3A, `blacksuit1_tex2_nor` B4A6F6A4 (512²),
`redsuit_tex1/2_spe` FBFCE874/4728B4B4, `blacksuit1_tex1/2_spe` E0A1AD7C/FC5F7F83 (brilho).

### Conversão para PNG (testada)
- DXT1/DXT5 decodificados em Python puro (sem numpy/Pillow): 1024² em ~1 s.
- Difusos: iguais aos PNGs do rip antigo (diferença média < 1/255, só arredondamento).
- Normal maps são "DXT5nm": **X no alfa, Y no verde** (R e B não usados). Para PNG: R=alfa, G=verde, B=Z calculado
  (`z = sqrt(1−x²−y²)`). O rip antigo pôs B=255; com Z calculado a diferença média para ele é 1,04.
- Traje preto: o rip antigo tinha `bsuit_*_n.png` 256² de **outra textura** (padrão de veias, não existe no MEGACITY).
  O do jogo é `blacksuit1_tex1_nor`/`tex2_nor` (512²) e combina com o desenho do traje preto (conferido visualmente).

## 5. Spider-Man no MEGACITY.PCPACK
- Malha: `ch_spiderman_rvb000` (seção MESH, hash 0x8C78CAA6).
- Esqueleto: `ch_spiderman_rvbskeleton_ch_spiderman_rvb000` (SKEL, 0x33315420); `ch_spiderman` (ASKL).
- Material: `ch_spiderman_rvbtex1` (MAT, 0x1BB85418).

## 6. Malha (seção MESH) — decifrada e validada
- Metadados de cada malha alinhados a 16 bytes (hash em +4). Spider-Man: 0x3E0 bytes.
- Dados de GPU no PHYS: logo depois de todos os pixels das texturas; cada malha alinhada a 4 bytes, na ordem do índice MESH.
  Dentro da malha: [vértices da submalha 1][índices da submalha 1, alinhado a 4][vértices da submalha 2]…
- Cabeçalho da malha: +0x0C nº de submalhas; +0x20 `f32 centro x,y,z`, +0x2C raio, +0x30 `f32 meia-largura x,y,z`
  (é a caixa usada para descomprimir as posições).
- Cada submalha tem: caixa própria, ponteiro de material, contagem de vértices (u32) e de índices (u32), lista de ossos (u16)
  e uma **declaração de vértices D3D9 padrão** (`D3DVERTEXELEMENT9`, 8 bytes cada, termina com stream 0xFF).
- Vértice do Spider-Man (48 bytes): +0x00 UV (FLOAT16_2), +0x04 tangente (FLOAT16_4), +0x0C posição (SHORT4N),
  +0x14 normal (FLOAT16_4), +0x1C cor, +0x20 pesos (UBYTE4N), +0x24 índices de osso (UBYTE4), +0x28 binormal (FLOAT16_4).
- Posição = centro + (valor/32767) × meia-largura. UV: o traje de baixo usa v entre 1 e 2 (usar a parte fracionária).
- Índices: **tri-strip** u16; pular triângulos degenerados e inverter a ordem nos ímpares.
  **Atenção:** o Direct3D usa sentido horário como frente; para OBJ/three.js cada triângulo precisa sair invertido
  (senão o boneco aparece "do avesso", translúcido). Conferido: orientação igual ao rip e às normais (7370/7372).
- Ponteiros dentro dos metadados (submalhas, declaração de vértices, material): posição = base_IMG + ponteiro×4,
  base_IMG = posição do texto "IMG" + 0x30. Endereços de vértices/índices: base_PHYS + ((endereço×4) & 0x0FFFFFFF).
- Spider-Man: 4 submalhas = parte de cima (2400 v), parte de cima extra (67 v), parte de baixo (1846 v), olhos (166 v).
  **Validação contra o gabarito**: 7372 triângulos (igual), 3688 posições únicas (igual), todos os UVs iguais (dif. ≤ 0,0007),
  materiais iguais (cima+olhos = 4120 faces, baixo = 3252). O rip antigo tem escala diferente (5–10%, não uniforme);
  os números do jogo dão: largura ±0,87, altura 2,14, profundidade −0,15..0,30.
- MEGACITY: metadado em 0x13D1A20 e dados GPU em 0x6EB0598 do fluxo descomprimido (o código deve calcular, não fixar).
- Esqueleto e pesos: veja a seção 7.

## 7. Esqueleto (SKEL) e pesos — decifrados e validados
- A malha aponta para o esqueleto: metadado da malha +0x14 = ponteiro (×4 a partir da base IMG) para o SKEL.
- SKEL `ch_spiderman_rvbskeleton_ch_spiderman_rvb000` (0x2D10 bytes): +0x04 hash, +0x08 nº de ossos (**80**), +0x0C ponteiro;
  depois 80 registros de 0x90 bytes a partir de +0x10: `[matriz A 4×4 (sempre identidade)][matriz B 4×4][tag, hash do nome,
  índice do pai (0xFFFFFFFF = raiz), ?]`. Nomes pelo hash ×33 (texto no cabeçalho do APKF): `bip01 pelvis`, `bip01 spine…`,
  `bip01 l/r upperarm…finger42`, `bip01 l/r thigh/calf/foot/toe0`, auxiliares (`bone l upperarm split1-3`, `bip01 l foretwist`,
  `… pivot`, `prop … hand/extra`, `sync`, `bip01_tentacle_main`). Pais sempre antes dos filhos? — ordenar por profundidade.
- Matriz B = **inversa da pose de repouso** (modelo → osso), D3D (vetor linha, translação na 4ª linha). A 4ª COLUNA tem lixo:
  zerar e pôr 1 no canto. Mundo de repouso = inversa(B). Coordenadas do jogo (as mesmas da malha antes da normalização).
  Conferido: pés y≈−1,04, ponta dos pés −1,19 (= mínimo da malha), cabeça 0,71, mãos x=±0,65 (pose em A), simétrico.
  `prop l/r extra` têm escala 0,42.
- Pesos no vértice: +0x20 UBYTE4N (soma sempre 255), +0x24 UBYTE4 = índices na **lista de ossos da submalha**
  (submalha +0x58, u16 × nbones) → índice no SKEL. Skinning linear: v' = Σ w·v·B·Mundo_atual. Conferido: repouso idêntico
  (desvio 1e-15); dobrar joelho/cabeça deforma certo.
- Atenção: a pele dos braços segue `upperarm split1-3` e `foretwist/foretwist1` (filhos do UPPERARM, não do forearm).
  Dobrar só o `forearm` move a mão mas deixa a pele do antebraço parada: o `foretwist` precisa acompanhar o `forearm`.

## 8. Animações (ANIM) — decodificadas (investigação da 8.7, ainda não integrado ao launcher)
- MEGACITY tem 1870 ANIM; 1001 usam o esqueleto de animação `ch_spiderman` (anim +0x10 = hash do ASKL). 1848 foram achadas
  procurando a assinatura `fc00xxxx, hash` com versão 0x20203 em +0x14 (a ordem do índice NÃO é a ordem no arquivo).
- Cabeçalho: +0x24 duração (s), +0x28 1/fps (30), +0x30 nº de quadros, +0x34 ptr cauda, +0x38 nº de valores por quadro,
  +0x44/+0x48 ponteiros dos fluxos, +0x4C..+0x68 8 posições em bits, +0x70/+0x74 lista/contagem de constantes inseridas,
  **+0x78 e +0xAC: máscaras de bits** (um bit por campo global da pose; o bit em +0x78 = campo vem no fluxo).
- **Decodificação**: emulada com Unicorn chamando o código do próprio jogo: `0x9CF1C0(quadro, saída)` com `ecx` = instância
  (inst+0x29 = anim, inst+0x2D = decodificador; dec+0x3C = anim, dec+0x140/0x144/0x148 = buffers). Ponteiros do cabeçalho
  (+0x34, +0x44, +0x48, +0x70) precisam virar endereços. Sai um vetor de inteiros por quadro. ~1 ms por quadro.
- **Ordem dos inteiros**: por tipo de campo, só os campos com bit na máscara: posições (3 ints), quaternions (4), dobradiças
  (1), correção FK (3), trajetória (0), chão (1), câmera (6), morph (1), escala (3)... (tabela de componentes no exe em
  0xDB6AE4; tamanho na pose em 0xDB6E20). Valor real = inteiro × escala do campo (ASKL: ponteiros em +0xE0 posições,
  +0xE4 quaternions, +0xE8 dobradiças, +0xEC correções).
- **ASKL `ch_spiderman`** (esqueleto NAL): 116 nós; +0x10C contagens por tipo (33 pos, 63 quat, 32 dobradiças, 34, 1, 1,
  1, 0, 14), +0x138 base global de cada tipo (0, 33, 96, 128, 162, 163, 164, 165, 165, 179); +0xC00/+0xC44/+0xCC4 nós de cada
  tipo; +0x2EA0/+0x2F88/+0x3070 (116 × int16) nó → índice do campo de posição/quaternion/dobradiça (−1 = não tem);
  +0xFD0: 116 blocos de 64 bytes = `[eixo da dobradiça (4f)][quaternion de repouso (x,y,z,w)][translação local (4f)]
  [tag, ?, hash do nome, 0]`. Os 80 ossos do SKEL casam pelo hash do nome; os outros 36 são auxiliares (`fakeroot`,
  `bip01 footsteps`, alvos de IK das mãos, tentáculos do simbionte `bip01_arm_*`, `game_camera`...).
- **Convenção (validada: o repouso da NAL reproduz o SKEL com erro 6e-7 após uma rotação global)**: quaternion (x,y,z,w)
  **conjugado**; filho = pai ∘ local (rotação do mundo = q_pai·q_local, posição = p_pai + q_pai·t). Raiz da cadeia:
  `bip01 pelvis` → `bip01 footsteps` → `fakeroot`. Dobradiça: q_local = q_repouso · eixoÂngulo(eixo, +ângulo).
- `mapa SKMP` (APKF tipo 0x1A) liga `ch_spiderman` a `rvb_skeleton1_standard` (reaproveitar animações), não ao SKEL.
- **Conteúdo conferido renderizando** (não pelo nome): `smrvictoryarmscrossed` (36 q) termina em pé de braços cruzados
  (q27–35); `smrhang` (41 q, loop) = pendurado pelos pés, joelhos em losango, braços dobrados (igual a docs/referencia);
  `smrhangclimb` (16 q) = invertido subindo a teia com as duas mãos entre as pernas; `sm3hangwebaction` = invertido atirando
  teia com um braço. Espera em pé: `smridlrlx`, `smbidlrlx`, `sm3idlrelax`, `smridllook*`, `sm3idl_tight`.
