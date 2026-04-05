"""Unit tests for pumpahead.weather — CSVWeather source."""

from __future__ import annotations

from pathlib import Path

import pytest

from pumpahead.weather import (
    CSVConfig,
    CSVParseError,
    CSVWeather,
    WeatherDataError,
    WeatherSource,
)

# ---------------------------------------------------------------------------
# Helper — write a CSV string to a temp file
# ---------------------------------------------------------------------------


def _write_csv(tmp_path: Path, content: str, name: str = "weather.csv") -> Path:
    """Write *content* to a CSV file in *tmp_path* and return the path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASIC_CSV = """\
timestamp,T_out,GHI,wind_speed,humidity
2024-01-01T00:00:00,0.0,0.0,2.0,60.0
2024-01-01T01:00:00,1.0,50.0,3.0,55.0
2024-01-01T02:00:00,2.0,100.0,4.0,50.0
"""


@pytest.fixture()
def basic_csv(tmp_path: Path) -> Path:
    """Return path to a minimal 3-row CSV with hourly data."""
    return _write_csv(tmp_path, _BASIC_CSV)


# ---------------------------------------------------------------------------
# TestCSVWeatherLoad — constructor and loading
# ---------------------------------------------------------------------------


class TestCSVWeatherLoad:
    """Tests for CSVWeather file loading and parsing."""

    @pytest.mark.unit
    def test_loads_basic_csv(self, basic_csv: Path) -> None:
        """CSVWeather loads a well-formed CSV without error."""
        w = CSVWeather(basic_csv)
        assert isinstance(w, CSVWeather)

    @pytest.mark.unit
    def test_file_not_found(self, tmp_path: Path) -> None:
        """FileNotFoundError is raised for a non-existent path."""
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            CSVWeather(tmp_path / "does_not_exist.csv")

    @pytest.mark.unit
    def test_empty_csv_only_header(self, tmp_path: Path) -> None:
        """CSVParseError for a file with only a header row (0 data rows)."""
        p = _write_csv(
            tmp_path,
            "timestamp,T_out,GHI,wind_speed,humidity\n",
        )
        with pytest.raises(CSVParseError, match="at least 2 data rows"):
            CSVWeather(p)

    @pytest.mark.unit
    def test_single_row_csv(self, tmp_path: Path) -> None:
        """CSVParseError for a file with only 1 data row (need >= 2)."""
        content = """\
timestamp,T_out,GHI,wind_speed,humidity
2024-01-01T00:00:00,0.0,0.0,2.0,60.0
"""
        p = _write_csv(tmp_path, content)
        with pytest.raises(CSVParseError, match="at least 2 data rows"):
            CSVWeather(p)

    @pytest.mark.unit
    def test_missing_column_raises(self, tmp_path: Path) -> None:
        """CSVParseError when a required column is absent."""
        content = """\
timestamp,T_out,GHI,humidity
2024-01-01T00:00:00,0.0,0.0,60.0
2024-01-01T01:00:00,1.0,50.0,55.0
"""
        p = _write_csv(tmp_path, content)
        with pytest.raises(CSVParseError, match="missing columns"):
            CSVWeather(p)

    @pytest.mark.unit
    def test_bad_numeric_value_raises(self, tmp_path: Path) -> None:
        """CSVParseError when a numeric field is unparseable."""
        content = """\
timestamp,T_out,GHI,wind_speed,humidity
2024-01-01T00:00:00,0.0,0.0,2.0,60.0
2024-01-01T01:00:00,bad,50.0,3.0,55.0
"""
        p = _write_csv(tmp_path, content)
        with pytest.raises(CSVParseError, match="Error parsing row"):
            CSVWeather(p)

    @pytest.mark.unit
    def test_non_monotonic_timestamps_raises(self, tmp_path: Path) -> None:
        """CSVParseError when timestamps are not strictly increasing."""
        content = """\
