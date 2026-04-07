"""Unit tests for pumpahead.identification_report."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pumpahead.cross_validation import (
    CrossValidationResult,
    HorizonRMSE,
    cross_validate,
)
from pumpahead.identification_report import (
    DEFAULT_RMSE_PASS_THRESHOLD,
    DEFAULT_RMSE_REIDENTIFICATION_THRESHOLD,
    IdentificationReport,
    QualityMonitor,
    RoomReport,
    plot_predicted_vs_measured,
    plot_residuals,
    plot_rmse_over_time,
)
from pumpahead.identifier import IdentificationResult, RCIdentifier
from pumpahead.model import ModelOrder, RCModel, RCParams

# ---------------------------------------------------------------------------
# Shared informed bounds (same as test_cross_validation.py)
# ---------------------------------------------------------------------------

_INFORMED_BOUNDS_2R2C: dict[str, tuple[float, float]] = {
    "R_sf": (0.0085, 0.0115),
    "R_env": (0.0255, 0.0345),
    "C_air": (51_000.0, 69_000.0),
    "C_slab": (2_762_500.0, 3_737_500.0),
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_id_result(params_2r2c: RCParams) -> IdentificationResult:
    """Minimal IdentificationResult for unit tests."""
    return IdentificationResult(
        params=params_2r2c,
        cost=0.01,
        n_starts=5,
        converged=True,
        all_costs=(0.01, 0.02, 0.03, 0.04, 0.05),
    )


@pytest.fixture()
def simple_cv_result(
    simple_id_result: IdentificationResult,
) -> CrossValidationResult:
    """Minimal CrossValidationResult for unit tests."""
    horizon = HorizonRMSE(
        horizon_hours=6.0,
        train_rmse=0.1,
        test_rmse=0.2,
        overfitting_ratio=2.0,
    )
    return CrossValidationResult(
        identification=simple_id_result,
        horizons=(horizon,),
        train_rmse=0.1,
        test_rmse=0.2,
        overfitting_ratio=2.0,
        is_overfitting=False,
        train_size=100,
        test_size=50,
    )


@pytest.fixture()
def cv_synth_data_2r2c(
    params_2r2c: RCParams,
    model_2r2c: RCModel,
) -> tuple[RCParams, np.ndarray, np.ndarray, np.ndarray]:
    """Synthetic 2R2C data for cross-validation: 4 days at dt=60s."""
    n_steps = 5760  # 4 days
    u_seq = np.zeros((n_steps, 1))
    for i in range(n_steps):
        block = (i // 240) % 2
        u_seq[i, 0] = 0.0 if block == 0 else 1500.0

    d_seq = np.zeros((n_steps, 2))
    d_seq[:, 0] = 5.0

    x0 = np.array([5.0, 5.0])
    traj = model_2r2c.predict(x0, u_seq, d_seq)
    T_room = traj[1:, 0]

    return params_2r2c, u_seq, d_seq, T_room


@pytest.fixture()
def identifier_2r2c() -> RCIdentifier:
    """2R2C identifier with informed bounds and 20 starts."""
    return RCIdentifier(
        ModelOrder.TWO,
        dt=60.0,
        n_starts=20,
        seed=42,
        bounds=_INFORMED_BOUNDS_2R2C,
    )


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module-level constants."""

    @pytest.mark.unit
    def test_default_rmse_pass_threshold(self) -> None:
        """DEFAULT_RMSE_PASS_THRESHOLD is 0.5."""
        assert DEFAULT_RMSE_PASS_THRESHOLD == 0.5

    @pytest.mark.unit
    def test_default_rmse_reidentification_threshold(self) -> None:
        """DEFAULT_RMSE_REIDENTIFICATION_THRESHOLD is 0.5."""
        assert DEFAULT_RMSE_REIDENTIFICATION_THRESHOLD == 0.5


# ---------------------------------------------------------------------------
# TestRoomReport
# ---------------------------------------------------------------------------


