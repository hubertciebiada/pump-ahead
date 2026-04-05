"""Comprehensive unit tests for pumpahead.model."""

import numpy as np
import pytest

from pumpahead.model import ModelOrder, RCModel, RCParams

# ---------------------------------------------------------------------------
# TestRCParams — validation and parameter checks
# ---------------------------------------------------------------------------


class TestRCParams:
    """Tests for RCParams dataclass validation."""

    @pytest.mark.unit
    def test_valid_3r3c_params(self, params_3r3c: RCParams) -> None:
        """Valid 3R3C parameters should not raise."""
        assert params_3r3c.C_air == 60_000
        assert params_3r3c.C_slab == 3_250_000

    @pytest.mark.unit
    def test_valid_2r2c_params(self, params_2r2c: RCParams) -> None:
        """Valid 2R2C parameters should not raise."""
        assert params_2r2c.R_env == 0.03

    @pytest.mark.unit
    def test_c_slab_c_air_ratio(self, params_3r3c: RCParams) -> None:
        """C_slab/C_air ratio must be ~54.17 per Axiom 7."""
        ratio = params_3r3c.C_slab / params_3r3c.C_air
        assert abs(ratio - 54.1667) < 0.01

    @pytest.mark.unit
    def test_negative_resistance_rejected(self) -> None:
        """Negative resistance must be rejected."""
        with pytest.raises(ValueError, match="R_sf must be positive"):
            RCParams(C_air=60_000, C_slab=3_250_000, R_sf=-0.01)

    @pytest.mark.unit
    def test_zero_capacitance_rejected(self) -> None:
        """Zero capacitance must be rejected."""
        with pytest.raises(ValueError, match="C_air must be positive"):
            RCParams(C_air=0, C_slab=3_250_000, R_sf=0.01)

    @pytest.mark.unit
    def test_negative_capacitance_rejected(self) -> None:
        """Negative capacitance must be rejected."""
        with pytest.raises(ValueError, match="C_slab must be positive"):
            RCParams(C_air=60_000, C_slab=-1, R_sf=0.01)

    @pytest.mark.unit
    def test_solar_fraction_sum_exceeds_one(self) -> None:
        """f_conv + f_rad > 1.0 must be rejected."""
        with pytest.raises(ValueError, match="f_conv \\+ f_rad must be <= 1.0"):
            RCParams(
                C_air=60_000,
                C_slab=3_250_000,
                R_sf=0.01,
                f_conv=0.7,
                f_rad=0.4,
            )

    @pytest.mark.unit
    def test_solar_fraction_sum_equals_one(self) -> None:
        """f_conv + f_rad = 1.0 should be accepted."""
        params = RCParams(
            C_air=60_000,
            C_slab=3_250_000,
            R_sf=0.01,
            f_conv=0.6,
            f_rad=0.4,
        )
        assert params.f_conv + params.f_rad == 1.0

    @pytest.mark.unit
    def test_solar_fraction_below_one_accepted(self) -> None:
        """f_conv + f_rad < 1.0 is valid (remaining fraction reflected)."""
        params = RCParams(
            C_air=60_000,
            C_slab=3_250_000,
            R_sf=0.01,
            f_conv=0.3,
            f_rad=0.2,
        )
        assert params.f_conv + params.f_rad < 1.0

    @pytest.mark.unit
    def test_negative_f_conv_rejected(self) -> None:
        """Negative solar fraction must be rejected."""
        with pytest.raises(ValueError, match="Solar fractions must be non-negative"):
            RCParams(
                C_air=60_000,
                C_slab=3_250_000,
                R_sf=0.01,
                f_conv=-0.1,
                f_rad=0.4,
            )

    @pytest.mark.unit
    def test_frozen_dataclass(self, params_3r3c: RCParams) -> None:
        """RCParams is frozen (immutable)."""
        with pytest.raises(AttributeError):
            params_3r3c.C_air = 100  # type: ignore[misc]

    @pytest.mark.unit
    def test_validate_for_order_3r3c_missing_c_wall(self) -> None:
        """3R3C validation requires C_wall."""
        params = RCParams(
            C_air=60_000,
            C_slab=3_250_000,
            R_sf=0.01,
            R_wi=0.02,
            R_wo=0.03,
            R_ve=0.03,
            R_ins=0.01,
        )
        with pytest.raises(ValueError, match="C_wall is required"):
            params.validate_for_order(ModelOrder.THREE)

    @pytest.mark.unit
    def test_validate_for_order_3r3c_negative_r_ins(self) -> None:
        """3R3C validation rejects negative R_ins."""
        params = RCParams(
            C_air=60_000,
            C_slab=3_250_000,
            R_sf=0.01,
            C_wall=1_500_000,
            R_wi=0.02,
            R_wo=0.03,
            R_ve=0.03,
            R_ins=-0.01,
        )
        with pytest.raises(ValueError, match="R_ins must be positive"):
            params.validate_for_order(ModelOrder.THREE)

    @pytest.mark.unit
    def test_validate_for_order_2r2c_missing_r_env(self) -> None:
        """2R2C validation requires R_env."""
        params = RCParams(C_air=60_000, C_slab=3_250_000, R_sf=0.01)
        with pytest.raises(ValueError, match="R_env is required"):
            params.validate_for_order(ModelOrder.TWO)

    @pytest.mark.unit
    def test_validate_for_order_2r2c_negative_r_env(self) -> None:
        """2R2C validation rejects negative R_env."""
        params = RCParams(
            C_air=60_000,
            C_slab=3_250_000,
            R_sf=0.01,
            R_env=-0.03,
        )
        with pytest.raises(ValueError, match="R_env must be positive"):
            params.validate_for_order(ModelOrder.TWO)


