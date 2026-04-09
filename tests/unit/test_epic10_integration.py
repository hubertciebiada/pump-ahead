"""Integration tests for Epic #10 -- MPC optimizer verification gate.

Verifies end-to-end wiring between the three sub-issue modules:
    #48 QP construction (optimizer.py: MPCOptimizer, MPCConfig, MPCResult)
    #49 Solver integration + receding horizon (optimizer.py: MPCController,
        RecedingHorizonResult, _PIDFallback)
    #50 A/B testing MPC vs PID (ab_testing.py: ABTestRunner, ABReport,
        MPCAdapter, PIDAdapter, ControllerAdapter, plot_overlay)

Each test verifies that the output of one module flows correctly into
the next, covering the full MPC pipeline from QP construction through
solver integration, receding horizon control, and A/B testing.

All unit-marked tests are deterministic and fast.  Simulation-marked
tests run longer scenarios to verify acceptance criteria.
"""

from __future__ import annotations

import inspect
import time
from unittest.mock import patch

import numpy as np
import pytest

from pumpahead.ab_testing import (
    ABReport,
    ABTestRunner,
    ControllerAdapter,
    MPCAdapter,
    PIDAdapter,
    plot_overlay,
)
from pumpahead.disturbance_vector import MPC_DT_SECONDS, MPC_HORIZON_STEPS
from pumpahead.estimator import KalmanEstimator
from pumpahead.metrics import SimMetrics, assert_floor_temp_safe
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.optimizer import (
    MPCConfig,
    MPCController,
    MPCInfeasibleError,
    MPCOptimizer,
    MPCResult,
    RecedingHorizonResult,
    _PIDFallback,
)
from pumpahead.scenarios import cold_snap, steady_state
from pumpahead.simulation_log import SimulationLog
from pumpahead.weather import SyntheticWeather


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_siso_model(dt: float = 900.0) -> RCModel:
    """Build a 3R3C SISO model at the given timestep (default 15 min)."""
    params = RCParams(
        C_air=60_000,
        C_slab=3_250_000,
        C_wall=1_500_000,
        R_sf=0.01,
        R_wi=0.02,
        R_wo=0.03,
        R_ve=0.03,
        R_ins=0.01,
        f_conv=0.6,
        f_rad=0.4,
        T_ground=10.0,
        has_split=False,
    )
    return RCModel(params, ModelOrder.THREE, dt=dt)


def _make_mimo_model(dt: float = 900.0) -> RCModel:
    """Build a 3R3C MIMO model at the given timestep (default 15 min)."""
    params = RCParams(
        C_air=60_000,
        C_slab=3_250_000,
        C_wall=1_500_000,
        R_sf=0.01,
        R_wi=0.02,
        R_wo=0.03,
        R_ve=0.03,
        R_ins=0.01,
        f_conv=0.6,
        f_rad=0.4,
        T_ground=10.0,
        has_split=True,
    )
    return RCModel(params, ModelOrder.THREE, dt=dt)


