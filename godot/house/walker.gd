extends RefCounted
## The capsule walker shared by `house --walk` (walk.gd) and the export check (export_check.gd, art #122;
## docs/house.md): a CharacterBody3D capsule walks waypoints on the world layer in simulated time. Works headless
## (physics needs no window). Preloaded by its relative path, so the export check's copy in `_check/` finds it too.

const SPEED: float = 3.0
const MAX_S: float = 8.0  # a walk's limit in simulated seconds unless the caller sets one
## Moves per physics frame: the walk runs in simulated time (steps x 1/ticks), several moves a frame, so the long
## routes (house_routes, art #78) take a quarter of their walking time on the clock.
const SUBSTEPS: int = 4


## A capsule (radius r, 1.8 m) walks the waypoints [x, h, z] at `speed`; it arrives when it reaches the last within
## 0.3 m and its height within 0.15 m. Stops early when it has not moved for 30 ticks, or after max_s simulated
## seconds. Reports the simulated seconds and the metres walked on the floor plan.
static func walk(tree: SceneTree, r: float, points: Array, speed: float = SPEED, max_s: float = MAX_S) -> Dictionary:
	var body: CharacterBody3D = CharacterBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	var cap: CapsuleShape3D = CapsuleShape3D.new()
	cap.radius = r
	cap.height = 1.8
	shape.shape = cap
	shape.position.y = 0.9
	body.add_child(shape)
	body.floor_snap_length = 0.3
	tree.root.add_child(body)
	body.global_position = v3(points[0]) + Vector3(0, 0.05, 0)
	await tree.physics_frame
	var reached: int = 0
	var dt: float = 1.0 / Engine.physics_ticks_per_second
	var steps: int = 0
	var stuck: int = 0
	var last: Vector3 = body.global_position
	var metres: float = 0.0
	while steps < max_s * Engine.physics_ticks_per_second and reached < points.size() - 1 and stuck < 30:
		if steps % SUBSTEPS == 0:
			await tree.physics_frame
		steps += 1
		var target: Vector3 = v3(points[reached + 1])
		var flat: Vector3 = Vector3(target.x - body.global_position.x, 0, target.z - body.global_position.z)
		while flat.length() < 0.3 and reached < points.size() - 2:  # next waypoint in the same tick: no idle ticks
			reached += 1
			target = v3(points[reached + 1])
			flat = Vector3(target.x - body.global_position.x, 0, target.z - body.global_position.z)
		if flat.length() < 0.3:
			reached += 1
			continue
		var v: Vector3 = flat.normalized() * speed
		v.y = 0.0 if body.is_on_floor() else body.velocity.y - 9.8 * dt
		body.velocity = v
		body.move_and_slide()
		stuck = stuck + 1 if body.global_position.distance_to(last) < 0.002 else 0
		metres += Vector2(body.global_position.x - last.x, body.global_position.z - last.z).length()
		last = body.global_position
	var end: Vector3 = body.global_position
	var arrived: bool = reached == points.size() - 1 and absf(end.y - float(points[-1][1])) < 0.15
	body.queue_free()
	await tree.physics_frame
	return {"radius_m": r, "reached": reached + 1, "of": points.size(), "end": [snappedf(end.x, 0.01),
		snappedf(end.y, 0.01), snappedf(end.z, 0.01)], "seconds": snappedf(steps * dt, 0.01), "metres": snappedf(metres, 0.01), "arrived": arrived}


## A pad under a walk's end that has no floor (the yard): [x, h, z] or [x, h, z, w, d] (cut back from a stairwell).
static func pad(tree: SceneTree, p: Array) -> void:
	var body: StaticBody3D = StaticBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	var box: BoxShape3D = BoxShape3D.new()
	box.size = Vector3(p[3], 0.2, p[4]) if p.size() > 4 else Vector3(3, 0.2, 3)
	shape.shape = box
	body.add_child(shape)
	body.position = Vector3(p[0], float(p[1]) - 0.1, p[2])
	tree.root.add_child(body)


static func v3(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))