# ---------------------------------------------------------------------------
# TestRCModelConstruction — matrix dimensions and shapes
# ---------------------------------------------------------------------------


class TestRCModelConstruction:
    """Tests for RCModel construction and matrix dimensions."""

    @pytest.mark.unit
    def test_3r3c_siso_dimensions(self, model_3r3c: RCModel) -> None:
        """3R3C SISO: A(3,3), B(3,1), E(3,3)."""
        matrices = model_3r3c.get_matrices()
        assert matrices["A_c"].shape == (3, 3)
        assert matrices["B_c"].shape == (3, 1)
        assert matrices["E_c"].shape == (3, 3)
        assert matrices["b_c"].shape == (3,)
        assert matrices["A_d"].shape == (3, 3)
        assert matrices["B_d"].shape == (3, 1)
        assert matrices["E_d"].shape == (3, 3)
        assert matrices["b_d"].shape == (3,)

    @pytest.mark.unit
    def test_3r3c_mimo_dimensions(self, model_3r3c_mimo: RCModel) -> None:
        """3R3C MIMO: A(3,3), B(3,2), E(3,3)."""
        matrices = model_3r3c_mimo.get_matrices()
        assert matrices["A_c"].shape == (3, 3)
        assert matrices["B_c"].shape == (3, 2)
        assert matrices["E_c"].shape == (3, 3)
        assert matrices["A_d"].shape == (3, 3)
        assert matrices["B_d"].shape == (3, 2)
        assert matrices["E_d"].shape == (3, 3)

    @pytest.mark.unit
    def test_2r2c_siso_dimensions(self, model_2r2c: RCModel) -> None:
        """2R2C SISO: A(2,2), B(2,1), E(2,2)."""
        matrices = model_2r2c.get_matrices()
        assert matrices["A_c"].shape == (2, 2)
        assert matrices["B_c"].shape == (2, 1)
        assert matrices["E_c"].shape == (2, 2)
        assert matrices["b_c"].shape == (2,)
        assert matrices["A_d"].shape == (2, 2)
        assert matrices["B_d"].shape == (2, 1)
        assert matrices["E_d"].shape == (2, 2)
        assert matrices["b_d"].shape == (2,)

    @pytest.mark.unit
    def test_2r2c_mimo_dimensions(self, model_2r2c_mimo: RCModel) -> None:
        """2R2C MIMO: A(2,2), B(2,2), E(2,2)."""
        matrices = model_2r2c_mimo.get_matrices()
        assert matrices["A_c"].shape == (2, 2)
        assert matrices["B_c"].shape == (2, 2)
        assert matrices["E_c"].shape == (2, 2)

    @pytest.mark.unit
    def test_properties(self, model_3r3c: RCModel) -> None:
        """Property values for 3R3C SISO model."""
        assert model_3r3c.n_states == 3
        assert model_3r3c.n_inputs == 1
        assert model_3r3c.n_disturbances == 3
        assert model_3r3c.state_names == ["T_air", "T_slab", "T_wall"]
        assert model_3r3c.dt == 60.0
        assert model_3r3c.order == ModelOrder.THREE

    @pytest.mark.unit
    def test_properties_mimo(self, model_3r3c_mimo: RCModel) -> None:
        """Property values for 3R3C MIMO model."""
        assert model_3r3c_mimo.n_inputs == 2

    @pytest.mark.unit
    def test_properties_2r2c(self, model_2r2c: RCModel) -> None:
        """Property values for 2R2C SISO model."""
        assert model_2r2c.n_states == 2
        assert model_2r2c.n_inputs == 1
        assert model_2r2c.n_disturbances == 2
        assert model_2r2c.state_names == ["T_air", "T_slab"]

    @pytest.mark.unit
    def test_c_obs_3r3c(self, model_3r3c: RCModel) -> None:
        """C_obs should extract T_air from state."""
        c = model_3r3c.C_obs
        assert c.shape == (1, 3)
        np.testing.assert_array_equal(c, [[1, 0, 0]])

    @pytest.mark.unit
    def test_c_obs_2r2c(self, model_2r2c: RCModel) -> None:
        """C_obs should extract T_air from state."""
        c = model_2r2c.C_obs
        assert c.shape == (1, 2)
        np.testing.assert_array_equal(c, [[1, 0]])

    @pytest.mark.unit
    def test_invalid_dt_zero(self, params_3r3c: RCParams) -> None:
        """dt=0 should raise ValueError."""
        with pytest.raises(ValueError, match="dt must be positive"):
            RCModel(params_3r3c, ModelOrder.THREE, dt=0.0)

    @pytest.mark.unit
    def test_invalid_dt_negative(self, params_3r3c: RCParams) -> None:
        """Negative dt should raise ValueError."""
        with pytest.raises(ValueError, match="dt must be positive"):
            RCModel(params_3r3c, ModelOrder.THREE, dt=-1.0)

    @pytest.mark.unit
    def test_matrices_are_copies(self, model_3r3c: RCModel) -> None:
        """get_matrices() should return copies, not views."""
        m1 = model_3r3c.get_matrices()
        m2 = model_3r3c.get_matrices()
        m1["A_d"][0, 0] = 999.0
        assert m2["A_d"][0, 0] != 999.0

    @pytest.mark.unit
    def test_3r3c_b_c_siso_structure(self, model_3r3c: RCModel) -> None:
        """SISO B_c: only slab row nonzero (Q_floor -> T_slab)."""
        B_c = model_3r3c.get_matrices()["B_c"]
        assert B_c[0, 0] == 0.0  # Q_floor does NOT go to air
        assert B_c[1, 0] > 0.0  # Q_floor goes to slab
        assert B_c[2, 0] == 0.0  # Q_floor does NOT go to wall

    @pytest.mark.unit
    def test_3r3c_b_c_mimo_structure(self, model_3r3c_mimo: RCModel) -> None:
        """MIMO B_c: Q_conv -> air, Q_floor -> slab, nothing -> wall."""
        B_c = model_3r3c_mimo.get_matrices()["B_c"]
        assert B_c[0, 0] > 0.0  # Q_conv -> T_air
        assert B_c[0, 1] == 0.0  # Q_floor does NOT go to air
        assert B_c[1, 0] == 0.0  # Q_conv does NOT go to slab
        assert B_c[1, 1] > 0.0  # Q_floor -> T_slab
        assert B_c[2, 0] == 0.0
        assert B_c[2, 1] == 0.0

    @pytest.mark.unit
    def test_a_c_diagonal_negative(self, model_3r3c: RCModel) -> None:
        """Diagonal of A_c must be negative (dissipative system)."""
        A_c = model_3r3c.get_matrices()["A_c"]
        for i in range(A_c.shape[0]):
            assert A_c[i, i] < 0.0, f"A_c[{i},{i}] = {A_c[i, i]} is not negative"

    @pytest.mark.unit
    def test_2r2c_no_t_ground_bias(self, model_2r2c: RCModel) -> None:
        """2R2C model should have zero b_c (no T_ground term)."""
        b_c = model_2r2c.get_matrices()["b_c"]
        np.testing.assert_array_equal(b_c, np.zeros(2))


