import numpy as np
import pytest
from PIL import Image

# これらは Task3 で実装するため、まだ ImportError が出る（RED 状態）
from scripts.extract_frames import (
    compute_frame_diff,
    estimate_tokens,
    calculate_cost_jpy,
)


class TestComputeFrameDiff:
    def test_identical_frames_returns_zero(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        assert compute_frame_diff(frame, frame) == pytest.approx(0.0)

    def test_opposite_frames_returns_100(self):
        black = np.zeros((100, 100, 3), dtype=np.uint8)
        white = np.full((100, 100, 3), 255, dtype=np.uint8)
        assert compute_frame_diff(black, white) == pytest.approx(100.0, abs=1.0)

    def test_half_diff_frames(self):
        frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
        frame2 = np.full((100, 100, 3), 128, dtype=np.uint8)
        diff = compute_frame_diff(frame1, frame2)
        assert 48.0 <= diff <= 52.0


class TestEstimateTokens:
    def test_standard_resolution(self):
        # 1280x720 → 921,600 / 750 = 1,228 tokens
        tokens = estimate_tokens(1280, 720)
        assert tokens == 1228

    def test_small_resolution(self):
        tokens = estimate_tokens(320, 240)
        assert tokens == 102  # 76,800 / 750

    def test_zero_returns_zero(self):
        assert estimate_tokens(0, 0) == 0


class TestCalculateCostJpy:
    def test_zero_tokens_returns_zero(self):
        assert calculate_cost_jpy(0) == 0.0

    def test_one_million_tokens_cost(self):
        # 1M tokens × $3/MTok × 150 JPY/USD = 450 JPY
        cost = calculate_cost_jpy(1_000_000)
        assert cost == pytest.approx(450.0, rel=0.01)

    def test_small_token_count(self):
        # 1,228 tokens × $3/MTok × 150 = ~0.55 JPY
        cost = calculate_cost_jpy(1228)
        assert cost == pytest.approx(0.553, abs=0.01)
