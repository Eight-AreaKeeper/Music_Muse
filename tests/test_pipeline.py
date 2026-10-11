"""用合成歌曲跑整条流程。分轨用合成时保存的分轨代替（不需要下载 Demucs 权重）。"""

from pathlib import Path
import shutil

from music21 import converter

import numpy as np

from music_muse import beats, pipeline, transcribe
from music_muse.notes import Note
from tests.synth import BASS, BEAT, LEAD, MELODY, write_song


def test_pipeline_on_synthetic_song(tmp_path, monkeypatch):
    src = write_song(tmp_path / "src")
    song_dir = tmp_path / "out" / "mix" / "stems"
    song_dir.mkdir(parents=True)
    for k in ("vocals", "bass", "piano", "drums", "guitar", "other"):
        shutil.copy(src[k], song_dir / f"{k}.wav")

    # 钢琴模型权重在没联网的环境里下载不了，测试时用 Basic Pitch 代替
    real = transcribe.transcribe
    def fake(path, spec, device="cpu"):
        if spec.name == "piano":
            return transcribe.transcribe_basic_pitch(path, spec)
        return real(path, spec, device)
    monkeypatch.setattr(transcribe, "transcribe", fake)

    # Beat This! 的权重同样下载不了；这里给出真实节拍，单独检验量化和出谱
    true_beats = LEAD + np.arange(32) * BEAT
    monkeypatch.setattr(beats, "detect", lambda path, device="cpu": beats.BeatGrid(
        true_beats, true_beats[::4], 4, "test"))

    res = pipeline.run(src["mix"], tmp_path / "out")

    assert 110 <= res.tempo <= 130
    assert res.meter == "4/4"
    assert res.note_counts["guitar"] == 0 and res.note_counts["other"] == 0
    assert "full_score" in res.scores

    vocal = converter.parse(res.scores["vocals"]["musicxml"])
    got = [n.pitch.midi for n in vocal.recurse().notes]
    want = [p for _, _, p in MELODY] * 2
    assert got == want, (got, want)

    bass = converter.parse(res.scores["bass"]["musicxml"])
    bass_pitches = [n.pitch.midi for n in bass.recurse().notes]
    assert len(bass_pitches) >= 0.8 * 2 * len(BASS)

    drums = res.note_counts["drums"]
    assert 64 <= drums <= 96
