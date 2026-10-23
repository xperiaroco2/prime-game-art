// The alien pilot's static heads' colour slots in the browser (art #196, 2026-10-23): three.js 0.160, the same maths
// as godot/alien/alien_static.gd (slot_colours, guard) and alien_static.gdshader's recolour, checked against
// tools/blender/alien_colour_geom.py by tools/tests/test_alien_colour_slots.py. Slots: skin, lips, detail (the crest
// stripes, the freckles and gills; detailOn), gillsDetail (the axolotl's gills on the details or the skin); the pale
// front follows the skin as a tinted cream. Every picked colour goes through the guard rails (CIELAB: a chroma cap,
// lower round yellow-green, a lightness range per slot, the lips at least 12 delta E from the skin); a slot left out
// keeps the build's own paint, and no picks is the build's look exactly.
//
//   import { makeColours, PRESETS } from "./colour.js";
//   const col = await makeColours(gltf.scene, "axolotl_accent.png", "axolotl_mask.png", bases);  // bases: heads.json's entry
//   col.set({ skin: "#e39c8c", lips: "#a2575a", detail: "#a2575a", detailOn: true });  // returns the uniforms (sRGB)
//
// Plain functions (slotColours, guard, toLab, fromLab, recolour) need no three.js: `node colour.js --json` prints
// them on the test colours.

export const RAILS = { skin: [40, 35, 85], lips: [42, 25, 80], detail: [42, 20, 85], front: [16, 82, 93] };
export const ACID = [125, 35, 0.7];
export const LIP_CONTRAST = 12;
export const FRONT_SAT_GAIN = 1.4;
const WHITE = [0.95047, 1.0, 1.08883];

export const PRESETS = [
  ["alien teal", {}],
  ["coral reef", { skin: "#e39c8c", lips: "#a2575a", detail: "#a2575a", detailOn: true }],
  ["lilac", { skin: "#a99cd8", lips: "#6c5896", detail: "#6c5896", detailOn: true }],
  ["honey", { skin: "#e2c07a", lips: "#a96e51", detail: "#a96e51", detailOn: true }],
  ["cobalt", { skin: "#6c87c6", lips: "#d48c72", detail: "#d48c72", detailOn: true }],
  ["sage", { skin: "#8fb99f", lips: "#4e7a65", detail: "#4e7a65", detailOn: true }],
  ["plum", { skin: "#a07596", lips: "#5c3a5a", detail: "#5c3a5a", detailOn: true }],
  ["slate", { skin: "#7f98a8", lips: "#c98a7e", detail: "#c98a7e", detailOn: true }],
];

export const hexc = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
export const hexs = (c) => "#" + c.map((x) => Math.round(Math.min(1, Math.max(0, x)) * 255).toString(16).padStart(2, "0")).join("");
const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const srgb = (c) => { c = Math.min(1, Math.max(0, c)); return c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055; };
const f = (t) => (t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116);
const finv = (t) => (t ** 3 > 216 / 24389 ? t ** 3 : (116 * t - 16) / (24389 / 27));

export function toLab(c) {
  const [r, g, b] = c.map(lin);
  const x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / WHITE[0];
  const y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / WHITE[1];
  const z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / WHITE[2];
  return [116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))];
}

export function fromLab([L, a, b]) {
  const fy = (L + 16) / 116;
  const x = finv(fy + a / 500) * WHITE[0], y = finv(fy) * WHITE[1], z = finv(fy - b / 200) * WHITE[2];
  return [3.2404542 * x - 1.5371385 * y - 0.4985314 * z, -0.9692660 * x + 1.8760108 * y + 0.0415560 * z,
    0.0556434 * x - 0.2040259 * y + 1.0572252 * z].map(srgb);
}

export function rgbToHsv([r, g, b]) {  // Python's colorsys
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), v = mx;
  if (mn === mx) return [0, 0, v];
  const s = (mx - mn) / mx, rc = (mx - r) / (mx - mn), gc = (mx - g) / (mx - mn), bc = (mx - b) / (mx - mn);
  let h = r === mx ? bc - gc : g === mx ? 2 + rc - bc : 4 + gc - rc;
  h = (((h / 6) % 1) + 1) % 1;
  return [h, s, v];
}

