"""扒谱：把单条音轨转成音符列表。

- 钢琴：ByteDance piano_transcription（钢琴专用，含踏板）
- 人声 / 贝斯 / 吉他 / 其他：Spotify Basic Pitch（ONNX 版，不需要 TensorFlow）
- 鼓：M0 先用起音检测 + 频段能量粗分底鼓 / 军鼓 / 踩镲，M2 换成 ADTOF
"""

from pathlib import Path
import urllib.request

import librosa
import numpy as np

from . import audio
from .notes import Note
from .stems import StemSpec

SILENCE_RMS = 0.005

PIANO_CKPT_URL = ("https://zenodo.org/record/4034264/files/"
                  "CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1")
PIANO_CKPT = (Path.home() / "piano_transcription_inference_data"
              / "note_F1=0.9677_pedal_F1=0.9186.pth")

# General MIDI 打击乐编号
KICK, SNARE, HIHAT = 36, 38, 42


def is_silent(path: Path) -> bool:
    y = audio.load(path, sr=22050, mono=True)
    return y.size == 0 or float(np.sqrt(np.mean(y ** 2))) < SILENCE_RMS


def transcribe(path: Path, spec: StemSpec, device: str = "cpu") -> list[Note]:
    if is_silent(path):
        return []
    if spec.is_drum:
        return transcribe_drums(path)
    if spec.name == "piano":
        return transcribe_piano(path, device)
    notes = transcribe_basic_pitch(path, spec)
    return keep_top_line(notes) if spec.monophonic else notes


def transcribe_basic_pitch(path: Path, spec: StemSpec) -> list[Note]:
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    _, _, events = predict(
        str(path), ICASSP_2022_MODEL_PATH,
        onset_threshold=spec.onset_threshold,
        frame_threshold=spec.frame_threshold,
        minimum_note_length=spec.min_note_ms,
        minimum_frequency=spec.min_hz,
        maximum_frequency=spec.max_hz,
        melodia_trick=True,
    )
    return [Note(float(s), float(e), int(p), int(np.clip(a * 127, 1, 127)))
            for s, e, p, a, _ in events]


def ensure_piano_checkpoint() -> Path:
    if PIANO_CKPT.exists() and PIANO_CKPT.stat().st_size > 1.6e8:
        return PIANO_CKPT
    PIANO_CKPT.parent.mkdir(parents=True, exist_ok=True)
    tmp = PIANO_CKPT.with_suffix(".part")
    urllib.request.urlretrieve(PIANO_CKPT_URL, tmp)
    tmp.replace(PIANO_CKPT)
    return PIANO_CKPT


def transcribe_piano(path: Path, device: str = "cpu") -> list[Note]:
    import torch
    from piano_transcription_inference import PianoTranscription, sample_rate

    ckpt = ensure_piano_checkpoint()
    model = PianoTranscription(device=torch.device(device), checkpoint_path=str(ckpt))
    y = audio.load(path, sr=sample_rate, mono=True)
    out_mid = path.with_suffix(".piano_raw.mid")
    result = model.transcribe(y, str(out_mid))
    return [Note(float(e["onset_time"]), float(e["offset_time"]),
                 int(e["midi_note"]), int(e["velocity"]))
            for e in result["est_note_events"]]


def transcribe_drums(path: Path) -> list[Note]:
    """粗略版：检测每个起音点，按低 / 中 / 高频能量判断是底鼓、军鼓还是踩镲。"""
    sr = 22050
    y = audio.load(path, sr=sr, mono=True)
    hop = 256
    onsets = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop, units="time",
                                        backtrack=True, delta=0.08)
    if len(onsets) == 0:
        return []
    # 一次击打可能触发两个相邻的起音点，60 毫秒内的合并成一个
    merged = [onsets[0]]
    for t in onsets[1:]:
        if t - merged[-1] > 0.06:
            merged.append(t)
    onsets = np.asarray(merged)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    bands = {KICK: (20, 150), SNARE: (150, 3000), HIHAT: (6000, 11000)}
    win = max(1, int(0.05 * sr / hop))

    energies = []
    for t in onsets:
        f = int(t * sr / hop)
        seg = S[:, f:f + win]
        energies.append({k: float(seg[(freqs >= lo) & (freqs < hi)].mean())
                         for k, (lo, hi) in bands.items()})
    # 每个频段按全曲的分布归一化，再用阈值决定是否算一次击打
    ref = {k: np.percentile([e[k] for e in energies], 90) + 1e-9 for k in bands}
    notes = []
    for t, e in zip(onsets, energies):
        hits = [k for k in bands if e[k] / ref[k] > 0.45]
        if not hits:
            hits = [max(bands, key=lambda k: e[k] / ref[k])]
        for k in hits:
            vel = int(np.clip(60 + 60 * min(1.0, e[k] / ref[k]), 1, 127))
            notes.append(Note(float(t), float(t) + 0.1, k, vel))
    return notes


def keep_top_line(notes: list[Note]) -> list[Note]:
    """单音声部：同一时间只保留最响的那个音，并把重叠部分截断。"""
    notes = sorted(notes, key=lambda n: (n.start, -n.velocity))
    out: list[Note] = []
    for n in notes:
        if out and n.start < out[-1].end:
            prev = out[-1]
            if n.velocity <= prev.velocity and n.end <= prev.end:
                continue
            prev.end = n.start
            if prev.end - prev.start < 0.05:
                out.pop()
        out.append(Note(n.start, n.end, n.pitch, n.velocity))
    return out
