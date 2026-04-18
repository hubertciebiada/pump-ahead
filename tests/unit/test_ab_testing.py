"""Unit tests for pumpahead.ab_testing."""

from __future__ import annotations

import dataclasses
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

import matplotlib
import numpy as np
import pytest

from pumpahead.ab_testing import (
    _HIGHER_IS_BETTER,
    ABReport,
    ABTestRunner,
    ControllerAdapter,
    MPCAdapter,
    PIDAdapter,
    plot_overlay,
)
from pumpahead.disturbance_vector import MPC_DT_SECONDS, MPC_HORIZON_STEPS
from pumpahead.metrics import SimMetrics
from pumpahead.optimizer import MPCConfig, MPCInfeasibleError
from pumpahead.scenarios import steady_state
from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.weather import WeatherPoint

matplotlib.use("Agg")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_measurements(
    *,
    T_room: float = 21.0,
    T_slab: float = 22.0,
    T_outdoor: float = 0.0,
    valve_pos: float = 50.0,
    hp_mode: HeatPumpMode = HeatPumpMode.HEATING,
    is_cwu_active: bool = False,
    humidity: float = 50.0,
) -> Measurements:
    """Build a ``Measurements`` snapshot with sensible heating defaults."""
    return Measurements(
        T_room=T_room,
        T_slab=T_slab,
        T_outdoor=T_outdoor,
        valve_pos=valve_pos,
        hp_mode=hp_mode,
        is_cwu_active=is_cwu_active,
        humidity=humidity,
    )


def _make_weather(
    *,
    T_out: float = 0.0,
    GHI: float = 0.0,
    wind_speed: float = 0.0,
    humidity: float = 50.0,
) -> WeatherPoint:
    """Build a ``WeatherPoint`` with constant conditions."""
    return WeatherPoint(
        T_out=T_out,
        GHI=GHI,
        wind_speed=wind_speed,
        humidity=humidity,
    )


@pytest.fixture
def mini_scenario():
    """Return a fresh ``steady_state`` scenario.

    ``steady_state`` is the canonical 3R3C single-room ``well_insulated``
    fixture used across the suite.  Tests cap simulation length via
    ``max_steps`` rather than mutating ``duration_minutes``.
    """
    return steady_state()


# ---------------------------------------------------------------------------
# TestPIDAdapter
# ---------------------------------------------------------------------------


