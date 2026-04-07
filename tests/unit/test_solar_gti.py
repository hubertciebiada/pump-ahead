"""Comprehensive unit tests for pumpahead.solar_gti."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from pumpahead.solar import (
    EphemerisCalculator,
    Orientation,
    WindowConfig,
)
from pumpahead.solar_gti import (
    DEFAULT_ALBEDO,
    SOLAR_CONSTANT,
    GTIModel,
    cos_incidence_vertical,
    erbs_decomposition,
    extraterrestrial_horizontal,
    gti_vertical,
)

# ---------------------------------------------------------------------------
# TestExtraterrestrialHorizontal
# ---------------------------------------------------------------------------


class TestExtraterrestrialHorizontal:
    """Tests for the extraterrestrial horizontal irradiance function."""

    @pytest.mark.unit
    def test_zero_at_night(self) -> None:
        """Elevation <= 0 returns zero (sun below horizon)."""
        assert extraterrestrial_horizontal(-5.0) == 0.0
        assert extraterrestrial_horizontal(0.0) == 0.0

    @pytest.mark.unit
    def test_positive_for_positive_elevation(self) -> None:
        """Any positive elevation gives positive I0h."""
        result = extraterrestrial_horizontal(30.0, day_of_year=172)
        assert result > 0.0

    @pytest.mark.unit
    def test_equinox_noon_overhead(self) -> None:
        """At 90 deg elevation on equinox (day ~80), I0h ~ SOLAR_CONSTANT.

        sin(90 deg) = 1.0, eccentricity near 1.0 at equinox.
        """
        result = extraterrestrial_horizontal(90.0, day_of_year=80)
        assert result == pytest.approx(SOLAR_CONSTANT, rel=0.04)

    @pytest.mark.unit
    def test_eccentricity_range(self) -> None:
        """I0h at 90 deg elevation varies by ~3.3% over the year.

        Perihelion (day ~3): max eccentricity.
        Aphelion (day ~186): min eccentricity.
        """
        i0h_perihelion = extraterrestrial_horizontal(90.0, day_of_year=3)
        i0h_aphelion = extraterrestrial_horizontal(90.0, day_of_year=186)
        ratio = i0h_perihelion / i0h_aphelion
        # Expected ratio ~ 1.033^2 / (1-0.033)^2, but simplified
        assert 1.05 < ratio < 1.08

    @pytest.mark.unit
    def test_scales_with_sin_elevation(self) -> None:
        """I0h at 30 deg is half I0h at 90 deg (same day)."""
        i0h_90 = extraterrestrial_horizontal(90.0, day_of_year=172)
        i0h_30 = extraterrestrial_horizontal(30.0, day_of_year=172)
        assert i0h_30 == pytest.approx(i0h_90 * math.sin(math.radians(30.0)), rel=1e-6)


# ---------------------------------------------------------------------------
# TestErbsDecomposition
# ---------------------------------------------------------------------------


class TestErbsDecomposition:
    """Tests for the Erbs beam/diffuse decomposition."""

    @pytest.mark.unit
    def test_zero_ghi(self) -> None:
        """GHI=0 returns (0, 0)."""
        beam, diffuse = erbs_decomposition(0.0, 45.0)
        assert beam == 0.0
        assert diffuse == 0.0

    @pytest.mark.unit
    def test_negative_ghi(self) -> None:
        """Negative GHI (sensor error) returns (0, 0)."""
        beam, diffuse = erbs_decomposition(-100.0, 45.0)
        assert beam == 0.0
        assert diffuse == 0.0

    @pytest.mark.unit
    def test_night(self) -> None:
        """Elevation <= 0 returns (0, 0) regardless of GHI."""
        beam, diffuse = erbs_decomposition(500.0, 0.0)
        assert beam == 0.0
        assert diffuse == 0.0

        beam, diffuse = erbs_decomposition(500.0, -5.0)
        assert beam == 0.0
        assert diffuse == 0.0

    @pytest.mark.unit
    def test_beam_plus_diffuse_equals_ghi(self) -> None:
        """beam + diffuse must always equal GHI (conservation of energy)."""
        ghi = 600.0
        beam, diffuse = erbs_decomposition(ghi, 45.0, day_of_year=172)
        assert beam + diffuse == pytest.approx(ghi, rel=1e-10)

    @pytest.mark.unit
    def test_clear_sky_mostly_beam(self) -> None:
        """Clear sky (high kt): beam should dominate over diffuse.

        Use a moderate GHI that gives kt ~ 0.7.
        """
        elevation = 60.0
        i0h = extraterrestrial_horizontal(elevation, day_of_year=172)
        ghi = 0.7 * i0h  # kt = 0.7 (clear sky)
        beam, diffuse = erbs_decomposition(ghi, elevation, day_of_year=172)
        assert beam > diffuse

    @pytest.mark.unit
    def test_overcast_mostly_diffuse(self) -> None:
        """Overcast (low kt): diffuse should dominate.

        kt ~ 0.15 means almost all radiation is diffuse.
        """
        elevation = 45.0
        i0h = extraterrestrial_horizontal(elevation, day_of_year=172)
        ghi = 0.15 * i0h  # kt = 0.15 (overcast)
        beam, diffuse = erbs_decomposition(ghi, elevation, day_of_year=172)
        assert diffuse > beam

    @pytest.mark.unit
    def test_kt_clamped_to_one(self) -> None:
        """GHI exceeding I0h (kt > 1) is clamped; no crash."""
        elevation = 30.0
        i0h = extraterrestrial_horizontal(elevation, day_of_year=172)
        ghi = i0h * 1.5  # kt would be 1.5, clamped to 1.0
        beam, diffuse = erbs_decomposition(ghi, elevation, day_of_year=172)
        # Should still produce valid output
        assert beam >= 0.0
        assert diffuse >= 0.0
        assert beam + diffuse == pytest.approx(ghi, rel=1e-10)

    @pytest.mark.unit
    def test_both_non_negative(self) -> None:
        """Both beam and diffuse are always >= 0."""
        for ghi in [10.0, 100.0, 500.0, 1000.0]:
            for elev in [5.0, 30.0, 60.0, 85.0]:
                beam, diffuse = erbs_decomposition(ghi, elev, day_of_year=172)
                assert beam >= 0.0, f"beam negative at GHI={ghi}, elev={elev}"
                assert diffuse >= 0.0, f"diffuse negative at GHI={ghi}, elev={elev}"


# ---------------------------------------------------------------------------
# TestCosIncidenceVertical
# ---------------------------------------------------------------------------


class TestCosIncidenceVertical:
    """Tests for the cosine of incidence angle on vertical surfaces."""

    @pytest.mark.unit
    def test_facing_directly(self) -> None:
        """Sun directly facing a south window at elevation 0 gives cos=1."""
        cos_theta = cos_incidence_vertical(0.0, 180.0, 180.0)
        assert cos_theta == pytest.approx(1.0, abs=1e-10)

    @pytest.mark.unit
    def test_sun_behind_window(self) -> None:
        """Sun behind window (180 deg difference) gives cos=0."""
        cos_theta = cos_incidence_vertical(30.0, 0.0, 180.0)
        assert cos_theta == 0.0

    @pytest.mark.unit
    def test_perpendicular(self) -> None:
        """Sun at 90 deg to window normal gives cos=0."""
        cos_theta = cos_incidence_vertical(30.0, 90.0, 180.0)
        assert cos_theta == pytest.approx(0.0, abs=1e-10)

    @pytest.mark.unit
    def test_high_elevation_reduces_cos(self) -> None:
        """Higher sun elevation means less direct beam on vertical surface.

        cos_theta = cos(elevation) * cos(0) = cos(elevation).
        """
        cos_30 = cos_incidence_vertical(30.0, 180.0, 180.0)
        cos_60 = cos_incidence_vertical(60.0, 180.0, 180.0)
        assert cos_30 > cos_60
        assert cos_30 == pytest.approx(math.cos(math.radians(30.0)), abs=1e-10)
        assert cos_60 == pytest.approx(math.cos(math.radians(60.0)), abs=1e-10)

    @pytest.mark.unit
    def test_never_negative(self) -> None:
        """Result is always clamped to >= 0."""
        for sun_az in range(0, 360, 30):
            for win_az in range(0, 360, 30):
                cos_theta = cos_incidence_vertical(45.0, float(sun_az), float(win_az))
                assert cos_theta >= 0.0


# ---------------------------------------------------------------------------
# TestGTIVertical
# ---------------------------------------------------------------------------


class TestGTIVertical:
    """Tests for the gti_vertical function."""

    @pytest.mark.unit
    def test_beam_south_noon(self) -> None:
        """South window at solar noon should get full beam contribution.

        Sun at elevation=45, azimuth=180 facing south window (azimuth=180).
        """
        beam, diffuse = 500.0, 100.0
        ghi = beam + diffuse
        result = gti_vertical(
            beam, diffuse, ghi,
            sun_elevation_deg=45.0, sun_azimuth_deg=180.0,
            window_azimuth_deg=180.0,
        )
        # Beam component: DNI * cos(theta_incidence)
        # DNI = beam / sin(45) = 500/0.7071 ~ 707.1
        # cos_theta = cos(45)*cos(0) = 0.7071
        # I_beam_v = 707.1 * 0.7071 = 500.0
        # Diffuse = 100 * 0.5 = 50
        # Ground = 600 * 0.2 * 0.5 = 60
        expected_beam = beam  # beam/sin(45) * cos(45) = beam
        expected_diffuse = diffuse * 0.5
        expected_ground = ghi * DEFAULT_ALBEDO * 0.5
        expected = expected_beam + expected_diffuse + expected_ground
        assert result == pytest.approx(expected, rel=1e-6)

    @pytest.mark.unit
    def test_diffuse_always_present(self) -> None:
        """Even when beam=0, diffuse and ground components remain."""
        result = gti_vertical(
            beam=0.0, diffuse=200.0, ghi=200.0,
            sun_elevation_deg=45.0, sun_azimuth_deg=180.0,
            window_azimuth_deg=0.0,  # North window: no beam
        )
        expected = 200.0 * 0.5 + 200.0 * DEFAULT_ALBEDO * 0.5
        assert result == pytest.approx(expected, rel=1e-6)

    @pytest.mark.unit
    def test_ground_reflection(self) -> None:
        """Ground-reflected component scales with albedo."""
        result_low = gti_vertical(
            beam=0.0, diffuse=100.0, ghi=100.0,
            sun_elevation_deg=45.0, sun_azimuth_deg=180.0,
            window_azimuth_deg=0.0, albedo=0.1,
        )
        result_high = gti_vertical(
            beam=0.0, diffuse=100.0, ghi=100.0,
            sun_elevation_deg=45.0, sun_azimuth_deg=180.0,
            window_azimuth_deg=0.0, albedo=0.5,
        )
        # Diffuse is same (100*0.5=50), ground differs
        # Low: 50 + 100*0.1*0.5 = 55
        # High: 50 + 100*0.5*0.5 = 75
        assert result_low == pytest.approx(55.0, rel=1e-6)
        assert result_high == pytest.approx(75.0, rel=1e-6)

    @pytest.mark.unit
    def test_zero_albedo(self) -> None:
        """With albedo=0, no ground-reflected component."""
        result = gti_vertical(
            beam=0.0, diffuse=200.0, ghi=200.0,
            sun_elevation_deg=45.0, sun_azimuth_deg=180.0,
            window_azimuth_deg=0.0, albedo=0.0,
        )
        # Only diffuse: 200 * 0.5 = 100
        assert result == pytest.approx(100.0, rel=1e-6)

    @pytest.mark.unit
    def test_night_returns_zero(self) -> None:
        """All-zero inputs produce zero GTI."""
        result = gti_vertical(
            beam=0.0, diffuse=0.0, ghi=0.0,
            sun_elevation_deg=-10.0, sun_azimuth_deg=180.0,
            window_azimuth_deg=180.0,
        )
        assert result == 0.0

    @pytest.mark.unit
    def test_low_elevation_no_beam(self) -> None:
        """Below 1 deg elevation, beam is excluded to avoid DNI blowup."""
        result = gti_vertical(
            beam=100.0, diffuse=50.0, ghi=150.0,
            sun_elevation_deg=0.5, sun_azimuth_deg=180.0,
            window_azimuth_deg=180.0,
        )
        # Only diffuse + ground: 50*0.5 + 150*0.2*0.5 = 25 + 15 = 40
        expected = 50.0 * 0.5 + 150.0 * DEFAULT_ALBEDO * 0.5
        assert result == pytest.approx(expected, rel=1e-6)

    @pytest.mark.unit
    def test_never_negative(self) -> None:
        """Result is always >= 0."""
        result = gti_vertical(
            beam=0.0, diffuse=0.0, ghi=0.0,
            sun_elevation_deg=45.0, sun_azimuth_deg=180.0,
            window_azimuth_deg=180.0,
        )
        assert result >= 0.0


# ---------------------------------------------------------------------------
# TestGTIModel
# ---------------------------------------------------------------------------


class TestGTIModel:
    """Tests for the GTIModel class."""

    @pytest.mark.unit
    def test_q_sol_zero_at_night(self, gti_model: GTIModel) -> None:
        """Q_sol is zero when sun is below horizon."""
        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        result = gti_model.compute(
            ghi=0.0, elevation_deg=-5.0, azimuth_deg=180.0,
            windows=[south],
        )
        assert result == 0.0

    @pytest.mark.unit
    def test_q_sol_zero_elevation_exactly_zero(self, gti_model: GTIModel) -> None:
        """Q_sol is zero when elevation is exactly 0."""
        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        result = gti_model.compute(
            ghi=500.0, elevation_deg=0.0, azimuth_deg=180.0,
            windows=[south],
        )
        assert result == 0.0

    @pytest.mark.unit
    def test_south_greater_than_north_winter(self, gti_model: GTIModel) -> None:
        """South window GTI > north window GTI in winter (acceptance criterion).

        Sun at azimuth=180 (south), elevation=20 deg (typical winter noon lat 50).
        """
        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        north = WindowConfig(Orientation.NORTH, area_m2=3.0, g_value=0.6)

        q_south = gti_model.compute(
            ghi=300.0, elevation_deg=20.0, azimuth_deg=180.0,
            windows=[south], day_of_year=355,  # December
        )
        q_north = gti_model.compute(
            ghi=300.0, elevation_deg=20.0, azimuth_deg=180.0,
            windows=[north], day_of_year=355,
        )
        assert q_south > q_north
        assert q_south > 0

    @pytest.mark.unit
    def test_per_window_length(self, gti_model: GTIModel) -> None:
        """gti_per_window returns one value per window."""
        windows = [
            WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6),
            WindowConfig(Orientation.EAST, area_m2=2.0, g_value=0.5),
            WindowConfig(Orientation.NORTH, area_m2=1.5, g_value=0.6),
        ]
        gtis = gti_model.gti_per_window(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=windows,
        )
        assert len(gtis) == 3

    @pytest.mark.unit
    def test_sum_equals_compute(self, gti_model: GTIModel) -> None:
        """Sum of compute_per_window equals compute (total Q_sol)."""
        windows = [
            WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6),
            WindowConfig(Orientation.EAST, area_m2=2.0, g_value=0.5),
            WindowConfig(Orientation.WEST, area_m2=2.5, g_value=0.55),
        ]
        total = gti_model.compute(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=windows, day_of_year=172,
        )
        per_window = gti_model.compute_per_window(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=windows, day_of_year=172,
        )
        assert sum(per_window) == pytest.approx(total, rel=1e-10)

    @pytest.mark.unit
    def test_g_value_scaling(self, gti_model: GTIModel) -> None:
        """g=0.5 gives exactly half Q_sol compared to g=1.0 (linearity)."""
        w_full = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=1.0)
        w_half = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.5)

        q_full = gti_model.compute(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[w_full],
        )
        q_half = gti_model.compute(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[w_half],
        )
        assert q_half == pytest.approx(q_full * 0.5, rel=1e-10)

    @pytest.mark.unit
    def test_area_scaling(self, gti_model: GTIModel) -> None:
        """Doubling area doubles Q_sol (linearity)."""
        w_small = WindowConfig(Orientation.SOUTH, area_m2=2.0, g_value=0.6)
        w_large = WindowConfig(Orientation.SOUTH, area_m2=4.0, g_value=0.6)

        q_small = gti_model.compute(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[w_small],
        )
        q_large = gti_model.compute(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[w_large],
        )
        assert q_large == pytest.approx(q_small * 2.0, rel=1e-10)

    @pytest.mark.unit
    def test_multiple_orientations(self, gti_model: GTIModel) -> None:
        """Room with 4 orientations produces positive total Q_sol.

        Even windows facing away from the sun get diffuse + ground.
        """
        windows = [
            WindowConfig(Orientation.NORTH, area_m2=2.0, g_value=0.6),
            WindowConfig(Orientation.EAST, area_m2=2.0, g_value=0.6),
            WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6),
            WindowConfig(Orientation.WEST, area_m2=2.0, g_value=0.6),
        ]
        total = gti_model.compute(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=windows, day_of_year=172,
        )
        assert total > 0

    @pytest.mark.unit
    def test_east_morning_vs_afternoon(self, gti_model: GTIModel) -> None:
        """East window gets more Q_sol when sun is in the east (morning)."""
        east = WindowConfig(Orientation.EAST, area_m2=3.0, g_value=0.6)

        # Morning: sun in east (azimuth ~90)
        q_morning = gti_model.compute(
            ghi=400.0, elevation_deg=30.0, azimuth_deg=90.0,
            windows=[east], day_of_year=172,
        )
        # Afternoon: sun in west (azimuth ~270)
        q_afternoon = gti_model.compute(
            ghi=400.0, elevation_deg=30.0, azimuth_deg=270.0,
            windows=[east], day_of_year=172,
        )
        assert q_morning > q_afternoon

    @pytest.mark.unit
    def test_gti_greater_than_simple_model_south_noon(self) -> None:
        """GTI model should give higher Q_sol on south window at noon than simple.

        The simple model uses cos(azimuth_diff)*cos(elevation)*GHI,
        while GTI uses DNI (beam/sin(elev)) projected onto vertical,
        which is physically larger for vertical surfaces when elevation < 45 deg.
        """
        from pumpahead.solar import SolarGainModel

        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)

        simple = SolarGainModel()
        gti = GTIModel()

        ghi = 500.0
        elevation = 20.0  # Low winter sun
        azimuth = 180.0

        q_simple = simple.compute(ghi, elevation, azimuth, [south])
        q_gti = gti.compute(ghi, elevation, azimuth, [south], day_of_year=355)

        assert q_gti > q_simple

    @pytest.mark.unit
    def test_empty_windows(self, gti_model: GTIModel) -> None:
        """Empty windows list returns Q_sol=0."""
        total = gti_model.compute(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[],
        )
        assert total == 0.0

    @pytest.mark.unit
    def test_empty_windows_per_window(self, gti_model: GTIModel) -> None:
        """Empty windows list returns empty per-window list."""
        per_window = gti_model.compute_per_window(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[],
        )
        assert per_window == []

    @pytest.mark.unit
    def test_compute_per_window_returns_watts(self, gti_model: GTIModel) -> None:
        """compute_per_window returns values in Watts (GTI * area * g_value)."""
        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        gtis = gti_model.gti_per_window(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[south], day_of_year=172,
        )
        per_window = gti_model.compute_per_window(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[south], day_of_year=172,
        )
        # Q_sol = GTI * area * g_value
        expected = gtis[0] * 3.0 * 0.6
        assert per_window[0] == pytest.approx(expected, rel=1e-10)

    @pytest.mark.unit
    def test_all_cardinal_directions_positive_with_diffuse(
        self, gti_model: GTIModel
    ) -> None:
        """All four cardinal windows get positive Q_sol due to diffuse + ground."""
        for orientation in Orientation:
            w = WindowConfig(orientation, area_m2=3.0, g_value=0.6)
            q = gti_model.compute(
                ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
                windows=[w], day_of_year=172,
            )
            assert q > 0, f"{orientation.name} window should have positive Q_sol"

    @pytest.mark.unit
    def test_gti_per_window_night(self, gti_model: GTIModel) -> None:
        """gti_per_window returns zeros at night."""
        windows = [
            WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6),
            WindowConfig(Orientation.NORTH, area_m2=2.0, g_value=0.5),
        ]
        gtis = gti_model.gti_per_window(
            ghi=0.0, elevation_deg=-5.0, azimuth_deg=180.0,
            windows=windows,
        )
        assert all(g == 0.0 for g in gtis)

    @pytest.mark.unit
    def test_custom_albedo(self) -> None:
        """Model with higher albedo gives higher Q_sol for windows facing away."""
        north = WindowConfig(Orientation.NORTH, area_m2=3.0, g_value=0.6)

        model_low = GTIModel(albedo=0.1)
        model_high = GTIModel(albedo=0.5)

        q_low = model_low.compute(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[north], day_of_year=172,
        )
        q_high = model_high.compute(
            ghi=500.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[north], day_of_year=172,
        )
        assert q_high > q_low

    @pytest.mark.unit
    def test_negative_ghi_returns_zero(self, gti_model: GTIModel) -> None:
        """Negative GHI (sensor error) returns Q_sol=0."""
        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        result = gti_model.compute(
            ghi=-100.0, elevation_deg=45.0, azimuth_deg=180.0,
            windows=[south],
        )
        assert result == 0.0


# ---------------------------------------------------------------------------
# TestGTIModelWithEphemeris — integration with EphemerisCalculator
# ---------------------------------------------------------------------------


class TestGTIModelWithEphemeris:
    """Tests combining GTIModel with EphemerisCalculator.

    These verify the end-to-end workflow: compute sun position from
    datetime, then compute solar gain through windows.
    """

    @pytest.mark.unit
    def test_lubcza_summer_noon(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """Summer noon at Lubcza: south window gets significant Q_sol.

        June 21, solar noon (~10:52 UTC) at lat 50.69.
        High GHI (~800 W/m^2), high sun elevation (~63 deg).
        """
        dt = datetime(2024, 6, 21, 10, 52, tzinfo=UTC)
        elevation, azimuth = ephemeris_lubcza.sun_position(dt)
        day_of_year = dt.timetuple().tm_yday

        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        q_sol = gti_model.compute(
            ghi=800.0, elevation_deg=elevation, azimuth_deg=azimuth,
            windows=[south], day_of_year=day_of_year,
        )
        # At ~63 deg elevation, beam hits vertical surface at shallow angle,
        # but diffuse + ground + some beam still give real heat gain
        assert q_sol > 0

    @pytest.mark.unit
    def test_lubcza_winter_south_vs_north(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """Winter noon at Lubcza: south window Q_sol >> north window Q_sol.

        December 21, solar noon (~10:48 UTC). Low sun elevation (~16 deg),
        azimuth ~180 (due south).  South window should strongly dominate.
        """
        dt = datetime(2024, 12, 21, 10, 48, tzinfo=UTC)
        elevation, azimuth = ephemeris_lubcza.sun_position(dt)
        day_of_year = dt.timetuple().tm_yday

        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        north = WindowConfig(Orientation.NORTH, area_m2=3.0, g_value=0.6)

        q_south = gti_model.compute(
            ghi=200.0, elevation_deg=elevation, azimuth_deg=azimuth,
            windows=[south], day_of_year=day_of_year,
        )
        q_north = gti_model.compute(
            ghi=200.0, elevation_deg=elevation, azimuth_deg=azimuth,
            windows=[north], day_of_year=day_of_year,
        )

        assert q_south > q_north
        # South should be at least 3x north in winter (beam dominates)
        assert q_south > 3.0 * q_north

    @pytest.mark.unit
    def test_lubcza_midnight_zero(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """Midnight at Lubcza: Q_sol = 0 (acceptance criterion)."""
        dt = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        elevation, azimuth = ephemeris_lubcza.sun_position(dt)

        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        q_sol = gti_model.compute(
            ghi=0.0, elevation_deg=elevation, azimuth_deg=azimuth,
            windows=[south],
        )
        assert q_sol == 0.0

    @pytest.mark.unit
    def test_lubcza_morning_east_advantage(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """Morning at Lubcza: east window gets more Q_sol than west."""
        dt = datetime(2024, 6, 21, 6, 0, tzinfo=UTC)
        elevation, azimuth = ephemeris_lubcza.sun_position(dt)
        day_of_year = dt.timetuple().tm_yday

        east = WindowConfig(Orientation.EAST, area_m2=3.0, g_value=0.6)
        west = WindowConfig(Orientation.WEST, area_m2=3.0, g_value=0.6)

        q_east = gti_model.compute(
            ghi=400.0, elevation_deg=elevation, azimuth_deg=azimuth,
            windows=[east], day_of_year=day_of_year,
        )
        q_west = gti_model.compute(
            ghi=400.0, elevation_deg=elevation, azimuth_deg=azimuth,
            windows=[west], day_of_year=day_of_year,
        )
        assert q_east > q_west