export function hsvToRgb([h, s, v]) {
  if (s === 0) return [v, v, v];
  const i = Math.floor(h * 6) % 6, fr = h * 6 - Math.floor(h * 6), p = v * (1 - s), q = v * (1 - s * fr), t = v * (1 - s * (1 - fr));
  return [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][i];
}

export function recolour(c, base, target) {
  const [h, s, v] = rgbToHsv(c), [bh, bs, bv] = rgbToHsv(base), [th, ts, tv] = rgbToHsv(target);
  return hsvToRgb([(((h + th - bh) % 1) + 1) % 1, Math.min(1, s * ts / Math.max(bs, 1e-4)), Math.min(1, v * tv / Math.max(bv, 1e-4))]);
}

export function chromaCap(slot, hueDeg) {
  let cap = RAILS[slot][0];
  const d = Math.abs((((hueDeg - ACID[0] + 180) % 360) + 360) % 360 - 180);
  if (d < ACID[1]) cap *= 1 - (1 - ACID[2]) * 0.5 * (1 + Math.cos(Math.PI * d / ACID[1]));
  return cap;
}

export function guard(slot, c) {
  const [L, a, b] = toLab(c), [, lo, hi] = RAILS[slot];
  const ch = Math.hypot(a, b), hue = ((Math.atan2(b, a) * 180 / Math.PI) % 360 + 360) % 360, cap = chromaCap(slot, hue);
  if (ch <= cap && L >= lo && L <= hi) return [...c];
  const k = ch > 0 ? Math.min(1, cap / ch) : 1;
  return fromLab([Math.max(lo, Math.min(hi, L)), a * k, b * k]);
}

const dist = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);

export function lipContrast(lips, skin) {
  const a = toLab(lips), s = toLab(skin);
  if (dist(a, s) >= LIP_CONTRAST) return [...lips];
  const dl = Math.sqrt(Math.max(0, LIP_CONTRAST ** 2 - (a[1] - s[1]) ** 2 - (a[2] - s[2]) ** 2)) + 0.5;
  const [, lo, hi] = RAILS.lips;
  return fromLab([s[0] - dl >= lo ? s[0] - dl : Math.min(hi, s[0] + dl), a[1], a[2]]);
}

const pick = (v) => (typeof v === "string" ? hexc(v) : [...v]);

// The shader's uniforms (sRGB arrays) for bases {skin, lips, detail, front} and picks {skin, lips, detail, detailOn,
// gillsDetail}; alien_colour_geom.slot_colours line for line.
export function slotColours(bases, picks = {}) {
  const base = [...bases.skin];
  const u = { base_skin: base, lip_base: [...bases.lips], detail_base: [...bases.detail], front_base: [...bases.front] };
  const skin = "skin" in picks ? guard("skin", pick(picks.skin)) : base;
  u.skin_color = skin;
  if ("skin" in picks) {
    u.front_color = guard("front", recolour(u.front_base, base, skin));
    u.front_sat_max = Math.min(1, FRONT_SAT_GAIN * rgbToHsv(u.front_color)[1]);
  } else {
    u.front_color = u.front_base;
    u.front_sat_max = 1;
  }
  u.lip_color = "lips" in picks ? lipContrast(guard("lips", pick(picks.lips)), skin) : recolour(u.lip_base, base, skin);
  const on = "detailOn" in picks ? !!picks.detailOn : "detail" in picks;
  u.detail_color = "detail" in picks ? guard("detail", pick(picks.detail)) : recolour(u.detail_base, base, skin);
  u.detail_on = on ? 1 : 0;
  u.gills_detail = picks.gillsDetail === false ? 0 : 1;
  return u;
}

