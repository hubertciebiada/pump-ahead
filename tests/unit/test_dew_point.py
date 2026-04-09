"""Unit tests for dew point calculation and condensation protection.

Tests cover:
- TestDewPoint: Magnus formula accuracy against psychrometric tables
- TestDewPointSimplified: linear approximation backward compatibility
- TestCoolingThrottleFactor: graduated valve throttling logic
- TestCondensationMargin: safety margin computation
"""

from __future__ import annotations

import pytest

from pumpahead.dew_point import (
    MAGNUS_A,
    MAGNUS_B,
    condensation_margin,
    cooling_throttle_factor,
    dew_point,
    dew_point_simplified,
)

# ---------------------------------------------------------------------------
# TestDewPoint — Magnus formula
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDewPoint:
    """Tests for the proper Magnus formula dew-point calculation."""

    def test_known_value_20c_50rh(self) -> None:
        """T_air=20C, RH=50% -> T_dew approx 9.26C (psychrometric table)."""
        result = dew_point(20.0, 50.0)
        assert result == pytest.approx(9.26, abs=0.1)

    def test_known_value_25c_60rh(self) -> None:
        """T_air=25C, RH=60% -> T_dew approx 16.7C."""
        result = dew_point(25.0, 60.0)
        assert result == pytest.approx(16.7, abs=0.2)

    def test_known_value_30c_40rh(self) -> None:
        """T_air=30C, RH=40% -> T_dew approx 14.9C."""
        result = dew_point(30.0, 40.0)
        assert result == pytest.approx(14.9, abs=0.2)

    def test_known_value_10c_80rh(self) -> None:
        """T_air=10C, RH=80% -> T_dew approx 6.7C."""
        result = dew_point(10.0, 80.0)
        assert result == pytest.approx(6.7, abs=0.2)

    def test_rh_100_equals_t_air(self) -> None:
        """At 100% RH, dew point equals air temperature."""
        for t_air in [-10.0, 0.0, 15.0, 20.0, 30.0, 50.0]:
            assert dew_point(t_air, 100.0) == pytest.approx(t_air, abs=0.01)

    def test_rh_0_returns_absolute_zero(self) -> None:
        """At 0% RH, returns -273.15 (guard for log(0))."""
        assert dew_point(20.0, 0.0) == -273.15
        assert dew_point(-20.0, 0.0) == -273.15

    def test_negative_temperature(self) -> None:
        """Magnus formula works for negative T_air."""
        result = dew_point(-10.0, 80.0)
        # T_dew should be below T_air
        assert result < -10.0

    def test_high_temperature(self) -> None:
        """Magnus formula works for T_air near upper range (60C)."""
        result = dew_point(55.0, 50.0)
        assert result < 55.0
        assert result > 0.0  # sanity check

    def test_extreme_cold_minus_40(self) -> None:
        """Magnus formula works at -40C (lower range boundary)."""
        result = dew_point(-40.0, 50.0)
        assert result < -40.0

    def test_invalid_rh_above_100_raises(self) -> None:
        """RH > 100 raises ValueError."""
        with pytest.raises(ValueError, match="rh"):
            dew_point(20.0, 101.0)

    def test_invalid_rh_negative_raises(self) -> None:
        """RH < 0 raises ValueError."""
        with pytest.raises(ValueError, match="rh"):
            dew_point(20.0, -1.0)

    def test_monotonic_in_rh(self) -> None:
        """Dew point increases monotonically with RH at constant T_air."""
        t_air = 20.0
        prev = dew_point(t_air, 1.0)  # Start above 0 to avoid -273.15
        for rh in range(2, 101):
            current = dew_point(t_air, float(rh))
            assert current >= prev, (
                f"T_dew not monotonic at RH={rh}: {current} < {prev}"
            )
            prev = current

    def test_monotonic_in_t_air(self) -> None:
        """Dew point increases monotonically with T_air at constant RH."""
        rh = 50.0
        prev = dew_point(-40.0, rh)
        for t_air_int in range(-39, 61):
            t_air = float(t_air_int)
            current = dew_point(t_air, rh)
            assert current >= prev, (
                f"T_dew not monotonic at T_air={t_air}: {current} < {prev}"
            )
            prev = current

    def test_dew_point_always_below_or_equal_t_air(self) -> None:
        """T_dew <= T_air for all valid inputs (physical constraint)."""
        for t_air in [-30.0, -10.0, 0.0, 10.0, 20.0, 30.0, 50.0]:
            for rh in [1.0, 10.0, 30.0, 50.0, 70.0, 90.0, 100.0]:
                result = dew_point(t_air, rh)
                assert result <= t_air + 0.01, (
                    f"T_dew={result} > T_air={t_air} at RH={rh}"
                )

    def test_constants_are_alduchov(self) -> None:
        """Verify constants match Alduchov & Eskridge (1996)."""
        assert pytest.approx(17.625) == MAGNUS_A
        assert pytest.approx(243.04) == MAGNUS_B


