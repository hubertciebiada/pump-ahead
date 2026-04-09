"""Dew point calculation and condensation protection.

Provides the proper Magnus formula for dew-point temperature, a simplified
linear approximation for backward compatibility, and graduated cooling
valve throttling for condensation prevention.

The Magnus formula uses Alduchov & Eskridge (1996) coefficients, which
provide < 0.1 degC error against psychrometric tables for T_air in
[-40, 60] degC.

Functions:
    ``dew_point`` -- Magnus formula dew-point calculation.
    ``dew_point_simplified`` -- linear approximation (legacy).
    ``cooling_throttle_factor`` -- graduated valve throttling [0, 1].
    ``condensation_margin`` -- safety margin above dew point.

Units:
    Temperatures: degC
    Humidity: % (0-100)
    Throttle factor: 0.0 (fully closed) to 1.0 (fully open)
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Magnus formula constants (Alduchov & Eskridge, 1996)
# ---------------------------------------------------------------------------

MAGNUS_A: float = 17.625
"""Dimensionless coefficient *a* in the Magnus formula."""

MAGNUS_B: float = 243.04
"""Coefficient *b* [degC] in the Magnus formula."""


# ---------------------------------------------------------------------------
# Dew-point functions
# ---------------------------------------------------------------------------


def dew_point(t_air: float, rh: float) -> float:
    """Compute dew-point temperature using the Magnus formula.

    Uses the Alduchov & Eskridge (1996) coefficients:

        gamma = (a * T) / (b + T) + ln(RH / 100)
        T_dew = (b * gamma) / (a - gamma)

    Valid for T_air in [-40, 60] degC with < 0.1 degC error against
    psychrometric tables.

    Args:
        t_air: Air temperature [degC].
        rh: Relative humidity [%] (0-100).

    Returns:
        Dew-point temperature [degC].  Returns -273.15 when rh is 0
        (absolute zero guard for log(0)).

    Raises:
        ValueError: If *rh* is outside [0, 100].
    """
    if rh < 0.0 or rh > 100.0:
        msg = f"rh must be in [0, 100], got {rh}"
        raise ValueError(msg)

    if rh == 0.0:
        return -273.15

    gamma = (MAGNUS_A * t_air) / (MAGNUS_B + t_air) + math.log(rh / 100.0)
    return (MAGNUS_B * gamma) / (MAGNUS_A - gamma)


def dew_point_simplified(t_air: float, rh: float) -> float:
    """Compute dew-point temperature using the simplified linear formula.

    This is the legacy approximation: ``T_dew = T_air - (100 - RH) / 5``.
    Retained for backward compatibility with earlier code.

    Args:
        t_air: Air temperature [degC].
        rh: Relative humidity [%] (0-100).

    Returns:
        Estimated dew-point temperature [degC].
    """
    return t_air - (100.0 - rh) / 5.0


# ---------------------------------------------------------------------------
# Graduated cooling throttle
# ---------------------------------------------------------------------------


def cooling_throttle_factor(
    t_floor: float,
    t_dew: float,
    margin: float = 2.0,
    ramp_width: float = 2.0,
) -> float:
    """Compute a graduated cooling valve throttle factor.

    Returns a factor in [0.0, 1.0] that should be multiplied with the
    cooling valve output to prevent condensation.

    The throttle ramps linearly:
    - ``gap <= margin``: returns 0.0 (fully closed, condensation risk).
    - ``gap >= margin + ramp_width``: returns 1.0 (fully open, safe).
    - In between: linear ramp from 0.0 to 1.0.

    Where ``gap = t_floor - t_dew``.

    Args:
        t_floor: Floor / slab surface temperature [degC].
        t_dew: Dew-point temperature [degC].
        margin: Minimum required gap above dew point [degC].
            Must be >= 0.
        ramp_width: Width of the linear ramp zone [degC].
            Must be > 0.

    Returns:
        Throttle factor in [0.0, 1.0].

    Raises:
        ValueError: If *margin* < 0 or *ramp_width* <= 0.
    """
    if margin < 0.0:
        msg = f"margin must be >= 0, got {margin}"
        raise ValueError(msg)
    if ramp_width <= 0.0:
        msg = f"ramp_width must be > 0, got {ramp_width}"
        raise ValueError(msg)

    gap = t_floor - t_dew

    if gap <= margin:
        return 0.0
    if gap >= margin + ramp_width:
        return 1.0

    return (gap - margin) / ramp_width


# ---------------------------------------------------------------------------
# Condensation margin
# ---------------------------------------------------------------------------


def condensation_margin(
    t_floor: float,
    t_air: float,
    rh: float,
    safety_margin: float = 2.0,
) -> float:
    """Compute the condensation safety margin.

    Returns ``t_floor - (T_dew + safety_margin)`` using the Magnus
    formula.  Positive values indicate safe conditions; negative values
    indicate condensation risk.

    Args:
        t_floor: Floor / slab surface temperature [degC].
        t_air: Air temperature [degC].
        rh: Relative humidity [%] (0-100).
        safety_margin: Required gap above dew point [degC].

    Returns:
        Condensation margin [degC].  Positive = safe, negative = risk.
    """
    t_dew = dew_point(t_air, rh)
    return t_floor - (t_dew + safety_margin)
