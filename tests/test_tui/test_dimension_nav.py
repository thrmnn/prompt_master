"""Tests for DimensionNavigator — cursor-driven state space exploration."""

import pytest

from prompt_master.tui.dimension_nav import DimensionNavigator, DIM_ORDER
from prompt_master.vibe import DIMENSIONS


class TestDimensionNavigatorLogic:
    def test_initial_state(self):
        nav = DimensionNavigator()
        assert nav.active_dim_index == 0
        assert nav.current_dimension == DIM_ORDER[0]

    def test_dim_order_matches_dimensions(self):
        for dim in DIM_ORDER:
            assert dim in DIMENSIONS

    def test_current_value_starts_at_first(self):
        nav = DimensionNavigator()
        dim = nav.current_dimension
        assert nav.current_value == DIMENSIONS[dim][0]

    def test_cycle_dimension_right(self):
        nav = DimensionNavigator()
        nav.active_dim_index = 0
        nav.active_dim_index = (nav.active_dim_index + 1) % len(DIM_ORDER)
        assert nav.current_dimension == DIM_ORDER[1]

    def test_cycle_dimension_wraps(self):
        nav = DimensionNavigator()
        nav.active_dim_index = len(DIM_ORDER) - 1
        nav.active_dim_index = (nav.active_dim_index + 1) % len(DIM_ORDER)
        assert nav.active_dim_index == 0

    def test_cycle_value_up(self):
        nav = DimensionNavigator()
        dim = nav.current_dimension
        nav._dim_values[dim] = 0
        nav._dim_values[dim] = (nav._dim_values[dim] + 1) % len(DIMENSIONS[dim])
        assert nav.current_value == DIMENSIONS[dim][1]

    def test_cycle_value_wraps(self):
        nav = DimensionNavigator()
        dim = nav.current_dimension
        values = DIMENSIONS[dim]
        nav._dim_values[dim] = len(values) - 1
        nav._dim_values[dim] = (nav._dim_values[dim] + 1) % len(values)
        assert nav._dim_values[dim] == 0

    def test_get_all_values(self):
        nav = DimensionNavigator()
        vals = nav.get_all_values()
        assert len(vals) == len(DIM_ORDER)
        for dim in DIM_ORDER:
            assert dim in vals
            assert vals[dim] in DIMENSIONS[dim]

    def test_section_name_set(self):
        nav = DimensionNavigator()
        nav._section_name = "Task"
        assert nav._section_name == "Task"

    def test_messages(self):
        msg = DimensionNavigator.DimensionChanged(
            section_name="Role", dimension="tone", value="formal"
        )
        assert msg.section_name == "Role"
        assert msg.dimension == "tone"
        assert msg.value == "formal"

        closed = DimensionNavigator.NavigatorClosed(section_name="Task")
        assert closed.section_name == "Task"

    def test_all_dimensions_navigable(self):
        """Every dimension in DIM_ORDER has at least 2 values to cycle through."""
        for dim in DIM_ORDER:
            assert len(DIMENSIONS[dim]) >= 2, f"Dimension {dim} needs >=2 values"
