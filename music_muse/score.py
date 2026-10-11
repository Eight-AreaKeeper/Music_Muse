"""把音符按节拍网格量化，生成 MusicXML / MIDI，有 MuseScore 时再出 PDF。"""

from collections import defaultdict
import copy
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from music21 import (clef, chord, instrument, key, layout, meter, note, percussion,
                     stream, tempo)

from .beats import BeatGrid
from .notes import Note
from .stems import STEMS, StemSpec
from .transcribe import HIHAT, KICK, SNARE

SUBDIV = 4          # 每拍分 4 格，即最小到十六分音符
MAX_CHORD = 6
DRUM_DISPLAY = {KICK: "F4", SNARE: "C5", HIHAT: "G5"}


class Grid:
    """时间（秒）↔ 网格格数 的换算；第 0 格是第一个音之前最近的小节线。"""

    def __init__(self, beats: BeatGrid, first_note: float, last_note: float):
        b = list(beats.beats)
        step = float(np.median(np.diff(b))) if len(b) > 1 else 0.5
        d0 = beats.downbeats[0] if len(beats.downbeats) else b[0]
        i0 = int(np.argmin(np.abs(np.asarray(b) - d0)))
        # 往前补拍子，让第 0 格落在小节线上并且早于第一个音
        while b[0] > first_note - 1e-3 or i0 % beats.beats_per_bar:
            b.insert(0, b[0] - step)
            i0 += 1
        b = b[i0 % beats.beats_per_bar:]
        while b[-1] < last_note + step:
            b.append(b[-1] + step)
        times = []
        for t0, t1 in zip(b[:-1], b[1:]):
            times.extend(np.linspace(t0, t1, SUBDIV, endpoint=False))
        times.append(b[-1])
        self.times = np.asarray(times)

    def index(self, t: float) -> int:
        return int(round(float(np.interp(t, self.times, np.arange(len(self.times))))))


def quantize(notes: list[Note], grid: Grid) -> dict[int, list[tuple[int, int, int]]]:
    """返回 {起始格: [(音高, 时值格数, 力度), ...]}。"""
    events: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    for n in notes:
        s = grid.index(n.start)
        e = max(s + 1, grid.index(n.end))
        events[s].append((n.pitch, e - s, n.velocity))
    return events


def to_chords(events) -> list[tuple[int, int, list[tuple[int, int]]]]:
    """同一时刻起的音合成和弦，时值截到下一个起音处，得到单声部的和弦序列。"""
    onsets = sorted(events)
    out = []
    for i, s in enumerate(onsets):
        group = sorted(events[s], key=lambda x: -x[2])[:MAX_CHORD]
        dur = max(d for _, d, _ in group)
        if i + 1 < len(onsets):
            dur = min(dur, onsets[i + 1] - s)
        pitches = {}
        for p, _, v in group:
            pitches[p] = max(v, pitches.get(p, 0))
        out.append((s, max(1, dur), sorted(pitches.items())))
    return out


def _new_part(spec: StemSpec, part_cls=stream.Part, name: str | None = None,
              part_id: str | None = None):
    part = part_cls()
    part.id = part_id or spec.name  # MIDI 轨道名只能用 ASCII，导出 MIDI 时用它
    inst = getattr(instrument, spec.music21_instrument)()
    inst.partName = name or spec.label
    inst.partAbbreviation = name or spec.label
    part.insert(0, inst)
    part.partName = name or spec.label
    return part


def _fill(part, chords, is_drum=False):
    for s, dur, pitches in chords:
        ql = dur / SUBDIV
        if is_drum:
            parts = []
            for p, v in pitches:
                u = note.Unpitched(displayName=DRUM_DISPLAY.get(p, "C5"))
                if p == HIHAT:
                    u.notehead = "x"
                u.volume.velocity = v
                parts.append(u)
            el = parts[0] if len(parts) == 1 else percussion.PercussionChord(parts)
        elif len(pitches) == 1:
            el = note.Note(pitches[0][0])
            el.volume.velocity = pitches[0][1]
        else:
            el = chord.Chord([p for p, _ in pitches])
            el.volume.velocity = max(v for _, v in pitches)
        el.quarterLength = ql
        part.insert(s / SUBDIV, el)


def _finish(part, ts, ks, mm, the_clef):
    part.insert(0, the_clef)
    part.insert(0, meter.TimeSignature(ts))
    if ks is not None:
        part.insert(0, key.KeySignature(ks.sharps))
    if mm is not None:
        part.insert(0, mm)
    part.makeRests(fillGaps=True, inPlace=True, timeRangeFromBarDuration=True)
    part.makeNotation(inPlace=True)
    return part


