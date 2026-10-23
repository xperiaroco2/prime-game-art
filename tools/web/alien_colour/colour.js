// The alien pilot's static heads' colour slots in the browser (art #196, 2026-10-23): three.js 0.160, the same maths
// as godot/alien/alien_static.gd (slot_colours) and alien_static.gdshader's recolour; the uniforms are checked
// against tools/blender/alien_colour_geom.py by tools/tests/test_alien_colour_slots.py (node), the GLSL's text
// against the Godot shader's (the same test); never yet run in a browser. Slots: skin, lips, detail (the crest
// stripes, the freckles and gills; detailOn), gills (the axolotl's gills: "gradient", the default, "whole" or
// "skin"; anything else throws), front (the pale front, no slot: "keep", the default, its two-tone against the skin,
// or "follow" the skin; a tinted cream either way). Every pick is applied as picked (CS6: no guard rails): the
// region's base texel becomes the pick and its median is within the albedo table's dE of it, the paint's lighter and
// darker texels stay so round it (the offset from the region's base carried onto the pick in OKLab, `shift`;
// CS6b: relative on a darker pick); a slot left out
// keeps the build's own paint, and no picks is the build's look exactly. The recolour acts on the raw albedo map
// texel, gated by the skin mask's red (the painted eyes keep their paint), then the material's base colour factor
// multiplies it, as glTF does; Godot's material ignores the factor, so makeColours sets it to white (the heads'
// GLBs have none: 1).
//
//   import { makeColours, PRESETS } from "./colour.js";
//   const col = await makeColours(gltf.scene, "axolotl_accent.png", "axolotl_mask.png", "axolotl_gill.png", bases);
//   col.set({ skin: "#e39c8c", lips: "#a2575a", detail: "#a2575a", detailOn: true });  // returns the uniforms (sRGB)
//
// Plain functions (slotColours, shift, toOklab, fromOklab, recolour) need no three.js: `node colour.js --json`
// prints them on the test colours.

export const GILL_MODES = ["skin", "gradient", "whole"];
export const FRONT_MODES = ["keep", "follow"];
export const FRONT_BAND = 0.08; // CS6c: the "keep" front's blend from above the skin to below it, in skin L round 1 - d/2

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

// One texel x (OKLab) from its region's base b to the target t: its offset from b carried onto t (alien_colour_geom.shift)
export function shift(x, b, t) {
  const dl = x[0] - b[0], kr = Math.min(1, t[0] / Math.max(b[0], 1e-4));
  const kl = dl > 0 ? Math.min(kr, (1 - t[0]) / Math.max(1 - b[0], 1e-4)) : kr;
  const cb = Math.hypot(b[1], b[2]), ct = Math.hypot(t[1], t[2]);
  let co = 1, si = 0;
  if (cb > 1e-4 && ct > 1e-4) { co = (b[1] * t[1] + b[2] * t[2]) / (cb * ct); si = (b[1] * t[2] - b[2] * t[1]) / (cb * ct); }
  const kc = Math.min(1, ct / Math.max(cb, 1e-4)) * kr, da = x[1] - b[1], db = x[2] - b[2];
  return [t[0] + dl * kl, t[1] + (da * co - db * si) * kc, t[2] + (da * si + db * co) * kc];
}

// shift on one sRGB colour (sRGB in and out, clamped)
export const recolour = (c, base, target) => fromOklab(shift(toOklab(c), toOklab(base), toOklab(target)));

