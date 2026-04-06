"""Configuration dataclasses for simulation parameters.

Provides ``CWUCycle`` for modeling domestic hot water (CWU/DHW) interrupts.
When the heat pump switches to DHW mode, floor heating loops lose power
(Q_floor=0) for the cycle duration.

Units:
    All time fields: minutes (simulation convention).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CWUCycle:
    """Defines a repeating CWU (domestic hot water) interrupt schedule.

    During a CWU cycle the heat pump is dedicated to DHW production and
    floor heating loops receive no power (Q_floor=0).

    Attributes:
        start_minute: Simulation minute when the first cycle begins.
        duration_minutes: How long each cycle lasts [min].
        interval_minutes: Repetition period [min].  Set to 0 for a
            single (non-repeating) occurrence.
    """

    start_minute: int
    duration_minutes: int
    interval_minutes: int

    def __post_init__(self) -> None:
        """Validate CWU cycle parameters."""
        if self.start_minute < 0:
            raise ValueError(
                f"start_minute must be >= 0, got {self.start_minute}"
            )
        if self.duration_minutes <= 0:
            raise ValueError(
                f"duration_minutes must be > 0, got {self.duration_minutes}"
            )
        if self.interval_minutes < 0:
            raise ValueError(
                f"interval_minutes must be >= 0, got {self.interval_minutes}"
            )
        if (
            self.interval_minutes > 0
            and self.interval_minutes <= self.duration_minutes
        ):
            raise ValueError(
                f"interval_minutes ({self.interval_minutes}) must be > "
                f"duration_minutes ({self.duration_minutes}) when repeating"
            )
