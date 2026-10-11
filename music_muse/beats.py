"""节拍与小节线检测：Beat This!，失败时退回 librosa。"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import audio


@dataclass
class BeatGrid:
    beats: np.ndarray        # 每一拍的时间（秒）
    downbeats: np.ndarray    # 每小节第一拍的时间（秒）
    beats_per_bar: int
    source: str

    @property
    def tempo(self) -> float:
        if len(self.beats) < 2:
            return 120.0
        return float(60.0 / np.median(np.diff(self.beats)))


def detect(path: Path, device: str = "cpu") -> BeatGrid:
    sr = 22050
    y = audio.load(path, sr=sr, mono=True)
    try:
        from beat_this.inference import Audio2Beats

        beats, downbeats = Audio2Beats(checkpoint_path="final0", device=device)(y, sr)
        beats, downbeats, source = np.asarray(beats), np.asarray(downbeats), "Beat This!"
    except Exception as exc:  # 模型下载失败等情况
        import librosa

        _, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        beats, downbeats, source = beats, beats[::4], f"librosa（Beat This! 不可用：{exc}）"

    if len(beats) < 4:
        beats = np.arange(0, len(y) / sr, 0.5)
        downbeats = beats[::4]
    return BeatGrid(beats, downbeats, estimate_meter(beats, downbeats), source)


def estimate_meter(beats: np.ndarray, downbeats: np.ndarray) -> int:
    if len(downbeats) < 2:
        return 4
    idx = np.searchsorted(beats, downbeats)
    counts = np.diff(idx)
    counts = counts[(counts >= 2) & (counts <= 7)]
    if len(counts) == 0:
        return 4
    return int(np.bincount(counts).argmax())
