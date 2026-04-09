"""Configurable HP operating-state mapping.

Maps raw state strings reported by any heat pump integration
(HeishaMon, Daikin, Nibe, eBUS, etc.) to internal PumpAhead
operating states.  Supports Axiom 8 (hardware-agnostic): the user
defines the mapping, PumpAhead never hardcodes brand-specific
state strings.
"""

from __future__ import annotations

import logging
from enum import Enum

from pumpahead.simulator import HeatPumpMode

_LOGGER = logging.getLogger(__name__)


class HPOperatingState(Enum):
    """Internal representation of a heat pump's operating state.

    Extends the simulation-level ``HeatPumpMode`` (HEATING / COOLING /
    OFF) with real-world states that the HP entity may report: DHW
    (domestic hot water), IDLE, and DEFROST.
    """

    HEATING = "heating"
    COOLING = "cooling"
    DHW = "dhw"
    IDLE = "idle"
    DEFROST = "defrost"


class HPModeMapper:
    """Stateless mapper from raw HP entity state strings to ``HPOperatingState``.

    Parameters
    ----------
    mapping:
        User-configured dict mapping raw state strings to
        ``HPOperatingState`` members.  Keys are normalised to
        lowercase at construction time.
    default:
        Fallback state returned for unknown raw state strings.
        Defaults to ``HPOperatingState.IDLE``.
    """

    def __init__(
        self,
        mapping: dict[str, HPOperatingState],
        default: HPOperatingState = HPOperatingState.IDLE,
    ) -> None:
        self._mapping: dict[str, HPOperatingState] = {
            k.strip().lower(): v for k, v in mapping.items()
        }
        self._default = default

    # -- Mapping -------------------------------------------------------------

    def map(self, raw_state: str) -> HPOperatingState:
        """Translate a raw HP entity state string to ``HPOperatingState``.

        Matching is case-insensitive and strips surrounding whitespace.
        Unknown states are logged as a warning and fall back to
        ``self._default``.
        """
        normalised = raw_state.strip().lower()
        result = self._mapping.get(normalised)
        if result is not None:
            return result

        _LOGGER.warning(
            "Unknown HP state '%s', falling back to %s",
            raw_state,
            self._default.value,
        )
        return self._default

    # -- Conversion to simulator enum ----------------------------------------

    @staticmethod
    def to_heat_pump_mode(state: HPOperatingState) -> HeatPumpMode:
        """Convert ``HPOperatingState`` to the simulator's ``HeatPumpMode``.

        ``HEATING`` -> ``HeatPumpMode.HEATING``,
        ``COOLING`` -> ``HeatPumpMode.COOLING``,
        everything else -> ``HeatPumpMode.OFF``.
        """
        if state is HPOperatingState.HEATING:
            return HeatPumpMode.HEATING
        if state is HPOperatingState.COOLING:
            return HeatPumpMode.COOLING
        return HeatPumpMode.OFF

    # -- Serialisation helpers -----------------------------------------------

    @classmethod
    def from_config(cls, config: dict[str, str]) -> HPModeMapper:
        """Construct a mapper from a JSON-serialisable config dict.

        Parameters
        ----------
        config:
            Mapping of raw state strings to ``HPOperatingState`` value
            strings, e.g. ``{"Heat": "heating", "Cool": "cooling"}``.

        Raises
        ------
        ValueError
            If any target value is not a valid ``HPOperatingState``
            member.
        """
        valid_values = {s.value for s in HPOperatingState}
        mapping: dict[str, HPOperatingState] = {}
        for raw_key, target_value in config.items():
            if target_value not in valid_values:
                msg = (
                    f"Invalid HP operating state '{target_value}' for "
                    f"key '{raw_key}'.  Valid values: "
                    f"{', '.join(sorted(valid_values))}"
                )
                raise ValueError(msg)
            mapping[raw_key] = HPOperatingState(target_value)
        return cls(mapping)
