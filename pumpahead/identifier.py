"""RC thermal model parameter identification using L-BFGS-B optimization.

Identifies 2R2C (4 parameters) or 3R3C (7 parameters) RC thermal model
parameters from measurement data using scipy.optimize.minimize with
L-BFGS-B and multi-start for global search.

The identifier generates forward trajectories using RCModel.predict()
for candidate parameter vectors and minimizes the mean squared error (MSE)
between predicted T_air (state index 0) and observed T_room measurements.
This is the standard grey-box identification approach for building thermal
models.

Multi-start uses log-uniform sampling to cover the wide dynamic range of
RC parameters (C_air ~ 60k J/K vs C_slab ~ 3.25M J/K).

Units: R in K/W, C in J/K, T in degC, Q in W, time in seconds.

Typical usage:
    identifier = RCIdentifier(ModelOrder.TWO, dt=60.0, n_starts=10)
    result = identifier.identify(u_sequence, d_sequence, T_room_measured)
    print(result.params)   # RCParams with identified values
    print(result.cost)     # Final MSE [degC^2]
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import OptimizeResult, minimize

from pumpahead.model import ModelOrder, RCModel, RCParams

# ---------------------------------------------------------------------------
# Default parameter bounds (physically sensible ranges)
# ---------------------------------------------------------------------------

DEFAULT_BOUNDS_2R2C: dict[str, tuple[float, float]] = {
    "R_sf": (0.001, 0.1),
    "R_env": (0.005, 0.2),
    "C_air": (10_000.0, 500_000.0),
    "C_slab": (500_000.0, 20_000_000.0),
}

DEFAULT_BOUNDS_3R3C: dict[str, tuple[float, float]] = {
    "R_sf": (0.001, 0.1),
    "R_wi": (0.005, 0.2),
    "R_wo": (0.005, 0.2),
    "R_ve": (0.005, 0.2),
    "C_air": (10_000.0, 500_000.0),
    "C_slab": (500_000.0, 20_000_000.0),
    "C_wall": (200_000.0, 10_000_000.0),
}

# Parameter vector ordering for each model order
_PARAM_NAMES_2R2C: list[str] = ["R_sf", "R_env", "C_air", "C_slab"]
_PARAM_NAMES_3R3C: list[str] = [
    "R_sf",
    "R_wi",
    "R_wo",
    "R_ve",
    "C_air",
    "C_slab",
    "C_wall",
]


# ---------------------------------------------------------------------------
# IdentificationResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentificationResult:
    """Result of RC parameter identification.

    Attributes:
        params: Identified RC model parameters.
        cost: Final MSE value [degC^2] (best across all starts).
        n_starts: Number of multi-start runs performed.
        converged: Whether the best run's optimizer reported success.
        all_costs: MSE from each start (sorted ascending, for diagnostics).
    """

    params: RCParams
    cost: float
    n_starts: int
    converged: bool
    all_costs: tuple[float, ...]

    def __post_init__(self) -> None:
        """Validate result fields."""
        if self.cost < 0:
            msg = f"cost must be non-negative, got {self.cost}"
            raise ValueError(msg)
        if self.n_starts < 1:
            msg = f"n_starts must be >= 1, got {self.n_starts}"
            raise ValueError(msg)
        if len(self.all_costs) != self.n_starts:
            msg = (
                f"all_costs length ({len(self.all_costs)}) "
                f"must equal n_starts ({self.n_starts})"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# RCIdentifier
# ---------------------------------------------------------------------------


class RCIdentifier:
    """RC thermal model parameter identifier using L-BFGS-B optimization.

    Identifies 2R2C (4 params: R_sf, R_env, C_air, C_slab) or 3R3C
    (7 params: R_sf, R_wi, R_wo, R_ve, C_air, C_slab, C_wall) from
    measurement data. Fixed parameters (f_conv, f_rad, T_ground, has_split,
    and R_ins for 3R3C) are set at construction time.

    The identifier uses multi-start with log-uniform sampling to handle
    local minima and the wide dynamic range of RC parameters.

    Typical usage:
        identifier = RCIdentifier(ModelOrder.TWO, dt=60.0, n_starts=10)
        result = identifier.identify(u_sequence, d_sequence, T_room_measured)
    """

    def __init__(
        self,
        order: ModelOrder,
        dt: float = 60.0,
        *,
        n_starts: int = 10,
        seed: int = 42,
        f_conv: float = 0.6,
        f_rad: float = 0.4,
        T_ground: float = 10.0,
        has_split: bool = False,
        R_ins: float | None = None,
        bounds: dict[str, tuple[float, float]] | None = None,
        maxiter: int = 500,
        burnin_steps: int = 0,
    ) -> None:
        """Initialize the RC parameter identifier.

        Args:
            order: Model order (TWO for 2R2C, THREE for 3R3C).
            dt: Discretization time step in seconds.
            n_starts: Number of multi-start optimization runs.
            seed: Random seed for reproducible initial point sampling.
            f_conv: Fraction of solar gain absorbed convectively [-].
            f_rad: Fraction of solar gain absorbed radiatively [-].
            T_ground: Ground temperature beneath slab [degC].
            has_split: Whether the room has a split/AC unit.
            R_ins: Insulation resistance [K/W] (required for 3R3C,
                fixed during identification).
            bounds: Optional override for parameter bounds. Keys are
                parameter names, values are (lower, upper) tuples.
                Merged with defaults (user values take priority).
            maxiter: Maximum iterations per L-BFGS-B run.
            burnin_steps: Number of initial steps to exclude from the
                MSE computation. This compensates for unknown initial
                state (especially T_slab), allowing the simulated
                trajectory to converge before fitting begins. Typical
                value: 360 (6 hours at dt=60s). Default 0 means no
                burn-in.

        Raises:
            ValueError: If dt <= 0, n_starts < 1, burnin_steps < 0,
                or R_ins is missing for 3R3C identification.
        """
        if dt <= 0:
            msg = f"dt must be positive, got {dt}"
            raise ValueError(msg)
        if n_starts < 1:
            msg = f"n_starts must be >= 1, got {n_starts}"
            raise ValueError(msg)
        if burnin_steps < 0:
            msg = f"burnin_steps must be >= 0, got {burnin_steps}"
            raise ValueError(msg)

        if order == ModelOrder.THREE:
            if R_ins is None:
                msg = "R_ins is required for 3R3C identification"
                raise ValueError(msg)
            if R_ins <= 0:
                msg = f"R_ins must be positive, got {R_ins}"
                raise ValueError(msg)

        self._order = order
        self._dt = dt
        self._n_starts = n_starts
        self._f_conv = f_conv
        self._f_rad = f_rad
        self._T_ground = T_ground
        self._has_split = has_split
        self._R_ins = R_ins
        self._maxiter = maxiter
        self._burnin_steps = burnin_steps

        # Set parameter names for this model order
        if order == ModelOrder.TWO:
            self._param_names = list(_PARAM_NAMES_2R2C)
        else:
            self._param_names = list(_PARAM_NAMES_3R3C)

        # Build bounds: start from defaults, merge user overrides
        if order == ModelOrder.TWO:
            merged_bounds = dict(DEFAULT_BOUNDS_2R2C)
        else:
            merged_bounds = dict(DEFAULT_BOUNDS_3R3C)
        if bounds is not None:
            merged_bounds.update(bounds)
        self._bounds_dict = merged_bounds
        self._bounds_list: list[tuple[float, float]] = [
            merged_bounds[name] for name in self._param_names
        ]

        # Seeded RNG for reproducible multi-start sampling
        self._rng = np.random.default_rng(seed)

    @property
    def n_params(self) -> int:
        """Number of identifiable parameters."""
        return len(self._param_names)

    @property
    def param_names(self) -> list[str]:
        """Ordered list of identifiable parameter names (copy)."""
        return list(self._param_names)

    def _pack_params(self, params: RCParams) -> NDArray[np.float64]:
        """Extract the identifiable parameters from RCParams into a vector.

        Args:
            params: RC model parameters.

        Returns:
            1D array of parameter values in ``_param_names`` order.
        """
        param_dict: dict[str, float] = {}
        for name in self._param_names:
            value = getattr(params, name)
            if value is None:
                msg = f"Parameter {name} is None in the given RCParams"
                raise ValueError(msg)
            param_dict[name] = float(value)
        return np.array(
            [param_dict[name] for name in self._param_names], dtype=np.float64
        )

    def _unpack_params(self, theta: NDArray[np.float64]) -> RCParams:
        """Reconstruct RCParams from a flat parameter vector.

        Fixed parameters (f_conv, f_rad, T_ground, has_split, R_ins) are
        taken from the identifier's construction-time settings.

        Args:
            theta: 1D array of parameter values in ``_param_names`` order.

        Returns:
            RCParams with identified + fixed parameter values.
        """
        kwargs: dict[str, float | bool | None] = dict(
            zip(self._param_names, theta.tolist(), strict=True)
        )
        # Add fixed parameters
        kwargs["f_conv"] = self._f_conv
        kwargs["f_rad"] = self._f_rad
        kwargs["T_ground"] = self._T_ground
        kwargs["has_split"] = self._has_split

        if self._order == ModelOrder.THREE:
            kwargs["R_ins"] = self._R_ins

        return RCParams(**kwargs)  # type: ignore[arg-type]

    def _cost_fn_log(
        self,
        phi: NDArray[np.float64],
        u_sequence: NDArray[np.float64],
        d_sequence: NDArray[np.float64],
        T_room_measured: NDArray[np.float64],
    ) -> float:
        """Compute MSE in log-parameter space.

        Optimizing in log-space equalises the gradient scale across
        parameters that span many orders of magnitude (R ~ 0.01 K/W
        vs C ~ 10^6 J/K), which is critical for L-BFGS-B convergence.

        Args:
            phi: Log-transformed parameter vector (phi = log(theta)).
            u_sequence: Control input sequence, shape (N, n_inputs).
            d_sequence: Disturbance sequence, shape (N, n_disturbances).
            T_room_measured: Measured room temperature, shape (N,).

        Returns:
            Mean squared error [degC^2], or inf if evaluation fails.
        """
        try:
            theta = np.exp(phi)
            params = self._unpack_params(theta)
            model = RCModel(params, self._order, self._dt)
            # Initialize all states to first measured temperature
            x0 = np.full(model.n_states, T_room_measured[0])
            trajectory = model.predict(x0, u_sequence, d_sequence)
            # trajectory shape: (N+1, n_states); skip x0 row
            pred_T_air = trajectory[1:, 0]
            # Skip burn-in steps from cost computation
            b = self._burnin_steps
            mse = float(np.mean((pred_T_air[b:] - T_room_measured[b:]) ** 2))
        except (ValueError, np.linalg.LinAlgError):
            return float("inf")
        else:
            return mse

    def _cost_fn(
        self,
        theta: NDArray[np.float64],
        u_sequence: NDArray[np.float64],
        d_sequence: NDArray[np.float64],
        T_room_measured: NDArray[np.float64],
    ) -> float:
        """Compute MSE between predicted T_air and measured T_room.

        All states are initialized to the first measured temperature.
        The first ``burnin_steps`` samples are excluded from the MSE
        to mitigate the effect of unknown initial conditions (especially
        for the unobserved T_slab and T_wall nodes whose true initial
        values differ from T_air).

        Args:
            theta: Parameter vector to evaluate (natural space).
            u_sequence: Control input sequence, shape (N, n_inputs).
            d_sequence: Disturbance sequence, shape (N, n_disturbances).
            T_room_measured: Measured room temperature, shape (N,).

        Returns:
            Mean squared error [degC^2], or inf if evaluation fails.
        """
        try:
            params = self._unpack_params(theta)
            model = RCModel(params, self._order, self._dt)
            # Initialize all states to first measured temperature
            x0 = np.full(model.n_states, T_room_measured[0])
            trajectory = model.predict(x0, u_sequence, d_sequence)
            # trajectory shape: (N+1, n_states); skip x0 row
            pred_T_air = trajectory[1:, 0]
            # Skip burn-in steps from cost computation
            b = self._burnin_steps
            mse = float(np.mean((pred_T_air[b:] - T_room_measured[b:]) ** 2))
        except (ValueError, np.linalg.LinAlgError):
            return float("inf")
        else:
            return mse

    def _sample_initial_points(self) -> list[NDArray[np.float64]]:
        """Generate uniformly distributed initial points in log-space.

        Log-uniform sampling covers the wide dynamic range of RC parameters
        (C_air ~ 60k J/K vs C_slab ~ 3.25M J/K). Returns log-transformed
        vectors for direct use with :meth:`_cost_fn_log`.

        Returns:
            List of initial log-parameter vectors, one per multi-start run.
        """
        points: list[NDArray[np.float64]] = []
        for _ in range(self._n_starts):
            phi = np.array(
                [
                    self._rng.uniform(np.log(lo), np.log(hi))
                    for lo, hi in self._bounds_list
                ],
                dtype=np.float64,
            )
            points.append(phi)
        return points

    def identify(
        self,
        u_sequence: NDArray[np.float64],
        d_sequence: NDArray[np.float64],
        T_room_measured: NDArray[np.float64],
    ) -> IdentificationResult:
        """Run multi-start L-BFGS-B identification on measurement data.

        Optimization is performed in log-parameter space to equalise
        gradient scales across parameters spanning many orders of
        magnitude.

        Args:
            u_sequence: Control input sequence, shape (N, n_inputs).
            d_sequence: Disturbance sequence, shape (N, n_disturbances).
            T_room_measured: Measured room temperature, shape (N,).

        Returns:
            IdentificationResult with the best parameters found.

        Raises:
            ValueError: If input array shapes are inconsistent.
        """
        # --- Input validation ---
        if u_sequence.ndim != 2:
            msg = f"u_sequence must be 2D, got {u_sequence.ndim}D"
            raise ValueError(msg)
        if d_sequence.ndim != 2:
            msg = f"d_sequence must be 2D, got {d_sequence.ndim}D"
            raise ValueError(msg)
        if T_room_measured.ndim != 1:
            msg = f"T_room_measured must be 1D, got {T_room_measured.ndim}D"
            raise ValueError(msg)
        if not (
            u_sequence.shape[0] == d_sequence.shape[0] == T_room_measured.shape[0]
        ):
            msg = (
                f"Sequence lengths must match: "
                f"u_sequence={u_sequence.shape[0]}, "
                f"d_sequence={d_sequence.shape[0]}, "
                f"T_room_measured={T_room_measured.shape[0]}"
            )
            raise ValueError(msg)

        # --- Multi-start optimization in log-space ---
        log_bounds = [
            (np.log(lo), np.log(hi)) for lo, hi in self._bounds_list
        ]
        initial_points = self._sample_initial_points()
        results: list[OptimizeResult] = []

        for phi0 in initial_points:
            res = minimize(
                self._cost_fn_log,
                x0=phi0,
                args=(u_sequence, d_sequence, T_room_measured),
                method="L-BFGS-B",
                bounds=log_bounds,
                options={
                    "maxiter": self._maxiter,
                    "ftol": 1e-12,
                    "gtol": 1e-8,
                },
            )
            results.append(res)

        # --- Select best result ---
        best = min(results, key=lambda r: float(r.fun))
        all_costs = tuple(sorted(float(r.fun) for r in results))
        best_params = self._unpack_params(np.exp(best.x))

        return IdentificationResult(
            params=best_params,
            cost=float(best.fun),
            n_starts=self._n_starts,
            converged=bool(best.success),
            all_costs=all_costs,
        )
