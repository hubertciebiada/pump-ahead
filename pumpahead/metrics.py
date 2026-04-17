"""Simulation quality metrics and assertion functions.

Provides ``SimMetrics``, a frozen dataclass that aggregates per-timestep
simulation records into numeric quality indicators covering comfort,
energy, safety, and system behaviour.

Metrics are computed deterministically via the ``from_log()`` classmethod:
the same ``SimulationLog`` and parameters always produce the same result.

Also provides five assertion functions that validate simulation logs for
correctness.  Each raises ``AssertionError`` with a diagnostic message
when a constraint is violated:

    - ``assert_comfort`` — comfort percentage above threshold
    - ``assert_floor_temp_safe`` — floor temperature within safe bounds
    - ``assert_no_priority_inversion`` — split runtime below threshold
    - ``assert_no_opposing_action`` — no split opposing the HP mode
    - ``assert_energy_vs_baseline`` — energy not exceeding baseline
    - ``assert_no_freezing`` — no room ever drops below a hard minimum
    - ``assert_no_prolonged_cold`` — no room stays cold for too long

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

from pumpahead.dew_point import dew_point as _dew_point
from pumpahead.simulation_log import SimRecord, SimulationLog
from pumpahead.simulator import HeatPumpMode, SplitMode

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
        ufh_nominal_power_w: float | None = None,
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
            ufh_nominal_power_w: Maximum UFH power [W].  Required (together
                with ``split_power_w``) to compute energy metrics.
            split_power_w: Maximum split power [W].  Required (together
                with ``ufh_nominal_power_w``) to compute energy metrics.
            dt_minutes: Simulation timestep length [minutes].

        Returns:
            A frozen ``SimMetrics`` instance.
        """
        n = len(log)

        # -- Empty log --------------------------------------------------------
        if n == 0:
            has_energy = ufh_nominal_power_w is not None and split_power_w is not None
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
        compute_energy = ufh_nominal_power_w is not None and split_power_w is not None
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
                assert ufh_nominal_power_w is not None
                assert split_power_w is not None
                floor_power = (rec.valve_position / 100.0) * ufh_nominal_power_w
                split_power = split_power_w if rec.split_mode != SplitMode.OFF else 0.0
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
                floor_energy_pct = (total_floor_energy_j / total_energy_j) * 100.0
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


# ---------------------------------------------------------------------------
# Assertion functions
# ---------------------------------------------------------------------------


def assert_comfort(
    log: SimulationLog,
    setpoint: float,
    *,
    comfort_band: float = 0.5,
    threshold: float = 90.0,
) -> None:
    """Assert that the comfort percentage meets or exceeds *threshold*.

    A timestep is "comfortable" when ``|T_room - setpoint| <= comfort_band``.
    The comfort percentage is the fraction of comfortable timesteps (0-100).

    Args:
        log: Simulation log to check.
        setpoint: Target room temperature [degC].
        comfort_band: Half-width of the comfort band [degC].
        threshold: Minimum acceptable comfort percentage [0-100 %].

    Raises:
        AssertionError: If the log is empty (no data to assess comfort) or
            the comfort percentage is below *threshold*.
    """
    n = len(log)
    if n == 0:
        msg = "assert_comfort: empty log — cannot assess comfort"
        raise AssertionError(msg)

    comfort_count = 0
    for rec in log:
        if abs(rec.T_room - setpoint) <= comfort_band:
            comfort_count += 1

    comfort_pct = (comfort_count / n) * 100.0

    if comfort_pct < threshold:
        msg = (
            f"assert_comfort: comfort {comfort_pct:.1f}% is below "
            f"threshold {threshold:.1f}% "
            f"(setpoint={setpoint}, band={comfort_band}, "
            f"comfortable={comfort_count}/{n})"
        )
        raise AssertionError(msg)


def assert_floor_temp_safe(
    log: SimulationLog,
    *,
    max_temp: float = 34.0,
) -> None:
    """Assert floor temperature is safe at every timestep.

    Checks two constraints per record (Axioms #4 and #5):

    1. ``T_floor <= max_temp`` — hard ceiling (default 34 degC).
    2. ``T_floor >= T_dew + 2`` — condensation protection.

    Empty logs pass silently (no records to violate).

    Args:
        log: Simulation log to check.
        max_temp: Maximum allowed floor temperature [degC].

    Raises:
        AssertionError: On the first record that violates either
            constraint.  The message includes the timestep and
            temperature values.
    """
    for rec in log:
        t_floor = rec.T_floor

        if t_floor > max_temp:
            msg = (
                f"assert_floor_temp_safe: T_floor={t_floor:.2f} degC "
                f"exceeds max {max_temp:.2f} degC at t={rec.t}"
            )
            raise AssertionError(msg)

        t_dew = _dew_point(rec.T_room, rec.humidity)
        if t_floor < t_dew + 2.0:
            msg = (
                f"assert_floor_temp_safe: T_floor={t_floor:.2f} degC "
                f"< T_dew+2={t_dew + 2.0:.2f} degC "
                f"(condensation risk) at t={rec.t}"
            )
            raise AssertionError(msg)


