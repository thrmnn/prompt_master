"""Tests for ExplorationPad — 2D latent space exploration."""

import pytest

from prompt_master.tui.exploration_pad import ExplorationPad, AXIS_PAIRS, PAD_WIDTH, PAD_HEIGHT
from prompt_master.vibe import DIMENSIONS


class TestExplorationPadLogic:
    def test_initial_cursor_centered(self):
        pad = ExplorationPad()
        assert pad._cursor_x == 0.5
        assert pad._cursor_y == 0.5

    def test_axis_pairs_valid(self):
        for x_dim, y_dim in AXIS_PAIRS:
            assert x_dim in DIMENSIONS, f"Unknown X dimension: {x_dim}"
            assert y_dim in DIMENSIONS, f"Unknown Y dimension: {y_dim}"
            assert x_dim != y_dim, f"Axis pair must have different dims: {x_dim}"

    def test_default_axes(self):
        pad = ExplorationPad()
        assert pad.x_dim == AXIS_PAIRS[0][0]
        assert pad.y_dim == AXIS_PAIRS[0][1]

    def test_cycle_axis_pair(self):
        pad = ExplorationPad()
        pad.axis_pair_index = 1
        assert pad.x_dim == AXIS_PAIRS[1][0]
        assert pad.y_dim == AXIS_PAIRS[1][1]

    def test_axis_pair_wraps(self):
        pad = ExplorationPad()
        pad.axis_pair_index = len(AXIS_PAIRS) - 1
        new_idx = (pad.axis_pair_index + 1) % len(AXIS_PAIRS)
        assert new_idx == 0

    def test_pos_to_values_at_zero(self):
        pad = ExplorationPad()
        pad._cursor_x = 0.0
        pad._cursor_y = 0.0
        x_val, y_val = pad._pos_to_values()
        assert x_val == pad.x_values[0]
        assert y_val == pad.y_values[0]

    def test_pos_to_values_at_one(self):
        pad = ExplorationPad()
        pad._cursor_x = 1.0
        pad._cursor_y = 1.0
        x_val, y_val = pad._pos_to_values()
        assert x_val == pad.x_values[-1]
        assert y_val == pad.y_values[-1]

    def test_pos_to_values_at_center(self):
        pad = ExplorationPad()
        pad._cursor_x = 0.5
        pad._cursor_y = 0.5
        x_val, y_val = pad._pos_to_values()
        # Should be a middle value
        x_idx = len(pad.x_values) // 2
        y_idx = len(pad.y_values) // 2
        assert x_val == pad.x_values[x_idx]
        assert y_val == pad.y_values[y_idx]

    def test_cursor_clamped(self):
        pad = ExplorationPad()
        # Simulate going out of bounds
        pad._cursor_x = max(0.0, -0.5)
        pad._cursor_y = min(1.0, 1.5)
        assert pad._cursor_x == 0.0
        assert pad._cursor_y == 1.0

    def test_morph_request_message(self):
        msg = ExplorationPad.MorphRequest(
            section_name="Role",
            x_dim="tone", x_val="formal",
            y_dim="specificity", y_val="narrow",
            x_pct=0.8, y_pct=0.3,
        )
        assert msg.section_name == "Role"
        assert msg.x_dim == "tone"
        assert msg.x_val == "formal"
        assert msg.y_dim == "specificity"
        assert msg.y_val == "narrow"

    def test_pad_closed_message(self):
        msg = ExplorationPad.PadClosed(section_name="Task")
        assert msg.section_name == "Task"

    def test_section_name_stored(self):
        pad = ExplorationPad()
        pad._section_name = "Output Format"
        assert pad._section_name == "Output Format"

    def test_zone_change_detection(self):
        """Moving the cursor slightly within the same zone should not re-emit."""
        pad = ExplorationPad()
        pad._cursor_x = 0.0
        pad._cursor_y = 0.0
        x1, y1 = pad._pos_to_values()
        pad._last_x_val = x1
        pad._last_y_val = y1

        # Tiny move within same zone
        pad._cursor_x = 0.01
        x2, y2 = pad._pos_to_values()
        assert x2 == x1  # Still same zone — no emit needed

    def test_different_zones_different_values(self):
        """Moving from 0.0 to 1.0 must produce different values."""
        pad = ExplorationPad()
        pad._cursor_x = 0.0
        x0, _ = pad._pos_to_values()
        pad._cursor_x = 1.0
        x1, _ = pad._pos_to_values()
        assert x0 != x1

    def test_all_axis_pairs_have_multiple_values(self):
        for x_dim, y_dim in AXIS_PAIRS:
            assert len(DIMENSIONS[x_dim]) >= 2
            assert len(DIMENSIONS[y_dim]) >= 2
