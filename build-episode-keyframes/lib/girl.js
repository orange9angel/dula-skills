// 小蓝 (Xiaolan) — parametric vector puppet, sunprint style.
// Design source: dula-story/episodes/cat_leads_e01_sunny_store/assets/girl_reference.png
//
// All measurements live in P (proportions) and C (palette). Views other than
// 'front' reshape features from the same constants — never hand-drawn per frame.
// v3: thin warm/cool outlines, 3-tone iris, dense plaid, layered bangs,
// fold/shade detail lines — closes the "finish" gap vs the imagegen master.
import { path, stroked, limb } from './svg.js';

export const C = {
  hairBase: '#33419B', hairShade: '#263272', hairLight: '#5468C4', hairLine: '#232B57',
  skin: '#F7D9C4', skinShade: '#EBBFA4', skinLine: '#C98A6A',
  iris: '#C97A3A', irisDark: '#8A4A20', irisLight: '#E09A55', irisRim: '#7A3E18',
  pupil: '#3A2210', eyeWhite: '#FFFFFF',
  lash: '#4A3244', mouth: '#B4564A', brow: '#4A3660', blush: '#F2A9A0',
  shirt: '#FDFBF4', shirtShade: '#C9BFE0', shirtLine: '#9B8FC4',
  skirt: '#2E3A66', skirtDark: '#26305A', skirtCrease: '#1E2748',
  plaid: '#7FD4E8', plaidLight: '#D9F2F8',
  sock: '#26262E', shoe: '#1B1B22', shoeSole: '#3A3444', shoeLine: '#121218',
};

// Proportion sheet, front view, viewBox 1000x1600. Unit: head height ~225.
export const P = {
  cx: 500,
  headTop: 44, chin: 264, faceHalf: 94,
  eyeY: 206, eyeDX: 48, eyeW: 54, eyeH: 60,
  browY: 172, noseY: 230, mouthY: 246,
  neckY0: 258, neckY1: 304, neckHalf: 26,
  shoulderY: 330, shoulderHalf: 156,
  waistY: 545, waistHalf: 92, shirtHemY: 612,
  sleeveEndY: 440, sleeveHalf: 172,
  wristY: 752, handEndY: 820,
  skirtTopY: 598, waistbandY: 638, skirtHemY: 878, skirtHemHalf: 206,
  kneeY: 1098, ankleY: 1388, sockTopY: 1240, shoeY: 1460,
  legCX: 40,
  hairBottom: 650, sidelockBottom: 585,
};

function eye(cx, cy, look = 0) {
  const { eyeW, eyeH } = P;
  const w = eyeW / 2, h = eyeH / 2;
  const ox = look * 7;
  const id = `eyeClip${cx}`;
  const outline = `M${cx - w} ${cy} Q${cx} ${cy - h - 6} ${cx + w} ${cy} Q${cx} ${cy + h - 4} ${cx - w} ${cy} Z`;
  return `
  <clipPath id="${id}"><path d="${outline}"/></clipPath>
  <g clip-path="url(#${id})">
    <path d="${outline}" fill="${C.eyeWhite}"/>
    <ellipse cx="${cx + ox}" cy="${cy + 4}" rx="23" ry="25" fill="${C.iris}"/>
    <ellipse cx="${cx + ox}" cy="${cy + 13}" rx="19" ry="14" fill="${C.irisLight}"/>
    <path d="M${cx + ox - 23} ${cy - 6} A23 24 0 0 1 ${cx + ox + 23} ${cy - 6} L${cx + ox + 23} ${cy - 22} L${cx + ox - 23} ${cy - 22} Z" fill="${C.irisDark}"/>
    <ellipse cx="${cx + ox}" cy="${cy + 4}" rx="23" ry="25" fill="none" stroke="${C.irisRim}" stroke-width="3.5"/>
    <circle cx="${cx + ox}" cy="${cy + 7}" r="10" fill="${C.pupil}"/>
    <circle cx="${cx + ox - 8}" cy="${cy - 6}" r="7" fill="${C.eyeWhite}"/>
    <circle cx="${cx + ox + 8}" cy="${cy + 14}" r="3" fill="${C.eyeWhite}" opacity="0.9"/>
  </g>
  <path d="M${cx - w - 3} ${cy - 1} Q${cx - w / 2} ${cy - h - 12} ${cx + 3} ${cy - h - 7} Q${cx + w} ${cy - h + 2} ${cx + w + 4} ${cy - 4} L${cx + w + 12} ${cy - 13} L${cx + w + 5} ${cy - 1} Q${cx + w + 2} ${cy + 2} ${cx + w - 2} ${cy + 2} Q${cx} ${cy - h} ${cx - w - 3} ${cy - 1} Z" fill="${C.lash}"/>
  <path d="M${cx - w + 6} ${cy + h - 12} Q${cx} ${cy + h - 1} ${cx + w - 8} ${cy + h - 14}" fill="none" stroke="${C.skinLine}" stroke-width="2.5" opacity="0.7" stroke-linecap="round"/>`;
}

function brow(cx, cy) {
  return `<path d="M${cx - 24} ${cy + 4} Q${cx + 2} ${cy - 7} ${cx + 24} ${cy - 1}" fill="none" stroke="${C.brow}" stroke-width="3.5" opacity="0.85" stroke-linecap="round"/>`;
}

