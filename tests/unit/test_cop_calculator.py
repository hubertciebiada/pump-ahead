"""Tests for the COP calculator module.

Tests the ``COPMode`` enum, ``COPSample`` dataclass, and ``COPCalculator``
class with all three resolution modes (CONSTANT, LOOKUP_TABLE, AUTO_LEARNED)
plus the ``from_config`` factory method.  No HA dependencies -- pure core
library testing.
"""

from __future__ import annotations

import numpy as np
import pytest

from pumpahead.cop_calculator import (
    COP_MAX,
    COP_MIN,
    DEFAULT_COP,
    DEFAULT_T_SUPPLY,
    MIN_SAMPLES_HOURS,
    COPCalculator,
    COPMode,
    COPSample,
)

# ---------------------------------------------------------------------------
# TestCOPMode
# ---------------------------------------------------------------------------


class TestCOPMode:
    """Verify enum members and their string values."""

    @pytest.mark.unit
    def test_enum_members_exist(self) -> None:
        """All expected enum members must be present."""
        assert COPMode.AUTO_LEARNED is not None
        assert COPMode.LOOKUP_TABLE is not None
        assert COPMode.CONSTANT is not None

    @pytest.mark.unit
    def test_enum_values(self) -> None:
        """Enum values must match expected strings."""
        assert COPMode.AUTO_LEARNED.value == "auto_learned"
        assert COPMode.LOOKUP_TABLE.value == "lookup_table"
        assert COPMode.CONSTANT.value == "constant"

    @pytest.mark.unit
    def test_enum_has_three_members(self) -> None:
        """Exactly three members must exist."""
        assert len(COPMode) == 3


# ---------------------------------------------------------------------------
# TestCOPSample
# ---------------------------------------------------------------------------


class TestCOPSample:
    """Verify the frozen COPSample dataclass and its validation."""

    @pytest.mark.unit
    def test_valid_sample(self) -> None:
        """A physically valid sample must be constructible."""
        sample = COPSample(
            t_outdoor=5.0,
            t_supply=35.0,
            p_electric=1000.0,
            q_thermal=3500.0,
            cop=3.5,
        )
        assert sample.t_outdoor == 5.0
        assert sample.t_supply == 35.0
        assert sample.p_electric == 1000.0
        assert sample.q_thermal == 3500.0
        assert sample.cop == 3.5

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """COPSample must be immutable (frozen dataclass)."""
        sample = COPSample(
            t_outdoor=5.0,
            t_supply=35.0,
            p_electric=1000.0,
            q_thermal=3500.0,
            cop=3.5,
        )
        with pytest.raises(AttributeError):
            sample.cop = 4.0  # type: ignore[misc]

    @pytest.mark.unit
    def test_rejects_zero_p_electric(self) -> None:
        """p_electric <= 0 must raise ValueError."""
        with pytest.raises(ValueError, match="p_electric must be positive"):
            COPSample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=0.0,
                q_thermal=3500.0,
                cop=3.5,
            )

    @pytest.mark.unit
    def test_rejects_negative_p_electric(self) -> None:
        """Negative p_electric must raise ValueError."""
        with pytest.raises(ValueError, match="p_electric must be positive"):
            COPSample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=-100.0,
                q_thermal=3500.0,
                cop=3.5,
            )

    @pytest.mark.unit
    def test_rejects_zero_q_thermal(self) -> None:
        """q_thermal <= 0 must raise ValueError."""
        with pytest.raises(ValueError, match="q_thermal must be positive"):
            COPSample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=1000.0,
                q_thermal=0.0,
                cop=3.5,
            )

    @pytest.mark.unit
    def test_rejects_negative_q_thermal(self) -> None:
        """Negative q_thermal must raise ValueError."""
        with pytest.raises(ValueError, match="q_thermal must be positive"):
            COPSample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=1000.0,
                q_thermal=-500.0,
                cop=3.5,
            )

    @pytest.mark.unit
    def test_rejects_cop_below_min(self) -> None:
        """COP below COP_MIN must raise ValueError."""
        with pytest.raises(ValueError, match="cop must be in"):
            COPSample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=1000.0,
                q_thermal=500.0,
                cop=0.5,
            )

    @pytest.mark.unit
    def test_rejects_cop_above_max(self) -> None:
        """COP above COP_MAX must raise ValueError."""
        with pytest.raises(ValueError, match="cop must be in"):
            COPSample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=1000.0,
                q_thermal=10000.0,
                cop=10.0,
            )

    @pytest.mark.unit
    def test_cop_at_boundaries(self) -> None:
        """COP at exact COP_MIN and COP_MAX must be accepted."""
        sample_min = COPSample(
            t_outdoor=5.0,
            t_supply=45.0,
            p_electric=1000.0,
            q_thermal=1000.0,
            cop=COP_MIN,
        )
        assert sample_min.cop == COP_MIN

        sample_max = COPSample(
            t_outdoor=15.0,
            t_supply=30.0,
            p_electric=1000.0,
            q_thermal=8000.0,
            cop=COP_MAX,
        )
        assert sample_max.cop == COP_MAX