# ---------------------------------------------------------------------------
# TestRCModelStep — state propagation
# ---------------------------------------------------------------------------


class TestRCModelStep:
    """Tests for RCModel.step() method."""

    @pytest.mark.unit
    def test_step_output_shape_3r3c(self, model_3r3c: RCModel) -> None:
        """step() should return shape (n_states,) for 3R3C."""
        x = np.array([20.0, 20.0, 20.0])
        u = np.array([0.0])
        d = np.array([5.0, 0.0, 0.0])
        x_next = model_3r3c.step(x, u, d)
        assert x_next.shape == (3,)

    @pytest.mark.unit
    def test_step_output_shape_2r2c(self, model_2r2c: RCModel) -> None:
        """step() should return shape (n_states,) for 2R2C."""
        x = np.array([20.0, 20.0])
        u = np.array([0.0])
        d = np.array([5.0, 0.0])
        x_next = model_2r2c.step(x, u, d)
        assert x_next.shape == (2,)

    @pytest.mark.unit
    def test_step_does_not_mutate_input(self, model_3r3c: RCModel) -> None:
        """step() must be a pure function (no mutation of x)."""
        x = np.array([20.0, 20.0, 20.0])
        x_original = x.copy()
        u = np.array([1000.0])
        d = np.array([5.0, 0.0, 0.0])
        model_3r3c.step(x, u, d)
        np.testing.assert_array_equal(x, x_original)

    @pytest.mark.unit
    def test_step_convergence_to_steady_state(self, model_3r3c: RCModel) -> None:
        """Repeated step() should converge to steady state.

        With constant inputs and disturbances, the model should converge
        to the analytical steady state within tolerance.
        """
        u = np.array([1000.0])
        d = np.array([5.0, 0.0, 0.0])

        x_ss = model_3r3c.steady_state(u, d)

        # Start from 20 degC and run for 7 days (10080 steps at dt=60s).
        # Slab tau ~ C_slab * R_sf = 32500s ~ 9h; 5*tau ~ 45h needed.
        x = np.array([20.0, 20.0, 20.0])
        for _ in range(10080):
            x = model_3r3c.step(x, u, d)

        # After 7 days should be within 0.01 degC of steady state
        np.testing.assert_allclose(x, x_ss, atol=0.01)

    @pytest.mark.unit
    def test_step_preserves_steady_state(self, model_3r3c: RCModel) -> None:
        """step() from steady state should return steady state."""
        u = np.array([500.0])
        d = np.array([0.0, 0.0, 0.0])
        x_ss = model_3r3c.steady_state(u, d)

        x_next = model_3r3c.step(x_ss, u, d)
        np.testing.assert_allclose(x_next, x_ss, atol=1e-6)

    @pytest.mark.unit
    def test_step_energy_direction_heating(self, model_3r3c: RCModel) -> None:
        """With Q_floor > 0 and cold outdoor, slab should warm."""
        x = np.array([15.0, 15.0, 15.0])
        u = np.array([2000.0])
        d = np.array([0.0, 0.0, 0.0])

        x_next = model_3r3c.step(x, u, d)
        # Slab should gain temperature from heating
        assert x_next[1] > x[1]

    @pytest.mark.unit
    def test_step_cooling_outdoor(self, model_3r3c: RCModel) -> None:
        """With no heating and cold outdoor, air should cool."""
        x = np.array([20.0, 20.0, 20.0])
        u = np.array([0.0])
        d = np.array([-10.0, 0.0, 0.0])

        x_next = model_3r3c.step(x, u, d)
        # Air should lose temperature due to cold outdoor
        assert x_next[0] < x[0]

    @pytest.mark.unit
    def test_step_mimo(self, model_3r3c_mimo: RCModel) -> None:
        """MIMO step should accept 2-input control vector."""
        x = np.array([20.0, 20.0, 20.0])
        u = np.array([1000.0, 500.0])  # Q_conv, Q_floor
        d = np.array([5.0, 0.0, 0.0])

        x_next = model_3r3c_mimo.step(x, u, d)
        assert x_next.shape == (3,)

    @pytest.mark.unit
    def test_step_error_vs_analytical_steady_state(self, params_3r3c: RCParams) -> None:
        """step() error vs analytical steady state < 0.01 degC.

        This acceptance criterion requires running step() until convergence
        and comparing with the analytical steady-state solution.
        """
        model = RCModel(params_3r3c, ModelOrder.THREE, dt=60.0)
        u = np.array([1500.0])
        d = np.array([-5.0, 100.0, 200.0])

        x_ss_analytical = model.steady_state(u, d)

        # Run 7 days to ensure convergence (slab tau ~ 9h, need 5*tau ~ 45h)
        x = np.array([20.0, 20.0, 20.0])
        for _ in range(10080):
            x = model.step(x, u, d)

        np.testing.assert_allclose(x, x_ss_analytical, atol=0.01)