class TestPIDAdapter:
    """Tests for :class:`PIDAdapter`."""

    @pytest.mark.unit
    def test_name_property(self) -> None:
        """``name`` is the literal ``'PID'``."""
        assert PIDAdapter().name == "PID"

    @pytest.mark.unit
    def test_compute_actions_returns_actions_in_heating(self, mini_scenario) -> None:
        """In heating mode the adapter returns a valid ``Actions`` for UFH."""
        adapter = PIDAdapter()
        meas = _make_measurements(T_room=18.0)
        wp = _make_weather()

        actions = adapter.compute_actions(
            t=0,
            measurements=meas,
            weather=wp,
            scenario=mini_scenario,
            room_name="main",
        )

        assert isinstance(actions, Actions)
        assert actions.split_mode is SplitMode.OFF
        assert 0.0 <= actions.valve_position <= 100.0
        # Below setpoint in heating: valve floor must be enforced
        assert actions.valve_position >= mini_scenario.controller.valve_floor_pct

    @pytest.mark.unit
    def test_compute_actions_below_setpoint_increases_valve(
        self, mini_scenario
    ) -> None:
        """Cold room produces a larger valve opening than a warm room."""
        cold_adapter = PIDAdapter()
        warm_adapter = PIDAdapter()
        wp = _make_weather()

        cold_actions = cold_adapter.compute_actions(
            t=0,
            measurements=_make_measurements(T_room=17.0),
            weather=wp,
            scenario=mini_scenario,
            room_name="main",
        )
        warm_actions = warm_adapter.compute_actions(
            t=0,
            measurements=_make_measurements(T_room=22.0),
            weather=wp,
            scenario=mini_scenario,
            room_name="main",
        )

        assert cold_actions.valve_position >= warm_actions.valve_position

    @pytest.mark.unit
    def test_pid_instance_cached_per_scenario(self, mini_scenario) -> None:
        """A second call reuses the cached PID; a different scenario adds a new one."""
        adapter = PIDAdapter()
        wp = _make_weather()
        meas = _make_measurements()

        adapter.compute_actions(
            t=0,
            measurements=meas,
            weather=wp,
            scenario=mini_scenario,
            room_name="main",
        )
        adapter.compute_actions(
            t=1,
            measurements=meas,
            weather=wp,
            scenario=mini_scenario,
            room_name="main",
        )
        assert len(adapter._pids) == 1

        other = dataclasses.replace(mini_scenario, name="other_scenario")
        adapter.compute_actions(
            t=0,
            measurements=meas,
            weather=wp,
            scenario=other,
            room_name="main",
        )
        assert len(adapter._pids) == 2

    @pytest.mark.unit
    def test_reset_clears_state(self, mini_scenario) -> None:
        """``reset()`` empties the per-scenario PID cache."""
        adapter = PIDAdapter()
        adapter.compute_actions(
            t=0,
            measurements=_make_measurements(),
            weather=_make_weather(),
            scenario=mini_scenario,
            room_name="main",
        )
        assert adapter._pids  # populated

        adapter.reset()
        assert adapter._pids == {}

    @pytest.mark.unit
    def test_valve_floor_not_applied_in_cooling_mode(self, mini_scenario) -> None:
        """The heating valve floor is bypassed when ``hp_mode == COOLING``."""
        adapter = PIDAdapter()
        # In cooling mode, error = setpoint - T_room = 21 - 15 = +6 still
        # produces a positive PID output, but the floor must not bump
        # tiny outputs upward.  Use very small kp to keep PID near zero.
        scenario = dataclasses.replace(
            mini_scenario,
            controller=dataclasses.replace(
                mini_scenario.controller, kp=0.0, ki=0.0, kd=0.0
            ),
        )
        actions = adapter.compute_actions(
            t=0,
            measurements=_make_measurements(T_room=15.0, hp_mode=HeatPumpMode.COOLING),
            weather=_make_weather(),
            scenario=scenario,
            room_name="main",
        )
        # PID output is 0; floor would have bumped to valve_floor_pct in
        # heating mode, but cooling mode bypasses the floor.
        assert actions.valve_position == 0.0

    @pytest.mark.unit
    def test_satisfies_controller_adapter_protocol(self) -> None:
        """``PIDAdapter`` is a structural ``ControllerAdapter``."""
        assert isinstance(PIDAdapter(), ControllerAdapter)


# ---------------------------------------------------------------------------
# TestMPCAdapter
# ---------------------------------------------------------------------------


