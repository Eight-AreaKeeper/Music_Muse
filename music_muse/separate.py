"""分轨：Demucs htdemucs_6s，输出 人声 / 鼓 / 贝斯 / 钢琴 / 吉他 / 其他 六条音轨。"""

from pathlib import Path
from typing import Callable

import torch

from . import audio

MODEL = "htdemucs_6s"


def separate(input_path: Path, out_dir: Path, device: str = "cpu",
             progress: Callable[[float], None] | None = None) -> dict[str, Path]:
    from demucs.api import Separator

    out_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(max(1, torch.get_num_threads()))

    def on_chunk(info: dict) -> None:
        if progress and info["state"] == "end":
            done = info["segment_offset"] / max(1, info["audio_length"])
            progress(min(1.0, done))

    sep = Separator(model=MODEL, device=device, shifts=0, overlap=0.25,
                    callback=on_chunk if progress else None)
    wav = torch.from_numpy(audio.load(input_path, sr=sep.samplerate, mono=False))
    _, stems = sep.separate_tensor(wav, sep.samplerate)

    paths = {}
    for name, tensor in stems.items():
        p = out_dir / f"{name}.wav"
        audio.save(p, tensor.cpu().numpy(), sep.samplerate)
        paths[name] = p
    return paths
