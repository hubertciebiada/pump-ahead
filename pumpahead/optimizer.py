"""MPC optimizer for predictive heating/cooling control.

Constructs and solves a quadratic program (QP) using cvxpy for Model
Predictive Control.  The problem is DPP-compliant (Disciplined Parametrized
Programming) so it can be compiled once and re-solved with updated parameter
values for real-time performance.

Decision variables:
    x  -- state trajectory, shape (N+1, n)
    u  -- control inputs, shape (N, m)

Hard constraints (safety, Axioms 4 & 5):
    T_slab <= T_floor_max  (default 34 degC)
    T_slab >= T_dew + T_dew_margin  (default margin 2 K)

Soft constraints (comfort):
    T_air in [T_set - band, T_set + band]  (slack-penalised)

Cost function:
    J = w_comfort * ||T_air - T_set||^2
      + w_energy  * ||u||^2
      + w_smooth  * ||du||^2
      + w_slack   * sum(slack)

DPP note:
    The disturbance contribution ``E_d @ d[k] + b_d`` is pre-computed as a
    single numpy array and passed to cvxpy as a single Parameter ``w``.
    This avoids a Parameter-times-Parameter product (``E_d @ d``) which
    would break DPP compliance.

Units: temperatures in degC, valve positions in [0, 1], time step from model.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import cvxpy as cp
import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from pumpahead.model import RCModel


# ---------------------------------------------------------------------------
# MPCInfeasibleError
# ---------------------------------------------------------------------------


class MPCInfeasibleError(Exception):
    """Raised when the MPC optimisation problem is infeasible."""


# ---------------------------------------------------------------------------
# MPCConfig
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MPCConfig:
    """Configuration for the MPC optimizer.

    Attributes:
        horizon: Prediction horizon in time steps (must be >= 1).
        w_comfort: Comfort weight -- penalises (T_air - T_set)^2 (>= 0).
        w_energy: Energy weight -- penalises ||u||^2 (>= 0).
        w_smooth: Move-suppression weight -- penalises ||du||^2 (>= 0).
        T_floor_max: Hard floor temperature limit [degC] (Axiom 4).
        T_dew_margin: Dew-point safety margin [K] (Axiom 5).
        w_slack: Penalty weight for soft comfort slack variables (> 0).
        T_comfort_band: Soft comfort band half-width around setpoint [K] (> 0).
        solver_timeout_s: OSQP solver time limit in seconds (> 0).
    """

    horizon: int = 96
    w_comfort: float = 1.0
    w_energy: float = 0.1
    w_smooth: float = 0.01
    T_floor_max: float = 34.0
    T_dew_margin: float = 2.0
    w_slack: float = 1000.0
    T_comfort_band: float = 2.0
    solver_timeout_s: float = 0.1

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.horizon < 1:
            msg = f"horizon must be >= 1, got {self.horizon}"
            raise ValueError(msg)
        if self.w_comfort < 0:
            msg = f"w_comfort must be >= 0, got {self.w_comfort}"
            raise ValueError(msg)
        if self.w_energy < 0:
            msg = f"w_energy must be >= 0, got {self.w_energy}"
            raise ValueError(msg)
        if self.w_smooth < 0:
            msg = f"w_smooth must be >= 0, got {self.w_smooth}"
            raise ValueError(msg)
        if self.T_floor_max <= 0:
            msg = f"T_floor_max must be > 0, got {self.T_floor_max}"
            raise ValueError(msg)
        if self.T_dew_margin < 0:
            msg = f"T_dew_margin must be >= 0, got {self.T_dew_margin}"
            raise ValueError(msg)
        if self.w_slack <= 0:
            msg = f"w_slack must be > 0, got {self.w_slack}"
            raise ValueError(msg)
        if self.T_comfort_band <= 0:
            msg = f"T_comfort_band must be > 0, got {self.T_comfort_band}"
            raise ValueError(msg)
        if self.solver_timeout_s <= 0:
            msg = f"solver_timeout_s must be > 0, got {self.solver_timeout_s}"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# MPCResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MPCResult:
    """Result of an MPC solve.

    Attributes:
        x: State trajectory, shape (N+1, n_states).
        u: Control trajectory, shape (N, n_inputs).
        u_floor: Extracted UFH valve trajectory, shape (N,).
        u_conv: Extracted split trajectory, shape (N,).  All zeros for SISO.
        cost: Optimal objective value.
        status: Solver status string (e.g. ``"optimal"``).
        slack: Soft comfort constraint violations, shape (N+1,).
    """

    x: NDArray[np.float64]
    u: NDArray[np.float64]
    u_floor: NDArray[np.float64]
    u_conv: NDArray[np.float64]
    cost: float
    status: str
    slack: NDArray[np.float64]


# ---------------------------------------------------------------------------
# RecedingHorizonResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecedingHorizonResult:
    """Result of a single receding-horizon MPC step.

    Attributes:
        u_floor_0: First-step UFH valve command [0, 1].
        u_conv_0: First-step split command (0.0 for SISO rooms).
        solve_time_ms: Wall-clock solver time in milliseconds.
        used_fallback: True if PID fallback was used instead of MPC.
        solver_status: Solver status string, or ``"fallback"`` when PID used.
        mpc_result: Full MPC solver result (None when fallback active).
        x_predicted: Predicted state trajectory (None when fallback active).
    """

    u_floor_0: float
    u_conv_0: float
    solve_time_ms: float
    used_fallback: bool
    solver_status: str
    mpc_result: MPCResult | None
    x_predicted: NDArray[np.float64] | None


# ---------------------------------------------------------------------------
# MPCOptimizer
# ---------------------------------------------------------------------------


class MPCOptimizer:
    """QP-based MPC optimizer using cvxpy.

    The problem is built once in the constructor (DPP-compliant) and
    re-solved with updated parameter values via :meth:`solve`.

    The disturbance contribution ``E_d @ d[k] + b_d`` is pre-computed
    as a numpy array before each solve and injected as a single cvxpy
    Parameter ``w``, shape ``(N, n)``.  This avoids a
    Parameter-times-Parameter product which would violate DPP.

    Typical usage::

        model = RCModel(params, ModelOrder.THREE, dt=900.0)
        opt = MPCOptimizer(model, MPCConfig(horizon=96))
        result = opt.solve(x0, d, T_set=21.0)
    """

    def __init__(
        self,
        model: RCModel,
        config: MPCConfig | None = None,
    ) -> None:
        """Initialise the MPC optimizer.

        Args:
            model: Discretised RC thermal model.
            config: MPC configuration; defaults to ``MPCConfig()``.
        """
        from pumpahead.model import RCModel as _RCModel  # deferred for TYPE_CHECKING

        if not isinstance(model, _RCModel):
            msg = f"model must be an RCModel, got {type(model).__name__}"
            raise TypeError(msg)

        self._model = model
        self._config = config if config is not None else MPCConfig()
        self._has_split = model.params.has_split

        # Dimensions
        self._n = model.n_states
        self._m = model.n_inputs
        self._p = model.n_disturbances
        self._N = self._config.horizon

        # Cache discrete model matrices (numpy, not cvxpy Parameters)
        matrices = model.get_matrices()
        self._E_d_np: NDArray[np.float64] = matrices["E_d"]
        self._b_d_np: NDArray[np.float64] = matrices["b_d"]

        # Build cvxpy problem
        self._build()

    # -- Public properties ---------------------------------------------------

    @property
    def problem(self) -> cp.Problem:
        """The cvxpy Problem instance (read-only)."""
        return self._problem

    @property
    def is_dpp(self) -> bool:
        """Whether the problem is DPP-compliant."""
        return bool(self._problem.is_dpp())

    @property
    def config(self) -> MPCConfig:
        """The MPC configuration."""
        return self._config

    @property
    def has_split(self) -> bool:
        """Whether the model includes a split/AC input."""
        return self._has_split

    # -- Problem construction ------------------------------------------------

    def _build(self) -> None:
        """Construct the cvxpy QP problem with parametrised data.

        The dynamics constraint is:
            x[k+1] = A_d @ x[k] + B_d @ u[k] + w[k]

        where ``w[k] = E_d @ d[k] + b_d`` is pre-computed outside cvxpy
        to maintain DPP compliance (no Parameter * Parameter products).
        """
        n, m, N = self._n, self._m, self._N
        cfg = self._config

        # --- Parameters (updated each solve call) ---
        # A_d and B_d multiply Variables, so they can be Parameters (DPP-ok).
        self._A_d_param = cp.Parameter((n, n), name="A_d")
        self._B_d_param = cp.Parameter((n, m), name="B_d")

        # Pre-computed disturbance + bias: w[k] = E_d @ d[k] + b_d
        self._w_param = cp.Parameter((N, n), name="w")

        self._x0_param = cp.Parameter(n, name="x0")
        self._T_set_param = cp.Parameter(name="T_set")
        self._T_dew_param = cp.Parameter(N, name="T_dew")

        # Mode-dependent split bounds (parameterised for DPP)
        if self._has_split:
            self._u_conv_lb = cp.Parameter(name="u_conv_lb", value=0.0)
            self._u_conv_ub = cp.Parameter(name="u_conv_ub", value=1.0)

        # Initialise parameters from current model
        matrices = self._model.get_matrices()
        self._A_d_param.value = matrices["A_d"]
        self._B_d_param.value = matrices["B_d"]
        self._w_param.value = np.zeros((N, n))
        self._T_set_param.value = 21.0
        self._T_dew_param.value = np.full(N, -50.0)

        # --- Decision variables ---
        self._x = cp.Variable((N + 1, n), name="x")
        self._u = cp.Variable((N, m), name="u")
        self._slack = cp.Variable(N + 1, nonneg=True, name="slack")

        # --- Constraints ---
        constraints: list[cp.Constraint] = []

        # Initial condition
        constraints.append(self._x[0] == self._x0_param)

        # Dynamics: x[k+1] = A_d @ x[k] + B_d @ u[k] + w[k]
        for k in range(N):
            constraints.append(
                self._x[k + 1]
                == self._A_d_param @ self._x[k]
                + self._B_d_param @ self._u[k]
                + self._w_param[k]
            )

        # Hard floor temperature constraints (Axioms 4 & 5)
        for k in range(N + 1):
            # T_slab <= T_floor_max (index 1 is always T_slab)
            constraints.append(self._x[k, 1] <= cfg.T_floor_max)
            # T_slab >= T_dew + margin (condensation protection)
            dew_idx = min(k, N - 1)
            constraints.append(
                self._x[k, 1] >= self._T_dew_param[dew_idx] + cfg.T_dew_margin
            )

        # Input bounds
        if self._has_split:
            # MIMO: u = [Q_conv, Q_floor]
            # Column 0: split (Q_conv) -- mode-dependent bounds
            constraints.append(self._u[:, 0] >= self._u_conv_lb)
            constraints.append(self._u[:, 0] <= self._u_conv_ub)
            # Column 1: UFH valve in [0, 1]
            constraints.append(self._u[:, 1] >= 0)
            constraints.append(self._u[:, 1] <= 1)
        else:
            # SISO: u = [Q_floor]
            constraints.append(self._u[:, 0] >= 0)
            constraints.append(self._u[:, 0] <= 1)

        # Soft comfort constraints
        for k in range(N + 1):
            constraints.append(
                self._x[k, 0] >= self._T_set_param - cfg.T_comfort_band - self._slack[k]
            )
            constraints.append(
                self._x[k, 0] <= self._T_set_param + cfg.T_comfort_band + self._slack[k]
            )

        # --- Objective ---
        # Comfort: penalise (T_air - T_set)^2 for k=1..N (skip fixed x0)
        comfort_cost = (
            cfg.w_comfort
            * cp.sum_squares(  # type: ignore[attr-defined]
                self._x[1:, 0] - self._T_set_param
            )
        )
        # Energy: penalise ||u||^2
        energy_cost = cfg.w_energy * cp.sum_squares(self._u)  # type: ignore[attr-defined]
        # Move suppression: penalise ||du||^2
        smooth_cost = cfg.w_smooth * cp.sum_squares(self._u[1:] - self._u[:-1])  # type: ignore[attr-defined]
        # Slack penalty
        slack_cost = cfg.w_slack * cp.sum(self._slack)  # type: ignore[attr-defined]

        objective = cp.Minimize(comfort_cost + energy_cost + smooth_cost + slack_cost)

        self._problem = cp.Problem(objective, constraints)

    # -- Pre-computation helpers ---------------------------------------------

    def _compute_w(
        self,
        d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Pre-compute disturbance + bias term for each horizon step.

        Returns:
            w array of shape (N, n) where w[k] = E_d @ d[k] + b_d.
        """
        # d shape (N, p), E_d shape (n, p) -> (d @ E_d.T) shape (N, n)
        return d @ self._E_d_np.T + self._b_d_np

    # -- Solve ---------------------------------------------------------------

    def solve(
        self,
        x0: NDArray[np.float64],
        d: NDArray[np.float64],
        T_set: float,
        T_dew: NDArray[np.float64] | None = None,
        mode: Literal["heating", "cooling"] = "heating",
        solver: str | None = cp.OSQP,
        **solver_kwargs: object,
    ) -> MPCResult:
        """Update parameters and solve the MPC problem.

        Args:
            x0: Initial state, shape ``(n_states,)``.
            d: Disturbance matrix, shape ``(N, n_disturbances)``.
            T_set: Setpoint temperature [degC].
            T_dew: Dew-point temperatures per step, shape ``(N,)``.
                Defaults to ``-50`` (constraint effectively inactive).
            mode: ``"heating"`` or ``"cooling"`` -- determines split bounds.
            solver: cvxpy solver name; defaults to ``cp.OSQP``.
            **solver_kwargs: Additional keyword arguments for the solver.

        Returns:
            :class:`MPCResult` with solved trajectories.

        Raises:
            ValueError: If input dimensions are wrong or mode is invalid.
            MPCInfeasibleError: If the solver reports infeasibility.
        """
        N, n, p = self._N, self._n, self._p

        # --- Validate inputs ---
        if x0.shape != (n,):
            msg = f"x0 shape must be ({n},), got {x0.shape}"
            raise ValueError(msg)
        if d.shape != (N, p):
            msg = f"d shape must be ({N}, {p}), got {d.shape}"
            raise ValueError(msg)
        if mode not in ("heating", "cooling"):
            msg = f"mode must be 'heating' or 'cooling', got {mode!r}"
            raise ValueError(msg)

        # --- Update parameters ---
        self._x0_param.value = x0
        self._w_param.value = self._compute_w(d)
        self._T_set_param.value = float(T_set)

        if T_dew is not None:
            if T_dew.shape != (N,):
                msg = f"T_dew shape must be ({N},), got {T_dew.shape}"
                raise ValueError(msg)
            self._T_dew_param.value = T_dew
        else:
            self._T_dew_param.value = np.full(N, -50.0)

        # Mode-dependent split bounds
        if self._has_split:
            if mode == "heating":
                self._u_conv_lb.value = 0.0
                self._u_conv_ub.value = 1.0
            else:  # cooling
                self._u_conv_lb.value = -1.0
                self._u_conv_ub.value = 0.0

        # --- Solve ---
        self._problem.solve(solver=solver, warm_start=True, **solver_kwargs)  # type: ignore[no-untyped-call]

        # Check status
        status = str(self._problem.status)
        if self._problem.status in (cp.INFEASIBLE, cp.INFEASIBLE_INACCURATE):
            msg = f"MPC problem infeasible (status: {status})"
            raise MPCInfeasibleError(msg)

        # --- Extract results ---
        x_val = np.array(self._x.value, dtype=np.float64)
        u_val = np.array(self._u.value, dtype=np.float64)
        slack_val = np.array(self._slack.value, dtype=np.float64)

        if self._has_split:
            # MIMO: u = [Q_conv, Q_floor]
            u_conv = u_val[:, 0].copy()
            u_floor = u_val[:, 1].copy()
        else:
            # SISO: u = [Q_floor]
            u_floor = u_val[:, 0].copy()
            u_conv = np.zeros(N, dtype=np.float64)

        return MPCResult(
            x=x_val,
            u=u_val,
            u_floor=u_floor,
            u_conv=u_conv,
            cost=float(self._problem.value),
            status=status,
            slack=slack_val,
        )

    # -- Model update --------------------------------------------------------

    def update_model(self, model: RCModel) -> None:
        """Update the internal model matrices without rebuilding the problem.

        The new model must have the same dimensions (n_states, n_inputs,
        n_disturbances) as the original.

        Args:
            model: New RC model with updated parameters.

        Raises:
            ValueError: If model dimensions differ from the original.
        """
        if model.n_states != self._n:
            msg = f"New model has {model.n_states} states, expected {self._n}"
            raise ValueError(msg)
        if model.n_inputs != self._m:
            msg = f"New model has {model.n_inputs} inputs, expected {self._m}"
            raise ValueError(msg)
        if model.n_disturbances != self._p:
            msg = (
                f"New model has {model.n_disturbances} disturbances, expected {self._p}"
            )
            raise ValueError(msg)

        matrices = model.get_matrices()
        self._A_d_param.value = matrices["A_d"]
        self._B_d_param.value = matrices["B_d"]
        self._E_d_np = matrices["E_d"]
        self._b_d_np = matrices["b_d"]
        self._model = model


