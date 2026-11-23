"""Original, copyright-free upbeat background track + cut sound effects for reels.

make_audio(cut_times, total_sec, out_wav): 124 BPM four-on-the-floor beat with bass
and chord stabs, plus a whoosh into every cut and a short pop on it.
"""
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

SR = 44100
BPM = 124
BEAT = 60 / BPM
rng = np.random.default_rng(7)


def _env(n, decay):
    return np.exp(-np.linspace(0, decay, n))


def _hp(x, hz):
    b, a = butter(2, hz / (SR / 2), "high")
    return lfilter(b, a, x)


def _lp(x, hz):
    b, a = butter(2, hz / (SR / 2), "low")
    return lfilter(b, a, x)


def _add(buf, sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += gain * sig[: j - i]


def kick():
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    freq = 45 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * _env(n, 7)


def hat():
    n = int(0.05 * SR)
    return _hp(rng.standard_normal(n), 7000) * _env(n, 9) * 0.5


def clap():
    n = int(0.16 * SR)
    return _lp(_hp(rng.standard_normal(n), 900), 5000) * _env(n, 10) * 0.7


def tone(freq, dur, decay=4, kind="saw"):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "saw":
        w = 2 * (t * freq - np.floor(0.5 + t * freq))
    else:
        w = np.sin(2 * np.pi * freq * t)
    return w * _env(n, decay)


def whoosh(dur=0.28):
    n = int(dur * SR)
    noise = _hp(rng.standard_normal(n), 1500)
    swell = np.linspace(0, 1, n) ** 2
    return _lp(noise, 6000) * swell * 0.35


def pop():
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    f = 1400 - 800 * t / 0.06
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 6) * 0.35


def make_audio(cut_times, total, out_wav):
    n = int((total + 0.5) * SR)
    music = np.zeros(n)
    sfx = np.zeros(n)
    roots = [110.0, 87.31, 130.81, 98.0]  # A2 F2 C3 G2
    chords = [[220, 261.63, 329.63], [174.61, 220, 261.63], [261.63, 329.63, 392], [196, 246.94, 293.66]]
    beats = int(total / BEAT) + 2
    for b in range(beats):
        t = b * BEAT
        bar = (b // 4) % 4
        _add(music, kick(), t, 0.9)
        _add(music, hat(), t + BEAT / 2, 0.6)
        if b % 4 in (1, 3):
            _add(music, clap(), t, 0.5)
        for e in range(2):
            _add(music, _lp(tone(roots[bar], BEAT / 2 * 0.9, 5), 900), t + e * BEAT / 2, 0.28)
        if b % 4 == 0:
            for f in chords[bar]:
                _add(music, tone(f, BEAT * 1.5, 3, "sine"), t, 0.09)
    for ct in cut_times:
        _add(sfx, whoosh(), max(0, ct - 0.28), 1.0)
        _add(sfx, pop(), ct, 1.0)
    mix = music * 0.55 + sfx
    fade = int(0.6 * SR)
    end = int(total * SR)
    mix = mix[:end]
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1e-9, np.max(np.abs(mix))) / 0.85
    stereo = np.stack([mix, mix], axis=1)
    wavfile.write(out_wav, SR, (stereo * 32767).astype(np.int16))
    return out_wav
