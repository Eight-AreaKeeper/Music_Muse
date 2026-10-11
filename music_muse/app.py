"""本地网页界面（Gradio）。启动后在浏览器打开 http://127.0.0.1:7860"""

from pathlib import Path

import gradio as gr

from .pipeline import run, zip_result
from .score import find_musescore
from .stems import STEM_ORDER, STEMS

OUT_ROOT = Path("output")


def process(audio_path, stems, progress=gr.Progress()):
    if not audio_path:
        raise gr.Error("请先上传一首歌")
    if not stems:
        raise gr.Error("至少选一个声部")
    res = run(audio_path, OUT_ROOT, stems, progress=lambda p, m: progress(p, desc=m))

    lines = [f"**速度** 约 {res.tempo:.0f} BPM　**拍号** {res.meter}　**节拍来源** {res.beat_source}", "",
             "| 声部 | 音符数 |", "| --- | --- |"]
    lines += [f"| {STEMS[s].label} | {n} |" for s, n in res.note_counts.items()]
    lines += ["", "**耗时**：" + "，".join(f"{k} {v:.0f} 秒" for k, v in res.timings.items())]
    if not find_musescore():
        lines += ["", "没找到 MuseScore，所以这次没有生成 PDF。装好 MuseScore 4 后重新处理即可，"
                      "也可以直接用 MuseScore 打开 .musicxml 文件。"]

    files = [str(zip_result(res))]
    for name in ["full_score", *res.note_counts]:
        files += [str(p) for p in res.scores.get(name, {}).values()]
    players = [gr.update(value=str(res.stems_audio[s]) if s in res.stems_audio else None,
                         visible=True) for s in STEM_ORDER]
    return ["\n".join(lines), files, *players]


def build() -> gr.Blocks:
    with gr.Blocks(title="Music_Muse") as demo:
        gr.Markdown("# Music_Muse\n上传一首歌，自动分轨，并为每个声部生成五线谱（MusicXML / MIDI / PDF）。")
        with gr.Row():
            with gr.Column(scale=1):
                audio_in = gr.Audio(label="歌曲文件", type="filepath", sources=["upload"])
                stems = gr.CheckboxGroup(label="要生成乐谱的声部",
                                         choices=[(STEMS[s].label, s) for s in STEM_ORDER],
                                         value=list(STEM_ORDER))
                go = gr.Button("开始处理", variant="primary")
            with gr.Column(scale=1):
                summary = gr.Markdown()
                files = gr.File(label="下载结果（压缩包包含全部文件）", file_count="multiple")
        gr.Markdown("### 分轨试听")
        players = []
        with gr.Row():
            for s in STEM_ORDER:
                players.append(gr.Audio(label=STEMS[s].label, interactive=False, visible=False))
        go.click(process, [audio_in, stems], [summary, files, *players])
    return demo


def launch(port: int = 7860, share: bool = False):
    OUT_ROOT.mkdir(exist_ok=True)
    build().queue().launch(server_name="127.0.0.1", server_port=port, share=share,
                           inbrowser=True, allowed_paths=[str(OUT_ROOT.resolve())])
