"""Home Assistant weather adapter for PumpAhead.

Maps HA's ``weather.get_forecasts`` service response to the core
``WeatherSource`` protocol from ``pumpahead.weather``.  This adapter
lives in the HA layer because it depends on ``homeassistant``, which
the core library must never import.

Separation of concerns:
    * ``async_update(hass)`` — async, fetches forecast data from HA.
    * ``get(t_minutes)`` — sync, satisfies the ``WeatherSource`` protocol.

The coordinator (issue #45) calls ``async_update()`` periodically;
downstream code consumes ``get()`` as a plain ``WeatherSource``.
"""

from __future__ import annotations

import contextlib
import logging
import math
from datetime import UTC, datetime
from typing import Any

import numpy as np
from homeassistant.core import HomeAssistant
from numpy.typing import NDArray

from pumpahead.solar import EphemerisCalculator
from pumpahead.weather import WeatherPoint

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_AGE_HOURS: float = 6.0
"""Forecast data older than this is considered stale."""

MIN_HORIZON_HOURS: float = 24.0
"""Minimum forecast horizon required by Axiom 10 (prediction >= 24 h)."""

_CLOUD_ATTENUATION: float = 0.75
"""Kasten-Czeplak linear cloud attenuation coefficient."""

_CLEAR_SKY_PEAK_W_M2: float = 1000.0
"""Approximate clear-sky GHI at the top of the atmosphere [W/m^2]."""

_DEFAULT_FALLBACK_T_OUT: float = 10.0
"""Default outdoor temperature when no data is available [degC]."""

_DEFAULT_HUMIDITY: float = 50.0
"""Default relative humidity when forecast doesn't provide it [%]."""


# ---------------------------------------------------------------------------
# HAWeatherSource
# ---------------------------------------------------------------------------


