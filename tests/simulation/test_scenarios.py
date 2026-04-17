"""Parametrized scenario tests for PumpAhead simulation framework.

Tests run simulation scenarios from ``SCENARIO_LIBRARY`` and
``PARAMETRIC_SWEEPS`` through the ``run_scenario`` fixture, then
verify metrics, safety constraints, and determinism.

Scenarios are split into two tiers:

* **FAST_SCENARIOS** -- short-duration (24h-48h) scenarios suitable for CI.
* **SLOW_SCENARIOS** -- longer scenarios (3-31 days) gated behind
  ``@pytest.mark.slow``.

``full_year_2025`` (525,600 steps) is excluded from both tiers.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import pytest

from pumpahead.config import SimScenario
from pumpahead.metrics import (
    SimMetrics,
    assert_floor_temp_safe,
    assert_no_freezing,
    assert_no_opposing_action,
    assert_no_prolonged_cold,
)
from pumpahead.scenarios import PARAMETRIC_SWEEPS, SCENARIO_LIBRARY
from pumpahead.simulation_log import SimulationLog

# ---------------------------------------------------------------------------
# Scenario tiers
# ---------------------------------------------------------------------------

FAST_SCENARIOS: list[str] = [
    "steady_state",
    "extreme_cold",
    "rapid_warming",
    "cwu_heavy",
    "cold_snap_weather_comp",
]
"""Short-duration scenarios (24h-48h) for regular CI runs."""

SLOW_SCENARIOS: list[str] = [
    "cold_snap",
    "hot_july",
    "solar_overshoot",
]
"""Longer scenarios (3-31 days) gated behind @pytest.mark.slow."""

SWEEP_NAMES: list[str] = [
    "insulation_sweep",
    "screed_sweep",
]
"""Parametric sweep names from PARAMETRIC_SWEEPS."""


# ---------------------------------------------------------------------------
# TestScenarioSimulation -- fast parametrized scenario tests
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestScenarioSimulation:
    """Fast scenario tests parametrized over FAST_SCENARIOS."""

    @pytest.mark.parametrize("scenario_name", FAST_SCENARIOS)
    def test_scenario_runs_and_produces_metrics(
        self,
        scenario_name: str,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
        save_scenario_plot: Callable[[SimulationLog, str, str, float], Path],
    ) -> None:
        """Scenario runs to completion and produces sane metrics."""
        scenario = SCENARIO_LIBRARY[scenario_name]()
        log, metrics = run_scenario(scenario)

        # Sanity checks
        assert len(log) > 0, f"{scenario_name}: empty log"
        assert metrics.comfort_pct >= 0.0, (
            f"{scenario_name}: comfort_pct={metrics.comfort_pct} < 0"
        )
        assert metrics.max_floor_temp < 50.0, (
            f"{scenario_name}: max_floor_temp={metrics.max_floor_temp} >= 50"
        )
        assert math.isfinite(metrics.mean_deviation), (
            f"{scenario_name}: mean_deviation is not finite"
        )

        # Generate plot for the first room
        first_room = scenario.building.rooms[0].name
        save_scenario_plot(log, scenario_name, first_room, scenario.controller.setpoint)

    @pytest.mark.parametrize("scenario_name", FAST_SCENARIOS)
    def test_scenario_floor_temp_safe(
        self,
        scenario_name: str,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Floor temperature stays within safe limits (Axioms #4 and #5)."""
        scenario = SCENARIO_LIBRARY[scenario_name]()
        log, _metrics = run_scenario(scenario)

        first_room = scenario.building.rooms[0].name
        assert_floor_temp_safe(log.get_room(first_room))

    @pytest.mark.parametrize("scenario_name", FAST_SCENARIOS)
    def test_scenario_no_opposing_action(
        self,
        scenario_name: str,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """No split action opposes the heat-pump mode (Axiom #3)."""
        scenario = SCENARIO_LIBRARY[scenario_name]()
        log, _metrics = run_scenario(scenario)

        first_room = scenario.building.rooms[0].name
        assert_no_opposing_action(log.get_room(first_room))

    @pytest.mark.parametrize("scenario_name", FAST_SCENARIOS)
    def test_scenario_no_freezing_or_prolonged_cold(
        self,
        scenario_name: str,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """No room ever freezes (T<16) or stays below 18 degC for >24h.

        ``extreme_cold`` (leaky_old_house) is the control case — it is
        expected to violate one of the assertions, so it is wrapped in
        ``pytest.raises``.  Cooling-mode scenarios are skipped (the
        assertions are heating-only by intent).
        """
        scenario = SCENARIO_LIBRARY[scenario_name]()
        log, _metrics = run_scenario(scenario)

        if scenario_name == "extreme_cold":
            with pytest.raises(AssertionError):
                assert_no_freezing(log)
                assert_no_prolonged_cold(log)
            return

        if scenario.mode == "cooling":
            return

        assert_no_freezing(log)
        assert_no_prolonged_cold(log)

    @pytest.mark.parametrize("scenario_name", FAST_SCENARIOS[:2])
    def test_scenario_deterministic(
        self,
        scenario_name: str,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Running the same scenario twice produces identical metrics."""
        scenario_a = SCENARIO_LIBRARY[scenario_name]()
        scenario_b = SCENARIO_LIBRARY[scenario_name]()

        _log_a, metrics_a = run_scenario(scenario_a)
        _log_b, metrics_b = run_scenario(scenario_b)

        assert metrics_a == metrics_b, (
            f"{scenario_name}: metrics differ between two identical runs"
        )


# ---------------------------------------------------------------------------
# TestSlowScenarios -- gated behind @pytest.mark.slow
# ---------------------------------------------------------------------------


@pytest.mark.simulation
@pytest.mark.slow
class TestSlowScenarios:
    """Longer scenarios capped at 4320 steps (3 days) for CI feasibility."""

    @pytest.mark.parametrize("scenario_name", SLOW_SCENARIOS)
    def test_slow_scenario_runs(
        self,
        scenario_name: str,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
        save_scenario_plot: Callable[[SimulationLog, str, str, float], Path],
    ) -> None:
        """Slow scenario runs (capped at 3 days) and produces sane metrics."""
        scenario = SCENARIO_LIBRARY[scenario_name]()
        log, metrics = run_scenario(scenario, max_steps=4320)

        assert len(log) > 0, f"{scenario_name}: empty log"
        assert metrics.comfort_pct >= 0.0, (
            f"{scenario_name}: comfort_pct={metrics.comfort_pct} < 0"
        )
        assert metrics.max_floor_temp < 50.0, (
            f"{scenario_name}: max_floor_temp={metrics.max_floor_temp} >= 50"
        )
        assert math.isfinite(metrics.mean_deviation), (
            f"{scenario_name}: mean_deviation is not finite"
        )

        # Generate plot for the first room
        first_room = scenario.building.rooms[0].name
        save_scenario_plot(log, scenario_name, first_room, scenario.controller.setpoint)

    @pytest.mark.parametrize("scenario_name", SLOW_SCENARIOS)
    def test_slow_scenario_no_freezing_or_prolonged_cold(
        self,
        scenario_name: str,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """No room ever freezes (T<16) or stays below 18 degC for >24h.

        Slow tier is capped at 4320 minutes (3 days) for CI feasibility.
        Cooling-mode scenarios (e.g. ``hot_july``) are skipped — these
        assertions are heating-only by intent.
        """
        scenario = SCENARIO_LIBRARY[scenario_name]()
        log, _metrics = run_scenario(scenario, max_steps=4320)

        if scenario.mode == "cooling":
            return

        assert_no_freezing(log)
        assert_no_prolonged_cold(log)


# ---------------------------------------------------------------------------
# TestParametricSweeps
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestParametricSweeps:
    """Test parametric sweep scenarios from PARAMETRIC_SWEEPS."""

    @pytest.mark.parametrize("sweep_name", SWEEP_NAMES)
    def test_sweep_scenarios_run(
        self,
        sweep_name: str,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
        save_scenario_plot: Callable[[SimulationLog, str, str, float], Path],
    ) -> None:
        """Every scenario in the sweep runs and produces a non-empty log."""
        scenarios = PARAMETRIC_SWEEPS[sweep_name]()

        for scenario in scenarios:
            log, _metrics = run_scenario(scenario, max_steps=1440)

            assert len(log) > 0, f"{sweep_name}/{scenario.name}: empty log"

            # Generate plot for the first room
            first_room = scenario.building.rooms[0].name
            save_scenario_plot(
                log,
                scenario.name,
                first_room,
                scenario.controller.setpoint,
            )


# ---------------------------------------------------------------------------
# TestMetricsIntegration
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestMetricsIntegration:
    """Integration tests for metrics computation across scenarios."""

    def test_steady_state_produces_finite_metrics(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Steady-state scenario produces finite, non-negative metrics.

        Note: proportional-only control has inherent steady-state offset,
        so we do not assert a high comfort percentage here.  The goal is
        to verify that the metrics pipeline computes reasonable values.
        """
        scenario = SCENARIO_LIBRARY["steady_state"]()
        _log, metrics = run_scenario(scenario)

        assert metrics.comfort_pct >= 0.0, (
            f"steady_state comfort_pct={metrics.comfort_pct} < 0"
        )
        assert math.isfinite(metrics.mean_deviation), (
            "steady_state mean_deviation is not finite"
        )
        assert metrics.max_undershoot >= 0.0, (
            f"steady_state max_undershoot={metrics.max_undershoot} < 0"
        )
        assert metrics.energy_kwh is not None, (
            "steady_state energy_kwh is None (power params were provided)"
        )
        assert metrics.energy_kwh >= 0.0, (
            f"steady_state energy_kwh={metrics.energy_kwh} < 0"
        )

    def test_metrics_compare_across_scenarios(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """SimMetrics.compare() returns non-empty diffs with expected keys."""
        scenario_a = SCENARIO_LIBRARY["steady_state"]()
        scenario_b = SCENARIO_LIBRARY["extreme_cold"]()

        _log_a, metrics_a = run_scenario(scenario_a)
        _log_b, metrics_b = run_scenario(scenario_b)

        diff = metrics_a.compare(metrics_b)

        assert len(diff) > 0, "compare() returned empty dict"

        # Check that diff keys match SimMetrics fields
        from dataclasses import fields

        expected_keys = {f.name for f in fields(SimMetrics)}
        assert set(diff.keys()) == expected_keys, (
            f"diff keys {set(diff.keys())} != SimMetrics fields {expected_keys}"
        )