def assert_no_priority_inversion(
    log: SimulationLog,
    *,
    max_split_pct: float = 50.0,
) -> None:
    """Assert that split runtime does not exceed *max_split_pct*.

    Priority inversion occurs when the split/AC unit runs for too large a
    fraction of the simulation, becoming the de-facto primary heat source
    (violating Axiom #2).

    Args:
        log: Simulation log to check.
        max_split_pct: Maximum allowed split runtime percentage [0-100 %].

    Raises:
        AssertionError: If the log is empty (no data to assess) or the
            split runtime percentage exceeds *max_split_pct*.
    """
    n = len(log)
    if n == 0:
        msg = "assert_no_priority_inversion: empty log — cannot assess split runtime"
        raise AssertionError(msg)

    split_on_count = 0
    for rec in log:
        if rec.split_mode != SplitMode.OFF:
            split_on_count += 1

    split_pct = (split_on_count / n) * 100.0

    if split_pct > max_split_pct:
        msg = (
            f"assert_no_priority_inversion: split runtime "
            f"{split_pct:.1f}% exceeds max {max_split_pct:.1f}% "
            f"(split_on={split_on_count}/{n})"
        )
        raise AssertionError(msg)


def assert_no_opposing_action(log: SimulationLog) -> None:
    """Assert that no split action opposes the heat-pump mode.

    Axiom #3: splits never oppose the mode.  Specifically:

    - In ``HEATING`` mode the split must not be ``COOLING``.
    - In ``COOLING`` mode the split must not be ``HEATING``.
    - When the heat pump is ``OFF``, any split mode is acceptable.

    Empty logs pass silently (no records to violate).

    Args:
        log: Simulation log to check.

    Raises:
        AssertionError: On the first record where the split opposes
            the HP mode.  The message includes the timestep and modes.
    """
    for rec in log:
        if rec.hp_mode == HeatPumpMode.OFF:
            continue

        if rec.hp_mode == HeatPumpMode.HEATING and rec.split_mode == SplitMode.COOLING:
            msg = (
                f"assert_no_opposing_action: split COOLING while HP "
                f"HEATING at t={rec.t}"
            )
            raise AssertionError(msg)

        if rec.hp_mode == HeatPumpMode.COOLING and rec.split_mode == SplitMode.HEATING:
            msg = (
                f"assert_no_opposing_action: split HEATING while HP "
                f"COOLING at t={rec.t}"
            )
            raise AssertionError(msg)


def assert_energy_vs_baseline(
    log: SimulationLog,
    baseline_log: SimulationLog,
    *,
    max_increase: float = 0.1,
    setpoint: float,
    ufh_nominal_power_w: float,
    split_power_w: float,
    dt_minutes: int = 1,
) -> None:
    """Assert that total energy does not exceed the baseline by too much.

    Computes ``SimMetrics.from_log()`` for both *log* and *baseline_log*,
    then checks that the test energy is within
    ``(1 + max_increase) * baseline_energy``.

    Args:
        log: Test simulation log.
        baseline_log: Baseline simulation log for comparison.
        max_increase: Maximum allowed fractional increase (e.g. 0.1 = 10%).
        setpoint: Target room temperature [degC] (passed to ``from_log``).
        ufh_nominal_power_w: Maximum UFH power [W].
        split_power_w: Maximum split power [W].
        dt_minutes: Simulation timestep length [minutes].

    Raises:
        AssertionError: If the test energy exceeds the baseline by more
            than *max_increase* fraction.  Also raises when the baseline
            has zero energy but the test has non-zero energy.
    """
    test_metrics = SimMetrics.from_log(
        log,
        setpoint=setpoint,
        ufh_nominal_power_w=ufh_nominal_power_w,
        split_power_w=split_power_w,
        dt_minutes=dt_minutes,
    )
    baseline_metrics = SimMetrics.from_log(
        baseline_log,
        setpoint=setpoint,
        ufh_nominal_power_w=ufh_nominal_power_w,
        split_power_w=split_power_w,
        dt_minutes=dt_minutes,
    )

    assert test_metrics.energy_kwh is not None
    assert baseline_metrics.energy_kwh is not None

    test_energy = test_metrics.energy_kwh
    baseline_energy = baseline_metrics.energy_kwh

    if baseline_energy == 0.0:
        if test_energy > 0.0:
            msg = (
                f"assert_energy_vs_baseline: test energy "
                f"{test_energy:.4f} kWh > 0 with zero baseline"
            )
            raise AssertionError(msg)
        return

    increase = (test_energy - baseline_energy) / baseline_energy

    if increase > max_increase:
        msg = (
            f"assert_energy_vs_baseline: test energy "
            f"{test_energy:.4f} kWh exceeds baseline "
            f"{baseline_energy:.4f} kWh by {increase:.1%} "
            f"(max allowed: {max_increase:.1%})"
        )
        raise AssertionError(msg)


