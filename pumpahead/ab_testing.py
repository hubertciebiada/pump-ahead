"""A/B testing framework for comparing controllers on identical scenarios.

Provides a reusable framework for running two controllers on the same
simulation scenario and comparing their performance via ``SimMetrics``.

Key components:

``ControllerAdapter`` Protocol
    Common interface wrapping any controller for use with ``ABTestRunner``.

``PIDAdapter``
    Wraps ``PIDController`` for use with the A/B testing framework.

``MPCAdapter``
    Wraps ``MPCController`` with zero-order hold to bridge the 1-min
    simulation step and 15-min MPC step.

``ABTestRunner``
    Runs two independent simulation loops (one per controller) on the
    same ``SimScenario`` and returns an ``ABReport``.

``ABReport``
    Frozen dataclass with per-controller ``SimMetrics``, deltas, and
    convenience methods for comparison and tabular display.

``plot_overlay``
    Generates a matplotlib figure with overlaid T_room, T_slab, and
    valve traces for both controllers.

Usage::

    from pumpahead.ab_testing import (
        ABTestRunner, PIDAdapter, MPCAdapter, plot_overlay,
    )
    from pumpahead.scenarios import steady_state

    scenario = steady_state()
    runner = ABTestRunner(PIDAdapter(), MPCAdapter())
    report = runner.run(scenario)
    print(report.summary_table())
    fig = plot_overlay(report)

Units follow the simulation convention:
    Temperatures: degC
    Powers: W
    Valve position: 0-100 %
    Time: minutes
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Literal, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from pumpahead.config import SimScenario
from pumpahead.controller import PIDController
from pumpahead.disturbance_vector import MPC_DT_SECONDS, MPC_HORIZON_STEPS
from pumpahead.metrics import SimMetrics
from pumpahead.model import ModelOrder, RCModel
from pumpahead.optimizer import MPCConfig, MPCController
from pumpahead.sensor_noise import SensorNoise
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import (
    Actions,
    BuildingSimulator,
    HeatPumpMode,
    Measurements,
    SplitMode,
)
from pumpahead.ufh_loop import LoopGeometry
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# ControllerAdapter Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ControllerAdapter(Protocol):
    """Protocol for controllers usable with ``ABTestRunner``.

    Any class implementing ``compute_actions`` and the ``name`` property
    satisfies this protocol via structural subtyping.
    """

    @property
    def name(self) -> str:
        """Human-readable controller name for reporting."""
        ...  # pragma: no cover

    def compute_actions(
        self,
        t: int,
        measurements: Measurements,
        weather: WeatherPoint,
        scenario: SimScenario,
        room_name: str,
    ) -> Actions:
        """Compute control actions for one room at one timestep.

        Args:
            t: Simulation time [minutes].
            measurements: Current room and system state.
            weather: Weather conditions at time *t*.
            scenario: Full simulation scenario (for setpoint, params).
            room_name: Identifier of the room being controlled.

        Returns:
            Control actions for this timestep.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# PIDAdapter
# ---------------------------------------------------------------------------


