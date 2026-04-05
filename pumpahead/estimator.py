"""Linear Kalman Filter for RC thermal model state estimation.

Reconstructs the full state vector [T_air, T_slab, T_wall] (3R3C) or
[T_air, T_slab] (2R2C) from temperature measurements using the standard
predict-update Kalman filter cycle.

The estimator provides x_0 initial conditions for MPC optimization every
5-15 min control cycle. It supports two measurement configurations:
  - T_room only: C = [[1, 0, 0]] (3R3C) or [[1, 0]] (2R2C)
  - T_room + T_floor_surface: C = [[1,0,0],[0,1,0]] (3R3C) or [[1,0],[0,1]] (2R2C)

Missing measurements are handled gracefully: when z=None, the update step
is skipped and only the predict step advances the state. The error covariance
P grows during predict-only phases, and the filter self-corrects when
measurements resume.

Units: temperatures in degC, covariances in degC^2.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pumpahead.model import RCModel


class KalmanEstimator:
    """Linear Kalman Filter for RC thermal model state estimation.

    Reconstructs hidden thermal states (T_slab, T_wall) from observable
    measurements (T_room, optionally T_floor_surface). The filter uses
    the discretized system matrices from an RCModel instance.

    Typical usage:
        model = RCModel(params, ModelOrder.THREE, dt=60.0)
        kf = KalmanEstimator(model, has_floor_sensor=False)
        kf.initialize_from_steady_state(u, d)

        for step in range(n_steps):
            x_hat = kf.step(u[step], d[step], z[step])
    """

    def __init__(
        self,
        model: RCModel,
        has_floor_sensor: bool = False,
        Q: NDArray[np.float64] | None = None,
        R: NDArray[np.float64] | None = None,
    ) -> None:
        """Initialize the Kalman estimator.

        Args:
            model: RC thermal model providing discretized system matrices.
            has_floor_sensor: If True, uses both T_room and T_floor_surface
                measurements. If False, uses T_room only.
            Q: Process noise covariance matrix, shape (n_states, n_states).
                Defaults to a diagonal matrix tuned for typical RC models.
            R: Measurement noise covariance matrix, shape (n_meas, n_meas).
                Defaults to a diagonal matrix for typical sensor noise.

        Raises:
            ValueError: If Q or R have wrong shape or are not symmetric
                positive semi-definite.
        """
        self._model = model
        self._has_floor_sensor = has_floor_sensor
        n = model.n_states

        # Extract discrete-time system matrices
        matrices = model.get_matrices()
        self._A_d: NDArray[np.float64] = matrices["A_d"]
        self._B_d: NDArray[np.float64] = matrices["B_d"]
        self._E_d: NDArray[np.float64] = matrices["E_d"]
        self._b_d: NDArray[np.float64] = matrices["b_d"]

        # Build observation matrix C
        if has_floor_sensor:
            # T_room = T_air (index 0), T_floor_surface ~ T_slab (index 1)
            self._C = np.eye(min(2, n), n, dtype=np.float64)
        else:
            # T_room = T_air (index 0) only
            self._C = np.zeros((1, n), dtype=np.float64)
            self._C[0, 0] = 1.0

        n_meas = self._C.shape[0]

        # Process noise covariance Q
        if Q is not None:
            Q = np.asarray(Q, dtype=np.float64)
            self._validate_covariance(Q, n, "Q")
            self._Q = Q
        else:
            if n == 3:
                self._Q = np.diag(np.array([0.01, 0.001, 0.01]))
            else:
                self._Q = np.diag(np.array([0.01, 0.001]))

        # Measurement noise covariance R
        if R is not None:
            R = np.asarray(R, dtype=np.float64)
            self._validate_covariance(R, n_meas, "R")
            self._R = R
        else:
            if n_meas == 2:
                self._R = np.diag(np.array([0.1, 0.2]))
            else:
                self._R = np.diag(np.array([0.1]))

        # State estimate and error covariance
        self._x_hat: NDArray[np.float64] = model.reset().astype(np.float64)
        self._P: NDArray[np.float64] = np.eye(n, dtype=np.float64) * 10.0

    @staticmethod
    def _validate_covariance(
        matrix: NDArray[np.float64], expected_size: int, name: str,
    ) -> None:
        """Validate that a matrix is square, correctly sized, and symmetric PSD.

        Args:
            matrix: The matrix to validate.
            expected_size: Expected number of rows and columns.
            name: Name for error messages (e.g. "Q" or "R").

        Raises:
            ValueError: If validation fails.
        """
        if matrix.shape != (expected_size, expected_size):
            msg = (
                f"{name} must have shape ({expected_size}, {expected_size}), "
                f"got {matrix.shape}"
            )
            raise ValueError(msg)
        if not np.allclose(matrix, matrix.T):
            msg = f"{name} must be symmetric"
            raise ValueError(msg)
        eigenvalues = np.linalg.eigvalsh(matrix)
        if np.any(eigenvalues < -1e-10):
            msg = f"{name} must be positive semi-definite"
            raise ValueError(msg)

    @property
    def x_hat(self) -> NDArray[np.float64]:
        """Current state estimate (copy).

        Returns:
            State estimate vector, shape (n_states,).
        """
        return self._x_hat.copy()

    @property
    def P(self) -> NDArray[np.float64]:
        """Current error covariance matrix (copy).

        Returns:
            Error covariance matrix, shape (n_states, n_states).
        """
        return self._P.copy()

    @property
    def n_states(self) -> int:
        """Number of state variables."""
        return self._model.n_states

    @property
    def n_measurements(self) -> int:
        """Number of measurement variables."""
        return self._C.shape[0]

    def initialize(
        self, x0: NDArray[np.float64], P0: NDArray[np.float64],
    ) -> None:
        """Set the state estimate and error covariance directly.

        Args:
            x0: Initial state estimate, shape (n_states,).
            P0: Initial error covariance, shape (n_states, n_states).

        Raises:
            ValueError: If shapes are incorrect or P0 is not symmetric PSD.
        """
        n = self.n_states
        x0 = np.asarray(x0, dtype=np.float64)
        P0 = np.asarray(P0, dtype=np.float64)

        if x0.shape != (n,):
            msg = f"x0 must have shape ({n},), got {x0.shape}"
            raise ValueError(msg)
        self._validate_covariance(P0, n, "P0")

        self._x_hat = x0.copy()
        self._P = P0.copy()

    def initialize_from_steady_state(
        self,
        u: NDArray[np.float64],
        d: NDArray[np.float64],
        P0: NDArray[np.float64] | None = None,
    ) -> None:
        """Initialize state from the model's steady-state solution.

        Sets x_hat to the steady-state temperatures for the given constant
        inputs and disturbances. P0 defaults to a diagonal with high
        uncertainty, especially for T_slab which is typically unobserved.

        Args:
            u: Constant control input vector, shape (n_inputs,).
            d: Constant disturbance vector, shape (n_disturbances,).
            P0: Initial error covariance, shape (n_states, n_states).
                Defaults to diag([5.0, 10.0, 5.0]) for 3R3C
                or diag([5.0, 10.0]) for 2R2C.

        Raises:
            ValueError: If P0 has wrong shape or is not symmetric PSD.
        """
        n = self.n_states
        x_ss = self._model.steady_state(u, d)
        self._x_hat = x_ss.copy()

        if P0 is not None:
            P0 = np.asarray(P0, dtype=np.float64)
            self._validate_covariance(P0, n, "P0")
            self._P = P0.copy()
        else:
            if n == 3:
                self._P = np.diag(np.array([5.0, 10.0, 5.0]))
            else:
                self._P = np.diag(np.array([5.0, 10.0]))

    def predict(
        self,
        u: NDArray[np.float64],
        d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Kalman predict step: propagate state and covariance forward.

        x_hat_minus = A_d @ x_hat + B_d @ u + E_d @ d + b_d
        P_minus = A_d @ P @ A_d^T + Q

        Args:
            u: Control input vector, shape (n_inputs,).
            d: Disturbance vector, shape (n_disturbances,).

        Returns:
            Predicted state estimate (copy), shape (n_states,).
        """
        self._x_hat = (
            self._A_d @ self._x_hat
            + self._B_d @ u
            + self._E_d @ d
            + self._b_d
        )
        self._P = self._A_d @ self._P @ self._A_d.T + self._Q
        # Symmetrize for numerical stability
        self._P = (self._P + self._P.T) / 2.0
        return self._x_hat.copy()

    def update(
        self, z: NDArray[np.float64] | None,
    ) -> NDArray[np.float64]:
        """Kalman update step: incorporate measurement.

        If z is None, skip the update (predict-only). This handles missing
        measurements gracefully: P grows during predict-only phases, and
        the filter self-corrects when measurements resume.

        Innovation: y = z - C @ x_hat
        Innovation covariance: S = C @ P @ C^T + R
        Kalman gain: K = P @ C^T @ S^{-1}
        State update: x_hat = x_hat + K @ y
        Covariance update: P = (I - K @ C) @ P

        Args:
            z: Measurement vector, shape (n_measurements,), or None for
                missing measurements.

        Returns:
            Updated state estimate (copy), shape (n_states,).

        Raises:
            ValueError: If z has wrong shape.
        """
        if z is None:
            return self._x_hat.copy()

        z = np.asarray(z, dtype=np.float64)
        n_meas = self.n_measurements
        if z.shape != (n_meas,):
            msg = f"z must have shape ({n_meas},), got {z.shape}"
            raise ValueError(msg)

        C = self._C
        # Innovation
        y = z - C @ self._x_hat
        # Innovation covariance
        S = C @ self._P @ C.T + self._R
        # Kalman gain via solve for numerical stability: K = P @ C^T @ S^{-1}
        # Solve S^T @ K^T = C @ P^T => K^T = solve(S^T, C @ P^T)
        K = np.linalg.solve(S.T, C @ self._P.T).T
        # State update
        self._x_hat = self._x_hat + K @ y
        # Covariance update (Joseph form for numerical stability)
        IKC = np.eye(self.n_states) - K @ C
        self._P = IKC @ self._P @ IKC.T + K @ self._R @ K.T
        # Symmetrize
        self._P = (self._P + self._P.T) / 2.0
        return self._x_hat.copy()

    def step(
        self,
        u: NDArray[np.float64],
        d: NDArray[np.float64],
        z: NDArray[np.float64] | None = None,
    ) -> NDArray[np.float64]:
        """Run one full Kalman filter cycle: predict then update.

        Convenience method that calls predict() followed by update().

        Args:
            u: Control input vector, shape (n_inputs,).
            d: Disturbance vector, shape (n_disturbances,).
            z: Measurement vector, shape (n_measurements,), or None for
                missing measurements.

        Returns:
            Updated state estimate (copy), shape (n_states,).
        """
        self.predict(u, d)
        return self.update(z)