# ---------------------------------------------------------------------------
# _PIDFallback — minimal proportional-integral fallback controller
# ---------------------------------------------------------------------------

_logger = logging.getLogger(__name__)


class _PIDFallback:
    """Minimal PI controller used as MPC fallback.

    Produces a UFH valve command in [0, 1] from the temperature error
    ``T_set - T_air``.  The integral term is clamped to avoid windup.

    This is intentionally simple — a full PIDController will be implemented
    separately.  The fallback exists solely to maintain thermal control when
    the MPC solver fails or times out.
    """

    _INTEGRAL_CLAMP = 100.0

    def __init__(
        self,
        kp: float = 5.0,
        ki: float = 0.01,
        dt_seconds: float = 900.0,
    ) -> None:
        self._kp = kp
        self._ki = ki
        self._dt = dt_seconds
        self._integral: float = 0.0

    def compute(self, T_air: float, T_set: float) -> float:
        """Return valve command in [0, 1] for the given error."""
        error = T_set - T_air
        self._integral += error * self._dt
        self._integral = max(
            -self._INTEGRAL_CLAMP,
            min(self._INTEGRAL_CLAMP, self._integral),
        )
        output = self._kp * error + self._ki * self._integral
        return max(0.0, min(1.0, output))

    def reset(self) -> None:
        """Reset accumulated integral."""
        self._integral = 0.0


