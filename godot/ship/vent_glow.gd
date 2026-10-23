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
	"cool": [Color(0.15, 0.75, 1.0), 0.9, 1.1],
	"heat": [Color(1.0, 0.38, 0.06), 0.7, 0.9],
}


## Adds the lights under every `<id>_cool` and `<id>_heat` mesh below n; `scale` multiplies their energy. Returns
## how many it added.
static func add(n: Node, scale: float = 1.0) -> int:
	var count: int = 0
	for suffix: String in LOOK:
		for found: Node in n.find_children("*_" + suffix, "MeshInstance3D", true, false):
			var mi: MeshInstance3D = found
			if not String(mi.name).begins_with("station_vent_") or mi.mesh == null:
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
				mi.add_child(o)
				count += 1
	return count