// the pale front for a picked skin: the build's front shifted with the skin, its chroma never above the build's front's;
// "keep": its lightness at least the build's front's, then the build's two-tone away from the skin (above, up to
// white, while half of it fits there, else below), the two blended over FRONT_BAND in the skin's L round 1 - d/2
// (CS6c: continuous)
export function frontFor(skin, baseSkin, frontBase, mode = "keep") {
  let [L, a, b] = shift(toOklab(frontBase), toOklab(baseSkin), toOklab(skin));
  const fb = toOklab(frontBase), ls = toOklab(skin)[0];
  const cf = Math.hypot(fb[1], fb[2]), c = Math.hypot(a, b), k = c > 0 ? Math.min(1, cf / c) : 1;
  if (mode === "keep") {
    const d = fb[0] - toOklab(baseSkin)[0];
    L = Math.max(L, fb[0]);
    if (Math.abs(L - ls) < d - 1e-6) {
      // CS6c: above the skin, then below it, blended over FRONT_BAND round 1 - d/2 (a step there before)
      let s = Math.min(1, Math.max(0, (ls - (1 - 0.5 * d)) / FRONT_BAND + 0.5));
      s = s * s * (3 - 2 * s);
      L = Math.min(1, ls + d) * (1 - s) + (ls - d) * s;
    }
  }
  return fromOklab([L, a * k, b * k]);
}

const pick = (v) => (typeof v === "string" ? hexc(v) : [...v]);

// The shader's uniforms (sRGB arrays) for bases {skin, lips, detail, front, gill_tips, gill_whole} and picks {skin,
// lips, detail, detailOn, gills, front}, applied as picked; alien_colour_geom.slot_colours line for line.
export function slotColours(bases, picks = {}) {
  const gills = picks.gills ?? "gradient", front = picks.front ?? "keep";
  if (!GILL_MODES.includes(gills)) throw new Error(`unknown gills ${JSON.stringify(gills)} (one of ${GILL_MODES.join(", ")})`);
  if (!FRONT_MODES.includes(front)) throw new Error(`unknown front ${JSON.stringify(front)} (one of ${FRONT_MODES.join(", ")})`);
  const base = [...bases.skin];
  const gb = [...(bases[gills === "whole" ? "gill_whole" : "gill_tips"] ?? bases.detail)];
  const u = { base_skin: base, lip_base: [...bases.lips], detail_base: [...bases.detail], gill_base: gb,
    front_base: [...bases.front] };
  const picked = "skin" in picks, skin = picked ? pick(picks.skin) : base;
  u.skin_color = skin;
  u.front_color = picked ? frontFor(skin, base, u.front_base, front) : u.front_base;
  // a slot left out: the build's paint there, following a picked skin as its paint does
  const follow = (b) => (picked ? recolour(b, base, skin) : b);
  u.lip_color = "lips" in picks ? pick(picks.lips) : follow(u.lip_base);
  u.detail_color = "detail" in picks ? pick(picks.detail) : follow(u.detail_base);
  u.gill_color = "detail" in picks ? pick(picks.detail) : follow(gb);
  u.detail_on = ("detailOn" in picks ? !!picks.detailOn : "detail" in picks) ? 1 : 0;
  u.gill_mode = GILL_MODES.indexOf(gills);
  return u;
}

