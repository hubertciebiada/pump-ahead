"""Reporting and visualization for RC parameter identification.

Provides frozen dataclasses for per-room and multi-room identification
quality reports, plot functions for predicted-vs-measured comparison,
residual analysis, and RMSE trends, plus a ``QualityMonitor`` class
that detects prediction quality degradation and triggers
auto-reidentification.

Plot functions use the matplotlib Agg backend and optionally save
figures as PNG.  matplotlib is an optional dependency (``viz`` extra);
plot functions raise ``ImportError`` with installation instructions
when it is not available.

Typical usage:
    report = IdentificationReport.from_cv_results(cv_results, data)
    for room in report.rooms:
        fig = plot_predicted_vs_measured(
            room.T_predicted, room.T_measured, room_name=room.room_name,
        )

    monitor = QualityMonitor(rmse_threshold=0.5)
    monitor.update("living_room", current_rmse=0.35)
    if monitor.needs_reidentification("living_room"):
        ...  # trigger reidentification

Units: T in degC, RMSE in degC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from pumpahead.cross_validation import CrossValidationResult
from pumpahead.identifier import IdentificationResult
from pumpahead.model import ModelOrder, RCModel, RCParams

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RMSE_PASS_THRESHOLD: float = 0.5
"""Default RMSE threshold for pass/fail [degC]."""

DEFAULT_RMSE_REIDENTIFICATION_THRESHOLD: float = 0.5
"""Default RMSE threshold for triggering auto-reidentification [degC]."""

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _lazy_import_matplotlib() -> Any:
    """Lazy-import matplotlib.pyplot with Agg backend.

    Returns:
        The ``matplotlib.pyplot`` module.

    Raises:
        ImportError: If matplotlib is not installed.
    """
    try:
        import matplotlib
    except ImportError:
        msg = (
            "matplotlib is required for identification report plots. "
            "Install it with: pip install pumpahead[viz]"
        )
        raise ImportError(msg) from None

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


# ---------------------------------------------------------------------------
# RoomReport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoomReport:
    """Per-room identification quality report.

    Attributes:
        room_name: Human-readable room identifier.
        params: Identified RC model parameters.
        identification: Full identification result from training.
        cross_validation: Full cross-validation result.
        rmse_threshold: Pass/fail threshold [degC].
        passed: ``True`` when ``cross_validation.test_rmse <= rmse_threshold``.
        T_predicted: Predicted room temperature on the test segment [degC].
        T_measured: Measured room temperature on the test segment [degC].
    """

    room_name: str
    params: RCParams
    identification: IdentificationResult
    cross_validation: CrossValidationResult
    rmse_threshold: float
    passed: bool
    T_predicted: NDArray[np.float64]
    T_measured: NDArray[np.float64]

    def __post_init__(self) -> None:
        """Validate report fields."""
        if not self.room_name:
            msg = "room_name must be a non-empty string"
            raise ValueError(msg)
        if self.rmse_threshold <= 0:
            msg = f"rmse_threshold must be positive, got {self.rmse_threshold}"
            raise ValueError(msg)
        if self.T_predicted.ndim != 1:
            msg = f"T_predicted must be 1D, got {self.T_predicted.ndim}D"
            raise ValueError(msg)
        if self.T_measured.ndim != 1:
            msg = f"T_measured must be 1D, got {self.T_measured.ndim}D"
            raise ValueError(msg)
        if self.T_predicted.shape != self.T_measured.shape:
            msg = (
                f"T_predicted shape {self.T_predicted.shape} must match "
                f"T_measured shape {self.T_measured.shape}"
            )
            raise ValueError(msg)

    @property
    def rmse(self) -> float:
        """Overall test RMSE from the cross-validation result [degC]."""
        return self.cross_validation.test_rmse

    @property
    def residuals(self) -> NDArray[np.float64]:
        """Prediction residuals: ``T_predicted - T_measured`` [degC]."""
        return self.T_predicted - self.T_measured


# ---------------------------------------------------------------------------
# IdentificationReport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentificationReport:
    """Multi-room identification quality report.

    Attributes:
        rooms: Per-room reports (at least one).
        created_at: ISO 8601 timestamp of report creation.
    """

    rooms: tuple[RoomReport, ...]
    created_at: str

    def __post_init__(self) -> None:
        """Validate report fields."""
        if len(self.rooms) == 0:
            msg = "IdentificationReport must contain at least one room"
            raise ValueError(msg)

    @property
    def all_passed(self) -> bool:
        """``True`` when all rooms passed their RMSE threshold."""
        return all(room.passed for room in self.rooms)

    @property
    def failed_rooms(self) -> tuple[str, ...]:
        """Names of rooms that did not pass the RMSE threshold."""
        return tuple(room.room_name for room in self.rooms if not room.passed)

    @classmethod
    def from_cv_results(
        cls,
        cv_results: dict[str, CrossValidationResult],
        data: dict[
            str,
            tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]],
        ],
        *,
        rmse_threshold: float = DEFAULT_RMSE_PASS_THRESHOLD,
        dt: float = 60.0,
    ) -> IdentificationReport:
        """Build a report from cross-validation results and raw data.

        For each room, recomputes the predicted temperature on the test
        segment using the identified parameters and the same train/test
        split that ``cross_validate`` used.

        Args:
            cv_results: Mapping of room name to ``CrossValidationResult``.
            data: Mapping of room name to
                ``(u_sequence, d_sequence, T_room_measured)``.
            rmse_threshold: Pass/fail RMSE threshold [degC].
            dt: Discretization time step in seconds (must match the
                value used during identification).

        Returns:
            An ``IdentificationReport`` covering all rooms.

        Raises:
            ValueError: If room names do not match between cv_results and
                data, if rmse_threshold is non-positive, or if either
                dict is empty.
        """
        if rmse_threshold <= 0:
            msg = f"rmse_threshold must be positive, got {rmse_threshold}"
            raise ValueError(msg)
        if not cv_results:
            msg = "cv_results must not be empty"
            raise ValueError(msg)
        if set(cv_results.keys()) != set(data.keys()):
            missing_in_data = set(cv_results.keys()) - set(data.keys())
            missing_in_cv = set(data.keys()) - set(cv_results.keys())
            msg = (
                f"Room name mismatch: "
                f"in cv_results but not data: {missing_in_data}, "
                f"in data but not cv_results: {missing_in_cv}"
            )
            raise ValueError(msg)

        room_reports: list[RoomReport] = []

        for room_name, cv_result in cv_results.items():
            u_seq, d_seq, T_measured_full = data[room_name]
            id_result = cv_result.identification

            # Reconstruct the train/test split indices
            n_total = len(T_measured_full)
            train_size = cv_result.train_size
            test_size = cv_result.test_size

            # Validate consistency
            if train_size + test_size != n_total:
                msg = (
                    f"Room '{room_name}': train_size ({train_size}) + "
                    f"test_size ({test_size}) != data length ({n_total})"
                )
                raise ValueError(msg)

            split_idx = train_size

            # Infer model order from identified params: if R_env is set,
            # it's 2R2C; otherwise 3R3C.
            if id_result.params.R_env is not None:
                order = ModelOrder.TWO
            else:
                order = ModelOrder.THREE

            model = RCModel(id_result.params, order, dt)

            # Compute predicted T on the training segment to get end state
            u_train = u_seq[:split_idx]
            d_train = d_seq[:split_idx]
            T_train = T_measured_full[:split_idx]
            x0_train = np.full(model.n_states, T_train[0])
            train_trajectory = model.predict(x0_train, u_train, d_train)

            # Use end-of-training state as test initial state
            x0_test = train_trajectory[-1]

            # Compute predicted T on the test segment
            u_test = u_seq[split_idx:]
            d_test = d_seq[split_idx:]
            T_test = T_measured_full[split_idx:]
            test_trajectory = model.predict(x0_test, u_test, d_test)
            T_predicted = test_trajectory[1:, 0]  # T_air, skip x0 row

            passed = cv_result.test_rmse <= rmse_threshold

            room_reports.append(
                RoomReport(
                    room_name=room_name,
                    params=id_result.params,
                    identification=id_result,
                    cross_validation=cv_result,
                    rmse_threshold=rmse_threshold,
                    passed=passed,
                    T_predicted=T_predicted,
                    T_measured=T_test,
                )
            )

        return cls(
            rooms=tuple(room_reports),
            created_at=datetime.now(tz=UTC).isoformat(),
        )


# ---------------------------------------------------------------------------
# QualityMonitor
# ---------------------------------------------------------------------------


class QualityMonitor:
    """Monitors prediction quality and triggers auto-reidentification.

    Tracks per-room RMSE over time and flags rooms where the latest RMSE
    exceeds a configurable threshold, indicating that the identified RC
    parameters no longer adequately represent the building's thermal
    behaviour.

    Typical usage:
        monitor = QualityMonitor(rmse_threshold=0.5)
        monitor.update("living_room", current_rmse=0.35)
        assert not monitor.needs_reidentification("living_room")

        monitor.update("living_room", current_rmse=0.65)
        assert monitor.needs_reidentification("living_room")
    """

    def __init__(
        self,
        rmse_threshold: float = DEFAULT_RMSE_REIDENTIFICATION_THRESHOLD,
    ) -> None:
        """Initialize the quality monitor.

        Args:
            rmse_threshold: RMSE above which reidentification is needed [degC].

        Raises:
            ValueError: If rmse_threshold is non-positive.
        """
        if rmse_threshold <= 0:
            msg = f"rmse_threshold must be positive, got {rmse_threshold}"
            raise ValueError(msg)
        self._rmse_threshold = rmse_threshold
        self._history: dict[str, list[float]] = {}

    @property
    def threshold(self) -> float:
        """Current RMSE reidentification threshold [degC]."""
        return self._rmse_threshold

    def update(self, room_name: str, current_rmse: float) -> None:
        """Record a new RMSE measurement for a room.

        Args:
            room_name: Room identifier.
            current_rmse: Latest RMSE value [degC].

        Raises:
            ValueError: If current_rmse is negative.
        """
        if current_rmse < 0:
            msg = f"current_rmse must be non-negative, got {current_rmse}"
            raise ValueError(msg)
        if room_name not in self._history:
            self._history[room_name] = []
        self._history[room_name].append(current_rmse)

    def needs_reidentification(self, room_name: str) -> bool:
        """Check whether a room needs reidentification.

        Returns ``True`` when the latest RMSE for the room exceeds the
        threshold.  Returns ``False`` for unknown rooms or rooms with
        no history.

        Args:
            room_name: Room identifier.

        Returns:
            ``True`` if the latest RMSE exceeds the threshold.
        """
        history = self._history.get(room_name)
        if not history:
            return False
        return history[-1] > self._rmse_threshold

    def get_history(self, room_name: str) -> list[float]:
        """Return the RMSE history for a room (copy).

        Args:
            room_name: Room identifier.

        Returns:
            List of recorded RMSE values, empty if room is unknown.
        """
        return list(self._history.get(room_name, []))

    def reset(self, room_name: str) -> None:
        """Clear the RMSE history for a room.

        Typically called after successful reidentification.

        Args:
            room_name: Room identifier.
        """
        self._history.pop(room_name, None)


# ---------------------------------------------------------------------------
# Plot functions
# ---------------------------------------------------------------------------


def plot_predicted_vs_measured(
    T_predicted: NDArray[np.float64],
    T_measured: NDArray[np.float64],
    *,
    room_name: str = "",
    title: str | None = None,
    save_path: Path | None = None,
) -> Figure:
    """Plot predicted vs measured room temperature.

    Creates a time-series overlay of predicted and measured T_room with
    a shaded residual band.

    Args:
        T_predicted: Predicted temperature array [degC].
        T_measured: Measured temperature array [degC].
        room_name: Room name for the plot title.
        title: Custom title (overrides auto-generated title).
        save_path: If provided, save the figure as PNG at this path.

    Returns:
        matplotlib Figure.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If array shapes don't match or are empty.
    """
    if T_predicted.shape != T_measured.shape:
        msg = (
            f"T_predicted shape {T_predicted.shape} must match "
            f"T_measured shape {T_measured.shape}"
        )
        raise ValueError(msg)
    if len(T_predicted) == 0:
        msg = "Arrays must not be empty"
        raise ValueError(msg)

    plt = _lazy_import_matplotlib()

    fig, ax = plt.subplots(figsize=(12, 5))
    steps = np.arange(len(T_predicted))

    ax.plot(steps, T_measured, label="Measured", color="#2196F3", linewidth=1.0)
    ax.plot(
        steps,
        T_predicted,
        label="Predicted",
        color="#FF5722",
        linewidth=1.0,
        linestyle="--",
    )
    ax.fill_between(
        steps,
        T_measured,
        T_predicted,
        alpha=0.15,
        color="#FF5722",
        label="Residual",
    )

    if title is not None:
        ax.set_title(title)
    elif room_name:
        ax.set_title(f"Predicted vs Measured T_room — {room_name}")
    else:
        ax.set_title("Predicted vs Measured T_room")

    ax.set_xlabel("Time step")
    ax.set_ylabel("Temperature [degC]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig  # type: ignore[no-any-return]


def plot_residuals(
    T_predicted: NDArray[np.float64],
    T_measured: NDArray[np.float64],
    *,
    room_name: str = "",
    save_path: Path | None = None,
) -> Figure:
    """Plot prediction residuals (T_predicted - T_measured).

    Creates a bar/line chart of residuals with a zero reference line.

    Args:
        T_predicted: Predicted temperature array [degC].
        T_measured: Measured temperature array [degC].
        room_name: Room name for the plot title.
        save_path: If provided, save the figure as PNG at this path.

    Returns:
        matplotlib Figure.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If array shapes don't match or are empty.
    """
    if T_predicted.shape != T_measured.shape:
        msg = (
            f"T_predicted shape {T_predicted.shape} must match "
            f"T_measured shape {T_measured.shape}"
        )
        raise ValueError(msg)
    if len(T_predicted) == 0:
        msg = "Arrays must not be empty"
        raise ValueError(msg)

    plt = _lazy_import_matplotlib()

    residuals = T_predicted - T_measured
    fig, ax = plt.subplots(figsize=(12, 4))
    steps = np.arange(len(residuals))

    ax.plot(steps, residuals, color="#9C27B0", linewidth=0.8, alpha=0.8)
    ax.axhline(y=0, color="black", linewidth=0.5, linestyle="-")
    ax.fill_between(steps, 0, residuals, alpha=0.2, color="#9C27B0")

    title_suffix = f" — {room_name}" if room_name else ""
    ax.set_title(f"Prediction Residuals{title_suffix}")
    ax.set_xlabel("Time step")
    ax.set_ylabel("Residual [degC]")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig  # type: ignore[no-any-return]


def plot_rmse_over_time(
    rmse_history: list[float],
    *,
    room_name: str = "",
    threshold: float | None = None,
    save_path: Path | None = None,
) -> Figure:
    """Plot RMSE trend over time with optional threshold line.

    Args:
        rmse_history: List of RMSE values in chronological order [degC].
        room_name: Room name for the plot title.
        threshold: If provided, draw a horizontal threshold line.
        save_path: If provided, save the figure as PNG at this path.

    Returns:
        matplotlib Figure.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If rmse_history is empty.
    """
    if len(rmse_history) == 0:
        msg = "rmse_history must not be empty"
        raise ValueError(msg)

    plt = _lazy_import_matplotlib()

    fig, ax = plt.subplots(figsize=(10, 4))
    steps = list(range(len(rmse_history)))

    ax.plot(
        steps,
        rmse_history,
        marker="o",
        markersize=4,
        color="#4CAF50",
        linewidth=1.5,
        label="RMSE",
    )

    if threshold is not None:
        ax.axhline(
            y=threshold,
            color="#F44336",
            linewidth=1.0,
            linestyle="--",
            label=f"Threshold ({threshold:.2f} degC)",
        )

    title_suffix = f" — {room_name}" if room_name else ""
    ax.set_title(f"RMSE Over Time{title_suffix}")
    ax.set_xlabel("Evaluation index")
    ax.set_ylabel("RMSE [degC]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig  # type: ignore[no-any-return]