function mouth(cx, cy, mode = 'smile') {
  if (mode === 'smile') {
    return `<path d="M${cx - 13} ${cy} Q${cx} ${cy + 8} ${cx + 13} ${cy}" fill="none" stroke="${C.mouth}" stroke-width="3.5" stroke-linecap="round"/>`;
  }
  if (mode === 'open') {
    return `<path d="M${cx - 13} ${cy - 3} Q${cx} ${cy - 8} ${cx + 13} ${cy - 3} Q${cx} ${cy + 18} ${cx - 13} ${cy - 3} Z" fill="${C.mouth}"/>
            <path d="M${cx - 8} ${cy + 7} Q${cx} ${cy + 13} ${cx + 8} ${cy + 7}" fill="none" stroke="#E88B7E" stroke-width="4.5" stroke-linecap="round"/>`;
  }
  return `<path d="M${cx - 11} ${cy + 2} L${cx + 11} ${cy + 2}" stroke="${C.mouth}" stroke-width="4" stroke-linecap="round"/>`;
}

function headAndFace(o) {
  const { cx, headTop, chin, faceHalf, eyeY, eyeDX, browY, noseY, mouthY } = P;
  const face = `M${cx - faceHalf} ${headTop + 86}
    Q${cx - faceHalf - 2} ${headTop + 8} ${cx} ${headTop}
    Q${cx + faceHalf + 2} ${headTop + 8} ${cx + faceHalf} ${headTop + 86}
    Q${cx + faceHalf} ${headTop + 152} ${cx + 54} ${chin - 24}
    Q${cx + 30} ${chin - 2} ${cx} ${chin}
    Q${cx - 30} ${chin - 2} ${cx - 54} ${chin - 24}
    Q${cx - faceHalf} ${headTop + 152} ${cx - faceHalf} ${headTop + 86} Z`;
  return `
  ${stroked(face, C.skin, C.skinLine, 2.5)}
  <path d="M${cx + faceHalf - 22} ${headTop + 130} Q${cx + faceHalf - 8} ${headTop + 170} ${cx + 58} ${chin - 28} L${cx + 48} ${chin - 36} Q${cx + faceHalf - 18} ${headTop + 160} ${cx + faceHalf - 30} ${headTop + 124} Z" fill="${C.skinShade}" opacity="0.45"/>
  ${eye(cx - eyeDX, eyeY, o.look)}${eye(cx + eyeDX, eyeY, o.look)}
  ${brow(cx - eyeDX, browY)}${brow(cx + eyeDX, browY)}
  <path d="M${cx + 2} ${noseY} q4 4 0 7" fill="none" stroke="${C.skinLine}" stroke-width="3" opacity="0.8" stroke-linecap="round"/>
  ${mouth(cx, mouthY, o.mouth)}
  <ellipse cx="${cx - 66}" cy="${eyeY + 44}" rx="14" ry="7" fill="${C.blush}" opacity="0.35"/>
  <ellipse cx="${cx + 66}" cy="${eyeY + 44}" rx="14" ry="7" fill="${C.blush}" opacity="0.35"/>`;
}

function backHair() {
  const { cx, headTop, hairBottom } = P;
  const d = `M${cx - 96} ${headTop + 76}
    Q${cx - 100} ${headTop - 12} ${cx} ${headTop - 16}
    Q${cx + 100} ${headTop - 12} ${cx + 96} ${headTop + 76}
    Q${cx + 106} ${headTop + 280} ${cx + 112} ${hairBottom - 62}
    L${cx + 104} ${hairBottom - 20} L${cx + 88} ${hairBottom - 40} L${cx + 74} ${hairBottom - 2}
    L${cx + 56} ${hairBottom - 30} L${cx + 40} ${hairBottom + 8} L${cx + 22} ${hairBottom - 24}
    L${cx} ${hairBottom + 4} L${cx - 22} ${hairBottom - 24}
    L${cx - 40} ${hairBottom + 8} L${cx - 56} ${hairBottom - 30} L${cx - 74} ${hairBottom - 2}
    L${cx - 88} ${hairBottom - 40} L${cx - 104} ${hairBottom - 20} L${cx - 112} ${hairBottom - 62}
    Q${cx - 106} ${headTop + 280} ${cx - 96} ${headTop + 76} Z`;
  const strand = (sx, bend) => `<path d="M${cx + sx} ${headTop + 240} Q${cx + sx + bend} ${headTop + 420} ${cx + sx + bend * 1.4} ${hairBottom - 40}" fill="none" stroke="${C.hairShade}" stroke-width="4" opacity="0.6" stroke-linecap="round"/>`;
  return `
  ${stroked(d, C.hairBase, C.hairLine, 3)}
  <path d="M${cx + 64} ${headTop + 60} Q${cx + 106} ${headTop + 280} ${cx + 112} ${hairBottom - 62} L${cx + 104} ${hairBottom - 20} L${cx + 88} ${hairBottom - 40} Q${cx + 84} ${headTop + 300} ${cx + 44} ${headTop + 70} Z" fill="${C.hairShade}" opacity="0.55"/>
  <path d="M${cx - 64} ${headTop + 60} Q${cx - 106} ${headTop + 280} ${cx - 112} ${hairBottom - 62} L${cx - 104} ${hairBottom - 20} L${cx - 88} ${hairBottom - 40} Q${cx - 84} ${headTop + 300} ${cx - 44} ${headTop + 70} Z" fill="${C.hairShade}" opacity="0.55"/>
  ${strand(-46, -14)}${strand(10, 8)}${strand(52, 12)}`;
}

