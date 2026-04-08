"""Comprehensive unit tests for pumpahead.optimizer (MPC QP construction)."""

from __future__ import annotations

import numpy as np
import pytest

from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.optimizer import MPCConfig, MPCInfeasibleError, MPCOptimizer, MPCResult

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mpc_config() -> MPCConfig:
    """Short-horizon MPC config for fast unit tests."""
    return MPCConfig(horizon=10)


@pytest.fixture()
def optimizer_3r3c_siso(
    model_3r3c: RCModel,
    mpc_config: MPCConfig,
) -> MPCOptimizer:
    """3R3C SISO (UFH-only) optimizer with short horizon."""
    return MPCOptimizer(model_3r3c, mpc_config)


@pytest.fixture()
def optimizer_3r3c_mimo(
    model_3r3c_mimo: RCModel,
    mpc_config: MPCConfig,
) -> MPCOptimizer:
    """3R3C MIMO (UFH + split) optimizer with short horizon."""
    return MPCOptimizer(model_3r3c_mimo, mpc_config)


@pytest.fixture()
def optimizer_2r2c_siso(
    model_2r2c: RCModel,
    mpc_config: MPCConfig,
) -> MPCOptimizer:
    """2R2C SISO (UFH-only) optimizer with short horizon."""
    return MPCOptimizer(model_2r2c, mpc_config)


@pytest.fixture()
def optimizer_2r2c_mimo(
    model_2r2c_mimo: RCModel,
    mpc_config: MPCConfig,
) -> MPCOptimizer:
    """2R2C MIMO (UFH + split) optimizer with short horizon."""
    return MPCOptimizer(model_2r2c_mimo, mpc_config)


@pytest.fixture()
def zero_disturbance_3r3c() -> np.ndarray:
    """10-step zero disturbance for 3R3C (3 disturbance channels)."""
    return np.zeros((10, 3))


@pytest.fixture()
def zero_disturbance_2r2c() -> np.ndarray:
    """10-step zero disturbance for 2R2C (2 disturbance channels)."""
    return np.zeros((10, 2))


@pytest.fixture()
def constant_disturbance_3r3c() -> np.ndarray:
    """10-step disturbance for 3R3C: T_out=5C, no solar, no internal."""
    return np.column_stack(
        [np.full(10, 5.0), np.zeros(10), np.zeros(10)]
    )


@pytest.fixture()
def constant_disturbance_2r2c() -> np.ndarray:
    """10-step disturbance for 2R2C: T_out=5C, no solar."""
    return np.column_stack([np.full(10, 5.0), np.zeros(10)])


# ---------------------------------------------------------------------------
# TestMPCConfig — configuration validation
# ---------------------------------------------------------------------------


class TestMPCConfig:
    """Tests for MPCConfig defaults and validation."""

    @pytest.mark.unit
    def test_default_values(self) -> None:
        """Verify default values match the spec."""
        cfg = MPCConfig()
        assert cfg.horizon == 96
        assert cfg.w_comfort == 1.0
        assert cfg.w_energy == 0.1
        assert cfg.w_smooth == 0.01
        assert cfg.T_floor_max == 34.0
        assert cfg.T_dew_margin == 2.0
        assert cfg.w_slack == 1000.0
        assert cfg.T_comfort_band == 2.0

    @pytest.mark.unit
    def test_negative_horizon_rejected(self) -> None:
        """Horizon < 1 raises ValueError."""
        with pytest.raises(ValueError, match="horizon"):
            MPCConfig(horizon=0)

    @pytest.mark.unit
    def test_negative_w_comfort_rejected(self) -> None:
        """Negative w_comfort raises ValueError."""
        with pytest.raises(ValueError, match="w_comfort"):
            MPCConfig(w_comfort=-1.0)

    @pytest.mark.unit
    def test_negative_w_energy_rejected(self) -> None:
        """Negative w_energy raises ValueError."""
        with pytest.raises(ValueError, match="w_energy"):
            MPCConfig(w_energy=-0.5)

    @pytest.mark.unit
    def test_negative_w_smooth_rejected(self) -> None:
        """Negative w_smooth raises ValueError."""
        with pytest.raises(ValueError, match="w_smooth"):
            MPCConfig(w_smooth=-0.01)

    @pytest.mark.unit
    def test_negative_w_slack_rejected(self) -> None:
        """Non-positive w_slack raises ValueError."""
        with pytest.raises(ValueError, match="w_slack"):
            MPCConfig(w_slack=0.0)

    @pytest.mark.unit
    def test_negative_T_comfort_band_rejected(self) -> None:
        """Non-positive T_comfort_band raises ValueError."""
        with pytest.raises(ValueError, match="T_comfort_band"):
            MPCConfig(T_comfort_band=0.0)


