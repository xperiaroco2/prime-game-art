// A static alien head made lively in the browser (art #196, lively): three.js 0.160, the same maths as
// godot/alien/alien_lively.gd and alien_static.gdshader's lively section (tools/blender/alien_lively_geom.py:
// eye_frame, gaze_dir, eye_offsets, clamp_gaze with cap_deg 25). Either head, from its lively.json:
// - the chameleon (controller.gaze "iris"): a procedural iris over the clean sclera on the fitted eye spheres follows
//   the target, clamped to what the lids leave open; the head follows with a lag; the crest springs after the head.
// - the axolotl (controller.gaze "none"): the all-dark bead does not visibly turn, so the head leads (faster, wider);
//   the painted catch light is painted out (its sclera PNG) and drawn fixed to the light (the mesh's own frame) while
//   the bead turns with the head; the six gills spring after the head, each at its own rate, capped at its own
//   rig.springs[].max_deg (the build's measured rig.gill_swing_deg).
// Both breathe (the chest's scale, a small nod). No face rig, no blink, no talk, no expressions.
//
//   import { makeLively } from "./lively.js";
//   const live = await makeLively(gltf.scene, "axolotl_lively.json", "axolotl_sclera.png");
//   // each frame: live.pointer(ndcX, ndcY, camera); live.update(dt);   (or live.target.copy(worldPoint))
//   live.setCatch(0.85);  // the chameleon's procedural catch light (0: none, as the merged look); the axolotl's is 1
//
// Call makeLively after the page's own material set-up (e.g. its skin tint): it chains an onBeforeCompile already set.
import * as THREE from "three";

const EYE_CAP = THREE.MathUtils.degToRad(25);
// the controller's values when lively.json leaves one out (AL6): the same table as alien_lively.gd's
// CONTROLLER_DEFAULTS (test_controller_defaults_agree); pitch_up_deg/pitch_down_deg fall back to pitch_deg,
// pitch_neck_share to neck_share; sclera_normal_map: the normal map's strength on the eye texels
export const CONTROLLER_DEFAULTS = {"gaze": "iris", "head_hz": 1.6, "yaw_deg": 35.0, "pitch_deg": 20.0, "neck_share": 0.4, "tilt": 0.0, "sclera_normal_map": 1.0};
const EYE_HZ = 9.0, BREATH_S = 4.4, BREATH_NOD = THREE.MathUtils.degToRad(0.6);
const BREATH_CHEST = new THREE.Vector3(0.006, 0.004, 0.010);

const GLSL = `
uniform float lvOn; uniform sampler2D lvSclera; uniform sampler2D lvMask;
uniform vec3 lvCentreL; uniform vec3 lvCentreR; uniform vec3 lvGazeL; uniform vec3 lvGazeR;
uniform float lvIris; uniform float lvPupil; uniform vec3 lvProfile[8]; uniform vec3 lvPupilColour;
uniform float lvCatch; uniform vec2 lvCatchOffset; uniform float lvCatchSize;
uniform float lvBead; uniform vec3 lvCatchL; uniform vec3 lvCatchR; uniform float lvCatchAngle; uniform vec3 lvCatchColour;
uniform float lvNormalMap;  // AL6: the normal map's strength on the eye texels (controller.sclera_normal_map)
uniform float lvReachL; uniform float lvReachR;  // AL3: the glint's reach from the posed bead front (lvGaze), 0 off
varying vec3 lvObj;
vec3 lvEye(vec3 sclera) {
  bool left = distance(lvObj, lvCentreL) < distance(lvObj, lvCentreR);  // the nearer eye (lvObj is posed)
  vec3 dir = normalize(lvObj - (left ? lvCentreL : lvCentreR));
  if (lvBead > 0.5) {  // the bead: its catch light fixed in the mesh's frame (to the light), the bead turning under it
    vec3 cd = left ? lvCatchL : lvCatchR, f = normalize(left ? lvGazeL : lvGazeR);
    float reach = left ? lvReachL : lvReachR, fa = acos(clamp(dot(f, cd), -1.0, 1.0));
    if (reach > 0.0 && fa > reach) cd = normalize(f * cos(reach) + normalize(cd - f * dot(cd, f)) * sin(reach));
    float a = acos(clamp(dot(dir, cd), -1.0, 1.0));
    float wa = max(fwidth(a), 1.0e-4);
    return mix(sclera, lvCatchColour, lvCatch * (1.0 - smoothstep(lvCatchAngle * 0.75 - wa, lvCatchAngle * 1.1 + wa, a)));
  }
  vec3 g = left ? lvGazeL : lvGazeR;
  float th = acos(clamp(dot(dir, g), -1.0, 1.0));
  float w = max(fwidth(th), 1.0e-4);
  float t = clamp((th - lvPupil) / (lvIris - lvPupil), 0.0, 1.0) * 7.0;
  int k = min(int(t), 6);
  vec3 iris = mix(lvProfile[k], lvProfile[k + 1], t - float(k));
  vec3 c = mix(sclera, iris, 1.0 - smoothstep(lvIris - w, lvIris + w, th));
  c = mix(c, lvPupilColour, 1.0 - smoothstep(lvPupil - w, lvPupil + w, th));
  if (lvCatch > 0.0) {
    vec3 side = normalize(vec3(g.z, 0.0, -g.x)); vec3 up = cross(g, side);
    vec3 cd = normalize(g + (side * lvCatchOffset.x + up * lvCatchOffset.y) * tan(lvIris));
    float cr = lvCatchSize * lvIris;
    c = mix(c, vec3(1.0), lvCatch * (1.0 - smoothstep(cr - w, cr + w, acos(clamp(dot(dir, cd), -1.0, 1.0)))));
  }
  return c;
}
`;