# ---------------------------------------------------------------------------
# TestCOPCalculatorConstant
# ---------------------------------------------------------------------------


class TestCOPCalculatorConstant:
    """Tests for CONSTANT mode."""

    @pytest.mark.unit
    def test_default_cop_value(self) -> None:
        """Default constant COP should be DEFAULT_COP."""
        calc = COPCalculator(mode=COPMode.CONSTANT)
        assert calc.get_cop(t_outdoor=0.0) == DEFAULT_COP

    @pytest.mark.unit
    def test_custom_cop_value(self) -> None:
        """Custom constant COP should be returned."""
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=4.0)
        assert calc.get_cop(t_outdoor=-15.0) == 4.0
        assert calc.get_cop(t_outdoor=20.0) == 4.0

    @pytest.mark.unit
    def test_constant_mode_ignores_t_supply(self) -> None:
        """CONSTANT mode should return the same COP regardless of t_supply."""
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=3.0)
        assert calc.get_cop(t_outdoor=5.0, t_supply=30.0) == 3.0
        assert calc.get_cop(t_outdoor=5.0, t_supply=55.0) == 3.0

    @pytest.mark.unit
    def test_constant_mode_properties(self) -> None:
        """Verify properties for CONSTANT mode."""
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=3.5)
        assert calc.mode is COPMode.CONSTANT
        assert calc.is_fitted is False
        assert calc.n_samples == 0
        assert calc.default_cop == 3.5

    @pytest.mark.unit
    def test_constant_cop_clamped_below(self) -> None:
        """Default COP below COP_MIN is clamped to COP_MIN."""
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=0.5)
        assert calc.get_cop(t_outdoor=0.0) == COP_MIN

    @pytest.mark.unit
    def test_constant_cop_clamped_above(self) -> None:
        """Default COP above COP_MAX is clamped to COP_MAX."""
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=12.0)
        assert calc.get_cop(t_outdoor=0.0) == COP_MAX


# ---------------------------------------------------------------------------
# TestCOPCalculatorLookupTable
# ---------------------------------------------------------------------------


