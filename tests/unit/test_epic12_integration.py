"""Integration tests for Epic 12 -- Weather forecast and solar gain.

Verifies end-to-end cross-module wiring for the three sub-issues:
    #51 HAWeatherSource (custom_components/pumpahead/ha_weather.py)
    #52 GTI solar model (pumpahead/solar_gti.py)
    #53 Disturbance vector builder (pumpahead/disturbance_vector.py)

Tests verify the full pipeline:
    WeatherSource -> GTIModel -> DisturbanceBuilder -> RCModel.predict()

All tests are fast (no network, no filesystem beyond tmp_path),
deterministic, and use the ``@pytest.mark.unit`` marker.
"""

from __future__ import annotations

import ast
import asyncio
import math
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from pumpahead.disturbance_vector import (
    MPC_DT_SECONDS,
    MPC_HORIZON_STEPS,
    DisturbanceBuilder,
    InternalGainProfile,
)
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.solar import EphemerisCalculator, Orientation, WindowConfig
from pumpahead.solar_gti import GTIModel
from pumpahead.weather import CSVWeather, SyntheticWeather

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(tmp_path: Path, content: str, name: str = "weather.csv") -> Path:
    """Write *content* to a CSV file in *tmp_path* and return the path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# 48-row hourly CSV spanning 2 days -- temperature ramps, GHI has a
# daytime peak pattern (0 at night, positive during hours 6-18 each day).


def _build_csv_48_rows() -> str:
    """Build a 48-row hourly CSV with proper 2-day timestamps."""
    base = datetime(2024, 6, 21, 0, 0)
    rows = ["timestamp,T_out,GHI,wind_speed,humidity"]
    for h in range(48):
        ts = base + timedelta(hours=h)
        hour_of_day = ts.hour
        t_out = -5.0 + 0.5 * h
        if 6 <= hour_of_day <= 18:
            ghi = 500.0 * math.sin(math.pi * (hour_of_day - 6) / 12)
        else:
            ghi = 0.0
        rows.append(f"{ts.isoformat()},{t_out:.1f},{max(0.0, ghi):.1f},3.0,60.0")
    return "\n".join(rows)


_HOURLY_CSV_48_ROWS = _build_csv_48_rows()


# ---------------------------------------------------------------------------
# HA mocking fixture (module-scoped, same pattern as test_ha_weather.py)
# ---------------------------------------------------------------------------


_ENTITY_ID = "weather.home"
_LATITUDE = 50.69
_LONGITUDE = 17.38


def _make_forecast_response(
    entity_id: str = _ENTITY_ID,
    hours: int = 48,
    start_temp: float = 5.0,
    cloud_coverage: float | None = 50.0,
    start_dt: datetime | None = None,
) -> dict[str, Any]:
    """Generate an HA-format forecast response dict."""
    base_dt = start_dt or datetime.now(UTC)
    entries: list[dict[str, Any]] = []
    for h in range(hours):
        entry: dict[str, Any] = {
            "datetime": (base_dt + timedelta(hours=h)).isoformat(),
            "temperature": start_temp + h * 0.1,
            "humidity": 60,
            "wind_speed": 3.0,
        }
        if cloud_coverage is not None:
            entry["cloud_coverage"] = cloud_coverage
        entries.append(entry)
    return {entity_id: {"forecast": entries}}


def _make_hass_mock(
    entity_id: str = _ENTITY_ID,
    forecast_response: dict[str, Any] | None = None,
    current_temp: float = 5.0,
) -> MagicMock:
    """Create a MagicMock hass with services.async_call and states.get."""
    if forecast_response is None:
        forecast_response = _make_forecast_response(entity_id)

    hass = MagicMock()
    hass.services.async_call = AsyncMock(return_value=forecast_response)

    state_mock = MagicMock()
    state_mock.attributes = {
        "temperature": current_temp,
        "humidity": 60,
        "wind_speed": 3.0,
    }
    hass.states.get = MagicMock(return_value=state_mock)

    return hass


@pytest.fixture(scope="module")
def ha_weather_mocks() -> Any:  # noqa: C901
    """Set up mock homeassistant modules, import HAWeatherSource, yield
    the imported symbols, and clean up sys.modules afterward.
    """
    existing_ha_keys = {
        k for k in sys.modules if k.startswith(("homeassistant", "custom_components"))
    }

    # Create mock HA modules
    ha_const = types.ModuleType("homeassistant.const")

    class _Platform:
        SENSOR = "sensor"
        CLIMATE = "climate"

    ha_const.Platform = _Platform  # type: ignore[attr-defined]

    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = MagicMock  # type: ignore[attr-defined]

    ha_config_entries = types.ModuleType("homeassistant.config_entries")

    class _FakeConfigEntry:
        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

    ha_config_entries.ConfigEntry = _FakeConfigEntry  # type: ignore[attr-defined]

    ha = types.ModuleType("homeassistant")

    # Inject into sys.modules
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.config_entries"] = ha_config_entries

    repo_root_str = str(_REPO_ROOT)
    path_added = repo_root_str not in sys.path
    if path_added:
        sys.path.insert(0, repo_root_str)

    from pumpahead.weather import WeatherPoint, WeatherSource as WS  # noqa: I001

    from custom_components.pumpahead.ha_weather import HAWeatherSource

    class _Namespace:
        pass

    ns = _Namespace()
    ns.HAWeatherSource = HAWeatherSource  # type: ignore[attr-defined]
    ns.WeatherSource = WS  # type: ignore[attr-defined]
    ns.WeatherPoint = WeatherPoint  # type: ignore[attr-defined]

    yield ns

    # Teardown
    keys_to_remove = [
        k
        for k in sys.modules
        if k.startswith(("homeassistant", "custom_components"))
        and k not in existing_ha_keys
    ]
    for k in keys_to_remove:
        del sys.modules[k]

    if path_added and repo_root_str in sys.path:
        sys.path.remove(repo_root_str)


# ---------------------------------------------------------------------------
# TestWeatherSourceToGTIToDisturbance — Core pipeline integration
# ---------------------------------------------------------------------------


class TestWeatherSourceToGTIToDisturbance:
    """Core pipeline: WeatherSource -> GTIModel -> DisturbanceBuilder -> RCModel."""

    @pytest.mark.unit
    def test_synthetic_weather_gti_disturbance_full_horizon(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """SyntheticWeather.constant -> GTIModel -> DisturbanceBuilder -> shape (96, 3).

        Verifies T_out constant, Q_sol positive during daytime, Q_int constant.
        """
        weather = SyntheticWeather.constant(T_out=5.0, GHI=500.0)
        profile = InternalGainProfile.constant(100.0)

        builder = DisturbanceBuilder(
            weather=weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        # Start at summer midnight -- ensures some daytime steps
        start = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        assert d.shape == (MPC_HORIZON_STEPS, 3)
        # T_out constant at 5.0
        np.testing.assert_allclose(d[:, 0], 5.0)
        # Q_sol should be positive for at least some daytime steps
        assert np.any(d[:, 1] > 0), "Q_sol should be positive during daytime"
        # Q_int constant at 100.0
        np.testing.assert_allclose(d[:, 2], 100.0)
        # All values finite
        assert np.all(np.isfinite(d))

    @pytest.mark.unit
    def test_csv_weather_gti_disturbance_pipeline(
        self,
        tmp_path: Path,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """CSVWeather -> GTIModel -> DisturbanceBuilder -> shape (96, 3).

        Verifies T_out reflects the ramping CSV data and Q_sol is positive
        during daytime hours.
        """
        csv_path = _write_csv(tmp_path, _HOURLY_CSV_48_ROWS)
        csv_weather = CSVWeather(csv_path)
        profile = InternalGainProfile.constant(100.0)

        builder = DisturbanceBuilder(
            weather=csv_weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        start = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        assert d.shape == (MPC_HORIZON_STEPS, 3)
        assert np.all(np.isfinite(d))
        # T_out should ramp: first value near -5.0, later values higher
        assert d[0, 0] < d[-1, 0], "T_out should increase over horizon (ramp)"
        # Q_sol positive during daytime steps
        assert np.any(d[:, 1] > 0), "Q_sol should be positive during daytime"

    @pytest.mark.unit
    def test_disturbance_matrix_drives_model_predict_3r3c(
        self,
        params_3r3c: RCParams,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """DisturbanceBuilder.build_for_model -> RCModel.predict for 3R3C.

        Verifies trajectory shape (97, 3), all finite, T_air in plausible range.
        """
        weather = SyntheticWeather.constant(T_out=5.0, GHI=500.0)
        profile = InternalGainProfile.constant(100.0)
        model = RCModel(params_3r3c, ModelOrder.THREE, dt=float(MPC_DT_SECONDS))

        builder = DisturbanceBuilder(
            weather=weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        start = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        d = builder.build_for_model(start, model)
        assert d.shape == (MPC_HORIZON_STEPS, 3)

        x0 = model.reset()
        u_seq = np.zeros((MPC_HORIZON_STEPS, model.n_inputs))
        trajectory = model.predict(x0, u_seq, d)

        assert trajectory.shape == (MPC_HORIZON_STEPS + 1, 3)
        assert np.all(np.isfinite(trajectory))
        # T_air in plausible range (-50 to 100 degC)
        assert np.all(trajectory[:, 0] > -50.0)
        assert np.all(trajectory[:, 0] < 100.0)

    @pytest.mark.unit
    def test_disturbance_matrix_drives_model_predict_2r2c(
        self,
        params_2r2c: RCParams,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """DisturbanceBuilder.build_for_model -> RCModel.predict for 2R2C.

        Verifies trajectory shape (97, 2), all finite, T_air in plausible range.
        """
        weather = SyntheticWeather.constant(T_out=5.0, GHI=500.0)
        profile = InternalGainProfile.constant(100.0)
        model = RCModel(params_2r2c, ModelOrder.TWO, dt=float(MPC_DT_SECONDS))

        builder = DisturbanceBuilder(
            weather=weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        start = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        d = builder.build_for_model(start, model)
        assert d.shape == (MPC_HORIZON_STEPS, 2)

        x0 = model.reset()
        u_seq = np.zeros((MPC_HORIZON_STEPS, model.n_inputs))
        trajectory = model.predict(x0, u_seq, d)

        assert trajectory.shape == (MPC_HORIZON_STEPS + 1, 2)
        assert np.all(np.isfinite(trajectory))
        assert np.all(trajectory[:, 0] > -50.0)
        assert np.all(trajectory[:, 0] < 100.0)

    @pytest.mark.unit
    def test_orientation_differentiation_in_disturbance_vector(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """South vs East windows produce different Q_sol distributions.

        Acceptance criterion: Q_sol correctly differentiates window orientations.

        At latitude 50 in winter, the sun stays in the southern sky all day,
        so south-facing windows receive substantially more total Q_sol than
        east-facing windows over a full 24h horizon.
        """
        weather = SyntheticWeather.constant(T_out=0.0, GHI=400.0)
        profile = InternalGainProfile.constant(0.0)

        south_win = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        east_win = WindowConfig(Orientation.EAST, area_m2=3.0, g_value=0.6)

        builder_south = DisturbanceBuilder(
            weather=weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_win,),
            gain_profile=profile,
        )
        builder_east = DisturbanceBuilder(
            weather=weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(east_win,),
            gain_profile=profile,
        )

        # Winter solstice -- sun stays low and in the south all day
        start = datetime(2024, 12, 21, 0, 0, tzinfo=UTC)
        d_south = builder_south.build(start, n_disturbances=3)
        d_east = builder_east.build(start, n_disturbances=3)

        total_south = float(np.sum(d_south[:, 1]))
        total_east = float(np.sum(d_east[:, 1]))

        # Both should have some Q_sol
        assert total_south > 0, "South Q_sol should be positive"
        assert total_east > 0, "East Q_sol should be positive"
        # South should get more than east in winter
        assert total_south > total_east, (
            f"South Q_sol total ({total_south:.1f}) should exceed "
            f"East Q_sol total ({total_east:.1f}) in winter"
        )

    @pytest.mark.unit
    def test_seasonal_differentiation_in_disturbance_vector(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """Summer vs winter: different Q_sol for same south window.

        Acceptance criterion: Q_sol reflects seasonal variation.
        """
        weather = SyntheticWeather.constant(T_out=10.0, GHI=500.0)
        profile = InternalGainProfile.constant(0.0)

        builder = DisturbanceBuilder(
            weather=weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        summer_start = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        winter_start = datetime(2024, 12, 21, 0, 0, tzinfo=UTC)

        d_summer = builder.build(summer_start, n_disturbances=3)
        d_winter = builder.build(winter_start, n_disturbances=3)

        total_summer = float(np.sum(d_summer[:, 1]))
        total_winter = float(np.sum(d_winter[:, 1]))

        # Both should have some Q_sol (sun is up some of the time)
        assert total_summer > 0, "Summer Q_sol should be positive"
        assert total_winter > 0, "Winter Q_sol should be positive"
        # They should differ (seasonal variation)
        assert total_summer != total_winter, (
            "Summer and winter Q_sol totals should differ due to season"
        )

    @pytest.mark.unit
    def test_multi_window_room_q_sol(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
    ) -> None:
        """Room with 4-orientation windows: Q_sol non-negative."""
        windows = (
            WindowConfig(Orientation.NORTH, area_m2=2.0, g_value=0.6),
            WindowConfig(Orientation.EAST, area_m2=2.0, g_value=0.6),
            WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6),
            WindowConfig(Orientation.WEST, area_m2=2.0, g_value=0.6),
        )
        weather = SyntheticWeather.constant(T_out=10.0, GHI=600.0)
        profile = InternalGainProfile.constant(50.0)

        builder = DisturbanceBuilder(
            weather=weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=windows,
            gain_profile=profile,
        )

        start = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        # Q_sol should never be negative
        assert np.all(d[:, 1] >= 0.0), "Q_sol must be non-negative"
        # Some daytime steps should be positive
        assert np.any(d[:, 1] > 0), "Q_sol should be positive during daytime"


# ---------------------------------------------------------------------------
# TestHAWeatherSourceIntegration — HA adapter integration
# ---------------------------------------------------------------------------


class TestHAWeatherSourceIntegration:
    """Verify HAWeatherSource plugs into DisturbanceBuilder end-to-end."""

    @pytest.mark.unit
    def test_ha_weather_source_plugs_into_disturbance_builder(
        self,
        ha_weather_mocks: Any,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """HAWeatherSource -> DisturbanceBuilder -> (96, 3)."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        hass = _make_hass_mock()
        asyncio.run(src.async_update(hass))

        profile = InternalGainProfile.constant(100.0)
        builder = DisturbanceBuilder(
            weather=src,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        start = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        assert d.shape == (MPC_HORIZON_STEPS, 3)
        assert np.all(np.isfinite(d))

    @pytest.mark.unit
    def test_ha_weather_fallback_produces_valid_disturbance(
        self,
        ha_weather_mocks: Any,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """HAWeatherSource without async_update -> fallback: T_out=10.0, Q_sol=0."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        # No async_update call -- data not available

        profile = InternalGainProfile.constant(50.0)
        builder = DisturbanceBuilder(
            weather=src,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        start = datetime(2024, 6, 21, 10, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        assert d.shape == (MPC_HORIZON_STEPS, 3)
        assert np.all(np.isfinite(d))
        # Fallback T_out = 10.0 (from _DEFAULT_FALLBACK_T_OUT)
        np.testing.assert_allclose(d[:, 0], 10.0)
        # Fallback GHI = 0.0 -> Q_sol = 0.0
        np.testing.assert_allclose(d[:, 1], 0.0)

    @pytest.mark.unit
    def test_ha_weather_stale_data_produces_fallback_disturbance(
        self,
        ha_weather_mocks: Any,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """HAWeatherSource with stale data (>6h old) -> fallback values."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        hass = _make_hass_mock()
        asyncio.run(src.async_update(hass))

        # Simulate data becoming stale (7 hours ago)
        src._last_update = datetime.now(UTC) - timedelta(hours=7)

        profile = InternalGainProfile.constant(100.0)
        builder = DisturbanceBuilder(
            weather=src,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        start = datetime(2024, 6, 21, 10, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        assert d.shape == (MPC_HORIZON_STEPS, 3)
        assert np.all(np.isfinite(d))
        # Stale data should trigger fallback: GHI=0 -> Q_sol=0
        np.testing.assert_allclose(d[:, 1], 0.0)

    @pytest.mark.unit
    def test_ha_weather_source_satisfies_weather_source_for_builder(
        self,
        ha_weather_mocks: Any,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """HAWeatherSource satisfies WeatherSource and is accepted by builder."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)

        # Protocol check
        assert isinstance(src, ha_weather_mocks.WeatherSource)

        # Builder accepts it without TypeError
        profile = InternalGainProfile.constant(100.0)
        builder = DisturbanceBuilder(
            weather=src,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )
        assert builder is not None


# ---------------------------------------------------------------------------
# TestForecastHorizonCoverage — 24h coverage acceptance criterion
# ---------------------------------------------------------------------------


class TestForecastHorizonCoverage:
    """Verify disturbance matrix covers the full 24h MPC horizon."""

    @pytest.mark.unit
    def test_full_horizon_24h_coverage(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """48h forecast -> 96-step disturbance, all rows finite."""
        weather = SyntheticWeather.constant(T_out=5.0, GHI=300.0)
        profile = InternalGainProfile.constant(100.0)

        builder = DisturbanceBuilder(
            weather=weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        start = datetime(2024, 1, 15, 0, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        assert d.shape == (96, 3)
        assert np.all(np.isfinite(d))
        # Every row should have T_out populated (non-NaN)
        assert not np.any(np.isnan(d[:, 0]))

    @pytest.mark.unit
    def test_horizon_with_short_forecast_still_produces_output(
        self,
        gti_model: GTIModel,
        ephemeris_lubcza: EphemerisCalculator,
        south_window: WindowConfig,
    ) -> None:
        """12h of data -> still produces (96, 3) with finite values.

        SyntheticWeather.constant provides data at any t_minutes,
        so the builder can always fill the full horizon.
        """
        weather = SyntheticWeather.constant(T_out=5.0, GHI=200.0)
        profile = InternalGainProfile.constant(50.0)

        builder = DisturbanceBuilder(
            weather=weather,
            gti_model=gti_model,
            ephemeris=ephemeris_lubcza,
            windows=(south_window,),
            gain_profile=profile,
        )

        start = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        assert d.shape == (96, 3)
        assert np.all(np.isfinite(d))


# ---------------------------------------------------------------------------
# TestNoHTTPCalls — No direct HTTP imports in key modules
# ---------------------------------------------------------------------------


class TestNoHTTPCalls:
    """Verify no direct HTTP client imports in the three Epic 12 modules."""

    _FORBIDDEN_IMPORTS = {"urllib", "requests", "httpx", "aiohttp"}

    @staticmethod
    def _check_no_http_imports(filepath: Path) -> list[str]:
        """Return list of forbidden HTTP imports found in the given file.

        Uses AST parsing for reliable detection of import statements.
        """
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        violations: list[str] = []
        forbidden = {"urllib", "requests", "httpx", "aiohttp"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_module = alias.name.split(".")[0]
                    if root_module in forbidden:
                        violations.append(
                            f"import {alias.name} at line {node.lineno}"
                        )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
            ):
                root_module = node.module.split(".")[0]
                if root_module in forbidden:
                    violations.append(
                        f"from {node.module} import ... "
                        f"at line {node.lineno}"
                    )
        return violations

    @pytest.mark.unit
    def test_no_http_imports_in_ha_weather_module(self) -> None:
        """ha_weather.py must not import urllib, requests, httpx, or aiohttp."""
        filepath = _REPO_ROOT / "custom_components" / "pumpahead" / "ha_weather.py"
        violations = self._check_no_http_imports(filepath)
        assert violations == [], (
            f"ha_weather.py has forbidden HTTP imports: {violations}"
        )

    @pytest.mark.unit
    def test_no_http_imports_in_disturbance_vector(self) -> None:
        """disturbance_vector.py must not import urllib, requests, httpx, or aiohttp."""
        filepath = _REPO_ROOT / "pumpahead" / "disturbance_vector.py"
        violations = self._check_no_http_imports(filepath)
        assert violations == [], (
            f"disturbance_vector.py has forbidden HTTP imports: {violations}"
        )

    @pytest.mark.unit
    def test_no_http_imports_in_solar_gti(self) -> None:
        """solar_gti.py must not import urllib, requests, httpx, or aiohttp."""
        filepath = _REPO_ROOT / "pumpahead" / "solar_gti.py"
        violations = self._check_no_http_imports(filepath)
        assert violations == [], (
            f"solar_gti.py has forbidden HTTP imports: {violations}"
        )


# ---------------------------------------------------------------------------
# TestArchitecturalBoundary — No homeassistant imports in core
# ---------------------------------------------------------------------------


class TestArchitecturalBoundary:
    """Verify architectural boundaries between core and HA layer."""

    @pytest.mark.unit
    def test_core_library_no_homeassistant_imports(self) -> None:
        """No .py file in pumpahead/ must import homeassistant.

        This is the key architectural invariant: pumpahead/ is testable
        standalone without HA installed.
        """
        core_dir = _REPO_ROOT / "pumpahead"
        violations: list[str] = []

        for py_file in sorted(core_dir.glob("*.py")):
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("homeassistant"):
                            violations.append(
                                f"{py_file.name}: import {alias.name} "
                                f"at line {node.lineno}"
                            )
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.module is not None
                    and node.module.startswith("homeassistant")
                ):
                    violations.append(
                        f"{py_file.name}: from {node.module} "
                        f"import ... at line {node.lineno}"
                    )

        assert violations == [], (
            "Core library has homeassistant imports:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    @pytest.mark.unit
    def test_ha_weather_imports_from_core(self) -> None:
        """ha_weather.py imports WeatherPoint and EphemerisCalculator from core.

        Proves the adapter correctly depends on core, not the reverse.
        """
        filepath = _REPO_ROOT / "custom_components" / "pumpahead" / "ha_weather.py"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))

        core_imports: list[str] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.startswith("pumpahead.")
            ):
                for alias in node.names:
                    core_imports.append(alias.name)

        assert "WeatherPoint" in core_imports, (
            "ha_weather.py should import WeatherPoint from pumpahead.weather"
        )
        assert "EphemerisCalculator" in core_imports, (
            "ha_weather.py should import EphemerisCalculator from pumpahead.solar"
        )

    @pytest.mark.unit
    def test_disturbance_builder_imports_only_core(self) -> None:
        """disturbance_vector.py imports only from pumpahead (core) and stdlib/numpy."""
        filepath = _REPO_ROOT / "pumpahead" / "disturbance_vector.py"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))

        allowed_prefixes = (
            "pumpahead",
            "numpy",
            "np",
            "collections",
            "dataclasses",
            "datetime",
            "typing",
            "__future__",
            "cvxpy",  # deferred import in as_parameter() -- solver wrapper
        )

        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                root = node.module.split(".")[0]
                if root not in allowed_prefixes:
                    violations.append(
                        f"from {node.module} import ... at line {node.lineno}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in allowed_prefixes:
                        violations.append(
                            f"import {alias.name} at line {node.lineno}"
                        )

        assert violations == [], (
            f"disturbance_vector.py has non-core imports: {violations}"
        )