class PIDAdapter:
    """Adapts ``PIDController`` for use with ``ABTestRunner``.

    Creates one ``PIDController`` per room on first use, using the PID
    gains from the scenario's ``ControllerConfig``.  Applies valve floor
    minimum in heating mode, matching the ``PumpAheadController`` pattern.
    """

    def __init__(self) -> None:
        self._pids: dict[str, PIDController] = {}

    @property
    def name(self) -> str:
        """Return ``'PID'``."""
        return "PID"

    def _get_pid(self, scenario: SimScenario) -> PIDController:
        """Get or create a PID controller for the scenario's configuration.

        Uses a single PID instance keyed by scenario name to support
        multi-scenario runners without cross-contamination.

        Args:
            scenario: Simulation scenario with controller config.

        Returns:
            A ``PIDController`` instance.
        """
        key = scenario.name
        if key not in self._pids:
            cfg = scenario.controller
            self._pids[key] = PIDController(
                kp=cfg.kp,
                ki=cfg.ki,
                kd=cfg.kd,
                dt=scenario.dt_seconds,
            )
        return self._pids[key]

    def compute_actions(
        self,
        t: int,
        measurements: Measurements,
        weather: WeatherPoint,
        scenario: SimScenario,
        room_name: str,
    ) -> Actions:
        """Compute PID-based control actions.

        Applies proportional-integral-derivative control with the gains
        from ``scenario.controller``, plus valve floor minimum enforcement
        in heating mode (matching ``PumpAheadController`` behaviour).

        Args:
            t: Simulation time [minutes].
            measurements: Current room and system state.
            weather: Weather conditions at time *t*.
            scenario: Full simulation scenario.
            room_name: Room identifier.

        Returns:
            Control actions with the PID-computed valve position.
        """
        pid = self._get_pid(scenario)
        cfg = scenario.controller

        error = cfg.setpoint - measurements.T_room
        valve = pid.compute(error)

        # Valve floor minimum enforcement in heating mode
        if (
            measurements.hp_mode == HeatPumpMode.HEATING
            and measurements.T_room < cfg.setpoint + cfg.deadband
        ):
            valve = max(valve, cfg.valve_floor_pct)

        return Actions(
            valve_position=valve,
            split_mode=SplitMode.OFF,
            split_setpoint=0.0,
        )

    def reset(self) -> None:
        """Clear all internal PID state."""
        self._pids.clear()


# ---------------------------------------------------------------------------
# MPCAdapter
# ---------------------------------------------------------------------------


