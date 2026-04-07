"""Full GTI (Global Tilted Irradiance) solar gain model with beam/diffuse decomposition.

Implements physics-correct GHI-to-GTI conversion for vertical window surfaces
using the Erbs et al. (1982) beam/diffuse decomposition and the Liu-Jordan
isotropic diffuse sky model.  Each window is treated individually, so the
model returns per-window GTI (W/m^2) and per-window Q_sol (W) as well as the
room-level total.

The public API accepts pre-computed sun position (elevation_deg, azimuth_deg)
so that the same model works with both:

* ``EphemerisCalculator`` (offline simulation)
* Home Assistant ``sun.sun`` entity (live control)

All angles are in **degrees** at the public interface and converted to radians
internally.  No ``homeassistant`` imports.

Units: GHI in W/m^2, GTI in W/m^2, Q_sol in W, areas in m^2, angles in
       degrees (API) / radians (internal).

References:
    Erbs, D.G., Klein, S.A. & Duffie, J.A. (1982).  Estimation of the
    diffuse radiation fraction for hourly, daily and monthly-average global
    radiation.  Solar Energy, 28(4), 293-302.

    Liu, B.Y.H. & Jordan, R.C. (1960).  The interrelationship and
    characteristic distribution of direct, diffuse and total solar radiation.
    Solar Energy, 4(3), 1-19.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pumpahead.solar import WindowConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOLAR_CONSTANT: float = 1361.0
"""Solar constant (W/m^2) -- total solar irradiance at 1 AU."""

DEFAULT_ALBEDO: float = 0.2
"""Default ground albedo (dimensionless).  Typical value for grass/soil."""

WINDOW_TILT_DEG: float = 90.0
"""All windows are assumed vertical (tilt = 90 deg from horizontal)."""

_MIN_ELEVATION_FOR_BEAM_DEG: float = 1.0
"""Minimum sun elevation (deg) to compute beam component.