def build_parts(stem: str, notes: list[Note], grid: Grid, ts: str, ks, mm) -> list:
    spec = STEMS[stem]
    if spec.is_drum:
        part = _new_part(spec)
        _fill(part, to_chords(quantize(notes, grid)), is_drum=True)
        return [_finish(part, ts, None, mm, clef.PercussionClef())]
    if stem == "piano":
        rh = _new_part(spec, stream.PartStaff, "钢琴", "piano_rh")
        lh = _new_part(spec, stream.PartStaff, "钢琴", "piano_lh")
        _fill(rh, to_chords(quantize([n for n in notes if n.pitch >= 60], grid)))
        _fill(lh, to_chords(quantize([n for n in notes if n.pitch < 60], grid)))
        return [_finish(rh, ts, ks, mm, clef.TrebleClef()),
                _finish(lh, ts, ks, None, clef.BassClef())]
    part = _new_part(spec)
    _fill(part, to_chords(quantize(notes, grid)))
    pitches = [n.pitch for n in notes]
    the_clef = clef.BassClef() if pitches and np.median(pitches) < 55 else clef.TrebleClef()
    return [_finish(part, ts, ks, mm, the_clef)]


def detect_key(all_notes: list[Note]):
    pitched = stream.Stream()
    for n in all_notes:
        x = note.Note(n.pitch)
        x.quarterLength = max(0.25, min(4.0, (n.end - n.start) * 2))
        pitched.append(x)
    if len(pitched) < 8:
        return None
    try:
        return pitched.analyze("key")
    except Exception:
        return None


def make_scores(stem_notes: dict[str, list[Note]], beats: BeatGrid, out_dir: Path,
                title: str) -> dict[str, dict[str, Path]]:
    """为每个声部和总谱写出 MusicXML 与 MIDI，返回 {名字: {格式: 路径}}。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    all_notes = [n for ns in stem_notes.values() for n in ns]
    if not all_notes:
        return {}
    grid = Grid(beats, min(n.start for n in all_notes), max(n.end for n in all_notes))
    ts = f"{beats.beats_per_bar}/4"
    pitched = [n for s, ns in stem_notes.items() if not STEMS[s].is_drum for n in ns]
    ks = detect_key(pitched)
    bpm = round(beats.tempo)

    results: dict[str, dict[str, Path]] = {}
    full = stream.Score()
    for stem, ns in stem_notes.items():
        if not ns:
            continue
        parts = build_parts(stem, ns, grid, ts, ks, tempo.MetronomeMark(number=bpm))
        single = stream.Score()
        _set_title(single, f"{title} - {STEMS[stem].label}")
        for p in parts:
            single.insert(0, p)
        if stem == "piano":
            single.insert(0, layout.StaffGroup(parts, symbol="brace", barTogether=True))
        results[stem] = _write(single, out_dir / stem)
        for p in build_parts(stem, ns, grid, ts, ks, tempo.MetronomeMark(number=bpm)):
            full.insert(0, p)
    _set_title(full, title)
    results["full_score"] = _write(full, out_dir / "full_score")
    return results


def _set_title(score, title):
    from music21 import metadata
    score.metadata = metadata.Metadata()
    score.metadata.title = title
    score.metadata.composer = "Music_Muse 自动扒谱"


def _write(score, base: Path) -> dict[str, Path]:
    out = {}
    xml = base.with_suffix(".musicxml")
    score.write("musicxml", fp=str(xml))
    out["musicxml"] = xml
    mid = base.with_suffix(".mid")
    ascii_copy = copy.deepcopy(score)
    for part in ascii_copy.parts:
        for inst in part.recurse().getElementsByClass(instrument.Instrument):
            inst.partName = inst.partAbbreviation = inst.instrumentName = str(part.id)
    ascii_copy.metadata.title = base.stem
    ascii_copy.metadata.composer = "Music_Muse"
    ascii_copy.write("midi", fp=str(mid))
    out["midi"] = mid
    pdf = render_pdf(xml)
    if pdf:
        out["pdf"] = pdf
    return out


def find_musescore() -> str | None:
    env = os.environ.get("MUSESCORE_PATH")
    if env and Path(env).exists():
        return env
    for name in ("MuseScore4", "mscore4portable", "mscore", "musescore", "MuseScore3"):
        found = shutil.which(name)
        if found:
            return found
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        for rel in (r"MuseScore 4\bin\MuseScore4.exe", r"MuseScore 3\bin\MuseScore3.exe"):
            p = Path(base) / rel
            if p.exists():
                return str(p)
    return None


def render_pdf(xml: Path) -> Path | None:
    exe = find_musescore()
    if not exe:
        return None
    pdf = xml.with_suffix(".pdf")
    try:
        subprocess.run([exe, "-o", str(pdf), str(xml)], check=True, timeout=300,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.SubprocessError, OSError):
        return None
    return pdf if pdf.exists() else None
