"""Comprehensive unit tests for pumpahead.solar."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pumpahead.solar import (
    EphemerisCalculator,
    Orientation,
    SolarGainModel,
    WindowConfig,
)

# ---------------------------------------------------------------------------
# TestOrientation — enum values and azimuth mapping
# ---------------------------------------------------------------------------


class TestOrientation:
    """Tests for Orientation enum."""

    @pytest.mark.unit
    def test_orientation_values(self) -> None:
        """Enum values are the compass letters N/E/S/W."""
        assert Orientation.NORTH.value == "N"
        assert Orientation.EAST.value == "E"
        assert Orientation.SOUTH.value == "S"
        assert Orientation.WEST.value == "W"

    @pytest.mark.unit
    def test_orientation_azimuth_deg(self) -> None:
        """Window-normal azimuths: N=0, E=90, S=180, W=270."""
        assert Orientation.NORTH.azimuth_deg == 0.0
        assert Orientation.EAST.azimuth_deg == 90.0
        assert Orientation.SOUTH.azimuth_deg == 180.0
        assert Orientation.WEST.azimuth_deg == 270.0


# ---------------------------------------------------------------------------
# TestWindowConfig — dataclass validation
# ---------------------------------------------------------------------------


class TestWindowConfig:
    """Tests for WindowConfig frozen dataclass."""

    @pytest.mark.unit
    def test_valid_window_config(self) -> None:
        """Valid parameters create a window without errors."""
        w = WindowConfig(orientation=Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        assert w.orientation is Orientation.SOUTH
        assert w.area_m2 == 3.0
        assert w.g_value == 0.6

    @pytest.mark.unit
    def test_zero_area_rejected(self) -> None:
        """area_m2=0 must be rejected."""
        with pytest.raises(ValueError, match="area_m2 must be positive"):
            WindowConfig(orientation=Orientation.SOUTH, area_m2=0, g_value=0.6)

    @pytest.mark.unit
    def test_negative_area_rejected(self) -> None:
        """Negative area must be rejected."""
        with pytest.raises(ValueError, match="area_m2 must be positive"):
            WindowConfig(orientation=Orientation.SOUTH, area_m2=-1.0, g_value=0.6)

    @pytest.mark.unit
    def test_g_value_zero_rejected(self) -> None:
        """g_value=0 must be rejected (no solar transmittance is meaningless)."""
        with pytest.raises(ValueError, match="g_value must be in"):
            WindowConfig(orientation=Orientation.SOUTH, area_m2=3.0, g_value=0.0)

    @pytest.mark.unit
    def test_g_value_above_one_rejected(self) -> None:
        """g_value > 1.0 must be rejected."""
        with pytest.raises(ValueError, match="g_value must be in"):
            WindowConfig(orientation=Orientation.SOUTH, area_m2=3.0, g_value=1.1)

    @pytest.mark.unit
    def test_g_value_one_accepted(self) -> None:
        """g_value=1.0 (perfect transmittance) is valid."""
        w = WindowConfig(orientation=Orientation.SOUTH, area_m2=3.0, g_value=1.0)
        assert w.g_value == 1.0

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """Cannot mutate fields on a frozen dataclass."""
        w = WindowConfig(orientation=Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        with pytest.raises(AttributeError):
            w.area_m2 = 5.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestSolarGainModel — Q_sol calculations
# ---------------------------------------------------------------------------


class TestSolarGainModel:
    """Tests for SolarGainModel stateless calculator."""

    @pytest.mark.unit
    def test_q_sol_zero_at_night(
        self,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """GHI=0 returns Q_sol=0 (night time)."""
        result = solar_model.compute(
            ghi=0.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[south_window],
        )
        assert result == 0.0

    @pytest.mark.unit
    def test_q_sol_zero_negative_elevation(
        self,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """Negative elevation (sun below horizon) returns Q_sol=0."""
        result = solar_model.compute(
            ghi=500.0, elevation_deg=-5.0, azimuth_deg=180.0,
            windows=[south_window],
        )
        assert result == 0.0

    @pytest.mark.unit
    def test_q_sol_zero_elevation_exactly_zero(
        self,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """Elevation exactly 0 (horizon) returns Q_sol=0."""
        result = solar_model.compute(
            ghi=500.0, elevation_deg=0.0, azimuth_deg=180.0,
            windows=[south_window],
        )
        assert result == 0.0

    @pytest.mark.unit
    def test_q_sol_zero_no_windows(
        self,
        solar_model: SolarGainModel,
    ) -> None:
        """Empty windows list returns Q_sol=0."""
        result = solar_model.compute(
            ghi=500.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[],
        )
        assert result == 0.0

    @pytest.mark.unit
    def test_q_sol_south_window_noon_winter(
        self,
        solar_model: SolarGainModel,
    ) -> None:
        """South-facing window at solar noon in winter gets positive Q_sol.

        Sun at azimuth=180 (south), elevation=20 deg (typical winter noon
        at lat 50). Window: 3 m^2, g=0.6.
        Expected: 0.6 * 3.0 * 500 * cos(0) * cos(20 deg) ~= 845.7 W
        """
        import math

        w = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        result = solar_model.compute(
            ghi=500.0, elevation_deg=20.0, azimuth_deg=180.0,
            windows=[w],
        )
        expected = 0.6 * 3.0 * 500.0 * math.cos(math.radians(20.0))
        assert result > 0
        assert result == pytest.approx(expected, rel=1e-6)

    @pytest.mark.unit
    def test_q_sol_south_greater_than_north_winter(
        self,
        solar_model: SolarGainModel,
    ) -> None:
        """South window must have higher Q_sol than north window in winter.

        Sun at azimuth=180 (south), elevation=20 deg.
        """
        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        north = WindowConfig(Orientation.NORTH, area_m2=3.0, g_value=0.6)

        q_south = solar_model.compute(
            ghi=500.0, elevation_deg=20.0, azimuth_deg=180.0,
            windows=[south],
        )
        q_north = solar_model.compute(
            ghi=500.0, elevation_deg=20.0, azimuth_deg=180.0,
            windows=[north],
        )
        assert q_south > 0
        assert q_north == 0.0  # Sun behind north window
        assert q_south > q_north

    @pytest.mark.unit
    def test_q_sol_east_window_morning(
        self,
        solar_model: SolarGainModel,
    ) -> None:
        """East-facing window gets more Q_sol than west when sun is in the east."""
        east = WindowConfig(Orientation.EAST, area_m2=3.0, g_value=0.6)
        west = WindowConfig(Orientation.WEST, area_m2=3.0, g_value=0.6)

        # Sun in the east: azimuth ~90 deg, low elevation
        q_east = solar_model.compute(
            ghi=300.0, elevation_deg=15.0, azimuth_deg=90.0,
            windows=[east],
        )
        q_west = solar_model.compute(
            ghi=300.0, elevation_deg=15.0, azimuth_deg=90.0,
            windows=[west],
        )
        assert q_east > 0
        assert q_west == 0.0  # Sun behind west window
        assert q_east > q_west

    @pytest.mark.unit
    def test_g_value_scaling(
        self,
        solar_model: SolarGainModel,
    ) -> None:
        """g=0.5 gives exactly half the Q_sol of g=1.0 (linearity)."""
        w_full = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=1.0)
        w_half = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.5)

        q_full = solar_model.compute(
            ghi=500.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[w_full],
        )
        q_half = solar_model.compute(
            ghi=500.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[w_half],
        )
        assert q_half == pytest.approx(q_full * 0.5, rel=1e-10)

    @pytest.mark.unit
    def test_multiple_windows_summed(
        self,
        solar_model: SolarGainModel,
    ) -> None:
        """Two identical windows produce double the Q_sol of one."""
        w = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)

        q_one = solar_model.compute(
            ghi=500.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[w],
        )
        q_two = solar_model.compute(
            ghi=500.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[w, w],
        )
        assert q_two == pytest.approx(q_one * 2.0, rel=1e-10)

    @pytest.mark.unit
    def test_sun_behind_window(
        self,
        solar_model: SolarGainModel,
    ) -> None:
        """Sun at north (azimuth=0), south-facing window: factor = 0."""
        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        result = solar_model.compute(
            ghi=500.0, elevation_deg=30.0, azimuth_deg=0.0,
            windows=[south],
        )
        assert result == 0.0

    @pytest.mark.unit
    def test_q_sol_proportional_to_ghi(
        self,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """Doubling GHI doubles Q_sol (linearity)."""
        q1 = solar_model.compute(
            ghi=250.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[south_window],
        )
        q2 = solar_model.compute(
            ghi=500.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[south_window],
        )
        assert q2 == pytest.approx(q1 * 2.0, rel=1e-10)

    @pytest.mark.unit
    def test_q_sol_proportional_to_area(
        self,
        solar_model: SolarGainModel,
    ) -> None:
        """Doubling window area doubles Q_sol (linearity)."""
        w_small = WindowConfig(Orientation.SOUTH, area_m2=2.0, g_value=0.6)
        w_large = WindowConfig(Orientation.SOUTH, area_m2=4.0, g_value=0.6)

        q_small = solar_model.compute(
            ghi=500.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[w_small],
        )
        q_large = solar_model.compute(
            ghi=500.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[w_large],
        )
        assert q_large == pytest.approx(q_small * 2.0, rel=1e-10)

    @pytest.mark.unit
    def test_q_sol_negative_ghi_returns_zero(
        self,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """Negative GHI (sensor error) still returns 0."""
        result = solar_model.compute(
            ghi=-100.0, elevation_deg=30.0, azimuth_deg=180.0,
            windows=[south_window],
        )
        assert result == 0.0


# ---------------------------------------------------------------------------
# TestEphemerisCalculator — sun position calculations
# ---------------------------------------------------------------------------


class TestEphemerisCalculator:
    """Tests for EphemerisCalculator sun position computations."""

    @pytest.mark.unit
    def test_noon_elevation_summer_solstice(
        self,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """At lat ~50.69, summer solstice noon: elevation ~62.8 deg.

        Expected: 90 - 50.69 + 23.45 = 62.76 deg. Allow +-2 deg
        tolerance for the simplified formula.
        Solar noon at lon 17.38 is approximately 10:52 UTC.
        """
        dt = datetime(2024, 6, 21, 10, 52, tzinfo=UTC)
        elevation, _ = ephemeris_lubcza.sun_position(dt)
        assert elevation == pytest.approx(62.76, abs=2.0)

    @pytest.mark.unit
    def test_noon_elevation_winter_solstice(
        self,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """At lat ~50.69, winter solstice noon: elevation ~15.86 deg.

        Expected: 90 - 50.69 - 23.45 = 15.86 deg. Allow +-2 deg.
        Solar noon at lon 17.38 is approximately 10:48 UTC in December.
        """
        dt = datetime(2024, 12, 21, 10, 48, tzinfo=UTC)
        elevation, _ = ephemeris_lubcza.sun_position(dt)
        assert elevation == pytest.approx(15.86, abs=2.0)

    @pytest.mark.unit
    def test_midnight_negative_elevation(
        self,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """At midnight UTC, sun should be well below the horizon."""
        dt = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        elevation, _ = ephemeris_lubcza.sun_position(dt)
        assert elevation < 0

    @pytest.mark.unit
    def test_azimuth_at_noon_is_south(
        self,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """At solar noon in northern hemisphere, azimuth ~180 (south)."""
        dt = datetime(2024, 6, 21, 10, 52, tzinfo=UTC)
        _, azimuth = ephemeris_lubcza.sun_position(dt)
        assert azimuth == pytest.approx(180.0, abs=5.0)

    @pytest.mark.unit
    def test_invalid_latitude_rejected(self) -> None:
        """Latitude outside [-90, 90] must be rejected."""
        with pytest.raises(ValueError, match="latitude must be in"):
            EphemerisCalculator(latitude=91, longitude=0)

    @pytest.mark.unit
    def test_invalid_longitude_rejected(self) -> None:
        """Longitude outside [-180, 180] must be rejected."""
        with pytest.raises(ValueError, match="longitude must be in"):
            EphemerisCalculator(latitude=50, longitude=200)

    @pytest.mark.unit
    def test_sunrise_elevation_near_zero(
        self,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """At approximate sunrise, elevation should be near zero.

        Summer solstice sunrise at lon 17.38, lat ~51 is approximately
        02:55 UTC (accounting for longitude offset from zone meridian).
        """
        dt = datetime(2024, 6, 21, 2, 55, tzinfo=UTC)
        elevation, _ = ephemeris_lubcza.sun_position(dt)
        # Near sunrise — elevation should be close to zero (within 5 deg)
        assert abs(elevation) < 5.0

    @pytest.mark.unit
    def test_equinox_noon_elevation(self) -> None:
        """At equinox noon on the equator, elevation should be ~90 deg."""
        calc = EphemerisCalculator(latitude=0.0, longitude=0.0)
        dt = datetime(2024, 3, 20, 12, 0, tzinfo=UTC)
        elevation, _ = calc.sun_position(dt)
        assert elevation == pytest.approx(90.0, abs=3.0)

    @pytest.mark.unit
    def test_naive_datetime_treated_as_utc(
        self,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """Naive datetime gives the same result as UTC-aware datetime."""
        dt_naive = datetime(2024, 6, 21, 12, 0)
        dt_aware = datetime(2024, 6, 21, 12, 0, tzinfo=UTC)

        elev_naive, az_naive = ephemeris_lubcza.sun_position(dt_naive)
        elev_aware, az_aware = ephemeris_lubcza.sun_position(dt_aware)

        assert elev_naive == pytest.approx(elev_aware, abs=1e-10)
        assert az_naive == pytest.approx(az_aware, abs=1e-10)

    @pytest.mark.unit
    def test_morning_azimuth_is_east(
        self,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """In the morning, sun azimuth should be in the eastern half (< 180)."""
        dt = datetime(2024, 6, 21, 6, 0, tzinfo=UTC)
        elevation, azimuth = ephemeris_lubcza.sun_position(dt)
        # Sun should be up and east of south
        assert elevation > 0
        assert azimuth < 180.0

    @pytest.mark.unit
    def test_afternoon_azimuth_is_west(
        self,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """In the afternoon, sun azimuth should be in the western half (> 180)."""
        dt = datetime(2024, 6, 21, 17, 0, tzinfo=UTC)
        elevation, azimuth = ephemeris_lubcza.sun_position(dt)
        # Sun should be up and west of south
        assert elevation > 0
        assert azimuth > 180.0
