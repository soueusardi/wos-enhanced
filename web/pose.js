/* Poses do modelo. Com o esqueleto do jogo (GameRig, mais abaixo) usa os ossos e pesos reais; sem ele, cai no
   esqueleto automático daqui (pesos por distância).
   Cada osso pode receber: direção alvo (dirs), para onde aponta o seu "lado de cima" (ups: dorso da mão, joelho, rosto)
   ou um giro local em relação ao osso pai (local, em graus). O resto é cinemática direta e "skinning" linear. */
(function(){
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const UP = V(0, 1, 0), FWD = V(0, 0, 1);

  // articulações em repouso (medidas na malha); s = +1 (x>0) ou -1 (x<0)
  function limb(s){
    return {
      shoulder: V(s*0.20, 1.55, 0.00), elbow: V(s*0.375, 1.43, 0.00), wrist: V(s*0.55, 1.31, 0.01),
      knuckle: V(s*0.69, 1.205, 0.045), fmid: V(s*0.74, 1.165, 0.058), tip: V(s*0.787, 1.127, 0.07),
      thumb0: V(s*0.60, 1.24, 0.05), thumb1: V(s*0.645, 1.17, 0.10),
      hip: V(s*0.11, 0.93, 0.03), knee: V(s*0.15, 0.52, 0.02), ankle: V(s*0.185, 0.10, 0.02), toe: V(s*0.19, 0.02, 0.22)
    };
  }
  const slab = (a, b) => [-0.035, 0, 0.035].map(dz => [a.clone().add(V(0, 0, dz)), b.clone().add(V(0, 0, dz))]);   // dedos lado a lado
  // nome, pai, pivô, fim, abertura da influência (sigma), referência de "cima", segmentos extras para os pesos
  const BONES = [
    ['pelvis', null,     V(0, 0.90, 0.03), V(0, 1.10, 0.03), 0.15, FWD],
    ['spine',  'pelvis', V(0, 1.10, 0.03), V(0, 1.50, 0.03), 0.17, FWD],
    ['neck',   'spine',  V(0, 1.52, 0.02), V(0, 1.68, 0.02), 0.07, FWD],
    ['head',   'neck',   V(0, 1.68, 0.02), V(0, 1.90, 0.02), 0.14, FWD],
  ];
  [['R', limb(+1)], ['L', limb(-1)]].forEach(([n, j]) => {
    BONES.push(['uarm' + n, 'spine', j.shoulder, j.elbow, 0.075, UP]);
    BONES.push(['farm' + n, 'uarm' + n, j.elbow, j.wrist, 0.060, UP]);
    BONES.push(['hand' + n, 'farm' + n, j.wrist, j.knuckle, 0.050, UP, [[j.wrist, j.knuckle], [j.thumb0, j.thumb1]]]);
    BONES.push(['fing1' + n, 'hand' + n, j.knuckle, j.fmid, 0.028, UP, slab(j.knuckle, j.fmid)]);
    BONES.push(['fing2' + n, 'fing1' + n, j.fmid, j.tip, 0.028, UP, slab(j.fmid, j.tip)]);
    BONES.push(['thigh' + n, 'pelvis', j.hip, j.knee, 0.095, FWD]);
    BONES.push(['shin' + n, 'thigh' + n, j.knee, j.ankle, 0.075, FWD]);
    BONES.push(['foot' + n, 'shin' + n, j.ankle, j.toe, 0.075, UP]);
  });
  const IDX = {}; BONES.forEach((b, i) => IDX[b[0]] = i);

  function distSeg(p, a, b){
    const ab = b.clone().sub(a), t = Math.max(0, Math.min(1, p.clone().sub(a).dot(ab) / ab.lengthSq()));
    return p.distanceTo(a.clone().add(ab.multiplyScalar(t)));
  }
  function frame(dir, up){            // base ortonormal: x = direção do osso, y = "cima" (ortogonalizado)
    const x = dir.clone().normalize();
    let y = up.clone().sub(x.clone().multiplyScalar(up.dot(x)));
    if(y.lengthSq() < 1e-6) y = V(1, 0, 0).sub(x.clone().multiplyScalar(x.x));
    y.normalize();
    return new THREE.Matrix4().makeBasis(x, y, new THREE.Vector3().crossVectors(x, y));
  }

  class Rig {
    constructor(geometry){
      this.geo = geometry;
      this.pos0 = Float32Array.from(geometry.attributes.position.array);
      this.nor0 = Float32Array.from(geometry.attributes.normal.array);
      this.n = this.pos0.length / 3;
      this.skin = [];
      const p = new THREE.Vector3(), cache = new Map();
      for(let i = 0; i < this.n; i++){
        p.set(this.pos0[3*i], this.pos0[3*i+1], this.pos0[3*i+2]);
        const key = p.x.toFixed(5) + ',' + p.y.toFixed(5) + ',' + p.z.toFixed(5);
        if(cache.has(key)){ this.skin.push(cache.get(key)); continue; }
        const ws = BONES.map(b => {
          const name = b[0], side = name.endsWith('R') ? 1 : (name.endsWith('L') ? -1 : 0);
          if(side && p.x * side < -0.05) return 0;               // osso de um lado não puxa o outro lado
          const segs = b[6] || [[b[2], b[3]]];
          const d = Math.min(...segs.map(s => distSeg(p, s[0], s[1]))) / b[4];
          return Math.exp(-d * d);
        });
        const order = ws.map((w, k) => [k, w]).sort((a, b) => b[1] - a[1]).slice(0, 4);
        const sum = order.reduce((s, o) => s + o[1], 0) || 1;
        const sk = order.map(o => [o[0], o[1] / sum]);
        cache.set(key, sk); this.skin.push(sk);
      }
      this.restDir = BONES.map(b => b[3].clone().sub(b[2]).normalize());
      this.restInv = BONES.map((b, i) => frame(this.restDir[i], b[5]).invert());
      this.M = null; this.shift = V(0, 0, 0);
    }

    // pose = { dirs:{osso:[x,y,z]}, ups:{osso:[x,y,z]}, local:{osso:[rx,ry,rz] graus}, root:{rotX,rotY,rotZ}, ground:true }
    apply(pose){
      pose = pose || {};
      const D2R = Math.PI / 180;
      const q = BONES.map(() => new THREE.Quaternion()), M = BONES.map(() => new THREE.Matrix4());
      const t2 = new THREE.Matrix4(), rot = new THREE.Matrix4();
      BONES.forEach((b, i) => {
        const parent = b[1] === null ? null : IDX[b[1]];
        let qt = parent === null ? new THREE.Quaternion() : q[parent].clone();
        const d = pose.dirs && pose.dirs[b[0]], u = pose.ups && pose.ups[b[0]], l = pose.local && pose.local[b[0]];
        if(d && u){
          const m = frame(V(d[0], d[1], d[2]), V(u[0], u[1], u[2])).multiply(this.restInv[i]);
          qt = new THREE.Quaternion().setFromRotationMatrix(m);
        } else if(d){
          qt = new THREE.Quaternion().setFromUnitVectors(this.restDir[i], V(d[0], d[1], d[2]).normalize());
        }
        if(l) qt = qt.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(l[0]*D2R, l[1]*D2R, l[2]*D2R)));
        q[i] = qt;
        const pv = b[2], pc = parent === null ? pv.clone() : pv.clone().applyMatrix4(M[parent]);
        t2.makeTranslation(-pv.x, -pv.y, -pv.z); rot.makeRotationFromQuaternion(qt);
        M[i] = new THREE.Matrix4().makeTranslation(pc.x, pc.y, pc.z).multiply(rot).multiply(t2);
      });
      let G = new THREE.Matrix4();
      if(pose.root){
        const c = BONES[0][2], r = pose.root, e = new THREE.Euler((r.rotX||0)*D2R, (r.rotY||0)*D2R, (r.rotZ||0)*D2R);
        G = new THREE.Matrix4().makeTranslation(c.x, c.y, c.z).multiply(new THREE.Matrix4().makeRotationFromEuler(e)).multiply(new THREE.Matrix4().makeTranslation(-c.x, -c.y, -c.z));
      }
      const MG = M.map(m => G.clone().multiply(m));
      const pos = this.geo.attributes.position.array, nor = this.geo.attributes.normal.array;
      const v = new THREE.Vector3(), n = new THREE.Vector3(), a = new THREE.Vector3(), nn = new THREE.Vector3();
      for(let i = 0; i < this.n; i++){
        v.set(this.pos0[3*i], this.pos0[3*i+1], this.pos0[3*i+2]); n.set(this.nor0[3*i], this.nor0[3*i+1], this.nor0[3*i+2]);
        a.set(0, 0, 0); nn.set(0, 0, 0);
        for(const [bi, w] of this.skin[i]){ a.addScaledVector(v.clone().applyMatrix4(MG[bi]), w); nn.addScaledVector(n.clone().transformDirection(MG[bi]), w); }
        pos[3*i] = a.x; pos[3*i+1] = a.y; pos[3*i+2] = a.z;
        nn.normalize(); nor[3*i] = nn.x; nor[3*i+1] = nn.y; nor[3*i+2] = nn.z;
      }
      this.shift.set(0, 0, 0);
      if(pose.ground){   // apoia o ponto mais baixo em y=0 e centraliza em x/z
        let minY = 1e9, cx = 0, cz = 0;
        for(let i = 0; i < this.n; i++){ minY = Math.min(minY, pos[3*i+1]); cx += pos[3*i]; cz += pos[3*i+2]; }
        cx /= this.n; cz /= this.n; if(pose.centerX === false) cx = 0;
        for(let i = 0; i < this.n; i++){ pos[3*i] -= cx; pos[3*i+1] -= minY; pos[3*i+2] -= cz; }
        this.shift.set(-cx, -minY, -cz);
      }
      this.M = MG;
      this.geo.attributes.position.needsUpdate = true; this.geo.attributes.normal.needsUpdate = true;
      this.geo.computeBoundingSphere(); this.geo.computeBoundingBox();
    }
    // onde foi parar um ponto preso a um osso (em coordenadas de repouso), depois da pose
    point(bone, p){ return V(p[0], p[1], p[2]).applyMatrix4(this.M[IDX[bone]]).add(this.shift); }
  }
  window.PoseRig = Rig;

  /* ---------- Rig com o esqueleto REAL do jogo (cache/gameassets/skeleton.json) ----------
     Mesma linguagem de pose (dirs/ups/local/root/ground), mas articulações nas posições do jogo e pesos da pele do jogo.
     Os nomes de pose (pelvis, spine, uarmR...) apontam para ossos do jogo; os ossos não citados acompanham o pai. */
  const GAME_MAP = {   // nome da pose -> [ossos do jogo controlados, osso alvo da direção (ou null), referência de "cima"]
    pelvis: [['bip01 pelvis'], 'bip01 spine1', FWD],
    spine:  [['bip01 spine'], 'bip01 neck', FWD],
    chest:  [['bip01 spine2'], 'bip01 neck', FWD],
    neck:   [['bip01 neck'], 'bip01 head', FWD],
    head:   [['bip01 head'], null, FWD],
  };
  ['r', 'l'].forEach(s => {
    const S = s.toUpperCase(), b = n => 'bip01 ' + s + ' ' + n;
    GAME_MAP['clav' + S]  = [[b('clavicle')], b('upperarm'), UP];
    GAME_MAP['uarm' + S]  = [[b('upperarm')], b('forearm'), UP];
    GAME_MAP['farm' + S]  = [[b('forearm')], b('hand'), UP];
    GAME_MAP['hand' + S]  = [[b('hand')], b('finger2'), UP];
    GAME_MAP['fing1' + S] = [[1, 2, 3, 4].map(k => b('finger' + k)), 'child', UP];
    GAME_MAP['fing2' + S] = [[1, 2, 3, 4].flatMap(k => [b('finger' + k + '1'), b('finger' + k + '2')]), 'child', UP];
    GAME_MAP['thumb' + S] = [[b('finger01'), b('finger02')], 'child', UP];
    GAME_MAP['thigh' + S] = [[b('thigh')], b('calf'), FWD];
    GAME_MAP['shin' + S]  = [[b('calf')], b('foot'), FWD];
    GAME_MAP['foot' + S]  = [[b('foot')], b('toe0'), UP];
  });
  // cadeias que aceitam alvo (pose.ik: { armR: {to: [x,y,z] do punho, pole: [x,y,z] para onde aponta o cotovelo}, legR: ... })
  const IK_TOP = { uarmR: {key: 'armR', kind: 'arm', side: 1}, uarmL: {key: 'armL', kind: 'arm', side: -1},
                   thighR: {key: 'legR', kind: 'leg'}, thighL: {key: 'legL', kind: 'leg'} };
  // ossos auxiliares que, para posar, seguem outro pai (no jogo quem os move é a animação)
  const REPARENT = {'bip01 r foretwist': 'bip01 r forearm', 'bip01 l foretwist': 'bip01 l forearm',
                    'bip01 r clavicle': 'bip01 spine2', 'bip01 l clavicle': 'bip01 spine2'};

  class GameRig {
    constructor(geometry, objText, skel){
      this.geo = geometry;
      this.pos0 = Float32Array.from(geometry.attributes.position.array);
      this.nor0 = Float32Array.from(geometry.attributes.normal.array);
      this.n = this.pos0.length / 3;
      // cada canto de triângulo do three.js -> vértice do OBJ (o OBJLoader segue a ordem das linhas 'f')
      const corner = [];
      for(const line of objText.split('\n')){
        if(line.charCodeAt(0) !== 102 || line.charCodeAt(1) !== 32) continue;   // 'f '
        const t = line.trim().split(/\s+/);
        for(let k = 1; k < t.length; k++) corner.push(parseInt(t[k], 10) - 1);
      }
      if(corner.length !== this.n) throw new Error('OBJ e malha não batem (' + corner.length + ' x ' + this.n + ')');
      const B = skel.bones, NB = B.length, id = {};
      B.forEach((b, i) => id[b.name] = i);
      this.id = id;
      this.parent = B.map(b => (REPARENT[b.name] !== undefined && id[REPARENT[b.name]] !== undefined) ? id[REPARENT[b.name]] : b.parent);
      const depth = i => { let d = 0; while(this.parent[i] >= 0){ i = this.parent[i]; d++; } return d; };
      this.order = B.map((b, i) => i).sort((a, b) => depth(a) - depth(b));
      this.pv = B.map(b => V(b.pos[0], b.pos[1], b.pos[2]));
      const kids = B.map(() => []); B.forEach((b, i) => { if(b.parent >= 0) kids[b.parent].push(i); });
      // controles: osso do jogo -> {nome da pose, direção de repouso, base de repouso invertida}
      this.ctl = {};
      for(const [pname, [names, target, upRef]] of Object.entries(GAME_MAP)){
        for(const nm of names){
          const i = id[nm]; if(i === undefined) continue;
          let dir;
          if(target === 'child'){
            const c = kids[i].find(k => /finger/.test(B[k].name));
            dir = c !== undefined ? this.pv[c].clone().sub(this.pv[i]) : this.pv[i].clone().sub(this.pv[B[i].parent]);
          } else if(target && id[target] !== undefined) dir = this.pv[id[target]].clone().sub(this.pv[i]);
          else dir = V(0, 1, 0);
          dir.normalize();
          this.ctl[i] = {name: pname, dir, restInv: frame(dir, upRef).invert()};
        }
      }
      // pesos por canto
      const si = skel.skin_index, sw = skel.skin_weight;
      this.skin = new Array(this.n);
      for(let c = 0; c < this.n; c++){
        const v = corner[c], sk = [];
        for(let k = 0; k < 4; k++){ const w = sw[4*v + k]; if(w) sk.push([si[4*v + k], w / 255]); }
        this.skin[c] = sk;
      }
      // cadeias para a IK: [osso de cima, do meio, da ponta]
      this.chainIdx = {};
      for(const s of ['r', 'l']){
        const S = s.toUpperCase(), g = n => id['bip01 ' + s + ' ' + n];
        if(g('upperarm') !== undefined && g('forearm') !== undefined && g('hand') !== undefined) this.chainIdx['uarm' + S] = [g('upperarm'), g('forearm'), g('hand')];
        if(g('thigh') !== undefined && g('calf') !== undefined && g('foot') !== undefined) this.chainIdx['thigh' + S] = [g('thigh'), g('calf'), g('foot')];
      }
      this.M = null; this.shift = V(0, 0, 0); this.poses = window.GAME_POSES;
    }

    // cinemática inversa de 2 ossos (ombro→cotovelo→punho, quadril→joelho→tornozelo): onde fica a articulação do meio
    _ik(S, T, a, b, pole){
      const st = T.clone().sub(S); let d = st.length(); const dir = st.clone().normalize();
      d = Math.max(Math.abs(a - b) + 1e-4, Math.min(a + b - 1e-4, d));          // alvo longe demais: estica até onde dá
      const x = (a * a - b * b + d * d) / (2 * d), h = Math.sqrt(Math.max(0, a * a - x * x));
      let perp = pole.clone().sub(S); perp.sub(dir.clone().multiplyScalar(perp.dot(dir)));
      if(perp.lengthSq() < 1e-8) perp = new THREE.Vector3(0, 0, 1); perp.normalize();
      const E = S.clone().addScaledVector(dir, x).addScaledVector(perp, h);
      return {E, W: S.clone().addScaledVector(dir, d)};
    }

    apply(pose){
      pose = pose || {};
      const D2R = Math.PI / 180, NB = this.pv.length;
      const q = new Array(NB), M = new Array(NB), t2 = new THREE.Matrix4(), rot = new THREE.Matrix4();
      const ik = pose.ik || {}, pend = {};   // pend: rotação já calculada pela IK para o osso do meio da cadeia
      // pose vinda de uma animação do jogo: uma matriz por osso (repouso -> pose, 16 números por coluna, espaço do visualizador)
      if(pose.mats){
        for(let i = 0; i < NB; i++) M[i] = pose.mats[i] ? new THREE.Matrix4().fromArray(pose.mats[i]) : new THREE.Matrix4();
      }
      for(const i of (pose.mats ? [] : this.order)){
        const parent = this.parent[i], c = this.ctl[i];
        const pv = this.pv[i], pc = parent < 0 ? pv.clone() : pv.clone().applyMatrix4(M[parent]);
        let qt = parent < 0 ? new THREE.Quaternion() : q[parent].clone();
        const chain = c && IK_TOP[c.name], goal = chain && ik[chain.key];
        if(goal && this.chainIdx[c.name]){
          // cadeia com alvo: o osso de cima gira para o plano da dobra (cotovelo/joelho como dobradiça) e o do meio só dobra
          const [iTop, iMid, iEnd] = this.chainIdx[c.name];
          const a = this.pv[iMid].distanceTo(this.pv[iTop]), b = this.pv[iEnd].distanceTo(this.pv[iMid]);
          const T = V(goal.to[0], goal.to[1], goal.to[2]), P = V(goal.pole[0], goal.pole[1], goal.pole[2]);
          const {E, W} = this._ik(pc, T, a, b, P);
          const du = E.clone().sub(pc).normalize(), f = W.clone().sub(E).normalize();
          let bend = f.clone().sub(du.clone().multiplyScalar(f.dot(du)));
          if(bend.lengthSq() < 1e-8) bend = P.clone().sub(pc).sub(du.clone().multiplyScalar(P.clone().sub(pc).dot(du)));
          bend.normalize();
          // braço: o "eixo z" de repouso é a frente (direito) ou as costas (esquerdo); perna: o "cima" de repouso é a frente do joelho
          let up;
          if(chain.kind === 'arm') up = bend.clone().multiplyScalar(chain.side).cross(du);
          else up = bend.clone().negate();
          qt = new THREE.Quaternion().setFromRotationMatrix(frame(du, up).multiply(c.restInv));
          const fRest = this.ctl[iMid].dir.clone().applyQuaternion(qt);
          pend[iMid] = new THREE.Quaternion().setFromUnitVectors(fRest, f).multiply(qt);
        } else if(pend[i]){
          qt = pend[i].clone();
        } else if(c){
          const d = pose.dirs && pose.dirs[c.name], u = pose.ups && pose.ups[c.name], l = pose.local && pose.local[c.name];
          if(d && u){
            qt = new THREE.Quaternion().setFromRotationMatrix(frame(V(d[0], d[1], d[2]), V(u[0], u[1], u[2])).multiply(c.restInv));
          } else if(d){
            qt = new THREE.Quaternion().setFromUnitVectors(c.dir, V(d[0], d[1], d[2]).normalize());
          }
          if(l) qt = qt.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(l[0]*D2R, l[1]*D2R, l[2]*D2R)));
        }
        const tw = c && pose.twist && pose.twist[c.name];   // torção em volta do próprio osso (ex.: virar a palma)
        if(tw) qt = new THREE.Quaternion().setFromAxisAngle(c.dir.clone().applyQuaternion(qt).normalize(), tw * D2R).multiply(qt);
        q[i] = qt;
        t2.makeTranslation(-pv.x, -pv.y, -pv.z); rot.makeRotationFromQuaternion(qt);
        M[i] = new THREE.Matrix4().makeTranslation(pc.x, pc.y, pc.z).multiply(rot).multiply(t2);
      }
      let G = new THREE.Matrix4();
      if(pose.root){
        const cpos = this.pv[this.id['bip01 pelvis'] || 0], r = pose.root, e = new THREE.Euler((r.rotX||0)*D2R, (r.rotY||0)*D2R, (r.rotZ||0)*D2R);
        G = new THREE.Matrix4().makeTranslation(cpos.x, cpos.y, cpos.z).multiply(new THREE.Matrix4().makeRotationFromEuler(e)).multiply(new THREE.Matrix4().makeTranslation(-cpos.x, -cpos.y, -cpos.z));
      }
      const MG = M.map(m => G.clone().multiply(m));
      const pos = this.geo.attributes.position.array, nor = this.geo.attributes.normal.array;
      const v = new THREE.Vector3(), n = new THREE.Vector3(), a = new THREE.Vector3(), nn = new THREE.Vector3(), tmp = new THREE.Vector3();
      for(let i = 0; i < this.n; i++){
        v.set(this.pos0[3*i], this.pos0[3*i+1], this.pos0[3*i+2]); n.set(this.nor0[3*i], this.nor0[3*i+1], this.nor0[3*i+2]);
        a.set(0, 0, 0); nn.set(0, 0, 0);
        for(const [bi, w] of this.skin[i]){ a.addScaledVector(tmp.copy(v).applyMatrix4(MG[bi]), w); nn.addScaledVector(tmp.copy(n).transformDirection(MG[bi]), w); }
        pos[3*i] = a.x; pos[3*i+1] = a.y; pos[3*i+2] = a.z;
        nn.normalize(); nor[3*i] = nn.x; nor[3*i+1] = nn.y; nor[3*i+2] = nn.z;
      }
      this.shift.set(0, 0, 0);
      if(pose.ground){
        let minY = 1e9, cx = 0, cz = 0;
        for(let i = 0; i < this.n; i++){ minY = Math.min(minY, pos[3*i+1]); cx += pos[3*i]; cz += pos[3*i+2]; }
        cx /= this.n; cz /= this.n; if(pose.centerX === false) cx = 0;
        for(let i = 0; i < this.n; i++){ pos[3*i] -= cx; pos[3*i+1] -= minY; pos[3*i+2] -= cz; }
        this.shift.set(-cx, -minY, -cz);
      }
      this.M = MG;
      this.geo.attributes.position.needsUpdate = true; this.geo.attributes.normal.needsUpdate = true;
      this.geo.computeBoundingSphere(); this.geo.computeBoundingBox();
    }
    // onde foi parar um ponto (coordenadas de repouso) preso a um osso do jogo, depois da pose
    point(bone, p){
      const i = this.id[bone] !== undefined ? this.id[bone] : this.id[(GAME_MAP[bone] || [[]])[0][0]];
      return V(p[0], p[1], p[2]).applyMatrix4(this.M[i]).add(this.shift);
    }
    bonePos(bone){ const i = this.id[bone]; return this.pv[i].clone(); }
    // poses tiradas das animações originais do jogo (cache/gameassets/poses.json): por osso [qx,qy,qz,qw,tx,ty,tz] =
    // rotação e translação do repouso até a pose. Substituem as poses feitas à mão de mesmo nome.
    useGamePoses(gp){
      const out = Object.assign({}, window.GAME_POSES);
      for(const [name, p] of Object.entries(gp || {})){
        if(!p || !Array.isArray(p.bones) || p.bones.length !== this.pv.length) continue;
        const mats = p.bones.map(b => new THREE.Matrix4().compose(new THREE.Vector3(b[4], b[5], b[6]),
          new THREE.Quaternion(b[0], b[1], b[2], b[3]), new THREE.Vector3(1, 1, 1)).toArray());
        out[name] = Object.assign({}, GAME_ANIM_VIEW[name] || { ground: true }, { mats, fromGame: p.anim + ' q' + p.frame });
      }
      this.poses = out;
    }
    // ponto de pegada da mão ('r'/'l'): o "túnel" entre a palma e os dedos fechados, onde passa a teia
    grip(side){
      const h = this.bonePos('bip01 ' + side + ' hand'), f = this.bonePos('bip01 ' + side + ' finger2');
      const dir = f.clone().sub(h).normalize(), back = UP.clone().sub(dir.clone().multiplyScalar(UP.dot(dir))).normalize();
      return this.point('bip01 ' + side + ' hand', h.lerp(f, 0.55).addScaledVector(back, -0.028).toArray());
    }
  }
  window.GameRig = GameRig;
  // apresentação das poses vindas das animações do jogo (o resto é a animação original, sem retoque)
  const GAME_ANIM_VIEW = {
    crossed: { ground: true },
    // smrhang: pendurado pelos pés; a teia sai do ponto entre as pontas dos dois pés
    // (a animação olha para trás; root.rotY 180 vira de frente para a câmera)
    hanging: { ground: true, centerX: false, root: { rotY: 180 }, web: { grip: ['r', 'l'] } },   // a teia desce reta até as mãos (passa entre os pés)
  };

  /* Poses para o esqueleto do jogo (articulações reais). Referência da pendurada: capturas em docs/referencia/. */
  /* Poses para o esqueleto do jogo. Os braços usam IK (pose.ik: onde fica o punho e para onde aponta o cotovelo);
     os números foram refinados olhando renderizações de vários ângulos e medindo a interpenetração da malha
     (braço x tronco/cabeça e braço x braço) até ficar só o contato natural de pele apoiada. */
  const LEGS_STAND = {   // em pé, peso na perna direita, a esquerda solta e um pouco à frente
    thighR: [0.07, -0.995, 0.02], shinR: [0.04, -0.995, -0.03], footR: [0.15, -0.33, 0.93],
    thighL: [-0.13, -0.98, 0.10], shinL: [-0.06, -0.98, -0.15], footL: [-0.30, -0.33, 0.89] };
  window.GAME_POSES = {
    tpose: {},
    // braços cruzados, relaxado: antebraços empilhados na frente do tórax (o esquerdo por cima e à frente), cotovelos
    // fora do corpo, mão direita sob o cotovelo esquerdo, mão esquerda envolvendo o bíceps direito; peito visível acima
    crossed: { ground: true,
      ik: { armR: { to: [0.005, 1.355, 0.215], pole: [0.328, 1.378, 0.151] },
            armL: { to: [0.075, 1.466, 0.289], pole: [-0.284, 1.517, 0.162] } },
      dirs: Object.assign({ clavR: [0.92, -0.30, 0.27], clavL: [-0.92, -0.30, 0.27], head: [0.04, 0.99, 0.08],
        handR: [-0.799, -0.163, -0.018], handL: [0.991, 0.145, -0.248] }, LEGS_STAND),
      ups: { head: [0.12, 0.05, 0.99], handR: [-0.316, -0.511, 0.873], handL: [0.477, 0.203, 0.925] },
      local: { fing1R: [0, 0, -35], fing2R: [0, 0, -40], fing1L: [0, 0, 50], fing2L: [0, 0, 55], thumbL: [0, 0, 25] } },
    // pendurado de cabeça para baixo segurando a teia com as duas mãos (uma acima da outra, na mesma linha vertical à
    // frente do corpo); cotovelos abertos e simétricos, punhos alinhados, pernas relaxadas com os joelhos um pouco
    // dobrados e os pés próximos. As direções são do corpo em pé; root.rotZ 180 vira tudo de cabeça para baixo
    hanging: { ground: true, centerX: false, root: { rotZ: 180 }, web: { grip: ['r', 'l'] },
      ik: { armR: { to: [0.081, 1.243, 0.215], pole: [0.397, 1.304, 0.088] },
            armL: { to: [-0.065, 1.33, 0.233], pole: [-0.382, 1.396, 0.047] } },
      dirs: { handR: [-0.754, -0.044, 0.478], handL: [0.67, 0.151, 0.241],
        thighR: [0.035, -0.97, 0.24], thighL: [-0.035, -0.97, 0.24], shinR: [0, -0.94, -0.34], shinL: [0, -0.94, -0.34],
        footR: [0.05, -0.72, 0.69], footL: [-0.05, -0.72, 0.69], spine: [0, 0.995, -0.06], head: [0, 0.97, 0.22] },
      ups: { handR: [0.323, 0.118, 0.762], handL: [-0.332, -0.033, 0.823] },
      local: { fing1R: [0, 0, -70], fing2R: [0, 0, -80], fing1L: [0, 0, 70], fing2L: [0, 0, 80], thumbR: [0, 0, -35], thumbL: [0, 0, 35] } }
  };
  const R = limb(+1);
  window.POSES = {
    tpose: {},
    // braços cruzados: antebraços empilhados na horizontal; a mão direita por baixo do braço esquerdo, a esquerda por cima do direito
    crossed: { ground: true,
      dirs: {
        uarmR: [0.22, -0.85, 0.48], farmR: [-0.88, -0.12, 0.46], handR: [-0.93, 0.02, -0.36],
        uarmL: [-0.22, -0.85, 0.48], farmL: [0.86, 0.14, 0.49], handL: [0.95, 0.05, -0.30],
        thighR: [0.15, -0.98, 0.05], thighL: [-0.15, -0.98, 0.05], shinR: [0.11, -0.99, -0.06], shinL: [-0.11, -0.99, -0.06],
        footR: [0.18, -0.30, 0.93], footL: [-0.18, -0.30, 0.93] },
      ups: { farmR: [0, 0.5, 0.85], handR: [0.3, 0.1, 0.95], farmL: [0, 0.5, 0.85], handL: [-0.3, 0.1, 0.95] },
      local: { fing1R: [0, 0, -35], fing2R: [0, 0, -35], fing1L: [0, 0, 35], fing2L: [0, 0, 35] } },
    // pose clássica pendurado na teia: de cabeça para baixo, joelhos abertos, pés juntos na linha, as duas mãos segurando a teia
    hanging: { ground: true, centerX: false, root: { rotZ: 180 }, web: { bone: 'handR', at: [R.knuckle.x, R.knuckle.y, R.knuckle.z] },
      dirs: {
        thighR: [0.80, -0.42, 0.42], thighL: [-0.80, -0.42, 0.42], shinR: [-0.80, -0.59, 0.08], shinL: [0.80, -0.59, 0.08],
        footR: [-0.20, -0.37, 0.91], footL: [0.20, -0.37, 0.91],
        uarmR: [0.15, -0.88, 0.45], farmR: [-0.56, -0.70, 0.44], handR: [-0.59, -0.74, 0.32],
        uarmL: [-0.20, -0.80, 0.56], farmL: [0.75, -0.43, 0.50], handL: [0.66, -0.72, 0.21],
        head: [0, 0.95, 0.25] },
      ups: { handR: [0.5, -0.2, 0.85], handL: [-0.5, -0.2, 0.85] },
      local: { fing1R: [0, 0, -60], fing2R: [0, 0, -60], fing1L: [0, 0, 60], fing2L: [0, 0, 60] } }
  };
})();