class TestRoomReport:
    """Tests for the RoomReport frozen dataclass."""

    @pytest.mark.unit
    def test_construction_valid(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """Valid RoomReport can be constructed."""
        T_pred = np.array([20.0, 20.5, 21.0])
        T_meas = np.array([20.1, 20.4, 20.9])
        report = RoomReport(
            room_name="living_room",
            params=simple_id_result.params,
            identification=simple_id_result,
            cross_validation=simple_cv_result,
            rmse_threshold=0.5,
            passed=True,
            T_predicted=T_pred,
            T_measured=T_meas,
        )
        assert report.room_name == "living_room"
        assert report.rmse_threshold == 0.5
        assert report.passed is True

    @pytest.mark.unit
    def test_frozen(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """RoomReport is immutable."""
        T_pred = np.array([20.0, 20.5])
        T_meas = np.array([20.1, 20.4])
        report = RoomReport(
            room_name="kitchen",
            params=simple_id_result.params,
            identification=simple_id_result,
            cross_validation=simple_cv_result,
            rmse_threshold=0.5,
            passed=True,
            T_predicted=T_pred,
            T_measured=T_meas,
        )
        with pytest.raises(AttributeError):
            report.room_name = "bedroom"  # type: ignore[misc]

    @pytest.mark.unit
    def test_rmse_property(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """rmse property returns test_rmse from cross-validation."""
        T_pred = np.array([20.0])
        T_meas = np.array([20.1])
        report = RoomReport(
            room_name="bedroom",
            params=simple_id_result.params,
            identification=simple_id_result,
            cross_validation=simple_cv_result,
            rmse_threshold=0.5,
            passed=True,
            T_predicted=T_pred,
            T_measured=T_meas,
        )
        assert report.rmse == 0.2  # from simple_cv_result.test_rmse

    @pytest.mark.unit
    def test_residuals_property(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """residuals property returns T_predicted - T_measured."""
        T_pred = np.array([20.5, 21.0, 21.5])
        T_meas = np.array([20.0, 21.0, 22.0])
        report = RoomReport(
            room_name="office",
            params=simple_id_result.params,
            identification=simple_id_result,
            cross_validation=simple_cv_result,
            rmse_threshold=0.5,
            passed=True,
            T_predicted=T_pred,
            T_measured=T_meas,
        )
        expected = np.array([0.5, 0.0, -0.5])
        np.testing.assert_allclose(report.residuals, expected)

    @pytest.mark.unit
    def test_empty_room_name_rejected(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """Empty room_name raises ValueError."""
        T = np.array([20.0])
        with pytest.raises(ValueError, match="room_name must be a non-empty"):
            RoomReport(
                room_name="",
                params=simple_id_result.params,
                identification=simple_id_result,
                cross_validation=simple_cv_result,
                rmse_threshold=0.5,
                passed=True,
                T_predicted=T,
                T_measured=T,
            )

    @pytest.mark.unit
    def test_non_positive_threshold_rejected(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """Non-positive rmse_threshold raises ValueError."""
        T = np.array([20.0])
        with pytest.raises(ValueError, match="rmse_threshold must be positive"):
            RoomReport(
                room_name="room",
                params=simple_id_result.params,
                identification=simple_id_result,
                cross_validation=simple_cv_result,
                rmse_threshold=0.0,
                passed=True,
                T_predicted=T,
                T_measured=T,
            )

    @pytest.mark.unit
    def test_shape_mismatch_rejected(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """Mismatched T_predicted/T_measured shapes raise ValueError."""
        with pytest.raises(ValueError, match="must match"):
            RoomReport(
                room_name="room",
                params=simple_id_result.params,
                identification=simple_id_result,
                cross_validation=simple_cv_result,
                rmse_threshold=0.5,
                passed=True,
                T_predicted=np.array([20.0, 21.0]),
                T_measured=np.array([20.0]),
            )

    @pytest.mark.unit
    def test_2d_array_rejected(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """2D T_predicted raises ValueError."""
        with pytest.raises(ValueError, match="T_predicted must be 1D"):
            RoomReport(
                room_name="room",
                params=simple_id_result.params,
                identification=simple_id_result,
                cross_validation=simple_cv_result,
                rmse_threshold=0.5,
                passed=True,
                T_predicted=np.array([[20.0]]),
                T_measured=np.array([20.0]),
            )


# ---------------------------------------------------------------------------
# TestIdentificationReport
# ---------------------------------------------------------------------------


class TestIdentificationReport:
    """Tests for the IdentificationReport frozen dataclass."""

    @pytest.mark.unit
    def test_construction_valid(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """Valid IdentificationReport can be constructed."""
        room = RoomReport(
            room_name="living_room",
            params=simple_id_result.params,
            identification=simple_id_result,
            cross_validation=simple_cv_result,
            rmse_threshold=0.5,
            passed=True,
            T_predicted=np.array([20.0]),
            T_measured=np.array([20.0]),
        )
        report = IdentificationReport(
            rooms=(room,),
            created_at="2026-04-07T12:00:00+00:00",
        )
        assert len(report.rooms) == 1
        assert report.rooms[0].room_name == "living_room"

    @pytest.mark.unit
    def test_empty_rooms_rejected(self) -> None:
        """Empty rooms tuple raises ValueError."""
        with pytest.raises(ValueError, match="must contain at least one room"):
            IdentificationReport(
                rooms=(),
                created_at="2026-04-07T12:00:00+00:00",
            )

    @pytest.mark.unit
    def test_all_passed_true(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """all_passed is True when all rooms pass."""
        room = RoomReport(
            room_name="room_a",
            params=simple_id_result.params,
            identification=simple_id_result,
            cross_validation=simple_cv_result,
            rmse_threshold=0.5,
            passed=True,
            T_predicted=np.array([20.0]),
            T_measured=np.array([20.0]),
        )
        report = IdentificationReport(
            rooms=(room,),
            created_at="2026-04-07T12:00:00+00:00",
        )
        assert report.all_passed is True
        assert report.failed_rooms == ()

    @pytest.mark.unit
    def test_all_passed_false(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """all_passed is False when at least one room fails."""
        passing = RoomReport(
            room_name="room_a",
            params=simple_id_result.params,
            identification=simple_id_result,
            cross_validation=simple_cv_result,
            rmse_threshold=0.5,
            passed=True,
            T_predicted=np.array([20.0]),
            T_measured=np.array([20.0]),
        )
        failing = RoomReport(
            room_name="room_b",
            params=simple_id_result.params,
            identification=simple_id_result,
            cross_validation=simple_cv_result,
            rmse_threshold=0.5,
            passed=False,
            T_predicted=np.array([20.0]),
            T_measured=np.array([20.0]),
        )
        report = IdentificationReport(
            rooms=(passing, failing),
            created_at="2026-04-07T12:00:00+00:00",
        )
        assert report.all_passed is False
        assert report.failed_rooms == ("room_b",)

    @pytest.mark.unit
    def test_frozen(
        self,
        simple_id_result: IdentificationResult,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """IdentificationReport is immutable."""
        room = RoomReport(
            room_name="room",
            params=simple_id_result.params,
            identification=simple_id_result,
            cross_validation=simple_cv_result,
            rmse_threshold=0.5,
            passed=True,
            T_predicted=np.array([20.0]),
            T_measured=np.array([20.0]),
        )
        report = IdentificationReport(
            rooms=(room,),
            created_at="2026-04-07T12:00:00+00:00",
        )
        with pytest.raises(AttributeError):
            report.created_at = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestIdentificationReportFromCvResults
# ---------------------------------------------------------------------------


class TestIdentificationReportFromCvResults:
    """Tests for IdentificationReport.from_cv_results factory."""

    @pytest.mark.unit
    def test_from_cv_results_single_room(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """from_cv_results produces a valid report from one room."""
        _, u, d, T = cv_synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)
        cv_results = {"living_room": cv_result}
        data = {"living_room": (u, d, T)}

        report = IdentificationReport.from_cv_results(cv_results, data)

        assert len(report.rooms) == 1
        room = report.rooms[0]
        assert room.room_name == "living_room"
        assert room.params == cv_result.identification.params
        assert len(room.T_predicted) == cv_result.test_size
        assert len(room.T_measured) == cv_result.test_size

    @pytest.mark.unit
    def test_from_cv_results_pass_fail(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Rooms pass/fail based on RMSE vs threshold."""
        _, u, d, T = cv_synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)
        cv_results = {"room": cv_result}
        data = {"room": (u, d, T)}

        # Very generous threshold: should pass
        report = IdentificationReport.from_cv_results(
            cv_results, data, rmse_threshold=10.0
        )
        assert report.rooms[0].passed is True
        assert report.all_passed is True

    @pytest.mark.unit
    def test_from_cv_results_room_mismatch_rejected(
        self,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """Mismatched room names between cv_results and data raise ValueError."""
        cv_results = {"room_a": simple_cv_result}
        data = {"room_b": (np.zeros((150, 1)), np.zeros((150, 2)), np.zeros(150))}

        with pytest.raises(ValueError, match="Room name mismatch"):
            IdentificationReport.from_cv_results(cv_results, data)

    @pytest.mark.unit
    def test_from_cv_results_empty_rejected(self) -> None:
        """Empty cv_results raises ValueError."""
        with pytest.raises(ValueError, match="cv_results must not be empty"):
            IdentificationReport.from_cv_results({}, {})

    @pytest.mark.unit
    def test_from_cv_results_non_positive_threshold_rejected(
        self,
        simple_cv_result: CrossValidationResult,
    ) -> None:
        """Non-positive rmse_threshold raises ValueError."""
        cv_results = {"room": simple_cv_result}
        data = {"room": (np.zeros((150, 1)), np.zeros((150, 2)), np.zeros(150))}
        with pytest.raises(ValueError, match="rmse_threshold must be positive"):
            IdentificationReport.from_cv_results(cv_results, data, rmse_threshold=0.0)

    @pytest.mark.unit
    def test_from_cv_results_iso_timestamp(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Report created_at is a valid ISO 8601 timestamp."""
        from datetime import datetime

        _, u, d, T = cv_synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)
        cv_results = {"room": cv_result}
        data = {"room": (u, d, T)}

        report = IdentificationReport.from_cv_results(cv_results, data)

        # Should not raise
        datetime.fromisoformat(report.created_at)


# ---------------------------------------------------------------------------
# TestQualityMonitor
# ---------------------------------------------------------------------------


class TestQualityMonitor:
    """Tests for QualityMonitor auto-reidentification logic."""

    @pytest.mark.unit
    def test_construction_default_threshold(self) -> None:
        """QualityMonitor defaults to DEFAULT_RMSE_REIDENTIFICATION_THRESHOLD."""
        monitor = QualityMonitor()
        assert monitor.threshold == DEFAULT_RMSE_REIDENTIFICATION_THRESHOLD

    @pytest.mark.unit
    def test_construction_custom_threshold(self) -> None:
        """QualityMonitor accepts custom threshold."""
        monitor = QualityMonitor(rmse_threshold=1.0)
        assert monitor.threshold == 1.0

    @pytest.mark.unit
    def test_non_positive_threshold_rejected(self) -> None:
        """Non-positive threshold raises ValueError."""
        with pytest.raises(ValueError, match="rmse_threshold must be positive"):
            QualityMonitor(rmse_threshold=0.0)
        with pytest.raises(ValueError, match="rmse_threshold must be positive"):
            QualityMonitor(rmse_threshold=-0.1)

    @pytest.mark.unit
    def test_unknown_room_no_reidentification(self) -> None:
        """Unknown room does not need reidentification."""
        monitor = QualityMonitor()
        assert monitor.needs_reidentification("unknown_room") is False

    @pytest.mark.unit
    def test_empty_history_no_reidentification(self) -> None:
        """Room with no history does not need reidentification."""
        monitor = QualityMonitor()
        assert monitor.get_history("room") == []
        assert monitor.needs_reidentification("room") is False

    @pytest.mark.unit
    def test_update_and_check_below_threshold(self) -> None:
        """RMSE below threshold: no reidentification needed."""
        monitor = QualityMonitor(rmse_threshold=0.5)
        monitor.update("room", 0.3)
        assert monitor.needs_reidentification("room") is False

    @pytest.mark.unit
    def test_update_and_check_above_threshold(self) -> None:
        """RMSE above threshold: reidentification needed."""
        monitor = QualityMonitor(rmse_threshold=0.5)
        monitor.update("room", 0.6)
        assert monitor.needs_reidentification("room") is True

    @pytest.mark.unit
    def test_update_and_check_at_threshold(self) -> None:
        """RMSE exactly at threshold: no reidentification (uses > not >=)."""
        monitor = QualityMonitor(rmse_threshold=0.5)
        monitor.update("room", 0.5)
        assert monitor.needs_reidentification("room") is False

    @pytest.mark.unit
    def test_history_tracks_updates(self) -> None:
        """get_history returns all updates in order."""
        monitor = QualityMonitor()
        monitor.update("room", 0.1)
        monitor.update("room", 0.2)
        monitor.update("room", 0.3)
        assert monitor.get_history("room") == [0.1, 0.2, 0.3]

    @pytest.mark.unit
    def test_history_returns_copy(self) -> None:
        """get_history returns a copy, not the internal list."""
        monitor = QualityMonitor()
        monitor.update("room", 0.1)
        history = monitor.get_history("room")
        history.append(999.0)
        assert monitor.get_history("room") == [0.1]

    @pytest.mark.unit
    def test_reset_clears_history(self) -> None:
        """reset clears the room's history."""
        monitor = QualityMonitor()
        monitor.update("room", 0.6)
        assert monitor.needs_reidentification("room") is True
        monitor.reset("room")
        assert monitor.needs_reidentification("room") is False
        assert monitor.get_history("room") == []

    @pytest.mark.unit
    def test_reset_unknown_room_no_error(self) -> None:
        """Resetting an unknown room does not raise."""
        monitor = QualityMonitor()
        monitor.reset("nonexistent")  # should not raise

    @pytest.mark.unit
    def test_negative_rmse_rejected(self) -> None:
        """Negative current_rmse raises ValueError."""
        monitor = QualityMonitor()
        with pytest.raises(ValueError, match="current_rmse must be non-negative"):
            monitor.update("room", -0.1)

    @pytest.mark.unit
    def test_latest_rmse_determines_reidentification(self) -> None:
        """Only the latest RMSE determines needs_reidentification."""
        monitor = QualityMonitor(rmse_threshold=0.5)
        monitor.update("room", 0.6)  # above
        assert monitor.needs_reidentification("room") is True
        monitor.update("room", 0.3)  # below
        assert monitor.needs_reidentification("room") is False
        monitor.update("room", 0.7)  # above again
        assert monitor.needs_reidentification("room") is True

    @pytest.mark.unit
    def test_multiple_rooms_independent(self) -> None:
        """Each room has independent RMSE tracking."""
        monitor = QualityMonitor(rmse_threshold=0.5)
        monitor.update("room_a", 0.6)
        monitor.update("room_b", 0.3)
        assert monitor.needs_reidentification("room_a") is True
        assert monitor.needs_reidentification("room_b") is False


# ---------------------------------------------------------------------------
# TestPlotPredictedVsMeasured
# ---------------------------------------------------------------------------


class TestPlotPredictedVsMeasured:
    """Tests for the plot_predicted_vs_measured function."""

    @pytest.mark.unit
    def test_returns_figure(self) -> None:
        """Function returns a matplotlib Figure."""
        import matplotlib.figure

        T_pred = np.array([20.0, 20.5, 21.0, 21.5])
        T_meas = np.array([20.1, 20.4, 20.9, 21.6])
        fig = plot_predicted_vs_measured(T_pred, T_meas)
        assert isinstance(fig, matplotlib.figure.Figure)

    @pytest.mark.unit
    def test_with_room_name(self) -> None:
        """Room name appears in figure title."""
        T = np.array([20.0, 21.0, 22.0])
        fig = plot_predicted_vs_measured(T, T, room_name="kitchen")
        ax = fig.axes[0]
        assert "kitchen" in ax.get_title()

    @pytest.mark.unit
    def test_with_custom_title(self) -> None:
        """Custom title overrides auto-generated title."""
        T = np.array([20.0, 21.0, 22.0])
        fig = plot_predicted_vs_measured(
            T, T, room_name="kitchen", title="Custom Title"
        )
        ax = fig.axes[0]
        assert ax.get_title() == "Custom Title"

    @pytest.mark.unit
    def test_save_to_file(self, tmp_path: Path) -> None:
        """Figure can be saved as PNG."""
        T = np.array([20.0, 21.0, 22.0])
        save_path = tmp_path / "pred_vs_meas.png"
        fig = plot_predicted_vs_measured(T, T, save_path=save_path)
        assert save_path.exists()
        assert save_path.stat().st_size > 0
        # Clean up
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_shape_mismatch_rejected(self) -> None:
        """Mismatched shapes raise ValueError."""
        with pytest.raises(ValueError, match="must match"):
            plot_predicted_vs_measured(
                np.array([20.0, 21.0]),
                np.array([20.0]),
            )

    @pytest.mark.unit
    def test_empty_arrays_rejected(self) -> None:
        """Empty arrays raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            plot_predicted_vs_measured(
                np.array([]),
                np.array([]),
            )


# ---------------------------------------------------------------------------
# TestPlotResiduals
# ---------------------------------------------------------------------------


class TestPlotResiduals:
    """Tests for the plot_residuals function."""

    @pytest.mark.unit
    def test_returns_figure(self) -> None:
        """Function returns a matplotlib Figure."""
        import matplotlib.figure

        T_pred = np.array([20.0, 20.5, 21.0])
        T_meas = np.array([20.1, 20.4, 20.9])
        fig = plot_residuals(T_pred, T_meas)
        assert isinstance(fig, matplotlib.figure.Figure)

    @pytest.mark.unit
    def test_with_room_name(self) -> None:
        """Room name appears in figure title."""
        T = np.array([20.0, 21.0, 22.0])
        fig = plot_residuals(T, T, room_name="bathroom")
        ax = fig.axes[0]
        assert "bathroom" in ax.get_title()

    @pytest.mark.unit
    def test_save_to_file(self, tmp_path: Path) -> None:
        """Figure can be saved as PNG."""
        T = np.array([20.0, 21.0, 22.0])
        save_path = tmp_path / "residuals.png"
        fig = plot_residuals(T, T, save_path=save_path)
        assert save_path.exists()
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_shape_mismatch_rejected(self) -> None:
        """Mismatched shapes raise ValueError."""
        with pytest.raises(ValueError, match="must match"):
            plot_residuals(np.array([20.0, 21.0]), np.array([20.0]))

    @pytest.mark.unit
    def test_empty_arrays_rejected(self) -> None:
        """Empty arrays raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            plot_residuals(np.array([]), np.array([]))


# ---------------------------------------------------------------------------
# TestPlotRmseOverTime
# ---------------------------------------------------------------------------


class TestPlotRmseOverTime:
    """Tests for the plot_rmse_over_time function."""

    @pytest.mark.unit
    def test_returns_figure(self) -> None:
        """Function returns a matplotlib Figure."""
        import matplotlib.figure

        fig = plot_rmse_over_time([0.1, 0.2, 0.3])
        assert isinstance(fig, matplotlib.figure.Figure)

    @pytest.mark.unit
    def test_with_threshold_line(self) -> None:
        """Threshold line is drawn when provided."""
        fig = plot_rmse_over_time([0.1, 0.2, 0.3], threshold=0.5)
        ax = fig.axes[0]
        # Should have at least 2 lines: data + threshold
        assert len(ax.lines) >= 2

    @pytest.mark.unit
    def test_with_room_name(self) -> None:
        """Room name appears in the title."""
        fig = plot_rmse_over_time([0.1], room_name="bedroom")
        ax = fig.axes[0]
        assert "bedroom" in ax.get_title()

    @pytest.mark.unit
    def test_save_to_file(self, tmp_path: Path) -> None:
        """Figure can be saved as PNG."""
        save_path = tmp_path / "rmse_trend.png"
        fig = plot_rmse_over_time([0.1, 0.2], save_path=save_path)
        assert save_path.exists()
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_empty_history_rejected(self) -> None:
        """Empty rmse_history raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            plot_rmse_over_time([])

    @pytest.mark.unit
    def test_single_point(self) -> None:
        """Single-point history does not error."""
        import matplotlib.figure

        fig = plot_rmse_over_time([0.5])
        assert isinstance(fig, matplotlib.figure.Figure)