class TestMPCAdapter:
    """Tests for :class:`MPCAdapter`."""

    @pytest.mark.unit
    def test_name_property(self) -> None:
        """``name`` is the literal ``'MPC'``."""
        assert MPCAdapter().name == "MPC"

    @pytest.mark.unit
    def test_satisfies_controller_adapter_protocol(self) -> None:
        """``MPCAdapter`` is a structural ``ControllerAdapter``."""
        assert isinstance(MPCAdapter(), ControllerAdapter)

    @pytest.mark.unit
    def test_default_constructor_uses_module_constants(self) -> None:
        """Default dt/horizon come from ``disturbance_vector`` module."""
        adapter = MPCAdapter()
        assert adapter._mpc_dt_seconds == MPC_DT_SECONDS
        assert adapter._horizon_steps == MPC_HORIZON_STEPS
        # 900 // 60 == 15 minutes between solves
        assert adapter._solve_interval == 15

    @pytest.mark.unit
    def test_custom_mpc_config_override_used(self, mini_scenario) -> None:
        """A user-supplied ``MPCConfig`` overrides the auto-built one."""
        override = MPCConfig(horizon=12, w_comfort=2.0, solver_timeout_s=5.0)
        adapter = MPCAdapter(mpc_config=override, horizon_steps=12)
        # Trigger controller construction
        adapter._get_controller(mini_scenario, "main")

        key = f"{mini_scenario.name}:main"
        assert adapter._controllers[key]._config is override  # noqa: SLF001

    @pytest.mark.unit
    def test_get_controller_unknown_room_raises_value_error(
        self, mini_scenario
    ) -> None:
        """Unknown room name raises ``ValueError``."""
        adapter = MPCAdapter()
        with pytest.raises(ValueError, match="not found in scenario"):
            adapter._get_controller(mini_scenario, "ghost_room")

    @pytest.mark.unit
    def test_build_disturbance_shape_and_values(self, mini_scenario) -> None:
        """Disturbance matrix has shape ``(horizon, 3)`` with expected columns."""
        adapter = MPCAdapter()
        # _build_disturbance does not require _get_controller to have run.
        d = adapter._build_disturbance(t=0, scenario=mini_scenario, room_name="main")

        assert d.shape == (MPC_HORIZON_STEPS, 3)
        # Steady-state weather is constant T_out=0.0
        assert np.all(d[:, 0] == 0.0)
        # Q_sol intentionally zero (conservative)
        assert np.all(d[:, 1] == 0.0)
        # Q_int matches well_insulated salon (100.0 W)
        assert np.all(d[:, 2] == 100.0)

    @pytest.mark.unit
    def test_compute_actions_returns_valid_valve_in_heating(
        self, mini_scenario
    ) -> None:
        """The first call solves MPC and yields a valve in [0, 100]."""
        adapter = MPCAdapter()
        actions = adapter.compute_actions(
            t=0,
            measurements=_make_measurements(T_room=19.0, T_slab=20.0),
            weather=_make_weather(),
            scenario=mini_scenario,
            room_name="main",
        )
        assert isinstance(actions, Actions)
        assert actions.split_mode is SplitMode.OFF
        assert 0.0 <= actions.valve_position <= 100.0

    @pytest.mark.unit
    def test_solve_interval_zero_order_hold(self, mini_scenario) -> None:
        """MPC solves on the first call and then once every ``solve_interval``."""
        adapter = MPCAdapter()
        # First call to populate ``_controllers`` via the real solver.
        adapter.compute_actions(
            t=0,
            measurements=_make_measurements(T_room=19.0, T_slab=20.0),
            weather=_make_weather(),
            scenario=mini_scenario,
            room_name="main",
        )
        key = f"{mini_scenario.name}:main"
        ctrl = adapter._controllers[key]
        # After the first solve, the counter resets to 0.
        assert adapter._steps_since_solve[key] == 0

        # Patch ``ctrl.step`` and call adapter.compute_actions
        # ``solve_interval - 1`` more times — none should trigger solve.
        with patch.object(ctrl, "step", wraps=ctrl.step) as mock_step:
            for i in range(adapter._solve_interval - 1):
                adapter.compute_actions(
                    t=i + 1,
                    measurements=_make_measurements(T_room=19.0, T_slab=20.0),
                    weather=_make_weather(),
                    scenario=mini_scenario,
                    room_name="main",
                )
            assert mock_step.call_count == 0
            # Counter should now be solve_interval - 1 (incremented but not reset)
            assert adapter._steps_since_solve[key] == adapter._solve_interval - 1

            # The next call hits the threshold and solves once.
            adapter.compute_actions(
                t=adapter._solve_interval,
                measurements=_make_measurements(T_room=19.0, T_slab=20.0),
                weather=_make_weather(),
                scenario=mini_scenario,
                room_name="main",
            )
            assert mock_step.call_count == 1

    @pytest.mark.unit
    def test_mpc_adapter_fallback_on_infeasible(self, mini_scenario) -> None:
        """``MPCInfeasibleError`` from the optimizer is handled gracefully."""
        adapter = MPCAdapter()
        # First call: real solve to populate ``_controllers``.
        adapter.compute_actions(
            t=0,
            measurements=_make_measurements(T_room=19.0, T_slab=20.0),
            weather=_make_weather(),
            scenario=mini_scenario,
            room_name="main",
        )
        key = f"{mini_scenario.name}:main"
        ctrl = adapter._controllers[key]

        # Force the next compute_actions call to take the solve branch.
        adapter._steps_since_solve[key] = adapter._solve_interval

        with patch.object(
            ctrl.optimizer,
            "solve",
            side_effect=MPCInfeasibleError("forced infeasible"),
        ):
            actions = adapter.compute_actions(
                t=adapter._solve_interval,
                measurements=_make_measurements(T_room=19.0, T_slab=20.0),
                weather=_make_weather(),
                scenario=mini_scenario,
                room_name="main",
            )
        # No exception leaked; valve still in valid range thanks to PID fallback.
        assert isinstance(actions, Actions)
        assert 0.0 <= actions.valve_position <= 100.0

    @pytest.mark.unit
    def test_mpc_adapter_fallback_on_generic_solver_exception(
        self, mini_scenario
    ) -> None:
        """A generic solver ``RuntimeError`` is also caught by the fallback."""
        adapter = MPCAdapter()
        adapter.compute_actions(
            t=0,
            measurements=_make_measurements(T_room=19.0, T_slab=20.0),
            weather=_make_weather(),
            scenario=mini_scenario,
            room_name="main",
        )
        key = f"{mini_scenario.name}:main"
        ctrl = adapter._controllers[key]
        adapter._steps_since_solve[key] = adapter._solve_interval

        with patch.object(
            ctrl.optimizer,
            "solve",
            side_effect=RuntimeError("simulated crash"),
        ):
            actions = adapter.compute_actions(
                t=adapter._solve_interval,
                measurements=_make_measurements(T_room=19.0, T_slab=20.0),
                weather=_make_weather(),
                scenario=mini_scenario,
                room_name="main",
            )
        assert isinstance(actions, Actions)
        assert 0.0 <= actions.valve_position <= 100.0

    @pytest.mark.unit
    def test_reset_clears_all_state(self, mini_scenario) -> None:
        """``reset()`` clears controllers, held actions, and solve counters."""
        adapter = MPCAdapter()
        adapter.compute_actions(
            t=0,
            measurements=_make_measurements(T_room=19.0, T_slab=20.0),
            weather=_make_weather(),
            scenario=mini_scenario,
            room_name="main",
        )
        assert adapter._controllers
        assert adapter._held_action
        assert adapter._steps_since_solve

        adapter.reset()
        assert adapter._controllers == {}
        assert adapter._held_action == {}
        assert adapter._steps_since_solve == {}