function bangs() {
  const { cx, headTop } = P;
  // Shallow scalloped hem just above the eyes, plus two see-through gap slits.
  const hem = [
    [cx + 92, headTop + 126], [cx + 40, headTop + 120], [cx + 14, headTop + 112],
    [cx - 10, headTop + 124], [cx - 36, headTop + 112], [cx - 62, headTop + 122], [cx - 92, headTop + 130],
  ];
  let bottom = `L${hem[0][0]} ${hem[0][1]}`;
  for (let i = 1; i < hem.length; i++) {
    const [x, y] = hem[i];
    const [px, py] = hem[i - 1];
    bottom += ` Q${(px + x) / 2} ${Math.max(py, y) + 3} ${x} ${y}`;
  }
  const d = `M${cx - 94} ${headTop + 88}
    Q${cx - 98} ${headTop - 8} ${cx} ${headTop - 12}
    Q${cx + 98} ${headTop - 8} ${cx + 94} ${headTop + 88}
    L${cx + 92} ${headTop + 118}
    ${bottom} Z`;
  const slit = (x, w, top, bot) =>
    `M${x - w / 2} ${bot} Q${x - w / 2 - 3} ${(top + bot) / 2} ${x - 2} ${top} Q${x + w / 2 + 2} ${(top + bot) / 2} ${x + w / 2} ${bot} Z`;
  return `
  ${stroked(d, C.hairBase, C.hairLine, 3)}
  ${path(slit(cx - 30, 12, headTop + 60, headTop + 116), C.skin)}
  ${path(slit(cx + 26, 10, headTop + 66, headTop + 112), C.skin)}
  <path d="M${cx - 56} ${headTop + 20} Q${cx} ${headTop - 2} ${cx + 54} ${headTop + 22} Q${cx + 18} ${headTop + 38} ${cx - 18} ${headTop + 36} Q${cx - 44} ${headTop + 32} ${cx - 56} ${headTop + 20} Z" fill="${C.hairLight}" opacity="0.9"/>`;
}

function sidelocks() {
  const { cx, headTop, sidelockBottom } = P;
  const lock = (s) => `M${cx + s * 92} ${headTop + 88}
    Q${cx + s * 100} ${headTop + 240} ${cx + s * 88} ${sidelockBottom - 110}
    L${cx + s * 82} ${sidelockBottom - 60} L${cx + s * 66} ${sidelockBottom}
    L${cx + s * 62} ${sidelockBottom - 70}
    Q${cx + s * 66} ${sidelockBottom - 170} ${cx + s * 68} ${headTop + 250}
    Q${cx + s * 70} ${headTop + 240} ${cx + s * 72} ${headTop + 110} Z`;
  return `
  ${stroked(lock(-1), C.hairBase, C.hairLine, 3)}
  ${stroked(lock(1), C.hairBase, C.hairLine, 3)}
  <path d="M${cx + 88} ${headTop + 140} Q${cx + 94} ${sidelockBottom - 160} ${cx + 76} ${sidelockBottom - 30}" fill="none" stroke="${C.hairShade}" stroke-width="3.5" opacity="0.6"/>
  <path d="M${cx - 88} ${headTop + 140} Q${cx - 94} ${sidelockBottom - 160} ${cx - 76} ${sidelockBottom - 30}" fill="none" stroke="${C.hairShade}" stroke-width="3.5" opacity="0.6"/>
  <path d="M${cx + 78} ${headTop + 180} Q${cx + 82} ${sidelockBottom - 140} ${cx + 68} ${sidelockBottom - 60}" fill="none" stroke="${C.hairShade}" stroke-width="2.5" opacity="0.45"/>
  <path d="M${cx - 78} ${headTop + 180} Q${cx - 82} ${sidelockBottom - 140} ${cx - 68} ${sidelockBottom - 60}" fill="none" stroke="${C.hairShade}" stroke-width="2.5" opacity="0.45"/>`;
}

function neckAndTorso() {
  const { cx, neckY0, neckY1, neckHalf, shoulderY, shoulderHalf, waistY, waistHalf, shirtHemY } = P;
  return `
  ${path(`M${cx - neckHalf} ${neckY0} L${cx - neckHalf + 3} ${neckY1} Q${cx} ${neckY1 + 10} ${cx + neckHalf - 3} ${neckY1} L${cx + neckHalf} ${neckY0} Z`, C.skin)}
  <ellipse cx="${cx}" cy="${neckY0 + 5}" rx="${neckHalf - 10}" ry="6" fill="${C.skinShade}" opacity="0.7"/>
  ${stroked(`M${cx - shoulderHalf + 22} ${shoulderY}
    Q${cx - shoulderHalf - 6} ${shoulderY + 60} ${cx - waistHalf - 14} ${waistY}
    L${cx - waistHalf - 10} ${shirtHemY} Q${cx} ${shirtHemY + 16} ${cx + waistHalf + 10} ${shirtHemY}
    L${cx + waistHalf + 14} ${waistY}
    Q${cx + shoulderHalf + 6} ${shoulderY + 60} ${cx + shoulderHalf - 22} ${shoulderY}
    Q${cx} ${shoulderY - 26} ${cx - shoulderHalf + 22} ${shoulderY} Z`, C.skin, C.skinLine, 2.5)}`;
}

