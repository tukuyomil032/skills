# video-frame-reader

A Claude Code skill that extracts keyframes from video files (MP4/GIF/MOV) and assembles them into a single horizontal strip image for Claude to analyze — cutting vision token costs by up to 95%.

## Why

Sending every frame of a 5-second video to Claude can cost ~¥250. By extracting only the frames where something actually changed, the same analysis costs ~¥0.5. This skill was built to make it practical to debug animation bugs, UI transitions, and other time-based visual behaviors that are impossible to convey with a static screenshot.

## How it works

1. Reads the video with OpenCV frame-by-frame
2. Detects keyframes using a **changed-pixel ratio**: counts the percentage of pixels that changed by more than 10 gray levels between consecutive frames — a metric that catches small, localized changes (progress bars, text updates) that a simple mean-diff would miss
3. If too many keyframes are found, uniformly subsamples down to `--max-frames` (default 20) to stay within image size limits
4. Composites keyframes into a timestamped horizontal strip and saves it to `/tmp/`
5. Emits a single JSON line to stdout with the output path, frame count, timestamps, and cost comparison

## Installation

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/tukuyomil032/skills.git
cd skills/video-frame-reader
uv tool install .
```

This installs `vfr-extract` as a global command.

## Usage

### As a Claude Code skill

Invoke with `/video-frame-reader` or the `/vfr` alias. If no path is given, Claude searches the current project for `.mp4`, `.gif`, and `.mov` files and lets you pick one.

```
/vfr [video_path] [--format jpeg|png] [--threshold FLOAT] [--max-frames N]
```

### As a CLI tool

```bash
# Basic usage (outputs JSON to stdout, progress to stderr)
vfr-extract path/to/video.mp4

# Lower threshold to catch subtle changes (e.g. installer progress bars)
vfr-extract path/to/video.mp4 --threshold 0.5

# Extract up to 30 keyframes in PNG format
vfr-extract path/to/video.mp4 --format png --max-frames 30
```

**Parameters**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `video_path` | optional | Path to MP4, GIF, or MOV. Omit to trigger auto-search in the skill. |
| `--format` | `jpeg` | Output format: `jpeg` (smaller) or `png` (lossless) |
| `--threshold` | `1.0` | % of pixels that must change (>10 gray levels) to qualify as a keyframe. Lower = more frames. |
| `--max-frames` | `20` | Maximum keyframes in the output strip. Excess frames are uniformly subsampled. |

**JSON output**

```json
{
  "output_path": "/tmp/vfr_abc123.jpg",
  "frames_extracted": 12,
  "total_frames": 900,
  "timestamps": [0.0, 1.23, 3.45, ...],
  "file_size_kb": 183,
  "estimated_tokens": 842,
  "threshold_used": 1.0,
  "subsampled_from": null,
  "cost_comparison": {
    "all_frames_png":   { "size_kb": 52000, "tokens": 108000, "cost_jpy": 170.0 },
    "all_frames_jpeg":  { "size_kb": 2900,  "tokens": 108000, "cost_jpy": 48.6 },
    "keyframes_this_run": { "size_kb": 183, "tokens": 842,    "cost_jpy": 0.4 }
  }
}
```

## Cost reference

Costs assume Claude Sonnet 4.6 at $3/MTok input, 1 USD = ¥150.

| Method | Tokens (5 s / 30 fps / 720p) | Est. cost |
|--------|------------------------------|-----------|
| All frames PNG | ~184,000 | ~¥250 |
| All frames JPEG | ~184,000 | ~¥83 |
| **Keyframes only (typical)** | ~1,200 | **~¥0.5** |

> [!NOTE]
> Actual costs vary by video content, resolution, and number of keyframes extracted. The `cost_comparison` field in the JSON output shows exact figures for each run.

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest tests/ -v
```

Tests cover `compute_frame_diff`, `subsample_keyframes`, `estimate_tokens`, and `calculate_cost_jpy`.

## Project structure

```
video-frame-reader/
├── scripts/
│   ├── extract_frames.py   # Core extraction logic + CLI entry point
│   └── find_video.sh       # Shell helper for fd-based file search
├── tests/
│   └── test_extract_frames.py
├── docs/
│   └── requirements.md
├── SKILL.md                # English skill definition (Claude Code)
├── SKILL.ja.md             # Japanese skill definition
└── pyproject.toml
```
