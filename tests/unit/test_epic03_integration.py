"""Integration tests for Epic 03 — Weather Data Sources pipeline.

Verifies end-to-end data flow:
    WeatherSource.get(t) -> WeatherPoint
        -> EphemerisCalculator.sun_position() -> SolarGainModel.compute()
        -> disturbance vector d = [T_out, Q_sol, Q_int]
        -> RCModel.step() / predict()

All tests are fast (no network, no filesystem beyond tmp_path),
deterministic, and use the @pytest.mark.unit marker.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from pumpahead.model import RCModel
from pumpahead.solar import (
    EphemerisCalculator,
    SolarGainModel,
    WindowConfig,
)
from pumpahead.weather import (
    CSVWeather,
    OpenMeteoHistorical,
    SyntheticWeather,
    WeatherPoint,
    WeatherSource,
)

# ---------------------------------------------------------------------------
# Helpers — OpenMeteo mock and CSV writer (local copies, small footprint)
# ---------------------------------------------------------------------------


def _make_response(
    n_hours: int = 24,
    t_out_start: float = -5.0,
    ghi_start: float = 0.0,
    wind_start: float = 2.0,
    hum_start: float = 60.0,
) -> dict[str, Any]:
    """Build a minimal Open-Meteo archive response dict."""
    times = [f"2024-01-01T{h:02d}:00" for h in range(n_hours)]
    temps: list[float | None] = [t_out_start + 0.5 * h for h in range(n_hours)]
    ghis: list[float | None] = [ghi_start + 10.0 * h for h in range(n_hours)]
    winds: list[float | None] = [wind_start for _ in range(n_hours)]
    hums: list[float | None] = [hum_start - 1.0 * h for h in range(n_hours)]
    return {
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "shortwave_radiation": ghis,
            "relative_humidity_2m": hums,
            "wind_speed_10m": winds,
        },
    }


def _mock_urlopen(response_data: dict[str, Any]) -> MagicMock:
    """Create a mock for ``urllib.request.urlopen`` returning *response_data*."""
    body = json.dumps(response_data).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _write_csv(tmp_path: Path, content: str, name: str = "weather.csv") -> Path:
    """Write *content* to a CSV file in *tmp_path* and return the path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# CSV data for multi-step tests
# ---------------------------------------------------------------------------

_HOURLY_CSV_4_ROWS = """\
timestamp,T_out,GHI,wind_speed,humidity
2024-01-01T00:00:00,-5.0,0.0,2.0,70.0
2024-01-01T01:00:00,-3.0,50.0,2.5,65.0
2024-01-01T02:00:00,-1.0,200.0,3.0,60.0
2024-01-01T03:00:00,0.0,350.0,3.5,55.0
"""


# ---------------------------------------------------------------------------
# Test 1: All WeatherSource implementations satisfy the protocol
# ---------------------------------------------------------------------------


class TestAllWeatherSourcesProtocol:
    """Parametrized test verifying all three implementations satisfy WeatherSource."""

    @staticmethod
    def _make_synthetic() -> SyntheticWeather:
        return SyntheticWeather.constant(T_out=-5.0, GHI=500.0)

    @staticmethod
    def _make_csv(tmp_path: Path) -> CSVWeather:
        csv_content = """\
timestamp,T_out,GHI,wind_speed,humidity
2024-01-01T00:00:00,-5.0,500.0,2.0,60.0
2024-01-01T01:00:00,-4.0,450.0,2.5,58.0
"""
        p = _write_csv(tmp_path, csv_content)
        return CSVWeather(p)

    @pytest.mark.unit
    def test_synthetic_satisfies_protocol(self) -> None:
        """SyntheticWeather satisfies WeatherSource and returns valid WeatherPoint."""
        src = self._make_synthetic()
        assert isinstance(src, WeatherSource)
        wp = src.get(0.0)
        assert isinstance(wp, WeatherPoint)
        for field in ("T_out", "GHI", "wind_speed", "humidity"):
            assert math.isfinite(getattr(wp, field))

    @pytest.mark.unit
    def test_csv_satisfies_protocol(self, tmp_path: Path) -> None:
        """CSVWeather satisfies WeatherSource and returns valid WeatherPoint."""
        src = self._make_csv(tmp_path)
        assert isinstance(src, WeatherSource)
        wp = src.get(0.0)
        assert isinstance(wp, WeatherPoint)
        for field in ("T_out", "GHI", "wind_speed", "humidity"):
            assert math.isfinite(getattr(wp, field))

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_openmeteo_satisfies_protocol(self, mock_url: MagicMock) -> None:
        """OpenMeteoHistorical satisfies WeatherSource protocol."""
        mock_url.return_value = _mock_urlopen(_make_response())
        src = OpenMeteoHistorical(
            lat=50.06, lon=19.94,
            start=date(2024, 1, 1), end=date(2024, 1, 1),
        )
        assert isinstance(src, WeatherSource)
        wp = src.get(0.0)
        assert isinstance(wp, WeatherPoint)
        for field in ("T_out", "GHI", "wind_speed", "humidity"):
            assert math.isfinite(getattr(wp, field))