class TestCOPCalculatorLookupTable:
    """Tests for LOOKUP_TABLE mode."""

    @pytest.mark.unit
    def test_exact_breakpoint_match(self) -> None:
        """COP at exact breakpoint should return the table value."""
        calc = COPCalculator(
            mode=COPMode.LOOKUP_TABLE,
            lookup_t_outdoor=np.array([-15.0, 0.0, 15.0]),
            lookup_cop=np.array([2.5, 3.5, 5.0]),
        )
        assert calc.get_cop(t_outdoor=0.0) == pytest.approx(3.5)
        assert calc.get_cop(t_outdoor=-15.0) == pytest.approx(2.5)
        assert calc.get_cop(t_outdoor=15.0) == pytest.approx(5.0)

    @pytest.mark.unit
    def test_interpolation(self) -> None:
        """COP between breakpoints should be linearly interpolated."""
        calc = COPCalculator(
            mode=COPMode.LOOKUP_TABLE,
            lookup_t_outdoor=np.array([-10.0, 10.0]),
            lookup_cop=np.array([2.0, 4.0]),
        )
        # Midpoint: COP = 3.0
        assert calc.get_cop(t_outdoor=0.0) == pytest.approx(3.0)
        # Quarter: COP = 2.5
        assert calc.get_cop(t_outdoor=-5.0) == pytest.approx(2.5)

    @pytest.mark.unit
    def test_extrapolation_below(self) -> None:
        """COP below the lowest breakpoint should clamp to the first value."""
        calc = COPCalculator(
            mode=COPMode.LOOKUP_TABLE,
            lookup_t_outdoor=np.array([-10.0, 10.0]),
            lookup_cop=np.array([2.5, 4.5]),
        )
        assert calc.get_cop(t_outdoor=-30.0) == pytest.approx(2.5)

    @pytest.mark.unit
    def test_extrapolation_above(self) -> None:
        """COP above the highest breakpoint should clamp to the last value."""
        calc = COPCalculator(
            mode=COPMode.LOOKUP_TABLE,
            lookup_t_outdoor=np.array([-10.0, 10.0]),
            lookup_cop=np.array([2.5, 4.5]),
        )
        assert calc.get_cop(t_outdoor=40.0) == pytest.approx(4.5)

    @pytest.mark.unit
    def test_unsorted_input_is_sorted(self) -> None:
        """Lookup table entries provided in wrong order should be sorted."""
        calc = COPCalculator(
            mode=COPMode.LOOKUP_TABLE,
            lookup_t_outdoor=np.array([15.0, -15.0, 0.0]),
            lookup_cop=np.array([5.0, 2.5, 3.5]),
        )
        # After sorting: [-15, 0, 15] -> [2.5, 3.5, 5.0]
        assert calc.get_cop(t_outdoor=0.0) == pytest.approx(3.5)

    @pytest.mark.unit
    def test_lookup_mode_ignores_t_supply(self) -> None:
        """LOOKUP_TABLE mode only uses t_outdoor."""
        calc = COPCalculator(
            mode=COPMode.LOOKUP_TABLE,
            lookup_t_outdoor=np.array([0.0, 10.0]),
            lookup_cop=np.array([3.0, 4.0]),
        )
        assert calc.get_cop(t_outdoor=5.0, t_supply=30.0) == pytest.approx(
            3.5
        )
        assert calc.get_cop(t_outdoor=5.0, t_supply=55.0) == pytest.approx(
            3.5
        )

    @pytest.mark.unit
    def test_lookup_missing_arrays_raises(self) -> None:
        """Missing lookup arrays must raise ValueError."""
        with pytest.raises(ValueError, match="must be provided"):
            COPCalculator(mode=COPMode.LOOKUP_TABLE)

    @pytest.mark.unit
    def test_lookup_mismatched_lengths_raises(self) -> None:
        """Mismatched array lengths must raise ValueError."""
        with pytest.raises(ValueError, match="must match"):
            COPCalculator(
                mode=COPMode.LOOKUP_TABLE,
                lookup_t_outdoor=np.array([0.0, 10.0]),
                lookup_cop=np.array([3.0]),
            )

    @pytest.mark.unit
    def test_lookup_single_entry_raises(self) -> None:
        """Lookup table with fewer than 2 entries must raise ValueError."""
        with pytest.raises(ValueError, match="at least 2 entries"):
            COPCalculator(
                mode=COPMode.LOOKUP_TABLE,
                lookup_t_outdoor=np.array([0.0]),
                lookup_cop=np.array([3.0]),
            )

    @pytest.mark.unit
    def test_lookup_cop_clamped(self) -> None:
        """Interpolated COP values should be clamped to [COP_MIN, COP_MAX]."""
        # Lookup table values within range, but this tests the clamping path
        calc = COPCalculator(
            mode=COPMode.LOOKUP_TABLE,
            lookup_t_outdoor=np.array([0.0, 10.0]),
            lookup_cop=np.array([1.0, 8.0]),
        )
        # At boundaries
        assert calc.get_cop(t_outdoor=0.0) == pytest.approx(COP_MIN)
        assert calc.get_cop(t_outdoor=10.0) == pytest.approx(COP_MAX)

    @pytest.mark.unit
    def test_lookup_properties(self) -> None:
        """Verify properties for LOOKUP_TABLE mode."""
        calc = COPCalculator(
            mode=COPMode.LOOKUP_TABLE,
            lookup_t_outdoor=np.array([0.0, 10.0]),
            lookup_cop=np.array([3.0, 4.0]),
        )
        assert calc.mode is COPMode.LOOKUP_TABLE
        assert calc.is_fitted is False
        assert calc.n_samples == 0


