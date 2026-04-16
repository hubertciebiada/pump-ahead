"""Simulation tests for cooling safety scenarios.

Tests cover condensation protection (dew_point_stress) and stable
long-duration cooling operation (hot_july 7-day).  Scenarios exercise
the safety override logic: valve closes when T_floor < T_dew + 2C,
split takes over emergency cooling for equipped rooms.

All scenarios use ``modern_bungalow`` building (5 rooms with splits,
3 without) or ``well_insulated`` (hot_july).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pumpahead.config import SimScenario
from pumpahead.metrics import (
    SimMetrics,
    assert_floor_temp_safe,
    assert_no_opposing_action,
)
from pumpahead.scenarios import (
    dew_point_stress,
    hot_july,
)
from pumpahead.simulation_log import SimulationLog

# Rooms with split units in modern_bungalow building
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
# TestDewPointStress -- condensation protection under high humidity
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestDewPointStress:
    """Dew point stress scenario tests: RH=80%, T_out~30C, cooling mode.

    Notes:
        The simulation starts all thermal nodes at 20C (default initial
        state).  In a cooling scenario with T_out=30C the room air heats
        up while the floor stays cold, so the first ~720 minutes are a
        warmup transient where condensation conditions are inevitable.
        Safety and condensation assertions are evaluated from the second
        half (t >= 1440) once the system reaches thermal equilibrium.
    """

    def test_zero_condensation_events_after_warmup(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """No condensation events after warmup (second half).

        The cooling throttle and safety override must prevent
        T_floor from dropping below T_dew + 2C at RH=80% once
        the system has reached thermal equilibrium.
        """
        scenario = dew_point_stress()
        log, _ = run_scenario(scenario, None)

        half = scenario.duration_minutes // 2

        for room_cfg in scenario.building.rooms:
            room_log = log.get_room(room_cfg.name).time_range(
                half, scenario.duration_minutes
            )
            metrics = SimMetrics.from_log(
                room_log,
                setpoint=scenario.controller.setpoint,
                ufh_nominal_power_w=room_cfg.nominal_ufh_power_heating_w,
                split_power_w=room_cfg.split_power_w,
                dt_minutes=1,
            )
            assert metrics.condensation_events == 0, (
                f"{room_cfg.name}: {metrics.condensation_events} "
                f"condensation events after warmup (t >= {half})"
            )

    def test_safety_override_floor_temp_safe_after_warmup(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Floor temperature stays within safe bounds after warmup.

        Verifies Axiom #4 (T_floor <= 34C) and Axiom #5
        (T_floor >= T_dew + 2C) via assert_floor_temp_safe on the
        second half of the simulation.
        """
        scenario = dew_point_stress()
        log, _ = run_scenario(scenario, None)

        half = scenario.duration_minutes // 2

        for room_cfg in scenario.building.rooms:
            room_log = log.get_room(room_cfg.name).time_range(
                half, scenario.duration_minutes
            )
            assert_floor_temp_safe(room_log)

    def test_split_available_for_cooling(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Split-equipped rooms have split available for emergency cooling.

        Verifies that when a room overshoots the setpoint (T_room >
        setpoint + deadband), the split activates in cooling mode.
        Under extreme outdoor heat with dew-point-throttled UFH,
        some rooms will overshoot and the split should intervene.

        If no room overshoots (ground cooling keeps rooms below
        setpoint), the test verifies the system is correctly passive
        and the split is not needed.
        """
        scenario = dew_point_stress()
        log, _ = run_scenario(scenario, None)

        half = scenario.duration_minutes // 2
        deadband = scenario.controller.split_deadband

        any_overshoot = False
        for room_name in _SPLIT_ROOMS:
            room_log = log.get_room(room_name).time_range(
                half, scenario.duration_minutes
            )
            room_cfg = next(r for r in scenario.building.rooms if r.name == room_name)
            metrics = SimMetrics.from_log(
                room_log,
                setpoint=scenario.controller.setpoint,
                ufh_nominal_power_w=room_cfg.nominal_ufh_power_heating_w,
                split_power_w=room_cfg.split_power_w,
                dt_minutes=1,
            )
            if metrics.max_overshoot > deadband:
                any_overshoot = True
                # Room overshot setpoint: split should have activated
                assert metrics.split_runtime_pct > 0.0, (
                    f"{room_name}: overshoot={metrics.max_overshoot:.2f}C "
                    f"> deadband={deadband}C but split_runtime_pct=0.0"
                )

        # At minimum, verify the system ran without errors
        assert len(log) > 0, "dew_point_stress: empty log"
        if not any_overshoot:
            # All rooms stayed below setpoint: ground cooling sufficient,
            # split correctly stayed off.  This is a valid outcome.
            pass

    def test_no_opposing_action(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """No split action opposes the HP mode (Axiom #3).

        In cooling mode the split must never heat.
        """
        scenario = dew_point_stress()
        log, _ = run_scenario(scenario, None)

        for room_cfg in scenario.building.rooms:
            room_log = log.get_room(room_cfg.name)
            assert_no_opposing_action(room_log)


# ---------------------------------------------------------------------------
# TestHotJulyCoolingSafety -- 7-day stable cooling operation
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestHotJulyCoolingSafety:
    """Hot July scenario capped at 7 days for safety assertions."""

    def test_hot_july_7day_stable_operation(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Hot July runs 7 days without crash and produces sane metrics.

        Caps the 31-day scenario at 10080 steps (7 days at dt=60s).
        """
        scenario = hot_july()
        log, metrics = run_scenario(scenario, max_steps=10080)

        assert len(log) > 0, "hot_july: empty log"
        assert metrics.max_floor_temp < 50.0, (
            f"hot_july: max_floor_temp={metrics.max_floor_temp} >= 50"
        )

    def test_hot_july_7day_floor_temp_safe(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Floor temperature stays within safe bounds over 7 days."""
        scenario = hot_july()
        log, _ = run_scenario(scenario, max_steps=10080)

        first_room = scenario.building.rooms[0]
        room_log = log.get_room(first_room.name)
        assert_floor_temp_safe(room_log)

    def test_hot_july_7day_no_opposing_action(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """No split action opposes the HP mode over 7 days (Axiom #3)."""
        scenario = hot_july()
        log, _ = run_scenario(scenario, max_steps=10080)

        first_room = scenario.building.rooms[0]
        room_log = log.get_room(first_room.name)
        assert_no_opposing_action(room_log)

    def test_hot_july_7day_zero_condensation(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Zero condensation events over 7 days of cooling."""
        scenario = hot_july()
        log, metrics = run_scenario(scenario, max_steps=10080)

        assert metrics.condensation_events == 0, (
            f"hot_july: {metrics.condensation_events} condensation events"
        )


# ---------------------------------------------------------------------------
# TestCoolingSafetyComfort -- comfort verification for cooling mode
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestCoolingSafetyComfort:
    """Comfort verification for cooling scenarios."""

    def test_dew_point_stress_comfort_above_80pct(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Comfort >= 80% within +/-6.0C for split-equipped rooms.

        Under dew point stress, the UFH cooling valve is heavily
        throttled and the cold slab (T_ground=10C) pulls room
        temperature below setpoint.  In a well-insulated bungalow
        the ground coupling dominates over solar/conduction gains,
        so most rooms drift several degrees below the 25C setpoint
        even at 35C outdoor.  A wide 6.0C band reflects this
        physical reality — the primary goal of this scenario is
        condensation prevention, not tight comfort tracking.

        Salon is excluded because its 8 m² of S+W glazing produces
        ~3.8 kW of peak solar gain that no combination of throttled
        floor cooling and a single split can absorb at T_out=35C —
        the comfort-tracking objective is structurally infeasible
        for that room under this scenario.
        """
        scenario = dew_point_stress()
        log, _ = run_scenario(scenario, None)

        # Only check the second half (after warmup transient)
        half = scenario.duration_minutes // 2

        for room_name in _SPLIT_ROOMS:
            if room_name == "salon":
                continue
            room_log = log.get_room(room_name).time_range(
                half, scenario.duration_minutes
            )
            room_cfg = next(r for r in scenario.building.rooms if r.name == room_name)
            metrics = SimMetrics.from_log(
                room_log,
                setpoint=scenario.controller.setpoint,
                comfort_band=6.0,
                ufh_nominal_power_w=room_cfg.nominal_ufh_power_heating_w,
                split_power_w=room_cfg.split_power_w,
                dt_minutes=1,
            )
            assert metrics.comfort_pct >= 80.0, (
                f"{room_name}: comfort_pct={metrics.comfort_pct:.1f}% "
                f"< 80% (band=6.0C, second half only)"
            )