# ---------------------------------------------------------------------------
# Test 2: Weather -> Solar gain pipeline
# ---------------------------------------------------------------------------


class TestWeatherToSolarGainPipeline:
    """Weather data flows through SolarGainModel to produce Q_sol."""

    @pytest.mark.unit
    def test_weather_to_solar_gain_with_known_sun_position(
        self,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """Q_sol matches analytic value for constant weather and fixed sun position."""
        weather = SyntheticWeather.constant(T_out=-5.0, GHI=500.0)
        wp = weather.get(0.0)

        # Fixed sun: elevation=30 deg, azimuth=180 deg (due south)
        elevation_deg = 30.0
        azimuth_deg = 180.0
        q_sol = solar_model.compute(
            wp.GHI, elevation_deg, azimuth_deg, [south_window]
        )

        # Expected: g_value * area * GHI * cos(azimuth_diff) * cos(elevation)
        # azimuth_diff = 180 - 180 = 0, cos(0)=1
        # cos(30 deg) = sqrt(3)/2 ~ 0.866
        expected = 0.6 * 3.0 * 500.0 * math.cos(math.radians(30.0))
        assert q_sol == pytest.approx(expected, rel=1e-6)
        assert q_sol > 0


# ---------------------------------------------------------------------------
# Test 3: Weather -> Ephemeris -> Solar pipeline (end-to-end)
# ---------------------------------------------------------------------------


class TestWeatherEphemerisSolarPipeline:
    """End-to-end chain: weather -> ephemeris -> solar model."""

    @pytest.mark.unit
    def test_summer_solstice_noon_south_window(
        self,
        ephemeris_lubcza: EphemerisCalculator,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """At summer solstice noon, south-facing window receives positive Q_sol."""
        weather = SyntheticWeather.constant(T_out=-5.0, GHI=500.0)
        wp = weather.get(0.0)

        # Summer solstice solar noon in Lubcza (approx 10:52 UTC)
        dt_noon = datetime(2024, 6, 21, 10, 52, tzinfo=UTC)
        elevation, azimuth = ephemeris_lubcza.sun_position(dt_noon)

        # Sun must be up at summer solstice noon
        assert elevation > 0, f"Expected positive elevation, got {elevation}"

        q_sol = solar_model.compute(wp.GHI, elevation, azimuth, [south_window])
        assert q_sol > 0, f"Expected positive Q_sol, got {q_sol}"


# ---------------------------------------------------------------------------
# Test 4: Weather -> Solar -> 3R3C disturbance vector
# ---------------------------------------------------------------------------


class TestWeatherToDisturbanceVector3R3C:
    """Integration: weather + solar -> disturbance vector -> 3R3C model step."""

    @pytest.mark.unit
    def test_single_step_3r3c(
        self,
        model_3r3c: RCModel,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """Weather-driven disturbance produces valid 3R3C state transition."""
        weather = SyntheticWeather.constant(T_out=-5.0, GHI=500.0)
        wp = weather.get(0.0)

        # Compute Q_sol with fixed sun position
        q_sol = solar_model.compute(wp.GHI, 30.0, 180.0, [south_window])

        # Construct 3R3C disturbance: d = [T_out, Q_sol, Q_int]
        d = np.array([wp.T_out, q_sol, 0.0])

        # Step the model with zero control input
        x0 = model_3r3c.reset()
        u = np.array([0.0])  # SISO, no heating
        x_next = model_3r3c.step(x0, u, d)

        # Verify valid state
        assert x_next.shape == (3,)
        assert np.all(np.isfinite(x_next))


# ---------------------------------------------------------------------------
# Test 5: Weather -> Solar -> 2R2C disturbance vector
# ---------------------------------------------------------------------------


class TestWeatherToDisturbanceVector2R2C:
    """Integration: weather + solar -> disturbance vector -> 2R2C model step."""

    @pytest.mark.unit
    def test_single_step_2r2c(
        self,
        model_2r2c: RCModel,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """Weather-driven disturbance produces valid 2R2C state transition."""
        weather = SyntheticWeather.constant(T_out=-5.0, GHI=500.0)
        wp = weather.get(0.0)

        # Compute Q_sol with fixed sun position
        q_sol = solar_model.compute(wp.GHI, 30.0, 180.0, [south_window])

        # Construct 2R2C disturbance: d = [T_out, Q_sol] (no Q_int)
        d = np.array([wp.T_out, q_sol])

        # Step the model with zero control input
        x0 = model_2r2c.reset()
        u = np.array([0.0])  # SISO, no heating
        x_next = model_2r2c.step(x0, u, d)

        # Verify valid state
        assert x_next.shape == (2,)
        assert np.all(np.isfinite(x_next))


# ---------------------------------------------------------------------------
# Test 6: CSV weather -> multi-step model simulation
# ---------------------------------------------------------------------------


class TestCSVWeatherMultiStepSimulation:
    """Multi-step simulation loop driven by CSVWeather data."""

    @pytest.mark.unit
    def test_csv_weather_drives_3step_simulation(
        self,
        tmp_path: Path,
        model_3r3c: RCModel,
        solar_model: SolarGainModel,
        south_window: WindowConfig,
    ) -> None:
        """CSVWeather feeding a 3-step sim produces physically reasonable trajectory."""
        csv_path = _write_csv(tmp_path, _HOURLY_CSV_4_ROWS)
        csv_weather = CSVWeather(csv_path)

        x = model_3r3c.reset()  # [20.0, 20.0, 20.0]
        u = np.array([0.0])  # No heating (SISO)
        trajectory = [x.copy()]

        # 3 steps at dt=60s (1 minute each), reading weather at t=0, 60, 120 min
        for step_idx in range(3):
            t_minutes = float(step_idx * 60)
            wp = csv_weather.get(t_minutes)
            q_sol = solar_model.compute(wp.GHI, 30.0, 180.0, [south_window])
            d = np.array([wp.T_out, q_sol, 0.0])
            x = model_3r3c.step(x, u, d)
            trajectory.append(x.copy())

        # 4 state vectors: initial + 3 steps
        assert len(trajectory) == 4

        for state in trajectory:
            assert state.shape == (3,)
            assert np.all(np.isfinite(state))
            # T_air physically reasonable: between -50 and 100 degC
            t_air = state[0]
            assert -50.0 < t_air < 100.0, f"T_air={t_air} out of plausible range"


# ---------------------------------------------------------------------------
# Test 7: Sinusoidal weather drives temperature variation in 3R3C model
# ---------------------------------------------------------------------------


class TestSinusoidalWeatherVariation:
    """24h sinusoidal outdoor temp must influence indoor air temperature."""

    @pytest.mark.unit
    def test_sinusoidal_outdoor_drives_indoor_variation(
        self,
        model_3r3c: RCModel,
    ) -> None:
        """Sinusoidal T_out over 24h produces measurable T_air range in 3R3C."""
        weather = SyntheticWeather.sinusoidal_t_out(
            baseline=5.0,
            amplitude=15.0,
            period_minutes=1440.0,
        )

        x = model_3r3c.reset()
        u = np.array([0.0])  # No heating
        t_air_values: list[float] = [float(x[0])]

        # 1440 steps at dt=60s = 24 hours
        for step in range(1440):
            t_minutes = float(step)
            wp = weather.get(t_minutes)
            # No solar, no internal gains
            d = np.array([wp.T_out, 0.0, 0.0])
            x = model_3r3c.step(x, u, d)
            t_air_values.append(float(x[0]))

        t_air_array = np.array(t_air_values)
        t_air_range = float(np.max(t_air_array) - np.min(t_air_array))

        # The sinusoidal outdoor variation (amplitude=15, range=30 degC)
        # must produce at least 1 degC of indoor variation over 24h
        assert t_air_range > 1.0, (
            f"T_air range {t_air_range:.3f} degC is too small; "
            f"sinusoidal outdoor temperature is not influencing indoor temperature"
        )

        # All values must be finite and plausible
        assert np.all(np.isfinite(t_air_array))
        assert np.all(t_air_array > -50.0)
        assert np.all(t_air_array < 100.0)