# ---------------------------------------------------------------------------
# TestABReport
# ---------------------------------------------------------------------------


def _make_metrics(
    *,
    comfort_pct: float = 90.0,
    max_overshoot: float = 0.5,
    max_undershoot: float = 0.5,
    mean_deviation: float = 0.2,
    split_runtime_pct: float = 0.0,
    energy_kwh: float | None = 5.0,
    peak_power_w: float | None = 4000.0,
    floor_energy_pct: float | None = 100.0,
    mean_cop: float | None = None,
    condensation_events: int = 0,
    max_floor_temp: float = 30.0,
    min_floor_temp: float = 20.0,
    mode_switches: int = 0,
) -> SimMetrics:
    """Build a ``SimMetrics`` instance with overridable defaults."""
    return SimMetrics(
        comfort_pct=comfort_pct,
        max_overshoot=max_overshoot,
        max_undershoot=max_undershoot,
        mean_deviation=mean_deviation,
        split_runtime_pct=split_runtime_pct,
        energy_kwh=energy_kwh,
        peak_power_w=peak_power_w,
        floor_energy_pct=floor_energy_pct,
        mean_cop=mean_cop,
        condensation_events=condensation_events,
        max_floor_temp=max_floor_temp,
        min_floor_temp=min_floor_temp,
        mode_switches=mode_switches,
    )


