"""PID controller and multi-room orchestrator for underfloor heating.

Provides two classes:

``PIDController``
    A discrete PID controller with back-calculation anti-windup.  Takes a
    temperature error (setpoint - measured) and outputs a valve position
    (0-100 %).  Stateful: maintains integral accumulator and previous error.

``PumpAheadController``
    Multi-room orchestrator that manages one ``PIDController`` per room.
    Accepts ``dict[str, Measurements]`` from the simulator and returns
    ``dict[str, Actions]``.  Enforces valve floor minimum in heating mode.

Discretisation uses backward Euler at the configured ``dt`` (default 60 s):

    P = kp * e
    I += ki * e * dt      (with back-calculation anti-windup correction)
    D = kd * (e - e_prev) / dt
    u_raw = P + I + D
    u_clamped = clip(u_raw, 0, 100)

Anti-windup: after clamping, the integral is corrected by
``(u_clamped - u_raw) / ki`` (only when ``ki > 0``).

Units:
    Temperatures: degC
    Valve position: 0-100 %
    Time step: seconds
"""

from __future__ import annotations

from collections.abc import Sequence

from pumpahead.config import ControllerConfig
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.split_coordinator import SplitCoordinator


class PIDController:
    """Discrete PID controller with back-calculation anti-windup.

    Computes a control output (0-100 %) from a temperature error signal.
    Internal state is maintained between calls to :meth:`compute` and
    can be cleared with :meth:`reset`.

    Typical usage::

        pid = PIDController(kp=5.0, ki=0.01, kd=0.0)
        for _ in range(1440):
            error = setpoint - T_room
            valve = pid.compute(error)
    """

    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        dt: float = 60.0,
        output_min: float = 0.0,
        output_max: float = 100.0,
    ) -> None:
        """Initialize the PID controller.

        Args:
            kp: Proportional gain (must be >= 0).
            ki: Integral gain (must be >= 0).
            kd: Derivative gain (must be >= 0).
            dt: Time step [seconds] (must be > 0).
            output_min: Minimum output value.
            output_max: Maximum output value (must be >= output_min).

        Raises:
            ValueError: If any parameter is out of range.
        """
        if kp < 0:
            msg = f"kp must be >= 0, got {kp}"
            raise ValueError(msg)
        if ki < 0:
            msg = f"ki must be >= 0, got {ki}"
            raise ValueError(msg)
        if kd < 0:
            msg = f"kd must be >= 0, got {kd}"
            raise ValueError(msg)
        if dt <= 0:
            msg = f"dt must be > 0, got {dt}"
            raise ValueError(msg)
        if output_max < output_min:
            msg = f"output_max ({output_max}) must be >= output_min ({output_min})"
            raise ValueError(msg)

        self._kp = kp
        self._ki = ki
        self._kd = kd
        self._dt = dt
        self._output_min = output_min
        self._output_max = output_max

        # Internal state
        self._integral: float = 0.0
        self._prev_error: float | None = None
        self._last_output: float = 0.0

    # -- Properties -----------------------------------------------------------

    @property
    def integral(self) -> float:
        """Current integral accumulator value (read-only)."""
        return self._integral

    @property
    def last_output(self) -> float:
        """Output from the most recent :meth:`compute` call (read-only)."""
        return self._last_output

    # -- Public interface -----------------------------------------------------

    def compute(self, error: float) -> float:
        """Compute the PID output for the given error.

        Applies proportional, integral, and derivative terms, clamps the
        result to ``[output_min, output_max]``, and corrects the integral
        via back-calculation anti-windup.

        Args:
            error: Control error (setpoint - measured) [degC].

        Returns:
            Clamped control output (0-100 %).
        """
        # Proportional term
        p_term = self._kp * error

        # Integral term (backward Euler accumulation)
        self._integral += self._ki * error * self._dt

        # Derivative term (zero on first call)
        if self._prev_error is not None:
            d_term = self._kd * (error - self._prev_error) / self._dt
        else:
            d_term = 0.0

        # Raw output
        u_raw = p_term + self._integral + d_term

        # Clamp to output limits
        u_clamped = max(self._output_min, min(self._output_max, u_raw))

        # Back-calculation anti-windup: correct integral
        if self._ki > 0:
            self._integral += u_clamped - u_raw

        # Store state for next call
        self._prev_error = error
        self._last_output = u_clamped

        return u_clamped

    def reset(self) -> None:
        """Reset all internal state to initial values."""
        self._integral = 0.0
        self._prev_error = None
        self._last_output = 0.0


