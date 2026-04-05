"""Weather data sources for building simulation.

Defines the ``WeatherSource`` protocol and concrete implementations:

* ``SyntheticWeather`` -- deterministic, analytically verifiable profiles
  for unit tests (stdlib only).
* ``CSVWeather`` -- loads historical data from a CSV file with linear
  interpolation to minute resolution (numpy).
* ``OpenMeteoHistorical`` -- fetches from the Open-Meteo archive API with
  shelve-based caching and numpy interpolation.

Units:
    T_out: degC
    GHI: W/m^2  (Global Horizontal Irradiance)
    wind_speed: m/s
    humidity: % (0-100)
    time: minutes (simulation convention)

Dependencies:
    SyntheticWeather uses stdlib only (math, dataclasses, enum, typing).
    CSVWeather and OpenMeteoHistorical additionally require numpy.
"""

from __future__ import annotations

import csv
import json
import math
import shelve
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# WeatherPoint — immutable snapshot of weather conditions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeatherPoint:
    """Immutable snapshot of weather conditions at a single instant.

    Attributes:
        T_out: Outdoor air temperature [degC].
        GHI: Global Horizontal Irradiance [W/m^2].
        wind_speed: Wind speed [m/s].
        humidity: Relative humidity [%] (0-100).
    """

    T_out: float
    GHI: float
    wind_speed: float
    humidity: float


