---
name: video-analyze
description: 分析本地视频：使用 ffmpeg 抽取关键帧，并使用阿里云百炼 Paraformer-v2 做语音转文字。抽帧需要 ffmpeg，语音转文字需要 ALIYUN_API_KEY 或 DASHSCOPE_API_KEY。
---

# 视频分析 Skill

## 当前状态

| 能力 | 实现方式 | 必需条件 |
| --- | --- | --- |
| 关键帧抽取 | 本地 `ffmpeg` / `ffprobe` | 已安装 ffmpeg |
| 语音转文字 | 阿里云百炼 / DashScope `paraformer-v2` | `ALIYUN_API_KEY` 或 `DASHSCOPE_API_KEY` |
| 本地 Whisper | 暂未实现 | 后续可选能力 |

如果未配置阿里云 ASR，命令仍会返回抽帧结果，并将 `audio_empty` 标记为 `true`。

## 代码流程

命令入口：

```bash
cd skills/video-analyze/scripts/video-analyzer
uv run va extract --file /path/to/video.mp4
```

执行流程：

```text
analyzer_cli.py
├── get_video_duration(video)
├── extract_keyframes(video)
│   ├── 调用 ffprobe 获取视频时长
│   ├── 按时长计算自适应抽帧数量
│   └── 调用 ffmpeg 保存 frame_XX_YYpct.jpg
└── transcribe_video(video)
    ├── 读取 ALIYUN_API_KEY 或 DASHSCOPE_API_KEY
    ├── 上传文件到阿里云临时 OSS
    ├── 提交 Paraformer-v2 转写任务
    └── 轮询任务结果并返回转写文本
```

## 阿里云配置

### 1. 获取 API Key

1. 打开阿里云百炼：<https://bailian.console.aliyun.com>
2. 进入 API Key 管理
3. 创建 `sk-xxx` 格式的 API Key

### 2. 开通 Paraformer-v2

1. 进入百炼模型广场
2. 搜索 `paraformer-v2`
3. 开通模型

### 3. 设置环境变量

macOS / Linux：

```bash
export ALIYUN_API_KEY="sk-xxx"
# 或
export DASHSCOPE_API_KEY="sk-xxx"
```

Windows PowerShell：

```powershell
$env:ALIYUN_API_KEY="sk-xxx"
# 或
$env:DASHSCOPE_API_KEY="sk-xxx"
```

## ffmpeg 配置

macOS：

```bash
brew install ffmpeg
```

Linux：

```bash
sudo apt install ffmpeg
```

Windows：

- 从 <https://www.gyan.dev/ffmpeg/builds/> 下载 ffmpeg
- 将 `ffmpeg.exe` 和 `ffprobe.exe` 加入 PATH

## 首次 Python 初始化

```bash
cd skills/video-analyze/scripts/video-analyzer
uv sync
```

分析器本身没有第三方 Python 包依赖，只使用 Python 标准库和系统 `ffmpeg`。

## 使用方式

### 抽帧 + 语音转文字

```bash
cd skills/video-analyze/scripts/video-analyzer
ALIYUN_API_KEY="sk-xxx" uv run va extract --file /path/to/video.mp4
```

### 指定输出目录

```bash
uv run va extract \
  --file /path/to/video.mp4 \
  --output-dir /tmp/my_video_frames
```

### 指定语言提示

```bash
uv run va extract --file /path/to/video.mp4 --language zh
uv run va extract --file /path/to/video.mp4 --language en
uv run va extract --file /path/to/video.mp4 --language auto
```

## 输出格式

```json
{
  "frames": [
    "/tmp/va_frames_xxx/frame_01_10pct.jpg",
    "/tmp/va_frames_xxx/frame_02_30pct.jpg"
  ],
  "transcript": "转写文本...",
  "duration": 45.2,
  "audio_empty": false
}
```

如果未配置 ASR 或 ASR 失败，抽帧仍会正常返回：

```json
{
  "frames": ["/tmp/va_frames_xxx/frame_01_10pct.jpg"],
  "transcript": "",
  "duration": 45.2,
  "audio_empty": true
}
```

## 关键帧抽取策略

| 视频时长 | 抽帧数量 |
| --- | --- |
| ≤15 秒 | 5 帧 |
| 15–60 秒 | 8 帧 |
| 1–3 分钟 | 8 帧 |
| 3–10 分钟 | 10 帧 |
| >10 分钟 | 12 帧 |

抽帧范围为视频时长的 10% 到 90%，用于尽量避开片头片尾噪声。

## Agent 使用流程

1. 执行 `va extract`。
2. 解析返回的 JSON。
3. 读取有代表性的关键帧图片。
4. 结合画面内容和转写文本理解视频。
5. 在 Agent 对话中生成平台对应的标题、描述、标签。
6. 发布前必须让用户确认。

## 故障排查

| 现象 | 原因 | 处理方式 |
| --- | --- | --- |
| `ffmpeg not found` | 未安装 ffmpeg 或 PATH 不正确 | 安装 ffmpeg，并确认 `ffmpeg -version` 可用 |
| `Aliyun API key not found` | 未设置环境变量 | 设置 `ALIYUN_API_KEY` 或 `DASHSCOPE_API_KEY` |
| `InvalidApiKey` | API Key 错误 | 到百炼控制台重新生成 Key |
| `Arrearage` / 模型未开通 | 账号欠费或未开通模型 | 开通 `paraformer-v2` 并检查阿里云账号状态 |
| ASR 超时 | 文件较长或网络问题 | 重试，或使用更短的视频文件 |

## 后续改进

后续可以增加本地 Whisper / faster-whisper provider：

```bash
VIDEO_ANALYZE_ASR=faster-whisper
VIDEO_ANALYZE_WHISPER_MODEL=small
```

当前 ASR 使用阿里云 Paraformer-v2。
