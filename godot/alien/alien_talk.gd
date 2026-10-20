extends RefCounted
## M12 (art #196): the talk data. A phase line (the mouth shapes of a spoken line, in time) and each mouth design's own
## talk style, which turns the line into the shown piece and its secondary motion at any moment. Pure functions, so a
## proof can render any frame of a line (alien.gd talk_at(), m12_shots.gd); alien.gd play_line() drives it in time.
##
## A line: an Array of words, each [start_ms, [[phase, ms], ...]] (phases rest, M, small, A, E, O; a word's phases
## follow each other; silence between words). segments() flattens it to [start_ms, end_ms, phase] runs.
##
## A style (STYLES[design]):
## - lag_ms: the mouth follows the voice this much later (a lazier mouth);
## - merge_ms: a phase shorter than this takes the shape before it (no flicker on fast syllables);
## - short_ms, short_to: an open phase (A, E) shorter than short_ms shows short_to (a softer, half-open talk);
## - m_gap_ms: a silence shorter than this between two phases shows M (the lips pressed), longer shows rest;
## - bounce {amp, hz, decay_ms}: after every change of shape the lower lip springs: drop = amp x the change in
##   openness x sin(2 pi hz dt) x exp(-dt / decay) metres (positive: down), alien_lip.gdshader `lip_drop`;
## - pucker {amount, min_gap_ms}: in a silence at least min_gap_ms long the lips purse, amount x a sine ease over the
##   gap (alien_lip.gdshader `pucker`).
## frog and overbite keep the snapped talk they had (no lag, merge, bounce or pucker). The pout (mp1, M12) talks soft
## and a little lazy: a 25 ms lag, merged 70 ms flickers, quick A and E shown half open, a soft lower-lip bounce, and a
## slight pucker between words.

const OPEN := {"rest": 0.0, "M": 0.0, "small": 0.4, "O": 0.6, "E": 0.7, "A": 1.0}

const STYLES := {
	"frog": {"lag_ms": 0.0, "merge_ms": 0.0, "short_ms": 0.0, "short_to": "small", "m_gap_ms": 160.0,
		"bounce": {"amp": 0.0, "hz": 6.0, "decay_ms": 150.0}, "pucker": {"amount": 0.0, "min_gap_ms": 100.0}},
	"overbite": {"lag_ms": 0.0, "merge_ms": 0.0, "short_ms": 0.0, "short_to": "small", "m_gap_ms": 160.0,
		"bounce": {"amp": 0.0, "hz": 6.0, "decay_ms": 150.0}, "pucker": {"amount": 0.0, "min_gap_ms": 100.0}},
	"pout": {"lag_ms": 25.0, "merge_ms": 70.0, "short_ms": 85.0, "short_to": "small", "m_gap_ms": 120.0,
		"bounce": {"amp": 0.0014, "hz": 6.5, "decay_ms": 140.0}, "pucker": {"amount": 0.8, "min_gap_ms": 100.0}},
}

## A test line with a voice-like rhythm (about 5.6 s: two short sentences and an answer; syllables 60-260 ms, word
## gaps 60-200 ms, sentence pauses 380-450 ms). The phases follow the words' vowels and lip closures.
const LINE := [
	[200, [["E", 150]]],  # hey
	[470, [["A", 170]]],  # I
	[700, [["small", 60], ["O", 150]]],  # saw
	[980, [["small", 50], ["O", 120]]],  # you
	[1230, [["M", 60], ["A", 140]]],  # by
	[1490, [["small", 80]]],  # the
	[1620, [["A", 160], ["E", 90], ["small", 70]]],  # garden
	[2400, [["O", 60], ["A", 120], ["small", 50]]],  # was
	[2700, [["A", 150]]],  # that
	[2940, [["small", 40], ["O", 160]]],  # you
	[3620, [["M", 260]]],  # mm
	[4000, [["A", 150]]],  # I
	[4230, [["small", 60], ["E", 110]]],  # think
	[4520, [["small", 60], ["O", 230]]],  # so
]
const LINE_MS := 5300.0


## The line as [start_ms, end_ms, phase] runs.
static func segments(line: Array) -> Array:
	var out: Array = []
	for w: Array in line:
		var t: float = float(w[0])
		for ph: Array in w[1]:
			out.append([t, t + float(ph[1]), str(ph[0])])
			t += float(ph[1])
	return out


## The style's runs: merged flickers and half-open quick syllables (the style's phase shapes).
static func styled(design: String, segs: Array) -> Array:
	var st: Dictionary = STYLES.get(design, STYLES["frog"])
	var out: Array = []
	for s: Array in segs:
		var ph: String = s[2]
		var dur: float = s[1] - s[0]
		if (ph == "A" or ph == "E") and dur < st["short_ms"]:
			ph = st["short_to"]
		if dur < st["merge_ms"] and not out.is_empty() and s[0] - out[-1][1] < 1.0:
			out[-1][1] = s[1]  # the shape before it holds on
			continue
		out.append([s[0], s[1], ph])
	return out


## The piece and its secondary motion at t_ms: {"piece", "drop" (m), "pucker" (0..1), "since_ms"}.
static func sample(design: String, segs: Array, t_ms: float) -> Dictionary:
	var st: Dictionary = STYLES.get(design, STYLES["frog"])
	var runs: Array = styled(design, segs)
	var t: float = t_ms - float(st["lag_ms"])
	var piece := "rest"
	var since: float = t  # when the shown shape began
	var prev_open: float = 0.0
	var pk: float = 0.0
	for i: int in runs.size():
		var r: Array = runs[i]
		if t < r[0]:
			# a silence before run i: M if short and after a phase, else rest (with the pucker)
			var g0: float = runs[i - 1][1] if i > 0 else -1e9
			if i > 0 and r[0] - g0 < st["m_gap_ms"]:
				piece = "M"
			since = g0 if i > 0 else 0.0
			prev_open = OPEN[runs[i - 1][2]] if i > 0 else 0.0
			var gap: float = r[0] - g0
			if i > 0 and gap >= st["pucker"]["min_gap_ms"]:
				pk = float(st["pucker"]["amount"]) * pow(sin(PI * clampf((t - g0) / gap, 0.0, 1.0)), 0.7)
			break
		if t < r[1]:
			piece = r[2]
			since = r[0]
			var before_open: float = 0.0
			if i > 0 and r[0] - runs[i - 1][1] < 1.0:
				before_open = OPEN[runs[i - 1][2]]
			prev_open = before_open
			break
		if i == runs.size() - 1:  # after the line
			since = r[1]
			prev_open = OPEN[r[2]]
	var dt: float = maxf(0.0, t - since)
	var b: Dictionary = st["bounce"]
	var change: float = absf(OPEN.get(piece, 0.0) - prev_open)
	var drop: float = float(b["amp"]) * change * sin(TAU * float(b["hz"]) * dt / 1000.0) * exp(-dt / float(b["decay_ms"]))
	return {"piece": piece, "drop": drop, "pucker": pk, "since_ms": since}
