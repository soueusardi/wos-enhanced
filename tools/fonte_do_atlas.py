"""Gera a fonte dos botões (web/fonts/wos-ui.otf) a partir do atlas de fonte do jogo (imagem 512x256, 6 linhas de 37 px).
Uso: python tools/fonte_do_atlas.py <atlas.png> [saida.otf]
Precisa de: pip install numpy pillow scipy potracer fonttools (só para gerar; o launcher não precisa disso).
Como funciona: separa as letras de cada linha (pedaços que se sobrepõem na horizontal viram uma letra; aspas e ™ partidos
são juntados até a contagem bater com ROWS), apaga os vizinhos, amplia 8x, vetoriza com o potrace e monta um OTF (CFF).
A ordem dos caracteres em ROWS foi conferida contra a imagem; \x00 = caixa de caractere ausente no atlas."""
import numpy as np, json
from PIL import Image
from scipy import ndimage
import potrace
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.cu2quPen import Cu2QuPen

import sys
SRC=sys.argv[1] if len(sys.argv)>1 else 'fonte_atlas.png'
OUT=sys.argv[2] if len(sys.argv)>2 else 'web/fonts/wos-ui.otf'
gray=np.asarray(Image.open(SRC).convert('L')).astype(np.float32)
ink=gray>52; P=37
ROWS=[
 '!"#$%&\'()*+,-./0123456789:;<=>?@A',
 'BCDEFGHIJKLMNOPQRSTUVWXY',
 'Z[\\]^_`abcdefghijklmnopqrstuvw',
 'xyz{|}~Œ™œ\x00\x00Ÿ¡©ª«\x00\xad®¯°º»¿ÀÁÂ',
 'ÃÄÅÆÇÈÉÊËÌÍÎÏ\x00ÑÒÓÔÕÖÙÚÛÜßà',
 'áâãäåæçèéêëìíîï\x00ñòóôõöùúûü\x00\x00ÿ',
]
def groups_of(r):
    sub=ink[r*P:(r+1)*P]
    lab,n=ndimage.label(sub,structure=np.ones((3,3)))
    boxes=sorted([(s[1].start,s[1].stop) for s in ndimage.find_objects(lab)])
    g=[]
    for a,b in boxes:
        if g and a<g[-1][1]: g[-1]=[g[-1][0],max(g[-1][1],b)]
        else: g.append([a,b])
    return g
glyphs={}
for r,chars in enumerate(ROWS):
    g=groups_of(r)
    # junta pedaços extras (aspas, ™) pelo menor espaço até a contagem bater
    while len(g)>len(chars):
        gaps=[(g[i+1][0]-g[i][1], (g[i][1]-g[i][0])+(g[i+1][1]-g[i+1][0]), i) for i in range(len(g)-1)]
        # prefere juntar pedaços estreitos com espaço pequeno
        i=min(gaps,key=lambda t:(t[0],t[1]))[2]
        g[i]=[g[i][0],g[i+1][1]]; del g[i+1]
    assert len(g)==len(chars),(r,len(g),len(chars))
    for (a,b),ch in zip(g,chars):
        if ch!='\x00': glyphs[ch]=(r,a,b)
# linha de base de cada linha = fundo mais comum dos glifos
def bottom(r,a,b):
    col=ink[r*P:(r+1)*P,a:b].any(1); ys=np.nonzero(col)[0]; return ys.max()+1, ys.min()
base={}
for r,chars in enumerate(ROWS):
    bots=[bottom(*glyphs[c])[0] for c in chars if c in glyphs and c.isalnum() and c not in 'gjpqyQ,;çÇ']
    base[r]=max(set(bots),key=bots.count)
capH=np.median([base[1]-bottom(*glyphs[c])[1] for c in 'BDEFHIKLMNPRTUVXY'])
xH=np.median([base[2]-bottom(*glyphs[c])[1] for c in 'acemnorsuvw'])
print('linhas de base:',base,'| altura maiúscula',capH,'px | altura x',xH,'px')
UPM=1000; S=700/capH; UP=8; SIDE=1.5
def trace(r,a,b):
    pad=4
    y0=r*P; crop=gray[y0:y0+P, max(a-pad,0):b+pad].copy()
    xs=np.arange(max(a-pad,0),max(a-pad,0)+crop.shape[1]); crop[:,(xs<a)|(xs>=b)]=12   # só a própria letra
    im=Image.fromarray(crop.astype(np.uint8)).resize((crop.shape[1]*UP,crop.shape[0]*UP),Image.BICUBIC)
    bm=np.asarray(im)>((52+200)/2)
    path=potrace.Bitmap(~bm).trace(turdsize=6*UP,alphamax=1.0,opticurve=True,opttolerance=0.2)
    xoff=max(a-pad,0)
    def T(p): return ((p.x/UP + xoff - a + SIDE)*S, (base[r] - p.y/UP)*S)
    return path,T
fb=FontBuilder(UPM,isTTF=False)
names=['.notdef','space']+[f'uni{ord(c):04X}' for c in glyphs]
fb.setupGlyphOrder(names)
cmap={32:'space'}; cmap.update({ord(c):f'uni{ord(c):04X}' for c in glyphs}); cmap[0xA0]='space'
fb.setupCharacterMap(cmap)
charstrings={}; metrics={}
def blank(w):
    pen=T2CharStringPen(w,None); return pen.getCharString()
charstrings['.notdef']=blank(500); metrics['.notdef']=(500,0)
sp=int(round(capH*0.32*S)); charstrings['space']=blank(sp); metrics['space']=(sp,0)
for c,(r,a,b) in glyphs.items():
    adv=int(round((b-a+2*SIDE)*S))
    path,T=trace(r,a,b)
    pen=T2CharStringPen(adv,None)
    for curve in path:
        pen.moveTo(T(curve.start_point))
        for seg in curve.segments:
            if seg.is_corner: pen.lineTo(T(seg.c)); pen.lineTo(T(seg.end_point))
            else: pen.curveTo(T(seg.c1),T(seg.c2),T(seg.end_point))
        pen.closePath()
    charstrings[f'uni{ord(c):04X}']=pen.getCharString(); metrics[f'uni{ord(c):04X}']=(adv,0)
fb.setupCFF('WebOfShadowsUI',{'FullName':'Web of Shadows UI'},charstrings,{})
lsb={}
fb.setupHorizontalMetrics(metrics)
asc=int(round((capH*1.32)*S)); desc=-int(round(capH*0.36*S))
fb.setupHorizontalHeader(ascent=asc,descent=desc)
fb.setupNameTable({'familyName':'Web of Shadows UI','styleName':'Regular'})
fb.setupOS2(sTypoAscender=asc,sTypoDescender=desc,usWinAscent=asc,usWinDescent=-desc,sxHeight=int(xH*S),sCapHeight=700)
fb.setupPost()
fb.save(OUT)
print('fonte gravada em', OUT)
print('glifos:',len(glyphs),'| exemplo larguras: A',metrics['uni0041'][0],'a',metrics['uni0061'][0],'espaço',sp)
