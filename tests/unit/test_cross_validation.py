"""Unit tests for pumpahead.cross_validation."""

from __future__ import annotations

import numpy as np
import pytest

from pumpahead.cross_validation import (
    DEFAULT_HORIZONS,
    DEFAULT_OVERFITTING_THRESHOLD,
    CrossValidationResult,
    HorizonRMSE,
    cross_validate,
    cross_validate_rooms,
)
from pumpahead.identifier import IdentificationResult, RCIdentifier
from pumpahead.model import ModelOrder, RCModel, RCParams

# ---------------------------------------------------------------------------
# Shared informed bounds (same as test_identifier.py)
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
def cv_synth_data_2r2c(
    params_2r2c: RCParams,
    model_2r2c: RCModel,
) -> tuple[RCParams, np.ndarray, np.ndarray, np.ndarray]:
    """Synthetic 2R2C data for cross-validation: 4 days at dt=60s.

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
    """2R2C identifier with informed bounds and 20 starts."""
    return RCIdentifier(
        ModelOrder.TWO,
        dt=60.0,
        n_starts=20,
        seed=42,
        bounds=_INFORMED_BOUNDS_2R2C,
    )


# ---------------------------------------------------------------------------
# TestHorizonRMSE
# ---------------------------------------------------------------------------


class TestHorizonRMSE:
    """Tests for the HorizonRMSE frozen dataclass."""

    @pytest.mark.unit
    def test_construction_valid(self) -> None:
        """Valid HorizonRMSE can be constructed."""
        h = HorizonRMSE(
            horizon_hours=6.0,
            train_rmse=0.1,
            test_rmse=0.2,
            overfitting_ratio=2.0,
        )
        assert h.horizon_hours == 6.0
        assert h.train_rmse == 0.1
        assert h.test_rmse == 0.2
        assert h.overfitting_ratio == 2.0

    @pytest.mark.unit
    def test_construction_with_none_test_rmse(self) -> None:
        """HorizonRMSE with None test_rmse (horizon exceeds test set)."""
        h = HorizonRMSE(
            horizon_hours=24.0,
            train_rmse=0.1,
            test_rmse=None,
            overfitting_ratio=None,
        )
        assert h.test_rmse is None
        assert h.overfitting_ratio is None

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """HorizonRMSE is immutable."""
        h = HorizonRMSE(
            horizon_hours=6.0,
            train_rmse=0.1,
            test_rmse=0.2,
            overfitting_ratio=2.0,
        )
        with pytest.raises(AttributeError):
            h.train_rmse = 0.5  # type: ignore[misc]

    @pytest.mark.unit
    def test_negative_horizon_rejected(self) -> None:
        """Negative horizon_hours raises ValueError."""
        with pytest.raises(ValueError, match="horizon_hours must be positive"):
            HorizonRMSE(
                horizon_hours=-1.0,
                train_rmse=0.1,
                test_rmse=0.2,
                overfitting_ratio=2.0,
            )

    @pytest.mark.unit
    def test_zero_horizon_rejected(self) -> None:
        """Zero horizon_hours raises ValueError."""
        with pytest.raises(ValueError, match="horizon_hours must be positive"):
            HorizonRMSE(
                horizon_hours=0.0,
                train_rmse=0.1,
                test_rmse=0.2,
                overfitting_ratio=2.0,
            )

    @pytest.mark.unit
    def test_negative_train_rmse_rejected(self) -> None:
        """Negative train_rmse raises ValueError."""
        with pytest.raises(ValueError, match="train_rmse must be non-negative"):
            HorizonRMSE(
                horizon_hours=6.0,
                train_rmse=-0.1,
                test_rmse=0.2,
                overfitting_ratio=2.0,
            )

    @pytest.mark.unit
    def test_negative_test_rmse_rejected(self) -> None:
        """Negative test_rmse raises ValueError."""
        with pytest.raises(ValueError, match="test_rmse must be non-negative"):
            HorizonRMSE(
                horizon_hours=6.0,
                train_rmse=0.1,
                test_rmse=-0.2,
                overfitting_ratio=None,
            )


# ---------------------------------------------------------------------------
# TestCrossValidationResult
# ---------------------------------------------------------------------------


class TestCrossValidationResult:
    """Tests for the CrossValidationResult frozen dataclass."""

    @pytest.mark.unit
    def test_construction_valid(self, params_2r2c: RCParams) -> None:
        """Valid CrossValidationResult can be constructed."""
        id_result = IdentificationResult(
            params=params_2r2c,
            cost=0.01,
            n_starts=5,
            converged=True,
            all_costs=(0.01, 0.02, 0.03, 0.04, 0.05),
        )
        horizon = HorizonRMSE(
            horizon_hours=6.0,
            train_rmse=0.1,
            test_rmse=0.2,
            overfitting_ratio=2.0,
        )
        result = CrossValidationResult(
            identification=id_result,
            horizons=(horizon,),
            train_rmse=0.1,
            test_rmse=0.2,
            overfitting_ratio=2.0,
            is_overfitting=True,
            train_size=100,
            test_size=50,
        )
        assert result.train_rmse == 0.1
        assert result.test_rmse == 0.2
        assert result.is_overfitting is True
        assert result.train_size == 100
        assert result.test_size == 50

    @pytest.mark.unit
    def test_frozen(self, params_2r2c: RCParams) -> None:
        """CrossValidationResult is immutable."""
        id_result = IdentificationResult(
            params=params_2r2c,
            cost=0.01,
            n_starts=1,
            converged=True,
            all_costs=(0.01,),
        )
        result = CrossValidationResult(
            identification=id_result,
            horizons=(),
            train_rmse=0.1,
            test_rmse=0.2,
            overfitting_ratio=2.0,
            is_overfitting=True,
            train_size=100,
            test_size=50,
        )
        with pytest.raises(AttributeError):
            result.train_rmse = 0.5  # type: ignore[misc]

    @pytest.mark.unit
    def test_negative_train_rmse_rejected(self, params_2r2c: RCParams) -> None:
        """Negative train_rmse raises ValueError."""
        id_result = IdentificationResult(
            params=params_2r2c,
            cost=0.01,
            n_starts=1,
            converged=True,
            all_costs=(0.01,),
        )
        with pytest.raises(ValueError, match="train_rmse must be non-negative"):
            CrossValidationResult(
                identification=id_result,
                horizons=(),
                train_rmse=-0.1,
                test_rmse=0.2,
                overfitting_ratio=None,
                is_overfitting=False,
                train_size=100,
                test_size=50,
            )

    @pytest.mark.unit
    def test_zero_train_size_rejected(self, params_2r2c: RCParams) -> None:
        """train_size < 1 raises ValueError."""
        id_result = IdentificationResult(
            params=params_2r2c,
            cost=0.01,
            n_starts=1,
            converged=True,
            all_costs=(0.01,),
        )
        with pytest.raises(ValueError, match="train_size must be >= 1"):
            CrossValidationResult(
                identification=id_result,
                horizons=(),
                train_rmse=0.1,
                test_rmse=0.2,
                overfitting_ratio=None,
                is_overfitting=False,
                train_size=0,
                test_size=50,
            )


# ---------------------------------------------------------------------------
# TestCrossValidateInputValidation
# ---------------------------------------------------------------------------


class TestCrossValidateInputValidation:
    """Tests for cross_validate input validation."""

    @pytest.mark.unit
    def test_train_ratio_zero_rejected(self) -> None:
        """train_ratio = 0 raises ValueError."""
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1)
        u = np.zeros((100, 1))
        d = np.zeros((100, 2))
        T = np.full(100, 20.0)
        with pytest.raises(ValueError, match="train_ratio must be in"):
            cross_validate(ident, u, d, T, train_ratio=0.0)

    @pytest.mark.unit
    def test_train_ratio_one_rejected(self) -> None:
        """train_ratio = 1.0 raises ValueError."""
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1)
        u = np.zeros((100, 1))
        d = np.zeros((100, 2))
        T = np.full(100, 20.0)
        with pytest.raises(ValueError, match="train_ratio must be in"):
            cross_validate(ident, u, d, T, train_ratio=1.0)

    @pytest.mark.unit
    def test_train_ratio_negative_rejected(self) -> None:
        """train_ratio < 0 raises ValueError."""
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1)
        u = np.zeros((100, 1))
        d = np.zeros((100, 2))
        T = np.full(100, 20.0)
        with pytest.raises(ValueError, match="train_ratio must be in"):
            cross_validate(ident, u, d, T, train_ratio=-0.5)

    @pytest.mark.unit
    def test_mismatched_lengths_rejected(self) -> None:
        """Mismatched sequence lengths raise ValueError."""
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1)
        u = np.zeros((100, 1))
        d = np.zeros((50, 2))
        T = np.full(100, 20.0)
        with pytest.raises(ValueError, match="Sequence lengths must match"):
            cross_validate(ident, u, d, T)


# ---------------------------------------------------------------------------
# TestCrossValidate2R2C — core cross-validation tests
# ---------------------------------------------------------------------------


class TestCrossValidate2R2C:
    """Core cross-validation tests using 2R2C synthetic data."""

    @pytest.mark.unit
    def test_produces_valid_result(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """cross_validate produces a valid CrossValidationResult."""
        _, u, d, T = cv_synth_data_2r2c
        result = cross_validate(identifier_2r2c, u, d, T)

        assert isinstance(result, CrossValidationResult)
        assert isinstance(result.identification, IdentificationResult)
        assert result.train_size > 0
        assert result.test_size > 0
        assert result.train_size + result.test_size == len(T)

    @pytest.mark.unit
    def test_train_rmse_near_zero_on_noiseless_data(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Training RMSE is near zero on noiseless synthetic data."""
        _, u, d, T = cv_synth_data_2r2c
        result = cross_validate(identifier_2r2c, u, d, T)
        assert result.train_rmse < 0.1  # < 0.1 degC

    @pytest.mark.unit
    def test_test_rmse_below_0_5_at_12h(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Test RMSE at 12h horizon is below 0.5 degC (acceptance criterion)."""
        _, u, d, T = cv_synth_data_2r2c
        result = cross_validate(identifier_2r2c, u, d, T)

        # Find the 12h horizon
        h12 = next(h for h in result.horizons if h.horizon_hours == 12.0)
        assert h12.test_rmse is not None
        assert h12.test_rmse < 0.5

    @pytest.mark.unit
    def test_no_overfitting_on_synthetic_data(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """No overfitting detected on well-conditioned synthetic data."""
        _, u, d, T = cv_synth_data_2r2c
        result = cross_validate(identifier_2r2c, u, d, T)
        assert result.is_overfitting is False

    @pytest.mark.unit
    def test_horizons_6h_12h_24h_present(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Default horizons (6h, 12h, 24h) are all present in the result."""
        _, u, d, T = cv_synth_data_2r2c
        result = cross_validate(identifier_2r2c, u, d, T)

        horizon_hours = [h.horizon_hours for h in result.horizons]
        assert horizon_hours == [6.0, 12.0, 24.0]

    @pytest.mark.unit
    def test_deterministic_with_same_seed(
        self,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Two runs with the same seed produce identical results."""
        _, u, d, T = cv_synth_data_2r2c
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
            seed=42,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        r1 = cross_validate(ident1, u, d, T)
        r2 = cross_validate(ident2, u, d, T)

        assert r1.train_rmse == pytest.approx(r2.train_rmse)
        assert r1.test_rmse == pytest.approx(r2.test_rmse)
        assert r1.identification.cost == pytest.approx(r2.identification.cost)

    @pytest.mark.unit
    def test_custom_train_ratio(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Custom train_ratio produces the expected split sizes."""
        _, u, d, T = cv_synth_data_2r2c
        n = len(T)
        result = cross_validate(identifier_2r2c, u, d, T, train_ratio=0.8)

        expected_train = int(n * 0.8)
        assert result.train_size == expected_train
        assert result.test_size == n - expected_train

    @pytest.mark.unit
    def test_custom_horizons(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Custom horizons are reflected in the result."""
        _, u, d, T = cv_synth_data_2r2c
        custom_horizons = (3.0, 9.0)
        result = cross_validate(
            identifier_2r2c, u, d, T, horizons_hours=custom_horizons
        )

        horizon_hours = [h.horizon_hours for h in result.horizons]
        assert horizon_hours == [3.0, 9.0]


# ---------------------------------------------------------------------------
# TestCrossValidateOverfitting
# ---------------------------------------------------------------------------


class TestCrossValidateOverfitting:
    """Tests for overfitting detection threshold."""

    @pytest.mark.unit
    def test_overfitting_flag_respects_threshold(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Overfitting flag is False when ratio is within threshold."""
        _, u, d, T = cv_synth_data_2r2c
        # Very high threshold ensures no overfitting
        result = cross_validate(identifier_2r2c, u, d, T, overfitting_threshold=100.0)
        assert result.is_overfitting is False

    @pytest.mark.unit
    def test_overfitting_flag_triggers_on_low_threshold(
        self,
        identifier_2r2c: RCIdentifier,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """Overfitting flag is True when threshold is unrealistically low.

        Using threshold=0.0 guarantees any nonzero test/train ratio triggers.
        Even perfect noiseless data will show slight differences between
        train/test segments due to differing initial conditions.
        """
        _, u, d, T = cv_synth_data_2r2c
        result = cross_validate(identifier_2r2c, u, d, T, overfitting_threshold=0.0)
        # With threshold=0.0, any ratio > 0 triggers overfitting.
        # On noiseless data the ratio might be very close to 1.0 (or even below),
        # but it's > 0.0, so overfitting should be flagged unless train_rmse is 0.
        if result.overfitting_ratio is not None:
            assert result.is_overfitting is True
        # If train_rmse is exactly 0, ratio is None and is_overfitting is False

    @pytest.mark.unit
    def test_zero_train_rmse_no_overfitting(self, params_2r2c: RCParams) -> None:
        """When train_rmse is exactly 0, overfitting_ratio is None."""
        id_result = IdentificationResult(
            params=params_2r2c,
            cost=0.0,
            n_starts=1,
            converged=True,
            all_costs=(0.0,),
        )
        result = CrossValidationResult(
            identification=id_result,
            horizons=(),
            train_rmse=0.0,
            test_rmse=0.1,
            overfitting_ratio=None,
            is_overfitting=False,
            train_size=100,
            test_size=50,
        )
        assert result.overfitting_ratio is None
        assert result.is_overfitting is False


# ---------------------------------------------------------------------------
# TestCrossValidateHorizonEdgeCases
# ---------------------------------------------------------------------------


class TestCrossValidateHorizonEdgeCases:
    """Tests for horizon edge cases (test set shorter than horizon)."""

    @pytest.mark.unit
    def test_horizon_exceeding_test_set_is_none(
        self,
        params_2r2c: RCParams,
        model_2r2c: RCModel,
    ) -> None:
        """When test set is shorter than a horizon, test_rmse is None."""
        # 600 steps (10 hours) total, 70/30 split = 420 train / 180 test (3h)
        # So 6h, 12h, 24h horizons all exceed the test set
        n_steps = 600
        u_seq = np.zeros((n_steps, 1))
        for i in range(n_steps):
            block = (i // 60) % 2
            u_seq[i, 0] = 0.0 if block == 0 else 1500.0

        d_seq = np.zeros((n_steps, 2))
        d_seq[:, 0] = 5.0

        x0 = np.array([5.0, 5.0])
        traj = model_2r2c.predict(x0, u_seq, d_seq)
        T_room = traj[1:, 0]

        ident = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=5,
            seed=42,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        result = cross_validate(ident, u_seq, d_seq, T_room)

        # All default horizons (6h=360 steps, 12h=720 steps, 24h=1440 steps)
        # exceed the test set (180 steps = 3h)
        for h in result.horizons:
            assert h.test_rmse is None
            assert h.overfitting_ratio is None


# ---------------------------------------------------------------------------
# TestCrossValidateRooms
# ---------------------------------------------------------------------------


class TestCrossValidateRooms:
    """Tests for cross_validate_rooms multi-room wrapper."""

    @pytest.mark.unit
    def test_multi_room_results(
        self,
        cv_synth_data_2r2c: tuple[RCParams, np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        """cross_validate_rooms produces per-room results."""
        _, u, d, T = cv_synth_data_2r2c
        ident = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=5,
            seed=42,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        rooms = {
            "living_room": (ident, u, d, T),
        }
        results = cross_validate_rooms(rooms)
        assert "living_room" in results
        assert isinstance(results["living_room"], CrossValidationResult)

    @pytest.mark.unit
    def test_multi_room_independent_identifiers(
        self,
        params_2r2c: RCParams,
        model_2r2c: RCModel,
    ) -> None:
        """Each room uses its own identifier (independent seeds)."""
        # Generate data
        n_steps = 2880
        u_seq = np.zeros((n_steps, 1))
        for i in range(n_steps):
            block = (i // 240) % 2
            u_seq[i, 0] = 0.0 if block == 0 else 1500.0

        d_seq = np.zeros((n_steps, 2))
        d_seq[:, 0] = 5.0

        x0 = np.array([5.0, 5.0])
        traj = model_2r2c.predict(x0, u_seq, d_seq)
        T_room = traj[1:, 0]

        # Two identifiers with different seeds
        ident1 = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=3,
            seed=42,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        ident2 = RCIdentifier(
            ModelOrder.TWO,
            dt=60.0,
            n_starts=3,
            seed=99,
            bounds=_INFORMED_BOUNDS_2R2C,
        )
        rooms = {
            "room_a": (ident1, u_seq, d_seq, T_room),
            "room_b": (ident2, u_seq, d_seq, T_room),
        }
        results = cross_validate_rooms(rooms)
        assert len(results) == 2
        assert "room_a" in results
        assert "room_b" in results


# ---------------------------------------------------------------------------
# TestIdentifierNewProperties
# ---------------------------------------------------------------------------


class TestIdentifierNewProperties:
    """Tests for new read-only properties on RCIdentifier."""

    @pytest.mark.unit
    def test_order_property(self) -> None:
        """order property returns the model order."""
        ident = RCIdentifier(ModelOrder.TWO)
        assert ident.order == ModelOrder.TWO

        ident3 = RCIdentifier(ModelOrder.THREE, R_ins=0.01)
        assert ident3.order == ModelOrder.THREE

    @pytest.mark.unit
    def test_dt_property(self) -> None:
        """dt property returns the time step."""
        ident = RCIdentifier(ModelOrder.TWO, dt=30.0)
        assert ident.dt == 30.0

    @pytest.mark.unit
    def test_burnin_steps_property(self) -> None:
        """burnin_steps property returns the burn-in value."""
        ident = RCIdentifier(ModelOrder.TWO, burnin_steps=360)
        assert ident.burnin_steps == 360

    @pytest.mark.unit
    def test_burnin_steps_default_zero(self) -> None:
        """burnin_steps defaults to 0."""
        ident = RCIdentifier(ModelOrder.TWO)
        assert ident.burnin_steps == 0


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module-level constants."""

    @pytest.mark.unit
    def test_default_horizons(self) -> None:
        """DEFAULT_HORIZONS is (6.0, 12.0, 24.0)."""
        assert DEFAULT_HORIZONS == (6.0, 12.0, 24.0)

    @pytest.mark.unit
    def test_default_overfitting_threshold(self) -> None:
        """DEFAULT_OVERFITTING_THRESHOLD is 1.5."""
        assert DEFAULT_OVERFITTING_THRESHOLD == 1.5