# ---------------------------------------------------------------------------
# TestCOPCalculatorAutoLearned
# ---------------------------------------------------------------------------


class TestCOPCalculatorAutoLearned:
    """Tests for AUTO_LEARNED mode."""

    @pytest.mark.unit
    def test_unfitted_returns_default(self) -> None:
        """Unfitted auto-learned calculator must fall back to default COP."""
        calc = COPCalculator(mode=COPMode.AUTO_LEARNED)
        assert calc.get_cop(t_outdoor=5.0) == DEFAULT_COP

    @pytest.mark.unit
    def test_add_sample_valid(self) -> None:
        """Valid samples must be accepted."""
        calc = COPCalculator(mode=COPMode.AUTO_LEARNED)
        accepted = calc.add_sample(
            t_outdoor=5.0,
            t_supply=35.0,
            p_electric=1000.0,
            q_thermal=3500.0,
        )
        assert accepted is True
        assert calc.n_samples == 1

    @pytest.mark.unit
    def test_add_sample_rejects_zero_power(self) -> None:
        """Samples with p_electric=0 must be rejected."""
        calc = COPCalculator(mode=COPMode.AUTO_LEARNED)
        assert (
            calc.add_sample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=0.0,
                q_thermal=3500.0,
            )
            is False
        )
        assert calc.n_samples == 0

    @pytest.mark.unit
    def test_add_sample_rejects_negative_power(self) -> None:
        """Samples with negative p_electric must be rejected."""
        calc = COPCalculator(mode=COPMode.AUTO_LEARNED)
        assert (
            calc.add_sample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=-100.0,
                q_thermal=3500.0,
            )
            is False
        )
        assert calc.n_samples == 0

    @pytest.mark.unit
    def test_add_sample_rejects_zero_thermal(self) -> None:
        """Samples with q_thermal=0 must be rejected."""
        calc = COPCalculator(mode=COPMode.AUTO_LEARNED)
        assert (
            calc.add_sample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=1000.0,
                q_thermal=0.0,
            )
            is False
        )

    @pytest.mark.unit
    def test_add_sample_rejects_cop_out_of_range(self) -> None:
        """Samples with computed COP outside [1.0, 8.0] must be rejected."""
        calc = COPCalculator(mode=COPMode.AUTO_LEARNED)
        # COP = 10000 / 1000 = 10.0, above COP_MAX
        assert (
            calc.add_sample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=1000.0,
                q_thermal=10000.0,
            )
            is False
        )
        # COP = 500 / 1000 = 0.5, below COP_MIN
        assert (
            calc.add_sample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=1000.0,
                q_thermal=500.0,
            )
            is False
        )

    @pytest.mark.unit
    def test_fit_insufficient_samples(self) -> None:
        """fit() must return False when fewer than min_samples_hours samples."""
        calc = COPCalculator(
            mode=COPMode.AUTO_LEARNED, min_samples_hours=10
        )
        for _ in range(5):
            calc.add_sample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=1000.0,
                q_thermal=3500.0,
            )
        assert calc.fit() is False
        assert calc.is_fitted is False

    @pytest.mark.unit
    def test_fit_sufficient_samples(self) -> None:
        """fit() must succeed with sufficient samples and produce a model."""
        calc = COPCalculator(
            mode=COPMode.AUTO_LEARNED, min_samples_hours=10
        )
        rng = np.random.default_rng(42)
        for _ in range(20):
            t_out = rng.uniform(-10.0, 15.0)
            t_sup = rng.uniform(30.0, 45.0)
            # COP roughly proportional to t_out, inversely to t_sup
            cop = 3.0 + 0.05 * t_out - 0.02 * t_sup
            cop = max(COP_MIN, min(COP_MAX, cop))
            p_elec = 1500.0
            q_therm = cop * p_elec
            calc.add_sample(
                t_outdoor=t_out,
                t_supply=t_sup,
                p_electric=p_elec,
                q_thermal=q_therm,
            )
        assert calc.fit() is True
        assert calc.is_fitted is True

    @pytest.mark.unit
    def test_regression_predictions(self) -> None:
        """Fitted model should produce reasonable COP predictions."""
        calc = COPCalculator(
            mode=COPMode.AUTO_LEARNED, min_samples_hours=10
        )
        rng = np.random.default_rng(42)
        # Generate data with known relationship:
        # COP = 3.0 + 0.05 * T_outdoor - 0.02 * T_supply
        for _ in range(50):
            t_out = rng.uniform(-10.0, 15.0)
            t_sup = rng.uniform(30.0, 45.0)
            cop = 3.0 + 0.05 * t_out - 0.02 * t_sup
            cop = max(COP_MIN, min(COP_MAX, cop))
            p_elec = 1500.0
            q_therm = cop * p_elec
            calc.add_sample(
                t_outdoor=t_out,
                t_supply=t_sup,
                p_electric=p_elec,
                q_thermal=q_therm,
            )
        calc.fit()

        # Test prediction at a known point
        # COP(t_out=5, t_sup=35) ~= 3.0 + 0.05*5 - 0.02*35 = 2.55
        predicted = calc.get_cop(t_outdoor=5.0, t_supply=35.0)
        assert predicted == pytest.approx(2.55, abs=0.1)

    @pytest.mark.unit
    def test_t_supply_none_uses_default(self) -> None:
        """AUTO_LEARNED with t_supply=None should use DEFAULT_T_SUPPLY."""
        calc = COPCalculator(
            mode=COPMode.AUTO_LEARNED, min_samples_hours=10
        )
        rng = np.random.default_rng(42)
        for _ in range(20):
            t_out = rng.uniform(-10.0, 15.0)
            t_sup = rng.uniform(30.0, 45.0)
            cop = 3.5 + 0.03 * t_out - 0.01 * t_sup
            cop = max(COP_MIN, min(COP_MAX, cop))
            calc.add_sample(
                t_outdoor=t_out,
                t_supply=t_sup,
                p_electric=1000.0,
                q_thermal=cop * 1000.0,
            )
        calc.fit()
        # Should use DEFAULT_T_SUPPLY (35.0) internally
        result_none = calc.get_cop(t_outdoor=5.0)
        result_explicit = calc.get_cop(
            t_outdoor=5.0, t_supply=DEFAULT_T_SUPPLY
        )
        assert result_none == pytest.approx(result_explicit)

    @pytest.mark.unit
    def test_regression_cop_clamped(self) -> None:
        """Regression predictions outside [COP_MIN, COP_MAX] must be clamped."""
        calc = COPCalculator(
            mode=COPMode.AUTO_LEARNED, min_samples_hours=5
        )
        # Provide data that will produce a model predicting very high COP
        # at certain conditions
        for i in range(10):
            t_out = float(i)
            cop = 7.5  # near upper bound
            calc.add_sample(
                t_outdoor=t_out,
                t_supply=30.0,
                p_electric=1000.0,
                q_thermal=cop * 1000.0,
            )
        calc.fit()
        # Model should predict ~7.5 and result should be clamped to COP_MAX
        result = calc.get_cop(t_outdoor=100.0, t_supply=30.0)
        assert result <= COP_MAX
        assert result >= COP_MIN

    @pytest.mark.unit
    def test_reset_clears_state(self) -> None:
        """reset() must clear samples and fitted model."""
        calc = COPCalculator(
            mode=COPMode.AUTO_LEARNED, min_samples_hours=5
        )
        for _ in range(10):
            calc.add_sample(
                t_outdoor=5.0,
                t_supply=35.0,
                p_electric=1000.0,
                q_thermal=3500.0,
            )
        calc.fit()
        assert calc.is_fitted is True
        assert calc.n_samples == 10

        calc.reset()
        assert calc.is_fitted is False
        assert calc.n_samples == 0
        # After reset, should fall back to default COP
        assert calc.get_cop(t_outdoor=5.0) == DEFAULT_COP

    @pytest.mark.unit
    def test_auto_learned_properties(self) -> None:
        """Verify properties for AUTO_LEARNED mode."""
        calc = COPCalculator(mode=COPMode.AUTO_LEARNED)
        assert calc.mode is COPMode.AUTO_LEARNED
        assert calc.is_fitted is False
        assert calc.n_samples == 0
        assert calc.default_cop == DEFAULT_COP