// The fragment code: the same recolour as alien_static.gdshader (OKLab, on the map's linear texel; the uniforms
// are sRGB here, turned linear as Godot's source_color does)
export const GLSL = `
uniform sampler2D csAccent; uniform sampler2D csMask; uniform sampler2D csGill; uniform vec3 csBaseSkin; uniform vec3 csSkin; uniform vec3 csLipBase; uniform vec3 csLip;
uniform vec3 csDetailBase; uniform vec3 csDetail; uniform vec3 csGillBase; uniform vec3 csGillColor; uniform vec3 csFrontBase; uniform vec3 csFront;
uniform float csDetailOn; uniform float csGillMode;
vec3 csLin(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c)); }
vec3 csLab(vec3 c) {
  vec3 lms = vec3(dot(c, vec3(0.4122214708, 0.5363325363, 0.0514459929)), dot(c, vec3(0.2119034982, 0.6806995451, 0.1073969566)),
    dot(c, vec3(0.0883024619, 0.2817188376, 0.6299787005)));
  lms = sign(lms) * pow(abs(lms), vec3(1.0 / 3.0));
  return vec3(dot(lms, vec3(0.2104542553, 0.7936177850, -0.0040720468)), dot(lms, vec3(1.9779984951, -2.4285922050, 0.4505937099)),
    dot(lms, vec3(0.0259040371, 0.7827717662, -0.8086757660)));
}
vec3 csLabLin(vec3 lab) {
  vec3 lms = vec3(dot(lab, vec3(1.0, 0.3963377774, 0.2158037573)), dot(lab, vec3(1.0, -0.1055613458, -0.0638541728)),
    dot(lab, vec3(1.0, -0.0894841775, -1.2914855480)));
  lms = lms * lms * lms;
  return vec3(dot(lms, vec3(4.0767416621, -3.3077115913, 0.2309699292)), dot(lms, vec3(-1.2684380046, 2.6097574011, -0.3413193965)),
    dot(lms, vec3(-0.0041960863, -0.7034186147, 1.7076147010)));
}
vec3 csShift(vec3 x, vec3 b, vec3 t) {
  float dl = x.x - b.x;
  float kr = min(1.0, t.x / max(b.x, 1.0e-4));
  float kl = dl > 0.0 ? min(kr, (1.0 - t.x) / max(1.0 - b.x, 1.0e-4)) : kr;
  float cb = length(b.yz);
  float ct = length(t.yz);
  vec2 r = vec2(1.0, 0.0);
  if (cb > 1.0e-4 && ct > 1.0e-4) { r = vec2(dot(b.yz, t.yz), b.y * t.z - b.z * t.y) / (cb * ct); }
  float kc = min(1.0, ct / max(cb, 1.0e-4)) * kr;
  vec2 d = x.yz - b.yz;
  return vec3(t.x + dl * kl, t.yz + vec2(d.x * r.x - d.y * r.y, d.x * r.y + d.y * r.x) * kc);
}
vec3 csU(vec3 c) { return csLab(csLin(c)); }  // an sRGB uniform in OKLab
vec3 csRecolour(vec3 c, vec3 acc, float gill) {
  vec3 x = csLab(c);
  vec3 t = csShift(x, csU(csBaseSkin), csU(csSkin));
  t = mix(t, csShift(x, csU(csFrontBase), csU(csFront)), acc.b);
  float dw = csGillMode < 0.5 ? max(acc.g - gill, 0.0) : (csGillMode < 1.5 ? acc.g : max(acc.g, gill));
  vec3 db = csLab(mix(csLin(csDetailBase), csLin(csGillBase), gill));
  vec3 dt = csLab(mix(csLin(csDetail), csLin(csGillColor), gill));
  t = mix(t, csShift(x, db, dt), csDetailOn * dw);
  t = mix(t, csShift(x, csU(csLipBase), csU(csLip)), acc.r);
  return clamp(csLabLin(t), 0.0, 1.0);
}
`;

const NAMES = { base_skin: "csBaseSkin", skin_color: "csSkin", lip_base: "csLipBase", lip_color: "csLip",
  detail_base: "csDetailBase", detail_color: "csDetail", gill_base: "csGillBase", gill_color: "csGillColor",
  front_base: "csFrontBase", front_color: "csFront", detail_on: "csDetailOn", gill_mode: "csGillMode" };

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

// No gillUrl: a black gill texture and a warning, as alien_static.gd's apply() ("skin" and "whole" act as "gradient").
export async function makeColours(root, accentUrl, maskUrl, gillUrl, bases) {
  const THREE = await import("three");
  let gillTex;
  if (gillUrl) gillTex = await dataTexture(THREE, gillUrl);
  else {
    console.warn("colour.js: an accent mask without the gill texture: the gills modes 'skin' and 'whole' act as 'gradient' (pass <head>_gill.png)");
    gillTex = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1);
    gillTex.needsUpdate = true;
  }
  const uniforms = { csAccent: { value: await dataTexture(THREE, accentUrl) }, csMask: { value: await dataTexture(THREE, maskUrl) },
    csGill: { value: gillTex } };
  for (const n of Object.values(NAMES)) uniforms[n] = { value: ["csDetailOn", "csGillMode"].includes(n) ? 1 : new THREE.Color() };
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