def _make_report(metrics_a: SimMetrics, metrics_b: SimMetrics) -> ABReport:
    """Build an ``ABReport`` from two ``SimMetrics`` instances."""
    return ABReport(
        controller_a_name="A",
        controller_b_name="B",
        scenario_name="test",
        metrics_a=metrics_a,
        metrics_b=metrics_b,
        deltas=metrics_a.compare(metrics_b),
        log_a=SimulationLog(),
        log_b=SimulationLog(),
    )


class TestABReport:
    """Tests for :class:`ABReport`."""

    @pytest.mark.unit
    def test_a_wins_on_higher_is_better_metric_a_wins(self) -> None:
        """Higher ``comfort_pct`` for A means A wins."""
        report = _make_report(
            _make_metrics(comfort_pct=95.0), _make_metrics(comfort_pct=85.0)
        )
        assert report.a_wins_on("comfort_pct") is True

    @pytest.mark.unit
    def test_a_wins_on_higher_is_better_metric_b_wins(self) -> None:
        """Lower ``comfort_pct`` for A means B wins."""
        report = _make_report(
            _make_metrics(comfort_pct=80.0), _make_metrics(comfort_pct=90.0)
        )
        assert report.a_wins_on("comfort_pct") is False

    @pytest.mark.unit
    def test_a_wins_on_lower_is_better_metric_a_wins(self) -> None:
        """Lower ``energy_kwh`` for A means A wins."""
        report = _make_report(
            _make_metrics(energy_kwh=3.0), _make_metrics(energy_kwh=5.0)
        )
        assert report.a_wins_on("energy_kwh") is True

    @pytest.mark.unit
    def test_a_wins_on_lower_is_better_metric_b_wins(self) -> None:
        """Higher ``energy_kwh`` for A means B wins."""
        report = _make_report(
            _make_metrics(energy_kwh=7.0), _make_metrics(energy_kwh=4.0)
        )
        assert report.a_wins_on("energy_kwh") is False

    @pytest.mark.unit
    def test_a_wins_on_equal_returns_false(self) -> None:
        """A delta of exactly zero returns ``False`` (not ``None``)."""
        report = _make_report(
            _make_metrics(comfort_pct=90.0), _make_metrics(comfort_pct=90.0)
        )
        # higher_is_better=True, delta=0.0, so 0 > 0 is False
        assert report.a_wins_on("comfort_pct") is False

    @pytest.mark.unit
    def test_a_wins_on_unknown_metric_returns_none(self) -> None:
        """An unknown metric name yields ``None``."""
        report = _make_report(_make_metrics(), _make_metrics())
        assert report.a_wins_on("not_a_real_metric") is None

    @pytest.mark.unit
    def test_a_wins_on_none_delta_returns_none(self) -> None:
        """``None`` energy on either side propagates to ``None`` via delta."""
        report = _make_report(
            _make_metrics(energy_kwh=None),
            _make_metrics(energy_kwh=None),
        )
        assert report.a_wins_on("energy_kwh") is None

    @pytest.mark.unit
    @pytest.mark.parametrize("field_name", [f.name for f in fields(SimMetrics)])
    def test_higher_is_better_lookup_covers_all_metrics(self, field_name: str) -> None:
        """Every ``SimMetrics`` field must have an entry in ``_HIGHER_IS_BETTER``."""
        assert field_name in _HIGHER_IS_BETTER

    @pytest.mark.unit
    def test_summary_table_contains_controller_names(self) -> None:
        """The summary table mentions both controller names and key columns."""
        report = _make_report(_make_metrics(), _make_metrics(comfort_pct=80.0))
        table = report.summary_table()
        assert "A" in table
        assert "B" in table
        assert "Metric" in table
        assert "Delta" in table
        assert "Winner" in table

    @pytest.mark.unit
    def test_summary_table_has_row_per_metric(self) -> None:
        """Header + separator + one row per ``SimMetrics`` field."""
        report = _make_report(_make_metrics(), _make_metrics())
        lines = report.summary_table().splitlines()
        assert len(lines) == 2 + len(fields(SimMetrics))

    @pytest.mark.unit
    def test_summary_table_handles_none_metric_values(self) -> None:
        """``None`` energy values render as ``N/A`` in the table."""
        report = _make_report(
            _make_metrics(energy_kwh=None, peak_power_w=None, floor_energy_pct=None),
            _make_metrics(energy_kwh=None, peak_power_w=None, floor_energy_pct=None),
        )
        table = report.summary_table()
        # The energy_kwh row contains a metric label and N/A markers.
        energy_row = next(
            line for line in table.splitlines() if line.startswith("energy_kwh")
        )
        assert "N/A" in energy_row

    @pytest.mark.unit
    def test_report_is_frozen_dataclass(self) -> None:
        """``ABReport`` is immutable; assigning attributes raises."""
        report = _make_report(_make_metrics(), _make_metrics())
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.controller_a_name = "X"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestABTestRunner
# ---------------------------------------------------------------------------