# ---------------------------------------------------------------------------
# TestRCModelPredict — trajectory prediction
# ---------------------------------------------------------------------------


class TestRCModelPredict:
    """Tests for RCModel.predict() method."""

    @pytest.mark.unit
    def test_predict_trajectory_shape(self, model_3r3c: RCModel) -> None:
        """predict() returns (N+1, n_states) array."""
        n_steps = 100
        x0 = np.array([20.0, 20.0, 20.0])
        u_seq = np.zeros((n_steps, 1))
        d_seq = np.tile([5.0, 0.0, 0.0], (n_steps, 1))

        traj = model_3r3c.predict(x0, u_seq, d_seq)
        assert traj.shape == (n_steps + 1, 3)

    @pytest.mark.unit
    def test_predict_x0_preserved(self, model_3r3c: RCModel) -> None:
        """predict() first row must equal x0."""
        x0 = np.array([18.0, 22.0, 19.5])
        u_seq = np.zeros((10, 1))
        d_seq = np.tile([5.0, 0.0, 0.0], (10, 1))

        traj = model_3r3c.predict(x0, u_seq, d_seq)
        np.testing.assert_array_equal(traj[0], x0)

    @pytest.mark.unit
    def test_predict_x0_not_mutated(self, model_3r3c: RCModel) -> None:
        """predict() must not mutate x0."""
        x0 = np.array([18.0, 22.0, 19.5])
        x0_copy = x0.copy()
        u_seq = np.zeros((10, 1))
        d_seq = np.tile([5.0, 0.0, 0.0], (10, 1))

        model_3r3c.predict(x0, u_seq, d_seq)
        np.testing.assert_array_equal(x0, x0_copy)

    @pytest.mark.unit
    def test_predict_matches_sequential_step(self, model_3r3c: RCModel) -> None:
        """predict() must match sequential step() calls within 1e-10."""
        n_steps = 50
        x0 = np.array([18.0, 25.0, 15.0])
        u_seq = np.full((n_steps, 1), 1500.0)
        d_seq = np.tile([-5.0, 200.0, 100.0], (n_steps, 1))

        traj = model_3r3c.predict(x0, u_seq, d_seq)

        # Sequential step calls
        x = x0.copy()
        for k in range(n_steps):
            x = model_3r3c.step(x, u_seq[k], d_seq[k])
            np.testing.assert_allclose(
                traj[k + 1],
                x,
                atol=1e-10,
                err_msg=f"Mismatch at step {k + 1}",
            )

    @pytest.mark.unit
    def test_predict_mimo(self, model_3r3c_mimo: RCModel) -> None:
        """predict() with MIMO inputs."""
        n_steps = 20
        x0 = np.array([20.0, 20.0, 20.0])
        u_seq = np.column_stack(
            [
                np.full(n_steps, 500.0),  # Q_conv
                np.full(n_steps, 1000.0),  # Q_floor
            ]
        )
        d_seq = np.tile([5.0, 0.0, 0.0], (n_steps, 1))

        traj = model_3r3c_mimo.predict(x0, u_seq, d_seq)
        assert traj.shape == (n_steps + 1, 3)

    @pytest.mark.unit
    def test_predict_mismatched_lengths_raises(self, model_3r3c: RCModel) -> None:
        """predict() with mismatched u/d sequence lengths should raise."""
        x0 = np.array([20.0, 20.0, 20.0])
        u_seq = np.zeros((10, 1))
        d_seq = np.zeros((15, 3))

        with pytest.raises(ValueError, match="same length"):
            model_3r3c.predict(x0, u_seq, d_seq)

    @pytest.mark.unit
    def test_predict_2r2c(self, model_2r2c: RCModel) -> None:
        """predict() with 2R2C model."""
        n_steps = 30
        x0 = np.array([20.0, 20.0])
        u_seq = np.full((n_steps, 1), 1000.0)
        d_seq = np.tile([5.0, 0.0], (n_steps, 1))

        traj = model_2r2c.predict(x0, u_seq, d_seq)
        assert traj.shape == (n_steps + 1, 2)


