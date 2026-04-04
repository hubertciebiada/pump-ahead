"""RC thermal model for building simulation.

Implements 2R2C and 3R3C state-space models with ZOH discretization
for use in MPC-based predictive heating/cooling control.

State-space form:
    dx/dt = A_c @ x + B_c @ u + E_c @ d + b_c  (continuous)
    x[k+1] = A_d @ x[k] + B_d @ u[k] + E_d @ d[k] + b_d  (discrete)

3R3C states: x = [T_air, T_slab, T_wall]
2R2C states: x = [T_air, T_slab]

Units: R in K/W, C in J/K, T in degC, Q in W, time in seconds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import scipy.linalg
from numpy.typing import NDArray


class ModelOrder(Enum):
    """RC model order (number of thermal nodes)."""

    TWO = 2
    THREE = 3


@dataclass(frozen=True)
class RCParams:
    """Thermal parameters for an RC model.

    All resistances in K/W, all capacitances in J/K.
    f_conv + f_rad <= 1.0 (remaining fraction is reflected).

    Attributes:
        C_air: Thermal capacitance of the air node [J/K].
        C_slab: Thermal capacitance of the slab node [J/K].
        R_sf: Thermal resistance slab-to-air (floor surface) [K/W].
        f_conv: Fraction of solar gain absorbed convectively by air [-].
        f_rad: Fraction of solar gain absorbed radiatively by walls [-].
        T_ground: Ground temperature beneath slab [degC].
        has_split: Whether the room has a split/AC unit (MIMO if True).

        # 3R3C-only parameters
        C_wall: Thermal capacitance of the wall node [J/K].
        R_wi: Thermal resistance wall-interior (wall-to-air) [K/W].
        R_wo: Thermal resistance wall-outdoor [K/W].
        R_ve: Thermal resistance for ventilation/infiltration [K/W].
        R_ins: Thermal resistance of insulation beneath slab [K/W].

        # 2R2C-only parameters
        R_env: Combined envelope resistance (air-to-outdoor) [K/W].
    """

    C_air: float
    C_slab: float
    R_sf: float
    f_conv: float = 0.6
    f_rad: float = 0.4
    T_ground: float = 10.0
    has_split: bool = False

    # 3R3C-only
    C_wall: float | None = None
    R_wi: float | None = None
    R_wo: float | None = None
    R_ve: float | None = None
    R_ins: float | None = None

    # 2R2C-only
    R_env: float | None = None

    def __post_init__(self) -> None:
        """Validate parameter constraints."""
        # Validate positive resistances
        for name in ("R_sf",):
            value = getattr(self, name)
            if value <= 0:
                msg = f"{name} must be positive, got {value}"
                raise ValueError(msg)

        # Validate positive capacitances
        for name in ("C_air", "C_slab"):
            value = getattr(self, name)
            if value <= 0:
                msg = f"{name} must be positive, got {value}"
                raise ValueError(msg)

        # Validate solar fractions
        if self.f_conv < 0 or self.f_rad < 0:
            msg = (
                f"Solar fractions must be non-negative, "
                f"got f_conv={self.f_conv}, f_rad={self.f_rad}"
            )
            raise ValueError(msg)
        if self.f_conv + self.f_rad > 1.0:
            msg = (
                f"f_conv + f_rad must be <= 1.0, "
                f"got {self.f_conv} + {self.f_rad} = {self.f_conv + self.f_rad}"
            )
            raise ValueError(msg)

    def validate_for_order(self, order: ModelOrder) -> None:
        """Validate that required parameters are present for a given model order.

        Args:
            order: The model order to validate against.

        Raises:
            ValueError: If required parameters for the order are missing or invalid.
        """
        if order == ModelOrder.THREE:
            required = {"C_wall": self.C_wall, "R_wi": self.R_wi,
                        "R_wo": self.R_wo, "R_ve": self.R_ve, "R_ins": self.R_ins}
            for name, value in required.items():
                if value is None:
                    msg = f"{name} is required for 3R3C model"
                    raise ValueError(msg)
                if name.startswith("R") and value <= 0:
                    msg = f"{name} must be positive, got {value}"
                    raise ValueError(msg)
                if name.startswith("C") and value <= 0:
                    msg = f"{name} must be positive, got {value}"
                    raise ValueError(msg)
        elif order == ModelOrder.TWO:
            if self.R_env is None:
                msg = "R_env is required for 2R2C model"
                raise ValueError(msg)
            if self.R_env <= 0:
                msg = f"R_env must be positive, got {self.R_env}"
                raise ValueError(msg)


class RCModel:
    """RC thermal model supporting 2R2C and 3R3C configurations.

    The model is constructed from physical parameters (RCParams) and
    supports both SISO (UFH-only) and MIMO (UFH+split) input configurations.
    Discretization uses the augmented matrix exponential (ZOH) method
    which is numerically stable for stiff systems.

    Typical usage:
        params = RCParams(C_air=60_000, C_slab=3_250_000, ...)
        model = RCModel(params, ModelOrder.THREE, dt=60.0)
        x_next = model.step(x, u, d)
        trajectory = model.predict(x0, u_sequence, d_sequence)
    """

    def __init__(
        self,
        params: RCParams,
        order: ModelOrder,
        dt: float = 60.0,
    ) -> None:
        """Initialize the RC model.

        Args:
            params: Thermal parameters for the model.
            order: Model order (TWO or THREE).
            dt: Discretization time step in seconds.

        Raises:
            ValueError: If parameters are invalid for the given order
                or dt is non-positive.
        """
        if dt <= 0:
            msg = f"dt must be positive, got {dt}"
            raise ValueError(msg)

        params.validate_for_order(order)

        self._params = params
        self._order = order
        self._dt = dt

        # Build continuous-time matrices
        self._A_c: NDArray[np.float64]
        self._B_c: NDArray[np.float64]
        self._E_c: NDArray[np.float64]
        self._b_c: NDArray[np.float64]
        self._build_continuous_matrices()

        # Discretize
        self._A_d: NDArray[np.float64]
        self._B_d: NDArray[np.float64]
        self._E_d: NDArray[np.float64]
        self._b_d: NDArray[np.float64]
        self._discretize()

    @property
    def params(self) -> RCParams:
        """Return the model parameters."""
        return self._params

    @property
    def order(self) -> ModelOrder:
        """Return the model order."""
        return self._order

    @property
    def dt(self) -> float:
        """Return the discretization time step in seconds."""
        return self._dt

    @property
    def n_states(self) -> int:
        """Number of state variables."""
        return self._order.value

    @property
    def n_inputs(self) -> int:
        """Number of control inputs (1 for SISO, 2 for MIMO)."""
        return 2 if self._params.has_split else 1

    @property
    def n_disturbances(self) -> int:
        """Number of disturbance inputs.

        3R3C: 3 (T_out, Q_sol, Q_int)
        2R2C: 2 (T_out, Q_sol)
        """
        if self._order == ModelOrder.THREE:
            return 3
        return 2

    @property
    def state_names(self) -> list[str]:
        """Names of the state variables."""
        if self._order == ModelOrder.THREE:
            return ["T_air", "T_slab", "T_wall"]
        return ["T_air", "T_slab"]

    @property
    def C_obs(self) -> NDArray[np.float64]:
        """Observation matrix extracting T_air from state vector."""
        c = np.zeros((1, self.n_states))
        c[0, 0] = 1.0
        return c

    def _build_continuous_matrices(self) -> None:
        """Construct continuous-time A_c, B_c, E_c, b_c matrices."""
        if self._order == ModelOrder.THREE:
            self._build_3r3c_matrices()
        else:
            self._build_2r2c_matrices()

    def _build_3r3c_matrices(self) -> None:
        """Build continuous-time matrices for 3R3C model.

        State: x = [T_air, T_slab, T_wall]
        Input (SISO): u = [Q_floor]
        Input (MIMO): u = [Q_conv, Q_floor]
        Disturbance: d = [T_out, Q_sol, Q_int]
        """
        p = self._params
        # Type narrowing: these are validated non-None by validate_for_order
        assert p.C_wall is not None
        assert p.R_wi is not None
        assert p.R_wo is not None
        assert p.R_ve is not None
        assert p.R_ins is not None

        # A matrix (3x3)
        A_c = np.zeros((3, 3))
        A_c[0, 0] = -(1 / (p.R_sf * p.C_air)
                       + 1 / (p.R_wi * p.C_air)
                       + 1 / (p.R_ve * p.C_air))
        A_c[0, 1] = 1 / (p.R_sf * p.C_air)
        A_c[0, 2] = 1 / (p.R_wi * p.C_air)
        A_c[1, 0] = 1 / (p.R_sf * p.C_slab)
        A_c[1, 1] = -(1 / (p.R_sf * p.C_slab) + 1 / (p.R_ins * p.C_slab))
        A_c[1, 2] = 0.0
        A_c[2, 0] = 1 / (p.R_wi * p.C_wall)
        A_c[2, 1] = 0.0
        A_c[2, 2] = -(1 / (p.R_wi * p.C_wall) + 1 / (p.R_wo * p.C_wall))
        self._A_c = A_c

        # B matrix
        if self._params.has_split:
            # MIMO: u = [Q_conv, Q_floor]
            B_c = np.zeros((3, 2))
            B_c[0, 0] = 1 / p.C_air   # Q_conv -> T_air
            B_c[1, 1] = 1 / p.C_slab  # Q_floor -> T_slab
        else:
            # SISO: u = [Q_floor]
            B_c = np.zeros((3, 1))
            B_c[1, 0] = 1 / p.C_slab  # Q_floor -> T_slab
        self._B_c = B_c

        # E matrix (3x3): d = [T_out, Q_sol, Q_int]
        E_c = np.zeros((3, 3))
        E_c[0, 0] = 1 / (p.R_ve * p.C_air)     # T_out -> T_air
        E_c[0, 1] = p.f_conv / p.C_air          # Q_sol (convective) -> T_air
        E_c[0, 2] = 1 / p.C_air                 # Q_int -> T_air
        E_c[2, 0] = 1 / (p.R_wo * p.C_wall)     # T_out -> T_wall
        E_c[2, 1] = p.f_rad / p.C_wall           # Q_sol (radiative) -> T_wall
        self._E_c = E_c

        # b vector (constant bias from T_ground)
        b_c = np.zeros(3)
        b_c[1] = p.T_ground / (p.R_ins * p.C_slab)
        self._b_c = b_c

    def _build_2r2c_matrices(self) -> None:
        """Build continuous-time matrices for 2R2C model.

        State: x = [T_air, T_slab]
        Input (SISO): u = [Q_floor]
        Input (MIMO): u = [Q_conv, Q_floor]
        Disturbance: d = [T_out, Q_sol]
        """
        p = self._params
        assert p.R_env is not None

        # A matrix (2x2)
        A_c = np.zeros((2, 2))
        A_c[0, 0] = -(1 / (p.R_sf * p.C_air) + 1 / (p.R_env * p.C_air))
        A_c[0, 1] = 1 / (p.R_sf * p.C_air)
        A_c[1, 0] = 1 / (p.R_sf * p.C_slab)
        A_c[1, 1] = -1 / (p.R_sf * p.C_slab)
        self._A_c = A_c

        # B matrix
        if self._params.has_split:
            # MIMO: u = [Q_conv, Q_floor]
            B_c = np.zeros((2, 2))
            B_c[0, 0] = 1 / p.C_air   # Q_conv -> T_air
            B_c[1, 1] = 1 / p.C_slab  # Q_floor -> T_slab
        else:
            # SISO: u = [Q_floor]
            B_c = np.zeros((2, 1))
            B_c[1, 0] = 1 / p.C_slab  # Q_floor -> T_slab
        self._B_c = B_c

        # E matrix (2x2): d = [T_out, Q_sol]
        E_c = np.zeros((2, 2))
        E_c[0, 0] = 1 / (p.R_env * p.C_air)    # T_out -> T_air
        E_c[0, 1] = p.f_conv / p.C_air           # Q_sol (convective) -> T_air
        self._E_c = E_c

        # b vector (no T_ground in 2R2C)
        self._b_c = np.zeros(2)

    def _discretize(self) -> None:
        """Discretize using the augmented matrix exponential (ZOH) method.

        Constructs the augmented matrix:
            M = [ A_c  B_c  E_c  b_c ]
                [ 0    0    0    0    ]
                [ 0    0    0    0    ]
                [ 0    0    0    0    ]

        Then computes exp(M * dt) and extracts A_d, B_d, E_d, b_d.
        This is numerically stable even for stiff systems (large C_slab/C_air ratio).
        """
        n = self.n_states
        m = self.n_inputs
        p = self.n_disturbances
        total = n + m + p + 1

        M = np.zeros((total, total))
        M[:n, :n] = self._A_c
        M[:n, n:n + m] = self._B_c
        M[:n, n + m:n + m + p] = self._E_c
        M[:n, n + m + p:] = self._b_c.reshape(-1, 1)

        Ms = scipy.linalg.expm(M * self._dt)

        self._A_d = Ms[:n, :n].copy()
        self._B_d = Ms[:n, n:n + m].copy()
        self._E_d = Ms[:n, n + m:n + m + p].copy()
        self._b_d = Ms[:n, n + m + p:].flatten().copy()

    def set_dt(self, dt: float) -> None:
        """Change the discretization time step and re-discretize.

        Args:
            dt: New time step in seconds.

        Raises:
            ValueError: If dt is non-positive.
        """
        if dt <= 0:
            msg = f"dt must be positive, got {dt}"
            raise ValueError(msg)
        self._dt = dt
        self._discretize()

    def step(
        self,
        x: NDArray[np.float64],
        u: NDArray[np.float64],
        d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Propagate state by one time step.

        Pure function: does not mutate x.

        Args:
            x: Current state vector, shape (n_states,).
            u: Control input vector, shape (n_inputs,).
            d: Disturbance vector, shape (n_disturbances,).

        Returns:
            New state vector, shape (n_states,).
        """
        return (
            self._A_d @ x
            + self._B_d @ u
            + self._E_d @ d
            + self._b_d
        )

    def predict(
        self,
        x0: NDArray[np.float64],
        u_sequence: NDArray[np.float64],
        d_sequence: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Predict state trajectory over N steps.

        Args:
            x0: Initial state vector, shape (n_states,).
            u_sequence: Control input sequence, shape (N, n_inputs).
            d_sequence: Disturbance sequence, shape (N, n_disturbances).

        Returns:
            State trajectory, shape (N+1, n_states). First row is x0.

        Raises:
            ValueError: If sequence lengths don't match.
        """
        n_steps = u_sequence.shape[0]
        if d_sequence.shape[0] != n_steps:
            msg = (
                f"u_sequence and d_sequence must have the same length, "
                f"got {u_sequence.shape[0]} and {d_sequence.shape[0]}"
            )
            raise ValueError(msg)

        trajectory = np.zeros((n_steps + 1, self.n_states))
        trajectory[0] = x0
        for k in range(n_steps):
            trajectory[k + 1] = self.step(
                trajectory[k], u_sequence[k], d_sequence[k]
            )
        return trajectory

    def steady_state(
        self,
        u: NDArray[np.float64],
        d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Compute the steady-state temperature vector.

        Solves 0 = A_c @ x_ss + B_c @ u + E_c @ d + b_c
        => x_ss = -A_c^{-1} @ (B_c @ u + E_c @ d + b_c)

        Args:
            u: Constant control input vector, shape (n_inputs,).
            d: Constant disturbance vector, shape (n_disturbances,).

        Returns:
            Steady-state vector, shape (n_states,).

        Raises:
            ValueError: If A_c is singular (no unique steady state).
        """
        rhs = self._B_c @ u + self._E_c @ d + self._b_c
        try:
            x_ss = np.asarray(
                np.linalg.solve(self._A_c, -rhs), dtype=np.float64
            )
        except np.linalg.LinAlgError as e:
            msg = "A_c is singular — no unique steady state exists"
            raise ValueError(msg) from e
        return x_ss

    def reset(self) -> NDArray[np.float64]:
        """Return a default initial state (20 degC for all nodes).

        Returns:
            Default state vector, shape (n_states,).
        """
        return np.full(self.n_states, 20.0)

    def get_matrices(self) -> dict[str, Any]:
        """Return all model matrices as a dictionary.

        Returns:
            Dictionary with keys: A_c, B_c, E_c, b_c, A_d, B_d, E_d, b_d.
        """
        return {
            "A_c": self._A_c.copy(),
            "B_c": self._B_c.copy(),
            "E_c": self._E_c.copy(),
            "b_c": self._b_c.copy(),
            "A_d": self._A_d.copy(),
            "B_d": self._B_d.copy(),
            "E_d": self._E_d.copy(),
            "b_d": self._b_d.copy(),
        }
