"""A/B testing: MPC vs PID controller comparison.

Tests the ``ABTestRunner`` framework on single-room heating scenarios,
verifying determinism, report generation, overlay plotting, summary
tables, framework reusability, and MPC performance advantage.

All tests use ``@pytest.mark.simulation`` and the steady_state scenario
(with optional step caps for fast tests).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pumpahead.ab_testing import (
    ABReport,
    ABTestRunner,
    MPCAdapter,
    PIDAdapter,
    plot_overlay,
)
from pumpahead.metrics import SimMetrics
from pumpahead.scenarios import steady_state
from pumpahead.simulation_log import SimulationLog

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SHORT_STEPS = 360  # 6 hours -- fast enough for CI


def _make_runner() -> ABTestRunner:
    """Create a fresh ABTestRunner with PID (A) and MPC (B) adapters."""
    return ABTestRunner(PIDAdapter(), MPCAdapter())


# ---------------------------------------------------------------------------
# TestABFrameworkSmoke — basic framework tests
# ---------------------------------------------------------------------------


class TestABFrameworkSmoke:
    """Smoke tests for the A/B testing framework."""

    @pytest.mark.simulation
    def test_determinism(self) -> None:
        """Running the same scenario twice produces identical metrics."""
        scenario = steady_state()

        runner1 = ABTestRunner(PIDAdapter(), MPCAdapter())
        report1 = runner1.run(scenario, max_steps=_SHORT_STEPS)

        runner2 = ABTestRunner(PIDAdapter(), MPCAdapter())
        report2 = runner2.run(scenario, max_steps=_SHORT_STEPS)

        # Metrics must be exactly equal (deterministic)
        assert report1.metrics_a == report2.metrics_a
        assert report1.metrics_b == report2.metrics_b
        assert report1.deltas == report2.deltas

    @pytest.mark.simulation
    def test_valid_report(self) -> None:
        """ABReport has correct controller names, scenario name, and types."""
        scenario = steady_state()
        runner = _make_runner()
        report = runner.run(scenario, max_steps=_SHORT_STEPS)

        assert isinstance(report, ABReport)
        assert report.controller_a_name == "PID"
        assert report.controller_b_name == "MPC"
        assert report.scenario_name == "steady_state"
        assert isinstance(report.metrics_a, SimMetrics)
        assert isinstance(report.metrics_b, SimMetrics)
        assert isinstance(report.deltas, dict)
        assert isinstance(report.log_a, SimulationLog)
        assert isinstance(report.log_b, SimulationLog)

    @pytest.mark.simulation
    def test_overlay_plot(self, tmp_path: Path) -> None:
        """plot_overlay produces a figure and saves to file without errors."""
        scenario = steady_state()
        runner = _make_runner()
        report = runner.run(scenario, max_steps=_SHORT_STEPS)

        save_path = str(tmp_path / "overlay.png")
        fig = plot_overlay(report, save_path=save_path)

        # Check that the figure was created
        assert fig is not None
        # Check that the file was saved
        assert Path(save_path).exists()
        assert Path(save_path).stat().st_size > 0

    @pytest.mark.simulation
    def test_summary_table(self) -> None:
        """summary_table returns a multi-line string with all metric names."""
        scenario = steady_state()
        runner = _make_runner()
        report = runner.run(scenario, max_steps=_SHORT_STEPS)

        table = report.summary_table()

        assert isinstance(table, str)
        # Table should contain key metric names
        assert "comfort_pct" in table
        assert "energy_kwh" in table
        assert "mean_deviation" in table
        assert "max_overshoot" in table
        # Table should contain controller names
        assert "PID" in table
        assert "MPC" in table

    @pytest.mark.simulation
    def test_reusability_different_adapters(self) -> None:
        """ABTestRunner works with two PID adapters (proving reusability).

        The framework is not hard-coded to MPC vs PID; any two adapters
        implementing ControllerAdapter work.
        """
        scenario = steady_state()

        # PID vs PID should produce identical results
        runner = ABTestRunner(PIDAdapter(), PIDAdapter())
        report = runner.run(scenario, max_steps=_SHORT_STEPS)

        assert report.controller_a_name == "PID"
        assert report.controller_b_name == "PID"

        # With identical controllers, metrics must be equal
        assert report.metrics_a == report.metrics_b
        # All deltas should be zero
        for _metric_name, delta in report.deltas.items():
            if delta is not None:
                assert delta == 0.0


# ---------------------------------------------------------------------------
# TestMPCvsPIDComparison — performance comparison
# ---------------------------------------------------------------------------


class TestMPCvsPIDComparison:
    """Tests that MPC outperforms PID on at least one metric."""

    @pytest.mark.simulation
    @pytest.mark.slow
    def test_mpc_beats_pid_steady_state(self) -> None:
        """MPC outperforms PID on comfort_pct OR energy_kwh on steady_state.

        Runs the full 2880-step steady_state scenario (48h). The
        acceptance criterion is that MPC must win on at least one of
        comfort_pct or energy_kwh.
        """
        scenario = steady_state()
        runner = _make_runner()
        report = runner.run(scenario, max_steps=2880)

        mpc_wins_comfort = report.a_wins_on("comfort_pct") is False
        mpc_wins_energy = report.a_wins_on("energy_kwh") is False

        # At least one must be True
        assert mpc_wins_comfort or mpc_wins_energy, (
            f"MPC did not outperform PID on either comfort_pct or energy_kwh.\n"
            f"PID comfort: {report.metrics_a.comfort_pct:.1f}%, "
            f"MPC comfort: {report.metrics_b.comfort_pct:.1f}%\n"
            f"PID energy: {report.metrics_a.energy_kwh}, "
            f"MPC energy: {report.metrics_b.energy_kwh}\n"
            f"{report.summary_table()}"
        )

    @pytest.mark.simulation
    def test_a_wins_on_returns_correct_type(self) -> None:
        """a_wins_on returns bool or None for various metric names."""
        scenario = steady_state()
        runner = _make_runner()
        report = runner.run(scenario, max_steps=_SHORT_STEPS)

        # Known metrics should return bool
        result = report.a_wins_on("comfort_pct")
        assert result is True or result is False

        # Unknown metric should return None
        assert report.a_wins_on("nonexistent_metric") is None

    @pytest.mark.simulation
    def test_logs_have_correct_length(self) -> None:
        """Simulation logs have the expected number of records."""
        scenario = steady_state()
        runner = _make_runner()
        steps = 120
        report = runner.run(scenario, max_steps=steps)

        # Each log should have records for each room * each step
        n_rooms = len(scenario.building.rooms)
        expected_total = steps * n_rooms

        assert len(report.log_a) == expected_total
        assert len(report.log_b) == expected_total

    @pytest.mark.simulation
    def test_metrics_values_are_sensible(self) -> None:
        """Basic sanity checks on metric values from both controllers."""
        scenario = steady_state()
        runner = _make_runner()
        report = runner.run(scenario, max_steps=_SHORT_STEPS)

        # Both controllers should produce some comfort (> 0%)
        assert report.metrics_a.comfort_pct >= 0.0
        assert report.metrics_b.comfort_pct >= 0.0

        # Both should have non-negative energy
        if report.metrics_a.energy_kwh is not None:
            assert report.metrics_a.energy_kwh >= 0.0
        if report.metrics_b.energy_kwh is not None:
            assert report.metrics_b.energy_kwh >= 0.0

        # Neither should produce condensation on the steady_state scenario
        assert report.metrics_a.condensation_events == 0
        assert report.metrics_b.condensation_events == 0
