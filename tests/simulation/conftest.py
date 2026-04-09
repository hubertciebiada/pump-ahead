"""Fixtures specific to PumpAhead simulation tests."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from pumpahead.config import SimScenario
from pumpahead.controller import PumpAheadController
from pumpahead.metrics import SimMetrics
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.sensor_noise import SensorNoise
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import (
    BuildingSimulator,
    HeatPumpMode,
)

# ---------------------------------------------------------------------------
# Existing fixtures (kept unchanged)
# ---------------------------------------------------------------------------


@pytest.fixture()
def sim_rng() -> np.random.Generator:
    """Seeded random generator for deterministic simulation tests.

    Uses a different seed than unit tests to catch seed-dependent bugs.
    """
    return np.random.default_rng(12345)


@pytest.fixture()
def sim_model_3r3c(params_3r3c: RCParams) -> RCModel:
    """3R3C model with dt=60s (1-min steps) for simulation tests."""
    return RCModel(params_3r3c, ModelOrder.THREE, dt=60.0)


@pytest.fixture()
def sim_steps_24h() -> int:
    """Number of simulation steps for a 24-hour simulation at dt=60s."""
    return 1440


@pytest.fixture()
def sim_steps_7d() -> int:
    """Number of simulation steps for a 7-day simulation at dt=60s."""
    return 10080


# ---------------------------------------------------------------------------
# New fixtures for Issue #40: pytest integration
# ---------------------------------------------------------------------------

_MODE_MAP: dict[str, HeatPumpMode] = {
    "heating": HeatPumpMode.HEATING,
    "cooling": HeatPumpMode.COOLING,
    "auto": HeatPumpMode.HEATING,
}


def _build_simulator(scenario: SimScenario) -> BuildingSimulator:
    """Construct a ``BuildingSimulator`` from a ``SimScenario``.

    Follows the same construction pattern as the integration test
    helper ``_build_simulator_from_scenario`` in
    ``tests/unit/test_epic04_integration.py``.

    Args:
        scenario: Fully configured simulation scenario.

    Returns:
        A ready-to-run ``BuildingSimulator``.
    """
    rooms: list[SimulatedRoom] = []
    for room_cfg in scenario.building.rooms:
        model = RCModel(room_cfg.params, ModelOrder.THREE, dt=scenario.dt_seconds)
        sim_room = SimulatedRoom(
            room_cfg.name,
            model,
            ufh_max_power_w=room_cfg.ufh_max_power_w,
            split_power_w=room_cfg.split_power_w,
            q_int_w=room_cfg.q_int_w,
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
    )


@pytest.fixture(scope="session")
def plot_output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped directory for scenario plot output.

    Resolution order:
    1. ``PUMPAHEAD_PLOT_DIR`` environment variable (explicit override).
    2. ``tests/simulation/output/`` when running under CI (``CI`` env var).
    3. pytest ``tmp_path_factory`` for local developer runs.

    Returns:
        A ``Path`` to the plot output directory (created if needed).
    """
    env_dir = os.environ.get("PUMPAHEAD_PLOT_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    if os.environ.get("CI"):
        p = Path("tests/simulation/output")
        p.mkdir(parents=True, exist_ok=True)
        return p

    return tmp_path_factory.mktemp("plots")


@pytest.fixture(scope="session")
def run_scenario() -> Callable[
    [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
]:
    """Session-scoped fixture returning a callable that runs a scenario.

    The callable constructs a ``BuildingSimulator`` from a ``SimScenario``,
    runs a proportional controller loop, collects records into a
    ``SimulationLog``, and computes ``SimMetrics`` from the first room.

    Signature::

        run(scenario: SimScenario, max_steps: int | None = None)
            -> tuple[SimulationLog, SimMetrics]

    Args (of the returned callable):
        scenario: Fully configured simulation scenario.
        max_steps: Optional cap on the number of simulation steps.
            Defaults to ``scenario.duration_minutes`` when ``None``.

    Returns (of the returned callable):
        A tuple of ``(SimulationLog, SimMetrics)`` computed from the
        first room in the building.
    """

    def _run(
        scenario: SimScenario,
        max_steps: int | None = None,
    ) -> tuple[SimulationLog, SimMetrics]:
        sim = _build_simulator(scenario)
        n_steps = (
            min(max_steps, scenario.duration_minutes)
            if max_steps is not None
            else scenario.duration_minutes
        )

        log = SimulationLog()
        setpoint = scenario.controller.setpoint

        # Build PumpAheadController from scenario configuration
        room_names = [r.name for r in scenario.building.rooms]
        room_has_split = {r.name: r.has_split for r in scenario.building.rooms}
        controller = PumpAheadController(
            scenario.controller,
            room_names,
            room_has_split=room_has_split,
            cwu_schedule=tuple(scenario.cwu_schedule),
        )

        for t in range(n_steps):
            all_meas = sim.get_all_measurements()
            wp = scenario.weather.get(float(t))

            actions_dict = controller.step(all_meas)

            sim.step_all(actions_dict)

            # Record measurements and actions for all rooms
            for room_cfg in scenario.building.rooms:
                log.append_from_step(
                    t=t,
                    measurements=all_meas[room_cfg.name],
                    actions=actions_dict[room_cfg.name],
                    weather=wp,
                    room_name=room_cfg.name,
                )

        # Compute metrics from the first room
        first_room = scenario.building.rooms[0]
        room_log = log.get_room(first_room.name)
        metrics = SimMetrics.from_log(
            room_log,
            setpoint=setpoint,
            ufh_max_power_w=first_room.ufh_max_power_w,
            split_power_w=first_room.split_power_w,
            dt_minutes=1,
        )

        return log, metrics

    return _run


@pytest.fixture(scope="session")
def save_scenario_plot(
    plot_output_dir: Path,
) -> Callable[[SimulationLog, str, str, float], Path]:
    """Session-scoped fixture returning a callable that saves a scenario plot.

    Generates a PNG with three vertically-stacked subplots:
    1. T_room vs time with a horizontal setpoint line.
    2. T_slab vs time.
    3. valve_position vs time.

    Signature::

        save(log: SimulationLog, scenario_name: str,
             room_name: str, setpoint: float) -> Path

    Args (of the returned callable):
        log: Full simulation log (will be filtered by *room_name*).
        scenario_name: Scenario identifier (used in the filename).
        room_name: Room identifier to filter and label.
        setpoint: Target temperature for the setpoint line [degC].

    Returns (of the returned callable):
        The ``Path`` to the saved PNG file.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def _save(
        log: SimulationLog,
        scenario_name: str,
        room_name: str,
        setpoint: float,
    ) -> Path:
        room_log = log.get_room(room_name)

        times = [r.t for r in room_log]
        t_rooms = [r.T_room for r in room_log]
        t_slabs = [r.T_slab for r in room_log]
        valves = [r.valve_position for r in room_log]

        fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)

        # Subplot 1: T_room
        axes[0].plot(times, t_rooms, label="T_room", color="tab:red")
        axes[0].axhline(setpoint, color="tab:gray", linestyle="--", label="setpoint")
        axes[0].set_ylabel("T_room [degC]")
        axes[0].legend(loc="upper right")

        # Subplot 2: T_slab
        axes[1].plot(times, t_slabs, label="T_slab", color="tab:orange")
        axes[1].set_ylabel("T_slab [degC]")
        axes[1].legend(loc="upper right")

        # Subplot 3: valve_position
        axes[2].plot(times, valves, label="valve_position", color="tab:blue")
        axes[2].set_ylabel("Valve [%]")
        axes[2].set_xlabel("Time [min]")
        axes[2].legend(loc="upper right")

        fig.suptitle(f"{scenario_name} / {room_name}")
        fig.tight_layout()

        out_path = plot_output_dir / f"{scenario_name}_{room_name}.png"
        fig.savefig(str(out_path), dpi=100)
        plt.close(fig)

        return out_path

    return _save
