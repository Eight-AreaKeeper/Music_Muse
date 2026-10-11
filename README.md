# Music_Muse

把一首完整的歌自动分成 人声 / 鼓 / 贝斯 / 钢琴 / 吉他 / 其他 六轨，并为每一轨生成五线谱（MusicXML、MIDI，装了 MuseScore 4 还会出 PDF）。全部在本机 CPU 上运行。

## 安装（Windows）

1. 双击 `install.bat`。它会装好 uv、Python 3.10、所有依赖，并下载约 1 GB 的模型。
2. （可选）安装 [MuseScore 4](https://musescore.org)，用来生成 PDF，也可以用它打开和修改生成的乐谱。

## 使用

- 网页界面：双击 `start.bat`，浏览器会打开 http://127.0.0.1:7860 ，上传歌曲后点“开始处理”。
- 命令行：`.venv\Scripts\python -m music_muse run 歌曲.mp3`

结果在 `output\<歌名>\`：

| 目录 | 内容 |
| --- | --- |
| `stems\` | 分轨后的音频（WAV） |
| `midi\` | 每轨未量化的原始 MIDI |
| `scores\` | 每轨及总谱的 MusicXML / MIDI / PDF |
| `summary.json` | 速度、拍号、各轨音符数、各步耗时 |

同一首歌第二次处理会直接复用已有的分轨和 MIDI；想重新跑就删掉对应目录。

## 流程

分轨（Demucs htdemucs_6s）→ 节拍（Beat This!）→ 扒谱（钢琴：ByteDance piano_transcription；鼓：起音检测粗分；其他：Spotify Basic Pitch）→ 按节拍量化到十六分音符（music21）→ 出谱（MuseScore）。

## 当前限制（M0）

- 鼓只粗分底鼓、军鼓、踩镲，M2 会换成 ADTOF。
- 只针对 4/4 拍、速度稳定的流行 / 乐队歌曲。
- 同一声部里同时开始的音合成一个和弦，复杂的多声部写法会被简化。
- 支持 MP3 / WAV / FLAC / OGG；M4A 需要另装 ffmpeg。

## 开发

`.venv\Scripts\python -m pytest`：用合成歌曲测试扒谱和出谱（不需要下载模型）。
