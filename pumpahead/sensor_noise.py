"""Configurable Gaussian sensor noise for simulation measurements.

Provides the ``SensorNoise`` class which adds deterministic Gaussian
noise to temperature measurements.  Noise corrupts only the measurement
snapshot returned to the controller -- it never affects the physical
simulation state inside ``SimulatedRoom``.

Units:
    Temperatures: degC
    Standard deviation: degC
"""

from __future__ import annotations

import numpy as np


class SensorNoise:
    """Adds Gaussian noise to temperature measurements.

    Wraps a seeded ``numpy.random.Generator`` so that noise is
    deterministic across runs with the same seed.

    Typical usage::

        noise = SensorNoise(std=0.1, seed=42)
        noisy_t_room = noise.corrupt(20.5)
        noisy_t_slab = noise.corrupt(22.3)
    """

    def __init__(self, std: float, seed: int = 42) -> None:
        """Initialize the sensor noise source.

        Args:
            std: Standard deviation of the Gaussian noise [degC].
                Must be >= 0.  A value of 0 disables noise (no-op).
            seed: Random seed for reproducibility.
        """
        if std < 0.0:
            raise ValueError(f"std must be >= 0.0, got {std}")
        self._std = std
        self._seed = seed
        self._rng = np.random.default_rng(seed)

    @property
    def std(self) -> float:
        """Return the configured noise standard deviation [degC]."""
        return self._std

    @property
    def seed(self) -> int:
        """Return the random seed."""
        return self._seed

    def corrupt(self, value: float) -> float:
        """Add Gaussian noise to a single temperature value.

        When ``std == 0.0`` the original value is returned unchanged.

        Args:
            value: Clean temperature measurement [degC].

        Returns:
            Noisy temperature measurement [degC].
        """
        if self._std == 0.0:
            return value
        return float(value + self._rng.normal(0.0, self._std))