# ---------------------------------------------------------------------------
# MPCController — receding-horizon wrapper with warm start & PID fallback
# ---------------------------------------------------------------------------


class MPCController:
    """Receding-horizon MPC controller with warm start and PID fallback.

    Wraps :class:`MPCOptimizer` to provide a ``step()`` method suitable for
    real-time control loops.  Each call:

    1. Optionally warm-starts the solver from the previous solution.
    2. Solves the QP with the configured OSQP timeout.
    3. On success, extracts the first-step control action.
    4. On failure (infeasibility, timeout, exception), falls back to a
       minimal PI controller.

    Typical usage::

        ctrl = MPCController(model)
        result = ctrl.step(x0, d, T_set=21.0)
        valve = result.u_floor_0
    """

    def __init__(
        self,
        model: RCModel,
        config: MPCConfig | None = None,
        fallback_kp: float = 5.0,
        fallback_ki: float = 0.01,
    ) -> None:
        """Initialise the receding-horizon controller.

        Args:
            model: Discretised RC thermal model.
            config: MPC configuration; defaults to ``MPCConfig()``.
            fallback_kp: Proportional gain for the PID fallback.
            fallback_ki: Integral gain for the PID fallback.
        """
        self._config = config if config is not None else MPCConfig()
        self._optimizer = MPCOptimizer(model, self._config)
        self._fallback = _PIDFallback(
            kp=fallback_kp,
            ki=fallback_ki,
            dt_seconds=model.dt,
        )
        self._prev_u: NDArray[np.float64] | None = None
        self._prev_x: NDArray[np.float64] | None = None

    # -- Public properties ---------------------------------------------------

    @property
    def config(self) -> MPCConfig:
        """The MPC configuration."""
        return self._config

    @property
    def has_split(self) -> bool:
        """Whether the underlying model includes a split/AC input."""
        return self._optimizer.has_split

    @property
    def optimizer(self) -> MPCOptimizer:
        """The underlying MPCOptimizer (read-only)."""
        return self._optimizer

    # -- Warm start ----------------------------------------------------------

    def _warm_start_from_previous(self) -> None:
        """Seed solver variables from the previous solution.

        Shifts previous u and x trajectories left by one step (discards the
        first element, duplicates the last) and assigns them as initial
        values for the cvxpy variables.
        """
        if self._prev_u is None or self._prev_x is None:
            return

        # Shift u: drop u[0], repeat u[-1]
        u_shifted = np.roll(self._prev_u, -1, axis=0)
        u_shifted[-1] = self._prev_u[-1]

        # Shift x: drop x[0], repeat x[-1]
        x_shifted = np.roll(self._prev_x, -1, axis=0)
        x_shifted[-1] = self._prev_x[-1]

        # Assign to cvxpy variables
        self._optimizer._x.value = x_shifted  # noqa: SLF001
        self._optimizer._u.value = u_shifted  # noqa: SLF001

    # -- Step ----------------------------------------------------------------

    def step(
        self,
        x0: NDArray[np.float64],
        d: NDArray[np.float64],
        T_set: float,
        T_dew: NDArray[np.float64] | None = None,
        mode: Literal["heating", "cooling"] = "heating",
    ) -> RecedingHorizonResult:
        """Execute one receding-horizon step.

        Solves the full MPC horizon, extracts the first control action,
        and stores the solution for warm-starting the next call.

        On solver failure the method returns a PID-fallback result instead
        of raising an exception.

        Args:
            x0: Current state, shape ``(n_states,)``.
            d: Disturbance forecast, shape ``(N, n_disturbances)``.
            T_set: Setpoint temperature [degC].
            T_dew: Dew-point temperatures per step, shape ``(N,)``.
            mode: ``"heating"`` or ``"cooling"``.

        Returns:
            :class:`RecedingHorizonResult` with the first-step action and
            solver metadata.
        """
        # Warm start from previous solution
        self._warm_start_from_previous()

        try:
            t0 = time.perf_counter()
            result = self._optimizer.solve(
                x0=x0,
                d=d,
                T_set=T_set,
                T_dew=T_dew,
                mode=mode,
                solver=cp.OSQP,
                time_limit=self._config.solver_timeout_s,
            )
            solve_ms = (time.perf_counter() - t0) * 1000.0
        except (MPCInfeasibleError, Exception) as exc:
            _logger.warning("MPC solver failed (%s), using PID fallback", exc)
            return self._fallback_result(x0, T_set)

        # Treat "optimal_inaccurate" as success (feasible but not converged)
        status = result.status
        if "infeasible" in status:
            _logger.warning(
                "MPC solver returned infeasible status '%s', using PID fallback",
                status,
            )
            return self._fallback_result(x0, T_set)

        # Store solution for warm start
        self._prev_u = result.u.copy()
        self._prev_x = result.x.copy()

        # Extract first-step action
        u_floor_0 = float(result.u_floor[0])
        u_conv_0 = float(result.u_conv[0])

        return RecedingHorizonResult(
            u_floor_0=u_floor_0,
            u_conv_0=u_conv_0,
            solve_time_ms=solve_ms,
            used_fallback=False,
            solver_status=status,
            mpc_result=result,
            x_predicted=result.x.copy(),
        )

    # -- Fallback ------------------------------------------------------------

    def _fallback_result(
        self,
        x0: NDArray[np.float64],
        T_set: float,
    ) -> RecedingHorizonResult:
        """Build a RecedingHorizonResult from PID fallback."""
        T_air = float(x0[0])
        u_floor_0 = self._fallback.compute(T_air, T_set)
        return RecedingHorizonResult(
            u_floor_0=u_floor_0,
            u_conv_0=0.0,
            solve_time_ms=0.0,
            used_fallback=True,
            solver_status="fallback",
            mpc_result=None,
            x_predicted=None,
        )

    # -- Reset / model update ------------------------------------------------

    def reset(self) -> None:
        """Clear warm-start state and reset the PID fallback integral."""
        self._prev_u = None
        self._prev_x = None
        self._fallback.reset()

    def update_model(self, model: RCModel) -> None:
        """Update the underlying model and clear warm-start state.

        Args:
            model: New RC model with the same dimensions.
        """
        self._optimizer.update_model(model)
        self._prev_u = None
        self._prev_x = None
