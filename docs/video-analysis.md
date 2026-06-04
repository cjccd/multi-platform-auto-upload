# Video Analysis Add-on

Video analysis is optional. It is not required for the main publishing workflow.

`skills/video-analyze` can turn a video into structured material for agents:

- extract keyframes with `ffmpeg/ffprobe`
- transcribe speech with Aliyun Bailian `paraformer-v2`
- output JSON for downstream reasoning

## Setup

```bash
cd skills/video-analyze/scripts/video-analyzer
uv sync
```

Install ffmpeg:

```bash
brew install ffmpeg
```

Set ASR key:

```bash
export ALIYUN_API_KEY="sk-xxx"
```

## Run

```bash
uv run va extract --file /path/to/video.mp4
```

Example output:

```json
{
  "frames": ["/tmp/va_frames_xxx/frame_01_10pct.jpg"],
  "transcript": "transcribed speech...",
  "duration": 45.2,
  "audio_empty": false
}
```

If no ASR key is configured, keyframe extraction still works and the transcript will be empty.