# ---------------------------------------------------------------------------
# TestCOPCalculatorFromConfig
# ---------------------------------------------------------------------------


class TestCOPCalculatorFromConfig:
    """Tests for the from_config() factory method."""

    @pytest.mark.unit
    def test_constant_config(self) -> None:
        """Constant mode config should produce a CONSTANT calculator."""
        calc = COPCalculator.from_config({"mode": "constant", "cop": 4.0})
        assert calc.mode is COPMode.CONSTANT
        assert calc.get_cop(t_outdoor=0.0) == 4.0

    @pytest.mark.unit
    def test_constant_config_default_cop(self) -> None:
        """Constant mode without explicit cop should use DEFAULT_COP."""
        calc = COPCalculator.from_config({"mode": "constant"})
        assert calc.mode is COPMode.CONSTANT
        assert calc.get_cop(t_outdoor=0.0) == DEFAULT_COP

    @pytest.mark.unit
    def test_lookup_table_config(self) -> None:
        """Lookup table config should produce a LOOKUP_TABLE calculator."""
        calc = COPCalculator.from_config(
            {
                "mode": "lookup_table",
                "data": [[-15, 2.5], [0, 3.5], [15, 5.0]],
            }
        )
        assert calc.mode is COPMode.LOOKUP_TABLE
        assert calc.get_cop(t_outdoor=0.0) == pytest.approx(3.5)

    @pytest.mark.unit
    def test_auto_learned_config(self) -> None:
        """Auto-learned config should produce an AUTO_LEARNED calculator."""
        calc = COPCalculator.from_config(
            {"mode": "auto_learned", "min_samples_hours": 24}
        )
        assert calc.mode is COPMode.AUTO_LEARNED
        assert calc.is_fitted is False

    @pytest.mark.unit
    def test_auto_learned_config_default_hours(self) -> None:
        """Auto-learned without min_samples_hours should use MIN_SAMPLES_HOURS."""
        calc = COPCalculator.from_config({"mode": "auto_learned"})
        assert calc.mode is COPMode.AUTO_LEARNED

    @pytest.mark.unit
    def test_missing_mode_raises(self) -> None:
        """Config without 'mode' key must raise ValueError."""
        with pytest.raises(ValueError, match="must contain a 'mode' key"):
            COPCalculator.from_config({})

    @pytest.mark.unit
    def test_invalid_mode_raises(self) -> None:
        """Unknown mode string must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid COP mode"):
            COPCalculator.from_config({"mode": "magic"})

    @pytest.mark.unit
    def test_lookup_missing_data_raises(self) -> None:
        """Lookup table config without 'data' key must raise ValueError."""
        with pytest.raises(ValueError, match="must contain a 'data' key"):
            COPCalculator.from_config({"mode": "lookup_table"})

    @pytest.mark.unit
    def test_lookup_insufficient_data_raises(self) -> None:
        """Lookup table config with <2 entries must raise ValueError."""
        with pytest.raises(ValueError, match="at least 2 entries"):
            COPCalculator.from_config(
                {"mode": "lookup_table", "data": [[0, 3.0]]}
            )


# ---------------------------------------------------------------------------
# TestCOPConstants
# ---------------------------------------------------------------------------


class TestCOPConstants:
    """Verify module-level constants have expected values."""

    @pytest.mark.unit
    def test_cop_min(self) -> None:
        """COP_MIN must be 1.0."""
        assert COP_MIN == 1.0

    @pytest.mark.unit
    def test_cop_max(self) -> None:
        """COP_MAX must be 8.0."""
        assert COP_MAX == 8.0

    @pytest.mark.unit
    def test_default_cop(self) -> None:
        """DEFAULT_COP must be 3.5."""
        assert DEFAULT_COP == 3.5

    @pytest.mark.unit
    def test_min_samples_hours(self) -> None:
        """MIN_SAMPLES_HOURS must be 48."""
        assert MIN_SAMPLES_HOURS == 48

    @pytest.mark.unit
    def test_default_t_supply(self) -> None:
        """DEFAULT_T_SUPPLY must be 35.0."""
        assert DEFAULT_T_SUPPLY == 35.0