// The fragment code: the same recolour as alien_static.gdshader (sRGB HSV on the map's linear texel)
const GLSL = `
uniform sampler2D csAccent; uniform sampler2D csMask; uniform vec3 csBaseSkin; uniform vec3 csSkin; uniform vec3 csLipBase; uniform vec3 csLip;
uniform vec3 csDetailBase; uniform vec3 csDetail; uniform vec3 csFrontBase; uniform vec3 csFront;
uniform float csFrontSatMax; uniform float csDetailOn; uniform float csGillsDetail;
vec3 csHsv(vec3 c) {
  vec4 k = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
  vec4 p = mix(vec4(c.bg, k.wz), vec4(c.gb, k.xy), step(c.b, c.g));
  vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
  float d = q.x - min(q.w, q.y);
  return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1.0e-10)), d / (q.x + 1.0e-10), q.x);
}
vec3 csRgb(vec3 c) { vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0); return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y); }
vec3 csSrgb(vec3 c) { c = clamp(c, 0.0, 1.0); return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c)); }
vec3 csLin(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c)); }
vec3 csTurn(vec3 h, vec3 b, vec3 t) {  // b, t: sRGB uniforms
  b = csHsv(b); t = csHsv(t);
  return vec3(fract(h.x + t.x - b.x), clamp(h.y * t.y / max(b.y, 1.0e-4), 0.0, 1.0), clamp(h.z * t.z / max(b.z, 1.0e-4), 0.0, 1.0));
}
vec3 csRecolour(vec3 c, vec4 acc) {
  vec3 h = csHsv(csSrgb(c));
  vec3 t = csRgb(csTurn(h, csBaseSkin, csSkin));
  vec3 fh = csTurn(h, csFrontBase, csFront); fh.y = min(fh.y, max(h.y, csFrontSatMax));
  t = mix(t, csRgb(fh), acc.b);
  float gill = min(1.0 - acc.a, acc.g);
  t = mix(t, csRgb(csTurn(h, csDetailBase, csDetail)), csDetailOn * max(acc.g - gill * (1.0 - csGillsDetail), 0.0));
  t = mix(t, csRgb(csTurn(h, csLipBase, csLip)), acc.r);
  return csLin(t);
}
`;

const NAMES = { base_skin: "csBaseSkin", skin_color: "csSkin", lip_base: "csLipBase", lip_color: "csLip",
  detail_base: "csDetailBase", detail_color: "csDetail", front_base: "csFrontBase", front_color: "csFront",
  front_sat_max: "csFrontSatMax", detail_on: "csDetailOn", gills_detail: "csGillsDetail" };

// Hooks the head's "_static_skin" materials: the accent mask and the skin mask (RGBA and RGB PNGs, loaded
// unpremultiplied and without colour conversion: the gills live in the accent's alpha, the skin mask in the mask's
// red). Returns {set(picks), uniforms}; set returns the uniforms (sRGB).
async function dataTexture(THREE, url) {
  const blob = await (await fetch(url)).blob();
  const bmp = await createImageBitmap(blob, { premultiplyAlpha: "none", colorSpaceConversion: "none" });
  const t = new THREE.Texture(bmp);
  t.flipY = false; t.colorSpace = THREE.NoColorSpace; t.needsUpdate = true;
  return t;
}

export async function makeColours(root, accentUrl, maskUrl, bases) {
  const THREE = await import("three");
  const uniforms = { csAccent: { value: await dataTexture(THREE, accentUrl) }, csMask: { value: await dataTexture(THREE, maskUrl) } };
  for (const n of Object.values(NAMES)) uniforms[n] = { value: ["csFrontSatMax", "csDetailOn", "csGillsDetail"].includes(n) ? 1 : new THREE.Color() };
  root.traverse((o) => {
    if (!o.isMesh || !o.material || !o.material.name.endsWith("_static_skin")) return;
    const mat = o.material, prev = mat.onBeforeCompile;
    mat.onBeforeCompile = (sh, r) => {
      if (prev) prev(sh, r);
      Object.assign(sh.uniforms, uniforms);
      sh.fragmentShader = GLSL + sh.fragmentShader.replace("#include <map_fragment>",
        "#include <map_fragment>\n  diffuseColor.rgb = csRecolour(diffuseColor.rgb, texture2D(csAccent, vMapUv));");
    };
    mat.needsUpdate = true;
  });
  function set(picks = {}) {
    const u = slotColours(bases, picks);
    for (const [k, n] of Object.entries(NAMES)) {
      const v = u[k];
      if (Array.isArray(v)) uniforms[n].value.setRGB(v[0], v[1], v[2], THREE.NoColorSpace);  // sRGB numbers, as the GLSL wants
      else uniforms[n].value = v;
    }
    return u;
  }
  set({});
  return { set, uniforms };
}

// node colour.js --json '<{"bases": {...}, "picks": [...]}>' : slotColours per picks (the parity test)
if (typeof process !== "undefined" && process.argv && process.argv[2] === "--json") {
  const job = JSON.parse(process.argv[3]);
  console.log(JSON.stringify(job.picks.map((p) => slotColours(job.bases, p))));
}
