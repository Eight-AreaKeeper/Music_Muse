"""整条流程：分轨 → 节拍 → 逐轨扒谱 → 出谱。中间结果缓存在输出目录里。"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import time
import zipfile
from typing import Callable

from . import beats as beats_mod
from .notes import Note, midi_to_notes, notes_to_midi
from .separate import separate
from .stems import STEM_ORDER, STEMS
from . import score as score_mod
from . import transcribe as tr

Progress = Callable[[float, str], None]


@dataclass
class Result:
    song_dir: Path
    stems_audio: dict[str, Path] = field(default_factory=dict)
    raw_midi: dict[str, Path] = field(default_factory=dict)
    scores: dict[str, dict[str, Path]] = field(default_factory=dict)
    note_counts: dict[str, int] = field(default_factory=dict)
    tempo: float = 0.0
    meter: str = ""
    beat_source: str = ""
    timings: dict[str, float] = field(default_factory=dict)


def slug(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_") or "song"


def run(input_path: str | Path, out_root: str | Path = "output",
        stems: list[str] | None = None, device: str = "cpu",
        progress: Progress | None = None) -> Result:
    input_path = Path(input_path)
    stems = [s for s in STEM_ORDER if stems is None or s in stems]
    song_dir = Path(out_root) / slug(input_path.stem)
    stem_dir, midi_dir, score_dir = (song_dir / d for d in ("stems", "midi", "scores"))
    for d in (stem_dir, midi_dir, score_dir):
        d.mkdir(parents=True, exist_ok=True)
    res = Result(song_dir)
    say = progress or (lambda p, m: print(f"[{p:4.0%}] {m}"))

    # 1. 分轨（已有缓存就跳过）
    t0 = time.time()
    cached = {s: stem_dir / f"{s}.wav" for s in STEMS}
    if all(p.exists() for p in cached.values()):
        say(0.05, "使用已缓存的分轨结果")
        res.stems_audio = cached
    else:
        say(0.0, "正在分轨（CPU 上较慢，请耐心等待）…")
        res.stems_audio = separate(input_path, stem_dir, device,
                                   progress=lambda f: say(0.5 * f, f"分轨中 {f:.0%}"))
    res.timings["分轨"] = time.time() - t0

    # 2. 节拍
    t0 = time.time()
    say(0.5, "正在检测节拍与小节线…")
    grid = beats_mod.detect(input_path, device)
    res.tempo, res.meter, res.beat_source = grid.tempo, f"{grid.beats_per_bar}/4", grid.source
    res.timings["节拍"] = time.time() - t0

    # 3. 逐轨扒谱
    stem_notes: dict[str, list[Note]] = {}
    for i, s in enumerate(stems):
        t0 = time.time()
        spec = STEMS[s]
        say(0.55 + 0.35 * i / len(stems), f"正在扒谱：{spec.label}")
        cache = midi_dir / f"{s}.mid"
        if cache.exists():
            import pretty_midi
            notes = midi_to_notes(pretty_midi.PrettyMIDI(str(cache)))
        else:
            notes = tr.transcribe(res.stems_audio[s], spec, device)
            notes_to_midi(notes, cache, spec.midi_program, spec.is_drum, spec.name, grid.tempo)
        stem_notes[s] = notes
        res.raw_midi[s] = cache
        res.note_counts[s] = len(notes)
        res.timings[f"扒谱-{spec.label}"] = time.time() - t0

    # 4. 出谱
    t0 = time.time()
    say(0.92, "正在生成乐谱…")
    res.scores = score_mod.make_scores(stem_notes, grid, score_dir, input_path.stem)
    res.timings["出谱"] = time.time() - t0

    (song_dir / "summary.json").write_text(json.dumps({
        "input": str(input_path), "tempo": round(res.tempo, 1), "meter": res.meter,
        "beat_source": res.beat_source, "note_counts": res.note_counts,
        "timings_sec": {k: round(v, 1) for k, v in res.timings.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    say(1.0, "完成")
    return res


def zip_result(res: Result) -> Path:
    """把乐谱和 MIDI 打成一个压缩包（不含体积很大的分轨 WAV）。"""
    path = res.song_dir.parent / f"{res.song_dir.name}_乐谱.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("scores", "midi"):
            for f in sorted((res.song_dir / sub).glob("*")):
                if f.suffix in (".musicxml", ".mid", ".pdf"):
                    z.write(f, f"{sub}/{f.name}")
        z.write(res.song_dir / "summary.json", "summary.json")
    return path