# ---------------------------------------------------------------------------
# TestMPCOptimizerConstruction — problem builds without errors
# ---------------------------------------------------------------------------


class TestMPCOptimizerConstruction:
    """Tests that the optimizer builds correctly for all model variants."""

    @pytest.mark.unit
    def test_builds_without_error_3r3c_siso(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
    ) -> None:
        """3R3C SISO optimizer builds and has a problem."""
        assert optimizer_3r3c_siso.problem is not None
        assert not optimizer_3r3c_siso.has_split

    @pytest.mark.unit
    def test_builds_without_error_3r3c_mimo(
        self,
        optimizer_3r3c_mimo: MPCOptimizer,
    ) -> None:
        """3R3C MIMO optimizer builds and has a problem."""
        assert optimizer_3r3c_mimo.problem is not None
        assert optimizer_3r3c_mimo.has_split

    @pytest.mark.unit
    def test_builds_without_error_2r2c_siso(
        self,
        optimizer_2r2c_siso: MPCOptimizer,
    ) -> None:
        """2R2C SISO optimizer builds and has a problem."""
        assert optimizer_2r2c_siso.problem is not None
        assert not optimizer_2r2c_siso.has_split

    @pytest.mark.unit
    def test_builds_without_error_2r2c_mimo(
        self,
        optimizer_2r2c_mimo: MPCOptimizer,
    ) -> None:
        """2R2C MIMO optimizer builds and has a problem."""
        assert optimizer_2r2c_mimo.problem is not None
        assert optimizer_2r2c_mimo.has_split

    @pytest.mark.unit
    def test_problem_is_dpp_3r3c(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
    ) -> None:
        """3R3C problem is DPP-compliant."""
        assert optimizer_3r3c_siso.is_dpp is True

    @pytest.mark.unit
    def test_problem_is_dpp_2r2c(
        self,
        optimizer_2r2c_siso: MPCOptimizer,
    ) -> None:
        """2R2C problem is DPP-compliant."""
        assert optimizer_2r2c_siso.is_dpp is True

    @pytest.mark.unit
    def test_problem_is_dpp_3r3c_mimo(
        self,
        optimizer_3r3c_mimo: MPCOptimizer,
    ) -> None:
        """3R3C MIMO problem is DPP-compliant."""
        assert optimizer_3r3c_mimo.is_dpp is True

    @pytest.mark.unit
    def test_problem_is_dpp_2r2c_mimo(
        self,
        optimizer_2r2c_mimo: MPCOptimizer,
    ) -> None:
        """2R2C MIMO problem is DPP-compliant."""
        assert optimizer_2r2c_mimo.is_dpp is True


# ---------------------------------------------------------------------------
# TestMPCFloorTempConstraint — hard safety constraints
# ---------------------------------------------------------------------------


class TestMPCFloorTempConstraint:
    """Tests for floor temperature hard constraints (Axioms 4 & 5)."""

    @pytest.mark.unit
    def test_floor_temp_never_exceeds_34(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        zero_disturbance_3r3c: np.ndarray,
    ) -> None:
        """T_slab never exceeds 34 degC (Axiom 4)."""
        x0 = np.array([20.0, 20.0, 20.0])
        result = optimizer_3r3c_siso.solve(
            x0=x0,
            d=zero_disturbance_3r3c,
            T_set=21.0,
        )
        # Allow OSQP solver tolerance
        np.testing.assert_array_less(result.x[:, 1], 34.0 + 1e-3)

    @pytest.mark.unit
    def test_floor_temp_never_exceeds_34_2r2c(
        self,
        optimizer_2r2c_siso: MPCOptimizer,
        zero_disturbance_2r2c: np.ndarray,
    ) -> None:
        """T_slab never exceeds 34 degC in 2R2C model (Axiom 4)."""
        x0 = np.array([20.0, 20.0])
        result = optimizer_2r2c_siso.solve(
            x0=x0,
            d=zero_disturbance_2r2c,
            T_set=21.0,
        )
        np.testing.assert_array_less(result.x[:, 1], 34.0 + 1e-3)

    @pytest.mark.unit
    def test_floor_temp_respects_dew_point(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        zero_disturbance_3r3c: np.ndarray,
    ) -> None:
        """T_slab stays above T_dew + 2 degC (Axiom 5)."""
        x0 = np.array([22.0, 22.0, 22.0])
        T_dew = np.full(10, 18.0)
        result = optimizer_3r3c_siso.solve(
            x0=x0,
            d=zero_disturbance_3r3c,
            T_set=21.0,
            T_dew=T_dew,
        )
        # T_slab >= T_dew + 2 = 20.0
        assert np.all(result.x[:, 1] >= 20.0 - 1e-3)