class TestABTestRunner:
    """Tests for :class:`ABTestRunner`."""

    @pytest.mark.unit
    def test_init_stores_controllers(self) -> None:
        """Both adapters are stored on the runner instance."""
        a, b = PIDAdapter(), PIDAdapter()
        runner = ABTestRunner(a, b)
        assert runner._controller_a is a
        assert runner._controller_b is b

    @pytest.mark.unit
    def test_build_simulator_uses_scenario_settings(self, mini_scenario) -> None:
        """``_build_simulator`` returns a heating-mode simulator with one room."""
        sim = ABTestRunner._build_simulator(mini_scenario)
        assert sim.hp_mode is HeatPumpMode.HEATING
        meas = sim.get_all_measurements()
        assert "main" in meas

    @pytest.mark.unit
    def test_run_returns_abreport_with_correct_names(self, mini_scenario) -> None:
        """``run`` returns an ``ABReport`` populated with both controllers."""
        runner = ABTestRunner(PIDAdapter(), PIDAdapter())
        report = runner.run(mini_scenario, max_steps=10)

        assert isinstance(report, ABReport)
        assert report.controller_a_name == "PID"
        assert report.controller_b_name == "PID"
        assert report.scenario_name == mini_scenario.name
        assert isinstance(report.metrics_a, SimMetrics)
        assert isinstance(report.metrics_b, SimMetrics)
        assert isinstance(report.log_a, SimulationLog)
        assert isinstance(report.log_b, SimulationLog)
        assert len(report.log_a) > 0
        assert len(report.log_b) > 0

    @pytest.mark.unit
    def test_run_max_steps_caps_simulation(self, mini_scenario) -> None:
        """``max_steps`` truncates the simulation horizon."""
        runner = ABTestRunner(PIDAdapter(), PIDAdapter())
        report = runner.run(mini_scenario, max_steps=5)
        assert len(report.log_a.get_room("main")) == 5
        assert len(report.log_b.get_room("main")) == 5

    @pytest.mark.unit
    def test_run_max_steps_none_uses_full_duration(self, mini_scenario) -> None:
        """Passing ``max_steps=None`` runs for ``scenario.duration_minutes``."""
        short_scenario = dataclasses.replace(mini_scenario, duration_minutes=8)
        runner = ABTestRunner(PIDAdapter(), PIDAdapter())
        report = runner.run(short_scenario, max_steps=None)
        assert len(report.log_a.get_room("main")) == 8

    @pytest.mark.unit
    def test_run_deltas_dict_populated(self, mini_scenario) -> None:
        """The deltas dict contains an entry for every ``SimMetrics`` field."""
        runner = ABTestRunner(PIDAdapter(), PIDAdapter())
        report = runner.run(mini_scenario, max_steps=5)
        assert set(report.deltas.keys()) == {f.name for f in fields(SimMetrics)}

    @pytest.mark.unit
    def test_run_two_pid_adapters_produces_identical_metrics(
        self, mini_scenario
    ) -> None:
        """Two PID adapters on the same scenario yield identical metrics."""
        runner = ABTestRunner(PIDAdapter(), PIDAdapter())
        report = runner.run(mini_scenario, max_steps=10)
        assert report.metrics_a == report.metrics_b
        for delta in report.deltas.values():
            assert delta is None or delta == 0.0

    @pytest.mark.unit
    def test_mode_map_cooling_uses_cooling_hp_mode(self, mini_scenario) -> None:
        """A cooling-mode scenario produces a cooling simulator."""
        cooling_scenario = dataclasses.replace(mini_scenario, mode="cooling")
        sim = ABTestRunner._build_simulator(cooling_scenario)
        assert sim.hp_mode is HeatPumpMode.COOLING

    @pytest.mark.unit
    def test_mode_map_auto_falls_back_to_heating(self, mini_scenario) -> None:
        """``mode='auto'`` defaults the simulator to heating mode."""
        auto_scenario = dataclasses.replace(mini_scenario, mode="auto")
        sim = ABTestRunner._build_simulator(auto_scenario)
        assert sim.hp_mode is HeatPumpMode.HEATING

    @pytest.mark.unit
    def test_run_max_steps_cap_below_duration(self, mini_scenario) -> None:
        """``min(max_steps, duration_minutes)`` honors the smaller bound."""
        # mini_scenario.duration_minutes == 2880; cap to 3 steps
        runner = ABTestRunner(PIDAdapter(), PIDAdapter())
        report = runner.run(mini_scenario, max_steps=3)
        assert len(report.log_a.get_room("main")) == 3

    @pytest.mark.unit
    def test_run_with_mpc_and_pid_smoke(self, mini_scenario) -> None:
        """Smoke test: the MPC vs PID combination runs end-to-end."""
        runner = ABTestRunner(PIDAdapter(), MPCAdapter())
        report = runner.run(mini_scenario, max_steps=20)
        assert report.controller_a_name == "PID"
        assert report.controller_b_name == "MPC"
        assert len(report.log_a.get_room("main")) == 20
        assert len(report.log_b.get_room("main")) == 20