function shirt() {
  const { cx, shoulderY, shoulderHalf, waistY, waistHalf, shirtHemY, sleeveEndY, sleeveHalf, neckY1 } = P;
  const body = `M${cx - shoulderHalf + 20} ${shoulderY - 2}
    Q${cx} ${shoulderY - 28} ${cx + shoulderHalf - 20} ${shoulderY - 2}
    Q${cx + shoulderHalf + 14} ${shoulderY + 50} ${cx + waistHalf + 16} ${waistY}
    L${cx + waistHalf + 10} ${shirtHemY}
    Q${cx} ${shirtHemY + 18} ${cx - waistHalf - 10} ${shirtHemY}
    L${cx - waistHalf - 16} ${waistY}
    Q${cx - shoulderHalf - 14} ${shoulderY + 50} ${cx - shoulderHalf + 20} ${shoulderY - 2} Z`;
  const sleeve = (s) => `M${cx + s * (shoulderHalf - 34)} ${shoulderY - 6}
    L${cx + s * sleeveHalf} ${sleeveEndY - 26}
    L${cx + s * (sleeveHalf - 24)} ${sleeveEndY + 16}
    L${cx + s * (shoulderHalf - 52)} ${shoulderY + 52} Z`;
  return `
  ${stroked(body, C.shirt, C.shirtLine, 2.5)}
  ${stroked(sleeve(-1), C.shirt, C.shirtLine, 2.5)}${stroked(sleeve(1), C.shirt, C.shirtLine, 2.5)}
  <path d="M${cx + waistHalf - 28} ${waistY - 70} Q${cx + waistHalf + 26} ${waistY - 30} ${cx + waistHalf + 10} ${shirtHemY} L${cx + waistHalf - 22} ${shirtHemY + 4} Q${cx + waistHalf - 6} ${waistY - 20} ${cx + waistHalf - 40} ${waistY - 60} Z" fill="${C.shirtShade}" opacity="0.5"/>
  ${path(sleeve(1), C.shirtShade, 'opacity="0.45"')}
  <path d="M${cx - 34} ${neckY1 - 4} L${cx - 4} ${neckY1 + 32} L${cx - 24} ${neckY1 + 44} L${cx - 48} ${neckY1 + 8} Z" fill="${C.shirt}" stroke="${C.shirtLine}" stroke-width="2.5"/>
  <path d="M${cx + 34} ${neckY1 - 4} L${cx + 4} ${neckY1 + 32} L${cx + 24} ${neckY1 + 44} L${cx + 48} ${neckY1 + 8} Z" fill="${C.shirt}" stroke="${C.shirtLine}" stroke-width="2.5"/>
  <path d="M${cx} ${neckY1 + 34} L${cx} ${shirtHemY - 24}" stroke="${C.shirtLine}" stroke-width="2.5" opacity="0.7"/>
  <circle cx="${cx}" cy="${neckY1 + 84}" r="4" fill="${C.shirtLine}"/>
  <circle cx="${cx}" cy="${neckY1 + 152}" r="4" fill="${C.shirtLine}"/>
  <circle cx="${cx}" cy="${neckY1 + 220}" r="4" fill="${C.shirtLine}"/>
  <rect x="${cx + 44}" y="${neckY1 + 100}" width="42" height="38" rx="4" fill="none" stroke="${C.shirtLine}" stroke-width="3"/>
  <path d="M${cx - sleeveHalf + 6} ${sleeveEndY - 22} L${cx - sleeveHalf + 28} ${sleeveEndY + 14}" stroke="${C.shirtLine}" stroke-width="3" fill="none"/>
  <path d="M${cx + sleeveHalf - 6} ${sleeveEndY - 22} L${cx + sleeveHalf - 28} ${sleeveEndY + 14}" stroke="${C.shirtLine}" stroke-width="3" fill="none"/>
  <path d="M${cx - waistHalf - 6} ${waistY + 30} q10 14 4 30" stroke="${C.shirtLine}" stroke-width="2" fill="none" opacity="0.7"/>
  <path d="M${cx + waistHalf + 2} ${waistY + 40} q-8 12 -4 26" stroke="${C.shirtLine}" stroke-width="2" fill="none" opacity="0.7"/>
  <path d="M${cx - shoulderHalf + 44} ${shoulderY + 60} q14 8 16 24" stroke="${C.shirtLine}" stroke-width="2" fill="none" opacity="0.6"/>`;
}

