---
description: Extract keyframes from MP4/GIF/MOV video files into a single strip image for Claude to analyze. Use when the user shares a video file and wants to understand animation behavior, UI transitions, or visual bugs that are hard to describe with static screenshots.
---

# video-frame-reader

Extract keyframes from video files (MP4/GIF/MOV) to analyze animations and UI behavior without reading every frame.

## When to Use

- Animation timing or visual progression is hard to describe in text
- UI transition bugs that static screenshots can't capture
- Sequential state changes: lyrics highlight, auto-scroll, modal transitions

## Syntax

```
/video-frame-reader [video_path] [--format jpeg|png] [--threshold 10-90]
/vfr [video_path] [--format jpeg|png] [--threshold 10-90]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `video_path` | optional | Path to MP4, GIF, or MOV. **Omit to auto-search.** |
| `--format` | `jpeg` | `jpeg` (smaller/lossy) or `png` (lossless) |
| `--threshold` | `30` | Pixel diff % to qualify as a keyframe (lower = more frames) |

## Instructions for Claude

### Step 0 — If no video_path given, search for files

Run:

```bash
fd -e mp4 -e gif -e mov . 2>/dev/null | sort -u | python3 -c "
import sys, json
files = [l.strip() for l in sys.stdin if l.strip()]
print(json.dumps({'files': files, 'count': len(files)}))
"
```

Parse `{"files": [...], "count": N}`. If `count` is 0, tell the user no video files were found and stop. Otherwise present as a numbered list and wait for the user to pick one.

### Step 1 — Run extraction script

```bash
vfr-extract <video_path> [--format jpeg] [--threshold 30]
```

If `vfr-extract` is not found, tell the user to run `uv tool install .` from the video-frame-reader project directory first.

Capture the single JSON line from stdout.

### Step 2 — Parse JSON output

Key fields:
- `output_path` — generated strip image path
- `frames_extracted` — number of keyframes
- `timestamps` — seconds of each frame
- `cost_comparison` — cost breakdown

### Step 3 — Read the image

Use the Read tool to load `output_path`. This injects the strip into the conversation.

### Step 4 — Analyze frame by frame

Describe left to right:
- What changed between each frame
- Notable transitions, glitches, or unexpected states

### Step 5 — Show cost comparison table

```markdown
| Method | Size | Tokens | Est. Cost |
|--------|------|--------|-----------|
| All frames PNG  | XXX KB | X,XXX | XX¥ |
| All frames JPEG | XXX KB | X,XXX | XX¥ |
| **Keyframes (this run)** | XXX KB | X,XXX | **XX¥** |
```
