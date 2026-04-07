"""Integration tests for Epic #13 -- RC parameter identification verification gate.

Verifies end-to-end wiring between the three sub-issue modules:
    #35 RCIdentifier (identifier.py)
    #36 Cross-validation framework (cross_validation.py)
    #37 Reporting and visualization (identification_report.py)

Each test verifies that the output of one module flows correctly into
the next, covering the full pipeline from identification through
cross-validation, reporting, visualization, and quality monitoring.

All tests are deterministic, use synthetic 2R2C data with informed
bounds, and carry the ``@pytest.mark.unit`` marker.
"""

from __future__ import annotations

import inspect
from datetime import datetime

import numpy as np
import pytest

from pumpahead.cross_validation import (
    CrossValidationResult,
    cross_validate,
    cross_validate_rooms,
)
from pumpahead.identification_report import (
    IdentificationReport,
    QualityMonitor,
    plot_predicted_vs_measured,
    plot_residuals,
    plot_rmse_over_time,
)
from pumpahead.identifier import (
    DEFAULT_BOUNDS_2R2C,
    IdentificationResult,
    RCIdentifier,
)
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
def synth_data_2r2c(
    params_2r2c: RCParams,
    model_2r2c: RCModel,
) -> tuple[RCParams, np.ndarray, np.ndarray, np.ndarray]:
    """Synthetic 2R2C data for integration tests: 4 days at dt=60s.

    4 days (5760 steps) provides enough data for a 70/30 split where
    the test set (1728 steps = 28.8 hours) exceeds the 24h horizon.
    Cyclic heating in 4-hour blocks provides rich excitation.
    """
    n_steps = 5760  # 4 days
    u_seq = np.zeros((n_steps, 1))
    for i in range(n_steps):
        block = (i // 240) % 2  # 4-hour blocks
        u_seq[i, 0] = 0.0 if block == 0 else 1500.0

    d_seq = np.zeros((n_steps, 2))
    d_seq[:, 0] = 5.0  # constant T_out = 5 C

    x0 = np.array([5.0, 5.0])
    traj = model_2r2c.predict(x0, u_seq, d_seq)
    T_room = traj[1:, 0]

    return params_2r2c, u_seq, d_seq, T_room


@pytest.fixture()
def identifier_2r2c() -> RCIdentifier:
    """2R2C identifier with informed bounds and 10 starts (fast)."""
    return RCIdentifier(
        ModelOrder.TWO,
        dt=60.0,
        n_starts=10,
        seed=42,
        bounds=_INFORMED_BOUNDS_2R2C,
    )


# ---------------------------------------------------------------------------
# TestIdentifierToCrossValidationPipeline
# ---------------------------------------------------------------------------


class TestIdentifierToCrossValidationPipeline:
    """Tests that the output of RCIdentifier flows into cross_validate."""

    @pytest.mark.unit
    def test_identify_then_cross_validate_produces_valid_result(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """RCIdentifier.identify() -> cross_validate() produces valid result."""
        _, u, d, T = synth_data_2r2c
        result = cross_validate(identifier_2r2c, u, d, T)

        assert isinstance(result, CrossValidationResult)
        assert isinstance(result.identification, IdentificationResult)
        assert len(result.horizons) > 0
        assert result.train_rmse >= 0
        assert result.test_rmse >= 0
        assert result.train_size + result.test_size == len(T)

    @pytest.mark.unit
    def test_cross_validate_identification_matches_params_type(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """cv_result.identification.params is RCParams with 2R2C fields set."""
        _, u, d, T = synth_data_2r2c
        result = cross_validate(identifier_2r2c, u, d, T)

        params = result.identification.params
        assert isinstance(params, RCParams)
        assert params.R_sf is not None
        assert params.R_env is not None
        assert params.C_air is not None
        assert params.C_slab is not None

    @pytest.mark.unit
    def test_identified_model_can_predict(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Identified params produce a stable RCModel with finite predictions."""
        _, u, d, T = synth_data_2r2c
        result = cross_validate(identifier_2r2c, u, d, T)

        model = RCModel(result.identification.params, ModelOrder.TWO, dt=60.0)
        x0 = np.full(model.n_states, T[0])
        traj = model.predict(x0, u[:100], d[:100])

        assert traj.shape == (101, model.n_states)
        assert np.all(np.isfinite(traj))


# ---------------------------------------------------------------------------
# TestCrossValidationToReportPipeline
# ---------------------------------------------------------------------------


class TestCrossValidationToReportPipeline:
    """Tests the handoff from cross_validate to IdentificationReport."""

    @pytest.mark.unit
    def test_single_room_cv_to_report(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """cross_validate -> IdentificationReport.from_cv_results works."""
        _, u, d, T = synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)

        report = IdentificationReport.from_cv_results(
            {"room": cv_result},
            {"room": (u, d, T)},
        )

        assert len(report.rooms) == 1
        room = report.rooms[0]
        assert room.room_name == "room"
        assert room.params == cv_result.identification.params
        assert len(room.T_predicted) == cv_result.test_size
        assert len(room.T_measured) == cv_result.test_size
        assert room.T_predicted.shape == room.T_measured.shape

    @pytest.mark.unit
    def test_report_pass_fail_matches_cv_rmse(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Room report passed=True when test_rmse <= threshold (noiseless)."""
        _, u, d, T = synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)

        # On noiseless data, RMSE should be well below default threshold 0.5
        assert cv_result.test_rmse <= 0.5

        report = IdentificationReport.from_cv_results(
            {"room": cv_result},
            {"room": (u, d, T)},
        )
        assert report.rooms[0].passed is True

    @pytest.mark.unit
    def test_report_created_at_is_iso_timestamp(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Report created_at is a valid ISO 8601 timestamp."""
        _, u, d, T = synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)

        report = IdentificationReport.from_cv_results(
            {"room": cv_result},
            {"room": (u, d, T)},
        )

        # Should not raise
        parsed = datetime.fromisoformat(report.created_at)
        assert isinstance(parsed, datetime)


# ---------------------------------------------------------------------------
# TestMultiRoomEndToEndPipeline
# ---------------------------------------------------------------------------


class TestMultiRoomEndToEndPipeline:
    """Tests multi-room flow through cross_validate_rooms -> report."""

    @pytest.mark.unit
    def test_two_rooms_cv_to_report(
        self,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Two rooms: cross_validate_rooms -> IdentificationReport works."""
        _, u, d, T = synth_data_2r2c

        ident1 = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=5,
            seed=42,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        ident2 = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=5,
            seed=99,
            bounds=_INFORMED_BOUNDS_2R2C,
        )

        rooms = {
            "living_room": (ident1, u, d, T),
            "bedroom": (ident2, u, d, T),
        }
        cv_results = cross_validate_rooms(rooms)

        data = {
            "living_room": (u, d, T),
            "bedroom": (u, d, T),
        }
        report = IdentificationReport.from_cv_results(cv_results, data)

        assert len(report.rooms) == 2
        room_names = {r.room_name for r in report.rooms}
        assert room_names == {"living_room", "bedroom"}

        for room in report.rooms:
            assert len(room.T_predicted) > 0
            assert len(room.T_measured) > 0
            assert room.T_predicted.shape == room.T_measured.shape

    @pytest.mark.unit
    def test_multi_room_report_all_passed(
        self,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """All rooms pass on noiseless synthetic data."""
        _, u, d, T = synth_data_2r2c

        ident1 = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=5,
            seed=42,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        ident2 = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=5,
            seed=99,
            bounds=_INFORMED_BOUNDS_2R2C,
        )

        rooms = {
            "room_a": (ident1, u, d, T),
            "room_b": (ident2, u, d, T),
        }
        cv_results = cross_validate_rooms(rooms)

        data = {
            "room_a": (u, d, T),
            "room_b": (u, d, T),
        }
        report = IdentificationReport.from_cv_results(cv_results, data)

        assert report.all_passed is True
        assert report.failed_rooms == ()


# ---------------------------------------------------------------------------
# TestReportToVisualizationPipeline
# ---------------------------------------------------------------------------


class TestReportToVisualizationPipeline:
    """Tests that report data feeds correctly into plot functions."""

    @pytest.mark.unit
    def test_room_report_feeds_plot_predicted_vs_measured(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """RoomReport T_predicted/T_measured feed plot_predicted_vs_measured."""
        import matplotlib.figure

        _, u, d, T = synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)
        report = IdentificationReport.from_cv_results(
            {"room": cv_result},
            {"room": (u, d, T)},
        )
        room = report.rooms[0]

        fig = plot_predicted_vs_measured(
            room.T_predicted,
            room.T_measured,
            room_name=room.room_name,
        )
        assert isinstance(fig, matplotlib.figure.Figure)

    @pytest.mark.unit
    def test_room_report_feeds_plot_residuals(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """RoomReport T_predicted/T_measured feed plot_residuals."""
        import matplotlib.figure

        _, u, d, T = synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)
        report = IdentificationReport.from_cv_results(
            {"room": cv_result},
            {"room": (u, d, T)},
        )
        room = report.rooms[0]

        fig = plot_residuals(
            room.T_predicted,
            room.T_measured,
            room_name=room.room_name,
        )
        assert isinstance(fig, matplotlib.figure.Figure)

    @pytest.mark.unit
    def test_quality_monitor_feeds_plot_rmse_over_time(self) -> None:
        """QualityMonitor history feeds plot_rmse_over_time."""
        import matplotlib.figure

        monitor = QualityMonitor(rmse_threshold=0.5)
        monitor.update("room", 0.1)
        monitor.update("room", 0.2)
        monitor.update("room", 0.3)

        history = monitor.get_history("room")
        fig = plot_rmse_over_time(
            history,
            threshold=monitor.threshold,
            room_name="room",
        )
        assert isinstance(fig, matplotlib.figure.Figure)


# ---------------------------------------------------------------------------
# TestQualityMonitorIntegration
# ---------------------------------------------------------------------------


class TestQualityMonitorIntegration:
    """Tests QualityMonitor with real CV results."""

    @pytest.mark.unit
    def test_monitor_detects_good_identification(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Good CV result: QualityMonitor does not flag reidentification."""
        _, u, d, T = synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)

        monitor = QualityMonitor(rmse_threshold=0.5)
        monitor.update("room", cv_result.test_rmse)

        assert monitor.needs_reidentification("room") is False

    @pytest.mark.unit
    def test_monitor_triggers_on_degraded_model(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """High RMSE triggers reidentification; reset clears the flag."""
        _, u, d, T = synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)

        monitor = QualityMonitor(rmse_threshold=0.5)

        # Simulate degraded model
        monitor.update("room", 0.8)
        assert monitor.needs_reidentification("room") is True

        # Simulate reset after reidentification
        monitor.reset("room")
        monitor.update("room", cv_result.test_rmse)
        assert monitor.needs_reidentification("room") is False


# ---------------------------------------------------------------------------
# TestAcceptanceCriteriaVerification
# ---------------------------------------------------------------------------


class TestAcceptanceCriteriaVerification:
    """Explicit verification of Epic #13 acceptance criteria."""

    @pytest.mark.unit
    def test_2r2c_identification_converges_on_synthetic_data(
        self,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """AC: 2R2C param recovery < 10% on known synthetic data.

        Uses 20 starts for robust convergence (this is the acceptance
        criterion test, not a wiring test).
        """
        true_params, u, d, T = synth_data_2r2c

        identifier = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=20,
            seed=42,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        result = identifier.identify(u, d, T)

        # Check each parameter is within 10% of the true value
        true_vals = {
            "R_sf": true_params.R_sf,
            "R_env": true_params.R_env,
            "C_air": true_params.C_air,
            "C_slab": true_params.C_slab,
        }
        identified_vals = {
            "R_sf": result.params.R_sf,
            "R_env": result.params.R_env,
            "C_air": result.params.C_air,
            "C_slab": result.params.C_slab,
        }

        for name in true_vals:
            true_val = true_vals[name]
            id_val = identified_vals[name]
            assert true_val is not None
            assert id_val is not None
            rel_error = abs(id_val - true_val) / true_val
            assert rel_error < 0.10, (
                f"{name}: relative error {rel_error:.4f} >= 10% "
                f"(true={true_val}, identified={id_val})"
            )

    @pytest.mark.unit
    def test_rmse_below_0_5_at_12h_horizon(
        self,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """AC: RMSE < 0.5 degC at 12h prediction horizon."""
        _, u, d, T = synth_data_2r2c

        identifier = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=20,
            seed=42,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        result = cross_validate(identifier, u, d, T)

        h12 = next(h for h in result.horizons if h.horizon_hours == 12.0)
        assert h12.test_rmse is not None
        assert h12.test_rmse < 0.5

    @pytest.mark.unit
    def test_box_constraints_prevent_nonphysical_values(
        self,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """AC: Box constraints keep params within physically sensible ranges.

        Uses default (wide) bounds and verifies all identified params
        fall within DEFAULT_BOUNDS_2R2C.
        """
        _, u, d, T = synth_data_2r2c

        identifier = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=10,
            seed=42,
            # Use default bounds (no informed bounds override)
        )
        result = identifier.identify(u, d, T)

        param_map = {
            "R_sf": result.params.R_sf,
            "R_env": result.params.R_env,
            "C_air": result.params.C_air,
            "C_slab": result.params.C_slab,
        }

        for name, value in param_map.items():
            assert value is not None
            lo, hi = DEFAULT_BOUNDS_2R2C[name]
            assert lo <= value <= hi, (
                f"{name}={value} outside bounds [{lo}, {hi}]"
            )

    @pytest.mark.unit
    def test_no_overfitting_on_cross_validation(
        self,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """AC: Cross-validation detects no overfitting on synthetic data."""
        _, u, d, T = synth_data_2r2c

        identifier = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=20,
            seed=42,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        result = cross_validate(identifier, u, d, T)

        assert result.is_overfitting is False

        # If overfitting_ratio is computed (train_rmse > 1e-3), verify <= 1.5
        if result.overfitting_ratio is not None:
            assert result.overfitting_ratio <= 1.5

    @pytest.mark.unit
    def test_report_produces_comparison_plots(
        self,
        identifier_2r2c: RCIdentifier,
        synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """AC: Report data produces valid comparison plot Figures."""
        import matplotlib.figure

        _, u, d, T = synth_data_2r2c
        cv_result = cross_validate(identifier_2r2c, u, d, T)
        report = IdentificationReport.from_cv_results(
            {"room": cv_result},
            {"room": (u, d, T)},
        )
        room = report.rooms[0]

        fig_pred = plot_predicted_vs_measured(
            room.T_predicted,
            room.T_measured,
            room_name=room.room_name,
        )
        fig_resid = plot_residuals(
            room.T_predicted,
            room.T_measured,
            room_name=room.room_name,
        )

        assert isinstance(fig_pred, matplotlib.figure.Figure)
        assert isinstance(fig_resid, matplotlib.figure.Figure)


# ---------------------------------------------------------------------------
# TestArchitecturalIntegrity
# ---------------------------------------------------------------------------


class TestArchitecturalIntegrity:
    """Verify DAG dependency direction and no architectural drift."""

    @pytest.mark.unit
    def test_identifier_does_not_import_cross_validation_or_report(
        self,
    ) -> None:
        """identifier.py only imports from model (no cross_validation, no report)."""
        import pumpahead.identifier as ident_mod

        source = inspect.getsource(ident_mod)

        assert "cross_validation" not in source, (
            "identifier.py must not import cross_validation"
        )
        assert "identification_report" not in source, (
            "identifier.py must not import identification_report"
        )

    @pytest.mark.unit
    def test_cross_validation_does_not_import_report(self) -> None:
        """cross_validation.py imports identifier and model, not report."""
        import pumpahead.cross_validation as cv_mod

        source = inspect.getsource(cv_mod)

        assert "identification_report" not in source, (
            "cross_validation.py must not import identification_report"
        )

    @pytest.mark.unit
    def test_identification_report_imports_cv_and_identifier(self) -> None:
        """identification_report.py imports from cross_validation, identifier, model."""
        import pumpahead.identification_report as report_mod

        source = inspect.getsource(report_mod)

        assert "cross_validation" in source, (
            "identification_report.py must import cross_validation"
        )
        assert "identifier" in source, (
            "identification_report.py must import identifier"
        )
        assert "model" in source, (
            "identification_report.py must import model"
        )

    @pytest.mark.unit
    def test_no_homeassistant_imports_in_core(self) -> None:
        """None of the three modules import homeassistant."""
        import pumpahead.cross_validation as cv_mod
        import pumpahead.identification_report as report_mod
        import pumpahead.identifier as ident_mod

        for mod_name, mod in [
            ("identifier", ident_mod),
            ("cross_validation", cv_mod),
            ("identification_report", report_mod),
        ]:
            source = inspect.getsource(mod)
            assert "homeassistant" not in source, (
                f"{mod_name} must not import homeassistant"
            )

    @pytest.mark.unit
    def test_all_public_symbols_exported_from_init(self) -> None:
        """All public symbols from the three modules are in pumpahead.__init__."""
        import pumpahead

        expected_symbols = [
            # From identifier.py
            "IdentificationResult",
            "RCIdentifier",
            # From cross_validation.py
            "cross_validate",
            "cross_validate_rooms",
            "CrossValidationResult",
            "HorizonRMSE",
            # From identification_report.py
            "IdentificationReport",
            "RoomReport",
            "QualityMonitor",
            "plot_predicted_vs_measured",
            "plot_residuals",
            "plot_rmse_over_time",
        ]

        for symbol in expected_symbols:
            assert hasattr(pumpahead, symbol), (
                f"{symbol} not exported from pumpahead.__init__"
            )
            assert symbol in pumpahead.__all__, (
                f"{symbol} not in pumpahead.__all__"
            )
