// Tiny SVG helpers shared by character/scene components.

export function path(d, fill, extra = '') {
  return `<path d="${d}" fill="${fill}" ${extra}/>`;
}

export function stroked(d, fill, stroke, w, extra = '') {
  return `<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round" ${extra}/>`;
}

// Smooth closed blob through points [[x,y],...] using Catmull-Rom -> bezier.
export function blob(pts, fill, extra = '') {
  const p = pts;
  let d = `M${p[0][0]} ${p[0][1]}`;
  for (let i = 0; i < p.length; i++) {
    const p0 = p[(i - 1 + p.length) % p.length];
    const p1 = p[i];
    const p2 = p[(i + 1) % p.length];
    const p3 = p[(i + 2) % p.length];
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += `C${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${p2[0]} ${p2[1]}`;
  }
  return path(d + 'Z', fill, extra);
}

// Tapered limb segment between two joints with rounded ends.
export function limb(x1, y1, x2, y2, w1, w2, fill, extra = '') {
  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const nx = (-dy / len), ny = (dx / len);
  const d = `M${x1 + nx * w1 / 2} ${y1 + ny * w1 / 2}
    L${x2 + nx * w2 / 2} ${y2 + ny * w2 / 2}
    A${w2 / 2} ${w2 / 2} 0 0 1 ${x2 - nx * w2 / 2} ${y2 - ny * w2 / 2}
    L${x1 - nx * w1 / 2} ${y1 - ny * w1 / 2}
    A${w1 / 2} ${w1 / 2} 0 0 1 ${x1 + nx * w1 / 2} ${y1 + ny * w1 / 2} Z`;
  return path(d, fill, extra);
}

export function doc(width, height, inner) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${inner}</svg>`;
}
