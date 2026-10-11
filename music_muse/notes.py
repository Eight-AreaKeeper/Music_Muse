"""各模块之间传递的统一音符格式。"""

from dataclasses import dataclass

import pretty_midi


@dataclass
class Note:
    start: float     # 秒
    end: float       # 秒
    pitch: int       # MIDI 音高；鼓轨里是 GM 打击乐编号
    velocity: int = 90


def notes_to_midi(notes: list[Note], path, program: int = 0, is_drum: bool = False,
                  name: str = "", tempo: float = 120.0) -> None:
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    inst = pretty_midi.Instrument(program=program, is_drum=is_drum, name=name)
    for n in notes:
        if n.end > n.start:
            inst.notes.append(pretty_midi.Note(n.velocity, n.pitch, n.start, n.end))
    pm.instruments.append(inst)
    pm.write(str(path))


def midi_to_notes(pm: pretty_midi.PrettyMIDI) -> list[Note]:
    return [Note(n.start, n.end, n.pitch, n.velocity)
            for inst in pm.instruments for n in inst.notes]