timestamp,T_out,GHI,wind_speed,humidity
2024-01-01T02:00:00,2.0,100.0,4.0,50.0
2024-01-01T01:00:00,1.0,50.0,3.0,55.0
2024-01-01T00:00:00,0.0,0.0,2.0,60.0
"""
        p = _write_csv(tmp_path, content)
        with pytest.raises(CSVParseError, match="monotonically increasing"):
            CSVWeather(p)

    @pytest.mark.unit
    def test_csv_parse_error_is_weather_data_error(self) -> None:
        """CSVParseError is a subclass of WeatherDataError."""
        assert issubclass(CSVParseError, WeatherDataError)


# ---------------------------------------------------------------------------
# TestCSVWeatherGet — interpolation
# ---------------------------------------------------------------------------


class TestCSVWeatherGet:
    """Tests for CSVWeather.get() linear interpolation."""

    @pytest.mark.unit
    def test_exact_data_points(self, basic_csv: Path) -> None:
        """get() returns exact values at data point times."""
        w = CSVWeather(basic_csv)
        # t=0 min -> first row
        p0 = w.get(0.0)
        assert p0.T_out == pytest.approx(0.0)
        assert pytest.approx(0.0) == p0.GHI
        assert p0.wind_speed == pytest.approx(2.0)
        assert p0.humidity == pytest.approx(60.0)

        # t=60 min -> second row
        p1 = w.get(60.0)
        assert p1.T_out == pytest.approx(1.0)
        assert pytest.approx(50.0) == p1.GHI

    @pytest.mark.unit
    def test_midpoint_interpolation(self, basic_csv: Path) -> None:
        """get() linearly interpolates at the midpoint between data points."""
        w = CSVWeather(basic_csv)
        # t=30 min is midpoint between row 0 (t=0) and row 1 (t=60)
        p = w.get(30.0)
        assert p.T_out == pytest.approx(0.5)
        assert pytest.approx(25.0) == p.GHI
        assert p.wind_speed == pytest.approx(2.5)
        assert p.humidity == pytest.approx(57.5)

    @pytest.mark.unit
    def test_clamped_below_range(self, basic_csv: Path) -> None:
        """get() clamps to first values for t < t_min."""
        w = CSVWeather(basic_csv)
        p = w.get(-60.0)
        assert p.T_out == pytest.approx(0.0)
        assert pytest.approx(0.0) == p.GHI

    @pytest.mark.unit
    def test_clamped_above_range(self, basic_csv: Path) -> None:
        """get() clamps to last values for t > t_max."""
        w = CSVWeather(basic_csv)
        p = w.get(999.0)
        assert p.T_out == pytest.approx(2.0)
        assert pytest.approx(100.0) == p.GHI


# ---------------------------------------------------------------------------
# TestCSVWeatherProtocol — WeatherSource compliance
# ---------------------------------------------------------------------------


class TestCSVWeatherProtocol:
    """Tests for CSVWeather protocol compliance."""

    @pytest.mark.unit
    def test_satisfies_weather_source(self, basic_csv: Path) -> None:
        """CSVWeather must satisfy isinstance(x, WeatherSource)."""
        w = CSVWeather(basic_csv)
        assert isinstance(w, WeatherSource)


# ---------------------------------------------------------------------------
# TestCSVWeatherTimeRange — time_range_minutes property
# ---------------------------------------------------------------------------


class TestCSVWeatherTimeRange:
    """Tests for CSVWeather.time_range_minutes property."""

    @pytest.mark.unit
    def test_time_range(self, basic_csv: Path) -> None:
        """time_range_minutes returns (0, total_minutes)."""
        w = CSVWeather(basic_csv)
        t_min, t_max = w.time_range_minutes
        assert t_min == pytest.approx(0.0)
        # 3 rows hourly: 0h, 1h, 2h -> 0, 60, 120 minutes
        assert t_max == pytest.approx(120.0)


# ---------------------------------------------------------------------------
# TestCSVWeatherConfig — custom CSVConfig
# ---------------------------------------------------------------------------


class TestCSVWeatherConfig:
    """Tests for CSVWeather with custom CSVConfig."""

    @pytest.mark.unit
    def test_custom_delimiter_and_columns(self, tmp_path: Path) -> None:
        """CSVWeather respects delimiter and column name mapping."""
        content = """\
ts;temp;irradiance;wind;hum
2024-01-01T00:00:00;-5.0;0.0;1.0;70.0
2024-01-01T01:00:00;-3.0;100.0;2.0;65.0
"""
        p = _write_csv(tmp_path, content)
        cfg = CSVConfig(
            delimiter=";",
            timestamp_column="ts",
            t_out_column="temp",
            ghi_column="irradiance",
            wind_speed_column="wind",
            humidity_column="hum",
        )
        w = CSVWeather(p, config=cfg)
        p0 = w.get(0.0)
        assert p0.T_out == pytest.approx(-5.0)
        assert pytest.approx(0.0) == p0.GHI

    @pytest.mark.unit
    def test_custom_timestamp_format(self, tmp_path: Path) -> None:
        """CSVWeather parses timestamps with a custom strptime format."""
        content = """\
timestamp,T_out,GHI,wind_speed,humidity
01/01/2024 00:00,0.0,0.0,2.0,60.0
01/01/2024 01:00,1.0,50.0,3.0,55.0
"""
        p = _write_csv(tmp_path, content)
        cfg = CSVConfig(timestamp_format="%m/%d/%Y %H:%M")
        w = CSVWeather(p, config=cfg)
        assert w.get(30.0).T_out == pytest.approx(0.5)

    @pytest.mark.unit
    def test_whitespace_in_values_stripped(self, tmp_path: Path) -> None:
        """CSVWeather strips whitespace from numeric values."""
        content = """\
timestamp,T_out,GHI,wind_speed,humidity
2024-01-01T00:00:00, 0.0 , 0.0 , 2.0 , 60.0
2024-01-01T01:00:00, 1.0 , 50.0 , 3.0 , 55.0
"""
        p = _write_csv(tmp_path, content)
        w = CSVWeather(p)
        assert w.get(0.0).T_out == pytest.approx(0.0)
        assert w.get(60.0).T_out == pytest.approx(1.0)
