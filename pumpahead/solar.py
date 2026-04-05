"""Solar gain model for building simulation.

Implements a simple orientation-based Q_sol calculation that converts
Global Horizontal Irradiance (GHI) to solar heat gain through windows.
Also provides an ephemeris calculator for sun position from lat/lon/datetime.

This is the *simple* model — no beam/diffuse decomposition or full
solar geometry (that belongs in solar_gti.py for issue #52).

Units: Q_sol in W, GHI in W/m^2, areas in m^2, angles in degrees (API)
       and radians (internal calculations).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum


class Orientation(Enum):
    """Cardinal orientation for a window.

    Values are short-form compass labels; the ``azimuth_deg`` property
    gives the outward-facing normal in degrees from north, clockwise.
    """

    NORTH = "N"
    EAST = "E"
    SOUTH = "S"
    WEST = "W"

    @property
    def azimuth_deg(self) -> float:
        """Window-normal azimuth in degrees from north, clockwise.

        Returns:
            Azimuth in degrees: N=0, E=90, S=180, W=270.
        """
        _azimuths: dict[str, float] = {
            "N": 0.0,
            "E": 90.0,
            "S": 180.0,
            "W": 270.0,
        }
        return _azimuths[self.value]


@dataclass(frozen=True)
class WindowConfig:
    """Configuration for a single window.

    Attributes:
        orientation: Cardinal direction the window faces.
        area_m2: Glazing area in square metres (must be > 0).
        g_value: Solar energy transmittance coefficient, 0 < g <= 1.0.
            Fraction of incident solar energy that passes through the glass.
            Typical double-glazing: 0.5-0.7.
    """

    orientation: Orientation
    area_m2: float
    g_value: float

    def __post_init__(self) -> None:
        """Validate physical constraints.

        Raises:
            ValueError: If area_m2 <= 0 or g_value outside (0, 1.0].
        """
        if self.area_m2 <= 0:
            msg = f"area_m2 must be positive, got {self.area_m2}"
            raise ValueError(msg)
        if self.g_value <= 0 or self.g_value > 1.0:
            msg = f"g_value must be in (0, 1.0], got {self.g_value}"
            raise ValueError(msg)


class SolarGainModel:
    """Stateless calculator for solar heat gain through windows.

    Converts GHI (horizontal irradiance) to heat gain on vertical window
    surfaces using a simplified orientation-based correction factor.

    The correction factor accounts for the angle between the sun and the
    window normal:

        factor = max(0, cos(azimuth_sun - azimuth_window)) * cos(elevation)

    This captures the key physics:
    - South-facing windows receive more solar gain in winter (low elevation).
    - East-facing windows receive more in the morning (sun in east).
    - Windows facing away from the sun receive zero gain.

    No beam/diffuse decomposition — see ``solar_gti.py`` (issue #52) for that.
    """

    def compute(
        self,
        ghi: float,
        elevation_deg: float,
        azimuth_deg: float,
        windows: Sequence[WindowConfig],
    ) -> float:
        """Calculate total solar gain through all windows.

        Args:
            ghi: Global Horizontal Irradiance in W/m^2.
            elevation_deg: Sun elevation angle in degrees above horizon.
            azimuth_deg: Sun azimuth angle in degrees from north, clockwise.
            windows: Sequence of window configurations.

        Returns:
            Total Q_sol in Watts.
        """
        if ghi <= 0 or elevation_deg <= 0 or len(windows) == 0:
            return 0.0

        total = 0.0
        for window in windows:
            factor = self._orientation_factor(azimuth_deg, elevation_deg, window)
            total += window.g_value * window.area_m2 * ghi * factor
        return total

    def _orientation_factor(
        self,
        sun_azimuth_deg: float,
        sun_elevation_deg: float,
        window: WindowConfig,
    ) -> float:
        """Compute the GHI-to-vertical-surface correction factor for a window.

        The factor converts horizontal irradiance to irradiance on a vertical
        surface facing a given orientation.  It combines:
        1. cos(azimuth difference) — how directly the sun faces the window.
        2. cos(elevation) — projection from horizontal to the sun's slant.

        Args:
            sun_azimuth_deg: Sun azimuth in degrees from north, clockwise.
            sun_elevation_deg: Sun elevation in degrees above horizon.
            window: Window configuration.

        Returns:
            Dimensionless correction factor in [0, 1].
        """
        azimuth_diff_rad = math.radians(sun_azimuth_deg - window.orientation.azimuth_deg)
        elevation_rad = math.radians(sun_elevation_deg)

        raw = math.cos(azimuth_diff_rad) * math.cos(elevation_rad)
        return max(0.0, min(raw, 1.0))


class EphemerisCalculator:
    """Simplified sun position calculator for offline simulation.

    Computes solar elevation and azimuth from geographic coordinates and
    a UTC datetime using standard approximate equations (accurate to ~1 deg).

    Naive datetimes are treated as UTC.  For best results, pass
    timezone-aware UTC datetimes.

    Attributes:
        latitude: Geographic latitude in degrees [-90, 90].
        longitude: Geographic longitude in degrees [-180, 180].
    """

    def __init__(self, latitude: float, longitude: float) -> None:
        """Initialise the ephemeris calculator.

        Args:
            latitude: Geographic latitude in degrees, positive north.
            longitude: Geographic longitude in degrees, positive east.

        Raises:
            ValueError: If latitude or longitude is out of range.
        """
        if latitude < -90 or latitude > 90:
            msg = f"latitude must be in [-90, 90], got {latitude}"
            raise ValueError(msg)
        if longitude < -180 or longitude > 180:
            msg = f"longitude must be in [-180, 180], got {longitude}"
            raise ValueError(msg)
        self.latitude = latitude
        self.longitude = longitude

    def sun_position(self, dt: datetime) -> tuple[float, float]:
        """Compute sun elevation and azimuth for a given UTC datetime.

        Uses the simplified solar position equations:
        - Declination from day-of-year (sinusoidal approximation).
        - Equation of time (Spencer 1971 approximation).
        - Hour angle from apparent solar time.

        Naive datetimes are treated as UTC.

        Args:
            dt: Datetime (UTC or naive-treated-as-UTC).

        Returns:
            Tuple of (elevation_deg, azimuth_deg) where:
            - elevation_deg is in degrees, negative when sun is below horizon.
            - azimuth_deg is in degrees from north, clockwise [0, 360).
        """
        # Convert aware datetimes to UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)

        day_of_year = dt.timetuple().tm_yday
        hour_utc = dt.hour + dt.minute / 60.0 + dt.second / 3600.0

        # Fractional year in radians (Spencer convention)
        gamma = 2.0 * math.pi * (day_of_year - 1) / 365.0

        # Declination (radians) — Spencer approximation
        declination = (
            0.006918
            - 0.399912 * math.cos(gamma)
            + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2.0 * gamma)
            + 0.000907 * math.sin(2.0 * gamma)
            - 0.002697 * math.cos(3.0 * gamma)
            + 0.001480 * math.sin(3.0 * gamma)
        )

        # Equation of time in minutes (Spencer approximation)
        eqtime = 229.18 * (
            0.000075
            + 0.001868 * math.cos(gamma)
            - 0.032077 * math.sin(gamma)
            - 0.014615 * math.cos(2.0 * gamma)
            - 0.040849 * math.sin(2.0 * gamma)
        )

        # Apparent solar time in minutes from midnight
        time_offset = eqtime + 4.0 * self.longitude  # minutes
        solar_time_min = hour_utc * 60.0 + time_offset

        # Hour angle in radians (negative morning, positive afternoon)
        hour_angle = math.radians((solar_time_min / 4.0) - 180.0)

        lat_rad = math.radians(self.latitude)

        # Elevation
        sin_elevation = (
            math.sin(lat_rad) * math.sin(declination)
            + math.cos(lat_rad) * math.cos(declination) * math.cos(hour_angle)
        )
        # Clamp to [-1, 1] to avoid domain errors from floating point
        sin_elevation = max(-1.0, min(sin_elevation, 1.0))
        elevation_rad = math.asin(sin_elevation)
        elevation_deg = math.degrees(elevation_rad)

        # Azimuth
        cos_elevation = math.cos(elevation_rad)
        if cos_elevation == 0:
            # Sun at zenith — azimuth undefined, return south by convention
            azimuth_deg = 180.0
        else:
            cos_azimuth = (
                math.sin(declination) - math.sin(lat_rad) * sin_elevation
            ) / (math.cos(lat_rad) * cos_elevation)
            # Clamp to [-1, 1]
            cos_azimuth = max(-1.0, min(cos_azimuth, 1.0))
            azimuth_rad = math.acos(cos_azimuth)

            # atan2-like disambiguation: morning → east (< 180), afternoon → west (> 180)
            if hour_angle > 0:
                azimuth_deg = 360.0 - math.degrees(azimuth_rad)
            else:
                azimuth_deg = math.degrees(azimuth_rad)

        return elevation_deg, azimuth_deg
