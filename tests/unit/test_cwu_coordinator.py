"""Unit tests for CWUCoordinator.

Tests cover schedule constants, anti-panic split blocking,
pre-charge valve boosting, and edge cases.
"""

from __future__ import annotations

import pytest

from pumpahead.config import ControllerConfig, CWUCycle
from pumpahead.cwu_coordinator import (
    CWU_HEAVY,
    CWU_STANDARD,
    CWU_WORST_CASE,
    CWUCoordinator,
)


# ---------------------------------------------------------------------------
# TestCWUScheduleConstants
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCWUScheduleConstants:
    """Tests for predefined CWU schedule constants."""

    def test_cwu_standard_is_tuple(self) -> None:
        """CWU_STANDARD is a non-empty tuple of CWUCycle."""
        assert isinstance(CWU_STANDARD, tuple)
        assert len(CWU_STANDARD) == 1
        assert isinstance(CWU_STANDARD[0], CWUCycle)

    def test_cwu_standard_values(self) -> None:
        """CWU_STANDARD: 30 min every 8 hours."""
        cycle = CWU_STANDARD[0]
        assert cycle.start_minute == 0
        assert cycle.duration_minutes == 30
        assert cycle.interval_minutes == 480

    def test_cwu_heavy_is_tuple(self) -> None:
        """CWU_HEAVY is a non-empty tuple of CWUCycle."""
        assert isinstance(CWU_HEAVY, tuple)
        assert len(CWU_HEAVY) == 1
        assert isinstance(CWU_HEAVY[0], CWUCycle)

    def test_cwu_heavy_values(self) -> None:
        """CWU_HEAVY: 45 min every 3 hours."""
        cycle = CWU_HEAVY[0]
        assert cycle.start_minute == 0
        assert cycle.duration_minutes == 45
        assert cycle.interval_minutes == 180

    def test_cwu_worst_case_is_tuple(self) -> None:
        """CWU_WORST_CASE is a non-empty tuple of CWUCycle."""
        assert isinstance(CWU_WORST_CASE, tuple)
        assert len(CWU_WORST_CASE) == 1
        assert isinstance(CWU_WORST_CASE[0], CWUCycle)

    def test_cwu_worst_case_values(self) -> None:
        """CWU_WORST_CASE: 45 min every 2 hours."""
        cycle = CWU_WORST_CASE[0]
        assert cycle.start_minute == 0
        assert cycle.duration_minutes == 45
        assert cycle.interval_minutes == 120


# ---------------------------------------------------------------------------
# TestCWUCoordinatorInit
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCWUCoordinatorInit:
    """Tests for CWUCoordinator initialization."""

    def test_init_with_empty_schedule(self) -> None:
        """Empty schedule creates a no-op coordinator."""
        config = ControllerConfig()
        cwu = CWUCoordinator(config, cwu_schedule=())
        # should_block_split always returns False with empty schedule
        assert not cwu.should_block_split(20.0, 21.0, is_cwu_active=True)

    def test_init_with_schedule(self) -> None:
        """Coordinator with a schedule is created without error."""
        config = ControllerConfig()
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        assert cwu is not None

    def test_default_schedule_is_empty(self) -> None:
        """Default cwu_schedule is empty tuple."""
        config = ControllerConfig()
        cwu = CWUCoordinator(config)
        # No blocking with default empty schedule
        assert not cwu.should_block_split(20.0, 21.0, is_cwu_active=True)

    def test_reset_is_noop(self) -> None:
        """reset() does not raise and is a no-op."""
        config = ControllerConfig()
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        cwu.reset()  # Should not raise


# ---------------------------------------------------------------------------
# TestShouldBlockSplit
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShouldBlockSplit:
    """Tests for CWUCoordinator.should_block_split()."""

    def test_blocks_when_cwu_active_and_warm(self) -> None:
        """Split is blocked when CWU is active and T_room > setpoint - margin."""
        config = ControllerConfig(cwu_anti_panic_margin=1.0)
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        # T_room=20.5, setpoint=21.0, margin=1.0 => threshold=20.0
        # 20.5 > 20.0 => blocked
        assert cwu.should_block_split(20.5, 21.0, is_cwu_active=True)

    def test_unblocks_when_t_room_below_threshold(self) -> None:
        """Split is unblocked when T_room <= setpoint - margin (safety fallback)."""
        config = ControllerConfig(cwu_anti_panic_margin=1.0)
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        # T_room=19.9, setpoint=21.0, margin=1.0 => threshold=20.0
        # 19.9 <= 20.0 => NOT blocked (safety)
        assert not cwu.should_block_split(19.9, 21.0, is_cwu_active=True)

    def test_unblocks_when_t_room_exactly_at_threshold(self) -> None:
        """Split is unblocked when T_room == setpoint - margin (conservative)."""
        config = ControllerConfig(cwu_anti_panic_margin=1.0)
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        # T_room=20.0, setpoint=21.0, margin=1.0 => threshold=20.0
        # 20.0 is NOT > 20.0 => NOT blocked
        assert not cwu.should_block_split(20.0, 21.0, is_cwu_active=True)

    def test_no_block_when_cwu_inactive(self) -> None:
        """No blocking when CWU is not active."""
        config = ControllerConfig(cwu_anti_panic_margin=1.0)
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        assert not cwu.should_block_split(20.5, 21.0, is_cwu_active=False)

    def test_no_block_with_empty_schedule(self) -> None:
        """No blocking with empty schedule even when CWU is active."""
        config = ControllerConfig(cwu_anti_panic_margin=1.0)
        cwu = CWUCoordinator(config, cwu_schedule=())
        assert not cwu.should_block_split(20.5, 21.0, is_cwu_active=True)

    def test_custom_margin(self) -> None:
        """Custom margin is respected."""
        config = ControllerConfig(cwu_anti_panic_margin=2.0)
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        # threshold = 21.0 - 2.0 = 19.0
        # T_room=19.5 > 19.0 => blocked
        assert cwu.should_block_split(19.5, 21.0, is_cwu_active=True)
        # T_room=18.5 <= 19.0 => NOT blocked
        assert not cwu.should_block_split(18.5, 21.0, is_cwu_active=True)


