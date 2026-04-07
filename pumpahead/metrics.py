"""Simulation quality metrics computed from a SimulationLog.

Provides ``SimMetrics``, a frozen dataclass that aggregates per-timestep
simulation records into numeric quality indicators covering comfort,
energy, safety, and system behaviour.

Metrics are computed deterministically via the ``from_log()`` classmethod:
the same ``SimulationLog`` and parameters always produce the same result.

Units follow the simulation convention:
    Temperatures: degC
    Powers: W
    Energy: kWh
    Valve position: 0-100 %
    Percentages: 0-100 %
    Time: minutes
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import SplitMode

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _dew_point(t_air: float, rh: float) -> float:
    """Compute dew-point temperature using the simplified Magnus formula.

    This is the same approximation referenced in the algorithm spec:
    ``T_dew = T_air - (100 - RH) / 5``.

    Args:
        t_air: Air temperature [degC].
        rh: Relative humidity [%] (0-100).

    Returns:
        Estimated dew-point temperature [degC].
    """
    return t_air - (100.0 - rh) / 5.0


# ---------------------------------------------------------------------------
# SimMetrics — frozen aggregation dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimMetrics:
    """Immutable aggregation of simulation quality metrics.

    Computed from a ``SimulationLog`` via the ``from_log()`` classmethod.
    Fields are grouped into four categories:

    **Comfort** -- how well room temperature tracks the setpoint.

    **Split** -- split/AC unit utilisation.

    **Energy** -- total consumption and source breakdown (requires power
    parameters; ``None`` when unknown).

    **Safety** -- floor temperature extremes and condensation protection
    (Axiom #5: ``T_floor >= T_dew + 2``).

    **System** -- heat-pump mode transitions.

    All percentage metrics use the 0-100 scale, consistent with the
    project convention for ``valve_pos`` and ``humidity``.

    Attributes:
        comfort_pct: Percentage of timesteps where ``|T_room - setpoint|
            <= comfort_band`` [0-100 %].
        max_overshoot: Maximum positive deviation ``T_room - setpoint``
            [degC]. Zero when room never exceeds setpoint.
        max_undershoot: Maximum negative deviation ``setpoint - T_room``
            [degC]. Zero when room never falls below setpoint.
        mean_deviation: Mean absolute deviation ``|T_room - setpoint|``
            [degC].
        split_runtime_pct: Percentage of timesteps where the split is
            not OFF [0-100 %].
        energy_kwh: Total energy consumed [kWh].  ``None`` when power
            parameters are not provided.
        peak_power_w: Maximum instantaneous power [W].  ``None`` when
            power parameters are not provided.
        floor_energy_pct: Percentage of total energy delivered by UFH
            [0-100 %].  ``None`` when power parameters are not provided.
        mean_cop: Mean coefficient of performance.  Always ``None`` in
            this milestone -- placeholder for future HP model integration.
        condensation_events: Number of timesteps where
            ``T_floor < T_dew + 2`` (Axiom #5 violation).
        max_floor_temp: Maximum slab/floor temperature [degC].
        min_floor_temp: Minimum slab/floor temperature [degC].
        mode_switches: Number of heat-pump mode transitions (consecutive
            records with differing ``hp_mode``).
    """

    # -- Comfort --------------------------------------------------------------
    comfort_pct: float
    max_overshoot: float
    max_undershoot: float
    mean_deviation: float

    # -- Split ----------------------------------------------------------------
    split_runtime_pct: float

    # -- Energy (nullable) ----------------------------------------------------
    energy_kwh: float | None
    peak_power_w: float | None
    floor_energy_pct: float | None
    mean_cop: float | None

    # -- Safety ---------------------------------------------------------------
    condensation_events: int
    max_floor_temp: float
    min_floor_temp: float

    # -- System ---------------------------------------------------------------
    mode_switches: int

    # -- Factory --------------------------------------------------------------

    @classmethod
    def from_log(
        cls,
        log: SimulationLog,
        setpoint: float,
        *,
        comfort_band: float = 0.5,
        ufh_max_power_w: float | None = None,
        split_power_w: float | None = None,
        dt_minutes: int = 1,
    ) -> SimMetrics:
        """Compute metrics from a simulation log.

        The computation is single-pass over all records, deterministic,
        and safe for empty or single-record logs.

        Args:
            log: Simulation log to analyse.  For multi-room logs the
                caller should filter with ``log.get_room()`` first.
            setpoint: Target room temperature [degC].
            comfort_band: Half-width of the comfort band [degC].
                A timestep is "comfortable" when
                ``|T_room - setpoint| <= comfort_band``.
            ufh_max_power_w: Maximum UFH power [W].  Required (together
                with ``split_power_w``) to compute energy metrics.
            split_power_w: Maximum split power [W].  Required (together
                with ``ufh_max_power_w``) to compute energy metrics.
            dt_minutes: Simulation timestep length [minutes].

        Returns:
            A frozen ``SimMetrics`` instance.
        """
        n = len(log)

        # -- Empty log --------------------------------------------------------
        if n == 0:
            has_energy = (
                ufh_max_power_w is not None and split_power_w is not None
            )
            return cls(
                comfort_pct=0.0,
                max_overshoot=0.0,
                max_undershoot=0.0,
                mean_deviation=0.0,
                split_runtime_pct=0.0,
                energy_kwh=0.0 if has_energy else None,
                peak_power_w=0.0 if has_energy else None,
                floor_energy_pct=0.0 if has_energy else None,
                mean_cop=None,
                condensation_events=0,
                max_floor_temp=0.0,
                min_floor_temp=0.0,
                mode_switches=0,
            )

        # -- Accumulators -----------------------------------------------------
        comfort_count = 0
        max_over = 0.0
        max_under = 0.0
        total_abs_dev = 0.0

        split_on_count = 0

        condensation_count = 0
        floor_max = -1e9
        floor_min = 1e9

        mode_switch_count = 0
        prev_hp_mode = None

        # Energy accumulators (only when power params provided)
        compute_energy = (
            ufh_max_power_w is not None and split_power_w is not None
        )
        total_floor_energy_j = 0.0
        total_split_energy_j = 0.0
        peak_power = 0.0
        dt_seconds = dt_minutes * 60.0

        # -- Single pass ------------------------------------------------------
        for rec in log:
            # Comfort
            deviation = rec.T_room - setpoint
            abs_dev = abs(deviation)
            total_abs_dev += abs_dev

            if abs_dev <= comfort_band:
                comfort_count += 1

            if deviation > max_over:
                max_over = deviation
            if -deviation > max_under:
                max_under = -deviation

            # Split runtime
            if rec.split_mode != SplitMode.OFF:
                split_on_count += 1

            # Safety: floor temperatures
            t_floor = rec.T_floor
            if t_floor > floor_max:
                floor_max = t_floor
            if t_floor < floor_min:
                floor_min = t_floor

            # Safety: condensation (Axiom #5)
            t_dew = _dew_point(rec.T_room, rec.humidity)
            if t_floor < t_dew + 2.0:
                condensation_count += 1

            # System: mode switches
            if prev_hp_mode is not None and rec.hp_mode != prev_hp_mode:
                mode_switch_count += 1
            prev_hp_mode = rec.hp_mode

            # Energy
            if compute_energy:
                assert ufh_max_power_w is not None
                assert split_power_w is not None
                floor_power = (rec.valve_position / 100.0) * ufh_max_power_w
                split_power = (
                    split_power_w
                    if rec.split_mode != SplitMode.OFF
                    else 0.0
                )
                total_power = floor_power + split_power

                total_floor_energy_j += floor_power * dt_seconds
                total_split_energy_j += split_power * dt_seconds
                if total_power > peak_power:
                    peak_power = total_power

        # -- Finalise ---------------------------------------------------------
        comfort_pct = (comfort_count / n) * 100.0
        split_runtime_pct = (split_on_count / n) * 100.0
        mean_deviation = total_abs_dev / n

        # Clamp negative overshoots/undershoots to zero
        max_overshoot = max(max_over, 0.0)
        max_undershoot = max(max_under, 0.0)

        # Energy
        if compute_energy:
            total_energy_j = total_floor_energy_j + total_split_energy_j
            energy_kwh = total_energy_j / 3_600_000.0
            peak_power_w = peak_power
            if total_energy_j > 0.0:
                floor_energy_pct = (
                    total_floor_energy_j / total_energy_j
                ) * 100.0
            else:
                floor_energy_pct = 0.0
        else:
            energy_kwh = None
            peak_power_w = None
            floor_energy_pct = None

        return cls(
            comfort_pct=comfort_pct,
            max_overshoot=max_overshoot,
            max_undershoot=max_undershoot,
            mean_deviation=mean_deviation,
            split_runtime_pct=split_runtime_pct,
            energy_kwh=energy_kwh,
            peak_power_w=peak_power_w,
            floor_energy_pct=floor_energy_pct,
            mean_cop=None,
            condensation_events=condensation_count,
            max_floor_temp=floor_max,
            min_floor_temp=floor_min,
            mode_switches=mode_switch_count,
        )

    # -- Comparison -----------------------------------------------------------

    def compare(self, other: SimMetrics) -> dict[str, float | None]:
        """Compute per-field deltas between this and another ``SimMetrics``.

        For each numeric field, the delta is ``self.value - other.value``.
        A positive delta means ``self`` is higher than ``other``.

        When either side is ``None`` (energy fields without power params),
        the delta is ``None``.

        Non-numeric fields (if any were added) are silently skipped.

        Args:
            other: The ``SimMetrics`` to compare against.

        Returns:
            A dictionary mapping field names to deltas.
        """
        result: dict[str, float | None] = {}
        for f in fields(SimMetrics):
            self_val = getattr(self, f.name)
            other_val = getattr(other, f.name)

            if self_val is None or other_val is None:
                result[f.name] = None
            elif isinstance(self_val, int | float) and isinstance(
                other_val, int | float
            ):
                result[f.name] = float(self_val) - float(other_val)
            # Skip non-numeric fields (none currently, but future-proof)

        return result
