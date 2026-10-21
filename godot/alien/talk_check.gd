extends SceneTree
## M13 (art #196, PR #246's review minor 2): alien_talk.gd's styled() and sample() run headless on its LINE, printed
## as one JSON line "TALK {...}" for tools/tests/test_alien_talk_godot.py: per design the raw segments, the styled
## runs and a sample every 5 ms (t, piece, drop, pucker, thrust; M14: the tongue's flop x and y).
##     godot --headless --path godot -s res://alien/talk_check.gd

const AlienTalk = preload("res://alien/alien_talk.gd")


func _init() -> void:
	var segs: Array = AlienTalk.segments(AlienTalk.LINE)
	var out := {"segments": segs, "line_ms": AlienTalk.LINE_MS, "open": AlienTalk.OPEN, "styles": AlienTalk.STYLES,
		"designs": {}}
	for d: String in AlienTalk.STYLES:
		var samples: Array = []
		var t := 0.0
		while t <= AlienTalk.LINE_MS:
			var s: Dictionary = AlienTalk.sample(d, segs, t)
			var fl: Vector3 = s["flop"]
			samples.append([t, s["piece"], s["drop"], s["pucker"], s["thrust"], fl.x, fl.y])
			t += 5.0
		out["designs"][d] = {"styled": AlienTalk.styled(d, segs), "samples": samples}
	print("TALK ", JSON.stringify(out))
	quit(0)
