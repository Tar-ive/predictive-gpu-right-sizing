"""Synthesize the video's background bed: a soft ambient pad with a quiet pluck.

Original, generated from scratch (no samples), so it is free to publish.
Output: public/music.wav (48 kHz stereo, 16-bit). Loudness is set afterwards
with ffmpeg loudnorm (see README in this folder / the render notes).

Run: python scripts/make_music.py
"""
import wave
from pathlib import Path

import numpy as np

SR = 48_000
DUR = 46.0  # video is 45.55 s
BPM = 84
EIGHTH = 60 / BPM / 2
OUT = Path(__file__).resolve().parent.parent / "public" / "music.wav"

A4 = 440.0
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name: str) -> float:
    pitch, octave = name[:-1], int(name[-1])
    semis = NOTE[pitch] - NOTE["A"] + 12 * (octave - 4)
    return A4 * 2 ** (semis / 12)


# Calm progression, one chord per ~5.7 s (8 chords ≈ the whole video)
CHORDS = [
    ("F2", ["F3", "A3", "C4", "E4", "G4"]),   # Fmaj9
    ("E2", ["E3", "G3", "C4", "E4", "B4"]),   # C/E add
    ("A2", ["A3", "C4", "E4", "G4"]),         # Am7
    ("G2", ["G3", "A3", "D4", "G4"]),         # Gsus2
] * 2
SEG = DUR / len(CHORDS)

t = np.arange(int(SR * DUR)) / SR
L = np.zeros_like(t)
R = np.zeros_like(t)


def env_adsr(n, attack, release):
    e = np.ones(n)
    a = int(attack * SR)
    r = int(release * SR)
    e[:a] = np.linspace(0, 1, a) ** 2
    e[-r:] *= np.linspace(1, 0, r) ** 1.5
    return e


def add(sig_l, sig_r, start):
    i = int(start * SR)
    j = min(len(t), i + len(sig_l))
    L[i:j] += sig_l[: j - i]
    R[i:j] += sig_r[: j - i]


# Pad + bass, overlapping chords for a seamless wash
for k, (bass, notes) in enumerate(CHORDS):
    start = k * SEG
    length = SEG + 1.8
    n = int(length * SR)
    tt = np.arange(n) / SR
    e = env_adsr(n, attack=1.6, release=1.8)
    lfo = 1 + 0.08 * np.sin(2 * np.pi * 0.17 * tt + k)  # slow breathing
    pl = np.zeros(n)
    pr = np.zeros(n)
    for f in map(hz, notes):
        for detune, amp in ((1.0, 1.0), (2.0, 0.18), (3.0, 0.05)):
            pl += amp * np.sin(2 * np.pi * f * detune * 1.0025 * tt)
            pr += amp * np.sin(2 * np.pi * f * detune * 0.9975 * tt + 0.7)
    pl *= 0.055 * e * lfo
    pr *= 0.055 * e * lfo
    fb = hz(bass)
    b = 0.16 * np.sin(2 * np.pi * fb * tt) * env_adsr(n, 2.0, 2.0)
    add(pl + b, pr + b, start)

# Quiet pluck arpeggio from the first demo scene (3.5 s) until the end card fades
PATTERN = [0, 2, 1, 3, 2, 1, 3, 2]
pluck_len = int(1.2 * SR)
pt = np.arange(pluck_len) / SR
pluck_env = np.exp(-pt * 5.5) * (1 - np.exp(-pt * 400))
step = 0
s = 3.5
while s < DUR - 3.0:
    chord = CHORDS[min(int(s // SEG), len(CHORDS) - 1)][1]
    f = hz(chord[PATTERN[step % len(PATTERN)] % len(chord)]) * 2
    tone = (np.sin(2 * np.pi * f * pt) + 0.25 * np.sin(2 * np.pi * 2 * f * pt)) * pluck_env * 0.045
    pan = 0.5 + 0.25 * np.sin(step * 0.9)
    add(tone * (1 - pan) * 2, tone * pan * 2, s)
    step += 1
    s += EIGHTH * (2 if step % 4 == 0 else 1)  # small rhythmic breath every bar


# Cheap room: a few decaying taps, crossed between channels
def taps(x, y):
    out_l, out_r = x.copy(), y.copy()
    for delay, g in ((0.149, 0.28), (0.233, 0.22), (0.371, 0.16), (0.523, 0.11), (0.797, 0.07)):
        d = int(delay * SR)
        out_l[d:] += g * y[:-d]
        out_r[d:] += g * x[:-d]
    return out_l, out_r


L, R = taps(L, R)

# Fades: in 1.5 s, out 3.5 s
fade_in = int(1.5 * SR)
fade_out = int(3.5 * SR)
for ch in (L, R):
    ch[:fade_in] *= np.linspace(0, 1, fade_in) ** 2
    ch[-fade_out:] *= np.linspace(1, 0, fade_out) ** 2

peak = max(np.abs(L).max(), np.abs(R).max())
stereo = np.stack([L, R], axis=1) / peak * 0.89
pcm = (stereo * 32767).astype(np.int16)

OUT.parent.mkdir(parents=True, exist_ok=True)
with wave.open(str(OUT), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f"wrote {OUT} ({DUR:.1f}s)")
