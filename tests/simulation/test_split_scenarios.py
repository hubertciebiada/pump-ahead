"""Simulation tests for split coordination scenarios.

Tests cover dual-source steady-state, cold-snap, and priority-inversion-stress
scenarios.  Each test exercises the split coordination logic through a full
multi-room simulation using ``run_scenario``.

All scenarios use ``hubert_real`` building (5 rooms with splits, 3 without).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pumpahead.config import SimScenario
from pumpahead.metrics import (
    SimMetrics,
    assert_floor_temp_safe,
    assert_no_opposing_action,
    assert_no_priority_inversion,
)
from pumpahead.scenarios import (
    dual_source_cold_snap,
    dual_source_steady_state,
    priority_inversion_stress,
)
from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import SplitMode

# Rooms with split units in hubert_real building
_SPLIT_ROOMS = ["salon", "kuchnia", "sypialnia", "gabinet", "pokoj_dzieci"]
# Rooms without split units
_UFH_ONLY_ROOMS = ["lazienka", "garderoba", "korytarz"]


# ---------------------------------------------------------------------------
# Dual-source steady-state tests
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestDualSourceSteadyState:
    """Steady-state dual-source scenario tests."""

    def test_split_runtime_below_threshold(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Split runtime stays below 50% in steady state for split rooms.

        Metrics are computed from the second half (after warmup) to
        exclude the transient startup period.  The anti-takeover
        mechanism (Axiom #2) ensures split runtime does not exceed
        50% even in a capacity-constrained multi-room building.
        """
        scenario = dual_source_steady_state()
        log, _ = run_scenario(scenario, None)

        # Only check the second half — after the warmup transient
        half = scenario.duration_minutes // 2

        for room_name in _SPLIT_ROOMS:
            room_log = log.get_room(room_name).time_range(
                half, scenario.duration_minutes
            )
            room_cfg = next(
                r for r in scenario.building.rooms if r.name == room_name
            )
            metrics = SimMetrics.from_log(
                room_log,
                setpoint=scenario.controller.setpoint,
                ufh_max_power_w=room_cfg.ufh_max_power_w,
                split_power_w=room_cfg.split_power_w,
            )
            assert metrics.split_runtime_pct < 50.0, (
                f"{room_name}: split_runtime_pct={metrics.split_runtime_pct:.1f}%"
                f" exceeds 50%"
            )

    def test_comfort_above_threshold(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Comfort exceeds 80% for dual-source rooms in steady state.

        Uses a comfort band of 2.0 degC to account for HP capacity
        constraints in an 8-room building sharing 9 kW.  Metrics
        computed from the second half (after warmup).
        """
        scenario = dual_source_steady_state()
        log, _ = run_scenario(scenario, None)

        half = scenario.duration_minutes // 2

        for room_name in _SPLIT_ROOMS:
            room_log = log.get_room(room_name).time_range(
                half, scenario.duration_minutes
            )
            room_cfg = next(
                r for r in scenario.building.rooms if r.name == room_name
            )
            metrics = SimMetrics.from_log(
                room_log,
                setpoint=scenario.controller.setpoint,
                comfort_band=2.0,
                ufh_max_power_w=room_cfg.ufh_max_power_w,
                split_power_w=room_cfg.split_power_w,
            )
            assert metrics.comfort_pct > 80.0, (
                f"{room_name}: comfort_pct={metrics.comfort_pct:.1f}%"
                f" below 80% (band=2.0)"
            )

    def test_no_opposing_action(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """No split action opposes the HP mode (Axiom #3)."""
        scenario = dual_source_steady_state()
        log, _ = run_scenario(scenario, None)
        assert_no_opposing_action(log)

    def test_ufh_only_rooms_unaffected(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """UFH-only rooms have zero split runtime.

        Verifies that rooms without split coordinators never activate
        the split unit, confirming backward compatibility.
        """
        scenario = dual_source_steady_state()
        log, _ = run_scenario(scenario, None)

        for room_name in _UFH_ONLY_ROOMS:
            room_log = log.get_room(room_name)
            room_cfg = next(
                r for r in scenario.building.rooms if r.name == room_name
            )
            metrics = SimMetrics.from_log(
                room_log,
                setpoint=scenario.controller.setpoint,
                ufh_max_power_w=room_cfg.ufh_max_power_w,
                split_power_w=room_cfg.split_power_w,
            )
            assert metrics.split_runtime_pct == pytest.approx(0.0), (
                f"{room_name}: split_runtime_pct={metrics.split_runtime_pct:.1f}%"
                f" expected 0.0%"
            )


# ---------------------------------------------------------------------------
# Dual-source cold-snap tests
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestDualSourceColdSnap:
    """Cold-snap dual-source scenario tests."""

    def test_split_enters_during_cold_snap(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """At least some split activations occur after the T_out drop."""
        scenario = dual_source_cold_snap()
        log, _ = run_scenario(scenario, None)

        # Check the period after the step drop (t >= 1440)
        post_drop_split_on = 0
        for room_name in _SPLIT_ROOMS:
            room_log = log.get_room(room_name).time_range(1440, 7200)
            for rec in room_log:
                if rec.split_mode != SplitMode.OFF:
                    post_drop_split_on += 1

        assert post_drop_split_on > 0, (
            "No split activations after cold snap drop — "
            "split should help during transient"
        )

    def test_no_priority_inversion(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Split runtime stays below 50% even during cold-snap transient."""
        scenario = dual_source_cold_snap()
        log, _ = run_scenario(scenario, None)

        # Check post-drop only (transient period)
        for room_name in _SPLIT_ROOMS:
            room_log = log.get_room(room_name).time_range(1440, 7200)
            assert_no_priority_inversion(room_log, max_split_pct=50.0)

    def test_floor_temp_safe(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Floor temperature stays within safe bounds (Axioms #4, #5)."""
        scenario = dual_source_cold_snap()
        log, _ = run_scenario(scenario, None)
        assert_floor_temp_safe(log)


# ---------------------------------------------------------------------------
# Priority inversion stress tests
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestPriorityInversionStress:
    """Priority inversion stress scenario tests."""

    def test_anti_takeover_prevents_inversion(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Split runtime stays below 50% even under extreme stress."""
        scenario = priority_inversion_stress()
        log, _ = run_scenario(scenario, None)

        for room_name in _SPLIT_ROOMS:
            room_log = log.get_room(room_name)
            room_cfg = next(
                r for r in scenario.building.rooms if r.name == room_name
            )
            metrics = SimMetrics.from_log(
                room_log,
                setpoint=scenario.controller.setpoint,
                ufh_max_power_w=room_cfg.ufh_max_power_w,
                split_power_w=room_cfg.split_power_w,
            )
            assert metrics.split_runtime_pct < 50.0, (
                f"{room_name}: split_runtime_pct={metrics.split_runtime_pct:.1f}%"
                f" exceeds 50%"
            )

    def test_no_opposing_action(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """No split action opposes the HP mode (Axiom #3)."""
        scenario = priority_inversion_stress()
        log, _ = run_scenario(scenario, None)
        assert_no_opposing_action(log)