// AL3: how far from the posed bead front the glint may sit (radians): its rest angle plus CATCH_MARGIN
const CATCH_MARGIN = 0.12;
function catchReach(e) {
  return Math.acos(THREE.MathUtils.clamp(v3(e.rest).normalize().dot(v3(e.catch.dir).normalize()), -1, 1)) + CATCH_MARGIN;
}

function damp(x, v, goal, hz, dt) {  // a critically damped step, the exact solution (stable at any dt): [x, v]
  const w = 2 * Math.PI * hz, y = x - goal, k = (v + w * y) * dt, e = Math.exp(-w * dt);
  return [goal + (y + k) * e, (v - w * k) * e];
}
function eyeFrame(rest) {
  const f = rest.clone().normalize(), s = new THREE.Vector3(f.z, 0, -f.x).normalize();
  return [f, s, f.clone().cross(s).normalize()];
}
function gazeDir(rest, yaw, pitch) {
  const [f, s, u] = eyeFrame(rest);
  return f.addScaledVector(s, Math.tan(yaw)).addScaledVector(u, Math.tan(pitch)).normalize();
}
function eyeOffsets(rest, t) {  // (yaw, pitch) of t in the eye's rest frame: gazeDir's inverse
  const [f, s, u] = eyeFrame(rest), a = t.dot(f);
  return [Math.atan2(t.dot(s), a), Math.atan2(t.dot(u), a)];
}
function clampGaze(yaw, pitch, lim) {
  const ly = Math.min(THREE.MathUtils.degToRad(yaw >= 0 ? lim.pos_x : lim.neg_x), EYE_CAP);
  const lp = Math.min(THREE.MathUtils.degToRad(pitch >= 0 ? lim.up : lim.down), EYE_CAP);
  if (ly <= 0 || lp <= 0) return [ly > 0 ? THREE.MathUtils.clamp(yaw, -ly, ly) : 0, lp > 0 ? THREE.MathUtils.clamp(pitch, -lp, lp) : 0];
  const e = (yaw / ly) ** 2 + (pitch / lp) ** 2;
  return e <= 1 ? [yaw, pitch] : [yaw / Math.sqrt(e), pitch / Math.sqrt(e)];
}
const v3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);
const lin = (c) => { const k = new THREE.Color().setRGB(c[0], c[1], c[2], THREE.SRGBColorSpace); return new THREE.Vector3(k.r, k.g, k.b); };

