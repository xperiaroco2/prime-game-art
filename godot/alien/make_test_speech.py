"""A short speech-like test WAV for the alien's talk proof (art #196, S3); Python standard library only.

No speech recording exists in the repo or the raw folder, so this makes one: syllables of a 125 Hz voice (harmonics
with a little vibrato) shaped by two formant resonances per vowel (A, E, O, with an M hum), loud and quiet syllables,
short gaps between them and two longer pauses. Mono, 16 bit, 22,050 Hz, about 4.6 s.

    python godot/alien/make_test_speech.py <out.wav>

Prints the syllable table (start, length, vowel, level) so a run can be checked against what was played.
"""
from __future__ import annotations

import math
import struct
import sys
import wave

RATE = 22050
F0 = 125.0
FORMANTS = {"A": (750, 1150), "E": (420, 2250), "O": (480, 850), "M": (260, 1100)}  # Hz
# (vowel, seconds, level 0-1, gap after in seconds)
SYLLABLES = [
    ("A", 0.22, 1.0, 0.05), ("E", 0.18, 0.8, 0.04), ("O", 0.26, 1.0, 0.25),
    ("M", 0.12, 0.5, 0.02), ("A", 0.30, 0.9, 0.06), ("E", 0.16, 0.45, 0.05), ("O", 0.20, 0.6, 0.45),
    ("E", 0.24, 1.0, 0.04), ("A", 0.14, 0.4, 0.04), ("O", 0.32, 0.95, 0.08), ("M", 0.10, 0.4, 0.03),
    ("A", 0.25, 0.85, 0.30), ("O", 0.18, 0.5, 0.05), ("E", 0.22, 0.9, 0.2),
]


def resonance(f, centre, width=90.0):
    return 1.0 / (1.0 + ((f - centre) / width) ** 2)


def syllable(vowel, seconds, level):
    f1, f2 = FORMANTS[vowel]
    n = int(seconds * RATE)
    harmonics = []
    for k in range(1, 40):
        f = F0 * k
        if f > 5000:
            break
        amp = (resonance(f, f1) + 0.7 * resonance(f, f2) + 0.02) / k ** 0.6
        harmonics.append((k, amp))
    total = sum(a for _, a in harmonics)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / 0.025, (seconds - t) / 0.04)  # 25 ms attack, 40 ms release
        f0 = F0 * (1.0 + 0.02 * math.sin(2 * math.pi * 5.0 * t))
        phase += 2 * math.pi * f0 / RATE
        s = sum(a * math.sin(k * phase) for k, a in harmonics) / total
        out.append(s * env * level)
    return out


def main():
    path = sys.argv[1]
    samples = [0.0] * int(0.15 * RATE)
    table = []
    for vowel, seconds, level, gap in SYLLABLES:
        table.append((round(len(samples) / RATE, 3), seconds, vowel, level))
        samples += syllable(vowel, seconds, level)
        samples += [0.0] * int(gap * RATE)
    samples += [0.0] * int(0.2 * RATE)
    peak = max(abs(s) for s in samples)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s / peak * 0.8 * 32767)) for s in samples))
    print(f"wrote {path}: {len(samples) / RATE:.2f} s")
    for row in table:
        print("SYLLABLE start %.3f len %.2f %s level %.2f" % row)


if __name__ == "__main__":
    main()
