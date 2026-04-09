"""Generic COP (Coefficient of Performance) calculator with fallback logic.

Provides three COP resolution modes:

1. **AUTO_LEARNED** -- Bilinear regression ``COP = a0 + a1*T_outdoor + a2*T_supply``
   fitted from historical measurement data.  Requires a minimum of 48 hours
   of valid samples before the model is usable.
2. **LOOKUP_TABLE** -- User-provided COP vs T_outdoor table with piecewise-linear
   interpolation (``numpy.interp``).  Edge values are clamped.
3. **CONSTANT** -- Fixed fallback COP value (default 3.5) when insufficient data
   is available.

The calculator is hardware-agnostic (Axiom 8): it receives ``q_thermal`` and
``p_electric`` directly -- it does not know whether ``q_thermal`` was derived
from ``flow_rate * c_p * delta_T`` or from ``T_supply - T_return`` and a flow
sensor.

All returned COP values are clamped to the physical range ``[COP_MIN, COP_MAX]``
(1.0 to 8.0).

Units:
    Temperatures: degrees Celsius.
    Power: Watts.
    COP: dimensionless.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

COP_MIN: float = 1.0
"""Minimum physically plausible COP."""

COP_MAX: float = 8.0
"""Maximum physically plausible COP."""

DEFAULT_COP: float = 3.5
"""Default constant COP used as fallback."""

MIN_SAMPLES_HOURS: int = 48
"""Minimum hours of measurement data required for auto-learned mode."""

DEFAULT_T_SUPPLY: float = 35.0
"""Default supply temperature [degC] used when ``t_supply`` is not provided."""


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class COPMode(Enum):
    """COP resolution mode.

    Members:
        AUTO_LEARNED: Bilinear regression from historical measurements.
        LOOKUP_TABLE: User-provided COP vs T_outdoor table.
        CONSTANT: Fixed fallback COP value.
    """

    AUTO_LEARNED = "auto_learned"
    LOOKUP_TABLE = "lookup_table"
    CONSTANT = "constant"


# ---------------------------------------------------------------------------
# Measurement sample
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class COPSample:
    """Single COP measurement observation.

    Attributes:
        t_outdoor: Outdoor temperature [degC].
        t_supply: HP supply temperature [degC].
        p_electric: HP electrical consumption [W].
        q_thermal: Thermal output [W].
        cop: Computed COP (``q_thermal / p_electric``).
    """

    t_outdoor: float
    t_supply: float
    p_electric: float
    q_thermal: float
    cop: float

    def __post_init__(self) -> None:
        """Validate physical constraints on construction."""
        if self.p_electric <= 0.0:
            msg = f"p_electric must be positive, got {self.p_electric}"
            raise ValueError(msg)
        if self.q_thermal <= 0.0:
            msg = f"q_thermal must be positive, got {self.q_thermal}"
            raise ValueError(msg)
        if self.cop < COP_MIN or self.cop > COP_MAX:
            msg = (
                f"cop must be in [{COP_MIN}, {COP_MAX}], got {self.cop:.3f}"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------


class COPCalculator:
    """Generic COP calculator with three resolution modes and fallback.

    Parameters
    ----------
    mode:
        Resolution mode (AUTO_LEARNED, LOOKUP_TABLE, or CONSTANT).
    default_cop:
        Constant fallback COP value.  Used in CONSTANT mode and as
        fallback when AUTO_LEARNED has insufficient data.
    lookup_t_outdoor:
        Sorted outdoor temperature breakpoints for LOOKUP_TABLE mode.
    lookup_cop:
        Corresponding COP values for each breakpoint.
    min_samples_hours:
        Minimum hours of data required to consider the auto-learned
        model as fitted.  Each sample is assumed to represent one
        observation per hour.
    """

    def __init__(
        self,
        mode: COPMode = COPMode.CONSTANT,
        default_cop: float = DEFAULT_COP,
        lookup_t_outdoor: np.ndarray | None = None,
        lookup_cop: np.ndarray | None = None,
        min_samples_hours: int = MIN_SAMPLES_HOURS,
    ) -> None:
        self._mode = mode
        self._default_cop = self._clamp_cop(default_cop)
        self._min_samples_hours = min_samples_hours

        # Lookup table arrays (LOOKUP_TABLE mode)
        self._lookup_t_outdoor: np.ndarray | None = None
        self._lookup_cop: np.ndarray | None = None
        if mode is COPMode.LOOKUP_TABLE:
            if lookup_t_outdoor is None or lookup_cop is None:
                msg = (
                    "lookup_t_outdoor and lookup_cop must be provided "
                    "for LOOKUP_TABLE mode"
                )
                raise ValueError(msg)
            if len(lookup_t_outdoor) != len(lookup_cop):
                msg = (
                    f"lookup_t_outdoor length ({len(lookup_t_outdoor)}) "
                    f"must match lookup_cop length ({len(lookup_cop)})"
                )
                raise ValueError(msg)
            if len(lookup_t_outdoor) < 2:
                msg = "lookup table must have at least 2 entries"
                raise ValueError(msg)
            # Sort by temperature
            sort_idx = np.argsort(lookup_t_outdoor)
            self._lookup_t_outdoor = np.asarray(
                lookup_t_outdoor, dtype=np.float64
            )[sort_idx]
            self._lookup_cop = np.asarray(lookup_cop, dtype=np.float64)[
                sort_idx
            ]

        # Auto-learned regression state
        self._samples: list[COPSample] = []
        self._coefficients: np.ndarray | None = None  # [a0, a1, a2]

    # -- Properties -----------------------------------------------------------

    @property
    def mode(self) -> COPMode:
        """Current COP resolution mode."""
        return self._mode

    @property
    def is_fitted(self) -> bool:
        """Whether the auto-learned regression model has been fitted."""
        return self._coefficients is not None

    @property
    def n_samples(self) -> int:
        """Number of stored measurement samples."""
        return len(self._samples)

    @property
    def default_cop(self) -> float:
        """Constant fallback COP value."""
        return self._default_cop

    # -- Sample management ----------------------------------------------------

    def add_sample(
        self,
        t_outdoor: float,
        t_supply: float,
        p_electric: float,
        q_thermal: float,
    ) -> bool:
        """Record a COP measurement sample.

        Computes ``COP = q_thermal / p_electric`` and stores the sample
        if it passes validation.  Rejects samples with non-physical
        values (``p_electric <= 0``, ``q_thermal <= 0``, or COP outside
        ``[COP_MIN, COP_MAX]``).

        Returns
        -------
        bool
            ``True`` if the sample was accepted, ``False`` if rejected.
        """
        if p_electric <= 0.0 or q_thermal <= 0.0:
            _LOGGER.debug(
                "Rejected sample: p_electric=%.1f, q_thermal=%.1f",
                p_electric,
                q_thermal,
            )
            return False

        cop = q_thermal / p_electric
        if cop < COP_MIN or cop > COP_MAX:
            _LOGGER.debug(
                "Rejected sample: computed COP=%.3f outside [%.1f, %.1f]",
                cop,
                COP_MIN,
                COP_MAX,
            )
            return False

        try:
            sample = COPSample(
                t_outdoor=t_outdoor,
                t_supply=t_supply,
                p_electric=p_electric,
                q_thermal=q_thermal,
                cop=cop,
            )
        except ValueError:
            return False

        self._samples.append(sample)
        return True

    # -- Model fitting --------------------------------------------------------

    def fit(self) -> bool:
        """Fit the bilinear regression model from stored samples.

        Model: ``COP = a0 + a1 * T_outdoor + a2 * T_supply``

        Requires at least ``min_samples_hours`` samples.  Returns
        ``True`` if the fit succeeded, ``False`` otherwise.
        """
        if len(self._samples) < self._min_samples_hours:
            _LOGGER.info(
                "Insufficient samples for fit: %d / %d required",
                len(self._samples),
                self._min_samples_hours,
            )
            return False

        t_outdoor = np.array([s.t_outdoor for s in self._samples])
        t_supply = np.array([s.t_supply for s in self._samples])
        cop_values = np.array([s.cop for s in self._samples])

        # Design matrix: [1, T_outdoor, T_supply]
        design = np.column_stack(
            [np.ones(len(self._samples)), t_outdoor, t_supply]
        )

        # Least-squares fit
        result, _, _, _ = np.linalg.lstsq(design, cop_values, rcond=None)
        self._coefficients = result

        _LOGGER.info(
            "COP model fitted: a0=%.4f, a1=%.4f, a2=%.4f "
            "(n_samples=%d)",
            result[0],
            result[1],
            result[2],
            len(self._samples),
        )
        return True

    # -- COP retrieval --------------------------------------------------------

    def get_cop(
        self,
        t_outdoor: float,
        t_supply: float | None = None,
    ) -> float:
        """Return the estimated COP for given conditions.

        Parameters
        ----------
        t_outdoor:
            Outdoor temperature [degC].
        t_supply:
            HP supply temperature [degC].  Optional for LOOKUP_TABLE
            and CONSTANT modes.  Defaults to ``DEFAULT_T_SUPPLY``
            (35.0 degC) in AUTO_LEARNED mode when not provided.

        Returns
        -------
        float
            Estimated COP, clamped to ``[COP_MIN, COP_MAX]``.
        """
        if self._mode is COPMode.CONSTANT:
            return self._default_cop

        if self._mode is COPMode.LOOKUP_TABLE:
            return self._get_cop_lookup(t_outdoor)

        # AUTO_LEARNED mode
        if not self.is_fitted:
            _LOGGER.debug(
                "Auto-learned model not fitted, returning default COP=%.2f",
                self._default_cop,
            )
            return self._default_cop

        if t_supply is None:
            t_supply = DEFAULT_T_SUPPLY

        return self._get_cop_regression(t_outdoor, t_supply)

    def _get_cop_lookup(self, t_outdoor: float) -> float:
        """Interpolate COP from the lookup table."""
        assert self._lookup_t_outdoor is not None
        assert self._lookup_cop is not None
        cop: float = float(
            np.interp(t_outdoor, self._lookup_t_outdoor, self._lookup_cop)
        )
        return self._clamp_cop(cop)

    def _get_cop_regression(
        self, t_outdoor: float, t_supply: float
    ) -> float:
        """Compute COP from the fitted bilinear regression."""
        assert self._coefficients is not None
        cop: float = float(
            self._coefficients[0]
            + self._coefficients[1] * t_outdoor
            + self._coefficients[2] * t_supply
        )
        return self._clamp_cop(cop)

    # -- Utilities ------------------------------------------------------------

    @staticmethod
    def _clamp_cop(cop: float) -> float:
        """Clamp a COP value to ``[COP_MIN, COP_MAX]``."""
        return max(COP_MIN, min(COP_MAX, cop))

    def reset(self) -> None:
        """Clear all stored samples and the fitted model."""
        self._samples.clear()
        self._coefficients = None
        _LOGGER.info("COP calculator reset: samples and model cleared")

    # -- Factory --------------------------------------------------------------

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> COPCalculator:
        """Construct a ``COPCalculator`` from a JSON-serialisable config dict.

        Supported config shapes:

        Constant mode::

            {"mode": "constant", "cop": 3.5}

        Lookup table mode::

            {"mode": "lookup_table", "data": [[-15, 2.5], [0, 3.5], [15, 5.0]]}

        Auto-learned mode::

            {"mode": "auto_learned", "min_samples_hours": 48}

        Parameters
        ----------
        config:
            Configuration dictionary.

        Raises
        ------
        ValueError
            If the mode is unknown or required keys are missing.
        """
        mode_str = config.get("mode")
        if mode_str is None:
            msg = "Config must contain a 'mode' key"
            raise ValueError(msg)

        valid_modes = {m.value for m in COPMode}
        if mode_str not in valid_modes:
            msg = (
                f"Invalid COP mode '{mode_str}'.  "
                f"Valid modes: {', '.join(sorted(valid_modes))}"
            )
            raise ValueError(msg)

        mode = COPMode(mode_str)

        if mode is COPMode.CONSTANT:
            cop_value = config.get("cop", DEFAULT_COP)
            return cls(mode=mode, default_cop=float(cop_value))

        if mode is COPMode.LOOKUP_TABLE:
            data = config.get("data")
            if data is None:
                msg = "LOOKUP_TABLE config must contain a 'data' key"
                raise ValueError(msg)
            if not isinstance(data, list) or len(data) < 2:
                msg = "LOOKUP_TABLE 'data' must be a list with at least 2 entries"
                raise ValueError(msg)
            t_outdoor_arr = np.array([row[0] for row in data], dtype=np.float64)
            cop_arr = np.array([row[1] for row in data], dtype=np.float64)
            return cls(
                mode=mode,
                lookup_t_outdoor=t_outdoor_arr,
                lookup_cop=cop_arr,
            )

        # AUTO_LEARNED
        min_hours = config.get("min_samples_hours", MIN_SAMPLES_HOURS)
        return cls(mode=mode, min_samples_hours=int(min_hours))