class HAWeatherSource:
    """Adapter that bridges HA ``weather.get_forecasts`` to ``WeatherSource``.

    Internally stores forecast arrays indexed by ``t_minutes`` relative to
    the last ``async_update()`` call.  The ``get()`` method uses
    ``numpy.interp`` for linear interpolation, identically to ``CSVWeather``
    and ``OpenMeteoHistorical``.

    When forecast data is unavailable or stale (older than *max_age_hours*),
    ``get()`` returns a conservative fallback ``WeatherPoint`` instead.
    """

    def __init__(
        self,
        entity_id: str,
        latitude: float,
        longitude: float,
        max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    ) -> None:
        """Initialise the HA weather adapter.

        Args:
            entity_id: HA entity ID of the weather integration
                (e.g. ``"weather.home"``).
            latitude: Geographic latitude in degrees (for GHI estimation).
            longitude: Geographic longitude in degrees (for GHI estimation).
            max_age_hours: Maximum age of forecast data before it is
                considered stale.
        """
        self._entity_id = entity_id
        self._max_age_hours = max_age_hours
        self._ephemeris = EphemerisCalculator(latitude, longitude)

        # Internal arrays — empty until the first async_update().
        self._t_minutes: NDArray[np.float64] = np.array([], dtype=np.float64)
        self._t_out: NDArray[np.float64] = np.array([], dtype=np.float64)
        self._ghi: NDArray[np.float64] = np.array([], dtype=np.float64)
        self._wind_speed: NDArray[np.float64] = np.array([], dtype=np.float64)
        self._humidity: NDArray[np.float64] = np.array([], dtype=np.float64)

        self._last_update: datetime | None = None
        self._fallback_t_out: float = _DEFAULT_FALLBACK_T_OUT

    # -- Async update -------------------------------------------------------

    async def async_update(self, hass: HomeAssistant) -> None:
        """Fetch forecast data from HA and rebuild internal arrays.

        Calls ``weather.get_forecasts`` for hourly data, parses the
        response, and updates the internal numpy arrays.  Also reads
        the entity's current temperature for fallback use.

        Args:
            hass: The Home Assistant instance.
        """
        try:
            response = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self._entity_id, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to call weather.get_forecasts")
            return

        forecasts = self._parse_forecast_response(response)

        # Read current state for fallback temperature.
        state = hass.states.get(self._entity_id)
        if state is not None:
            attrs = getattr(state, "attributes", {})
            if isinstance(attrs, dict) and "temperature" in attrs:
                with contextlib.suppress(TypeError, ValueError):
                    self._fallback_t_out = float(attrs["temperature"])

        if not forecasts:
            _LOGGER.warning(
                "No usable forecast entries from %s", self._entity_id
            )
            return

        now = datetime.now(UTC)

        t_minutes_list: list[float] = []
        t_out_list: list[float] = []
        ghi_list: list[float] = []
        wind_list: list[float] = []
        hum_list: list[float] = []

        for entry in forecasts:
            entry_dt = datetime.fromisoformat(entry["datetime"])
            if entry_dt.tzinfo is None:
                entry_dt = entry_dt.replace(tzinfo=UTC)

            t_min = (entry_dt - now).total_seconds() / 60.0
            t_minutes_list.append(t_min)
            t_out_list.append(float(entry["temperature"]))
            hum_list.append(
                float(entry["humidity"])
                if entry.get("humidity") is not None
                else _DEFAULT_HUMIDITY
            )
            wind_list.append(
                float(entry["wind_speed"])
                if entry.get("wind_speed") is not None
                else 0.0
            )
            ghi_list.append(self._estimate_ghi(entry_dt, entry.get("cloud_coverage")))

        self._t_minutes = np.array(t_minutes_list, dtype=np.float64)
        self._t_out = np.array(t_out_list, dtype=np.float64)
        self._ghi = np.array(ghi_list, dtype=np.float64)
        self._wind_speed = np.array(wind_list, dtype=np.float64)
        self._humidity = np.array(hum_list, dtype=np.float64)
        self._last_update = now

        # Axiom 10: warn if forecast horizon is below 24 h.
        horizon_h = float(self._t_minutes[-1]) / 60.0
        if horizon_h < MIN_HORIZON_HOURS:
            _LOGGER.warning(
                "Forecast horizon %.1fh is below minimum %.1fh (Axiom 10)",
                horizon_h,
                MIN_HORIZON_HOURS,
            )

    # -- WeatherSource protocol ---------------------------------------------

    def get(self, t_minutes: float) -> WeatherPoint:
        """Return weather conditions at *t_minutes* from now.

        Values are linearly interpolated from the stored forecast arrays.
        If data is stale or absent, a conservative fallback is returned.

        Args:
            t_minutes: Time offset in minutes from "now" (the moment of
                the last ``async_update()``).

        Returns:
            A ``WeatherPoint`` with interpolated or fallback conditions.
        """
        if self._is_stale() or len(self._t_minutes) == 0:
            return self._fallback_point()

        # Compensate for elapsed time since the last update so that
        # t_minutes=0 always means "right now".
        elapsed = 0.0
        if self._last_update is not None:
            elapsed = (datetime.now(UTC) - self._last_update).total_seconds() / 60.0
        adjusted_t = t_minutes + elapsed

        return WeatherPoint(
            T_out=float(np.interp(adjusted_t, self._t_minutes, self._t_out)),
            GHI=max(0.0, float(np.interp(adjusted_t, self._t_minutes, self._ghi))),
            wind_speed=float(
                np.interp(adjusted_t, self._t_minutes, self._wind_speed)
            ),
            humidity=float(np.interp(adjusted_t, self._t_minutes, self._humidity)),
        )

    # -- Properties ---------------------------------------------------------

    @property
    def forecast_horizon_hours(self) -> float:
        """Forecast horizon in hours (time span of stored forecast data)."""
        if len(self._t_minutes) == 0:
            return 0.0
        return float(self._t_minutes[-1]) / 60.0

    @property
    def has_data(self) -> bool:
        """Return True if valid (non-stale) forecast data is available."""
        return len(self._t_minutes) > 0 and not self._is_stale()

    # -- Private helpers ----------------------------------------------------

    def _is_stale(self) -> bool:
        """Return True if forecast data is too old or missing entirely."""
        if self._last_update is None:
            return True
        age_seconds = (datetime.now(UTC) - self._last_update).total_seconds()
        return age_seconds > self._max_age_hours * 3600

    def _fallback_point(self) -> WeatherPoint:
        """Return a conservative fallback ``WeatherPoint``.

        GHI=0 ensures the controller does not count on unpredictable
        solar gains (Axiom 9: comfort > cost).
        """
        return WeatherPoint(
            T_out=self._fallback_t_out,
            GHI=0.0,
            wind_speed=0.0,
            humidity=_DEFAULT_HUMIDITY,
        )

    def _estimate_ghi(
        self, dt_utc: datetime, cloud_coverage_pct: float | None
    ) -> float:
        """Estimate GHI from sun position and cloud coverage.

        Uses the existing ``EphemerisCalculator`` for sun elevation and
        applies the Kasten-Czeplak linear attenuation model.

        If *cloud_coverage_pct* is ``None`` (provider doesn't supply it),
        GHI defaults to 0.0 — conservative (Axiom 9).

        Args:
            dt_utc: Forecast timestamp (UTC).
            cloud_coverage_pct: Cloud coverage percentage (0-100) or None.

        Returns:
            Estimated GHI in W/m^2 (>= 0).
        """
        if cloud_coverage_pct is None:
            return 0.0

        elevation_deg, _ = self._ephemeris.sun_position(dt_utc)
        if elevation_deg <= 0:
            return 0.0

        clear_sky = _CLEAR_SKY_PEAK_W_M2 * math.sin(math.radians(elevation_deg))
        attenuation = float(cloud_coverage_pct) / 100.0 * _CLOUD_ATTENUATION
        return clear_sky * (1.0 - attenuation)

    def _parse_forecast_response(
        self, response: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract forecast entries from HA service response.

        HA returns ``{entity_id: {"forecast": [...]}}`` for the standard
        format, but some providers may return a bare list.

        Entries missing ``"datetime"`` or ``"temperature"`` (or with None
        temperature) are filtered out.

        Args:
            response: Raw HA ``weather.get_forecasts`` response dict.

        Returns:
            Cleaned list of forecast entry dicts.
        """
        entity_data = response.get(self._entity_id, {})

        if isinstance(entity_data, dict):
            forecasts = entity_data.get("forecast", [])
        elif isinstance(entity_data, list):
            # Legacy format: bare list.
            forecasts = entity_data
        else:
            forecasts = []

        return [
            entry
            for entry in forecasts
            if isinstance(entry, dict)
            and entry.get("datetime") is not None
            and entry.get("temperature") is not None
        ]
