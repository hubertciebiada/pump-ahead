"""Simulation tests for the ``cold_snap_weather_comp`` scenario.

Exercises the weather-compensation curve introduced in #141 and wired
into the simulator in #143 under a 48 h cold snap (0 C -> -15 C step at
t=1440 min).  The scenario uses the ``modern_bungalow`` building and a
realistic Aquarea/Daikin-style heating curve
(``t_supply_base=35``, ``slope=0.4``, ``t_neutral=0``, ``min=25``,
``max=55``).

Tests:
    * Comfort above 18 C in every room over the full 2880 min.
    * Floor-temperature safety per room (Axiom #4 and Axiom #5).
    * No freezing and no prolonged cold in the whole log.
    * ``T_supply`` peak during the cold half (t >= 1440) ~ 41 C ± 1 C.
    * ``T_supply`` stays within the configured min/max clamps.
    * ``T_supply`` is monotonically non-decreasing as ``T_out`` drops.
    * A 2-panel PNG plot of ``T_out`` and ``T_supply`` is produced.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pumpahead.config import SimScenario
from pumpahead.metrics import (
    SimMetrics,
    assert_floor_temp_safe,
    assert_no_freezing,
    assert_no_prolonged_cold,
)
from pumpahead.scenarios import cold_snap_weather_comp
from pumpahead.simulation_log import SimulationLog
from pumpahead.weather_comp import WeatherCompCurve


def _curve(scenario: SimScenario) -> WeatherCompCurve:
    """Return the scenario's heating weather-compensation curve.

    Args:
        scenario: Scenario under test.

    Returns:
        The configured :class:`WeatherCompCurve`.

    Raises:
        AssertionError: If the scenario does not have a ``weather_comp``.
    """
    curve = scenario.weather_comp
    assert curve is not None, "cold_snap_weather_comp must configure weather_comp"
    return curve


@pytest.mark.simulation
class TestColdSnapWeatherComp:
    """Tests for the ``cold_snap_weather_comp`` scenario."""

    def test_all_rooms_comfort_above_18c(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Every room stays strictly above 18 C for the full 48 h."""
        scenario = cold_snap_weather_comp()
        log, _ = run_scenario(scenario, None)

        for room_cfg in scenario.building.rooms:
            room_log = log.get_room(room_cfg.name)
            min_t_room = min(rec.T_room for rec in room_log)
            assert min_t_room > 18.0, (
                f"{room_cfg.name}: min T_room={min_t_room:.2f} C "
                "dropped to or below 18 C"
            )

    def test_floor_temp_safe_all_rooms(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Floor temperature stays within safe bounds in every room."""
        scenario = cold_snap_weather_comp()
        log, _ = run_scenario(scenario, None)

        for room_cfg in scenario.building.rooms:
            assert_floor_temp_safe(log.get_room(room_cfg.name))

    def test_no_freezing_no_prolonged_cold(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """No room ever freezes (T<16) or stays below 18 C for >24 h."""
        scenario = cold_snap_weather_comp()
        log, _ = run_scenario(scenario, None)

        assert_no_freezing(log)
        assert_no_prolonged_cold(log)

    def test_t_supply_peaks_at_41c_during_cold(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Peak T_supply during the cold half (t >= 1440) is ~41 C ± 1 C."""
        scenario = cold_snap_weather_comp()
        log, _ = run_scenario(scenario, None)

        curve = _curve(scenario)
        first_room = scenario.building.rooms[0].name
        room_log = log.get_room(first_room)

        peak_t_supply = max(
            curve.t_supply(rec.T_out) for rec in room_log if rec.t >= 1440
        )
        assert peak_t_supply == pytest.approx(41.0, abs=1.0), (
            f"peak T_supply during cold half={peak_t_supply:.2f} C, "
            "expected ~41 C ± 1 C"
        )

    def test_t_supply_within_clamps(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """T_supply never falls below 25 C nor exceeds 55 C."""
        scenario = cold_snap_weather_comp()
        log, _ = run_scenario(scenario, None)

        curve = _curve(scenario)
        first_room = scenario.building.rooms[0].name
        room_log = log.get_room(first_room)

        t_supplies = [curve.t_supply(rec.T_out) for rec in room_log]
        assert min(t_supplies) >= 25.0, (
            f"min T_supply={min(t_supplies):.2f} C below min-clamp 25 C"
        )
        assert max(t_supplies) <= 55.0 + 1e-9, (
            f"max T_supply={max(t_supplies):.2f} C above max-clamp 55 C"
        )

    def test_t_supply_monotonic_with_cold(self) -> None:
        """T_supply monotonically rises as T_out drops and equals base at warm."""
        scenario = cold_snap_weather_comp()
        curve = _curve(scenario)

        assert curve.t_supply(-15.0) > curve.t_supply(0.0) >= curve.t_supply(5.0)
        assert curve.t_supply(5.0) == pytest.approx(35.0)
        assert curve.t_supply(-15.0) == pytest.approx(41.0)

    def test_t_supply_plot_generated(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
        plot_output_dir: Path,
    ) -> None:
        """Generate a 2-panel PNG of T_out and T_supply over the simulation."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        scenario = cold_snap_weather_comp()
        log, _ = run_scenario(scenario, None)

        curve = _curve(scenario)
        first_room = scenario.building.rooms[0].name
        room_log = log.get_room(first_room)

        times = [rec.t for rec in room_log]
        t_outs = [rec.T_out for rec in room_log]
        t_supplies = [curve.t_supply(rec.T_out) for rec in room_log]

        fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
        axes[0].plot(times, t_outs, label="T_out", color="tab:blue")
        axes[0].set_ylabel("T_out [degC]")
        axes[0].legend(loc="upper right")

        axes[1].plot(times, t_supplies, label="T_supply", color="tab:red")
        axes[1].axhline(25.0, color="tab:gray", linestyle="--", label="min=25")
        axes[1].axhline(55.0, color="tab:gray", linestyle=":", label="max=55")
        axes[1].set_ylabel("T_supply [degC]")
        axes[1].set_xlabel("Time [min]")
        axes[1].legend(loc="upper right")

        fig.suptitle("cold_snap_weather_comp / T_out vs T_supply")
        fig.tight_layout()

        out_path = plot_output_dir / "cold_snap_weather_comp_t_supply.png"
        fig.savefig(str(out_path), dpi=100)
        plt.close(fig)

        assert out_path.exists(), f"plot not created at {out_path}"
        assert out_path.stat().st_size > 0, f"plot is empty: {out_path}"
