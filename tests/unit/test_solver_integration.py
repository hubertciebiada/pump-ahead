"""Unit tests for MPCController (solver integration + receding horizon).

Tests cover:
- MPCController construction and property access
- Receding-horizon step() method correctness
- Warm start from previous solution
- Solver timeout configuration and validation
- PID fallback behaviour on solver failure
- _PIDFallback internal logic
- MPCConfig solver_timeout_s field
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from pumpahead.model import RCModel
from pumpahead.optimizer import (
    MPCConfig,
    MPCController,
    MPCOptimizer,
    MPCResult,
    RecedingHorizonResult,
    _PIDFallback,
)

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def short_config() -> MPCConfig:
    """Short-horizon MPC config for fast unit tests."""
    return MPCConfig(horizon=10, solver_timeout_s=0.1)


@pytest.fixture()
def controller_3r3c_siso(
    model_3r3c: RCModel,
    short_config: MPCConfig,
) -> MPCController:
    """3R3C SISO (UFH-only) MPCController with short horizon."""
    return MPCController(model_3r3c, short_config)


@pytest.fixture()
def controller_3r3c_mimo(
    model_3r3c_mimo: RCModel,
    short_config: MPCConfig,
) -> MPCController:
    """3R3C MIMO (UFH + split) MPCController with short horizon."""
    return MPCController(model_3r3c_mimo, short_config)


@pytest.fixture()
def zero_disturbance_3r3c() -> np.ndarray:
    """10-step zero disturbance for 3R3C (3 disturbance channels)."""
    return np.zeros((10, 3))


@pytest.fixture()
def constant_disturbance_3r3c() -> np.ndarray:
    """10-step disturbance for 3R3C: T_out=5C, no solar, no internal."""
    return np.column_stack([np.full(10, 5.0), np.zeros(10), np.zeros(10)])


# ---------------------------------------------------------------------------
# TestMPCControllerConstruction
# ---------------------------------------------------------------------------


class TestMPCControllerConstruction:
    """Tests that MPCController builds correctly."""

    @pytest.mark.unit
    def test_builds_without_error(
        self,
        controller_3r3c_siso: MPCController,
    ) -> None:
        """Controller constructs without raising."""
        assert controller_3r3c_siso is not None

    @pytest.mark.unit
    def test_config_accessible(
        self,
        controller_3r3c_siso: MPCController,
        short_config: MPCConfig,
    ) -> None:
        """Config property returns the config passed at construction."""
        assert controller_3r3c_siso.config is short_config

    @pytest.mark.unit
    def test_has_split_siso(
        self,
        controller_3r3c_siso: MPCController,
    ) -> None:
        """SISO controller reports has_split=False."""
        assert controller_3r3c_siso.has_split is False

    @pytest.mark.unit
    def test_has_split_mimo(
        self,
        controller_3r3c_mimo: MPCController,
    ) -> None:
        """MIMO controller reports has_split=True."""
        assert controller_3r3c_mimo.has_split is True

    @pytest.mark.unit
    def test_default_config_when_none(
        self,
        model_3r3c: RCModel,
    ) -> None:
        """When config=None, default MPCConfig is used."""
        ctrl = MPCController(model_3r3c)
        assert ctrl.config.horizon == 96
        assert ctrl.config.solver_timeout_s == 0.1

    @pytest.mark.unit
    def test_optimizer_accessible(
        self,
        controller_3r3c_siso: MPCController,
    ) -> None:
        """Underlying optimizer is accessible."""
        assert isinstance(controller_3r3c_siso.optimizer, MPCOptimizer)


# ---------------------------------------------------------------------------
# TestRecedingHorizonStep
# ---------------------------------------------------------------------------


class TestRecedingHorizonStep:
    """Tests for the step() method correctness."""

    @pytest.mark.unit
    def test_step_returns_valid_result(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """step() returns a RecedingHorizonResult with correct types."""
        x0 = np.array([20.0, 20.0, 20.0])
        result = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert isinstance(result, RecedingHorizonResult)
        assert isinstance(result.u_floor_0, float)
        assert isinstance(result.u_conv_0, float)
        assert isinstance(result.solve_time_ms, float)
        assert result.used_fallback is False
        assert "optimal" in result.solver_status

    @pytest.mark.unit
    def test_first_action_bounded(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """First-step valve command is within [0, 1]."""
        x0 = np.array([18.0, 18.0, 18.0])
        result = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert 0.0 - 1e-6 <= result.u_floor_0 <= 1.0 + 1e-6

    @pytest.mark.unit
    def test_mpc_result_present_on_success(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """On successful solve, mpc_result is not None."""
        x0 = np.array([20.0, 20.0, 20.0])
        result = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result.mpc_result is not None
        assert isinstance(result.mpc_result, MPCResult)

    @pytest.mark.unit
    def test_x_predicted_present_on_success(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """On successful solve, x_predicted is present with correct shape."""
        x0 = np.array([20.0, 20.0, 20.0])
        result = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result.x_predicted is not None
        assert result.x_predicted.shape == (11, 3)  # N+1=11, n=3

    @pytest.mark.unit
    def test_consecutive_steps_succeed(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Multiple consecutive steps all produce valid results."""
        x0 = np.array([20.0, 20.0, 20.0])
        for _ in range(3):
            result = controller_3r3c_siso.step(
                x0=x0,
                d=constant_disturbance_3r3c,
                T_set=21.0,
            )
            assert result.used_fallback is False
            assert 0.0 - 1e-6 <= result.u_floor_0 <= 1.0 + 1e-6

    @pytest.mark.unit
    def test_mimo_step_returns_split_action(
        self,
        controller_3r3c_mimo: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """MIMO step returns non-trivial u_conv_0 when room needs heating."""
        x0 = np.array([16.0, 16.0, 16.0])
        result = controller_3r3c_mimo.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert isinstance(result.u_conv_0, float)
        # In heating mode, u_conv >= 0
        assert result.u_conv_0 >= -1e-6

    @pytest.mark.unit
    def test_u_conv_zero_for_siso(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """SISO controller always returns u_conv_0 = 0."""
        x0 = np.array([18.0, 18.0, 18.0])
        result = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result.u_conv_0 == 0.0

    @pytest.mark.unit
    def test_solve_time_positive(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Solve time is positive after a successful solve."""
        x0 = np.array([20.0, 20.0, 20.0])
        result = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result.solve_time_ms > 0.0


# ---------------------------------------------------------------------------
# TestWarmStart
# ---------------------------------------------------------------------------


class TestWarmStart:
    """Tests for warm-start behaviour across consecutive solves."""

    @pytest.mark.unit
    def test_first_call_no_warm_start_succeeds(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """First call (no previous solution) succeeds without warm start."""
        x0 = np.array([20.0, 20.0, 20.0])
        result = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result.used_fallback is False

    @pytest.mark.unit
    def test_stores_previous_solution(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """After a successful step, previous solution is stored."""
        x0 = np.array([20.0, 20.0, 20.0])
        controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert controller_3r3c_siso._prev_u is not None
        assert controller_3r3c_siso._prev_x is not None

    @pytest.mark.unit
    def test_reset_clears_warm_start(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """reset() clears the stored solution."""
        x0 = np.array([20.0, 20.0, 20.0])
        controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        controller_3r3c_siso.reset()
        assert controller_3r3c_siso._prev_u is None
        assert controller_3r3c_siso._prev_x is None

    @pytest.mark.unit
    def test_warm_start_does_not_degrade_solution(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Second solve with warm start still produces optimal result."""
        x0 = np.array([20.0, 20.0, 20.0])
        # First solve (cold)
        controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        # Second solve (warm)
        result2 = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result2.used_fallback is False
        assert "optimal" in result2.solver_status


# ---------------------------------------------------------------------------
# TestSolverTimeout
# ---------------------------------------------------------------------------


class TestSolverTimeout:
    """Tests for solver timeout configuration."""

    @pytest.mark.unit
    def test_default_timeout_is_100ms(self) -> None:
        """Default solver_timeout_s is 0.1 (100 ms)."""
        cfg = MPCConfig()
        assert cfg.solver_timeout_s == 0.1

    @pytest.mark.unit
    def test_negative_timeout_rejected(self) -> None:
        """Negative solver_timeout_s raises ValueError."""
        with pytest.raises(ValueError, match="solver_timeout_s"):
            MPCConfig(solver_timeout_s=-0.05)

    @pytest.mark.unit
    def test_zero_timeout_rejected(self) -> None:
        """Zero solver_timeout_s raises ValueError."""
        with pytest.raises(ValueError, match="solver_timeout_s"):
            MPCConfig(solver_timeout_s=0.0)

    @pytest.mark.unit
    def test_custom_timeout_accepted(self) -> None:
        """Custom positive timeout is accepted."""
        cfg = MPCConfig(solver_timeout_s=0.5)
        assert cfg.solver_timeout_s == 0.5


# ---------------------------------------------------------------------------
# TestFallbackBehavior
# ---------------------------------------------------------------------------


class TestFallbackBehavior:
    """Tests for PID fallback when solver fails."""

    @pytest.mark.unit
    def test_infeasible_triggers_fallback(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """When solver raises MPCInfeasibleError, fallback is used."""
        # x0 with T_slab > 34 is infeasible
        x0 = np.array([20.0, 35.0, 20.0])
        result = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result.used_fallback is True
        assert result.solver_status == "fallback"
        assert result.mpc_result is None
        assert result.x_predicted is None

    @pytest.mark.unit
    def test_fallback_proportional_response(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Fallback produces higher valve for colder room."""
        x0_cold = np.array([15.0, 35.0, 15.0])  # T_slab infeasible for MPC
        x0_warm = np.array([20.5, 35.0, 20.5])
        result_cold = controller_3r3c_siso.step(
            x0=x0_cold,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        controller_3r3c_siso.reset()
        result_warm = controller_3r3c_siso.step(
            x0=x0_warm,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result_cold.used_fallback is True
        assert result_warm.used_fallback is True
        assert result_cold.u_floor_0 >= result_warm.u_floor_0

    @pytest.mark.unit
    def test_fallback_u_conv_always_zero(
        self,
        controller_3r3c_mimo: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Fallback always sets u_conv_0 = 0 (splits are not used)."""
        x0 = np.array([20.0, 35.0, 20.0])  # infeasible
        result = controller_3r3c_mimo.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result.used_fallback is True
        assert result.u_conv_0 == 0.0

    @pytest.mark.unit
    def test_fallback_valve_bounded(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Fallback valve is clamped to [0, 1]."""
        x0 = np.array([5.0, 35.0, 5.0])  # very cold, infeasible
        result = controller_3r3c_siso.step(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert result.used_fallback is True
        assert 0.0 <= result.u_floor_0 <= 1.0

    @pytest.mark.unit
    def test_exception_in_solver_triggers_fallback(
        self,
        controller_3r3c_siso: MPCController,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Generic exception in solver triggers fallback (not crash)."""
        x0 = np.array([20.0, 20.0, 20.0])
        with patch.object(
            controller_3r3c_siso._optimizer,
            "solve",
            side_effect=RuntimeError("solver crashed"),
        ):
            result = controller_3r3c_siso.step(
                x0=x0,
                d=constant_disturbance_3r3c,
                T_set=21.0,
            )
        assert result.used_fallback is True
        assert result.solver_status == "fallback"


# ---------------------------------------------------------------------------
# TestPIDFallback
# ---------------------------------------------------------------------------


class TestPIDFallback:
    """Tests for the internal _PIDFallback class."""

    @pytest.mark.unit
    def test_positive_error_gives_positive_output(self) -> None:
        """When T_air < T_set, output is positive."""
        pid = _PIDFallback(kp=5.0, ki=0.01, dt_seconds=900.0)
        valve = pid.compute(T_air=18.0, T_set=21.0)
        assert valve > 0.0

    @pytest.mark.unit
    def test_negative_error_gives_zero_output(self) -> None:
        """When T_air > T_set, output is clamped to 0."""
        pid = _PIDFallback(kp=5.0, ki=0.01, dt_seconds=900.0)
        valve = pid.compute(T_air=25.0, T_set=21.0)
        assert valve == 0.0

    @pytest.mark.unit
    def test_integral_accumulation(self) -> None:
        """Successive calls with same error increase output."""
        pid = _PIDFallback(kp=0.0, ki=0.1, dt_seconds=1.0)
        v1 = pid.compute(T_air=20.0, T_set=21.0)
        v2 = pid.compute(T_air=20.0, T_set=21.0)
        assert v2 > v1

    @pytest.mark.unit
    def test_reset_clears_integral(self) -> None:
        """reset() sets integral to zero."""
        pid = _PIDFallback(kp=0.0, ki=0.1, dt_seconds=1.0)
        pid.compute(T_air=18.0, T_set=21.0)
        pid.compute(T_air=18.0, T_set=21.0)
        pid.reset()
        # After reset, integral is zero again
        assert pid._integral == 0.0

    @pytest.mark.unit
    def test_output_clamped_to_unit_interval(self) -> None:
        """Output is always in [0, 1] regardless of error magnitude."""
        pid = _PIDFallback(kp=100.0, ki=0.0, dt_seconds=900.0)
        # Large positive error -> clamped to 1.0
        assert pid.compute(T_air=0.0, T_set=21.0) == 1.0
        pid.reset()
        # Large negative error -> clamped to 0.0
        assert pid.compute(T_air=50.0, T_set=21.0) == 0.0

    @pytest.mark.unit
    def test_integral_windup_clamp(self) -> None:
        """Integral is clamped to [-100, 100]."""
        pid = _PIDFallback(kp=0.0, ki=1.0, dt_seconds=1.0)
        # Accumulate a large positive integral
        for _ in range(1000):
            pid.compute(T_air=0.0, T_set=100.0)
        assert pid._integral <= 100.0
        assert pid._integral >= -100.0


# ---------------------------------------------------------------------------
# TestMPCConfigTimeout
# ---------------------------------------------------------------------------


class TestMPCConfigTimeout:
    """Tests specifically for MPCConfig solver_timeout_s field."""

    @pytest.mark.unit
    def test_default_is_100ms(self) -> None:
        """Default solver_timeout_s is 0.1 seconds."""
        assert MPCConfig().solver_timeout_s == 0.1

    @pytest.mark.unit
    def test_custom_value_stored(self) -> None:
        """Custom timeout is stored correctly."""
        cfg = MPCConfig(solver_timeout_s=0.25)
        assert cfg.solver_timeout_s == 0.25

    @pytest.mark.unit
    def test_frozen_dataclass(self) -> None:
        """MPCConfig is frozen -- fields cannot be reassigned."""
        cfg = MPCConfig()
        with pytest.raises(AttributeError):
            cfg.solver_timeout_s = 0.5  # type: ignore[misc]
