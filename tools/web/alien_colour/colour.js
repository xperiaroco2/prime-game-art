// The alien pilot's static heads' colour slots in the browser (art #196, 2026-10-23): three.js 0.160, the same maths
// as godot/alien/alien_static.gd (slot_colours, guard) and alien_static.gdshader's recolour; the uniforms are
// checked against tools/blender/alien_colour_geom.py by tools/tests/test_alien_colour_slots.py (node), the GLSL's
// text against the Godot shader's (the same test); never yet run in a browser. Slots: skin, lips, detail (the crest
// stripes, the freckles and gills; detailOn), gills (the axolotl's gills: "gradient", the default, "whole" or
// "skin"; anything else throws); the pale front follows the skin as a tinted cream. Every picked colour goes through
// the guard rails (OKLCh, the hue kept: a chroma cap, lower round yellow-green and hot pink, a lightness range per
// slot, the lips at least 0.1 OKLab delta E from the skin); a slot left out keeps the build's own paint, and no
// picks is the build's look exactly. The recolour acts on the raw albedo map texel, gated by the skin mask's red
// (the painted eyes keep their paint), then the material's base colour factor multiplies it, as glTF does; Godot's
// material ignores the factor, so makeColours sets it to white (the heads' GLBs have none: 1).
//
//   import { makeColours, PRESETS } from "./colour.js";
//   const col = await makeColours(gltf.scene, "axolotl_accent.png", "axolotl_mask.png", "axolotl_gill.png", bases);
//   col.set({ skin: "#e39c8c", lips: "#a2575a", detail: "#a2575a", detailOn: true });  // returns the uniforms (sRGB)
//
// Plain functions (slotColours, guard, toOklab, fromOklab, recolour) need no three.js: `node colour.js --json` prints
// them on the test colours.

// per slot (OKLCh): [chroma cap C, L min, L max, dark knee, light knee] (null: no knee); hue bands [centre (deg),
// half width (deg), the cap's factor at the centre]
export const RAILS = { skin: [0.108, 0.44, 0.871, 0.612, null], lips: [0.113, 0.353, 0.828, null, 0.741],
  detail: [0.113, 0.31, 0.871, null, 0.741], front: [0.043, 0.845, 0.94, null, null] };  // OKLCh
export const BANDS = [[125, 36, 0.7], [341, 41, 0.8]];
export const LIP_CONTRAST = 0.1;  // OKLab delta E
export const GILL_MODES = ["skin", "gradient", "whole"];
export const FRONT_SAT_GAIN = 1.4;

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
export function toOklab(c) {
  const [r, g, b] = c.map(lin);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s];
}

function oklabRgb([L, a, b]) {  // linear sRGB, unclipped
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3;
  return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s];
}

export const fromOklab = (lab) => oklabRgb(lab).map(srgb);

// OKLab to sRGB, the chroma scaled down (bisection, the hue and L kept) until every channel is inside 0-1
function inGamut(lab) {
  const fits = (k) => oklabRgb([lab[0], lab[1] * k, lab[2] * k]).every((v) => v >= -1e-6 && v <= 1 + 1e-6);
  if (fits(1)) return fromOklab(lab);
  let lo = 0, hi = 1;
  for (let i = 0; i < 20; i++) { const k = 0.5 * (lo + hi); if (fits(k)) lo = k; else hi = k; }
  return fromOklab([lab[0], lab[1] * lo, lab[2] * lo]);
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

export function chromaCap(slot, hueDeg, L) {
  const [c0, , , dark, light] = RAILS[slot];
  let cap = c0;
  for (const [centre, half, k] of BANDS) {
    const d = Math.abs((((hueDeg - centre + 180) % 360) + 360) % 360 - 180);
    if (d < half) cap *= 1 - (1 - k) * 0.5 * (1 + Math.cos(Math.PI * d / half));
  }
  if (dark !== null) cap *= Math.min(1, (L - 0.009) / (dark - 0.009));
  if (light !== null) cap *= Math.min(1, (1 - L) / (1 - light));
  return cap;
}

export function guard(slot, c) {
  const [L, a, b] = toOklab(c), [, lo, hi] = RAILS[slot], Lc = Math.max(lo, Math.min(hi, L));
  const ch = Math.hypot(a, b), hue = ((Math.atan2(b, a) * 180 / Math.PI) % 360 + 360) % 360, cap = chromaCap(slot, hue, Lc);
  if (ch <= cap && L >= lo && L <= hi) return [...c];
  const k = ch > 0 ? Math.min(1, cap / ch) : 1;
  return inGamut([Lc, a * k, b * k]);
}

const dist = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);

export function lipContrast(lips, skin) {
  const a = toOklab(lips), s = toOklab(skin);
  if (dist(a, s) >= LIP_CONTRAST) return [...lips];
  const dl = Math.sqrt(Math.max(0, LIP_CONTRAST ** 2 - (a[1] - s[1]) ** 2 - (a[2] - s[2]) ** 2)) + 0.005;
  const [, lo, hi] = RAILS.lips;
  return inGamut([s[0] - dl >= lo ? s[0] - dl : Math.min(hi, s[0] + dl), a[1], a[2]]);
}

const pick = (v) => (typeof v === "string" ? hexc(v) : [...v]);

