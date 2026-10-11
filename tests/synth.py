"""合成一首已知音符的测试曲：120 BPM、4/4、C 大调，四个声部各写成一条音轨。"""

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
BPM = 120
BEAT = 60 / BPM
LEAD = 0.5  # 开头留半秒静音，和真实录音一样


def tone(midi, dur, sr=SR, harmonics=(1, .5, .3, .15)):
    t = np.arange(int(dur * sr)) / sr
    f = 440 * 2 ** ((midi - 69) / 12)
    y = sum(a * np.sin(2 * np.pi * f * (k + 1) * t) for k, a in enumerate(harmonics))
    env = np.minimum(1, t / 0.01) * np.exp(-t * 1.5)
    env[-int(0.02 * sr):] *= np.linspace(1, 0, int(0.02 * sr))
    return (y * env).astype(np.float32)


def place(buf, y, t):
    i = int((t + LEAD) * SR)
    buf[i:i + len(y)] += y[: max(0, len(buf) - i)]


# (起始拍, 时值拍, 音高)
MELODY = [(0, 1, 72), (1, 1, 74), (2, 1, 76), (3, 1, 72), (4, 2, 76), (6, 2, 77),
          (8, 1, 79), (9, 1, 77), (10, 1, 76), (11, 1, 74), (12, 4, 72)]
BASS = [(b, 1, p) for b, p in zip(range(16), [36] * 4 + [41] * 4 + [43] * 4 + [36] * 4)]
CHORDS = [(0, 4, (60, 64, 67)), (4, 4, (60, 65, 69)), (8, 4, (59, 62, 67)), (12, 4, (60, 64, 67))]


def write_song(out_dir: Path, bars: int = 8) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = int((bars * 4 * BEAT + 1 + LEAD) * SR)
    stems = {k: np.zeros(n, np.float32) for k in ("vocals", "bass", "piano", "drums", "guitar", "other")}
    for rep in range(bars // 4):  # 四小节的乐句重复
        o = rep * 16
        for b, d, p in MELODY:
            place(stems["vocals"], 0.3 * tone(p, d * BEAT * 0.95), (o + b) * BEAT)
        for b, d, p in BASS:
            place(stems["bass"], 0.4 * tone(p, d * BEAT * 0.9, harmonics=(1, .6, .2)), (o + b) * BEAT)
        for b, d, ch in CHORDS:
            for p in ch:
                place(stems["piano"], 0.15 * tone(p, d * BEAT * 0.95), (o + b) * BEAT)
    rng = np.random.default_rng(0)
    t = np.arange(int(0.15 * SR)) / SR
    kick = (np.sin(2 * np.pi * (60 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 20)).astype(np.float32)
    hat = (rng.standard_normal(int(0.05 * SR)) * np.exp(-np.arange(int(0.05 * SR)) / SR * 80)).astype(np.float32)
    hat = np.diff(hat, prepend=0).astype(np.float32)
    fade = np.linspace(1, 0, len(t)) ** 2  # 避免截断处的爆音被当成一次击打
    kick *= fade
    snare = ((rng.standard_normal(len(t)) * np.exp(-t * 25) * 0.5
              + np.sin(2 * np.pi * 200 * t) * np.exp(-t * 30)) * fade).astype(np.float32)
    for beat in range(bars * 4):
        place(stems["drums"], 0.8 * (kick if beat % 2 == 0 else snare), beat * BEAT)
        place(stems["drums"], 0.2 * hat, beat * BEAT + BEAT / 2)
    paths = {}
    for k, y in stems.items():
        paths[k] = out_dir / f"{k}.wav"
        sf.write(paths[k], np.stack([y, y], 1), SR)
    mix = sum(stems.values())
    mix /= np.abs(mix).max() + 1e-9
    paths["mix"] = out_dir / "mix.wav"
    sf.write(paths["mix"], np.stack([mix, mix], 1) * 0.9, SR)
    return paths
