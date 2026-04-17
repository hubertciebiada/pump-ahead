"""Sanity checks for MODERN_BUNGALOW_LOOPS constant (issue #145).

The loop table is anonymized real-world installation data; these tests
verify aggregate invariants that would catch transcription errors.
"""

import pytest

from pumpahead.building_profiles import (
    MODERN_BUNGALOW_LOOPS,
    MODERN_BUNGALOW_ROOMS,
    modern_bungalow,
)


@pytest.mark.unit
class TestModernBungalowLoops:
    """Aggregate invariants for MODERN_BUNGALOW_LOOPS."""

    def test_exactly_13_loops(self) -> None:
        assert len(MODERN_BUNGALOW_LOOPS) == 13

    def test_total_power_in_expected_range(self) -> None:
        total_qh = sum(loop[0] for loop in MODERN_BUNGALOW_LOOPS)
        assert 4500.0 <= total_qh <= 4700.0, f"Q_total={total_qh} W outside 4500-4700"

    def test_total_length_in_expected_range(self) -> None:
        total_len = sum(loop[1] for loop in MODERN_BUNGALOW_LOOPS)
        # L_total = 411.4 m across the 13 loops in the anonymized PDF.
        assert 405.0 <= total_len <= 420.0, f"L_total={total_len} m outside 405-420"

    def test_exactly_one_loop_with_0_15_spacing(self) -> None:
        count = sum(1 for loop in MODERN_BUNGALOW_LOOPS if loop[2] == 0.15)
        assert count == 1, f"expected 1 loop with 0.15 m spacing, got {count}"

    def test_exactly_twelve_loops_with_0_20_spacing(self) -> None:
        count = sum(1 for loop in MODERN_BUNGALOW_LOOPS if loop[2] == 0.20)
        assert count == 12, f"expected 12 loops with 0.20 m spacing, got {count}"

    def test_largest_loop_is_at_least_1000_w(self) -> None:
        max_qh = max(loop[0] for loop in MODERN_BUNGALOW_LOOPS)
        assert max_qh >= 1000.0, f"largest loop Qh={max_qh} W, expected >= 1000"

    def test_loops_ordered_by_descending_qh(self) -> None:
        """Canonical order (required by issue #146)."""
        qh_values = [loop[0] for loop in MODERN_BUNGALOW_LOOPS]
        assert qh_values == sorted(qh_values, reverse=True)

    def test_all_rooms_have_pipe_length_m_set(self) -> None:
        """Each of the 13 rooms has pipe_length_m bound to a loop."""
        for room in MODERN_BUNGALOW_ROOMS:
            assert room.pipe_length_m is not None, f"{room.name} has no pipe_length_m"
            assert room.pipe_length_m > 0

    def test_all_rooms_have_no_pipe_spacing_m(self) -> None:
        """pipe_spacing_m must be None — XOR with pipe_length_m."""
        for room in MODERN_BUNGALOW_ROOMS:
            assert room.pipe_spacing_m is None, (
                f"{room.name} has both pipe_length_m and pipe_spacing_m"
            )

    def test_room_pipe_lengths_match_loop_table(self) -> None:
        """Every room's pipe_length_m appears in MODERN_BUNGALOW_LOOPS."""
        loop_lengths = {loop[1] for loop in MODERN_BUNGALOW_LOOPS}
        for room in MODERN_BUNGALOW_ROOMS:
            assert room.pipe_length_m in loop_lengths, (
                f"{room.name} pipe_length_m={room.pipe_length_m} not in loop table"
            )

    def test_hp_max_power_matches_anonymized_spec(self) -> None:
        """Real HP nominal output is 4.9 kW per issue #145."""
        building = modern_bungalow()
        assert building.hp_max_power_w == pytest.approx(4900.0)
