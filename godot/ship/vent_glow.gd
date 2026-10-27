extends RefCounted
## The throat vents' well lights (art #263 station 1, vents-b2; docs/ship.md "Station 1"): the concept's charm is the
## light pouring out between the blades, so each vent's two glow panels get OmniLights of their own, children of the
## panel, a few cm in front of it between the panel and the blades' backs: `<id>_cool` cyan (calm), `<id>_heat` orange
## (the problem). The state that hides a panel puts its lights out too (calm hides `heat`, the problem hides `cool`).
## The lights light the blades' undersides and noses, the frame's inner lip and a little of the floor in front; no
## shadows (the blades would black them out). The game copies this rule (HANDOFF).

const ROWS := 3                 # lights up the opening
const OUT_M := 0.075            # in front of the panel (the blades' backs stand about 17 cm in front of it)
const LOOK := {                 # suffix: [colour, energy, range m]
	"cool": [Color(0.0, 0.62, 1.0), 0.7, 0.75],    # vents-b3: saturated, shorter (b2's 1.1 m hazed the wall above)
	"heat": [Color(1.0, 0.2, 0.02), 0.7, 0.75],    # vents-b3: a deep red-orange

}
## gills step 2 (2026-10-27): the gills' panels light their four slits instead: per slit (the middle of its two cyan
## jambs `<id>_jamb<k>a/b`, inside the 3 cm cut) SLIT_ROWS lights, so the light pours out of each gap onto the
## covers' backs and sides and back onto the well's walls and honeycomb
const SLIT_ROWS := 3
const SLIT_LOOK := {"cool": [Color(0.0, 0.48, 1.0), 1.0, 0.6], "heat": [Color(1.0, 0.2, 0.02), 1.6, 0.6]}
## gills step 3: the slit lights SLIT_IN_M deeper than the jambs, inside the well: from the cut they lit the convex
## covers' fronts through the covers (no shadows); from there the fronts face away from them
const SLIT_IN_M := 0.03
## gills step 3: per groove under a rib edge (its seam `<id>_seam<k>`) GAP_ROWS small lights between the ribs' flanks;
## gills step 4 (the window: every gap a slot into the well): per gap's seam GAP_ROWS lights GAP_IN_M behind the wall's
## face (in the plate's cut, behind the ribs' backs, so no cover front faces them: no blob on the faces), at GAP_FRAC of the seam's height
## (the top row low enough to leave the crowns' feet dark), lighting the ribs' pale flanks and the well; the cyan a
## little less saturated (the floor wash)
const GAP_ROWS := 3
const GAP_IN_M := 0.015
const GAP_FRAC := [0.25, 0.5, 0.72]
const GAP_LOOK := {"cool": [Color(0.18, 0.66, 1.0), 0.9, 0.36], "heat": [Color(1.0, 0.2, 0.02), 0.9, 0.36]}
## Every well light lights the inside's render layer only (ship.gd's INSIDE_LAYER): none leaks onto the hull's
## outside behind a shallow well (omni lights pass through walls)
const INSIDE_MASK := 1


## Adds the lights under every `<id>_cool` and `<id>_heat` mesh below n; `scale` multiplies their energy. Returns
## how many it added.
static func add(n: Node, scale: float = 1.0) -> int:
	var count: int = 0
	for suffix: String in LOOK:
		for found: Node in n.find_children("*_" + suffix, "MeshInstance3D", true, false):
			var mi: MeshInstance3D = found
			if not String(mi.name).begins_with("station_vent_") or mi.mesh == null:
				continue
			if _slits(mi, suffix) > 0:
				count += _slits(mi, suffix, true, scale)
				continue
			var box: AABB = mi.mesh.get_aabb()
			var spec: Array = LOOK[suffix]
			for k: int in ROWS:
				var o: OmniLight3D = OmniLight3D.new()
				o.name = "%s_light%d" % [mi.name, k + 1]
				o.position = Vector3(box.get_center().x, box.position.y + box.size.y * (k + 0.5) / ROWS,
					box.end.z + OUT_M)
				o.light_color = spec[0]
				o.light_energy = float(spec[1]) * scale
				o.omni_range = float(spec[2])
				o.omni_attenuation = 1.2
				o.shadow_enabled = false
				o.light_cull_mask = INSIDE_MASK
				mi.add_child(o)
				count += 1
	return count


## The gills' slit lights under the glow panel mi (its piece's jambs, siblings of mi); returns how many there are
## (put: adds them).
static func _slits(mi: MeshInstance3D, suffix: String, put: bool = false, scale: float = 1.0) -> int:
	var pid: String = String(mi.name).trim_suffix("_" + suffix)
	var parent: Node = mi.get_parent()
	if parent == null:
		return 0
	var count: int = 0
	var spec: Array = SLIT_LOOK[suffix]
	for k: int in range(1, 9):
		var a: Node = parent.get_node_or_null(NodePath("%s_jamb%da" % [pid, k]))
		var b: Node = parent.get_node_or_null(NodePath("%s_jamb%db" % [pid, k]))
		if not (a is MeshInstance3D and b is MeshInstance3D):
			break
		if not put:
			count += SLIT_ROWS
			continue
		var ja: MeshInstance3D = a
		var jb: MeshInstance3D = b
		var inv: Transform3D = mi.transform.affine_inverse()
		var ba: AABB = ja.mesh.get_aabb()
		var pa: Vector3 = inv * (ja.transform * ba.get_center())
		var pb: Vector3 = inv * (jb.transform * jb.mesh.get_aabb().get_center())
		for r: int in SLIT_ROWS:
			var o: OmniLight3D = OmniLight3D.new()
			o.name = "%s_slit%d_light%d" % [mi.name, k, r + 1]
			var y: float = ba.position.y + ba.size.y * (r + 0.5) / SLIT_ROWS - ba.get_center().y
			o.position = (pa + pb) * 0.5 + Vector3(0.0, y, SLIT_IN_M)   # +z: into the wall
			o.light_color = spec[0]
			o.light_energy = float(spec[1]) * scale
			o.omni_range = float(spec[2])
			o.omni_attenuation = 1.2
			o.shadow_enabled = false
			o.light_cull_mask = INSIDE_MASK
			mi.add_child(o)
			count += 1
	for k: int in range(1, 9):
		var g: Node = parent.get_node_or_null(NodePath("%s_seam%d" % [pid, k]))
		if not (g is MeshInstance3D):
			break
		if not put:
			count += GAP_ROWS
			continue
		var gm: MeshInstance3D = g
		var gb: AABB = gm.mesh.get_aabb()
		var inv2: Transform3D = mi.transform.affine_inverse()
		var look: Array = GAP_LOOK[suffix]
		for r: int in GAP_ROWS:
			var c: Vector3 = gb.get_center()
			var y2: float = gb.position.y + gb.size.y * float(GAP_FRAC[r])
			var o2: OmniLight3D = OmniLight3D.new()
			o2.name = "%s_gap%d_light%d" % [mi.name, k, r + 1]
			# GAP_IN_M behind the wall's face: the piece's +z (Godot (x, h, -v))
			o2.position = inv2 * (gm.transform * Vector3(c.x, y2, GAP_IN_M))
			o2.light_color = look[0]
			o2.light_energy = float(look[1]) * scale
			o2.omni_range = float(look[2])
			o2.omni_attenuation = 1.2
			o2.shadow_enabled = false
			o2.light_cull_mask = INSIDE_MASK
			mi.add_child(o2)
			count += 1
	return count
