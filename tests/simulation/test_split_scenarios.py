"""Simulation tests for split coordination scenarios.

Tests cover dual-source steady-state, cold-snap, and priority-inversion-stress
scenarios.  Each test exercises the split coordination logic through a full
multi-room simulation using ``run_scenario``.

All scenarios use ``modern_bungalow`` building (5 rooms with splits, 3 without).
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
    bathroom_heater,
    bathroom_heater_cooling,
    dual_source_cold_snap,
    dual_source_steady_state,
    priority_inversion_stress,
)
from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import SplitMode

# Rooms with split units in modern_bungalow_with_splits building
_SPLIT_ROOMS = [
    "salon",
    "sypialnia",
    "gabinet_1",
    "gabinet_2",
    "pokoj_dziecka_1",
    "pokoj_dziecka_2",
]
# Rooms without split units
_UFH_ONLY_ROOMS = ["lazienka", "garderoba", "dlugi_korytarz"]


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
            room_cfg = next(r for r in scenario.building.rooms if r.name == room_name)
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
            room_cfg = next(r for r in scenario.building.rooms if r.name == room_name)
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
            room_cfg = next(r for r in scenario.building.rooms if r.name == room_name)
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
            room_cfg = next(r for r in scenario.building.rooms if r.name == room_name)
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


# ---------------------------------------------------------------------------
# Bathroom heater (heating-only auxiliary) tests
# ---------------------------------------------------------------------------


_LIVING_ROOMS_20C = [
    "salon",
    "kuchnia_jadalnia",
    "sypialnia",
    "pokoj_dziecka_1",
]


@pytest.mark.simulation
class TestBathroomHeater:
    """Tests for the ``bathroom_heater`` and ``bathroom_heater_cooling``
    scenarios — heating-only electric heater in the bathroom.
    """

    def test_bathroom_reaches_24c(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Bathroom tracks its 24 C override setpoint in the second 24h."""
        scenario = bathroom_heater()
        log, _ = run_scenario(scenario, None)

        half = scenario.duration_minutes // 2
        room_log = log.get_room("lazienka").time_range(
            half, scenario.duration_minutes
        )
        room_cfg = next(r for r in scenario.building.rooms if r.name == "lazienka")
        metrics = SimMetrics.from_log(
            room_log,
            setpoint=24.0,
            comfort_band=0.7,
            ufh_max_power_w=room_cfg.ufh_max_power_w,
            split_power_w=room_cfg.split_power_w,
        )
        assert metrics.comfort_pct > 80.0, (
            f"lazienka: comfort_pct={metrics.comfort_pct:.1f}% below 80% "
            f"(band=0.7, setpoint=24.0)"
        )

    def test_living_area_reaches_20c(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Living-area rooms track the 20 C scenario setpoint."""
        scenario = bathroom_heater()
        log, _ = run_scenario(scenario, None)

        half = scenario.duration_minutes // 2
        for room_name in _LIVING_ROOMS_20C:
            room_log = log.get_room(room_name).time_range(
                half, scenario.duration_minutes
            )
            room_cfg = next(r for r in scenario.building.rooms if r.name == room_name)
            metrics = SimMetrics.from_log(
                room_log,
                setpoint=20.0,
                comfort_band=1.0,
                ufh_max_power_w=room_cfg.ufh_max_power_w,
                split_power_w=room_cfg.split_power_w,
            )
            assert metrics.comfort_pct > 80.0, (
                f"{room_name}: comfort_pct={metrics.comfort_pct:.1f}% "
                f"below 80% (band=1.0, setpoint=20.0)"
            )

    def test_heater_activates_in_heating_mode(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Heater activates (runtime > 0) but stays below 50% (Axiom #2)."""
        scenario = bathroom_heater()
        log, _ = run_scenario(scenario, None)

        room_log = log.get_room("lazienka")
        room_cfg = next(r for r in scenario.building.rooms if r.name == "lazienka")
        metrics = SimMetrics.from_log(
            room_log,
            setpoint=24.0,
            ufh_max_power_w=room_cfg.ufh_max_power_w,
            split_power_w=room_cfg.split_power_w,
        )
        assert metrics.split_runtime_pct > 0.0, (
            "heater never activated during heating — expected > 0% "
            "runtime while tracking 24 C against 20 C house setpoint"
        )
        assert metrics.split_runtime_pct < 50.0, (
            f"heater runtime {metrics.split_runtime_pct:.1f}% exceeds "
            f"50% — priority inversion"
        )

    def test_bathroom_passive_in_cooling_mode(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Bathroom heater is OFF at every step in cooling mode."""
        scenario = bathroom_heater_cooling()
        log, _ = run_scenario(scenario, None)

        room_log = log.get_room("lazienka")
        off_count = 0
        total = 0
        for rec in room_log:
            total += 1
            if rec.split_mode == SplitMode.OFF:
                off_count += 1
        assert off_count == total, (
            f"lazienka heater activated in cooling mode: "
            f"{total - off_count}/{total} records had split_mode != OFF"
        )

    def test_no_opposing_action_across_modes(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Heater never opposes the HP mode (Axiom #3) in either scenario."""
        heating_scenario = bathroom_heater()
        heating_log, _ = run_scenario(heating_scenario, None)
        assert_no_opposing_action(heating_log)

        cooling_scenario = bathroom_heater_cooling()
        cooling_log, _ = run_scenario(cooling_scenario, None)
        assert_no_opposing_action(cooling_log)

    def test_no_priority_inversion_bathroom_heater(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Heater runtime below 50% (Axiom #2)."""
        scenario = bathroom_heater()
        log, _ = run_scenario(scenario, None)
        room_log = log.get_room("lazienka")
        assert_no_priority_inversion(room_log, max_split_pct=50.0)

    def test_floor_temp_safe_bathroom_heater(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Floor temperature stays within safe bounds (Axioms #4, #5)."""
        scenario = bathroom_heater()
        log, _ = run_scenario(scenario, None)
        assert_floor_temp_safe(log)