export async function makeLively(root, jsonUrl, scleraUrl) {
  const [data, sclera] = await Promise.all([fetch(jsonUrl).then((r) => r.json()), new THREE.TextureLoader().loadAsync(scleraUrl)]);
  sclera.flipY = false;
  sclera.colorSpace = THREE.SRGBColorSpace;
  const ctl = { ...CONTROLLER_DEFAULTS, ...(data.controller || {}) };
  const YAW = THREE.MathUtils.degToRad(ctl.yaw_deg);
  // AL5: separate up and down pitch limits, the pitch's own neck share and the head's roll per radian of yaw
  const PITCH = THREE.MathUtils.degToRad(ctl.pitch_up_deg ?? ctl.pitch_deg), PITCH_DOWN = THREE.MathUtils.degToRad(ctl.pitch_down_deg ?? ctl.pitch_deg);
  const NECK_SHARE = ctl.neck_share, HEAD_HZ = ctl.head_hz, bead = ctl.gaze === "none";
  const PITCH_NECK = ctl.pitch_neck_share ?? NECK_SHARE, TILT = ctl.tilt;
  let mesh = null;
  root.traverse((o) => { if (o.isSkinnedMesh && !mesh) mesh = o; });
  if (!mesh) throw new Error("lively: no skinned mesh (load a <head>_lively.glb)");
  const bone = (n) => { const b = mesh.skeleton.getBoneByName(n); if (!b) throw new Error("lively: no bone " + n); return b; };
  const B = { chest: bone("Chest"), neck: bone("Neck"), head: bone("Head") };
  // no rig.springs: no spring (as alien_lively.gd)
  const springs = (data.rig.springs || []).map((s) => ({ ...s, b: s.bones.map(bone), y: 0, p: 0, vy: 0, vp: 0 }));
  root.updateMatrixWorld(true);
  // the head's rest relative to the mesh (moving root later keeps it valid)
  const headRestInv = mesh.matrixWorld.clone().invert().multiply(B.head.matrixWorld).invert();
  const eyes = data.eyes, L = eyes.left, R = eyes.right;
  const U = {
    lvOn: { value: 1 }, lvSclera: { value: sclera }, lvMask: { value: mesh.material.roughnessMap },
    lvCentreL: { value: v3(L.centre) }, lvCentreR: { value: v3(R.centre) }, lvGazeL: { value: v3(L.rest) }, lvGazeR: { value: v3(R.rest) },
    lvIris: { value: bead ? 0.3 : (L.iris_angle + R.iris_angle) / 2 }, lvPupil: { value: bead ? 0.2 : (L.pupil_angle + R.pupil_angle) / 2 },
    lvProfile: { value: bead ? Array(8).fill(new THREE.Vector3()) : L.iris_profile.map(lin) },
    lvPupilColour: { value: bead ? new THREE.Vector3() : lin(L.pupil_colour) },
    lvCatch: { value: bead ? 1 : 0 }, lvCatchOffset: { value: new THREE.Vector2(-0.35, 0.45) }, lvCatchSize: { value: 0.16 },
    lvBead: { value: bead ? 1 : 0 }, lvNormalMap: { value: ctl.sclera_normal_map },
    lvReachL: { value: bead && L.catch ? catchReach(L) : 0 }, lvReachR: { value: bead && R.catch ? catchReach(R) : 0 },
    lvCatchL: { value: v3(bead && L.catch ? L.catch.dir : [0, 0, 1]) }, lvCatchR: { value: v3(bead && R.catch ? R.catch.dir : [0, 0, 1]) },
    lvCatchAngle: { value: bead && L.catch ? (L.catch.angle + (R.catch ? R.catch.angle : L.catch.angle)) / 2 : 0.1 },
    lvCatchColour: { value: bead && L.catch ? lin(L.catch.colour) : new THREE.Vector3(1, 1, 1) },
  };
  const mat = mesh.material, prev = mat.onBeforeCompile;
  mat.onBeforeCompile = (sh, r) => {
    if (prev) prev(sh, r);
    Object.assign(sh.uniforms, U);
    sh.vertexShader = "varying vec3 lvObj;\n" + sh.vertexShader.replace("#include <skinning_vertex>", "#include <skinning_vertex>\n  lvObj = transformed;");
    sh.fragmentShader = GLSL + sh.fragmentShader.replace("#include <map_fragment>",
      "#include <map_fragment>\n  diffuseColor.rgb = mix(diffuseColor.rgb, lvEye(texture2D(lvSclera, vMapUv).rgb), lvOn * (1.0 - texture2D(lvMask, vMapUv).r));")
      .replace("#include <normal_fragment_maps>", "#include <normal_fragment_maps>\n  normal = normalize(mix(nonPerturbedNormal, normal, mix(1.0, lvNormalMap, lvOn * (1.0 - texture2D(lvMask, vMapUv).r))));");
  };
  mat.customProgramCacheKey = () => "lively";
  mat.needsUpdate = true;

  const mid = v3(L.centre).add(v3(R.centre)).multiplyScalar(0.5);
  const st = { hy: 0, hp: 0, vy: 0, vp: 0, time: 0, eye: { left: [0, 0, 0, 0], right: [0, 0, 0, 0] } };
  const target = mesh.localToWorld(mid.clone().add(new THREE.Vector3(0, 0, 1000)));
  const ray = new THREE.Raycaster(), plane = new THREE.Plane();
  return {
    target, uniforms: U, data,
    setCatch(v) { if (!bead) U.lvCatch.value = v; },
    setOn(v) { U.lvOn.value = v ? 1 : 0; },
    // the target under the pointer: on a plane facing the camera, 60% of the way from the head to the camera
    pointer(x, y, camera) {
      const head = mesh.localToWorld(mid.clone());
      plane.setFromNormalAndCoplanarPoint(camera.getWorldDirection(new THREE.Vector3()),
        head.clone().lerp(camera.getWorldPosition(new THREE.Vector3()), 0.6));
      ray.setFromCamera(new THREE.Vector2(x, y), camera);
      ray.ray.intersectPlane(plane, target);
    },
    update(dt) {
      dt = Math.min(dt, 0.05);
      st.time += dt;
      const t = mesh.worldToLocal(target.clone()), d = t.clone().sub(mid);
      const gy = THREE.MathUtils.clamp(Math.atan2(d.x, d.z), -YAW, YAW);
      const gp = THREE.MathUtils.clamp(Math.atan2(d.y, Math.hypot(d.x, d.z)), -PITCH_DOWN, PITCH);
      [st.hy, st.vy] = damp(st.hy, st.vy, gy, HEAD_HZ, dt);
      [st.hp, st.vp] = damp(st.hp, st.vp, gp, HEAD_HZ, dt);
      const b = 0.5 - 0.5 * Math.cos(2 * Math.PI * st.time / BREATH_S), nod = BREATH_NOD * Math.sin(2 * Math.PI * st.time / BREATH_S - 0.6);
      const chest = new THREE.Vector3(1, 1, 1).addScaledVector(BREATH_CHEST, b);
      B.chest.scale.copy(chest);
      B.neck.scale.set(1 / chest.x, 1 / chest.y, 1 / chest.z);  // the head keeps its size
      B.neck.quaternion.setFromEuler(new THREE.Euler(-st.hp * PITCH_NECK, st.hy * NECK_SHARE, 0, "YXZ"));
      B.head.quaternion.setFromEuler(new THREE.Euler(-st.hp * (1 - PITCH_NECK) - nod, st.hy * (1 - NECK_SHARE), -TILT * st.hy, "YXZ"));
      // the springs (crest or gills): under-damped, pulled back by the head's turn speed, capped at max_deg (0 or missing: held still)
      for (const s of springs) {
        const w = 2 * Math.PI * s.hz, cap = THREE.MathUtils.degToRad(s.max_deg || 0);
        s.vy += (-w * w * (s.y + st.vy * s.lag) - 2 * s.zeta * w * s.vy) * dt;
        s.vp += (-w * w * (s.p + st.vp * s.lag) - 2 * s.zeta * w * s.vp) * dt;
        s.y += s.vy * dt;
        s.p += s.vp * dt;
        // AL6: at the cap the outward velocity is dropped, the inward kept (as alien_lively.gd)
        if (Math.abs(s.y) >= cap && s.vy * s.y > 0) s.vy = 0;
        if (Math.abs(s.p) >= cap && s.vp * s.p > 0) s.vp = 0;
        s.y = THREE.MathUtils.clamp(s.y, -cap, cap);
        s.p = THREE.MathUtils.clamp(s.p, -cap, cap);
        if (!(cap > 0)) { s.vy = 0; s.vp = 0; }
        for (const c of s.b) c.quaternion.setFromEuler(new THREE.Euler(-s.p / s.b.length, s.y / s.b.length, 0, "YXZ"));
      }
      root.updateMatrixWorld(true);
      // the eyes, in the posed head's frame (mesh-local: the skin's bind space is the mesh's own)
      const posed = mesh.matrixWorld.clone().invert().multiply(B.head.matrixWorld).multiply(headRestInv);
      const basis = new THREE.Matrix3().setFromMatrix4(posed), inv = basis.clone().invert();
      for (const side of ["left", "right"]) {
        const e = eyes[side], c = v3(e.centre).applyMatrix4(posed);
        (side === "left" ? U.lvCentreL : U.lvCentreR).value.copy(c);
        if (bead) {  // the catch light stays in the mesh's frame; the bead's front bounds how far (lvReach)
          (side === "left" ? U.lvGazeL : U.lvGazeR).value.copy(v3(e.rest).applyMatrix3(basis).normalize());
          continue;
        }
        const tl = t.clone().sub(c).applyMatrix3(inv);
        const [ly, lp] = clampGaze(...eyeOffsets(v3(e.rest), tl), e.limits_deg);
        const s = st.eye[side];
        [s[0], s[2]] = damp(s[0], s[2], ly, EYE_HZ, dt);
        [s[1], s[3]] = damp(s[1], s[3], lp, EYE_HZ, dt);
        (side === "left" ? U.lvGazeL : U.lvGazeR).value.copy(gazeDir(v3(e.rest), s[0], s[1]).applyMatrix3(basis).normalize());
      }
    },
  };
}