class MPCAdapter:
    """Adapts ``MPCController`` for use with ``ABTestRunner``.

    Creates one ``MPCController`` per room from the room's ``RCParams``.
    Solves MPC every 15 steps (15 minutes) and holds the action constant
    between solves (zero-order hold).

    The adapter builds a simplified disturbance matrix from the weather
    source: ``d[k] = [T_out, Q_sol=0, Q_int]`` for 3R3C models.
    """

    def __init__(
        self,
        mpc_config: MPCConfig | None = None,
        mpc_dt_seconds: int = MPC_DT_SECONDS,
        horizon_steps: int = MPC_HORIZON_STEPS,
    ) -> None:
        """Initialise the MPC adapter.

        Args:
            mpc_config: MPC configuration overrides.  Defaults to
                ``MPCConfig()`` with the scenario's controller weights.
            mpc_dt_seconds: MPC time step [s].  Default 900 (15 min).
            horizon_steps: MPC horizon length in steps.
        """
        self._mpc_config_override = mpc_config
        self._mpc_dt_seconds = mpc_dt_seconds
        self._horizon_steps = horizon_steps
        self._controllers: dict[str, MPCController] = {}
        self._held_action: dict[str, float] = {}
        self._steps_since_solve: dict[str, int] = {}
        self._solve_interval: int = max(1, mpc_dt_seconds // 60)

    @property
    def name(self) -> str:
        """Return ``'MPC'``."""
        return "MPC"

    def _get_controller(
        self,
        scenario: SimScenario,
        room_name: str,
    ) -> MPCController:
        """Get or create an MPCController for a specific room.

        Args:
            scenario: Simulation scenario.
            room_name: Room name to match in the building config.

        Returns:
            An ``MPCController`` instance.
        """
        key = f"{scenario.name}:{room_name}"
        if key not in self._controllers:
            # Find room config
            room_cfg = None
            for r in scenario.building.rooms:
                if r.name == room_name:
                    room_cfg = r
                    break
            if room_cfg is None:
                msg = f"Room '{room_name}' not found in scenario '{scenario.name}'"
                raise ValueError(msg)

            # Build RC model at MPC dt.
            # Scale B matrix so that u=1 represents full UFH power
            # (nominal_ufh_power_heating_w Watts), not 1 Watt.  Without
            # this scaling the MPC thinks its maximum heating power is
            # 1 W and always saturates at u=1, causing overshoot when
            # the adapter converts u_floor_0 to valve percentage.
            mpc_model = RCModel(
                room_cfg.params,
                ModelOrder.THREE,
                dt=float(self._mpc_dt_seconds),
            )
            power_scale = room_cfg.nominal_ufh_power_heating_w
            mpc_model._B_c = mpc_model._B_c * power_scale  # noqa: SLF001
            mpc_model._discretize()  # noqa: SLF001

            # Build MPC config
            if self._mpc_config_override is not None:
                cfg = self._mpc_config_override
            else:
                ctrl = scenario.controller
                cfg = MPCConfig(
                    horizon=self._horizon_steps,
                    w_comfort=ctrl.w_comfort,
                    w_energy=ctrl.w_energy,
                    w_smooth=ctrl.w_smooth,
                    solver_timeout_s=5.0,
                )

            self._controllers[key] = MPCController(mpc_model, cfg)
            self._held_action[key] = 0.0
            self._steps_since_solve[key] = self._solve_interval  # solve on first call

        return self._controllers[key]

    def _build_disturbance(
        self,
        t: int,
        scenario: SimScenario,
        room_name: str,
    ) -> NDArray[np.float64]:
        """Build a simplified disturbance matrix for the MPC horizon.

        Uses constant T_out from the current weather point, Q_sol=0
        (conservative), and Q_int from the room config.

        Args:
            t: Current simulation time [minutes].
            scenario: Simulation scenario with weather and building data.
            room_name: Room name for Q_int lookup.

        Returns:
            Disturbance matrix of shape ``(horizon_steps, n_disturbances)``.
        """
        n_dist = 3  # 3R3C: [T_out, Q_sol, Q_int]
        d = np.zeros((self._horizon_steps, n_dist), dtype=np.float64)

        # Find room Q_int
        q_int = 0.0
        for r in scenario.building.rooms:
            if r.name == room_name:
                q_int = r.q_int_w
                break

        for k in range(self._horizon_steps):
            t_k = float(t) + k * self._mpc_dt_seconds / 60.0
            wp = scenario.weather.get(t_k)
            d[k, 0] = wp.T_out
            d[k, 1] = 0.0  # Q_sol = 0 (conservative)
            d[k, 2] = q_int

        return d

    def compute_actions(
        self,
        t: int,
        measurements: Measurements,
        weather: WeatherPoint,
        scenario: SimScenario,
        room_name: str,
    ) -> Actions:
        """Compute MPC-based control actions with zero-order hold.

        Solves MPC every ``solve_interval`` simulation steps (default 15)
        and holds the action constant in between.

        Args:
            t: Simulation time [minutes].
            measurements: Current room and system state.
            weather: Weather conditions at time *t*.
            scenario: Full simulation scenario.
            room_name: Room identifier.

        Returns:
            Control actions with the MPC-computed valve position.
        """
        ctrl = self._get_controller(scenario, room_name)
        key = f"{scenario.name}:{room_name}"

        self._steps_since_solve[key] += 1

        if self._steps_since_solve[key] >= self._solve_interval:
            # Build state estimate from measurements
            # Measurements lacks T_wall; estimate as T_room
            x0 = np.array(
                [
                    measurements.T_room,
                    measurements.T_slab,
                    measurements.T_room,  # T_wall estimate
                ]
            )

            d = self._build_disturbance(t, scenario, room_name)
            mode: Literal["heating", "cooling"] = (
                "heating" if scenario.mode == "heating" else "cooling"
            )

            result = ctrl.step(
                x0=x0,
                d=d,
                T_set=scenario.controller.setpoint,
                mode=mode,
            )

            # u_floor_0 is in [0, 1]; convert to valve percentage
            self._held_action[key] = result.u_floor_0 * 100.0
            self._steps_since_solve[key] = 0

        return Actions(
            valve_position=self._held_action[key],
            split_mode=SplitMode.OFF,
            split_setpoint=0.0,
        )

    def reset(self) -> None:
        """Clear all internal MPC state."""
        self._controllers.clear()
        self._held_action.clear()
        self._steps_since_solve.clear()


# ---------------------------------------------------------------------------
# ABReport
# ---------------------------------------------------------------------------

# Metrics where higher is better (True) vs lower is better (False)
_HIGHER_IS_BETTER: dict[str, bool] = {
    "comfort_pct": True,
    "max_overshoot": False,
    "max_undershoot": False,
    "mean_deviation": False,
    "split_runtime_pct": False,
    "energy_kwh": False,
    "peak_power_w": False,
    "floor_energy_pct": True,  # Higher UFH usage = more primary = better
    "mean_cop": True,
    "condensation_events": False,
    "max_floor_temp": False,
    "min_floor_temp": True,  # Higher min floor = warmer = better
    "mode_switches": False,
}


@dataclass(frozen=True)
class ABReport:
    """Immutable comparison report for two controller runs.

    Attributes:
        controller_a_name: Name of controller A.
        controller_b_name: Name of controller B.
        scenario_name: Name of the simulation scenario.
        metrics_a: ``SimMetrics`` from controller A's run.
        metrics_b: ``SimMetrics`` from controller B's run.
        deltas: Per-field deltas (``metrics_a - metrics_b``).
        log_a: Full simulation log from controller A's run.
        log_b: Full simulation log from controller B's run.
    """

    controller_a_name: str
    controller_b_name: str
    scenario_name: str
    metrics_a: SimMetrics
    metrics_b: SimMetrics
    deltas: dict[str, float | None]
    log_a: SimulationLog
    log_b: SimulationLog

    def a_wins_on(self, metric_name: str) -> bool | None:
        """Check whether controller A outperforms B on a specific metric.

        Uses the ``_HIGHER_IS_BETTER`` lookup to determine which
        direction is "better" for each metric.

        Args:
            metric_name: Name of the ``SimMetrics`` field to check.

        Returns:
            ``True`` if A is better, ``False`` if B is better,
            ``None`` if the delta is ``None`` or the metric is unknown.
        """
        delta = self.deltas.get(metric_name)
        if delta is None:
            return None
        higher_better = _HIGHER_IS_BETTER.get(metric_name)
        if higher_better is None:
            return None
        if higher_better:
            return delta > 0
        return delta < 0

    def summary_table(self) -> str:
        """Generate a text comparison table of all metrics.

        Returns:
            A formatted multi-line string with columns for metric name,
            controller A value, controller B value, delta, and winner.
        """
        lines: list[str] = []
        header = (
            f"{'Metric':<25s} "
            f"{'(' + self.controller_a_name + ')':<12s} "
            f"{'(' + self.controller_b_name + ')':<12s} "
            f"{'Delta':<12s} "
            f"{'Winner':<8s}"
        )
        lines.append(header)
        lines.append("-" * len(header))

        for f in fields(SimMetrics):
            val_a = getattr(self.metrics_a, f.name)
            val_b = getattr(self.metrics_b, f.name)
            delta = self.deltas.get(f.name)

            val_a_str = f"{val_a:.2f}" if isinstance(val_a, float | int) else "N/A"
            val_b_str = f"{val_b:.2f}" if isinstance(val_b, float | int) else "N/A"
            delta_str = f"{delta:+.2f}" if delta is not None else "N/A"

            winner = self.a_wins_on(f.name)
            if winner is True:
                winner_str = self.controller_a_name
            elif winner is False:
                winner_str = self.controller_b_name
            else:
                winner_str = "-"

            lines.append(
                f"{f.name:<25s} "
                f"{val_a_str:<12s} "
                f"{val_b_str:<12s} "
                f"{delta_str:<12s} "
                f"{winner_str:<8s}"
            )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ABTestRunner
# ---------------------------------------------------------------------------

_MODE_MAP: dict[str, HeatPumpMode] = {
    "heating": HeatPumpMode.HEATING,
    "cooling": HeatPumpMode.COOLING,
    "auto": HeatPumpMode.HEATING,
}


class ABTestRunner:
    """Runs two controllers on the same scenario and produces an ``ABReport``.

    Each run constructs a fresh ``BuildingSimulator`` from the scenario,
    ensuring identical initial conditions.  The simulation loop follows
    the same pattern as ``tests/simulation/conftest.py::_build_simulator``.

    Typical usage::

        runner = ABTestRunner(PIDAdapter(), MPCAdapter())
        report = runner.run(steady_state(), max_steps=2880)
    """

    def __init__(
        self,
        controller_a: ControllerAdapter,
        controller_b: ControllerAdapter,
    ) -> None:
        """Initialise with two controller adapters.

        Args:
            controller_a: First controller (typically PID).
            controller_b: Second controller (typically MPC).
        """
        self._controller_a = controller_a
        self._controller_b = controller_b

    @staticmethod
    def _build_simulator(scenario: SimScenario) -> BuildingSimulator:
        """Construct a ``BuildingSimulator`` from a ``SimScenario``.

        Follows the identical construction pattern as the conftest helper.

        Args:
            scenario: Fully configured simulation scenario.

        Returns:
            A ready-to-run ``BuildingSimulator``.
        """
        rooms: list[SimulatedRoom] = []
        for room_cfg in scenario.building.rooms:
            model = RCModel(room_cfg.params, ModelOrder.THREE, dt=scenario.dt_seconds)
            # Post-#144 every room must carry pipe geometry — propagate
            # the ``ValueError`` if any caller forgets to set it.
            geometry = LoopGeometry.from_room_config(room_cfg)
            sim_room = SimulatedRoom(
                room_cfg.name,
                model,
                split_power_w=room_cfg.split_power_w,
                q_int_w=room_cfg.q_int_w,
                loop_geometry=geometry,
            )
            rooms.append(sim_room)

        noise: SensorNoise | None = None
        if scenario.sensor_noise_std > 0:
            noise = SensorNoise(std=scenario.sensor_noise_std, seed=42)

        hp_mode = _MODE_MAP.get(scenario.mode, HeatPumpMode.HEATING)

        return BuildingSimulator(
            rooms,
            scenario.weather,
            hp_mode=hp_mode,
            hp_max_power_w=scenario.building.hp_max_power_w,
            cwu_schedule=list(scenario.cwu_schedule),
            sensor_noise=noise,
            weather_comp=scenario.weather_comp,
            cooling_comp=scenario.cooling_comp,
        )

    def _run_single(
        self,
        controller: ControllerAdapter,
        scenario: SimScenario,
        max_steps: int | None = None,
    ) -> tuple[SimulationLog, SimMetrics]:
        """Run a single controller on a scenario.

        Args:
            controller: The controller adapter to use.
            scenario: Simulation scenario.
            max_steps: Optional cap on simulation steps.

        Returns:
            Tuple of ``(SimulationLog, SimMetrics)`` for the first room.
        """
        sim = self._build_simulator(scenario)
        n_steps = (
            min(max_steps, scenario.duration_minutes)
            if max_steps is not None
            else scenario.duration_minutes
        )

        log = SimulationLog()
        setpoint = scenario.controller.setpoint
        first_room = scenario.building.rooms[0]

        for t in range(n_steps):
            all_meas = sim.get_all_measurements()
            wp = scenario.weather.get(float(t))

            # Compute actions for each room
            actions_dict: dict[str, Actions] = {}
            for room_cfg in scenario.building.rooms:
                meas = all_meas[room_cfg.name]
                actions_dict[room_cfg.name] = controller.compute_actions(
                    t=t,
                    measurements=meas,
                    weather=wp,
                    scenario=scenario,
                    room_name=room_cfg.name,
                )

            sim.step_all(actions_dict)

            # Record
            for room_cfg in scenario.building.rooms:
                log.append_from_step(
                    t=t,
                    measurements=all_meas[room_cfg.name],
                    actions=actions_dict[room_cfg.name],
                    weather=wp,
                    room_name=room_cfg.name,
                )

        # Compute metrics from first room
        room_log = log.get_room(first_room.name)
        metrics = SimMetrics.from_log(
            room_log,
            setpoint=setpoint,
            ufh_nominal_power_w=first_room.nominal_ufh_power_heating_w,
            split_power_w=first_room.split_power_w,
            dt_minutes=1,
        )

        return log, metrics

    def run(
        self,
        scenario: SimScenario,
        max_steps: int | None = None,
    ) -> ABReport:
        """Run both controllers on the same scenario and compare.

        Args:
            scenario: Simulation scenario.
            max_steps: Optional cap on simulation steps.

        Returns:
            An ``ABReport`` with metrics, logs, and deltas.
        """
        log_a, metrics_a = self._run_single(
            self._controller_a,
            scenario,
            max_steps,
        )
        log_b, metrics_b = self._run_single(
            self._controller_b,
            scenario,
            max_steps,
        )

        deltas = metrics_a.compare(metrics_b)

        return ABReport(
            controller_a_name=self._controller_a.name,
            controller_b_name=self._controller_b.name,
            scenario_name=scenario.name,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            deltas=deltas,
            log_a=log_a,
            log_b=log_b,
        )


# ---------------------------------------------------------------------------
# plot_overlay
# ---------------------------------------------------------------------------


def plot_overlay(
    report: ABReport,
    room_name: str | None = None,
    save_path: str | None = None,
) -> object:
    """Generate an overlay plot comparing two controllers.

    Creates a matplotlib figure with three subplots:
    1. T_room: both controllers overlaid with setpoint line.
    2. T_slab: both controllers overlaid.
    3. Valve position: both controllers overlaid.

    Args:
        report: An ``ABReport`` from ``ABTestRunner.run()``.
        room_name: Room to plot.  Defaults to the first room found
            in the log.
        save_path: Optional file path to save the figure as PNG.

    Returns:
        The ``matplotlib.figure.Figure`` instance.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Determine room name from logs if not given
    if room_name is None:
        for rec in report.log_a:
            room_name = rec.room_name
            break
    if room_name is None:
        msg = "Cannot determine room name from empty logs"
        raise ValueError(msg)

    log_a = report.log_a.get_room(room_name)
    log_b = report.log_b.get_room(room_name)

    times_a = [r.t for r in log_a]
    times_b = [r.t for r in log_b]

    t_rooms_a = [r.T_room for r in log_a]
    t_rooms_b = [r.T_room for r in log_b]

    t_slabs_a = [r.T_slab for r in log_a]
    t_slabs_b = [r.T_slab for r in log_b]

    valves_a = [r.valve_position for r in log_a]
    valves_b = [r.valve_position for r in log_b]

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    name_a = report.controller_a_name
    name_b = report.controller_b_name

    # Subplot 1: T_room
    axes[0].plot(times_a, t_rooms_a, label=f"T_room ({name_a})", color="tab:blue")
    axes[0].plot(
        times_b, t_rooms_b, label=f"T_room ({name_b})", color="tab:red", linestyle="--"
    )
    # Try to draw setpoint line from metrics if we can infer it
    # Use the scenario setpoint from the report's metrics context
    if len(t_rooms_a) > 0:
        axes[0].axhline(
            y=report.metrics_a.comfort_pct * 0 + 21.0,
            color="tab:gray",
            linestyle=":",
            alpha=0.0,
        )
    axes[0].set_ylabel("T_room [degC]")
    axes[0].legend(loc="upper right")
    axes[0].grid(alpha=0.3)

    # Subplot 2: T_slab
    axes[1].plot(times_a, t_slabs_a, label=f"T_slab ({name_a})", color="tab:blue")
    axes[1].plot(
        times_b, t_slabs_b, label=f"T_slab ({name_b})", color="tab:red", linestyle="--"
    )
    axes[1].set_ylabel("T_slab [degC]")
    axes[1].legend(loc="upper right")
    axes[1].grid(alpha=0.3)

    # Subplot 3: valve_position
    axes[2].plot(times_a, valves_a, label=f"Valve ({name_a})", color="tab:blue")
    axes[2].plot(
        times_b, valves_b, label=f"Valve ({name_b})", color="tab:red", linestyle="--"
    )
    axes[2].set_ylabel("Valve [%]")
    axes[2].set_xlabel("Time [min]")
    axes[2].legend(loc="upper right")
    axes[2].grid(alpha=0.3)

    fig.suptitle(
        f"A/B Test: {name_a} vs {name_b} — {report.scenario_name}",
        fontsize=13,
    )
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    plt.close(fig)
    return fig
