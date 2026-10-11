"""每个声部的显示名与扒谱参数。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StemSpec:
    name: str            # Demucs 输出的轨道名
    label: str           # 界面上显示的中文名
    music21_instrument: str
    midi_program: int    # General MIDI 音色（0 起）
    is_drum: bool = False
    monophonic: bool = False
    min_hz: float | None = None
    max_hz: float | None = None
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    min_note_ms: float = 80.0


STEMS: dict[str, StemSpec] = {
    "vocals": StemSpec("vocals", "人声", "Vocalist", 52, monophonic=True,
                       min_hz=80, max_hz=1100, onset_threshold=0.6, min_note_ms=100),
    "drums": StemSpec("drums", "鼓", "Percussion", 0, is_drum=True),
    "bass": StemSpec("bass", "贝斯", "ElectricBass", 33, monophonic=True,
                     min_hz=30, max_hz=400, onset_threshold=0.55, min_note_ms=90),
    "piano": StemSpec("piano", "钢琴", "Piano", 0),
    "guitar": StemSpec("guitar", "吉他", "ElectricGuitar", 27,
                       min_hz=75, max_hz=1400, onset_threshold=0.6),
    "other": StemSpec("other", "其他", "Piano", 0, onset_threshold=0.6, min_note_ms=100),
}

STEM_ORDER = ["vocals", "guitar", "piano", "other", "bass", "drums"]