# ---------------------------------------------------------------------------
# TestGetPreChargeBoost
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetPreChargeBoost:
    """Tests for CWUCoordinator.get_pre_charge_boost()."""

    def test_boost_before_cwu_cycle(self) -> None:
        """Boost is returned when CWU cycle starts within lookahead."""
        config = ControllerConfig(
            cwu_pre_charge_lookahead_minutes=30,
            cwu_pre_charge_valve_boost_pct=15.0,
        )
        # CWU starts at t=60, duration=45, interval=180
        schedule = (CWUCycle(start_minute=60, duration_minutes=45, interval_minutes=180),)
        cwu = CWUCoordinator(config, cwu_schedule=schedule)

        # At t=35, CWU starts at t=60 (25 min away) => within 30 min lookahead
        boost = cwu.get_pre_charge_boost(35, is_cwu_active=False)
        assert boost == pytest.approx(15.0)

    def test_no_boost_when_cwu_far_away(self) -> None:
        """No boost when CWU cycle is beyond the lookahead window."""
        config = ControllerConfig(
            cwu_pre_charge_lookahead_minutes=30,
            cwu_pre_charge_valve_boost_pct=15.0,
        )
        schedule = (CWUCycle(start_minute=100, duration_minutes=45, interval_minutes=180),)
        cwu = CWUCoordinator(config, cwu_schedule=schedule)

        # At t=60, CWU starts at t=100 (40 min away) => beyond 30 min
        boost = cwu.get_pre_charge_boost(60, is_cwu_active=False)
        assert boost == pytest.approx(0.0)

    def test_no_boost_during_active_cwu(self) -> None:
        """No boost when CWU is currently active."""
        config = ControllerConfig(
            cwu_pre_charge_lookahead_minutes=30,
            cwu_pre_charge_valve_boost_pct=15.0,
        )
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        # CWU is active right now => no pre-charge
        boost = cwu.get_pre_charge_boost(0, is_cwu_active=True)
        assert boost == pytest.approx(0.0)

    def test_no_boost_with_empty_schedule(self) -> None:
        """No boost with empty schedule."""
        config = ControllerConfig(
            cwu_pre_charge_lookahead_minutes=30,
            cwu_pre_charge_valve_boost_pct=15.0,
        )
        cwu = CWUCoordinator(config, cwu_schedule=())
        boost = cwu.get_pre_charge_boost(0, is_cwu_active=False)
        assert boost == pytest.approx(0.0)

    def test_no_boost_when_lookahead_is_zero(self) -> None:
        """No boost when lookahead is 0."""
        config = ControllerConfig(
            cwu_pre_charge_lookahead_minutes=0,
            cwu_pre_charge_valve_boost_pct=15.0,
        )
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        boost = cwu.get_pre_charge_boost(0, is_cwu_active=False)
        assert boost == pytest.approx(0.0)

    def test_boost_for_repeating_cycle(self) -> None:
        """Boost is returned before a repeating CWU cycle (second occurrence)."""
        config = ControllerConfig(
            cwu_pre_charge_lookahead_minutes=30,
            cwu_pre_charge_valve_boost_pct=15.0,
        )
        # CWU: starts at t=0, 45 min every 180 min
        # Second cycle starts at t=180
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)

        # At t=160, CWU starts at t=180 (20 min away) => within 30 min
        boost = cwu.get_pre_charge_boost(160, is_cwu_active=False)
        assert boost == pytest.approx(15.0)

    def test_cwu_starts_exactly_at_t_zero(self) -> None:
        """Edge case: CWU starts at t=0, pre-charge at t=0 returns 0 (CWU active)."""
        config = ControllerConfig(
            cwu_pre_charge_lookahead_minutes=30,
            cwu_pre_charge_valve_boost_pct=15.0,
        )
        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)
        # At t=0, CWU is already active => no pre-charge
        boost = cwu.get_pre_charge_boost(0, is_cwu_active=True)
        assert boost == pytest.approx(0.0)

    def test_custom_boost_percentage(self) -> None:
        """Custom boost percentage is returned."""
        config = ControllerConfig(
            cwu_pre_charge_lookahead_minutes=30,
            cwu_pre_charge_valve_boost_pct=25.0,
        )
        schedule = (CWUCycle(start_minute=50, duration_minutes=30, interval_minutes=0),)
        cwu = CWUCoordinator(config, cwu_schedule=schedule)
        boost = cwu.get_pre_charge_boost(30, is_cwu_active=False)
        assert boost == pytest.approx(25.0)