# ---------------------------------------------------------------------------
# WeatherSource — structural-subtyping protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class WeatherSource(Protocol):
    """Protocol for objects that provide weather data at a given simulation time.

    Any class implementing a ``get(t_minutes: float) -> WeatherPoint`` method
    satisfies this protocol via structural subtyping.
    """

    def get(self, t_minutes: float) -> WeatherPoint:
        """Return weather conditions at simulation time *t_minutes*.

        Args:
            t_minutes: Simulation time in minutes.

        Returns:
            A ``WeatherPoint`` with conditions at the requested time.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WeatherDataError(Exception):
    """Base exception for weather data errors."""


class CSVParseError(WeatherDataError):
    """Raised when a CSV weather file cannot be parsed."""


class WeatherAPIError(WeatherDataError):
    """Raised when the Open-Meteo API request fails."""


class WeatherRangeError(WeatherDataError):
    """Raised when the requested time is outside the data range."""


# ---------------------------------------------------------------------------
# CSVConfig — configuration for CSV weather file parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CSVConfig:
    """Configuration for parsing a CSV weather data file.

    Attributes:
        delimiter: Column delimiter character.
        timestamp_column: Header name for the timestamp column.
        t_out_column: Header name for outdoor temperature [degC].
        ghi_column: Header name for GHI [W/m^2].
        wind_speed_column: Header name for wind speed [m/s].
        humidity_column: Header name for humidity [%].
        timestamp_format: strptime format string; empty string means ISO 8601.
        timezone_name: IANA timezone name (currently only "UTC" is supported).
    """

    delimiter: str = ","
    timestamp_column: str = "timestamp"
    t_out_column: str = "T_out"
    ghi_column: str = "GHI"
    wind_speed_column: str = "wind_speed"
    humidity_column: str = "humidity"
    timestamp_format: str = ""
    timezone_name: str = "UTC"


# ---------------------------------------------------------------------------
# ProfileKind — enumeration of channel profile shapes
# ---------------------------------------------------------------------------


class ProfileKind(Enum):
    """Kind of time-varying profile for a single weather channel."""

    CONSTANT = "constant"
    STEP = "step"
    RAMP = "ramp"
    SINUSOIDAL = "sinusoidal"


# ---------------------------------------------------------------------------
# ChannelProfile — describes one channel's time evolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChannelProfile:
    """Describes how a single weather channel evolves over time.

    Attributes:
        kind: Shape of the profile (constant, step, ramp, sinusoidal).
        baseline: Base value returned at t=0 (for constant/step/ramp)
            or the DC offset (for sinusoidal).
        amplitude: Magnitude of the change.
            * STEP: added to baseline after ``step_time_minutes``.
            * RAMP: total rise from baseline to baseline + amplitude.
            * SINUSOIDAL: peak deviation from baseline.
            * CONSTANT: ignored.
        period_minutes: Duration of one full cycle (SINUSOIDAL) or ramp
            duration (RAMP).  Must be > 0 for SINUSOIDAL and RAMP.
        step_time_minutes: Time at which the step occurs (STEP only).
    """

    kind: ProfileKind
    baseline: float = 0.0
    amplitude: float = 0.0
    period_minutes: float = 0.0
    step_time_minutes: float = 0.0

    def __post_init__(self) -> None:
        """Validate profile parameters."""
        if (
            self.kind in (ProfileKind.SINUSOIDAL, ProfileKind.RAMP)
            and self.period_minutes <= 0
        ):
            msg = (
                f"period_minutes must be > 0 for {self.kind.name}, "
                f"got {self.period_minutes}"
            )
            raise ValueError(msg)

    def evaluate(self, t_minutes: float) -> float:
        """Evaluate the profile value at simulation time *t_minutes*.

        Args:
            t_minutes: Simulation time in minutes.

        Returns:
            Channel value at the given time.
        """
        if self.kind == ProfileKind.CONSTANT:
            return self.baseline

        if self.kind == ProfileKind.STEP:
            if t_minutes < self.step_time_minutes:
                return self.baseline
            return self.baseline + self.amplitude

        if self.kind == ProfileKind.RAMP:
            progress = min(max(t_minutes / self.period_minutes, 0.0), 1.0)
            return self.baseline + self.amplitude * progress

        # SINUSOIDAL
        return self.baseline + self.amplitude * math.sin(
            2.0 * math.pi * t_minutes / self.period_minutes
        )


# ---------------------------------------------------------------------------
# SyntheticWeather — deterministic weather source for testing
# ---------------------------------------------------------------------------


class SyntheticWeather:
    """Deterministic weather source built from per-channel profiles.

    Each of the four weather channels (T_out, GHI, wind_speed, humidity)
    is driven by an independent ``ChannelProfile``, making the output
    analytically verifiable and perfectly reproducible.

    Typical usage::

        weather = SyntheticWeather.constant(T_out=-5.0, GHI=0.0)
        point = weather.get(t_minutes=60.0)
        assert point.T_out == -5.0
    """

    def __init__(
        self,
        t_out: ChannelProfile,
        ghi: ChannelProfile,
        wind_speed: ChannelProfile,
        humidity: ChannelProfile,
    ) -> None:
        """Initialize with one profile per weather channel.

        Args:
            t_out: Profile for outdoor temperature [degC].
            ghi: Profile for Global Horizontal Irradiance [W/m^2].
            wind_speed: Profile for wind speed [m/s].
            humidity: Profile for relative humidity [%].
        """
        self._t_out = t_out
        self._ghi = ghi
        self._wind_speed = wind_speed
        self._humidity = humidity

    def get(self, t_minutes: float) -> WeatherPoint:
        """Return weather conditions at simulation time *t_minutes*.

        Args:
            t_minutes: Simulation time in minutes.

        Returns:
            A ``WeatherPoint`` evaluated from the four channel profiles.
        """
        return WeatherPoint(
            T_out=self._t_out.evaluate(t_minutes),
            GHI=self._ghi.evaluate(t_minutes),
            wind_speed=self._wind_speed.evaluate(t_minutes),
            humidity=self._humidity.evaluate(t_minutes),
        )

    # -- Factory class methods -----------------------------------------------

    @classmethod
    def constant(
        cls,
        T_out: float = 0.0,
        GHI: float = 0.0,
        wind_speed: float = 0.0,
        humidity: float = 50.0,
    ) -> SyntheticWeather:
        """Create a weather source with all-constant channels.

        Args:
            T_out: Outdoor temperature [degC].
            GHI: Global Horizontal Irradiance [W/m^2].
            wind_speed: Wind speed [m/s].
            humidity: Relative humidity [%].

        Returns:
            A ``SyntheticWeather`` that returns the same values for any time.
        """
        return cls(
            t_out=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=T_out),
            ghi=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=GHI),
            wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=wind_speed),
            humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=humidity),
        )

    @classmethod
    def step_t_out(
        cls,
        baseline: float = 0.0,
        amplitude: float = 10.0,
        step_time_minutes: float = 60.0,
        GHI: float = 0.0,
        wind_speed: float = 0.0,
        humidity: float = 50.0,
    ) -> SyntheticWeather:
        """Create a weather source with a step change in T_out.

        T_out is *baseline* for t < step_time, then *baseline + amplitude*.
        All other channels are constant.

        Args:
            baseline: T_out before the step [degC].
            amplitude: Temperature change at the step [degC].
            step_time_minutes: Time of the step [minutes].
            GHI: Constant GHI [W/m^2].
            wind_speed: Constant wind speed [m/s].
            humidity: Constant humidity [%].

        Returns:
            A ``SyntheticWeather`` with a step profile on T_out.
        """
        return cls(
            t_out=ChannelProfile(
                kind=ProfileKind.STEP,
                baseline=baseline,
                amplitude=amplitude,
                step_time_minutes=step_time_minutes,
            ),
            ghi=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=GHI),
            wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=wind_speed),
            humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=humidity),
        )

    @classmethod
    def ramp_t_out(
        cls,
        baseline: float = 0.0,
        amplitude: float = 10.0,
        period_minutes: float = 120.0,
        GHI: float = 0.0,
        wind_speed: float = 0.0,
        humidity: float = 50.0,
    ) -> SyntheticWeather:
        """Create a weather source with a linear ramp in T_out.

        T_out ramps from *baseline* to *baseline + amplitude* over
        *period_minutes*, then stays at the final value.

        Args:
            baseline: Starting T_out [degC].
            amplitude: Total temperature rise [degC].
            period_minutes: Duration of the ramp [minutes].
            GHI: Constant GHI [W/m^2].
            wind_speed: Constant wind speed [m/s].
            humidity: Constant humidity [%].

        Returns:
            A ``SyntheticWeather`` with a ramp profile on T_out.
        """
        return cls(
            t_out=ChannelProfile(
                kind=ProfileKind.RAMP,
                baseline=baseline,
                amplitude=amplitude,
                period_minutes=period_minutes,
            ),
            ghi=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=GHI),
            wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=wind_speed),
            humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=humidity),
        )

    @classmethod
    def sinusoidal_t_out(
        cls,
        baseline: float = 0.0,
        amplitude: float = 10.0,
        period_minutes: float = 1440.0,
        GHI: float = 0.0,
        wind_speed: float = 0.0,
        humidity: float = 50.0,
    ) -> SyntheticWeather:
        """Create a weather source with sinusoidal T_out variation.

        T_out = baseline + amplitude * sin(2*pi*t / period_minutes).

        Args:
            baseline: Mean outdoor temperature [degC].
            amplitude: Peak deviation from baseline [degC].
            period_minutes: Full cycle duration [minutes] (default 1440 = 1 day).
            GHI: Constant GHI [W/m^2].
            wind_speed: Constant wind speed [m/s].
            humidity: Constant humidity [%].

        Returns:
            A ``SyntheticWeather`` with a sinusoidal profile on T_out.
        """
        return cls(
            t_out=ChannelProfile(
                kind=ProfileKind.SINUSOIDAL,
                baseline=baseline,
                amplitude=amplitude,
                period_minutes=period_minutes,
            ),
            ghi=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=GHI),
            wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=wind_speed),
            humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=humidity),
        )


# ---------------------------------------------------------------------------
# CSVWeather — load weather data from a CSV file
# ---------------------------------------------------------------------------


class CSVWeather:
    """Weather source that loads data from a CSV file.

    The CSV must contain a timestamp column and columns for T_out, GHI,
    wind_speed, and humidity.  Data is linearly interpolated to minute
    resolution using ``numpy.interp``.

    Typical usage::

        weather = CSVWeather(Path("data/krakow_2024.csv"))
        point = weather.get(t_minutes=120.0)
    """

    def __init__(self, path: Path, config: CSVConfig | None = None) -> None:
        """Load and parse a CSV weather data file.

        Args:
            path: Path to the CSV file.
            config: Column mapping and parsing options.  Uses defaults if None.

        Raises:
            FileNotFoundError: If *path* does not exist.
            CSVParseError: If the file cannot be parsed or contains < 2 rows.
        """
        self._config = config or CSVConfig()
        if not path.exists():
            msg = f"CSV file not found: {path}"
            raise FileNotFoundError(msg)

        timestamps: list[float] = []
        t_out_vals: list[float] = []
        ghi_vals: list[float] = []
        wind_vals: list[float] = []
        hum_vals: list[float] = []

        try:
            with path.open(newline="") as f:
                reader = csv.DictReader(f, delimiter=self._config.delimiter)
                if reader.fieldnames is None:
                    msg = f"CSV file has no header row: {path}"
                    raise CSVParseError(msg)

                required = {
                    self._config.timestamp_column,
                    self._config.t_out_column,
                    self._config.ghi_column,
                    self._config.wind_speed_column,
                    self._config.humidity_column,
                }
                missing = required - set(reader.fieldnames)
                if missing:
                    msg = f"CSV missing columns: {sorted(missing)}"
                    raise CSVParseError(msg)

                for row_num, row in enumerate(reader, start=2):
                    try:
                        ts_str = row[self._config.timestamp_column].strip()
                        ts = self._parse_timestamp(ts_str)
                        timestamps.append(ts)
                        t_out_vals.append(float(row[self._config.t_out_column].strip()))
                        ghi_vals.append(float(row[self._config.ghi_column].strip()))
                        wind_vals.append(
                            float(row[self._config.wind_speed_column].strip())
                        )
                        hum_vals.append(
                            float(row[self._config.humidity_column].strip())
                        )
                    except (ValueError, KeyError) as exc:
                        msg = f"Error parsing row {row_num}: {exc}"
                        raise CSVParseError(msg) from exc
        except CSVParseError:
            raise
        except OSError as exc:
            msg = f"Cannot read CSV file: {path}: {exc}"
            raise CSVParseError(msg) from exc

        if len(timestamps) < 2:
            msg = f"CSV file must contain at least 2 data rows, got {len(timestamps)}"
            raise CSVParseError(msg)

        # Convert absolute timestamps to minutes relative to the first entry.
        ts_array = np.array(timestamps)
        t0 = ts_array[0]
        self._t_minutes: NDArray[np.float64] = (ts_array - t0) / 60.0
        self._t_out: NDArray[np.float64] = np.array(t_out_vals, dtype=np.float64)
        self._ghi: NDArray[np.float64] = np.array(ghi_vals, dtype=np.float64)
        self._wind_speed: NDArray[np.float64] = np.array(wind_vals, dtype=np.float64)
        self._humidity: NDArray[np.float64] = np.array(hum_vals, dtype=np.float64)

        # Verify monotonically increasing time
        if not np.all(np.diff(self._t_minutes) > 0):
            msg = "CSV timestamps must be strictly monotonically increasing"
            raise CSVParseError(msg)

    def _parse_timestamp(self, ts_str: str) -> float:
        """Parse a timestamp string to seconds since epoch (UTC).

        Args:
            ts_str: Timestamp string from the CSV.

        Returns:
            Seconds since epoch as a float.
        """
        fmt = self._config.timestamp_format
        if fmt:
            dt = datetime.strptime(ts_str, fmt).replace(tzinfo=UTC)
        else:
            # ISO 8601 auto-parse
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()

    def get(self, t_minutes: float) -> WeatherPoint:
        """Return interpolated weather conditions at simulation time *t_minutes*.

        Values are clamped at the edges (no extrapolation beyond the data range).

        Args:
            t_minutes: Simulation time in minutes (relative to first CSV row).

        Returns:
            A ``WeatherPoint`` with linearly interpolated values.
        """
        return WeatherPoint(
            T_out=float(np.interp(t_minutes, self._t_minutes, self._t_out)),
            GHI=float(np.interp(t_minutes, self._t_minutes, self._ghi)),
            wind_speed=float(np.interp(t_minutes, self._t_minutes, self._wind_speed)),
            humidity=float(np.interp(t_minutes, self._t_minutes, self._humidity)),
        )

    @property
    def time_range_minutes(self) -> tuple[float, float]:
        """Return ``(t_min, t_max)`` of available data in minutes."""
        return (float(self._t_minutes[0]), float(self._t_minutes[-1]))


# ---------------------------------------------------------------------------
# OpenMeteoHistorical — fetch from Open-Meteo archive API
# ---------------------------------------------------------------------------

_OPEN_METEO_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"


class OpenMeteoHistorical:
    """Weather source that fetches historical data from the Open-Meteo archive API.

    Hourly data is fetched for the requested date range and linearly
    interpolated to minute resolution.  A ``shelve``-based cache prevents
    repeated API calls for the same query.

    Typical usage::

        weather = OpenMeteoHistorical(
            lat=50.06, lon=19.94,
            start=date(2024, 1, 1), end=date(2024, 1, 7),
        )
        point = weather.get(t_minutes=120.0)
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        start: date,
        end: date,
        cache_dir: Path | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Fetch (or load from cache) historical weather data.

        Args:
            lat: Latitude in decimal degrees.
            lon: Longitude in decimal degrees.
            start: First date of the range (inclusive).
            end: Last date of the range (inclusive).
            cache_dir: Directory for the shelve cache file.  If None, no cache
                is used.
            timeout_seconds: HTTP request timeout in seconds.

        Raises:
            WeatherAPIError: If the API request fails or returns invalid data.
        """
        self._lat = lat
        self._lon = lon
        self._start = start
        self._end = end
        self._timeout = timeout_seconds

        cache_key = f"openmeteo_{lat:.4f}_{lon:.4f}_{start}_{end}"
        raw_data = self._load_from_cache(cache_dir, cache_key)

        if raw_data is None:
            raw_data = self._fetch(lat, lon, start, end)
            if cache_dir is not None:
                self._save_to_cache(cache_dir, cache_key, raw_data)

        self._build_arrays(raw_data)

    def _load_from_cache(
        self, cache_dir: Path | None, key: str
    ) -> dict[str, object] | None:
        """Attempt to load cached API response."""
        if cache_dir is None:
            return None
        db_path = str(cache_dir / "openmeteo_cache")
        try:
            with shelve.open(db_path, flag="r") as db:
                if key in db:
                    raw = db[key]
                    result: dict[str, object] = dict(raw)
                    return result
        except Exception:  # noqa: BLE001 -- shelve can raise various errors
            pass
        return None

    def _save_to_cache(
        self, cache_dir: Path, key: str, data: dict[str, object]
    ) -> None:
        """Persist API response to the shelve cache."""
        cache_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(cache_dir / "openmeteo_cache")
        try:
            with shelve.open(db_path) as db:
                db[key] = data
        except Exception:  # noqa: BLE001 -- best-effort caching
            pass

    def _fetch(
        self, lat: float, lon: float, start: date, end: date
    ) -> dict[str, object]:
        """Fetch hourly data from the Open-Meteo archive API.

        Raises:
            WeatherAPIError: On HTTP or JSON errors.
        """
        params = (
            f"latitude={lat}&longitude={lon}"
            f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
            f"&hourly=temperature_2m,shortwave_radiation,"
            f"relative_humidity_2m,wind_speed_10m"
            f"&timezone=UTC"
        )
        url = f"{_OPEN_METEO_BASE_URL}?{params}"

        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as resp:
                body = resp.read().decode("utf-8")
                data: dict[str, object] = json.loads(body)
        except urllib.error.URLError as exc:
            msg = f"Open-Meteo API request failed: {exc}"
            raise WeatherAPIError(msg) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            msg = f"Open-Meteo API returned invalid data: {exc}"
            raise WeatherAPIError(msg) from exc

        if "hourly" not in data:
            msg = "Open-Meteo API response missing 'hourly' key"
            raise WeatherAPIError(msg)

        return data

    def _build_arrays(self, data: dict[str, object]) -> None:
        """Convert API JSON to internal numpy arrays.

        Raises:
            WeatherAPIError: If the data is missing required fields or all
                values are null for a channel.
        """
        hourly = data.get("hourly")
        if not isinstance(hourly, dict):
            msg = "Open-Meteo response 'hourly' is not a dict"
            raise WeatherAPIError(msg)

        time_list = hourly.get("time")
        if not isinstance(time_list, list) or len(time_list) < 2:
            msg = "Open-Meteo response must contain at least 2 hourly timestamps"
            raise WeatherAPIError(msg)

        # Parse ISO timestamps to minutes relative to first entry
        epoch_seconds: list[float] = []
        for ts_str in time_list:
            if not isinstance(ts_str, str):
                msg = f"Expected string timestamp, got {type(ts_str)}"
                raise WeatherAPIError(msg)
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            epoch_seconds.append(dt.timestamp())

        ts_arr = np.array(epoch_seconds)
        t0 = ts_arr[0]
        self._t_minutes: NDArray[np.float64] = (ts_arr - t0) / 60.0

        # Channel mapping: API key -> attribute name
        channel_keys = [
            "temperature_2m",
            "shortwave_radiation",
            "relative_humidity_2m",
            "wind_speed_10m",
        ]
        parsed: dict[str, NDArray[np.float64]] = {}

        for api_key in channel_keys:
            raw_list = hourly.get(api_key)
            if not isinstance(raw_list, list):
                msg = f"Open-Meteo response missing '{api_key}' channel"
                raise WeatherAPIError(msg)

            values = np.array(
                [float(v) if v is not None else np.nan for v in raw_list],
                dtype=np.float64,
            )

            # Interpolate over NaN gaps
            valid_mask = ~np.isnan(values)
            if not np.any(valid_mask):
                msg = f"All values are null for channel '{api_key}'"
                raise WeatherAPIError(msg)

            if np.any(~valid_mask):
                values[~valid_mask] = np.interp(
                    self._t_minutes[~valid_mask],
                    self._t_minutes[valid_mask],
                    values[valid_mask],
                )

            parsed[api_key] = values

        self._t_out = parsed["temperature_2m"]
        self._ghi = parsed["shortwave_radiation"]
        self._humidity = parsed["relative_humidity_2m"]
        self._wind_speed = parsed["wind_speed_10m"]

    def get(self, t_minutes: float) -> WeatherPoint:
        """Return interpolated weather conditions at simulation time *t_minutes*.

        Values are clamped at the edges (no extrapolation beyond the data range).

        Args:
            t_minutes: Simulation time in minutes (relative to first data point).

        Returns:
            A ``WeatherPoint`` with linearly interpolated values.
        """
        return WeatherPoint(
            T_out=float(np.interp(t_minutes, self._t_minutes, self._t_out)),
            GHI=float(np.interp(t_minutes, self._t_minutes, self._ghi)),
            wind_speed=float(np.interp(t_minutes, self._t_minutes, self._wind_speed)),
            humidity=float(np.interp(t_minutes, self._t_minutes, self._humidity)),
        )

    @property
    def time_range_minutes(self) -> tuple[float, float]:
        """Return ``(t_min, t_max)`` of available data in minutes."""
        return (float(self._t_minutes[0]), float(self._t_minutes[-1]))
