"""Cross-validation framework for RC parameter identification quality.

Validates identified RC model parameters by splitting time-series data
into contiguous train/test segments (default 70/30), running identification
on the training set, and evaluating forward prediction accuracy on both
sets at multiple horizons (6h, 12h, 24h).

Overfitting is detected when the test-to-train RMSE ratio exceeds a
configurable threshold (default 1.5).

Typical usage:
    identifier = RCIdentifier(ModelOrder.TWO, dt=60.0, n_starts=10)
    result = cross_validate(
        identifier, u_sequence, d_sequence, T_room_measured,
    )
    print(result.is_overfitting)       # False if model generalises
    for h in result.horizons:
        print(f"{h.horizon_hours}h: test RMSE = {h.test_rmse}")

Units: R in K/W, C in J/K, T in degC, Q in W, time in seconds.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from pumpahead.identifier import IdentificationResult, RCIdentifier
from pumpahead.model import RCModel

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HORIZONS: tuple[float, ...] = (6.0, 12.0, 24.0)
"""Default prediction horizons in hours."""

DEFAULT_OVERFITTING_THRESHOLD: float = 1.5
"""Default maximum test/train RMSE ratio before flagging overfitting."""

# ---------------------------------------------------------------------------
# HorizonRMSE
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HorizonRMSE:
    """Per-horizon RMSE for train and test sets.

    Attributes:
        horizon_hours: Prediction horizon length [hours].
        train_rmse: RMSE on the training segment [degC].
        test_rmse: RMSE on the test segment [degC], or ``None``
            if the test set is shorter than the horizon.
        overfitting_ratio: ``test_rmse / train_rmse``, or ``None``
            when either RMSE is ``None`` or train_rmse is zero.
    """

    horizon_hours: float
    train_rmse: float
    test_rmse: float | None
    overfitting_ratio: float | None

    def __post_init__(self) -> None:
        """Validate horizon fields."""
        if self.horizon_hours <= 0:
            msg = f"horizon_hours must be positive, got {self.horizon_hours}"
            raise ValueError(msg)
        if self.train_rmse < 0:
            msg = f"train_rmse must be non-negative, got {self.train_rmse}"
            raise ValueError(msg)
        if self.test_rmse is not None and self.test_rmse < 0:
            msg = f"test_rmse must be non-negative, got {self.test_rmse}"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# CrossValidationResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CrossValidationResult:
    """Result of cross-validation for one room / dataset.

    Attributes:
        identification: The ``IdentificationResult`` from training.
        horizons: Per-horizon RMSE breakdown.
        train_rmse: Overall RMSE on the full training segment [degC].
        test_rmse: Overall RMSE on the full test segment [degC].
        overfitting_ratio: ``test_rmse / train_rmse``, or ``None``
            when train_rmse is zero.
        is_overfitting: Whether overfitting_ratio exceeds the threshold.
        train_size: Number of timesteps in the training set.
        test_size: Number of timesteps in the test set.
    """

    identification: IdentificationResult
    horizons: tuple[HorizonRMSE, ...]
    train_rmse: float
    test_rmse: float
    overfitting_ratio: float | None
    is_overfitting: bool
    train_size: int
    test_size: int

    def __post_init__(self) -> None:
        """Validate result fields."""
        if self.train_rmse < 0:
            msg = f"train_rmse must be non-negative, got {self.train_rmse}"
            raise ValueError(msg)
        if self.test_rmse < 0:
            msg = f"test_rmse must be non-negative, got {self.test_rmse}"
            raise ValueError(msg)
        if self.train_size < 1:
            msg = f"train_size must be >= 1, got {self.train_size}"
            raise ValueError(msg)
        if self.test_size < 1:
            msg = f"test_size must be >= 1, got {self.test_size}"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _forward_rmse(
    model: RCModel,
    x0: NDArray[np.float64],
    u_segment: NDArray[np.float64],
    d_segment: NDArray[np.float64],
    T_measured: NDArray[np.float64],
    n_steps: int,
) -> float:
    """Compute RMSE of T_air prediction over *n_steps* steps.

    Args:
        model: Discrete RC model with identified parameters.
        x0: Initial state vector, shape (n_states,).
        u_segment: Control inputs for the segment, shape (>=n_steps, n_inputs).
        d_segment: Disturbances for the segment, shape (>=n_steps, n_disturbances).
        T_measured: Measured T_room for the segment, shape (>=n_steps,).
        n_steps: Number of prediction steps to evaluate.

    Returns:
        RMSE in degC.
    """
    trajectory = model.predict(x0, u_segment[:n_steps], d_segment[:n_steps])
    pred_T_air = trajectory[1:, 0]  # skip x0 row
    residuals = pred_T_air - T_measured[:n_steps]
    return float(np.sqrt(np.mean(residuals**2)))


# ---------------------------------------------------------------------------
# cross_validate
# ---------------------------------------------------------------------------


def cross_validate(
    identifier: RCIdentifier,
    u_sequence: NDArray[np.float64],
    d_sequence: NDArray[np.float64],
    T_room_measured: NDArray[np.float64],
    *,
    train_ratio: float = 0.7,
    horizons_hours: tuple[float, ...] = DEFAULT_HORIZONS,
    overfitting_threshold: float = DEFAULT_OVERFITTING_THRESHOLD,
) -> CrossValidationResult:
    """Run cross-validation on a single dataset.

    Splits data into contiguous train/test segments (first *train_ratio*
    fraction for training, remainder for testing), identifies RC parameters
    on the training set, then evaluates forward prediction RMSE on both
    sets at each requested horizon.

    Args:
        identifier: Configured ``RCIdentifier`` instance.
        u_sequence: Control input sequence, shape (N, n_inputs).
        d_sequence: Disturbance sequence, shape (N, n_disturbances).
        T_room_measured: Measured room temperature, shape (N,).
        train_ratio: Fraction of data used for training (0 < ratio < 1).
        horizons_hours: Prediction horizons in hours.
        overfitting_threshold: Maximum test/train RMSE ratio before
            flagging overfitting.

    Returns:
        ``CrossValidationResult`` with per-horizon RMSE and overfitting
        diagnostics.

    Raises:
        ValueError: If inputs are invalid (bad train_ratio, mismatched
            lengths, data too short for a meaningful split).
    """
    # --- Input validation ---
    if not 0 < train_ratio < 1:
        msg = f"train_ratio must be in (0, 1), got {train_ratio}"
        raise ValueError(msg)

    n = T_room_measured.shape[0]
    if u_sequence.shape[0] != n or d_sequence.shape[0] != n:
        msg = (
            f"Sequence lengths must match: "
            f"u_sequence={u_sequence.shape[0]}, "
            f"d_sequence={d_sequence.shape[0]}, "
            f"T_room_measured={n}"
        )
        raise ValueError(msg)

    split_idx = int(n * train_ratio)
    if split_idx < 1:
        msg = f"Training set too short: {split_idx} steps (need >= 1)"
        raise ValueError(msg)
    if n - split_idx < 1:
        msg = f"Test set too short: {n - split_idx} steps (need >= 1)"
        raise ValueError(msg)

    # --- Split data ---
    u_train = u_sequence[:split_idx]
    d_train = d_sequence[:split_idx]
    T_train = T_room_measured[:split_idx]

    u_test = u_sequence[split_idx:]
    d_test = d_sequence[split_idx:]
    T_test = T_room_measured[split_idx:]

    train_size = split_idx
    test_size = n - split_idx

    # --- Identify on training set ---
    id_result = identifier.identify(u_train, d_train, T_train)

    # --- Build model from identified params ---
    model = RCModel(id_result.params, identifier.order, identifier.dt)

    # --- Compute overall train RMSE (full training segment) ---
    # Initialize all states to first measured temperature (same as identifier)
    x0_train = np.full(model.n_states, T_train[0])
    train_trajectory = model.predict(x0_train, u_train, d_train)
    pred_train_T_air = train_trajectory[1:, 0]
    train_rmse = float(
        np.sqrt(np.mean((pred_train_T_air - T_train) ** 2))
    )

    # --- Derive test initial state from end of training trajectory ---
    # Using the model's end-of-training state provides realistic initial
    # conditions for unobserved states (T_slab, T_wall) that differ
    # significantly from T_air due to thermal mass.
    x0_test = train_trajectory[-1]

    # --- Compute overall test RMSE (full test segment) ---
    test_rmse = _forward_rmse(
        model, x0_test, u_test, d_test, T_test, test_size
    )

    # --- Overfitting detection (overall) ---
    # When train_rmse is near zero (< 1e-3 degC), the ratio is numerically
    # meaningless. Both segments fit well, so overfitting is not a concern.
    _RMSE_FLOOR = 1e-3
    if train_rmse < _RMSE_FLOOR:
        overfitting_ratio: float | None = None
        is_overfitting = False
    else:
        overfitting_ratio = test_rmse / train_rmse
        is_overfitting = overfitting_ratio > overfitting_threshold

    # --- Per-horizon RMSE ---
    dt = identifier.dt
    horizon_results: list[HorizonRMSE] = []

    for h in horizons_hours:
        h_steps = int(h * 3600 / dt)

        # Train horizon RMSE (reuse precomputed train trajectory)
        n_train_eval = min(h_steps, train_size)
        h_train_residuals = pred_train_T_air[:n_train_eval] - T_train[:n_train_eval]
        h_train_rmse = float(np.sqrt(np.mean(h_train_residuals**2)))

        # Test horizon RMSE
        if h_steps <= test_size:
            h_test_rmse: float | None = _forward_rmse(
                model, x0_test, u_test, d_test, T_test, h_steps
            )
        else:
            h_test_rmse = None

        # Per-horizon overfitting ratio
        if h_test_rmse is not None and h_train_rmse > 0.0:
            h_ratio: float | None = h_test_rmse / h_train_rmse
        else:
            h_ratio = None

        horizon_results.append(
            HorizonRMSE(
                horizon_hours=h,
                train_rmse=h_train_rmse,
                test_rmse=h_test_rmse,
                overfitting_ratio=h_ratio,
            )
        )

    return CrossValidationResult(
        identification=id_result,
        horizons=tuple(horizon_results),
        train_rmse=train_rmse,
        test_rmse=test_rmse,
        overfitting_ratio=overfitting_ratio,
        is_overfitting=is_overfitting,
        train_size=train_size,
        test_size=test_size,
    )


# ---------------------------------------------------------------------------
# cross_validate_rooms
# ---------------------------------------------------------------------------


def cross_validate_rooms(
    rooms: dict[
        str,
        tuple[
            RCIdentifier,
            NDArray[np.float64],
            NDArray[np.float64],
            NDArray[np.float64],
        ],
    ],
    *,
    train_ratio: float = 0.7,
    horizons_hours: tuple[float, ...] = DEFAULT_HORIZONS,
    overfitting_threshold: float = DEFAULT_OVERFITTING_THRESHOLD,
) -> dict[str, CrossValidationResult]:
    """Run cross-validation for multiple rooms.

    Each room provides its own ``RCIdentifier`` and data sequences, since
    different rooms may have different model orders, time steps, or sensor
    configurations.

    Args:
        rooms: Mapping of room name to a tuple of
            ``(identifier, u_sequence, d_sequence, T_room_measured)``.
        train_ratio: Fraction of data used for training (0 < ratio < 1).
        horizons_hours: Prediction horizons in hours.
        overfitting_threshold: Maximum test/train RMSE ratio before
            flagging overfitting.

    Returns:
        Dictionary mapping room name to ``CrossValidationResult``.
    """
    results: dict[str, CrossValidationResult] = {}
    for name, (ident, u, d, t_room) in rooms.items():
        results[name] = cross_validate(
            ident,
            u,
            d,
            t_room,
            train_ratio=train_ratio,
            horizons_hours=horizons_hours,
            overfitting_threshold=overfitting_threshold,
        )
    return results
