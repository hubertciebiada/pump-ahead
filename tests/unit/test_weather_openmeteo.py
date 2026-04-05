"""Unit tests for pumpahead.weather — OpenMeteoHistorical source."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pumpahead.weather import (
    OpenMeteoHistorical,
    WeatherAPIError,
    WeatherDataError,
    WeatherSource,
)

# ---------------------------------------------------------------------------
# Helper — build a valid Open-Meteo API JSON response
# ---------------------------------------------------------------------------


def _make_response(
    n_hours: int = 24,
    t_out_start: float = -5.0,
    ghi_start: float = 0.0,
    wind_start: float = 2.0,
    hum_start: float = 60.0,
    *,
    null_indices: list[int] | None = None,
) -> dict[str, Any]:
    """Build a minimal Open-Meteo archive response dict.

    Args:
        n_hours: Number of hourly data points.
        t_out_start: Starting temperature (increases by 0.5 per hour).
        ghi_start: Starting GHI (increases by 10 per hour).
        wind_start: Starting wind speed (constant).
        hum_start: Starting humidity (decreases by 1 per hour).
        null_indices: Indices at which to insert None (null) values.

    Returns:
        A dict matching the Open-Meteo hourly JSON structure.
    """
    times = [f"2024-01-01T{h:02d}:00" for h in range(n_hours)]
    temps: list[float | None] = [t_out_start + 0.5 * h for h in range(n_hours)]
    ghis: list[float | None] = [ghi_start + 10.0 * h for h in range(n_hours)]
    winds: list[float | None] = [wind_start for _ in range(n_hours)]
    hums: list[float | None] = [hum_start - 1.0 * h for h in range(n_hours)]

    if null_indices:
        for i in null_indices:
            temps[i] = None
            ghis[i] = None

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


# ---------------------------------------------------------------------------
# TestOpenMeteoHistoricalLoad — constructor and fetching
# ---------------------------------------------------------------------------


class TestOpenMeteoHistoricalLoad:
    """Tests for OpenMeteoHistorical data loading."""

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_loads_from_api(self, mock_url: MagicMock) -> None:
        """OpenMeteoHistorical fetches data and constructs without error."""
        mock_url.return_value = _mock_urlopen(_make_response())
        w = OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 1),
        )
        assert isinstance(w, OpenMeteoHistorical)

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_api_called_with_correct_url(self, mock_url: MagicMock) -> None:
        """The request URL contains the correct lat/lon and date range."""
        mock_url.return_value = _mock_urlopen(_make_response())
        OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 7),
        )
        call_args = mock_url.call_args
        url: str = call_args[0][0]
        assert "latitude=50.06" in url
        assert "longitude=19.94" in url
        assert "start_date=2024-01-01" in url
        assert "end_date=2024-01-07" in url

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_api_error_raises_weather_api_error(self, mock_url: MagicMock) -> None:
        """WeatherAPIError on network failure."""
        import urllib.error

        mock_url.side_effect = urllib.error.URLError("Connection refused")
        with pytest.raises(WeatherAPIError, match="request failed"):
            OpenMeteoHistorical(
                lat=50.06,
                lon=19.94,
                start=date(2024, 1, 1),
                end=date(2024, 1, 1),
            )

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_invalid_json_raises(self, mock_url: MagicMock) -> None:
        """WeatherAPIError when response is not valid JSON."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_url.return_value = mock_resp
        with pytest.raises(WeatherAPIError, match="invalid data"):
            OpenMeteoHistorical(
                lat=50.06,
                lon=19.94,
                start=date(2024, 1, 1),
                end=date(2024, 1, 1),
            )

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_missing_hourly_key_raises(self, mock_url: MagicMock) -> None:
        """WeatherAPIError when response lacks 'hourly' key."""
        mock_url.return_value = _mock_urlopen({"latitude": 50.0})
        with pytest.raises(WeatherAPIError, match="missing 'hourly'"):
            OpenMeteoHistorical(
                lat=50.06,
                lon=19.94,
                start=date(2024, 1, 1),
                end=date(2024, 1, 1),
            )

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_all_null_channel_raises(self, mock_url: MagicMock) -> None:
        """WeatherAPIError when all values for a channel are null."""
        data = _make_response(n_hours=3)
        data["hourly"]["temperature_2m"] = [None, None, None]
        mock_url.return_value = _mock_urlopen(data)
        with pytest.raises(WeatherAPIError, match="All values are null"):
            OpenMeteoHistorical(
                lat=50.06,
                lon=19.94,
                start=date(2024, 1, 1),
                end=date(2024, 1, 1),
            )

    @pytest.mark.unit
    def test_weather_api_error_is_weather_data_error(self) -> None:
        """WeatherAPIError is a subclass of WeatherDataError."""
        assert issubclass(WeatherAPIError, WeatherDataError)