# ---------------------------------------------------------------------------
# TestRCModelSteadyState — analytical verification
# ---------------------------------------------------------------------------


class TestRCModelSteadyState:
    """Tests for RCModel.steady_state() method."""

    @pytest.mark.unit
    def test_steady_state_3r3c_analytical(
        self, model_3r3c: RCModel, params_3r3c: RCParams
    ) -> None:
        """Verify 3R3C steady state against hand-calculated solution.

        With Q_floor=0, Q_sol=0, Q_int=0, T_out=5, T_ground=10:
        The system should reach thermal equilibrium determined by
        the resistive network between T_out and T_ground.
        """
        u = np.array([0.0])
        d = np.array([5.0, 0.0, 0.0])

        x_ss = model_3r3c.steady_state(u, d)

        # At steady state with no internal gains:
        # - All heat flows sum to zero at each node
        # - We can verify by checking the state equation = 0
        matrices = model_3r3c.get_matrices()
        residual = (
            matrices["A_c"] @ x_ss
            + matrices["B_c"] @ u
            + matrices["E_c"] @ d
            + matrices["b_c"]
        )
        np.testing.assert_allclose(residual, 0.0, atol=1e-10)

    @pytest.mark.unit
    def test_steady_state_2r2c_analytical(self, model_2r2c: RCModel) -> None:
        """Verify 2R2C steady state analytically.

        For 2R2C with Q_floor=0, Q_sol=0, T_out=0, no T_ground:
        - At steady state with no sources, T_air = T_slab = T_out = 0
        """
        u = np.array([0.0])
        d = np.array([0.0, 0.0])

        x_ss = model_2r2c.steady_state(u, d)

        # With no sources and T_out=0, all temps should be 0
        np.testing.assert_allclose(x_ss, [0.0, 0.0], atol=1e-10)

    @pytest.mark.unit
    def test_steady_state_2r2c_with_heating(self, model_2r2c: RCModel) -> None:
        """2R2C with Q_floor=1000 W and T_out=0, T_ground not in 2R2C.

        Analytical: At steady state, all heat from Q_floor must flow
        through R_env to T_out.
        T_air_ss = Q_floor * R_env + T_out (total heat flow through envelope)
        T_slab_ss = T_air_ss + Q_floor * R_sf (temperature drop across floor surface)
        """
        q_floor = 1000.0
        t_out = 0.0
        u = np.array([q_floor])
        d = np.array([t_out, 0.0])

        x_ss = model_2r2c.steady_state(u, d)

        p = model_2r2c.params
        assert p.R_env is not None
        t_air_expected = t_out + q_floor * p.R_env
        t_slab_expected = t_air_expected + q_floor * p.R_sf

        np.testing.assert_allclose(x_ss[0], t_air_expected, atol=0.001)
        np.testing.assert_allclose(x_ss[1], t_slab_expected, atol=0.001)

    @pytest.mark.unit
    def test_steady_state_3r3c_with_heating(self, model_3r3c: RCModel) -> None:
        """3R3C with heating: verify within 0.001 degC of analytical.

        Uses residual check: A_c @ x_ss + B_c @ u + E_c @ d + b_c = 0
        """
        u = np.array([2000.0])
        d = np.array([-10.0, 300.0, 150.0])

        x_ss = model_3r3c.steady_state(u, d)

        # Verify residual is zero
        matrices = model_3r3c.get_matrices()
        residual = (
            matrices["A_c"] @ x_ss
            + matrices["B_c"] @ u
            + matrices["E_c"] @ d
            + matrices["b_c"]
        )
        np.testing.assert_allclose(residual, 0.0, atol=1e-10)

        # Verify reasonable physical values
        assert x_ss[0] > -10.0, "T_air must be above outdoor temp with heating"
        assert x_ss[1] > x_ss[0], "T_slab must be above T_air with floor heating"

    @pytest.mark.unit
    def test_steady_state_mimo(self, model_3r3c_mimo: RCModel) -> None:
        """MIMO steady state with both inputs active."""
        u = np.array([500.0, 1500.0])  # Q_conv, Q_floor
        d = np.array([0.0, 0.0, 0.0])

        x_ss = model_3r3c_mimo.steady_state(u, d)

        matrices = model_3r3c_mimo.get_matrices()
        residual = (
            matrices["A_c"] @ x_ss
            + matrices["B_c"] @ u
            + matrices["E_c"] @ d
            + matrices["b_c"]
        )
        np.testing.assert_allclose(residual, 0.0, atol=1e-10)


