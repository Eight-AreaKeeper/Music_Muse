"""命令行入口：  music-muse run 歌曲.mp3   /   music-muse web"""

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(add_completion=False, help="Music_Muse：分轨并生成各轨五线谱")


@app.command()
def run(audio: Path = typer.Argument(..., exists=True, help="要处理的音频文件"),
        out: Path = typer.Option(Path("output"), "--out", "-o", help="输出目录"),
        stems: Optional[str] = typer.Option(None, help="只处理这些声部，逗号分隔，如 vocals,bass")):
    """处理一首歌：分轨、扒谱、出谱。"""
    from .pipeline import run as run_pipeline

    res = run_pipeline(audio, out, stems.split(",") if stems else None)
    typer.echo(f"\n速度约 {res.tempo:.0f} BPM，拍号 {res.meter}（节拍来源：{res.beat_source}）")
    for s, n in res.note_counts.items():
        typer.echo(f"  {s:7s} {n:5d} 个音符")
    typer.echo("耗时：" + "，".join(f"{k} {v:.0f}s" for k, v in res.timings.items()))
    typer.echo(f"结果在：{res.song_dir.resolve()}")


@app.command()
def web(port: int = 7860, share: bool = False):
    """打开本地网页界面。"""
    from .app import launch

    launch(port=port, share=share)


if __name__ == "__main__":
    app()
