#!/usr/bin/env python3
"""Extract keyframes from video files for Claude vision analysis."""

import argparse
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

FRAME_HEIGHT = 320
TIMESTAMP_BAR_HEIGHT = 24
COST_PER_TOKEN_USD = 3.0 / 1_000_000  # Claude Sonnet 4.x pricing
JPY_PER_USD = 150.0


def compute_frame_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """2フレーム間の平均ピクセル差分をパーセンテージで返す（0.0〜100.0）。"""
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY).astype(float)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY).astype(float)
    return (np.abs(gray1 - gray2).mean() / 255.0) * 100.0


def estimate_tokens(width: int, height: int) -> int:
    """Claude vision モデルのトークン数を近似する（pixels / 750）。"""
    return (width * height) // 750


def calculate_cost_jpy(tokens: int) -> float:
    """トークン数から推定コスト（円）を計算する。"""
    return tokens * COST_PER_TOKEN_USD * JPY_PER_USD


def extract_keyframes(
    cap: cv2.VideoCapture, threshold: float
) -> list[tuple[np.ndarray, float]]:
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    keyframes: list[tuple[np.ndarray, float]] = []
    prev_frame: np.ndarray | None = None
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / fps

        if prev_frame is None:
            keyframes.append((frame.copy(), timestamp))
            prev_frame = frame.copy()
        else:
            diff = compute_frame_diff(prev_frame, frame)
            if diff >= threshold:
                keyframes.append((frame.copy(), timestamp))
                prev_frame = frame.copy()

        frame_idx += 1

    return keyframes


def build_strip(
    keyframes: list[tuple[np.ndarray, float]], target_height: int = FRAME_HEIGHT
) -> Image.Image:
    pil_frames: list[Image.Image] = []

    for frame_bgr, timestamp in keyframes:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)

        w, h = img.size
        new_w = max(1, int(w * target_height / h))
        img = img.resize((new_w, target_height), Image.LANCZOS)

        canvas = Image.new(
            "RGB", (new_w, target_height + TIMESTAMP_BAR_HEIGHT), (30, 30, 30)
        )
        canvas.paste(img, (0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((4, target_height + 4), f"{timestamp:.2f}s", fill=(220, 220, 220))
        pil_frames.append(canvas)

    total_width = sum(f.width for f in pil_frames)
    strip_height = target_height + TIMESTAMP_BAR_HEIGHT
    strip = Image.new("RGB", (total_width, strip_height), (20, 20, 20))

    x = 0
    for frame_img in pil_frames:
        strip.paste(frame_img, (x, 0))
        x += frame_img.width

    return strip


def build_stats(
    output_path: str,
    keyframes: list[tuple[np.ndarray, float]],
    strip: Image.Image,
    vid_width: int,
    vid_height: int,
    total_frames: int,
    threshold: float,
) -> dict:
    output_size_kb = Path(output_path).stat().st_size // 1024
    strip_w, strip_h = strip.size
    keyframe_tokens = estimate_tokens(strip_w, strip_h)

    per_frame_tokens = estimate_tokens(vid_width, vid_height)
    all_frames_tokens = per_frame_tokens * total_frames

    return {
        "output_path": output_path,
        "frames_extracted": len(keyframes),
        "total_frames": total_frames,
        "timestamps": [round(ts, 2) for _, ts in keyframes],
        "file_size_kb": output_size_kb,
        "estimated_tokens": keyframe_tokens,
        "threshold_used": threshold,
        "cost_comparison": {
            "all_frames_png": {
                "size_kb": (vid_width * vid_height * 3 * total_frames) // 1024,
                "tokens": all_frames_tokens,
                "cost_jpy": round(calculate_cost_jpy(all_frames_tokens) * 3.5, 1),
            },
            "all_frames_jpeg": {
                "size_kb": (vid_width * vid_height * total_frames) // (1024 * 6),
                "tokens": all_frames_tokens,
                "cost_jpy": round(calculate_cost_jpy(all_frames_tokens), 1),
            },
            "keyframes_this_run": {
                "size_kb": output_size_kb,
                "tokens": keyframe_tokens,
                "cost_jpy": round(calculate_cost_jpy(keyframe_tokens), 1),
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract keyframes from video for Claude vision analysis"
    )
    parser.add_argument("video_path", nargs="?", default=None, help="MP4/GIF/MOV ファイルのパス")
    parser.add_argument("--format", choices=["jpeg", "png"], default="jpeg")
    parser.add_argument("--threshold", type=float, default=30.0)
    args = parser.parse_args()

    if args.video_path is None:
        print(json.dumps({"error": "no_path", "message": "video_path not specified"}))
        raise SystemExit(2)

    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        print(json.dumps({"error": f"Cannot open video: {args.video_path}"}))
        raise SystemExit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vid_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    keyframes = extract_keyframes(cap, args.threshold)
    cap.release()

    if not keyframes:
        print(json.dumps({"error": "No frames extracted. Try lowering --threshold."}))
        raise SystemExit(1)

    strip = build_strip(keyframes)

    suffix = ".jpg" if args.format == "jpeg" else ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, prefix="vfr_", delete=False) as f:
        output_path = f.name

    if args.format == "jpeg":
        strip.save(output_path, "JPEG", quality=85, optimize=True)
    else:
        strip.save(output_path, "PNG", optimize=True)

    stats = build_stats(
        output_path, keyframes, strip, vid_width, vid_height, total_frames, args.threshold
    )
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
