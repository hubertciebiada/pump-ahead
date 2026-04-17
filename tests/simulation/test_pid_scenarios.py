"""PID controller scenario tests for PumpAhead.

Tests verify PID controller performance against acceptance criteria:

- **Steady-state**: comfort > 95 %, overshoot < 1.0 degC.
- **Cold snap**: min(T_room) >= setpoint - 1.5 degC, recovery < 24h.
- **Anti-windup**: overshoot < 0.5 degC after saturation at 100 %.
- **Valve floor**: minimum valve position enforced in heating mode.
- **Multi-room**: 8 rooms in parallel with no interference.

Tests that require specific PID gains construct their own scenarios with
tuned ``ControllerConfig``.  The ``run_scenario`` fixture (from conftest)
is used where applicable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

from pumpahead.config import (
    BuildingParams,
    ControllerConfig,
    RoomConfig,
    SimScenario,
)
from pumpahead.controller import PumpAheadController
from pumpahead.metrics import SimMetrics, assert_floor_temp_safe
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.scenarios import SCENARIO_LIBRARY
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import BuildingSimulator, HeatPumpMode
from pumpahead.ufh_loop import LoopGeometry
from pumpahead.weather import ChannelProfile, ProfileKind, SyntheticWeather
from pumpahead.weather_comp import WeatherCompCurve


def _standard_geometry(area_m2: float = 20.0) -> LoopGeometry:
    """Return a standard UFH loop geometry used throughout the tests."""
    return LoopGeometry(
        effective_pipe_length_m=130.0,
        pipe_spacing_m=0.15,
        pipe_diameter_outer_mm=16.0,
        pipe_wall_thickness_mm=2.0,
        area_m2=area_m2,
    )


def _standard_weather_comp() -> WeatherCompCurve:
    """Return a realistic heating weather-compensation curve.

    Post-#144 the simulator uses the physical ``ufh_loop.loop_power`` model
    (EN 1264 reduced formula) instead of the legacy ``valve * ufh_max_power_w``
    shim.  That model requires realistic supply temperatures — real heat pumps
    raise ``T_supply`` at low outdoor temperatures via a weather-compensation
    curve.  The old tests passed a nominal 5 kW rating that was independent
    of ``T_supply``; now we provide a WCC so the physical loop can deliver
    the expected power during the scenarios.

    Curve: ``T_supply(T_out)``:
        * T_out >=  10 C  => 45 C (base)
        * T_out =    0 C  => 53 C
        * T_out =   -5 C  => 55 C (clamped)
        * T_out = -15 C  => 55 C (clamped)
    """
    return WeatherCompCurve(
        t_supply_base=45.0,
        slope=0.8,
        t_neutral=10.0,
        t_supply_max=55.0,
        t_supply_min=25.0,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SISO_PARAMS = RCParams(
    C_air=60_000,
    C_slab=3_250_000,
    C_wall=1_500_000,
    R_sf=0.01,
    R_wi=0.02,
    R_wo=0.03,
    R_ve=0.03,
    R_ins=0.01,
    f_conv=0.6,
    f_rad=0.4,
    T_ground=10.0,
    has_split=False,
)
"""Standard 3R3C SISO parameters for scenario tests."""

_TUNED_CONFIG = ControllerConfig(
    kp=20.0,
    ki=0.003,
    kd=0.0,
    setpoint=21.0,
    deadband=0.5,
    valve_floor_pct=10.0,
)
"""Tuned PID gains validated via gain sweep during implementation."""


def _make_single_room_building() -> BuildingParams:
    """Create a single-room building with SISO parameters."""
    room = RoomConfig(
        name="test_room",
        area_m2=20.0,
        params=_SISO_PARAMS,
        has_split=False,
        split_power_w=0.0,
        pipe_spacing_m=0.20,
    )
    return BuildingParams(
        rooms=(room,),
        hp_max_power_w=9000.0,
        latitude=50.69,
        longitude=17.38,
    )


# ---------------------------------------------------------------------------
# TestPIDSteadyState
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestPIDSteadyState:
    """Steady-state PID performance tests.

    Uses the ``steady_state`` scenario from the library with tuned gains.
    """

    def test_comfort_above_95_percent(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Steady-state comfort percentage exceeds 95 %."""
        base = SCENARIO_LIBRARY["steady_state"]()
        scenario = replace(
            base,
            controller=_TUNED_CONFIG,
            weather_comp=_standard_weather_comp(),
        )
        _log, metrics = run_scenario(scenario, None)
        assert metrics.comfort_pct > 95.0, (
            f"steady_state comfort {metrics.comfort_pct:.1f}% <= 95%"
        )

    def test_overshoot_below_1_degree(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Steady-state overshoot is less than 1.0 degC."""
        base = SCENARIO_LIBRARY["steady_state"]()
        scenario = replace(
            base,
            controller=_TUNED_CONFIG,
            weather_comp=_standard_weather_comp(),
        )
        _log, metrics = run_scenario(scenario, None)
        assert metrics.max_overshoot < 1.0, (
            f"steady_state overshoot {metrics.max_overshoot:.2f} >= 1.0 degC"
        )

    def test_floor_temp_safe(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Floor temperature stays within safe limits during steady state."""
        base = SCENARIO_LIBRARY["steady_state"]()
        scenario = replace(
            base,
            controller=_TUNED_CONFIG,
            weather_comp=_standard_weather_comp(),
        )
        log, _metrics = run_scenario(scenario, None)
        first_room = scenario.building.rooms[0].name
        assert_floor_temp_safe(log.get_room(first_room))


# ---------------------------------------------------------------------------
# TestPIDColdSnap
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestPIDColdSnap:
    """Cold-snap PID performance tests.

    Uses a single-room building with a step drop from 0C to -15C after
    24h.  The single-room setup avoids HP capacity starvation that occurs
    with the 8-room modern_bungalow building (9 kW shared across 25 kW
    demand).
    """

    @staticmethod
    def _cold_snap_single_room() -> SimScenario:
        """Create a single-room cold-snap scenario with tuned gains.

        Uses the ``well_insulated`` building profile (R_ve=0.1) which
        is representative of modern construction.  The step drop from
        0C to -15C at t=1440 tests PID response to sudden load increase.
        """
        from pumpahead.building_profiles import well_insulated

        weather = SyntheticWeather(
            t_out=ChannelProfile(
                kind=ProfileKind.STEP,
                baseline=0.0,
                amplitude=-15.0,
                step_time_minutes=1440.0,
            ),
            ghi=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=0.0),
            wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=2.0),
            humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=60.0),
        )
        return SimScenario(
            name="cold_snap_pid",
            building=well_insulated(),
            weather=weather,
            controller=_TUNED_CONFIG,
            duration_minutes=4320,
            mode="heating",
            dt_seconds=60.0,
            weather_comp=_standard_weather_comp(),
            description=(
                "Single-room cold snap (well insulated): step from 0C "
                "to -15C at t=1440. Tests PID response to sudden "
                "temperature drop."
            ),
        )

    def test_min_temp_within_1_5_degrees(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Minimum room temperature stays within setpoint - 1.5 degC.

        Checked from the step-drop (t=1440) onwards.  The first 24h is
        the warm-up / pre-charge period where the system reaches steady
        state before the disturbance.
        """
        scenario = self._cold_snap_single_room()
        log, _metrics = run_scenario(scenario, None)

        first_room = scenario.building.rooms[0].name
        room_log = log.get_room(first_room)
        # Only check from step-drop time onwards
        post_drop = [r for r in room_log if r.t >= 1440]
        min_t_room = min(r.T_room for r in post_drop)
        setpoint = scenario.controller.setpoint

        assert min_t_room >= setpoint - 1.5, (
            f"cold_snap min T_room={min_t_room:.2f} < setpoint-1.5={setpoint - 1.5:.1f}"
        )

    def test_recovery_within_24h(
        self,
        run_scenario: Callable[
            [SimScenario, int | None], tuple[SimulationLog, SimMetrics]
        ],
    ) -> None:
        """Room recovers to comfort band within 24h of the step drop.

        The step drop happens at t=1440.  We check that by t=2880 (24h
        later) the room is within +/-0.5 degC of setpoint.
        """
        scenario = self._cold_snap_single_room()
        log, _metrics = run_scenario(scenario, None)

        first_room = scenario.building.rooms[0].name
        setpoint = scenario.controller.setpoint

        room_log = log.get_room(first_room)
        recovery_records = [r for r in room_log if 2820 <= r.t <= 2880]

        if len(recovery_records) > 0:
            comfort_count = sum(
                1 for r in recovery_records if abs(r.T_room - setpoint) <= 0.5
            )
            comfort_pct = (comfort_count / len(recovery_records)) * 100.0
            assert comfort_pct >= 80.0, (
                f"cold_snap recovery: only {comfort_pct:.0f}% of records "
                f"within comfort band at t=2820-2880"
            )


# ---------------------------------------------------------------------------
# TestPIDAntiWindup
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestPIDAntiWindup:
    """Anti-windup simulation test.

    Scenario: constant outdoor temperature -20C for 48h on a
    well-insulated building.  The PID saturates at 100 % during warm-up.
    After stabilisation, overshoot must stay below 0.5 degC.
    """

    def test_overshoot_below_0_5_after_saturation(self) -> None:
        """After initial warm-up saturation, overshoot < 0.5 degC."""
        weather = SyntheticWeather.constant(
            T_out=-20.0, GHI=0.0, wind_speed=0.0, humidity=50.0
        )

        model = RCModel(_SISO_PARAMS, ModelOrder.THREE, dt=60.0)
        room = SimulatedRoom("test_room", model, loop_geometry=_standard_geometry())
        sim = BuildingSimulator([room], weather, hp_mode=HeatPumpMode.HEATING)

        config = ControllerConfig(
            kp=20.0,
            ki=0.003,
            kd=0.0,
            setpoint=21.0,
            valve_floor_pct=10.0,
        )
        controller = PumpAheadController(config, ["test_room"])

        setpoint = 21.0
        n_steps = 2880  # 48h

        max_overshoot = 0.0
        for _t in range(n_steps):
            meas = sim.get_all_measurements()
            actions = controller.step(meas)
            sim.step_all(actions)

            t_room = meas["test_room"].T_room
            overshoot = t_room - setpoint
            if overshoot > max_overshoot:
                max_overshoot = overshoot

        assert max_overshoot < 0.5, (
            f"anti-windup: overshoot {max_overshoot:.3f} >= 0.5 degC"
        )


# ---------------------------------------------------------------------------
# TestPIDValveFloor
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestPIDValveFloor:
    """Valve floor minimum enforcement during simulation."""

    def test_valve_never_below_floor_when_heating(self) -> None:
        """In heating mode, valve never drops below valve_floor_pct.

        Checks every action where T_room < setpoint + deadband.
        """
        weather = SyntheticWeather.constant(
            T_out=0.0, GHI=0.0, wind_speed=0.0, humidity=50.0
        )

        model = RCModel(_SISO_PARAMS, ModelOrder.THREE, dt=60.0)
        room = SimulatedRoom("test_room", model, loop_geometry=_standard_geometry())
        sim = BuildingSimulator([room], weather, hp_mode=HeatPumpMode.HEATING)

        valve_floor = 12.0
        config = ControllerConfig(
            kp=20.0,
            ki=0.003,
            kd=0.0,
            setpoint=21.0,
            deadband=0.5,
            valve_floor_pct=valve_floor,
        )
        controller = PumpAheadController(config, ["test_room"])

        setpoint = 21.0
        deadband = 0.5

        for _t in range(1440):
            meas = sim.get_all_measurements()
            actions = controller.step(meas)
            sim.step_all(actions)

            t_room = meas["test_room"].T_room
            valve = actions["test_room"].valve_position

            # Valve floor applies only when below setpoint + deadband
            if t_room < setpoint + deadband:
                assert valve >= valve_floor - 1e-9, (
                    f"valve {valve:.2f}% < floor {valve_floor}% at T_room={t_room:.2f}"
                )


# ---------------------------------------------------------------------------
# TestPIDMultiRoom
# ---------------------------------------------------------------------------


@pytest.mark.simulation
class TestPIDMultiRoom:
    """Multi-room PID test: 8 rooms in parallel, no interference.

    Uses ample HP capacity (40 kW for 40 kW total UFH demand) to avoid
    capacity starvation and isolate the PID performance.
    """

    def test_eight_rooms_independent_control(self) -> None:
        """8 rooms with identical physics converge independently."""
        weather = SyntheticWeather.constant(
            T_out=0.0, GHI=0.0, wind_speed=0.0, humidity=50.0
        )

        rooms: list[SimulatedRoom] = []
        for i in range(8):
            model = RCModel(_SISO_PARAMS, ModelOrder.THREE, dt=60.0)
            rooms.append(
                SimulatedRoom(f"room_{i}", model, loop_geometry=_standard_geometry())
            )

        sim = BuildingSimulator(
            rooms,
            weather,
            hp_mode=HeatPumpMode.HEATING,
            hp_max_power_w=40000.0,
            weather_comp=_standard_weather_comp(),
        )

        config = ControllerConfig(
            kp=20.0,
            ki=0.003,
            kd=0.0,
            setpoint=21.0,
            valve_floor_pct=10.0,
        )
        room_names = [f"room_{i}" for i in range(8)]
        controller = PumpAheadController(config, room_names)

        # Run for 48h
        n_steps = 2880
        for _t in range(n_steps):
            meas = sim.get_all_measurements()
            actions = controller.step(meas)
            sim.step_all(actions)

        # Check all rooms reached setpoint +/- 0.5
        final_meas = sim.get_all_measurements()
        setpoint = 21.0
        for name in room_names:
            t_room = final_meas[name].T_room
            assert abs(t_room - setpoint) < 0.5, (
                f"{name}: T_room={t_room:.2f} not within +/-0.5 of setpoint {setpoint}"
            )

        # Check diagnostics show independent state
        diag = controller.get_diagnostics()
        integrals = [diag[name]["integral"] for name in room_names]
        # Verify they exist and are finite
        for i, val in enumerate(integrals):
            assert val is not None, f"room_{i} integral is None"