function skirt() {
  const { cx, skirtTopY, waistbandY, skirtHemY, skirtHemHalf } = P;
  const waistHalf = 102;
  const silhouette = `M${cx - waistHalf} ${skirtTopY}
    L${cx + waistHalf} ${skirtTopY}
    L${cx + skirtHemHalf} ${skirtHemY}
    Q${cx} ${skirtHemY + 24} ${cx - skirtHemHalf} ${skirtHemY} Z`;
  const pleats = [];
  const n = 7;
  for (let i = 0; i < n; i++) {
    const t0 = i / n, t1 = (i + 1) / n, tm = (t0 + t1) / 2;
    const xt = (t) => cx - waistHalf + 2 * waistHalf * t;
    const xh = (t) => cx - skirtHemHalf + 2 * skirtHemHalf * t;
    pleats.push(path(`M${xt(t0)} ${waistbandY} L${xt(t1)} ${waistbandY} L${xh(t1)} ${skirtHemY} L${xh(t0)} ${skirtHemY} Z`, i % 2 === 0 ? C.skirt : C.skirtDark));
    pleats.push(`<path d="M${xt(tm)} ${waistbandY} L${xh(tm)} ${skirtHemY}" stroke="${C.skirtCrease}" stroke-width="2.5" opacity="0.55"/>`);
  }
  // dense fine plaid: verticals converge to waist, horizontals follow the flare
  const verticals = [];
  for (let i = -7; i <= 7; i++) {
    if (i === 0) continue;
    const color = i % 2 === 0 ? C.plaid : C.plaidLight;
    verticals.push(`<path d="M${cx + i * 13} ${waistbandY} L${cx + i * 27} ${skirtHemY}" stroke="${color}" stroke-width="${i % 2 === 0 ? 2.5 : 1.8}" opacity="0.7"/>`);
  }
  const plaidY = (dy, w, color, wd) => `<path d="M${cx - w} ${skirtTopY + dy} Q${cx} ${skirtTopY + dy + 8} ${cx + w} ${skirtTopY + dy}" stroke="${color}" stroke-width="${wd}" fill="none" opacity="0.7"/>`;
  return `
  <clipPath id="skirtClip">${path(silhouette, '#000')}</clipPath>
  ${stroked(silhouette, C.skirt, C.skirtCrease, 2.5)}
  <g clip-path="url(#skirtClip)">
    ${pleats.join('')}
    ${verticals.join('')}
    ${plaidY(60, 122, C.plaidLight, 1.8)}${plaidY(110, 146, C.plaid, 2.5)}
    ${plaidY(160, 168, C.plaidLight, 1.8)}${plaidY(210, 190, C.plaid, 2.5)}
    ${plaidY(248, 202, C.plaidLight, 1.8)}
  </g>
  <rect x="${cx - waistHalf}" y="${skirtTopY}" width="${waistHalf * 2}" height="${waistbandY - skirtTopY}" fill="${C.skirtDark}"/>
  <path d="M${cx - waistHalf} ${waistbandY} L${cx + waistHalf} ${waistbandY}" stroke="${C.skirtCrease}" stroke-width="3"/>`;
}

function arms() {
  const { cx, shoulderY, shoulderHalf, wristY } = P;
  const one = (s) => {
    const sx = cx + s * (shoulderHalf - 30), sy = shoulderY + 26;
    const wx = cx + s * (shoulderHalf - 44), wy = wristY;
    const inner = s > 0 ? -1 : 1;
    return `
    ${limb(sx, sy, wx, wy, 44, 30, C.skin)}
    <path d="M${sx + inner * 16} ${sy + 40} Q${wx + inner * 12} ${(sy + wy) / 2} ${wx + inner * 10} ${wy - 20}" fill="none" stroke="${C.skinShade}" stroke-width="4" opacity="0.55" stroke-linecap="round"/>
    ${stroked(`M${wx - 14} ${wy - 6}
      Q${wx - 19} ${wy + 30} ${wx - 9} ${P.handEndY - 16}
      Q${wx - 2} ${P.handEndY - 4} ${wx + 8} ${P.handEndY - 14}
      Q${wx + 17} ${wy + 28} ${wx + 12} ${wy - 4} Z`, C.skin, C.skinLine, 2)}
    <path d="M${wx - 2} ${wy + 26} l-4 24" stroke="${C.skinShade}" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    <path d="M${wx + 5} ${wy + 28} l-2 22" stroke="${C.skinShade}" stroke-width="2.5" fill="none" stroke-linecap="round"/>`;
  };
  return one(-1) + one(1);
}

function legs() {
  const { cx, skirtHemY, kneeY, ankleY, sockTopY, shoeY, legCX } = P;
  const one = (s) => {
    const hx = cx + s * legCX, hy = skirtHemY - 16;
    const ax = cx + s * (legCX + 3);
    const leg = `M${hx - 27} ${hy}
      Q${hx - 30} ${kneeY - 40} ${hx - 21} ${kneeY + 30}
      Q${hx - 18} ${sockTopY + 40} ${ax - 16} ${ankleY}
      L${ax + 16} ${ankleY}
      Q${hx + 20} ${sockTopY + 40} ${hx + 22} ${kneeY + 30}
      Q${hx + 26} ${kneeY - 40} ${hx + 25} ${hy} Z`;
    const sock = `M${hx - 19} ${sockTopY}
      Q${hx - 18} ${sockTopY + 60} ${ax - 16} ${ankleY + 4}
      L${ax + 16} ${ankleY + 4}
      Q${hx + 19} ${sockTopY + 60} ${hx + 20} ${sockTopY} Z`;
    const shoe = `M${ax - 21} ${ankleY - 2}
      Q${ax - 26} ${shoeY - 26} ${ax - 12} ${shoeY - 10}
      L${ax - 14} ${shoeY} L${ax + 34} ${shoeY}
      Q${ax + 40} ${shoeY - 24} ${ax + 22} ${ankleY + 22}
      Q${ax + 10} ${ankleY + 2} ${ax - 21} ${ankleY - 2} Z`;
    return `
    ${stroked(leg, C.skin, C.skinLine, 2.5)}
    <path d="M${hx + 16} ${hy + 30} Q${hx + 14} ${kneeY} ${ax + 10} ${ankleY - 20}" fill="none" stroke="${C.skinShade}" stroke-width="6" opacity="0.45" stroke-linecap="round"/>
    ${stroked(sock, C.sock, C.shoeLine, 2.5)}
    ${stroked(shoe, C.shoe, C.shoeLine, 2.5)}
    <path d="M${ax - 14} ${shoeY - 8} L${ax + 34} ${shoeY - 8}" stroke="${C.shoeSole}" stroke-width="5"/>
    <ellipse cx="${ax + 2}" cy="${ankleY + 12}" rx="14" ry="6" fill="${C.shoeSole}"/>`;
  };
  return one(-1) + one(1);
}