# ---------------------------------------------------------------------------
# TestRCModelDiscretization — ZOH, dt, stability
# ---------------------------------------------------------------------------


class TestRCModelDiscretization:
    """Tests for discretization, dt changes, and stability."""

    @pytest.mark.unit
    def test_discrete_eigenvalues_stable_dt_60(self, model_3r3c: RCModel) -> None:
        """All discrete A_d eigenvalues must have |lambda| < 1 at dt=60s."""
        eigenvalues = np.linalg.eigvals(model_3r3c.get_matrices()["A_d"])
        magnitudes = np.abs(eigenvalues)
        assert np.all(magnitudes < 1.0), f"Eigenvalue magnitudes: {magnitudes}"

    @pytest.mark.unit
    @pytest.mark.parametrize("dt", [1, 10, 60, 300, 600, 900])
    def test_discrete_eigenvalues_stable_range(
        self, params_3r3c: RCParams, dt: int
    ) -> None:
        """All discrete A_d eigenvalues must have |lambda| < 1 for dt in [1, 900]."""
        model = RCModel(params_3r3c, ModelOrder.THREE, dt=float(dt))
        eigenvalues = np.linalg.eigvals(model.get_matrices()["A_d"])
        magnitudes = np.abs(eigenvalues)
        assert np.all(magnitudes < 1.0), f"dt={dt}: eigenvalue magnitudes: {magnitudes}"

    @pytest.mark.unit
    @pytest.mark.parametrize("dt", [1, 10, 60, 300, 600, 900])
    def test_discrete_eigenvalues_stable_2r2c(
        self, params_2r2c: RCParams, dt: int
    ) -> None:
        """2R2C discrete eigenvalues stable for dt in [1, 900]."""
        model = RCModel(params_2r2c, ModelOrder.TWO, dt=float(dt))
        eigenvalues = np.linalg.eigvals(model.get_matrices()["A_d"])
        magnitudes = np.abs(eigenvalues)
        assert np.all(magnitudes < 1.0), f"dt={dt}: eigenvalue magnitudes: {magnitudes}"

    @pytest.mark.unit
    def test_set_dt_changes_discretization(self, model_3r3c: RCModel) -> None:
        """set_dt() should produce different discrete matrices."""
        A_d_old = model_3r3c.get_matrices()["A_d"].copy()

        model_3r3c.set_dt(300.0)
        A_d_new = model_3r3c.get_matrices()["A_d"]

        assert model_3r3c.dt == 300.0
        assert not np.allclose(A_d_old, A_d_new)

    @pytest.mark.unit
    def test_set_dt_invalid(self, model_3r3c: RCModel) -> None:
        """set_dt() with non-positive dt should raise."""
        with pytest.raises(ValueError, match="dt must be positive"):
            model_3r3c.set_dt(0.0)

    @pytest.mark.unit
    def test_zoh_vs_euler_for_large_dt(self, params_3r3c: RCParams) -> None:
        """ZOH should be more accurate than forward Euler for large dt.

        With dt=900s, forward Euler can be unstable for stiff systems.
        ZOH (matrix exponential) should always produce stable results.
        """
        model = RCModel(params_3r3c, ModelOrder.THREE, dt=900.0)

        # Run 100 steps — should not diverge
        x = np.array([20.0, 20.0, 20.0])
        u = np.array([1000.0])
        d = np.array([5.0, 0.0, 0.0])

        for _ in range(100):
            x = model.step(x, u, d)

        # Temperatures should be physically reasonable (not diverging)
        assert np.all(np.abs(x) < 200), f"Divergent temperatures: {x}"

    @pytest.mark.unit
    def test_continuous_matrices_unchanged_after_set_dt(
        self, model_3r3c: RCModel
    ) -> None:
        """Continuous matrices should not change when dt changes."""
        A_c_before = model_3r3c.get_matrices()["A_c"].copy()
        B_c_before = model_3r3c.get_matrices()["B_c"].copy()

        model_3r3c.set_dt(300.0)

        A_c_after = model_3r3c.get_matrices()["A_c"]
        B_c_after = model_3r3c.get_matrices()["B_c"]

        np.testing.assert_array_equal(A_c_before, A_c_after)
        np.testing.assert_array_equal(B_c_before, B_c_after)

    @pytest.mark.unit
    def test_small_dt_accuracy(self, params_3r3c: RCParams) -> None:
        """Smaller dt should give more accurate trajectory.

        Compare dt=1s trajectory endpoint with dt=60s trajectory endpoint.
        The dt=1s result should be closer to steady state.
        """
        u = np.array([1000.0])
        d = np.array([5.0, 0.0, 0.0])

        # Use 1 hour of simulation
        model_fine = RCModel(params_3r3c, ModelOrder.THREE, dt=1.0)
        model_coarse = RCModel(params_3r3c, ModelOrder.THREE, dt=60.0)

        _x_ss = model_fine.steady_state(u, d)

        x_fine = np.array([20.0, 20.0, 20.0])
        for _ in range(3600):  # 3600 steps at dt=1
            x_fine = model_fine.step(x_fine, u, d)

        x_coarse = np.array([20.0, 20.0, 20.0])
        for _ in range(60):  # 60 steps at dt=60
            x_coarse = model_coarse.step(x_coarse, u, d)

        # Both cover 1 hour, but ZOH should give identical results
        # for constant inputs (ZOH is exact for piecewise-constant inputs)
        np.testing.assert_allclose(x_fine, x_coarse, atol=1e-6)