# ---------------------------------------------------------------------------
# TestOpenMeteoHistoricalGet — interpolation
# ---------------------------------------------------------------------------


class TestOpenMeteoHistoricalGet:
    """Tests for OpenMeteoHistorical.get() interpolation."""

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_exact_data_point(self, mock_url: MagicMock) -> None:
        """get(0) returns the first data point exactly."""
        mock_url.return_value = _mock_urlopen(_make_response())
        w = OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 1),
        )
        p = w.get(0.0)
        assert p.T_out == pytest.approx(-5.0)
        assert pytest.approx(0.0) == p.GHI
        assert p.wind_speed == pytest.approx(2.0)
        assert p.humidity == pytest.approx(60.0)

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_midpoint_interpolation(self, mock_url: MagicMock) -> None:
        """get() linearly interpolates between hourly data points."""
        mock_url.return_value = _mock_urlopen(_make_response())
        w = OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 1),
        )
        # Midpoint between hour 0 and hour 1 = 30 minutes
        # T_out: -5.0 to -4.5 -> midpoint = -4.75
        p = w.get(30.0)
        assert p.T_out == pytest.approx(-4.75)

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_clamped_beyond_range(self, mock_url: MagicMock) -> None:
        """get() clamps at edges for out-of-range times."""
        resp = _make_response(n_hours=3)
        mock_url.return_value = _mock_urlopen(resp)
        w = OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 1),
        )
        # Last point: t=120min, T_out = -5 + 0.5*2 = -4.0
        p = w.get(9999.0)
        assert p.T_out == pytest.approx(-4.0)

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_null_values_interpolated(self, mock_url: MagicMock) -> None:
        """Null values in the API response are filled via interpolation."""
        resp = _make_response(n_hours=5, null_indices=[2])
        mock_url.return_value = _mock_urlopen(resp)
        w = OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 1),
        )
        # Hour 2 was null; interpolated between hour 1 and hour 3
        # T_out: hour 1 = -4.5, hour 3 = -3.5 -> hour 2 = -4.0
        p = w.get(120.0)
        assert p.T_out == pytest.approx(-4.0)


# ---------------------------------------------------------------------------
# TestOpenMeteoHistoricalProtocol — WeatherSource compliance
# ---------------------------------------------------------------------------


class TestOpenMeteoHistoricalProtocol:
    """Tests for OpenMeteoHistorical protocol compliance."""

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_satisfies_weather_source(self, mock_url: MagicMock) -> None:
        """OpenMeteoHistorical must satisfy isinstance(x, WeatherSource)."""
        mock_url.return_value = _mock_urlopen(_make_response())
        w = OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 1),
        )
        assert isinstance(w, WeatherSource)


# ---------------------------------------------------------------------------
# TestOpenMeteoHistoricalTimeRange — time_range_minutes property
# ---------------------------------------------------------------------------


class TestOpenMeteoHistoricalTimeRange:
    """Tests for OpenMeteoHistorical.time_range_minutes property."""

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_time_range(self, mock_url: MagicMock) -> None:
        """time_range_minutes returns (0, total_minutes)."""
        mock_url.return_value = _mock_urlopen(_make_response(n_hours=24))
        w = OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 1),
        )
        t_min, t_max = w.time_range_minutes
        assert t_min == pytest.approx(0.0)
        # 24 hours: 0..23 -> 0..1380 minutes
        assert t_max == pytest.approx(23 * 60.0)


# ---------------------------------------------------------------------------
# TestOpenMeteoHistoricalCache — shelve caching
# ---------------------------------------------------------------------------


class TestOpenMeteoHistoricalCache:
    """Tests for OpenMeteoHistorical shelve caching."""

    @pytest.mark.unit
    @patch("pumpahead.weather.urllib.request.urlopen")
    def test_cache_prevents_second_fetch(
        self, mock_url: MagicMock, tmp_path: Path
    ) -> None:
        """Second construction with same params loads from cache, no API call."""
        mock_url.return_value = _mock_urlopen(_make_response(n_hours=3))

        # First call: fetches from API
        w1 = OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 1),
            cache_dir=tmp_path,
        )
        assert mock_url.call_count == 1

        # Second call: should use cache
        w2 = OpenMeteoHistorical(
            lat=50.06,
            lon=19.94,
            start=date(2024, 1, 1),
            end=date(2024, 1, 1),
            cache_dir=tmp_path,
        )
        # API should NOT be called again
        assert mock_url.call_count == 1

        # Both should produce the same data
        assert w1.get(0.0) == w2.get(0.0)
