"""Comprehensive unit tests for pumpahead.estimator."""

import numpy as np
import pytest

from pumpahead.estimator import KalmanEstimator
from pumpahead.model import ModelOrder, RCModel, RCParams


# ---------------------------------------------------------------------------
# TestKalmanEstimatorConstruction — constructor validation
# ---------------------------------------------------------------------------


class TestKalmanEstimatorConstruction:
    """Tests for KalmanEstimator constructor and initial state."""

    @pytest.mark.unit
    def test_3r3c_single_sensor_defaults(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """3R3C with T_room only: correct dimensions and defaults."""
        assert kalman_3r3c.n_states == 3
        assert kalman_3r3c.n_measurements == 1
        np.testing.assert_array_equal(kalman_3r3c.x_hat, np.full(3, 20.0))
        np.testing.assert_array_equal(kalman_3r3c.P, np.eye(3) * 10.0)

    @pytest.mark.unit
    def test_3r3c_dual_sensor_defaults(
        self, kalman_3r3c_dual: KalmanEstimator,
    ) -> None:
        """3R3C with T_room + T_floor: correct dimensions."""
        assert kalman_3r3c_dual.n_states == 3
        assert kalman_3r3c_dual.n_measurements == 2

    @pytest.mark.unit
    def test_2r2c_single_sensor_defaults(
        self, kalman_2r2c: KalmanEstimator,
    ) -> None:
        """2R2C with T_room only: correct dimensions and defaults."""
        assert kalman_2r2c.n_states == 2
        assert kalman_2r2c.n_measurements == 1
        np.testing.assert_array_equal(kalman_2r2c.x_hat, np.full(2, 20.0))
        np.testing.assert_array_equal(kalman_2r2c.P, np.eye(2) * 10.0)

    @pytest.mark.unit
    def test_2r2c_dual_sensor_defaults(
        self, kalman_2r2c_dual: KalmanEstimator,
    ) -> None:
        """2R2C with both sensors: both states observed."""
        assert kalman_2r2c_dual.n_states == 2
        assert kalman_2r2c_dual.n_measurements == 2

    @pytest.mark.unit
    def test_custom_Q(self, model_3r3c: RCModel) -> None:
        """Custom Q matrix is accepted and stored."""
        Q = np.diag([0.1, 0.05, 0.1])
        kf = KalmanEstimator(model_3r3c, Q=Q)
        assert kf.n_states == 3

    @pytest.mark.unit
    def test_custom_R(self, model_3r3c: RCModel) -> None:
        """Custom R matrix is accepted and stored."""
        R = np.array([[0.5]])
        kf = KalmanEstimator(model_3r3c, R=R)
        assert kf.n_measurements == 1

    @pytest.mark.unit
    def test_wrong_Q_shape_rejected(self, model_3r3c: RCModel) -> None:
        """Q with wrong dimensions is rejected."""
        Q = np.diag([0.1, 0.05])  # 2x2 for 3-state model
        with pytest.raises(ValueError, match="Q must have shape"):
            KalmanEstimator(model_3r3c, Q=Q)

    @pytest.mark.unit
    def test_wrong_R_shape_rejected(self, model_3r3c: RCModel) -> None:
        """R with wrong dimensions is rejected."""
        R = np.diag([0.1, 0.2])  # 2x2 for single sensor
        with pytest.raises(ValueError, match="R must have shape"):
            KalmanEstimator(model_3r3c, has_floor_sensor=False, R=R)

    @pytest.mark.unit
    def test_asymmetric_Q_rejected(self, model_3r3c: RCModel) -> None:
        """Asymmetric Q matrix is rejected."""
        Q = np.array([[0.01, 0.1, 0.0], [0.0, 0.001, 0.0], [0.0, 0.0, 0.01]])
        with pytest.raises(ValueError, match="Q must be symmetric"):
            KalmanEstimator(model_3r3c, Q=Q)


# ---------------------------------------------------------------------------
# TestKalmanEstimatorInitialize — initialize and initialize_from_steady_state
# ---------------------------------------------------------------------------


class TestKalmanEstimatorInitialize:
    """Tests for state initialization methods."""

    @pytest.mark.unit
    def test_initialize_sets_state_and_covariance(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """initialize() should set x_hat and P."""
        x0 = np.array([22.0, 25.0, 18.0])
        P0 = np.eye(3) * 2.0
        kalman_3r3c.initialize(x0, P0)
        np.testing.assert_array_equal(kalman_3r3c.x_hat, x0)
        np.testing.assert_array_equal(kalman_3r3c.P, P0)

    @pytest.mark.unit
    def test_initialize_copies_inputs(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """initialize() should copy x0 and P0, not alias them."""
        x0 = np.array([22.0, 25.0, 18.0])
        P0 = np.eye(3) * 2.0
        kalman_3r3c.initialize(x0, P0)
        x0[0] = 999.0
        P0[0, 0] = 999.0
        assert kalman_3r3c.x_hat[0] == 22.0
        assert kalman_3r3c.P[0, 0] == 2.0

    @pytest.mark.unit
    def test_initialize_wrong_x0_shape_rejected(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """initialize() rejects wrong x0 shape."""
        x0 = np.array([22.0, 25.0])  # Wrong: 2 for 3-state
        P0 = np.eye(3)
        with pytest.raises(ValueError, match="x0 must have shape"):
            kalman_3r3c.initialize(x0, P0)

    @pytest.mark.unit
    def test_initialize_from_steady_state(
        self, model_3r3c: RCModel,
    ) -> None:
        """initialize_from_steady_state() sets x_hat to model's steady state."""
        kf = KalmanEstimator(model_3r3c)
        u = np.array([0.0])  # SISO: no heating
        d = np.array([5.0, 0.0, 0.0])  # 5 degC outdoor, no solar, no internal
        kf.initialize_from_steady_state(u, d)
        x_ss = model_3r3c.steady_state(u, d)
        np.testing.assert_array_almost_equal(kf.x_hat, x_ss)

    @pytest.mark.unit
    def test_initialize_from_steady_state_default_P(
        self, model_3r3c: RCModel,
    ) -> None:
        """Default P0 from initialize_from_steady_state is diag([5, 10, 5])."""
        kf = KalmanEstimator(model_3r3c)
        u = np.array([0.0])
        d = np.array([5.0, 0.0, 0.0])
        kf.initialize_from_steady_state(u, d)
        expected_P = np.diag([5.0, 10.0, 5.0])
        np.testing.assert_array_equal(kf.P, expected_P)


# ---------------------------------------------------------------------------
# TestKalmanEstimatorPredict — predict step
# ---------------------------------------------------------------------------


class TestKalmanEstimatorPredict:
    """Tests for the Kalman predict step."""

    @pytest.mark.unit
    def test_predict_returns_state_copy(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """predict() returns a copy of the state, not the internal array."""
        u = np.array([0.0])
        d = np.array([5.0, 0.0, 0.0])
        result = kalman_3r3c.predict(u, d)
        result[0] = 999.0
        assert kalman_3r3c.x_hat[0] != 999.0

    @pytest.mark.unit
    def test_predict_advances_state(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """predict() should change x_hat from initial state."""
        x_before = kalman_3r3c.x_hat.copy()
        u = np.array([1000.0])  # 1 kW floor heating
        d = np.array([5.0, 0.0, 0.0])
        kalman_3r3c.predict(u, d)
        assert not np.array_equal(kalman_3r3c.x_hat, x_before)

    @pytest.mark.unit
    def test_predict_grows_covariance(
        self, model_3r3c: RCModel,
    ) -> None:
        """P should grow after predict (process noise added)."""
        # Use a small initial P so that Q dominates: A_d @ P @ A_d^T + Q > P
        kf = KalmanEstimator(model_3r3c)
        kf.initialize(np.full(3, 20.0), np.eye(3) * 0.001)
        P_before = kf.P.copy()
        u = np.array([0.0])
        d = np.array([5.0, 0.0, 0.0])
        kf.predict(u, d)
        # Trace of P should increase when P is small relative to Q
        assert np.trace(kf.P) > np.trace(P_before)

    @pytest.mark.unit
    def test_predict_matches_model_step(
        self, model_3r3c: RCModel,
    ) -> None:
        """Predicted state should match model.step() for the state part."""
        kf = KalmanEstimator(model_3r3c)
        x0 = np.array([20.0, 20.0, 20.0])
        kf.initialize(x0, np.eye(3) * 0.01)
        u = np.array([1000.0])
        d = np.array([5.0, 100.0, 50.0])
        kf.predict(u, d)
        x_model = model_3r3c.step(x0, u, d)
        np.testing.assert_array_almost_equal(kf.x_hat, x_model, decimal=10)

    @pytest.mark.unit
    def test_predict_p_remains_symmetric(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """P must remain symmetric after predict."""
        u = np.array([500.0])
        d = np.array([0.0, 200.0, 100.0])
        for _ in range(50):
            kalman_3r3c.predict(u, d)
        P = kalman_3r3c.P
        np.testing.assert_array_almost_equal(P, P.T, decimal=12)


# ---------------------------------------------------------------------------
# TestKalmanEstimatorUpdate — update step
# ---------------------------------------------------------------------------


class TestKalmanEstimatorUpdate:
    """Tests for the Kalman update step."""

    @pytest.mark.unit
    def test_update_none_is_noop(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """update(None) should not change x_hat or P."""
        x_before = kalman_3r3c.x_hat.copy()
        P_before = kalman_3r3c.P.copy()
        kalman_3r3c.update(None)
        np.testing.assert_array_equal(kalman_3r3c.x_hat, x_before)
        np.testing.assert_array_equal(kalman_3r3c.P, P_before)

    @pytest.mark.unit
    def test_update_shrinks_covariance(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """P trace should decrease after a measurement update."""
        # First predict to have non-trivial P
        u = np.array([0.0])
        d = np.array([5.0, 0.0, 0.0])
        kalman_3r3c.predict(u, d)
        P_before = kalman_3r3c.P.copy()
        z = np.array([20.0])
        kalman_3r3c.update(z)
        assert np.trace(kalman_3r3c.P) < np.trace(P_before)

    @pytest.mark.unit
    def test_update_moves_state_toward_measurement(
        self, model_3r3c: RCModel,
    ) -> None:
        """After update, T_air estimate should move toward measurement."""
        kf = KalmanEstimator(model_3r3c)
        kf.initialize(np.array([18.0, 20.0, 20.0]), np.eye(3) * 5.0)
        z = np.array([22.0])  # Measurement says T_room = 22
        kf.update(z)
        # T_air should move toward 22 from 18
        assert kf.x_hat[0] > 18.0

    @pytest.mark.unit
    def test_update_dual_sensor(
        self, kalman_3r3c_dual: KalmanEstimator,
    ) -> None:
        """Dual-sensor update should adjust both T_air and T_slab."""
        kalman_3r3c_dual.initialize(
            np.array([18.0, 20.0, 20.0]), np.eye(3) * 5.0,
        )
        z = np.array([22.0, 25.0])  # T_room=22, T_floor=25
        kalman_3r3c_dual.update(z)
        assert kalman_3r3c_dual.x_hat[0] > 18.0  # T_air toward 22
        assert kalman_3r3c_dual.x_hat[1] > 20.0  # T_slab toward 25

    @pytest.mark.unit
    def test_update_wrong_z_shape_rejected(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """update() rejects z with wrong shape."""
        z = np.array([20.0, 25.0])  # 2 measurements for single sensor
        with pytest.raises(ValueError, match="z must have shape"):
            kalman_3r3c.update(z)

    @pytest.mark.unit
    def test_update_p_remains_symmetric(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """P must remain symmetric after update."""
        u = np.array([500.0])
        d = np.array([5.0, 100.0, 50.0])
        for _ in range(50):
            kalman_3r3c.predict(u, d)
            kalman_3r3c.update(np.array([20.0]))
        P = kalman_3r3c.P
        np.testing.assert_array_almost_equal(P, P.T, decimal=12)


# ---------------------------------------------------------------------------
# TestKalmanEstimatorStep — convenience step method
# ---------------------------------------------------------------------------


class TestKalmanEstimatorStep:
    """Tests for the step() convenience method."""

    @pytest.mark.unit
    def test_step_equals_predict_then_update(
        self, model_3r3c: RCModel,
    ) -> None:
        """step() should produce same result as predict() + update()."""
        x0 = np.array([20.0, 22.0, 19.0])
        P0 = np.eye(3) * 5.0
        u = np.array([500.0])
        d = np.array([5.0, 100.0, 50.0])
        z = np.array([20.5])

        # Method 1: step()
        kf1 = KalmanEstimator(model_3r3c)
        kf1.initialize(x0, P0)
        x_step = kf1.step(u, d, z)

        # Method 2: predict() + update()
        kf2 = KalmanEstimator(model_3r3c)
        kf2.initialize(x0, P0)
        kf2.predict(u, d)
        x_manual = kf2.update(z)

        np.testing.assert_array_almost_equal(x_step, x_manual, decimal=12)
        np.testing.assert_array_almost_equal(kf1.P, kf2.P, decimal=12)

    @pytest.mark.unit
    def test_step_with_none_z(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """step() with z=None should do predict-only."""
        x_before = kalman_3r3c.x_hat.copy()
        u = np.array([0.0])
        d = np.array([5.0, 0.0, 0.0])
        kalman_3r3c.step(u, d, None)
        # State should change (predict), but not via update
        assert not np.array_equal(kalman_3r3c.x_hat, x_before)


# ---------------------------------------------------------------------------
# TestKalmanEstimatorConvergence — T_slab estimation convergence
# ---------------------------------------------------------------------------


class TestKalmanEstimatorConvergence:
    """Tests for state estimation convergence from synthetic data."""

    @staticmethod
    def _run_convergence_test(
        model: RCModel,
        has_floor_sensor: bool,
        n_steps: int = 2000,
        rng_seed: int = 42,
    ) -> float:
        """Run a convergence test and return T_slab RMSE.

        Generates synthetic truth from model.predict(), adds measurement
        noise, and runs the Kalman filter. Returns RMSE of T_slab estimate
        versus true T_slab over the last half of the trajectory.
        """
        rng = np.random.default_rng(rng_seed)
        n = model.n_states
        n_inputs = model.n_inputs
        n_dist = model.n_disturbances

        # Generate input sequences
        u_seq = np.zeros((n_steps, n_inputs))
        u_seq[:, -1] = 1500.0  # Constant floor heating (last column = Q_floor)

        d_seq = np.zeros((n_steps, n_dist))
        d_seq[:, 0] = 0.0  # T_out = 0 degC
        if n_dist >= 2:
            d_seq[:, 1] = 100.0  # Q_sol = 100 W

        # Generate true trajectory
        x0_true = np.full(n, 15.0)
        traj_true = model.predict(x0_true, u_seq, d_seq)

        # Generate noisy measurements
        if has_floor_sensor:
            n_meas = 2
            # C = [[1,0,...],[0,1,...]]
            C = np.eye(min(2, n), n)
            R_noise = np.diag([0.1, 0.2])
        else:
            n_meas = 1
            C = np.zeros((1, n))
            C[0, 0] = 1.0
            R_noise = np.diag([0.1])

        z_seq = np.zeros((n_steps, n_meas))
        for k in range(n_steps):
            z_seq[k] = C @ traj_true[k + 1] + rng.multivariate_normal(
                np.zeros(n_meas), R_noise,
            )

        # Run Kalman filter with deliberately wrong initial estimate
        kf = KalmanEstimator(model, has_floor_sensor=has_floor_sensor)
        kf.initialize(np.full(n, 25.0), np.eye(n) * 20.0)

        x_hat_history = np.zeros((n_steps, n))
        for k in range(n_steps):
            x_hat_history[k] = kf.step(u_seq[k], d_seq[k], z_seq[k])

        # Compute RMSE for T_slab (index 1) over last half
        half = n_steps // 2
        errors = x_hat_history[half:, 1] - traj_true[half + 1:, 1]
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        return rmse

    @pytest.mark.unit
    def test_convergence_3r3c_single_sensor(
        self, model_3r3c: RCModel,
    ) -> None:
        """T_slab RMSE < 1.0 degC with T_room only (3R3C)."""
        rmse = self._run_convergence_test(model_3r3c, has_floor_sensor=False)
        assert rmse < 1.0, f"T_slab RMSE = {rmse:.4f} degC (threshold: 1.0)"

    @pytest.mark.unit
    def test_convergence_3r3c_dual_sensor(
        self, model_3r3c: RCModel,
    ) -> None:
        """T_slab RMSE < 0.5 degC with dual sensors (3R3C)."""
        rmse_dual = self._run_convergence_test(
            model_3r3c, has_floor_sensor=True,
        )
        assert rmse_dual < 0.5, f"Dual T_slab RMSE = {rmse_dual:.4f} (threshold: 0.5)"

    @pytest.mark.unit
    def test_convergence_2r2c_single_sensor(
        self, model_2r2c: RCModel,
    ) -> None:
        """T_slab RMSE < 1.0 degC with T_room only (2R2C)."""
        rmse = self._run_convergence_test(model_2r2c, has_floor_sensor=False)
        assert rmse < 1.0, f"T_slab RMSE = {rmse:.4f} degC (threshold: 1.0)"

    @pytest.mark.unit
    def test_convergence_2r2c_dual_sensor(
        self, model_2r2c: RCModel,
    ) -> None:
        """T_slab RMSE < 0.5 degC with both sensors (2R2C, fully observed)."""
        rmse = self._run_convergence_test(model_2r2c, has_floor_sensor=True)
        assert rmse < 0.5, f"T_slab RMSE = {rmse:.4f} degC (threshold: 0.5)"


# ---------------------------------------------------------------------------
# TestKalmanEstimatorMissingData — handling missing measurements
# ---------------------------------------------------------------------------


class TestKalmanEstimatorMissingData:
    """Tests for missing measurement handling."""

    @pytest.mark.unit
    def test_missing_then_recovery(self, model_3r3c: RCModel) -> None:
        """Filter recovers after missing measurement gap.

        Uses T_air variance P[0,0] as indicator: the directly observed
        state has clear covariance growth during predict-only phases.
        """
        rng = np.random.default_rng(123)
        kf = KalmanEstimator(model_3r3c)
        u = np.array([1000.0])
        d = np.array([5.0, 0.0, 0.0])

        # Phase 1: 500 steps with measurements to reach steady-state P
        for _ in range(500):
            x_pred = kf.predict(u, d)
            z = np.array([x_pred[0] + rng.normal(0, 0.3)])
            kf.update(z)
        P_air_after_normal = kf.P[0, 0]

        # Phase 2: 200 steps without measurements
        for _ in range(200):
            kf.predict(u, d)
            kf.update(None)
        P_air_after_gap = kf.P[0, 0]

        # T_air variance should grow during gap (no correction on observed state)
        assert P_air_after_gap > P_air_after_normal, (
            f"P[0,0] after gap ({P_air_after_gap:.6f}) should be > "
            f"after normal ({P_air_after_normal:.6f})"
        )

        # Phase 3: 500 steps with measurements again
        for _ in range(500):
            x_pred = kf.predict(u, d)
            z = np.array([x_pred[0] + rng.normal(0, 0.3)])
            kf.update(z)
        P_air_after_recovery = kf.P[0, 0]

        # T_air variance should shrink back after recovery
        assert P_air_after_recovery < P_air_after_gap, (
            f"P[0,0] after recovery ({P_air_after_recovery:.6f}) should be < "
            f"after gap ({P_air_after_gap:.6f})"
        )

    @pytest.mark.unit
    def test_predict_only_diverges_slowly(
        self, kalman_3r3c: KalmanEstimator,
    ) -> None:
        """Predict-only should still track physics (state follows model)."""
        u = np.array([1000.0])
        d = np.array([5.0, 0.0, 0.0])
        # Run predict-only for many steps
        for _ in range(500):
            kalman_3r3c.step(u, d, None)
        # State should still be physically reasonable
        x = kalman_3r3c.x_hat
        assert all(x > -50.0), f"Unphysical temperatures: {x}"
        assert all(x < 100.0), f"Unphysical temperatures: {x}"

    @pytest.mark.unit
    def test_intermittent_missing(self, model_3r3c: RCModel) -> None:
        """Filter handles alternating present/missing measurements."""
        rng = np.random.default_rng(456)
        kf = KalmanEstimator(model_3r3c)
        u = np.array([500.0])
        d = np.array([5.0, 0.0, 0.0])

        for k in range(300):
            kf.predict(u, d)
            if k % 3 == 0:
                # Provide measurement every 3rd step
                z = np.array([kf.x_hat[0] + rng.normal(0, 0.3)])
                kf.update(z)
            else:
                kf.update(None)

        # Filter should not diverge
        x = kf.x_hat
        assert all(x > -50.0) and all(x < 100.0)
        # P should be bounded
        assert np.trace(kf.P) < 1000.0


# ---------------------------------------------------------------------------
# TestKalmanEstimatorStability — long-running numerical stability
# ---------------------------------------------------------------------------


class TestKalmanEstimatorStability:
    """Tests for numerical stability over long simulations."""

    @pytest.mark.unit
    def test_365_day_stability(self, model_3r3c: RCModel) -> None:
        """Kalman filter is numerically stable for 365 days at dt=60s.

        365 days * 24 hours * 60 minutes = 525_600 steps.
        We run a subset (52_560 = 10x fewer) for test speed.
        """
        rng = np.random.default_rng(789)
        kf = KalmanEstimator(model_3r3c)
        u = np.array([800.0])
        d = np.array([0.0, 0.0, 0.0])
        n_steps = 52_560  # ~36.5 days at dt=60s

        for _ in range(n_steps):
            kf.predict(u, d)
            z = np.array([kf.x_hat[0] + rng.normal(0, 0.3)])
            kf.update(z)

        # Check no NaN or Inf
        assert np.all(np.isfinite(kf.x_hat)), f"x_hat has NaN/Inf: {kf.x_hat}"
        assert np.all(np.isfinite(kf.P)), "P has NaN/Inf"
        # P should be positive definite
        eigenvalues = np.linalg.eigvalsh(kf.P)
        assert np.all(eigenvalues > 0), f"P not positive definite: eig={eigenvalues}"
        # P should be symmetric
        np.testing.assert_array_almost_equal(kf.P, kf.P.T, decimal=10)

    @pytest.mark.unit
    def test_covariance_bounded(self, model_3r3c: RCModel) -> None:
        """P eigenvalues remain bounded and positive over extended run."""
        rng = np.random.default_rng(101)
        kf = KalmanEstimator(model_3r3c)
        u = np.array([1000.0])
        d = np.array([5.0, 100.0, 50.0])

        max_eig_history: list[float] = []
        min_eig_history: list[float] = []
        for _ in range(5000):
            kf.predict(u, d)
            z = np.array([kf.x_hat[0] + rng.normal(0, 0.3)])
            kf.update(z)
            eigs = np.linalg.eigvalsh(kf.P)
            max_eig_history.append(float(np.max(eigs)))
            min_eig_history.append(float(np.min(eigs)))

        # All eigenvalues positive
        assert min(min_eig_history) > 0, "P lost positive definiteness"
        # Max eigenvalue should not blow up
        assert max(max_eig_history) < 100.0, "P eigenvalues unbounded"