Below this threshold sin(elevation) is too small and DNI = beam/sin(elev)
produces unrealistically large values.  Only diffuse + ground reflection
are included for lower elevations.
"""

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def extraterrestrial_horizontal(
    elevation_deg: float,
    day_of_year: int = 172,
) -> float:
    """Extraterrestrial irradiance on a horizontal surface (I0h).

    Accounts for Earth-Sun distance variation (eccentricity) and the
    projection of the solar beam onto a horizontal plane.

    Args:
        elevation_deg: Sun elevation angle in degrees above horizon.
        day_of_year: Day of year (1-365).  Defaults to 172 (summer solstice).

    Returns:
        I0h in W/m^2.  Returns 0.0 when the sun is at or below the horizon.
    """
    if elevation_deg <= 0.0:
        return 0.0

    elevation_rad = math.radians(elevation_deg)
    # Eccentricity correction factor (Spencer, 1971 simplified)
    eccentricity = 1.0 + 0.033 * math.cos(2.0 * math.pi * day_of_year / 365.0)
    return SOLAR_CONSTANT * eccentricity * math.sin(elevation_rad)


def erbs_decomposition(
    ghi: float,
    elevation_deg: float,
    day_of_year: int = 172,
) -> tuple[float, float]:
    """Decompose GHI into beam and diffuse components using the Erbs model.

    The Erbs et al. (1982) correlation estimates the diffuse fraction from
    the clearness index kt = GHI / I0h.

    Args:
        ghi: Global Horizontal Irradiance in W/m^2.
        elevation_deg: Sun elevation angle in degrees above horizon.
        day_of_year: Day of year (1-365).  Defaults to 172 (summer solstice).

    Returns:
        Tuple of (I_beam, I_diffuse) in W/m^2.  Both are >= 0.
        Returns (0.0, 0.0) when GHI <= 0, elevation <= 0, or I0h <= 0.
    """
    if ghi <= 0.0 or elevation_deg <= 0.0:
        return 0.0, 0.0

    i0h = extraterrestrial_horizontal(elevation_deg, day_of_year)
    if i0h <= 0.0:
        return 0.0, 0.0

    # Clearness index, clamped to [0, 1]
    kt = min(ghi / i0h, 1.0)
    kt = max(kt, 0.0)

    # Erbs correlation for diffuse fraction kd
    if kt <= 0.22:
        kd = 1.0 - 0.09 * kt
    elif kt <= 0.80:
        kd = 0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4
    else:
        kd = 0.165

    i_diffuse = kd * ghi
    i_beam = ghi - i_diffuse
    # Ensure non-negative (floating point safety)
    return max(i_beam, 0.0), max(i_diffuse, 0.0)


def cos_incidence_vertical(
    sun_elevation_deg: float,
    sun_azimuth_deg: float,
    window_azimuth_deg: float,
) -> float:
    """Cosine of incidence angle for a vertical surface.

    For a vertical window with outward-normal azimuth ``window_azimuth_deg``,
    the cosine of the angle of incidence is:

        cos(theta) = cos(elevation) * cos(sun_azimuth - window_azimuth)

    Args:
        sun_elevation_deg: Sun elevation angle in degrees above horizon.
        sun_azimuth_deg: Sun azimuth in degrees from north, clockwise.
        window_azimuth_deg: Window outward-normal azimuth in degrees from
            north, clockwise.

    Returns:
        cos(theta_incidence), clamped to [0, 1].  Returns 0 when the sun
        is behind the window.
    """
    elevation_rad = math.radians(sun_elevation_deg)
    azimuth_diff_rad = math.radians(sun_azimuth_deg - window_azimuth_deg)
    cos_theta = math.cos(elevation_rad) * math.cos(azimuth_diff_rad)
    return max(0.0, cos_theta)


def gti_vertical(
    beam: float,
    diffuse: float,
    ghi: float,
    sun_elevation_deg: float,
    sun_azimuth_deg: float,
    window_azimuth_deg: float,
    albedo: float = DEFAULT_ALBEDO,
) -> float:
    """Compute GTI on a vertical window surface.

    Combines three components:

    1. **Beam**: DNI projected onto the vertical surface.
    2. **Diffuse**: Isotropic sky diffuse (Liu-Jordan model) for a vertical
       surface = diffuse * 0.5.
    3. **Ground-reflected**: GHI * albedo * 0.5 for a vertical surface.

    Args:
        beam: Beam (direct) irradiance on horizontal in W/m^2.
        diffuse: Diffuse irradiance on horizontal in W/m^2.
        ghi: Global Horizontal Irradiance in W/m^2.
        sun_elevation_deg: Sun elevation angle in degrees above horizon.
        sun_azimuth_deg: Sun azimuth in degrees from north, clockwise.
        window_azimuth_deg: Window outward-normal azimuth in degrees from
            north, clockwise.
        albedo: Ground albedo (dimensionless).  Defaults to 0.2.

    Returns:
        GTI in W/m^2 (>= 0).
    """
    # Diffuse component on vertical surface (isotropic Liu-Jordan model)
    # For tilt=90 deg: (1 + cos(90))/2 = 0.5
    i_diff_v = diffuse * 0.5

    # Ground-reflected component on vertical surface
    # For tilt=90 deg: (1 - cos(90))/2 = 0.5
    i_ground = ghi * albedo * 0.5

    # Beam component on vertical surface
    i_beam_v = 0.0
    if beam > 0.0 and sun_elevation_deg >= _MIN_ELEVATION_FOR_BEAM_DEG:
        elevation_rad = math.radians(sun_elevation_deg)
        sin_elev = math.sin(elevation_rad)
        # DNI = beam / sin(elevation)
        dni = beam / sin_elev
        cos_theta = cos_incidence_vertical(
            sun_elevation_deg, sun_azimuth_deg, window_azimuth_deg
        )
        i_beam_v = dni * cos_theta

    return max(0.0, i_beam_v + i_diff_v + i_ground)


# ---------------------------------------------------------------------------
# GTIModel class
# ---------------------------------------------------------------------------


class GTIModel:
    """Full GTI solar gain model with beam/diffuse decomposition per window.

    Unlike the simplified ``SolarGainModel`` (which uses a single orientation
    factor), this model decomposes GHI into beam and diffuse components using
    the Erbs correlation, then computes GTI on each vertical window surface
    accounting for:

    * Direct beam projected via the cosine of incidence
    * Isotropic sky diffuse (Liu-Jordan)
    * Ground-reflected irradiance

    Attributes:
        albedo: Ground albedo used for ground-reflected component.
    """

    def __init__(self, albedo: float = DEFAULT_ALBEDO) -> None:
        """Initialise the GTI model.

        Args:
            albedo: Ground albedo (dimensionless, 0 to 1).
                Defaults to 0.2 (typical grass/soil).
        """
        self.albedo = albedo

    def gti_per_window(
        self,
        ghi: float,
        elevation_deg: float,
        azimuth_deg: float,
        windows: Sequence[WindowConfig],
        day_of_year: int = 172,
    ) -> list[float]:
        """Compute GTI in W/m^2 for each window.

        This is the raw irradiance on each window surface, before applying
        g_value or window area.

        Args:
            ghi: Global Horizontal Irradiance in W/m^2.
            elevation_deg: Sun elevation angle in degrees above horizon.
            azimuth_deg: Sun azimuth in degrees from north, clockwise.
            windows: Sequence of window configurations.
            day_of_year: Day of year (1-365).  Defaults to 172.

        Returns:
            List of GTI values in W/m^2, one per window.
        """
        if ghi <= 0.0 or elevation_deg <= 0.0:
            return [0.0] * len(windows)

        beam, diffuse = erbs_decomposition(ghi, elevation_deg, day_of_year)

        result: list[float] = []
        for window in windows:
            window_az = window.orientation.azimuth_deg
            gti = gti_vertical(
                beam,
                diffuse,
                ghi,
                elevation_deg,
                azimuth_deg,
                window_az,
                albedo=self.albedo,
            )
            result.append(gti)
        return result

    def compute(
        self,
        ghi: float,
        elevation_deg: float,
        azimuth_deg: float,
        windows: Sequence[WindowConfig],
        day_of_year: int = 172,
    ) -> float:
        """Compute total Q_sol for all windows in a room.

        Q_sol per window = GTI * area_m2 * g_value.
        Total Q_sol = sum over all windows.

        Args:
            ghi: Global Horizontal Irradiance in W/m^2.
            elevation_deg: Sun elevation angle in degrees above horizon.
            azimuth_deg: Sun azimuth in degrees from north, clockwise.
            windows: Sequence of window configurations.
            day_of_year: Day of year (1-365).  Defaults to 172.

        Returns:
            Total Q_sol in Watts.
        """
        gti_values = self.gti_per_window(
            ghi, elevation_deg, azimuth_deg, windows, day_of_year
        )
        total = 0.0
        for gti, window in zip(gti_values, windows, strict=True):
            total += gti * window.area_m2 * window.g_value
        return total

    def compute_per_window(
        self,
        ghi: float,
        elevation_deg: float,
        azimuth_deg: float,
        windows: Sequence[WindowConfig],
        day_of_year: int = 172,
    ) -> list[float]:
        """Compute Q_sol per window in Watts.

        Q_sol per window = GTI * area_m2 * g_value.

        Args:
            ghi: Global Horizontal Irradiance in W/m^2.
            elevation_deg: Sun elevation angle in degrees above horizon.
            azimuth_deg: Sun azimuth in degrees from north, clockwise.
            windows: Sequence of window configurations.
            day_of_year: Day of year (1-365).  Defaults to 172.

        Returns:
            List of Q_sol values in Watts, one per window.
        """
        gti_values = self.gti_per_window(
            ghi, elevation_deg, azimuth_deg, windows, day_of_year
        )
        return [
            gti * window.area_m2 * window.g_value
            for gti, window in zip(gti_values, windows, strict=True)
        ]