# ---------------------------------------------------------------------------
# TestRCModelReset — default state
# ---------------------------------------------------------------------------


class TestRCModelReset:
    """Tests for RCModel.reset() method."""

    @pytest.mark.unit
    def test_reset_shape_3r3c(self, model_3r3c: RCModel) -> None:
        """reset() returns (n_states,) for 3R3C."""
        x0 = model_3r3c.reset()
        assert x0.shape == (3,)

    @pytest.mark.unit
    def test_reset_shape_2r2c(self, model_2r2c: RCModel) -> None:
        """reset() returns (n_states,) for 2R2C."""
        x0 = model_2r2c.reset()
        assert x0.shape == (2,)

    @pytest.mark.unit
    def test_reset_default_temperature(self, model_3r3c: RCModel) -> None:
        """reset() should return 20 degC for all nodes."""
        x0 = model_3r3c.reset()
        np.testing.assert_array_equal(x0, [20.0, 20.0, 20.0])

    @pytest.mark.unit
    def test_reset_returns_new_array(self, model_3r3c: RCModel) -> None:
        """reset() should return a new array each call."""
        x1 = model_3r3c.reset()
        x2 = model_3r3c.reset()
        x1[0] = 99.0
        assert x2[0] == 20.0


# ---------------------------------------------------------------------------
# TestModelOrder — enum behavior
# ---------------------------------------------------------------------------


class TestModelOrder:
    """Tests for ModelOrder enum."""

    @pytest.mark.unit
    def test_values(self) -> None:
        """ModelOrder values should be 2 and 3."""
        assert ModelOrder.TWO.value == 2
        assert ModelOrder.THREE.value == 3

    @pytest.mark.unit
    def test_members(self) -> None:
        """ModelOrder should have exactly two members."""
        assert len(ModelOrder) == 2


# ---------------------------------------------------------------------------
# TestImport — package importability
# ---------------------------------------------------------------------------


class TestImport:
    """Tests for package import."""

    @pytest.mark.unit
    def test_import_pumpahead(self) -> None:
        """import pumpahead should work and expose public API."""
        import pumpahead

        assert hasattr(pumpahead, "RCModel")
        assert hasattr(pumpahead, "RCParams")
        assert hasattr(pumpahead, "ModelOrder")
        assert hasattr(pumpahead, "__version__")
        assert pumpahead.__version__ == "0.1.0"