def _make_x0_and_disturbance(
    model: RCModel,
    horizon: int,
    T_out: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a plausible x0 and constant-disturbance matrix for testing."""
    x0 = np.array([20.0, 22.0, 18.0])
    d = np.zeros((horizon, model.n_disturbances))
    d[:, 0] = T_out  # T_out
    return x0, d


# ---------------------------------------------------------------------------
# TestQPToSolverPipeline
# ---------------------------------------------------------------------------


class TestQPToSolverPipeline:
    """Tests that QP construction feeds the solver and controller correctly."""

    @pytest.mark.unit
    def test_qp_result_feeds_mpc_controller(self) -> None:
        """MPCOptimizer.solve() -> MPCResult -> MPCController.step() pipeline."""
        model = _make_siso_model()
        horizon = 10
        config = MPCConfig(horizon=horizon)

        # Step 1: solve via MPCOptimizer
        opt = MPCOptimizer(model, config)
        x0, d = _make_x0_and_disturbance(model, horizon)
        result = opt.solve(x0, d, T_set=21.0)

        assert isinstance(result, MPCResult)
        assert result.x.shape == (horizon + 1, model.n_states)
        assert result.u.shape == (horizon, model.n_inputs)
        assert result.u_floor.shape == (horizon,)
        assert result.u_conv.shape == (horizon,)

        # Step 2: feed the same model into MPCController and call step()
        ctrl = MPCController(model, config)
        rh = ctrl.step(x0, d, T_set=21.0)

        assert isinstance(rh, RecedingHorizonResult)
        assert rh.used_fallback is False
        assert 0.0 <= rh.u_floor_0 <= 1.0
        assert rh.mpc_result is not None

    @pytest.mark.unit
    def test_mimo_qp_feeds_controller_with_split(self) -> None:
        """MIMO (UFH + split) model: optimizer and controller produce valid split output."""
        model = _make_mimo_model()
        horizon = 10
        config = MPCConfig(horizon=horizon)

        opt = MPCOptimizer(model, config)
        x0, d = _make_x0_and_disturbance(model, horizon)
        result = opt.solve(x0, d, T_set=21.0, mode="heating")

        assert result.u_conv.shape == (horizon,)
        # In heating mode, u_conv should be >= -1e-6 (non-negative or near-zero)
        assert np.all(result.u_conv >= -1e-6)

        # Controller step
        ctrl = MPCController(model, config)
        rh = ctrl.step(x0, d, T_set=21.0, mode="heating")

        assert isinstance(rh.u_conv_0, float)
        assert rh.u_conv_0 >= -1e-6

    @pytest.mark.unit
    def test_disturbance_builder_output_feeds_optimizer(
        self,
    ) -> None:
        """DisturbanceBuilder output shape matches what MPCOptimizer expects."""
        from datetime import UTC, datetime

        from pumpahead.disturbance_vector import DisturbanceBuilder, InternalGainProfile
        from pumpahead.solar import EphemerisCalculator, Orientation, WindowConfig
        from pumpahead.solar_gti import GTIModel

        model = _make_siso_model()
        horizon = 10
        config = MPCConfig(horizon=horizon)

        weather = SyntheticWeather.constant(T_out=0.0, GHI=300.0)
        gti = GTIModel()
        ephem = EphemerisCalculator(latitude=50.69, longitude=17.38)
        window = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        profile = InternalGainProfile.constant(100.0)

        builder = DisturbanceBuilder(
            weather=weather,
            gti_model=gti,
            ephemeris=ephem,
            windows=(window,),
            gain_profile=profile,
        )

        start = datetime(2025, 1, 15, 12, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        # The full builder produces MPC_HORIZON_STEPS rows; slice to our test horizon
        d_sliced = d[:horizon]
        assert d_sliced.shape == (horizon, model.n_disturbances)

        opt = MPCOptimizer(model, config)
        x0 = np.array([20.0, 22.0, 18.0])
        result = opt.solve(x0, d_sliced, T_set=21.0)

        assert isinstance(result, MPCResult)
        assert result.status in ("optimal", "optimal_inaccurate")

    @pytest.mark.unit
    def test_estimator_output_feeds_optimizer(
        self,
        model_3r3c: RCModel,
    ) -> None:
        """KalmanEstimator x_hat -> MPCOptimizer.solve() works end-to-end."""
        # Run Kalman estimator for a few steps to get a state estimate
        kf = KalmanEstimator(model_3r3c, has_floor_sensor=False)
        u = np.zeros(model_3r3c.n_inputs)
        d = np.array([5.0, 0.0, 0.0])
        z = np.array([20.0])

        for _ in range(5):
            x_hat = kf.step(u, d, z)

        assert x_hat.shape == (model_3r3c.n_states,)

        # Build an optimizer at MPC dt (900s) with a short horizon
        mpc_model = _make_siso_model(dt=900.0)
        horizon = 10
        config = MPCConfig(horizon=horizon)
        opt = MPCOptimizer(mpc_model, config)

        d_mpc = np.zeros((horizon, mpc_model.n_disturbances))
        d_mpc[:, 0] = 5.0

        result = opt.solve(x_hat, d_mpc, T_set=21.0)

        assert isinstance(result, MPCResult)
        assert np.all(np.isfinite(result.x))
        assert np.all(np.isfinite(result.u))


# ---------------------------------------------------------------------------
# TestControllerToSimulatorPipeline
# ---------------------------------------------------------------------------


class TestControllerToSimulatorPipeline:
    """Tests that MPC controller drives simulation and produces valid metrics."""

    @pytest.mark.unit
    def test_mpc_controller_drives_single_room_simulation(self) -> None:
        """MPCController -> BuildingSimulator -> SimulationLog -> SimMetrics pipeline."""
        from pumpahead.simulated_room import SimulatedRoom
        from pumpahead.simulator import (
            Actions,
            BuildingSimulator,
            HeatPumpMode,
            SplitMode,
        )

        # Build a SISO model at sim dt=60s for the room
        sim_model = RCModel(
            RCParams(
                C_air=60_000,
                C_slab=3_250_000,
                C_wall=1_500_000,
                R_sf=0.01,
                R_wi=0.02,
                R_wo=0.03,
                R_ve=0.03,
                R_ins=0.01,
                f_conv=0.6,
                f_rad=0.4,
                T_ground=10.0,
                has_split=False,
            ),
            ModelOrder.THREE,
            dt=60.0,
        )
        room = SimulatedRoom(
            "test_room",
            sim_model,
            ufh_max_power_w=3000.0,
            split_power_w=0.0,
            q_int_w=50.0,
        )
        weather = SyntheticWeather.constant(T_out=0.0)
        sim = BuildingSimulator(
            [room],
            weather,
            hp_mode=HeatPumpMode.HEATING,
            hp_max_power_w=8000.0,
        )

        # Build MPC controller at 15-min dt
        mpc_model = _make_siso_model(dt=900.0)
        horizon = 10
        config = MPCConfig(horizon=horizon, solver_timeout_s=5.0)
        ctrl = MPCController(mpc_model, config)

        log = SimulationLog()
        n_steps = 120
        solve_interval = 15  # solve every 15 sim steps (= 15 min)
        held_valve = 0.0

        for t in range(n_steps):
            all_meas = sim.get_all_measurements()
            meas = all_meas["test_room"]
            wp = weather.get(float(t))

            # Solve MPC every solve_interval steps
            if t % solve_interval == 0:
                x0 = np.array([meas.T_room, meas.T_slab, meas.T_room])
                d_mpc = np.zeros((horizon, mpc_model.n_disturbances))
                d_mpc[:, 0] = wp.T_out
                d_mpc[:, 2] = 50.0  # Q_int

                rh = ctrl.step(x0, d_mpc, T_set=21.0)
                held_valve = rh.u_floor_0 * 100.0

            actions = Actions(
                valve_position=held_valve,
                split_mode=SplitMode.OFF,
                split_setpoint=0.0,
            )
            sim.step_all({"test_room": actions})
            log.append_from_step(
                t=t,
                measurements=meas,
                actions=actions,
                weather=wp,
                room_name="test_room",
            )

        room_log = log.get_room("test_room")
        metrics = SimMetrics.from_log(
            room_log,
            setpoint=21.0,
            ufh_max_power_w=3000.0,
            split_power_w=0.0,
            dt_minutes=1,
        )

        assert metrics.comfort_pct >= 0
        assert metrics.energy_kwh is not None
        assert metrics.max_floor_temp <= 34.0

    @pytest.mark.unit
    def test_mpc_adapter_runs_through_ab_framework(self) -> None:
        """MPCAdapter + PIDAdapter -> ABTestRunner.run() -> ABReport pipeline."""
        scenario = steady_state()
        runner = ABTestRunner(PIDAdapter(), MPCAdapter())
        report = runner.run(scenario, max_steps=120)

        assert isinstance(report, ABReport)
        assert isinstance(report.metrics_a, SimMetrics)
        assert isinstance(report.metrics_b, SimMetrics)
        assert len(report.log_a) > 0
        assert len(report.log_b) > 0
        assert isinstance(report.deltas, dict)
        assert "comfort_pct" in report.deltas
        assert "energy_kwh" in report.deltas


# ---------------------------------------------------------------------------
# TestAcceptanceCriteria
# ---------------------------------------------------------------------------


class TestAcceptanceCriteria:
    """Explicit verification of Epic #10 acceptance criteria."""

    @pytest.mark.unit
    def test_qp_solve_time_under_100ms(self) -> None:
        """AC: Mean QP solve time < 100ms on 10 warm-start solves with horizon=96."""
        model = _make_siso_model(dt=900.0)
        config = MPCConfig(horizon=96)
        opt = MPCOptimizer(model, config)

        x0, d = _make_x0_and_disturbance(model, 96)

        # Cold start (compile)
        opt.solve(x0, d, T_set=21.0)

        # 10 warm-start solves
        times: list[float] = []
        for _ in range(10):
            t0 = time.perf_counter()
            opt.solve(x0, d, T_set=21.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            times.append(elapsed_ms)

        mean_ms = sum(times) / len(times)
        assert mean_ms < 100.0, (
            f"Mean solve time {mean_ms:.1f}ms exceeds 100ms limit "
            f"(individual: {[f'{t:.1f}' for t in times]})"
        )

    @pytest.mark.simulation
    def test_floor_temp_never_exceeds_34_on_cold_snap(self) -> None:
        """AC: T_floor <= 34 degC on cold_snap scenario (MPC controller)."""
        scenario = cold_snap()
        runner = ABTestRunner(PIDAdapter(), MPCAdapter())
        report = runner.run(scenario, max_steps=2880)

        # Check all rooms in the MPC log (log_b)
        room_names: set[str] = set()
        for rec in report.log_b:
            room_names.add(rec.room_name)

        for room_name in room_names:
            room_log = report.log_b.get_room(room_name)
            assert_floor_temp_safe(room_log, max_temp=34.0)

    @pytest.mark.simulation
    def test_mpc_better_than_pid_on_steady_state(self) -> None:
        """AC: MPC wins on comfort_pct OR energy_kwh on steady_state scenario."""
        scenario = steady_state()
        runner = ABTestRunner(PIDAdapter(), MPCAdapter())
        report = runner.run(scenario, max_steps=2880)

        mpc_wins_comfort = report.a_wins_on("comfort_pct") is False
        mpc_wins_energy = report.a_wins_on("energy_kwh") is False

        assert mpc_wins_comfort or mpc_wins_energy, (
            f"MPC did not win on comfort_pct or energy_kwh. "
            f"PID comfort={report.metrics_a.comfort_pct:.1f}%, "
            f"MPC comfort={report.metrics_b.comfort_pct:.1f}%, "
            f"PID energy={report.metrics_a.energy_kwh}, "
            f"MPC energy={report.metrics_b.energy_kwh}"
        )

    @pytest.mark.unit
    def test_graceful_degradation_solver_fail_to_pid_fallback(self) -> None:
        """AC: Solver failure triggers PID fallback with valid valve output."""
        model = _make_siso_model()
        horizon = 10
        config = MPCConfig(horizon=horizon)
        ctrl = MPCController(model, config)

        x0, d = _make_x0_and_disturbance(model, horizon)

        with patch.object(
            ctrl.optimizer,
            "solve",
            side_effect=RuntimeError("simulated crash"),
        ):
            result = ctrl.step(x0, d, T_set=21.0)

        assert result.used_fallback is True
        assert result.solver_status == "fallback"
        assert 0.0 <= result.u_floor_0 <= 1.0
        assert result.mpc_result is None

    @pytest.mark.unit
    def test_u_conv_zero_for_rooms_without_split(self) -> None:
        """AC: SISO (has_split=False) rooms produce zero split output."""
        model = _make_siso_model()
        horizon = 10
        config = MPCConfig(horizon=horizon)

        # Optimizer level
        opt = MPCOptimizer(model, config)
        x0, d = _make_x0_and_disturbance(model, horizon)
        result = opt.solve(x0, d, T_set=21.0)

        assert np.all(result.u_conv == 0.0), (
            f"u_conv should be all zeros for SISO, got max={np.max(result.u_conv)}"
        )

        # Controller level
        ctrl = MPCController(model, config)
        rh = ctrl.step(x0, d, T_set=21.0)

        assert rh.u_conv_0 == 0.0, (
            f"u_conv_0 should be 0.0 for SISO, got {rh.u_conv_0}"
        )


# ---------------------------------------------------------------------------
# TestArchitecturalIntegrity
# ---------------------------------------------------------------------------


class TestArchitecturalIntegrity:
    """Verify DAG dependency direction, no circular imports, no HA imports."""

    @pytest.mark.unit
    def test_optimizer_does_not_import_controller_or_ab_testing(self) -> None:
        """optimizer.py must not import controller.py or ab_testing.py."""
        import pumpahead.optimizer as opt_mod

        source = inspect.getsource(opt_mod)

        assert "from pumpahead.controller" not in source, (
            "optimizer.py must not import from pumpahead.controller"
        )
        assert "from pumpahead.ab_testing" not in source, (
            "optimizer.py must not import from pumpahead.ab_testing"
        )

    @pytest.mark.unit
    def test_controller_does_not_import_ab_testing(self) -> None:
        """controller.py must not import ab_testing.py."""
        import pumpahead.controller as ctrl_mod

        source = inspect.getsource(ctrl_mod)

        assert "from pumpahead.ab_testing" not in source, (
            "controller.py must not import from pumpahead.ab_testing"
        )

    @pytest.mark.unit
    def test_no_homeassistant_imports_in_mpc_modules(self) -> None:
        """None of the MPC modules import homeassistant."""
        import pumpahead.ab_testing as ab_mod
        import pumpahead.controller as ctrl_mod
        import pumpahead.disturbance_vector as dv_mod
        import pumpahead.optimizer as opt_mod

        for mod_name, mod in [
            ("optimizer", opt_mod),
            ("controller", ctrl_mod),
            ("ab_testing", ab_mod),
            ("disturbance_vector", dv_mod),
        ]:
            source = inspect.getsource(mod)
            assert "homeassistant" not in source, (
                f"{mod_name} must not import homeassistant"
            )

    @pytest.mark.unit
    def test_all_mpc_public_symbols_exported_from_init(self) -> None:
        """All MPC public symbols are in pumpahead.__init__ and __all__."""
        import pumpahead

        expected_symbols = [
            # From optimizer.py
            "MPCOptimizer",
            "MPCController",
            "MPCConfig",
            "MPCResult",
            "RecedingHorizonResult",
            "MPCInfeasibleError",
            # From ab_testing.py
            "MPCAdapter",
            "ABTestRunner",
            "ABReport",
            "PIDAdapter",
            "ControllerAdapter",
            "plot_overlay",
        ]

        for symbol in expected_symbols:
            assert hasattr(pumpahead, symbol), (
                f"{symbol} not exported from pumpahead.__init__"
            )
            assert symbol in pumpahead.__all__, (
                f"{symbol} not in pumpahead.__all__"
            )

    @pytest.mark.unit
    def test_optimizer_module_does_not_import_simulator(self) -> None:
        """optimizer.py must not import simulator or simulated_room."""
        import pumpahead.optimizer as opt_mod

        source = inspect.getsource(opt_mod)

        assert "from pumpahead.simulator" not in source, (
            "optimizer.py must not import from pumpahead.simulator"
        )
        assert "from pumpahead.simulated_room" not in source, (
            "optimizer.py must not import from pumpahead.simulated_room"
        )
