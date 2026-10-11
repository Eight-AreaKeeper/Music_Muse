"""音频读写。统一用 librosa / soundfile，Windows 上不需要单独装 ffmpeg 也能读 MP3。"""

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


def load(path: str | Path, sr: int, mono: bool) -> np.ndarray:
    """返回 float32 数组；立体声时形状为 (2, n)。"""
    y, _ = librosa.load(str(path), sr=sr, mono=mono)
    if not mono and y.ndim == 1:
        y = np.stack([y, y])
    return y.astype(np.float32)


def save(path: str | Path, y: np.ndarray, sr: int) -> None:
    data = y.T if y.ndim == 2 else y
    sf.write(str(path), data, sr, subtype="PCM_16")