class PumpAheadController:
    """Multi-room controller managing per-room PID instances.

    Orchestrates one ``PIDController`` per room, applies valve floor
    minimum enforcement, and translates measurements into actions.

    Typical usage::

        config = ControllerConfig(kp=5.0, ki=0.01, setpoint=21.0)
        ctrl = PumpAheadController(config, ["salon", "bedroom"])
        actions = ctrl.step(simulator.get_all_measurements())
        simulator.step_all(actions)
    """

    def __init__(
        self,
        config: ControllerConfig,
        room_names: Sequence[str],
        *,
        room_overrides: dict[str, ControllerConfig] | None = None,
        room_has_split: dict[str, bool] | None = None,
    ) -> None:
        """Initialize the multi-room controller.

        Args:
            config: Default controller configuration (PID gains, setpoint,
                valve floor, etc.).
            room_names: Sequence of room identifiers.  Must be non-empty.
            room_overrides: Optional per-room configuration overrides.
                Rooms not listed use the default *config*.
            room_has_split: Optional per-room split availability map.
                When ``None`` (default), all rooms are treated as
                UFH-only (backward compatible).  When provided, rooms
                with ``True`` get a ``SplitCoordinator`` instance.

        Raises:
            ValueError: If *room_names* is empty or contains duplicates,
                or if *room_overrides* references unknown room names.
        """
        names = list(room_names)
        if len(names) == 0:
            msg = "room_names must be non-empty"
            raise ValueError(msg)
        if len(names) != len(set(names)):
            msg = f"room_names must be unique, got {names}"
            raise ValueError(msg)

        overrides = room_overrides or {}
        unknown = set(overrides.keys()) - set(names)
        if unknown:
            msg = f"room_overrides contains unknown room names: {sorted(unknown)}"
            raise ValueError(msg)

        self._config = config
        self._room_names = names
        self._room_configs: dict[str, ControllerConfig] = {}
        self._pids: dict[str, PIDController] = {}
        self._split_coordinators: dict[str, SplitCoordinator] = {}

        split_map = room_has_split or {}

        for name in names:
            cfg = overrides.get(name, config)
            self._room_configs[name] = cfg
            self._pids[name] = PIDController(
                kp=cfg.kp,
                ki=cfg.ki,
                kd=cfg.kd,
                dt=60.0,
            )
            if split_map.get(name, False):
                self._split_coordinators[name] = SplitCoordinator(cfg)

    # -- Properties -----------------------------------------------------------

    @property
    def room_names(self) -> list[str]:
        """List of managed room names (read-only copy)."""
        return list(self._room_names)

    # -- Public interface -----------------------------------------------------

    def step(
        self,
        measurements: dict[str, Measurements],
    ) -> dict[str, Actions]:
        """Compute control actions for all rooms from current measurements.

        For each room:
        1. Compute the error: ``setpoint - T_room``.
        2. Feed the error to the room's ``PIDController``.
        3. Apply valve floor minimum if the room is in heating mode
           and below ``setpoint + deadband``.

        Args:
            measurements: Dictionary of ``Measurements`` keyed by room name.
                Must contain exactly one entry per managed room.

        Returns:
            Dictionary of ``Actions`` keyed by room name.

        Raises:
            ValueError: If measurement keys do not match managed room names.
        """
        meas_names = set(measurements.keys())
        room_set = set(self._room_names)
        if meas_names != room_set:
            missing = room_set - meas_names
            extra = meas_names - room_set
            parts: list[str] = []
            if missing:
                parts.append(f"missing rooms: {sorted(missing)}")
            if extra:
                parts.append(f"unknown rooms: {sorted(extra)}")
            msg = f"Measurement keys do not match room names: {', '.join(parts)}"
            raise ValueError(msg)

        actions: dict[str, Actions] = {}
        for name in self._room_names:
            meas = measurements[name]
            cfg = self._room_configs[name]

            error = cfg.setpoint - meas.T_room
            valve = self._pids[name].compute(error)

            # Valve floor minimum: enforce when HP is heating and room
            # is below setpoint + deadband (room needs heat)
            if (
                meas.hp_mode == HeatPumpMode.HEATING
                and meas.T_room < cfg.setpoint + cfg.deadband
            ):
                valve = max(valve, cfg.valve_floor_pct)

            # Split coordination (only for rooms with a coordinator)
            split_mode = SplitMode.OFF
            split_setpoint = 0.0

            if name in self._split_coordinators:
                decision = self._split_coordinators[name].decide(
                    error=error,
                    setpoint=cfg.setpoint,
                    hp_mode=meas.hp_mode,
                )
                split_mode = decision.split_mode
                split_setpoint = decision.split_setpoint

                # Apply anti-takeover valve boost
                if decision.valve_floor_boost > 0:
                    boosted_floor = cfg.valve_floor_pct + decision.valve_floor_boost
                    valve = max(valve, min(boosted_floor, 100.0))

            actions[name] = Actions(
                valve_position=valve,
                split_mode=split_mode,
                split_setpoint=split_setpoint,
            )

        return actions

    def reset(self) -> None:
        """Reset all per-room PID controllers and split coordinators."""
        for pid in self._pids.values():
            pid.reset()
        for coordinator in self._split_coordinators.values():
            coordinator.reset()

    def get_diagnostics(self) -> dict[str, dict[str, float]]:
        """Return per-room diagnostic information.

        Returns:
            Dictionary keyed by room name.  Each value is a dict with:
            - ``"integral"``: Current integral accumulator.
            - ``"last_output"``: Most recent PID output.
            - ``"setpoint"``: Room setpoint [degC].
            - ``"valve_floor_pct"``: Valve floor minimum [%].
            - ``"split_runtime_minutes"``: Split runtime in the sliding
              window [min] (only for rooms with a split coordinator).
            - ``"anti_takeover_active"``: 1.0 if anti-takeover is
              triggered, 0.0 otherwise (only for rooms with a split
              coordinator).
        """
        result: dict[str, dict[str, float]] = {}
        for name in self._room_names:
            pid = self._pids[name]
            cfg = self._room_configs[name]
            diag: dict[str, float] = {
                "integral": pid.integral,
                "last_output": pid.last_output,
                "setpoint": cfg.setpoint,
                "valve_floor_pct": cfg.valve_floor_pct,
            }
            if name in self._split_coordinators:
                coordinator = self._split_coordinators[name]
                diag["split_runtime_minutes"] = float(coordinator.split_runtime_minutes)
                diag["anti_takeover_active"] = (
                    1.0 if coordinator.anti_takeover_active else 0.0
                )
            result[name] = diag
        return result