// The shader's uniforms (sRGB arrays) for bases {skin, lips, detail, front} and picks {skin, lips, detail, detailOn,
// gills}; alien_colour_geom.slot_colours line for line.
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
  const gills = picks.gills ?? "gradient";
  if (!GILL_MODES.includes(gills)) throw new Error(`unknown gills ${JSON.stringify(gills)} (one of ${GILL_MODES.join(", ")})`);
  u.gill_mode = GILL_MODES.indexOf(gills);
  return u;
}

// The fragment code: the same recolour as alien_static.gdshader (sRGB HSV on the map's linear texel)
export const GLSL = `
uniform sampler2D csAccent; uniform sampler2D csMask; uniform sampler2D csGill; uniform vec3 csBaseSkin; uniform vec3 csSkin; uniform vec3 csLipBase; uniform vec3 csLip;
uniform vec3 csDetailBase; uniform vec3 csDetail; uniform vec3 csFrontBase; uniform vec3 csFront;
uniform float csFrontSatMax; uniform float csDetailOn; uniform float csGillMode;
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
vec3 csRecolour(vec3 c, vec3 acc, float gill) {
  vec3 h = csHsv(csSrgb(c));
  vec3 t = csRgb(csTurn(h, csBaseSkin, csSkin));
  vec3 fh = csTurn(h, csFrontBase, csFront); fh.y = min(fh.y, max(h.y, csFrontSatMax));
  t = mix(t, csRgb(fh), acc.b);
  float dw = csGillMode < 0.5 ? max(acc.g - gill, 0.0) : (csGillMode < 1.5 ? acc.g : max(acc.g, gill));
  t = mix(t, csRgb(csTurn(h, csDetailBase, csDetail)), csDetailOn * dw);
  t = mix(t, csRgb(csTurn(h, csLipBase, csLip)), acc.r);
  return csLin(t);
}
`;

const NAMES = { base_skin: "csBaseSkin", skin_color: "csSkin", lip_base: "csLipBase", lip_color: "csLip",
  detail_base: "csDetailBase", detail_color: "csDetail", front_base: "csFrontBase", front_color: "csFront",
  front_sat_max: "csFrontSatMax", detail_on: "csDetailOn", gill_mode: "csGillMode" };

// three.js's map_fragment with the recolour on the raw map texel, gated by the skin mask as Godot's
// mix(a, recolour(a, acc, gill), m.r), before the base colour factor multiplies it
export const MAP_FRAGMENT = `
#ifdef USE_MAP
  vec4 sampledDiffuseColor = texture2D( map, vMapUv );
  vec3 csA = sampledDiffuseColor.rgb;
  sampledDiffuseColor.rgb = mix(csA, csRecolour(csA, texture2D(csAccent, vMapUv).rgb, texture2D(csGill, vMapUv).r),
    texture2D(csMask, vMapUv).r);
  diffuseColor *= sampledDiffuseColor;
#endif
`;

// Hooks the head's "_static_skin" materials: the accent mask, the skin mask and the gills (RGB PNGs, loaded without
// colour conversion: data, as Godot's Image.load_from_file path). Returns {set(picks), uniforms}; set returns the
// uniforms (sRGB).
async function dataTexture(THREE, url) {
  const blob = await (await fetch(url)).blob();
  const bmp = await createImageBitmap(blob, { premultiplyAlpha: "none", colorSpaceConversion: "none" });
  const t = new THREE.Texture(bmp);
  t.flipY = false; t.colorSpace = THREE.NoColorSpace; t.needsUpdate = true;
  return t;
}

export async function makeColours(root, accentUrl, maskUrl, gillUrl, bases) {
  const THREE = await import("three");
  const uniforms = { csAccent: { value: await dataTexture(THREE, accentUrl) }, csMask: { value: await dataTexture(THREE, maskUrl) },
    csGill: { value: await dataTexture(THREE, gillUrl) } };
  for (const n of Object.values(NAMES)) uniforms[n] = { value: ["csFrontSatMax", "csDetailOn", "csGillMode"].includes(n) ? 1 : new THREE.Color() };
  root.traverse((o) => {
    if (!o.isMesh || !o.material || !o.material.name.endsWith("_static_skin")) return;
    const mat = o.material, prev = mat.onBeforeCompile;
    if (!mat.map) throw new Error(`${mat.name}: no albedo map`);
    if (mat.color.r !== 1 || mat.color.g !== 1 || mat.color.b !== 1) {  // Godot ignores the factor: so do we
      console.warn(`${mat.name}: base colour factor ${mat.color.getHexString()} set to white, as Godot's material`);
      mat.color.setRGB(1, 1, 1);
    }
    mat.onBeforeCompile = (sh, r) => {
      if (prev) prev(sh, r);
      Object.assign(sh.uniforms, uniforms);
      if (!sh.fragmentShader.includes("#include <map_fragment>")) throw new Error("three.js: no map_fragment");
      sh.fragmentShader = GLSL + sh.fragmentShader.replace("#include <map_fragment>", MAP_FRAGMENT);
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
// node colour.js --glsl : the GLSL and the map chunk (the shader test)
if (typeof process !== "undefined" && process.argv && process.argv[2] === "--json") {
  const job = JSON.parse(process.argv[3]);
  console.log(JSON.stringify(job.picks.map((p) => {
    try { return slotColours(job.bases, p); } catch (e) { return { error: String(e.message) }; }
  })));
} else if (typeof process !== "undefined" && process.argv && process.argv[2] === "--glsl") {
  console.log(JSON.stringify({ glsl: GLSL, map: MAP_FRAGMENT }));
}
