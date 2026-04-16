"""Unit tests for UFH loop thermal power calculation.

Tests cover:
- TestLoopGeometryValidation: construction, from_room_config, validation errors
- TestDeltaTLog: known LMTD, equal deltas, zero/negative deltas
- TestLoopPowerHeating: monotonicity, hard zeros, positive results, sanity range
- TestLoopPowerCooling: negative results, hard zeros, default dt
- TestLoopPowerWithValve: valve=0/1/0.5, clamping
- TestAxiom3Compliance: sweep t_supply for heating/cooling sign invariants
"""

from __future__ import annotations

import math

import pytest

from pumpahead.config import RoomConfig
from pumpahead.model import RCParams
from pumpahead.ufh_loop import (
    DEFAULT_DT_COOLING,
    DEFAULT_DT_HEATING,
    LoopGeometry,
    _delta_t_log,
    loop_power,
    loop_power_with_valve,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _siso_params() -> RCParams:
    """Standard 3R3C SISO (UFH-only) parameters."""
    return RCParams(
        C_air=60_000,
        C_slab=3_250_000,
        C_wall=1_500_000,
        R_sf=0.01,
        R_wi=0.02,
        R_wo=0.03,
        R_ve=0.03,
        R_ins=0.01,
        f_conv=0.6,
        f_rad=0.4,
        T_ground=10.0,
        has_split=False,
    )


def _default_geometry() -> LoopGeometry:
    """Standard 25 m^2 room with 120 m of 16x2 PE-X at 0.15 m spacing."""
    return LoopGeometry(
        effective_pipe_length_m=120.0,
        pipe_spacing_m=0.15,
        pipe_diameter_outer_mm=16.0,
        pipe_wall_thickness_mm=2.0,
        area_m2=25.0,
    )


# ===========================================================================
# TestLoopGeometryValidation
# ===========================================================================


@pytest.mark.unit
class TestLoopGeometryValidation:
    """Tests for LoopGeometry construction and validation."""

    def test_valid_construction(self) -> None:
        """All fields positive and consistent -> no error."""
        geo = _default_geometry()
        assert geo.effective_pipe_length_m == 120.0
        assert geo.pipe_spacing_m == 0.15
        assert geo.pipe_diameter_outer_mm == 16.0
        assert geo.pipe_wall_thickness_mm == 2.0
        assert geo.area_m2 == 25.0

    def test_frozen(self) -> None:
        """LoopGeometry is immutable."""
        geo = _default_geometry()
        with pytest.raises(AttributeError):
            geo.area_m2 = 30.0  # type: ignore[misc]

    def test_negative_pipe_length_raises(self) -> None:
        with pytest.raises(ValueError, match="effective_pipe_length_m must be > 0"):
            LoopGeometry(
                effective_pipe_length_m=-1.0,
                pipe_spacing_m=0.15,
                pipe_diameter_outer_mm=16.0,
                pipe_wall_thickness_mm=2.0,
                area_m2=25.0,
            )

    def test_zero_pipe_length_raises(self) -> None:
        with pytest.raises(ValueError, match="effective_pipe_length_m must be > 0"):
            LoopGeometry(
                effective_pipe_length_m=0.0,
                pipe_spacing_m=0.15,
                pipe_diameter_outer_mm=16.0,
                pipe_wall_thickness_mm=2.0,
                area_m2=25.0,
            )

    def test_negative_spacing_raises(self) -> None:
        with pytest.raises(ValueError, match="pipe_spacing_m must be > 0"):
            LoopGeometry(
                effective_pipe_length_m=120.0,
                pipe_spacing_m=-0.1,
                pipe_diameter_outer_mm=16.0,
                pipe_wall_thickness_mm=2.0,
                area_m2=25.0,
            )

    def test_negative_diameter_raises(self) -> None:
        with pytest.raises(ValueError, match="pipe_diameter_outer_mm must be > 0"):
            LoopGeometry(
                effective_pipe_length_m=120.0,
                pipe_spacing_m=0.15,
                pipe_diameter_outer_mm=-16.0,
                pipe_wall_thickness_mm=2.0,
                area_m2=25.0,
            )

    def test_wall_too_thick_raises(self) -> None:
        """Wall thickness >= diameter/2 is physically impossible."""
        with pytest.raises(ValueError, match="pipe_wall_thickness_mm.*must be <"):
            LoopGeometry(
                effective_pipe_length_m=120.0,
                pipe_spacing_m=0.15,
                pipe_diameter_outer_mm=16.0,
                pipe_wall_thickness_mm=8.0,  # == d/2
                area_m2=25.0,
            )

    def test_negative_area_raises(self) -> None:
        with pytest.raises(ValueError, match="area_m2 must be > 0"):
            LoopGeometry(
                effective_pipe_length_m=120.0,
                pipe_spacing_m=0.15,
                pipe_diameter_outer_mm=16.0,
                pipe_wall_thickness_mm=2.0,
                area_m2=-5.0,
            )

    def test_from_room_config_with_pipe_length(self) -> None:
        """from_room_config extracts geometry from RoomConfig with pipe_length_m."""
        room = RoomConfig(
            name="test_room",
            area_m2=25.0,
            params=_siso_params(),
            pipe_length_m=120.0,
            pipe_diameter_outer_mm=16.0,
            pipe_wall_thickness_mm=2.0,
        )
        geo = LoopGeometry.from_room_config(room)
        assert geo.effective_pipe_length_m == 120.0
        # Spacing estimated as area / length
        assert geo.pipe_spacing_m == pytest.approx(25.0 / 120.0)
        assert geo.area_m2 == 25.0

    def test_from_room_config_with_pipe_spacing(self) -> None:
        """from_room_config extracts geometry from RoomConfig with pipe_spacing_m."""
        room = RoomConfig(
            name="test_room",
            area_m2=25.0,
            params=_siso_params(),
            pipe_spacing_m=0.15,
            pipe_diameter_outer_mm=16.0,
            pipe_wall_thickness_mm=2.0,
        )
        geo = LoopGeometry.from_room_config(room)
        assert geo.pipe_spacing_m == 0.15
        # Length estimated from area / spacing * safety factor
        assert geo.effective_pipe_length_m == pytest.approx(25.0 / 0.15 * 1.1, rel=1e-6)
        assert geo.area_m2 == 25.0

    def test_from_room_config_no_geometry_raises(self) -> None:
        """from_room_config raises ValueError when no geometry is configured."""
        room = RoomConfig(
            name="test_room",
            area_m2=25.0,
            params=_siso_params(),
        )
        with pytest.raises(ValueError, match="pipe geometry not configured"):
            LoopGeometry.from_room_config(room)


# ===========================================================================
# TestDeltaTLog
# ===========================================================================


@pytest.mark.unit
class TestDeltaTLog:
    """Tests for the private _delta_t_log helper."""

    def test_known_lmtd(self) -> None:
        """Known LMTD: dT_in=10, dT_out=5 -> (10-5)/ln(10/5) = 7.213."""
        result = _delta_t_log(10.0, 5.0)
        expected = (10.0 - 5.0) / math.log(10.0 / 5.0)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_equal_deltas(self) -> None:
        """When dT_in == dT_out, result is the arithmetic mean."""
        result = _delta_t_log(8.0, 8.0)
        assert result == pytest.approx(8.0, rel=1e-9)

    def test_nearly_equal_deltas(self) -> None:
        """When dT_in ~= dT_out within epsilon, use arithmetic mean."""
        result = _delta_t_log(8.0, 8.0 + 1e-12)
        assert result == pytest.approx(8.0, rel=1e-6)

    def test_zero_delta_in(self) -> None:
        """dT_in == 0 -> 0.0 (no heat transfer)."""
        assert _delta_t_log(0.0, 5.0) == 0.0

    def test_zero_delta_out(self) -> None:
        """dT_out == 0 -> 0.0 (no heat transfer)."""
        assert _delta_t_log(5.0, 0.0) == 0.0

    def test_negative_delta_in(self) -> None:
        """Negative dT_in -> 0.0."""
        assert _delta_t_log(-1.0, 5.0) == 0.0

    def test_negative_delta_out(self) -> None:
        """Negative dT_out -> 0.0."""
        assert _delta_t_log(5.0, -2.0) == 0.0

    def test_both_negative(self) -> None:
        """Both negative -> 0.0."""
        assert _delta_t_log(-3.0, -5.0) == 0.0

    def test_symmetric_inputs(self) -> None:
        """LMTD(a, b) == LMTD(b, a) for positive a, b."""
        assert _delta_t_log(10.0, 5.0) == pytest.approx(
            _delta_t_log(5.0, 10.0), rel=1e-9
        )

    def test_result_always_non_negative(self) -> None:
        """Result is >= 0 for all combinations of positive inputs."""
        for dt_in in [0.5, 1.0, 5.0, 10.0, 20.0]:
            for dt_out in [0.5, 1.0, 5.0, 10.0, 20.0]:
                assert _delta_t_log(dt_in, dt_out) >= 0.0


# ===========================================================================
# TestLoopPowerHeating
# ===========================================================================


@pytest.mark.unit
class TestLoopPowerHeating:
    """Tests for loop_power in heating mode."""

    def test_positive_result(self) -> None:
        """Heating with t_supply > t_slab returns Q > 0."""
        geo = _default_geometry()
        q = loop_power(35.0, 22.0, geo, "heating")
        assert q > 0.0

    def test_zero_when_supply_equals_slab(self) -> None:
        """t_supply == t_slab returns exactly 0.0."""
        geo = _default_geometry()
        q = loop_power(22.0, 22.0, geo, "heating")
        assert q == 0.0

    def test_zero_when_supply_below_slab(self) -> None:
        """t_supply < t_slab returns 0.0 in heating (Axiom #3)."""
        geo = _default_geometry()
        q = loop_power(20.0, 25.0, geo, "heating")
        assert q == 0.0

    def test_monotonic_with_t_supply(self) -> None:
        """Higher t_supply -> higher power (monotonically increasing).

        Start from t_slab + DEFAULT_DT_HEATING + 1 to ensure the return
        temperature is above the slab, keeping both LMTD deltas positive.
        """
        geo = _default_geometry()
        t_slab = 22.0
        # Return temp = t_supply - 5; both deltas positive when t_supply > 27
        start = int(t_slab + DEFAULT_DT_HEATING) + 1  # 28
        supplies = list(range(start, 50))
        powers = [loop_power(float(t), t_slab, geo, "heating") for t in supplies]
        for i in range(1, len(powers)):
            assert powers[i] > powers[i - 1], (
                f"Power at t_supply={supplies[i]} ({powers[i]:.1f}) "
                f"<= power at t_supply={supplies[i - 1]} ({powers[i - 1]:.1f})"
            )

    def test_monotonic_with_pipe_length(self) -> None:
        """Longer pipe -> more power (same area, spacing, etc.)."""
        t_supply, t_slab = 35.0, 22.0
        lengths = [60.0, 80.0, 100.0, 120.0, 150.0]
        powers = []
        for length in lengths:
            geo = LoopGeometry(
                effective_pipe_length_m=length,
                pipe_spacing_m=0.15,
                pipe_diameter_outer_mm=16.0,
                pipe_wall_thickness_mm=2.0,
                area_m2=25.0,
            )
            powers.append(loop_power(t_supply, t_slab, geo, "heating"))
        for i in range(1, len(powers)):
            assert powers[i] > powers[i - 1]

    def test_explicit_return_temp(self) -> None:
        """Providing t_return_estimate changes the result vs default."""
        geo = _default_geometry()
        q_default = loop_power(35.0, 22.0, geo, "heating")
        q_explicit = loop_power(35.0, 22.0, geo, "heating", t_return_estimate=32.0)
        # With higher return temp (32 vs 35-5=30), LMTD is larger
        assert q_explicit > q_default

    def test_sanity_range_watts(self) -> None:
        """Typical room: Q should be in a plausible range (100-5000 W)."""
        geo = _default_geometry()
        q = loop_power(35.0, 22.0, geo, "heating")
        assert 100.0 < q < 5000.0

    def test_invalid_mode_raises(self) -> None:
        """Invalid mode string raises ValueError."""
        geo = _default_geometry()
        with pytest.raises(ValueError, match="mode must be"):
            loop_power(35.0, 22.0, geo, "auto")  # type: ignore[arg-type]


# ===========================================================================
# TestLoopPowerCooling
# ===========================================================================


@pytest.mark.unit
class TestLoopPowerCooling:
    """Tests for loop_power in cooling mode."""

    def test_negative_result(self) -> None:
        """Cooling with t_supply < t_slab returns Q < 0."""
        geo = _default_geometry()
        q = loop_power(16.0, 24.0, geo, "cooling")
        assert q < 0.0

    def test_zero_when_supply_equals_slab(self) -> None:
        """t_supply == t_slab returns exactly 0.0."""
        geo = _default_geometry()
        q = loop_power(24.0, 24.0, geo, "cooling")
        assert q == 0.0

    def test_zero_when_supply_above_slab(self) -> None:
        """t_supply > t_slab returns 0.0 in cooling (Axiom #3)."""
        geo = _default_geometry()
        q = loop_power(28.0, 24.0, geo, "cooling")
        assert q == 0.0

    def test_default_dt_cooling(self) -> None:
        """Default return temp uses DEFAULT_DT_COOLING offset."""
        geo = _default_geometry()
        t_supply = 16.0
        t_slab = 24.0
        q_default = loop_power(t_supply, t_slab, geo, "cooling")
        q_explicit = loop_power(
            t_supply,
            t_slab,
            geo,
            "cooling",
            t_return_estimate=t_supply + DEFAULT_DT_COOLING,
        )
        assert q_default == pytest.approx(q_explicit, rel=1e-9)

    def test_more_negative_with_lower_supply(self) -> None:
        """Lower t_supply extracts more heat (more negative Q)."""
        geo = _default_geometry()
        t_slab = 24.0
        q_16 = loop_power(16.0, t_slab, geo, "cooling")
        q_12 = loop_power(12.0, t_slab, geo, "cooling")
        assert q_12 < q_16 < 0.0


# ===========================================================================
# TestLoopPowerWithValve
# ===========================================================================


@pytest.mark.unit
class TestLoopPowerWithValve:
    """Tests for loop_power_with_valve."""

    def test_valve_zero_returns_zero(self) -> None:
        """valve=0 always returns 0.0."""
        geo = _default_geometry()
        assert loop_power_with_valve(0.0, 35.0, 22.0, geo, "heating") == 0.0

    def test_valve_one_equals_full_power(self) -> None:
        """valve=1 returns full loop_power value."""
        geo = _default_geometry()
        q_full = loop_power(35.0, 22.0, geo, "heating")
        q_valve = loop_power_with_valve(1.0, 35.0, 22.0, geo, "heating")
        assert q_valve == pytest.approx(q_full, rel=1e-9)

    def test_valve_half(self) -> None:
        """valve=0.5 returns half of full power."""
        geo = _default_geometry()
        q_full = loop_power(35.0, 22.0, geo, "heating")
        q_half = loop_power_with_valve(0.5, 35.0, 22.0, geo, "heating")
        assert q_half == pytest.approx(q_full * 0.5, rel=1e-9)

    def test_valve_clamped_above_one(self) -> None:
        """valve > 1.0 is clamped to 1.0."""
        geo = _default_geometry()
        q_full = loop_power(35.0, 22.0, geo, "heating")
        q_over = loop_power_with_valve(1.5, 35.0, 22.0, geo, "heating")
        assert q_over == pytest.approx(q_full, rel=1e-9)

    def test_valve_clamped_below_zero(self) -> None:
        """valve < 0.0 is clamped to 0.0."""
        geo = _default_geometry()
        assert loop_power_with_valve(-0.5, 35.0, 22.0, geo, "heating") == 0.0

    def test_valve_with_cooling(self) -> None:
        """valve scaling works in cooling mode."""
        geo = _default_geometry()
        q_full = loop_power(16.0, 24.0, geo, "cooling")
        q_valve = loop_power_with_valve(0.7, 16.0, 24.0, geo, "cooling")
        assert q_valve == pytest.approx(q_full * 0.7, rel=1e-9)


# ===========================================================================
# TestAxiom3Compliance
# ===========================================================================


@pytest.mark.unit
class TestAxiom3Compliance:
    """Axiom #3: loop_power never opposes the mode."""

    def test_heating_never_negative(self) -> None:
        """Sweep t_supply: heating mode never produces negative power."""
        geo = _default_geometry()
        t_slab = 22.0
        for t_supply_int in range(-10, 60):
            t_supply = float(t_supply_int)
            q = loop_power(t_supply, t_slab, geo, "heating")
            assert q >= 0.0, (
                f"Heating produced Q={q:.1f} W at t_supply={t_supply}, t_slab={t_slab}"
            )

    def test_cooling_never_positive(self) -> None:
        """Sweep t_supply: cooling mode never produces positive power."""
        geo = _default_geometry()
        t_slab = 24.0
        for t_supply_int in range(-10, 60):
            t_supply = float(t_supply_int)
            q = loop_power(t_supply, t_slab, geo, "cooling")
            assert q <= 0.0, (
                f"Cooling produced Q={q:.1f} W at t_supply={t_supply}, t_slab={t_slab}"
            )

    def test_heating_with_valve_never_negative(self) -> None:
        """Valve-scaled heating is also never negative."""
        geo = _default_geometry()
        t_slab = 22.0
        for valve in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for t_supply_int in range(10, 50):
                t_supply = float(t_supply_int)
                q = loop_power_with_valve(valve, t_supply, t_slab, geo, "heating")
                assert q >= 0.0

    def test_cooling_with_valve_never_positive(self) -> None:
        """Valve-scaled cooling is also never positive."""
        geo = _default_geometry()
        t_slab = 24.0
        for valve in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for t_supply_int in range(5, 40):
                t_supply = float(t_supply_int)
                q = loop_power_with_valve(valve, t_supply, t_slab, geo, "cooling")
                assert q <= 0.0