// options: { mouth: 'smile'|'line'|'open', look: -1..1 }
export function drawGirlFront(o = {}) {
  const opts = { mouth: 'smile', look: 0, ...o };
  return `<g>
    ${backHair()}
    ${arms()}
    ${neckAndTorso()}
    ${legs()}
    ${skirt()}
    ${shirt()}
    ${headAndFace(opts)}
    ${bangs()}
    ${sidelocks()}
  </g>`;
}

// ---- back view: same P, hair mass covers the whole back ----
function backHairFull() {
  const { cx, headTop, hairBottom } = P;
  const d = `M${cx - 100} ${headTop + 72}
    Q${cx - 104} ${headTop - 12} ${cx} ${headTop - 16}
    Q${cx + 104} ${headTop - 12} ${cx + 100} ${headTop + 72}
    Q${cx + 112} ${headTop + 260} ${cx + 118} ${hairBottom - 58}
    L${cx + 108} ${hairBottom - 16} L${cx + 92} ${hairBottom - 36} L${cx + 76} ${hairBottom + 2}
    L${cx + 58} ${hairBottom - 26} L${cx + 40} ${hairBottom + 10} L${cx + 20} ${hairBottom - 22}
    L${cx} ${hairBottom + 6} L${cx - 20} ${hairBottom - 22}
    L${cx - 40} ${hairBottom + 10} L${cx - 58} ${hairBottom - 26} L${cx - 76} ${hairBottom + 2}
    L${cx - 92} ${hairBottom - 36} L${cx - 108} ${hairBottom - 16} L${cx - 118} ${hairBottom - 58}
    Q${cx - 112} ${headTop + 260} ${cx - 100} ${headTop + 72} Z`;
  const strand = (sx, bend, w = 4.5) => `<path d="M${cx + sx} ${headTop + 120} Q${cx + sx + bend} ${headTop + 380} ${cx + sx + bend * 1.5} ${hairBottom - 36}" fill="none" stroke="${C.hairShade}" stroke-width="${w}" opacity="0.65" stroke-linecap="round"/>`;
  return `
  ${stroked(d, C.hairBase, C.hairLine, 3)}
  <path d="M${cx + 62} ${headTop + 40} Q${cx + 108} ${headTop + 260} ${cx + 118} ${hairBottom - 58} L${cx + 108} ${hairBottom - 16} L${cx + 92} ${hairBottom - 36} Q${cx + 88} ${headTop + 280} ${cx + 40} ${headTop + 50} Z" fill="${C.hairShade}" opacity="0.5"/>
  <path d="M${cx - 52} ${headTop + 12} Q${cx} ${headTop - 8} ${cx + 50} ${headTop + 14} Q${cx + 14} ${headTop + 34} ${cx - 20} ${headTop + 32} Q${cx - 42} ${headTop + 28} ${cx - 52} ${headTop + 12} Z" fill="${C.hairLight}" opacity="0.85"/>
  ${strand(-58, -12)}${strand(-16, 6)}${strand(22, -6)}${strand(60, 10)}`;
}

export function drawGirlBack() {
  return `<g>
    ${arms()}
    ${legs()}
    ${skirt()}
    ${backHairFull()}
  </g>`;
}