def assert_no_freezing(
    log: SimulationLog,
    *,
    hard_min: float = 16.0,
) -> None:
    """Assert that no room ever drops below ``hard_min`` degC.

    Hard-fail comfort assertion: a single record with
    ``T_room < hard_min`` is enough to fail.  Multi-room aware -- every
    record is checked regardless of ``room_name``, so an interleaved
    multi-room log is handled correctly.

    Empty logs pass silently (matches ``assert_floor_temp_safe``).

    Args:
        log: Simulation log to check.
        hard_min: Hard minimum room temperature [degC].  Default 16.0.

    Raises:
        AssertionError: On the first record where
            ``T_room < hard_min``.  The diagnostic message includes the
            room name, simulation time, temperature, and threshold.
    """
    for rec in log:
        if rec.T_room < hard_min:
            room_label = rec.room_name if rec.room_name else "<unnamed>"
            msg = (
                f"assert_no_freezing: T_room={rec.T_room:.2f} degC "
                f"< hard_min={hard_min:.2f} degC "
                f"in room '{room_label}' at t={rec.t} min"
            )
            raise AssertionError(msg)


def _raise_prolonged_cold(
    room_name: str,
    run_start_t: int,
    duration: int,
    min_temp: float,
    threshold: float,
    max_duration_minutes: int,
) -> None:
    """Raise ``AssertionError`` for a prolonged cold-run violation."""
    room_label = room_name if room_name else "<unnamed>"
    msg = (
        f"assert_no_prolonged_cold: room '{room_label}' stayed below "
        f"{threshold:.2f} degC for {duration} min "
        f"(max allowed: {max_duration_minutes} min) "
        f"starting at t={run_start_t} min, "
        f"reaching min T_room={min_temp:.2f} degC"
    )
    raise AssertionError(msg)


def assert_no_prolonged_cold(
    log: SimulationLog,
    *,
    threshold: float = 18.0,
    max_duration_minutes: int = 1440,
) -> None:
    """Assert no room stays below ``threshold`` for more than ``max_duration_minutes``.

    A "cold run" is a maximal contiguous block of records (per room)
    where ``T_room < threshold``.  The duration of a run is the
    difference in ``rec.t`` between the last and first records of the
    block.  A run resets the moment a record meets or exceeds the
    threshold.

    Multi-room aware: records are grouped by ``room_name`` and each
    room's chronological sequence is scanned independently.  The check
    raises on the first room/run that exceeds ``max_duration_minutes``.

    Empty logs pass silently.

    Args:
        log: Simulation log to check.
        threshold: Cold-run temperature ceiling [degC].  A record with
            ``T_room < threshold`` extends the current cold run.
            Default 18.0.
        max_duration_minutes: Maximum allowed cold-run duration
            [minutes].  Default 1440 (24 hours).

    Raises:
        AssertionError: On the first cold run whose duration strictly
            exceeds ``max_duration_minutes``.  The diagnostic message
            includes the room name, run start time, duration, and the
            minimum temperature reached during the run.
    """
    by_room: dict[str, list[SimRecord]] = {}
    for rec in log:
        by_room.setdefault(rec.room_name, []).append(rec)

    for room_name, records in by_room.items():
        run_start_t: int | None = None
        run_min_temp = float("inf")
        for rec in records:
            if rec.T_room < threshold:
                if run_start_t is None:
                    run_start_t = rec.t
                    run_min_temp = rec.T_room
                elif rec.T_room < run_min_temp:
                    run_min_temp = rec.T_room
                duration = rec.t - run_start_t
                if duration > max_duration_minutes:
                    _raise_prolonged_cold(
                        room_name,
                        run_start_t,
                        duration,
                        run_min_temp,
                        threshold,
                        max_duration_minutes,
                    )
            else:
                run_start_t = None
                run_min_temp = float("inf")