# ---------------------------------------------------------------------------
# TestPlotOverlay
# ---------------------------------------------------------------------------


def _make_overlay_report(mini_scenario) -> ABReport:
    """Build an ``ABReport`` from a tiny PID/PID run for plotting tests."""
    runner = ABTestRunner(PIDAdapter(), PIDAdapter())
    return runner.run(mini_scenario, max_steps=5)


class TestPlotOverlay:
    """Tests for :func:`plot_overlay`."""

    @pytest.mark.unit
    def test_returns_figure(self, mini_scenario) -> None:
        """The function returns a matplotlib ``Figure``."""
        import matplotlib.figure
        import matplotlib.pyplot as plt

        report = _make_overlay_report(mini_scenario)
        fig = plot_overlay(report)
        assert isinstance(fig, matplotlib.figure.Figure)
        plt.close(fig)

    @pytest.mark.unit
    def test_save_to_file(self, mini_scenario, tmp_path: Path) -> None:
        """Saving with ``save_path`` writes a non-empty PNG."""
        import matplotlib.pyplot as plt

        report = _make_overlay_report(mini_scenario)
        save_path = tmp_path / "overlay.png"
        fig = plot_overlay(report, save_path=str(save_path))
        assert save_path.exists()
        assert save_path.stat().st_size > 0
        plt.close(fig)

    @pytest.mark.unit
    def test_explicit_room_name_used(self, mini_scenario) -> None:
        """An explicit ``room_name`` is accepted without error."""
        import matplotlib.pyplot as plt

        report = _make_overlay_report(mini_scenario)
        fig = plot_overlay(report, room_name="main")
        plt.close(fig)

    @pytest.mark.unit
    def test_empty_log_raises_value_error(self) -> None:
        """An ``ABReport`` with empty logs raises ``ValueError``."""
        report = ABReport(
            controller_a_name="A",
            controller_b_name="B",
            scenario_name="empty",
            metrics_a=_make_metrics(),
            metrics_b=_make_metrics(),
            deltas={},
            log_a=SimulationLog(),
            log_b=SimulationLog(),
        )
        with pytest.raises(ValueError, match="Cannot determine room name"):
            plot_overlay(report)