// ---- side view (profile, facing right): same P and C ----
// Anatomy rules (learned from the "not human" review):
// ear sits above shoulder center; jaw connects back to a visible neck;
// the skull is one continuous oval (hair covers it, never floats);
// torso has bust-waist S-curve; near/far legs are offset, not parallel.
export function drawGirlSide(o = {}) {
  const opts = { mouth: 'smile', ...o };
  const { headTop, chin, eyeY, browY, noseY, mouthY, shoulderY, waistY, shirtHemY,
    sleeveEndY, wristY, handEndY, skirtTopY, waistbandY, skirtHemY, kneeY, ankleY,
    sockTopY, shoeY, hairBottom } = P;

  // skin: face profile + jaw + neck + full cranium (hair drawn over it)
  const skull = `M548 100
    Q558 142 562 168
    Q566 182 570 190
    Q588 200 589 208
    Q584 218 575 221
    Q581 229 577 236
    Q571 242 575 249
    Q572 258 561 264
    Q545 271 524 267
    L506 324
    Q500 333 490 333
    L466 330
    Q460 300 456 262
    Q444 210 446 160
    Q448 90 490 52
    Q520 32 548 58
    Q556 74 548 100 Z`;
  const ear = `
    <ellipse cx="499" cy="210" rx="12" ry="15" fill="${C.skin}" stroke="${C.skinLine}" stroke-width="2"/>
    <path d="M495 202 Q503 210 496 220" fill="none" stroke="${C.skinShade}" stroke-width="2.5"/>`;

  // profile eye: almond pointing forward
  const ex = 543, ey = eyeY;
  const eyeOutline = `M${ex - 20} ${ey} Q${ex - 2} ${ey - 26} ${ex + 16} ${ey - 4} Q${ex + 14} ${ey + 18} ${ex - 8} ${ey + 20} Q${ex - 20} ${ey + 12} ${ex - 20} ${ey} Z`;
  const profileEye = `
  <clipPath id="sideEyeClip"><path d="${eyeOutline}"/></clipPath>
  <g clip-path="url(#sideEyeClip)">
    <path d="${eyeOutline}" fill="${C.eyeWhite}"/>
    <ellipse cx="${ex + 6}" cy="${ey + 2}" rx="16" ry="18" fill="${C.iris}"/>
    <ellipse cx="${ex + 6}" cy="${ey + 9}" rx="13" ry="10" fill="${C.irisLight}"/>
    <path d="M${ex - 10} ${ey - 10} A16 17 0 0 1 ${ex + 20} ${ey - 8} L${ex + 20} ${ey - 20} L${ex - 10} ${ey - 20} Z" fill="${C.irisDark}"/>
    <ellipse cx="${ex + 6}" cy="${ey + 2}" rx="16" ry="18" fill="none" stroke="${C.irisRim}" stroke-width="3"/>
    <circle cx="${ex + 8}" cy="${ey + 4}" r="7" fill="${C.pupil}"/>
    <circle cx="${ex + 1}" cy="${ey - 4}" r="4.5" fill="${C.eyeWhite}"/>
  </g>
  <path d="M${ex - 22} ${ey - 3} Q${ex - 2} ${ey - 28} ${ex + 18} ${ey - 6} L${ex + 24} ${ey - 14}" fill="none" stroke="${C.lash}" stroke-width="5" stroke-linecap="round"/>`;
  const mouthPath = opts.mouth === 'open'
    ? `<path d="M566 ${mouthY - 4} Q580 ${mouthY + 3} 566 ${mouthY + 12} Q558 ${mouthY + 4} 566 ${mouthY - 4} Z" fill="${C.mouth}"/>`
    : `<path d="M560 ${mouthY} Q569 ${mouthY + 5} 575 ${mouthY - 1}" fill="none" stroke="${C.mouth}" stroke-width="3.5" stroke-linecap="round"/>`;

  // hair: back mass behind the body; crown covers the cranium; sidelock in front of ear
  const hairBack = `M452 116
    Q428 240 424 400
    Q420 540 422 ${hairBottom - 34}
    L436 ${hairBottom - 8} L454 ${hairBottom - 34} L470 ${hairBottom + 2}
    L486 ${hairBottom - 26} L502 ${hairBottom - 4}
    Q508 480 500 340
    Q494 240 478 160
    Q468 128 452 116 Z`;
  const hairCrown = `M556 108
    Q572 66 534 42
    Q492 20 458 56
    Q432 88 436 150
    Q438 182 448 202
    Q478 190 506 174
    Q524 170 538 168
    L546 154 L554 168 L562 152
    Q568 128 556 108 Z`;
  const sidelock = `M524 118
    Q528 260 516 400
    Q510 500 498 566
    Q488 520 488 420
    Q488 280 500 150
    Q508 122 524 118 Z`;
  const strand = (sx, bend) => `<path d="M${sx} 240 Q${sx + bend} 420 ${sx + bend * 1.3} ${hairBottom - 60}" fill="none" stroke="${C.hairShade}" stroke-width="4" opacity="0.6" stroke-linecap="round"/>`;

  // torso S-curve: bust forward, waist in, back sway
  const torso = `M464 326
    Q446 380 452 450
    Q458 510 470 545
    L472 ${shirtHemY}
    L518 ${shirtHemY}
    Q526 560 530 520
    Q552 470 566 438
    Q574 398 548 356
    Q534 330 505 327
    Q485 325 464 326 Z`;
  const sleeve = `M462 330
    Q500 314 540 328
    L556 ${sleeveEndY - 12}
    Q512 ${sleeveEndY + 14} 470 ${sleeveEndY - 4}
    Q456 380 462 330 Z`;
  const arm = `
  ${limb(500, 420, 494, wristY, 40, 27, C.skin)}
  ${stroked(`M482 ${wristY - 4} Q478 ${wristY + 34} 488 ${handEndY - 14} Q496 ${handEndY - 2} 506 ${handEndY - 12} Q512 ${wristY + 30} 508 ${wristY - 4} Z`, C.skin, C.skinLine, 2)}`;

  // skirt profile: waist -> flared hem, back hem slightly longer
  const skirtD = `M462 ${skirtTopY}
    L538 ${skirtTopY}
    L596 ${skirtHemY - 8}
    Q512 ${skirtHemY + 16} 428 ${skirtHemY}
    Q438 ${skirtTopY + 140} 462 ${skirtTopY} Z`;
  const pleat = (x0, x1) => `<path d="M${x0} ${waistbandY} L${x1} ${skirtHemY}" stroke="${C.skirtCrease}" stroke-width="2.5" opacity="0.55"/>`;

  // legs: near leg knee slightly forward, far leg offset back and shaded
  const legNear = `M524 ${skirtHemY - 10}
    Q522 1010 516 ${kneeY + 10}
    Q512 1260 510 ${ankleY}
    L488 ${ankleY}
    Q480 1260 482 1180
    Q478 1090 486 1010
    Q490 930 492 ${skirtHemY - 10} Z`;
  const legFar = `M500 ${skirtHemY - 10}
    Q498 1010 494 ${kneeY}
    Q490 1200 490 ${ankleY - 40}
    L470 ${ankleY - 40}
    Q466 1100 470 1000
    Q472 920 476 ${skirtHemY - 10} Z`;
  const sock = `M511 ${sockTopY}
    Q510 1330 509 ${ankleY + 4}
    L488 ${ankleY + 4}
    Q483 1330 485 ${sockTopY} Z`;
  const shoe = `M488 ${ankleY - 2}
    Q482 ${shoeY - 30} 494 ${shoeY - 12}
    L492 ${shoeY} L560 ${shoeY}
    Q570 ${shoeY - 14} 556 ${shoeY - 32}
    Q540 ${ankleY + 22} 528 ${ankleY + 10}
    Q512 ${ankleY - 2} 488 ${ankleY - 2} Z`;

  return `<g>
    ${stroked(hairBack, C.hairBase, C.hairLine, 3)}
    <path d="M486 260 Q500 420 494 ${hairBottom - 50} Q500 ${hairBottom - 10} 502 ${hairBottom - 4} Q508 480 500 340 Q494 260 486 260 Z" fill="${C.hairShade}" opacity="0.5"/>
    ${strand(448, -16)}${strand(466, -12)}${strand(490, -8)}
    ${path(legFar, C.skinShade)}
    ${stroked(skull, C.skin, C.skinLine, 2.5)}
    ${ear}
    ${stroked(legNear, C.skin, C.skinLine, 2.5)}
    ${stroked(sock, C.sock, C.shoeLine, 2.5)}
    ${stroked(shoe, C.shoe, C.shoeLine, 2.5)}
    <path d="M492 ${shoeY - 8} L560 ${shoeY - 8}" stroke="${C.shoeSole}" stroke-width="5"/>
    <clipPath id="sideSkirtClip">${path(skirtD, '#000')}</clipPath>
    ${stroked(skirtD, C.skirt, C.skirtCrease, 2.5)}
    <g clip-path="url(#sideSkirtClip)">
      ${pleat(478, 452)}${pleat(500, 492)}${pleat(520, 540)}
      <path d="M440 ${skirtTopY + 70} Q512 ${skirtTopY + 82} 590 ${skirtTopY + 66}" stroke="${C.plaidLight}" stroke-width="1.8" fill="none" opacity="0.7"/>
      <path d="M436 ${skirtTopY + 120} Q512 ${skirtTopY + 134} 596 ${skirtTopY + 116}" stroke="${C.plaid}" stroke-width="2.5" fill="none" opacity="0.7"/>
      <path d="M432 ${skirtTopY + 170} Q512 ${skirtTopY + 184} 600 ${skirtTopY + 166}" stroke="${C.plaidLight}" stroke-width="1.8" fill="none" opacity="0.7"/>
      <path d="M430 ${skirtTopY + 214} Q512 ${skirtTopY + 228} 600 ${skirtTopY + 210}" stroke="${C.plaid}" stroke-width="2.5" fill="none" opacity="0.7"/>
    </g>
    <rect x="462" y="${skirtTopY}" width="76" height="${waistbandY - skirtTopY}" fill="${C.skirtDark}"/>
    ${stroked(torso, C.shirt, C.shirtLine, 2.5)}
    ${stroked(sleeve, C.shirt, C.shirtLine, 2.5)}
    <path d="M536 400 Q552 460 528 540 Q522 580 518 ${shirtHemY} L500 ${shirtHemY} Q514 560 518 510 Q536 460 528 406 Z" fill="${C.shirtShade}" opacity="0.5"/>
    <path d="M500 318 L532 338 L550 322 L522 304 Z" fill="${C.shirt}" stroke="${C.shirtLine}" stroke-width="2.5"/>
    ${arm}
    ${profileEye}
    <path d="M${ex - 20} ${browY + 4} Q${ex + 4} ${browY - 6} ${ex + 18} ${browY}" fill="none" stroke="${C.brow}" stroke-width="3.5" opacity="0.85" stroke-linecap="round"/>
    ${mouthPath}
    <ellipse cx="545" cy="${eyeY + 40}" rx="11" ry="6" fill="${C.blush}" opacity="0.35"/>
    ${stroked(hairCrown, C.hairBase, C.hairLine, 3)}
    <path d="M470 50 Q510 30 540 52 Q514 44 492 52 Q478 56 470 50 Z" fill="${C.hairLight}" opacity="0.85"/>
    ${stroked(sidelock, C.hairBase, C.hairLine, 2.5)}
  </g>`;
}
