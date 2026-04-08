"""Tests for HAWeatherSource — HA weather adapter for PumpAhead.

Uses the same module-scoped mocking pattern as ``test_ha_scaffold.py``
to inject mock ``homeassistant`` modules into ``sys.modules``, import
the adapter, run tests, and clean up afterward.
"""

from __future__ import annotations

import asyncio
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Module-scoped fixture: mock homeassistant and import HAWeatherSource
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ha_weather_mocks() -> Any:  # noqa: C901
    """Set up mock homeassistant modules, import HAWeatherSource, yield
    the imported symbols, and clean up sys.modules afterward.
    """
    # Record existing keys to avoid removing them in teardown.
    existing_ha_keys = {
        k for k in sys.modules if k.startswith(("homeassistant", "custom_components"))
    }

    # Create mock HA modules -------------------------------------------------
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

    # ConfigFlow base class mock (needed by config_flow.py in the package).
    class _FakeConfigFlow:
        DOMAIN: str = ""
        VERSION: int = 1
        hass: Any = None

        def __init_subclass__(cls, domain: str = "", **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            cls.DOMAIN = domain

    ha_config_entries.ConfigFlow = _FakeConfigFlow  # type: ignore[attr-defined]

    ha = types.ModuleType("homeassistant")

    # helpers mock chain (needed by coordinator.py / config_flow.py imports).
    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers_update_coordinator = types.ModuleType(
        "homeassistant.helpers.update_coordinator"
    )

    class _FakeDataUpdateCoordinator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.hass = args[0] if args else kwargs.get("hass")

        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

        async def async_config_entry_first_refresh(self) -> None:
            pass

    ha_helpers_update_coordinator.DataUpdateCoordinator = _FakeDataUpdateCoordinator  # type: ignore[attr-defined]

    ha_helpers_selector = types.ModuleType("homeassistant.helpers.selector")

    class _SelectorConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class _Selector:
        def __init__(self, config: Any = None) -> None:
            self.config = config

    ha_helpers_selector.EntitySelector = _Selector  # type: ignore[attr-defined]
    ha_helpers_selector.EntitySelectorConfig = _SelectorConfig  # type: ignore[attr-defined]
    ha_helpers_selector.NumberSelector = _Selector  # type: ignore[attr-defined]
    ha_helpers_selector.NumberSelectorConfig = _SelectorConfig  # type: ignore[attr-defined]
    ha_helpers_selector.NumberSelectorMode = types.SimpleNamespace(BOX="box")  # type: ignore[attr-defined]
    ha_helpers_selector.SelectSelector = _Selector  # type: ignore[attr-defined]
    ha_helpers_selector.SelectSelectorConfig = _SelectorConfig  # type: ignore[attr-defined]
    ha_helpers_selector.BooleanSelector = _Selector  # type: ignore[attr-defined]
    ha_helpers_selector.TextSelector = _Selector  # type: ignore[attr-defined]

    ha_data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    ha_data_entry_flow.FlowResult = dict  # type: ignore[attr-defined]

    # voluptuous mock (needed by config_flow.py).
    vol = types.ModuleType("voluptuous")

    class _VolSchema:
        def __init__(self, schema: Any) -> None:
            self._schema = schema

    class _VolRequired:
        def __init__(self, key: str, **kwargs: Any) -> None:
            self.key = key

        def __hash__(self) -> int:
            return hash(self.key)

        def __eq__(self, other: object) -> bool:
            if isinstance(other, _VolRequired):
                return self.key == other.key
            return self.key == other

    class _VolOptional:
        def __init__(self, key: str, **kwargs: Any) -> None:
            self.key = key

        def __hash__(self) -> int:
            return hash(self.key)

        def __eq__(self, other: object) -> bool:
            if isinstance(other, _VolOptional):
                return self.key == other.key
            return self.key == other

    vol.Schema = _VolSchema  # type: ignore[attr-defined]
    vol.Required = _VolRequired  # type: ignore[attr-defined]
    vol.Optional = _VolOptional  # type: ignore[attr-defined]

    # Inject into sys.modules ------------------------------------------------
    sys.modules["voluptuous"] = vol
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.update_coordinator"] = (
        ha_helpers_update_coordinator
    )
    sys.modules["homeassistant.helpers.selector"] = ha_helpers_selector
    sys.modules["homeassistant.data_entry_flow"] = ha_data_entry_flow

    repo_root_str = str(_REPO_ROOT)
    path_added = repo_root_str not in sys.path
    if path_added:
        sys.path.insert(0, repo_root_str)

    # Import adapter and core types ------------------------------------------
    from custom_components.pumpahead.ha_weather import HAWeatherSource
    from pumpahead.weather import WeatherPoint, WeatherSource

    class _Namespace:
        pass

    ns = _Namespace()
    ns.HAWeatherSource = HAWeatherSource  # type: ignore[attr-defined]
    ns.WeatherSource = WeatherSource  # type: ignore[attr-defined]
    ns.WeatherPoint = WeatherPoint  # type: ignore[attr-defined]

    yield ns

    # Teardown ---------------------------------------------------------------
    keys_to_remove = [
        k
        for k in sys.modules
        if k.startswith(("homeassistant", "custom_components", "voluptuous"))
        and k not in existing_ha_keys
    ]
    for k in keys_to_remove:
        del sys.modules[k]

    if path_added and repo_root_str in sys.path:
        sys.path.remove(repo_root_str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENTITY_ID = "weather.home"
_LATITUDE = 50.06
_LONGITUDE = 19.94


def _make_forecast_response(
    entity_id: str = _ENTITY_ID,
    hours: int = 48,
    start_temp: float = 5.0,
    cloud_coverage: float | None = 50.0,
    start_dt: datetime | None = None,
) -> dict[str, Any]:
    """Generate an HA-format forecast response dict.

    One entry per hour from *start_dt* (defaults to ``now(UTC)``).
    Temperature increments by 0.1 degC per hour.
    """
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


# ---------------------------------------------------------------------------
# TestHAWeatherSourceInit
# ---------------------------------------------------------------------------


class TestHAWeatherSourceInit:
    """Tests for HAWeatherSource construction and initial state."""

    @pytest.mark.unit
    def test_creates_with_valid_params(self, ha_weather_mocks: Any) -> None:
        """Constructor succeeds with valid entity ID and coordinates."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        assert src is not None

    @pytest.mark.unit
    def test_has_data_false_before_update(self, ha_weather_mocks: Any) -> None:
        """has_data must be False before the first async_update()."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        assert src.has_data is False

    @pytest.mark.unit
    def test_forecast_horizon_zero_before_update(self, ha_weather_mocks: Any) -> None:
        """forecast_horizon_hours must be 0 before the first update."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        assert src.forecast_horizon_hours == 0.0

    @pytest.mark.unit
    def test_get_returns_fallback_before_update(self, ha_weather_mocks: Any) -> None:
        """get() must return the default fallback before any update."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        point = src.get(0.0)
        assert isinstance(point, ha_weather_mocks.WeatherPoint)
        assert point.T_out == 10.0  # _DEFAULT_FALLBACK_T_OUT
        assert point.GHI == 0.0
        assert point.wind_speed == 0.0
        assert point.humidity == 50.0


# ---------------------------------------------------------------------------
# TestHAWeatherSourceUpdate
# ---------------------------------------------------------------------------


class TestHAWeatherSourceUpdate:
    """Tests for async_update() behaviour."""

    @pytest.mark.unit
    def test_update_parses_hourly_forecast(self, ha_weather_mocks: Any) -> None:
        """After update, has_data must be True and horizon > 0."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        hass = _make_hass_mock()
        asyncio.run(src.async_update(hass))
        assert src.has_data is True
        assert src.forecast_horizon_hours > 0

    @pytest.mark.unit
    def test_update_calls_ha_service(self, ha_weather_mocks: Any) -> None:
        """async_update must call weather.get_forecasts with correct args."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        hass = _make_hass_mock()
        asyncio.run(src.async_update(hass))
        hass.services.async_call.assert_awaited_once_with(
            "weather",
            "get_forecasts",
            {"entity_id": _ENTITY_ID, "type": "hourly"},
            blocking=True,
            return_response=True,
        )

    @pytest.mark.unit
    def test_update_reads_current_temp_for_fallback(
        self, ha_weather_mocks: Any
    ) -> None:
        """After update, fallback T_out must use the entity's current temp."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        hass = _make_hass_mock(current_temp=2.0)
        asyncio.run(src.async_update(hass))
        # Force fallback by making it stale.
        src._last_update = datetime.now(UTC) - timedelta(hours=7)
        point = src.get(0.0)
        assert point.T_out == 2.0

    @pytest.mark.unit
    def test_update_short_horizon_logs_warning(self, ha_weather_mocks: Any) -> None:
        """Forecast horizon < 24h must trigger a warning log."""
        response = _make_forecast_response(hours=12)  # only 12 h
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        hass = _make_hass_mock(forecast_response=response)
        with patch("custom_components.pumpahead.ha_weather._LOGGER") as mock_logger:
            asyncio.run(src.async_update(hass))
            # Check that warning was called with the Axiom 10 message.
            assert mock_logger.warning.called
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "Axiom 10" in warning_msg


# ---------------------------------------------------------------------------
# TestHAWeatherSourceGet
# ---------------------------------------------------------------------------


class TestHAWeatherSourceGet:
    """Tests for the get() method (WeatherSource protocol)."""

    @pytest.mark.unit
    def test_get_at_first_forecast_point(self, ha_weather_mocks: Any) -> None:
        """get(0) after update must return approximately the first forecast temp."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        hass = _make_hass_mock()
        asyncio.run(src.async_update(hass))
        point = src.get(0.0)
        # First entry has start_temp=5.0; there's a small elapsed time
        # since the forecast was built, so np.interp may shift slightly.
        assert abs(point.T_out - 5.0) < 1.0

    @pytest.mark.unit
    def test_get_interpolates_between_points(self, ha_weather_mocks: Any) -> None:
        """get() at 30 min between two hourly points must interpolate."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        hass = _make_hass_mock()
        asyncio.run(src.async_update(hass))
        # Temperature increases by 0.1 per hour.
        # At 30 min past the first point, interpolation should give ~5.05.
        point = src.get(30.0)
        assert 4.5 < point.T_out < 6.0  # reasonable range

    @pytest.mark.unit
    def test_get_clamps_beyond_range(self, ha_weather_mocks: Any) -> None:
        """get() beyond the forecast horizon must clamp (np.interp behaviour)."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        response = _make_forecast_response(hours=6, start_temp=5.0)
        hass = _make_hass_mock(forecast_response=response)
        asyncio.run(src.async_update(hass))
        # Way beyond the 6 h horizon (in minutes).
        point = src.get(1000.0)
        # np.interp clamps to the last value: 5.0 + 5 * 0.1 = 5.5
        assert abs(point.T_out - 5.5) < 1.0

    @pytest.mark.unit
    def test_get_returns_fallback_when_stale(self, ha_weather_mocks: Any) -> None:
        """get() must return fallback when data is older than max_age_hours."""
        src = ha_weather_mocks.HAWeatherSource(
            _ENTITY_ID, _LATITUDE, _LONGITUDE, max_age_hours=1.0
        )
        hass = _make_hass_mock()
        asyncio.run(src.async_update(hass))
        # Simulate data becoming stale.
        src._last_update = datetime.now(UTC) - timedelta(hours=2)
        point = src.get(0.0)
        assert point.GHI == 0.0
        assert point.wind_speed == 0.0

    @pytest.mark.unit
    def test_get_returns_fallback_when_no_data(self, ha_weather_mocks: Any) -> None:
        """get() must return fallback when async_update was never called."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        point = src.get(60.0)
        assert point.T_out == 10.0
        assert point.GHI == 0.0


# ---------------------------------------------------------------------------
# TestHAWeatherSourceGHI
# ---------------------------------------------------------------------------


class TestHAWeatherSourceGHI:
    """Tests for GHI estimation from cloud coverage."""

    @pytest.mark.unit
    def test_ghi_positive_daytime_with_cloud_data(self, ha_weather_mocks: Any) -> None:
        """GHI must be > 0 when sun is up and cloud data is provided."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        # Summer noon UTC — sun is well above the horizon at lat 50.
        dt = datetime(2024, 6, 21, 12, 0, 0, tzinfo=UTC)
        ghi = src._estimate_ghi(dt, 50.0)
        assert ghi > 0

    @pytest.mark.unit
    def test_ghi_zero_nighttime(self, ha_weather_mocks: Any) -> None:
        """GHI must be 0 when the sun is below the horizon."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        # Midnight in winter — sun is below the horizon.
        dt = datetime(2024, 12, 21, 0, 0, 0, tzinfo=UTC)
        ghi = src._estimate_ghi(dt, 0.0)
        assert ghi == 0.0

    @pytest.mark.unit
    def test_ghi_zero_when_no_cloud_data(self, ha_weather_mocks: Any) -> None:
        """GHI must be 0 when cloud_coverage is None (conservative default)."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        dt = datetime(2024, 6, 21, 12, 0, 0, tzinfo=UTC)
        ghi = src._estimate_ghi(dt, None)
        assert ghi == 0.0

    @pytest.mark.unit
    def test_ghi_reduced_by_cloud_coverage(self, ha_weather_mocks: Any) -> None:
        """Higher cloud coverage must produce lower GHI."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        dt = datetime(2024, 6, 21, 12, 0, 0, tzinfo=UTC)
        ghi_clear = src._estimate_ghi(dt, 0.0)
        ghi_cloudy = src._estimate_ghi(dt, 80.0)
        assert ghi_clear > ghi_cloudy > 0


# ---------------------------------------------------------------------------
# TestHAWeatherSourceFallback
# ---------------------------------------------------------------------------


class TestHAWeatherSourceFallback:
    """Tests for the fallback WeatherPoint."""

    @pytest.mark.unit
    def test_fallback_default_temp(self, ha_weather_mocks: Any) -> None:
        """Default fallback T_out must be 10.0 degC."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        point = src._fallback_point()
        assert point.T_out == 10.0

    @pytest.mark.unit
    def test_fallback_ghi_is_zero(self, ha_weather_mocks: Any) -> None:
        """Fallback GHI must be 0 (conservative per Axiom 9)."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        point = src._fallback_point()
        assert point.GHI == 0.0

    @pytest.mark.unit
    def test_fallback_humidity_is_default(self, ha_weather_mocks: Any) -> None:
        """Fallback humidity must be 50%."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        point = src._fallback_point()
        assert point.humidity == 50.0

    @pytest.mark.unit
    def test_fallback_wind_speed_is_zero(self, ha_weather_mocks: Any) -> None:
        """Fallback wind_speed must be 0."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        point = src._fallback_point()
        assert point.wind_speed == 0.0


# ---------------------------------------------------------------------------
# TestHAWeatherSourceProtocol
# ---------------------------------------------------------------------------


class TestHAWeatherSourceProtocol:
    """Tests verifying WeatherSource protocol compliance."""

    @pytest.mark.unit
    def test_satisfies_weather_source(self, ha_weather_mocks: Any) -> None:
        """HAWeatherSource must satisfy the WeatherSource protocol."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        assert isinstance(src, ha_weather_mocks.WeatherSource)


# ---------------------------------------------------------------------------
# TestHAWeatherSourceForecastParsing
# ---------------------------------------------------------------------------


class TestHAWeatherSourceForecastParsing:
    """Tests for _parse_forecast_response()."""

    @pytest.mark.unit
    def test_parse_standard_response_format(self, ha_weather_mocks: Any) -> None:
        """Standard HA format {entity_id: {"forecast": [...]}} is parsed."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        response = _make_forecast_response(hours=24)
        entries = src._parse_forecast_response(response)
        assert len(entries) == 24

    @pytest.mark.unit
    def test_parse_legacy_list_format(self, ha_weather_mocks: Any) -> None:
        """Legacy format {entity_id: [...]} is parsed as a bare list."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        now = datetime.now(UTC)
        entries_raw = [
            {
                "datetime": (now + timedelta(hours=h)).isoformat(),
                "temperature": 5.0 + h,
            }
            for h in range(5)
        ]
        response: dict[str, Any] = {_ENTITY_ID: entries_raw}
        entries = src._parse_forecast_response(response)
        assert len(entries) == 5

    @pytest.mark.unit
    def test_parse_empty_forecast(self, ha_weather_mocks: Any) -> None:
        """Empty forecast list must return an empty list."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        response: dict[str, Any] = {_ENTITY_ID: {"forecast": []}}
        entries = src._parse_forecast_response(response)
        assert entries == []

    @pytest.mark.unit
    def test_parse_skips_entries_with_none_temperature(
        self, ha_weather_mocks: Any
    ) -> None:
        """Entries with temperature=None must be filtered out."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        now = datetime.now(UTC)
        response: dict[str, Any] = {
            _ENTITY_ID: {
                "forecast": [
                    {
                        "datetime": now.isoformat(),
                        "temperature": 5.0,
                    },
                    {
                        "datetime": (now + timedelta(hours=1)).isoformat(),
                        "temperature": None,
                    },
                    {
                        "datetime": (now + timedelta(hours=2)).isoformat(),
                        "temperature": 6.0,
                    },
                ]
            }
        }
        entries = src._parse_forecast_response(response)
        assert len(entries) == 2

    @pytest.mark.unit
    def test_parse_defaults_missing_humidity(self, ha_weather_mocks: Any) -> None:
        """Forecast entries without humidity must use the default (50%)."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        now = datetime.now(UTC)
        response: dict[str, Any] = {
            _ENTITY_ID: {
                "forecast": [
                    {
                        "datetime": (now + timedelta(hours=h)).isoformat(),
                        "temperature": 5.0,
                    }
                    for h in range(24)
                ]
            }
        }
        hass = _make_hass_mock(forecast_response=response)
        asyncio.run(src.async_update(hass))
        point = src.get(0.0)
        assert point.humidity == 50.0

    @pytest.mark.unit
    def test_parse_defaults_missing_wind_speed(self, ha_weather_mocks: Any) -> None:
        """Forecast entries without wind_speed must default to 0.0."""
        src = ha_weather_mocks.HAWeatherSource(_ENTITY_ID, _LATITUDE, _LONGITUDE)
        now = datetime.now(UTC)
        response: dict[str, Any] = {
            _ENTITY_ID: {
                "forecast": [
                    {
                        "datetime": (now + timedelta(hours=h)).isoformat(),
                        "temperature": 5.0,
                    }
                    for h in range(24)
                ]
            }
        }
        hass = _make_hass_mock(forecast_response=response)
        asyncio.run(src.async_update(hass))
        point = src.get(0.0)
        assert point.wind_speed == 0.0
