"""提前下载所有模型权重（约 1 GB），之后处理歌曲就不需要再联网。"""


def main() -> None:
    print("1/3 下载分轨模型 Demucs htdemucs_6s …")
    from demucs.pretrained import get_model
    get_model("htdemucs_6s")

    print("2/3 下载节拍模型 Beat This! …")
    from beat_this.inference import load_checkpoint
    load_checkpoint("final0")

    print("3/3 下载钢琴扒谱模型（约 165 MB）…")
    from .transcribe import ensure_piano_checkpoint
    print("    保存在", ensure_piano_checkpoint())

    print("模型已全部就绪。Basic Pitch 的模型随安装包自带，不用下载。")

    from .score import find_musescore
    exe = find_musescore()
    if exe:
        print("找到 MuseScore：", exe)
    else:
        print("没找到 MuseScore 4：能生成 MusicXML 和 MIDI，但没有 PDF。"
              "可到 https://musescore.org 免费下载，装好后无需重装本工具。")


if __name__ == "__main__":
    main()