# ---------------------------------------------------------------------------
# TestDewPointSimplified — linear approximation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDewPointSimplified:
    """Tests for the simplified (legacy) dew-point formula."""

    def test_typical_value(self) -> None:
        """T_air=21C, RH=50% -> T_dew = 21 - 50/5 = 11.0."""
        assert dew_point_simplified(21.0, 50.0) == pytest.approx(11.0)

    def test_rh_100_equals_t_air(self) -> None:
        """At 100% RH, simplified T_dew = T_air."""
        assert dew_point_simplified(20.0, 100.0) == pytest.approx(20.0)

    def test_rh_0(self) -> None:
        """At 0% RH, simplified T_dew = T_air - 20."""
        assert dew_point_simplified(21.0, 0.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TestCoolingThrottleFactor — graduated valve throttling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoolingThrottleFactor:
    """Tests for graduated cooling valve throttle logic."""

    def test_full_cooling_when_gap_large(self) -> None:
        """Returns 1.0 when floor is well above dew point."""
        # gap = 30 - 10 = 20, margin+ramp = 4 -> fully open
        assert cooling_throttle_factor(30.0, 10.0) == pytest.approx(1.0)

    def test_no_cooling_at_margin(self) -> None:
        """Returns 0.0 when gap equals margin (condensation risk)."""
        # gap = 12 - 10 = 2.0, margin = 2.0 -> 0.0
        assert cooling_throttle_factor(12.0, 10.0) == pytest.approx(0.0)

    def test_no_cooling_below_margin(self) -> None:
        """Returns 0.0 when gap is below margin."""
        # gap = 11 - 10 = 1.0, margin = 2.0 -> 0.0
        assert cooling_throttle_factor(11.0, 10.0) == pytest.approx(0.0)

    def test_half_throttle_at_midpoint(self) -> None:
        """Returns 0.5 at the midpoint of the ramp."""
        # margin=2, ramp_width=2, midpoint gap = 2 + 1 = 3
        # t_floor = t_dew + 3 = 13
        assert cooling_throttle_factor(13.0, 10.0) == pytest.approx(0.5)

    def test_full_at_ramp_upper_bound(self) -> None:
        """Returns 1.0 when gap equals margin + ramp_width."""
        # gap = 14 - 10 = 4.0, margin + ramp = 4.0 -> 1.0
        assert cooling_throttle_factor(14.0, 10.0) == pytest.approx(1.0)

    def test_smooth_graduated_not_step(self) -> None:
        """Throttle transitions smoothly through the ramp zone."""
        t_dew = 10.0
        prev = 0.0
        for floor_temp_10x in range(120, 141):  # 12.0 to 14.0 in 0.1 steps
            t_floor = floor_temp_10x / 10.0
            current = cooling_throttle_factor(t_floor, t_dew)
            assert current >= prev, (
                f"Non-monotonic at t_floor={t_floor}: {current} < {prev}"
            )
            prev = current
        # Should go from 0.0 to 1.0
        assert cooling_throttle_factor(12.0, t_dew) == pytest.approx(0.0)
        assert cooling_throttle_factor(14.0, t_dew) == pytest.approx(1.0)

    def test_custom_margin_and_ramp(self) -> None:
        """Custom margin=3, ramp_width=5 produces correct values."""
        # gap = 20 - 10 = 10, margin=3, ramp=5
        # gap > margin + ramp (8) -> 1.0
        result = cooling_throttle_factor(
            20.0,
            10.0,
            margin=3.0,
            ramp_width=5.0,
        )
        assert result == pytest.approx(1.0)

        # gap = 13 - 10 = 3 = margin -> 0.0
        result = cooling_throttle_factor(
            13.0,
            10.0,
            margin=3.0,
            ramp_width=5.0,
        )
        assert result == pytest.approx(0.0)

        # gap = 15.5 - 10 = 5.5, (5.5 - 3) / 5 = 0.5
        result = cooling_throttle_factor(
            15.5,
            10.0,
            margin=3.0,
            ramp_width=5.0,
        )
        assert result == pytest.approx(0.5)

    def test_negative_margin_raises(self) -> None:
        """Negative margin raises ValueError."""
        with pytest.raises(ValueError, match="margin"):
            cooling_throttle_factor(20.0, 10.0, margin=-1.0)

    def test_zero_ramp_width_raises(self) -> None:
        """Zero ramp_width raises ValueError."""
        with pytest.raises(ValueError, match="ramp_width"):
            cooling_throttle_factor(20.0, 10.0, ramp_width=0.0)

    def test_negative_ramp_width_raises(self) -> None:
        """Negative ramp_width raises ValueError."""
        with pytest.raises(ValueError, match="ramp_width"):
            cooling_throttle_factor(20.0, 10.0, ramp_width=-1.0)

    def test_zero_margin_valid(self) -> None:
        """margin=0 is valid; ramp starts at gap=0."""
        # gap = 11 - 10 = 1, margin=0, ramp=2 -> 0.5
        result = cooling_throttle_factor(
            11.0,
            10.0,
            margin=0.0,
            ramp_width=2.0,
        )
        assert result == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# TestCondensationMargin — safety margin computation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCondensationMargin:
    """Tests for the condensation_margin function."""

    def test_positive_when_safe(self) -> None:
        """Returns positive value when floor is well above dew point + margin."""
        # T_air=20, RH=50 -> T_dew ~ 9.26 -> threshold = 11.26
        # margin = 25 - 11.26 = 13.74
        result = condensation_margin(25.0, 20.0, 50.0)
        assert result > 0.0
        assert result == pytest.approx(13.74, abs=0.1)

    def test_negative_at_risk(self) -> None:
        """Returns negative value when floor is below dew point + margin."""
        # T_air=20, RH=80 -> T_dew ~ 16.44 -> threshold = 18.44
        # margin = 17 - 18.44 = -1.44
        result = condensation_margin(17.0, 20.0, 80.0)
        assert result < 0.0

    def test_uses_magnus_formula(self) -> None:
        """Result uses proper Magnus formula, not simplified."""
        # With simplified: T_dew = 20 - 50/5 = 10, margin = 25 - 12 = 13.0
        # With Magnus: T_dew ~ 9.26, margin = 25 - 11.26 ~ 13.74
        result = condensation_margin(25.0, 20.0, 50.0)
        # Should NOT equal 13.0 (simplified), should be ~13.74
        assert result != pytest.approx(13.0, abs=0.1)
        assert result == pytest.approx(13.74, abs=0.1)

    def test_custom_safety_margin(self) -> None:
        """Custom safety_margin is used in the calculation."""
        # T_air=20, RH=50 -> T_dew ~ 9.26
        # margin_3 = 25 - (9.26 + 3) = 12.74
        result = condensation_margin(25.0, 20.0, 50.0, safety_margin=3.0)
        assert result == pytest.approx(12.74, abs=0.1)

    def test_rh_100_margin_equals_floor_minus_room_minus_safety(self) -> None:
        """At RH=100%, T_dew=T_air -> margin = T_floor - T_air - safety."""
        result = condensation_margin(25.0, 20.0, 100.0, safety_margin=2.0)
        assert result == pytest.approx(3.0, abs=0.01)