# ---------------------------------------------------------------------------
# TestMPCSplitConstraints — split/AC mode constraints
# ---------------------------------------------------------------------------


class TestMPCSplitConstraints:
    """Tests for split (Q_conv) constraints and SISO/MIMO handling."""

    @pytest.mark.unit
    def test_u_conv_zero_when_no_split(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """SISO optimizer returns all-zero u_conv."""
        x0 = np.array([18.0, 18.0, 18.0])
        result = optimizer_3r3c_siso.solve(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        np.testing.assert_array_equal(result.u_conv, np.zeros(10))
        assert result.u.shape[1] == 1

    @pytest.mark.unit
    def test_u_conv_nonneg_in_heating_mode(
        self,
        optimizer_3r3c_mimo: MPCOptimizer,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """In heating mode, split only heats (u_conv >= 0)."""
        x0 = np.array([18.0, 18.0, 18.0])
        result = optimizer_3r3c_mimo.solve(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
            mode="heating",
        )
        assert np.all(result.u_conv >= -1e-6)

    @pytest.mark.unit
    def test_u_conv_nonpos_in_cooling_mode(
        self,
        optimizer_3r3c_mimo: MPCOptimizer,
    ) -> None:
        """In cooling mode, split only cools (u_conv <= 0)."""
        # Hot room, warm outdoor — cooling scenario
        x0 = np.array([28.0, 28.0, 28.0])
        d = np.column_stack(
            [np.full(10, 30.0), np.full(10, 300.0), np.zeros(10)]
        )
        result = optimizer_3r3c_mimo.solve(
            x0=x0,
            d=d,
            T_set=24.0,
            mode="cooling",
        )
        assert np.all(result.u_conv <= 1e-6)


# ---------------------------------------------------------------------------
# TestMPCCostFunction — cost term behaviour
# ---------------------------------------------------------------------------


class TestMPCCostFunction:
    """Tests for cost function weight effects."""

    @pytest.mark.unit
    def test_zero_energy_weight_maximizes_comfort(
        self,
        model_3r3c: RCModel,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """With w_energy=0 and w_smooth=0, temperature stays near setpoint."""
        cfg = MPCConfig(
            horizon=10,
            w_comfort=10.0,
            w_energy=0.0,
            w_smooth=0.0,
        )
        opt = MPCOptimizer(model_3r3c, cfg)
        x0 = np.array([19.0, 19.0, 19.0])
        result = opt.solve(x0=x0, d=constant_disturbance_3r3c, T_set=21.0)
        # T_air should be reasonably close to 21 for most of the horizon
        mean_deviation = np.mean(np.abs(result.x[1:, 0] - 21.0))
        assert mean_deviation < 5.0

    @pytest.mark.unit
    def test_high_energy_weight_reduces_input(
        self,
        model_3r3c: RCModel,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """With very high w_energy, control inputs are near zero."""
        cfg = MPCConfig(
            horizon=10,
            w_comfort=0.001,
            w_energy=1000.0,
            w_smooth=0.0,
        )
        opt = MPCOptimizer(model_3r3c, cfg)
        x0 = np.array([19.0, 19.0, 19.0])
        result = opt.solve(x0=x0, d=constant_disturbance_3r3c, T_set=21.0)
        assert np.all(np.abs(result.u_floor) < 0.1)

    @pytest.mark.unit
    def test_move_suppression_smooths_input(
        self,
        model_3r3c: RCModel,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """With high w_smooth, control input changes are small."""
        cfg = MPCConfig(
            horizon=10,
            w_comfort=1.0,
            w_energy=0.1,
            w_smooth=100.0,
        )
        opt = MPCOptimizer(model_3r3c, cfg)
        x0 = np.array([19.0, 19.0, 19.0])
        result = opt.solve(x0=x0, d=constant_disturbance_3r3c, T_set=21.0)
        du = np.diff(result.u_floor)
        max_du = np.max(np.abs(du))
        assert max_du < 0.5


# ---------------------------------------------------------------------------
# TestMPCSolve — basic solve behaviour
# ---------------------------------------------------------------------------


class TestMPCSolve:
    """Tests for solve method correctness."""

    @pytest.mark.unit
    def test_solve_returns_valid_result(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Basic solve returns result with correct shapes."""
        x0 = np.array([20.0, 20.0, 20.0])
        result = optimizer_3r3c_siso.solve(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert isinstance(result, MPCResult)
        assert result.x.shape == (11, 3)  # N+1=11, n=3
        assert result.u.shape == (10, 1)  # N=10, m=1
        assert result.u_floor.shape == (10,)
        assert result.u_conv.shape == (10,)
        assert result.slack.shape == (11,)

    @pytest.mark.unit
    def test_solve_status_optimal(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Solver status contains 'optimal'."""
        x0 = np.array([20.0, 20.0, 20.0])
        result = optimizer_3r3c_siso.solve(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert "optimal" in result.status

    @pytest.mark.unit
    def test_valve_position_bounded_zero_one(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """UFH valve stays within [0, 1]."""
        x0 = np.array([18.0, 18.0, 18.0])
        result = optimizer_3r3c_siso.solve(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        assert np.all(result.u_floor >= -1e-6)
        assert np.all(result.u_floor <= 1.0 + 1e-6)

    @pytest.mark.unit
    def test_dynamics_satisfied(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        constant_disturbance_3r3c: np.ndarray,
        model_3r3c: RCModel,
    ) -> None:
        """State dynamics x[k+1] = A_d @ x[k] + B_d @ u[k] + E_d @ d[k] + b_d."""
        x0 = np.array([20.0, 20.0, 20.0])
        result = optimizer_3r3c_siso.solve(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )
        matrices = model_3r3c.get_matrices()
        A_d = matrices["A_d"]
        B_d = matrices["B_d"]
        E_d = matrices["E_d"]
        b_d = matrices["b_d"]

        for k in range(10):
            x_next_expected = (
                A_d @ result.x[k]
                + B_d @ result.u[k]
                + E_d @ constant_disturbance_3r3c[k]
                + b_d
            )
            np.testing.assert_allclose(
                result.x[k + 1],
                x_next_expected,
                atol=1e-3,
            )

    @pytest.mark.unit
    def test_invalid_x0_shape_rejected(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Wrong x0 shape raises ValueError."""
        with pytest.raises(ValueError, match="x0 shape"):
            optimizer_3r3c_siso.solve(
                x0=np.array([20.0, 20.0]),
                d=constant_disturbance_3r3c,
                T_set=21.0,
            )

    @pytest.mark.unit
    def test_invalid_d_shape_rejected(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
    ) -> None:
        """Wrong disturbance shape raises ValueError."""
        with pytest.raises(ValueError, match="d shape"):
            optimizer_3r3c_siso.solve(
                x0=np.array([20.0, 20.0, 20.0]),
                d=np.zeros((5, 3)),  # wrong: 5 != horizon=10
                T_set=21.0,
            )

    @pytest.mark.unit
    def test_invalid_mode_rejected(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Invalid mode string raises ValueError."""
        with pytest.raises(ValueError, match="mode"):
            optimizer_3r3c_siso.solve(
                x0=np.array([20.0, 20.0, 20.0]),
                d=constant_disturbance_3r3c,
                T_set=21.0,
                mode="auto",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# TestMPCUpdateModel — model parameter update
# ---------------------------------------------------------------------------


class TestMPCUpdateModel:
    """Tests for update_model method."""

    @pytest.mark.unit
    def test_update_model_changes_parameters(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        params_3r3c: RCParams,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Updating to a model with different dt changes the solution."""
        x0 = np.array([20.0, 20.0, 20.0])
        result_before = optimizer_3r3c_siso.solve(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )

        # Create a new model with different dt (different A_d)
        new_model = RCModel(params_3r3c, ModelOrder.THREE, dt=120.0)
        optimizer_3r3c_siso.update_model(new_model)

        result_after = optimizer_3r3c_siso.solve(
            x0=x0,
            d=constant_disturbance_3r3c,
            T_set=21.0,
        )

        # Solutions should differ
        assert not np.allclose(result_before.u, result_after.u, atol=1e-4)

    @pytest.mark.unit
    def test_update_model_wrong_dimensions_rejected(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        params_2r2c: RCParams,
    ) -> None:
        """Updating with a differently-dimensioned model raises ValueError."""
        model_2r2c = RCModel(params_2r2c, ModelOrder.TWO, dt=60.0)
        with pytest.raises(ValueError, match="states"):
            optimizer_3r3c_siso.update_model(model_2r2c)


# ---------------------------------------------------------------------------
# TestMPCEdgeCases — edge case behaviour
# ---------------------------------------------------------------------------


class TestMPCEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.unit
    def test_single_step_horizon(
        self,
        model_3r3c: RCModel,
    ) -> None:
        """Horizon=1 solves without error."""
        cfg = MPCConfig(horizon=1)
        opt = MPCOptimizer(model_3r3c, cfg)
        x0 = np.array([20.0, 20.0, 20.0])
        d = np.zeros((1, 3))
        result = opt.solve(x0=x0, d=d, T_set=21.0)
        assert result.x.shape == (2, 3)
        assert result.u.shape == (1, 1)
        assert "optimal" in result.status

    @pytest.mark.unit
    def test_soft_comfort_slack_activates(
        self,
        model_3r3c: RCModel,
    ) -> None:
        """When temperature is far from setpoint, slack > 0."""
        # Very cold start, limited heating capacity (model dt short so
        # little heating per step), but the slack should activate to
        # keep the problem feasible
        cfg = MPCConfig(
            horizon=10,
            w_comfort=1.0,
            w_energy=0.1,
            w_smooth=0.01,
            T_comfort_band=0.5,
        )
        opt = MPCOptimizer(model_3r3c, cfg)
        # Start very cold — far from setpoint
        x0 = np.array([5.0, 5.0, 5.0])
        d = np.zeros((10, 3))
        result = opt.solve(x0=x0, d=d, T_set=21.0)
        # Slack should be nonzero at least at the beginning
        assert np.any(result.slack > 1e-6)

    @pytest.mark.unit
    def test_initial_state_violating_floor_limit_infeasible(
        self,
        model_3r3c: RCModel,
    ) -> None:
        """x0 with T_slab > 34 raises MPCInfeasibleError."""
        cfg = MPCConfig(horizon=10)
        opt = MPCOptimizer(model_3r3c, cfg)
        x0 = np.array([20.0, 35.0, 20.0])  # T_slab=35 > 34
        d = np.zeros((10, 3))
        with pytest.raises(MPCInfeasibleError):
            opt.solve(x0=x0, d=d, T_set=21.0)

    @pytest.mark.unit
    def test_2r2c_mimo_solve(
        self,
        optimizer_2r2c_mimo: MPCOptimizer,
        constant_disturbance_2r2c: np.ndarray,
    ) -> None:
        """2R2C MIMO optimizer solves successfully."""
        x0 = np.array([18.0, 18.0])
        result = optimizer_2r2c_mimo.solve(
            x0=x0,
            d=constant_disturbance_2r2c,
            T_set=21.0,
        )
        assert result.x.shape == (11, 2)
        assert result.u.shape == (10, 2)
        assert "optimal" in result.status

    @pytest.mark.unit
    def test_invalid_T_dew_shape_rejected(
        self,
        optimizer_3r3c_siso: MPCOptimizer,
        constant_disturbance_3r3c: np.ndarray,
    ) -> None:
        """Wrong T_dew shape raises ValueError."""
        x0 = np.array([20.0, 20.0, 20.0])
        with pytest.raises(ValueError, match="T_dew shape"):
            optimizer_3r3c_siso.solve(
                x0=x0,
                d=constant_disturbance_3r3c,
                T_set=21.0,
                T_dew=np.full(5, 15.0),  # wrong: 5 != horizon=10
            )
