"""Unit tests for cooling mode, auto-switching, and asymmetric power.

Tests cover:
- RC model propagation with negative Q_floor (TestRCModelCooling)
- ModeController hysteresis and auto-switching (TestModeController)
- Asymmetric cooling power in RoomConfig (TestCoolingPowerAsymmetry)
- PID error inversion and valve floor in cooling mode (TestControllerCoolingMode)
- BuildingSimulator power distribution in cooling mode (TestSimulatorCoolingMode)
- 7-day hot_july scenario smoke test (TestHotJulyScenario)
"""

from __future__ import annotations

import numpy as np
import pytest

from pumpahead.building_profiles import hubert_real
from pumpahead.config import ControllerConfig, RoomConfig
from pumpahead.controller import PumpAheadController
from pumpahead.mode_controller import ModeController
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.scenarios import (
    dual_source_cooling_steady,
    hot_july,
    spring_transition,
)
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulator import (
    Actions,
    BuildingSimulator,
    HeatPumpMode,
    Measurements,
    SplitMode,
)
from pumpahead.weather import SyntheticWeather

# ---------------------------------------------------------------------------
# TestRCModelCooling — RC model correctly propagates negative Q_floor
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRCModelCooling:
    """Verify that the RC model handles negative floor power correctly."""

    def test_negative_q_floor_decreases_t_slab(
        self, params_3r3c: RCParams, model_3r3c: RCModel
    ) -> None:
        """Applying Q_floor < 0 for N steps causes T_slab to decrease monotonically."""
        x = np.array([25.0, 25.0, 25.0])
        d = np.array([30.0, 0.0, 0.0])  # Hot outdoor, no solar
        u = np.array([-3000.0])  # Negative floor power (cooling)

        t_slab_prev = x[1]
        for _ in range(60):
            x = model_3r3c.step(x, u, d)
            assert x[1] < t_slab_prev, "T_slab must decrease with Q_floor < 0"
            t_slab_prev = x[1]

    def test_negative_q_floor_decreases_t_air(
        self, params_3r3c: RCParams, model_3r3c: RCModel
    ) -> None:
        """Negative Q_floor eventually pulls T_air down through slab-air coupling."""
        x = np.array([25.0, 25.0, 25.0])
        d = np.array([25.0, 0.0, 0.0])  # Outdoor = indoor (neutral)
        u = np.array([-3000.0])

        for _ in range(120):
            x = model_3r3c.step(x, u, d)

        assert x[0] < 25.0, "T_air should decrease after sustained negative Q_floor"

    def test_positive_q_floor_increases_t_slab(
        self, params_3r3c: RCParams, model_3r3c: RCModel
    ) -> None:
        """Sanity check: positive Q_floor increases T_slab (heating baseline)."""
        x = np.array([20.0, 20.0, 20.0])
        d = np.array([0.0, 0.0, 0.0])
        u = np.array([3000.0])

        t_slab_prev = x[1]
        for _ in range(60):
            x = model_3r3c.step(x, u, d)
            assert x[1] > t_slab_prev, "T_slab must increase with Q_floor > 0"
            t_slab_prev = x[1]

    def test_mimo_negative_q_conv_cools(
        self, params_3r3c_mimo: RCParams, model_3r3c_mimo: RCModel
    ) -> None:
        """Negative Q_conv (split cooling) reduces T_air in MIMO model."""
        x = np.array([25.0, 25.0, 25.0])
        d = np.array([25.0, 0.0, 0.0])
        u = np.array([-2500.0, 0.0])  # Split cooling, no floor power

        for _ in range(60):
            x = model_3r3c_mimo.step(x, u, d)

        assert x[0] < 25.0, "T_air should decrease with negative Q_conv"


# ---------------------------------------------------------------------------
# TestModeController — auto-switching with hysteresis
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestModeController:
    """Tests for ModeController hysteresis logic."""

    def test_initial_mode_is_heating(self) -> None:
        """Default initial mode is HEATING."""
        mc = ModeController()
        assert mc.current_mode == HeatPumpMode.HEATING

    def test_switch_to_cooling_above_threshold(self) -> None:
        """Mode switches to COOLING when T_outdoor > cooling_threshold
        after min_hold_minutes."""
        mc = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=10,
        )
        # Spend 10 steps at T=25 (above cooling threshold)
        for _ in range(10):
            mode = mc.update(25.0)

        # After 10 minutes (= min_hold), should switch to cooling
        assert mode == HeatPumpMode.COOLING

    def test_switch_to_heating_below_threshold(self) -> None:
        """Mode switches to HEATING when T_outdoor < heating_threshold
        after min_hold_minutes."""
        mc = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=10,
            initial_mode=HeatPumpMode.COOLING,
        )
        for _ in range(10):
            mode = mc.update(15.0)

        assert mode == HeatPumpMode.HEATING

    def test_no_switch_in_deadzone(self) -> None:
        """Mode does not switch when T_outdoor is between thresholds."""
        mc = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=0,
        )
        for _ in range(100):
            mode = mc.update(20.0)

        assert mode == HeatPumpMode.HEATING  # Stays at initial

    def test_hysteresis_prevents_oscillation(self) -> None:
        """Oscillating T_outdoor around thresholds does not cause
        rapid mode switching due to min_hold_minutes."""
        mc = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=30,
        )
        switches = 0
        prev_mode = mc.current_mode

        # 120 steps of oscillating temperature around the boundary
        for i in range(120):
            # Oscillate between 17 and 23 every 5 minutes
            t_out = 17.0 if (i // 5) % 2 == 0 else 23.0
            mode = mc.update(t_out)
            if mode != prev_mode:
                switches += 1
                prev_mode = mode

        # With 30-minute hold, at most a few switches in 120 minutes
        assert switches <= 4, f"Too many mode switches: {switches}"

    def test_min_hold_zero_allows_immediate_switch(self) -> None:
        """With min_hold_minutes=0, mode can switch every step."""
        mc = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=0,
        )
        # First call: above cooling threshold -> switch
        mode = mc.update(25.0)
        assert mode == HeatPumpMode.COOLING

    def test_minutes_in_current_mode_resets_on_switch(self) -> None:
        """minutes_in_current_mode resets to 0 when mode switches."""
        mc = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=5,
        )
        # Accumulate 5 minutes
        for _ in range(5):
            mc.update(25.0)

        # Should have just switched
        assert mc.current_mode == HeatPumpMode.COOLING
        assert mc.minutes_in_current_mode == 0

    def test_reset_clears_state(self) -> None:
        """reset() sets minutes_in_current_mode back to 0."""
        mc = ModeController(min_hold_minutes=10)
        for _ in range(5):
            mc.update(20.0)
        assert mc.minutes_in_current_mode == 5
        mc.reset()
        assert mc.minutes_in_current_mode == 0

    def test_invalid_thresholds_raises(self) -> None:
        """heating_threshold >= cooling_threshold raises ValueError."""
        with pytest.raises(ValueError, match="heating_threshold"):
            ModeController(heating_threshold=22.0, cooling_threshold=18.0)

    def test_off_mode_initial_raises(self) -> None:
        """initial_mode=OFF raises ValueError."""
        with pytest.raises(ValueError, match="initial_mode"):
            ModeController(initial_mode=HeatPumpMode.OFF)

    def test_negative_min_hold_raises(self) -> None:
        """Negative min_hold_minutes raises ValueError."""
        with pytest.raises(ValueError, match="min_hold_minutes"):
            ModeController(min_hold_minutes=-1)


# ---------------------------------------------------------------------------
# TestCoolingPowerAsymmetry — RoomConfig validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoolingPowerAsymmetry:
    """Tests for ufh_cooling_max_power_w in RoomConfig."""

    def test_default_cooling_power_is_zero(self) -> None:
        """Default ufh_cooling_max_power_w is 0.0."""
        params = RCParams(
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
        room = RoomConfig(
            name="test",
            area_m2=20.0,
            params=params,
            ufh_max_power_w=5000.0,
        )
        assert room.ufh_cooling_max_power_w == 0.0

    def test_explicit_cooling_power(self) -> None:
        """Explicit ufh_cooling_max_power_w is stored correctly."""
        params = RCParams(
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
        room = RoomConfig(
            name="test",
            area_m2=20.0,
            params=params,
            ufh_max_power_w=5000.0,
            ufh_cooling_max_power_w=3000.0,
        )
        assert room.ufh_cooling_max_power_w == 3000.0

    def test_negative_cooling_power_raises(self) -> None:
        """Negative ufh_cooling_max_power_w raises ValueError."""
        params = RCParams(
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
        with pytest.raises(ValueError, match="ufh_cooling_max_power_w"):
            RoomConfig(
                name="test",
                area_m2=20.0,
                params=params,
                ufh_max_power_w=5000.0,
                ufh_cooling_max_power_w=-100.0,
            )

    def test_hubert_rooms_have_cooling_power(self) -> None:
        """All hubert_real rooms have ufh_cooling_max_power_w > 0."""
        building = hubert_real()
        for room in building.rooms:
            assert room.ufh_cooling_max_power_w > 0, (
                f"{room.name}: ufh_cooling_max_power_w should be > 0"
            )

    def test_cooling_power_less_than_heating(self) -> None:
        """All hubert_real rooms have cooling power < heating power."""
        building = hubert_real()
        for room in building.rooms:
            assert room.ufh_cooling_max_power_w < room.ufh_max_power_w, (
                f"{room.name}: cooling ({room.ufh_cooling_max_power_w}) "
                f"must be < heating ({room.ufh_max_power_w})"
            )

    def test_cooling_power_roughly_60_percent_of_heating(self) -> None:
        """Cooling power is approximately 60% of heating power."""
        building = hubert_real()
        for room in building.rooms:
            ratio = room.ufh_cooling_max_power_w / room.ufh_max_power_w
            assert 0.5 <= ratio <= 0.7, (
                f"{room.name}: cooling/heating ratio {ratio:.2f} outside [0.5, 0.7]"
            )


# ---------------------------------------------------------------------------
# TestControllerCoolingMode — PID error inversion + valve floor
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestControllerCoolingMode:
    """Tests for cooling-mode PID error inversion and valve floor."""

    def test_cooling_mode_positive_error_when_room_above_setpoint(self) -> None:
        """In cooling mode, room above setpoint produces positive PID output."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=25.0)
        ctrl = PumpAheadController(
            config,
            ["room"],
            mode="cooling",
        )
        meas = {
            "room": Measurements(
                T_room=27.0,
                T_slab=26.0,
                T_outdoor=32.0,
                valve_pos=0.0,
                hp_mode=HeatPumpMode.COOLING,
            )
        }
        actions = ctrl.step(meas)
        # Room is 2C above setpoint -> error = 27-25 = 2.0 -> valve = 10%
        assert actions["room"].valve_position > 0.0

    def test_cooling_mode_zero_valve_when_below_setpoint(self) -> None:
        """In cooling mode, room below setpoint produces zero valve output."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=25.0)
        ctrl = PumpAheadController(
            config,
            ["room"],
            mode="cooling",
        )
        meas = {
            "room": Measurements(
                T_room=23.0,
                T_slab=24.0,
                T_outdoor=32.0,
                valve_pos=0.0,
                hp_mode=HeatPumpMode.COOLING,
            )
        }
        actions = ctrl.step(meas)
        # Room is below setpoint -> error = 23-25 = -2 -> valve = 0
        assert actions["room"].valve_position == pytest.approx(0.0)

    def test_valve_floor_not_enforced_in_cooling_mode(self) -> None:
        """Valve floor minimum is NOT applied in cooling mode."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=25.0,
            valve_floor_pct=15.0,
        )
        ctrl = PumpAheadController(
            config,
            ["room"],
            mode="cooling",
        )
        # Room exactly at setpoint — PID error = 0 -> valve = 0
        meas = {
            "room": Measurements(
                T_room=25.0,
                T_slab=25.0,
                T_outdoor=32.0,
                valve_pos=0.0,
                hp_mode=HeatPumpMode.COOLING,
            )
        }
        actions = ctrl.step(meas)
        assert actions["room"].valve_position == pytest.approx(0.0)

    def test_valve_floor_enforced_in_heating_mode(self) -> None:
        """Valve floor IS applied in heating mode (regression check)."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=21.0,
            valve_floor_pct=15.0,
        )
        ctrl = PumpAheadController(
            config,
            ["room"],
            mode="heating",
        )
        # Room 0.3C below setpoint — small positive error
        meas = {
            "room": Measurements(
                T_room=20.7,
                T_slab=22.0,
                T_outdoor=0.0,
                valve_pos=0.0,
                hp_mode=HeatPumpMode.HEATING,
            )
        }
        actions = ctrl.step(meas)
        # PID output = 5 * 0.3 = 1.5 %, but valve floor = 15%
        assert actions["room"].valve_position >= 15.0

    def test_split_never_heats_in_cooling_mode(self) -> None:
        """In cooling mode, split NEVER activates in HEATING (Axiom #3)."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=25.0,
            split_deadband=0.5,
        )
        ctrl = PumpAheadController(
            config,
            ["room"],
            room_has_split={"room": True},
            mode="cooling",
        )
        # Room below setpoint in cooling mode
        meas = {
            "room": Measurements(
                T_room=23.0,
                T_slab=24.0,
                T_outdoor=32.0,
                valve_pos=0.0,
                hp_mode=HeatPumpMode.COOLING,
            )
        }
        actions = ctrl.step(meas)
        assert actions["room"].split_mode != SplitMode.HEATING

    def test_split_never_cools_in_heating_mode(self) -> None:
        """In heating mode, split NEVER activates in COOLING (Axiom #3)."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=21.0,
            split_deadband=0.5,
        )
        ctrl = PumpAheadController(
            config,
            ["room"],
            room_has_split={"room": True},
            mode="heating",
        )
        # Room above setpoint in heating mode
        meas = {
            "room": Measurements(
                T_room=23.0,
                T_slab=22.0,
                T_outdoor=5.0,
                valve_pos=50.0,
                hp_mode=HeatPumpMode.HEATING,
            )
        }
        actions = ctrl.step(meas)
        assert actions["room"].split_mode != SplitMode.COOLING


# ---------------------------------------------------------------------------
# TestControllerAutoMode — auto-switching via PumpAheadController
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestControllerAutoMode:
    """Tests for auto-mode integration in PumpAheadController."""

    def test_auto_mode_creates_mode_controller(self) -> None:
        """PumpAheadController with mode='auto' creates a ModeController."""
        config = ControllerConfig(setpoint=22.0)
        ctrl = PumpAheadController(config, ["room"], mode="auto")
        assert ctrl.mode_controller is not None

    def test_heating_mode_no_mode_controller(self) -> None:
        """PumpAheadController with mode='heating' has no ModeController."""
        config = ControllerConfig(setpoint=22.0)
        ctrl = PumpAheadController(config, ["room"], mode="heating")
        assert ctrl.mode_controller is None

    def test_auto_mode_switches_to_cooling(self) -> None:
        """Auto mode switches HP mode from HEATING to COOLING when warm."""
        config = ControllerConfig(
            setpoint=22.0,
            mode_switch_heating_threshold=18.0,
            mode_switch_cooling_threshold=22.0,
            mode_switch_min_hold_minutes=5,
        )
        weather = SyntheticWeather.constant(T_out=25.0, GHI=0.0)
        room_model = RCModel(
            RCParams(
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
            ),
            ModelOrder.THREE,
            dt=60.0,
        )
        sim_room = SimulatedRoom(
            "room",
            room_model,
            ufh_max_power_w=5000.0,
            ufh_cooling_max_power_w=3000.0,
        )
        sim = BuildingSimulator(
            sim_room,
            weather,
            hp_mode=HeatPumpMode.HEATING,
        )
        ctrl = PumpAheadController(config, ["room"], mode="auto")

        # Run for 10 steps with T_out=25 (above cooling threshold)
        for _ in range(10):
            meas = sim.get_all_measurements()
            ctrl.step(meas, simulator=sim)

        # Mode should have switched to COOLING
        assert sim.hp_mode == HeatPumpMode.COOLING

    def test_auto_mode_resets_pid_on_switch(self) -> None:
        """PID integral resets to 0 when mode switches."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.01,
            setpoint=22.0,
            mode_switch_heating_threshold=18.0,
            mode_switch_cooling_threshold=22.0,
            mode_switch_min_hold_minutes=0,
        )
        ctrl = PumpAheadController(config, ["room"], mode="auto")

        # Build up integral in heating mode
        for _ in range(10):
            meas = {
                "room": Measurements(
                    T_room=20.0,
                    T_slab=20.0,
                    T_outdoor=10.0,
                    valve_pos=50.0,
                    hp_mode=HeatPumpMode.HEATING,
                )
            }
            ctrl.step(meas)

        # Get integral before switch
        diag_before = ctrl.get_diagnostics()
        integral_before = diag_before["room"]["integral"]
        assert integral_before > 0, "Integral should have accumulated"

        # Now feed a measurement with T_outdoor > cooling_threshold
        # With min_hold_minutes=0, switch should happen immediately
        # (need at least 1 step to satisfy min_hold_minutes=0)
        meas = {
            "room": Measurements(
                T_room=20.0,
                T_slab=20.0,
                T_outdoor=25.0,
                valve_pos=50.0,
                hp_mode=HeatPumpMode.HEATING,
            )
        }
        ctrl.step(meas)

        # Integral should have been reset
        diag_after = ctrl.get_diagnostics()
        # After reset and one step, integral should be much smaller
        # than what accumulated over 10 steps
        assert abs(diag_after["room"]["integral"]) < abs(integral_before)


# ---------------------------------------------------------------------------
# TestSimulatorCoolingMode — BuildingSimulator power distribution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimulatorCoolingMode:
    """Tests for cooling-mode power distribution in BuildingSimulator."""

    def test_distribute_hp_power_negative_in_cooling(self) -> None:
        """In cooling mode, _distribute_hp_power returns negative values."""
        params = RCParams(
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
        model = RCModel(params, ModelOrder.THREE, dt=60.0)
        room = SimulatedRoom(
            "test",
            model,
            ufh_max_power_w=5000.0,
            ufh_cooling_max_power_w=3000.0,
        )
        weather = SyntheticWeather.constant(T_out=30.0, GHI=0.0)
        sim = BuildingSimulator(
            room,
            weather,
            hp_mode=HeatPumpMode.COOLING,
        )

        actions = {"test": Actions(valve_position=50.0)}
        allocated = sim._distribute_hp_power(actions)

        assert allocated["test"] < 0, "Cooling mode should produce negative power"
        assert allocated["test"] == pytest.approx(-1500.0)  # 50% of 3000

    def test_distribute_hp_power_positive_in_heating(self) -> None:
        """In heating mode, _distribute_hp_power returns positive values."""
        params = RCParams(
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
        model = RCModel(params, ModelOrder.THREE, dt=60.0)
        room = SimulatedRoom(
            "test",
            model,
            ufh_max_power_w=5000.0,
            ufh_cooling_max_power_w=3000.0,
        )
        weather = SyntheticWeather.constant(T_out=0.0, GHI=0.0)
        sim = BuildingSimulator(
            room,
            weather,
            hp_mode=HeatPumpMode.HEATING,
        )

        actions = {"test": Actions(valve_position=50.0)}
        allocated = sim._distribute_hp_power(actions)

        assert allocated["test"] > 0, "Heating mode should produce positive power"
        assert allocated["test"] == pytest.approx(2500.0)  # 50% of 5000

    def test_set_hp_mode(self) -> None:
        """set_hp_mode updates the simulator's mode."""
        params = RCParams(
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
        model = RCModel(params, ModelOrder.THREE, dt=60.0)
        room = SimulatedRoom("test", model)
        weather = SyntheticWeather.constant(T_out=0.0, GHI=0.0)
        sim = BuildingSimulator(room, weather, hp_mode=HeatPumpMode.HEATING)

        assert sim.hp_mode == HeatPumpMode.HEATING
        sim.set_hp_mode(HeatPumpMode.COOLING)
        assert sim.hp_mode == HeatPumpMode.COOLING

    def test_zero_cooling_power_means_no_floor_cooling(self) -> None:
        """Room with ufh_cooling_max_power_w=0 produces Q_floor=0 in cooling mode."""
        params = RCParams(
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
        model = RCModel(params, ModelOrder.THREE, dt=60.0)
        room = SimulatedRoom(
            "test",
            model,
            ufh_max_power_w=5000.0,
            ufh_cooling_max_power_w=0.0,
        )
        weather = SyntheticWeather.constant(T_out=30.0, GHI=0.0)
        sim = BuildingSimulator(
            room,
            weather,
            hp_mode=HeatPumpMode.COOLING,
        )

        actions = {"test": Actions(valve_position=100.0)}
        allocated = sim._distribute_hp_power(actions)

        assert allocated["test"] == pytest.approx(0.0)

    def test_multi_room_cooling_power_distribution(self) -> None:
        """Multi-room cooling respects HP capacity and produces negative power."""
        params = RCParams(
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
        model1 = RCModel(params, ModelOrder.THREE, dt=60.0)
        model2 = RCModel(params, ModelOrder.THREE, dt=60.0)
        room1 = SimulatedRoom(
            "a",
            model1,
            ufh_max_power_w=5000.0,
            ufh_cooling_max_power_w=3000.0,
        )
        room2 = SimulatedRoom(
            "b",
            model2,
            ufh_max_power_w=5000.0,
            ufh_cooling_max_power_w=3000.0,
        )
        weather = SyntheticWeather.constant(T_out=30.0, GHI=0.0)
        sim = BuildingSimulator(
            [room1, room2],
            weather,
            hp_mode=HeatPumpMode.COOLING,
            hp_max_power_w=4000.0,  # Limit < total demand
        )

        actions = {
            "a": Actions(valve_position=100.0),
            "b": Actions(valve_position=100.0),
        }
        allocated = sim._distribute_hp_power(actions)

        # Total demand = 6000, HP limit = 4000, scale = 4000/6000
        assert allocated["a"] < 0
        assert allocated["b"] < 0
        # Total magnitude should not exceed HP capacity
        assert abs(allocated["a"]) + abs(allocated["b"]) <= 4000.0 + 0.01

    def test_step_all_cooling_mode_propagates(self) -> None:
        """step_all in cooling mode propagates negative Q_floor through RC model."""
        params = RCParams(
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
        model = RCModel(params, ModelOrder.THREE, dt=60.0)
        room = SimulatedRoom(
            "test",
            model,
            ufh_max_power_w=5000.0,
            ufh_cooling_max_power_w=3000.0,
        )
        room.set_initial_state(np.array([28.0, 28.0, 28.0]))
        weather = SyntheticWeather.constant(T_out=28.0, GHI=0.0)
        sim = BuildingSimulator(
            [room],
            weather,
            hp_mode=HeatPumpMode.COOLING,
            hp_max_power_w=9000.0,
        )

        t_slab_initial = room.T_slab
        for _ in range(60):
            actions = {"test": Actions(valve_position=80.0)}
            sim.step_all(actions)

        assert room.T_slab < t_slab_initial, "T_slab should decrease in cooling mode"


# ---------------------------------------------------------------------------
# TestHotJulyScenario — 7-day cooling scenario smoke test
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHotJulyScenario:
    """Smoke tests for cooling scenarios."""

    def test_hot_july_scenario_constructs(self) -> None:
        """hot_july scenario constructs without error."""
        scenario = hot_july()
        assert scenario.mode == "cooling"
        assert scenario.duration_minutes == 44640  # 31 days

    def test_dual_source_cooling_steady_constructs(self) -> None:
        """dual_source_cooling_steady scenario constructs without error."""
        scenario = dual_source_cooling_steady()
        assert scenario.mode == "cooling"
        assert scenario.duration_minutes == 10080  # 7 days

    def test_spring_transition_constructs(self) -> None:
        """spring_transition scenario constructs without error."""
        scenario = spring_transition()
        assert scenario.mode == "auto"

    def test_hot_july_7day_no_crash(self) -> None:
        """hot_july scenario runs for 7 days (10080 minutes) without crash."""
        scenario = hot_july()
        building = scenario.building
        rooms: list[SimulatedRoom] = []
        for room_cfg in building.rooms:
            model = RCModel(room_cfg.params, ModelOrder.THREE, dt=60.0)
            sim_room = SimulatedRoom(
                room_cfg.name,
                model,
                ufh_max_power_w=room_cfg.ufh_max_power_w,
                ufh_cooling_max_power_w=room_cfg.ufh_cooling_max_power_w,
            )
            rooms.append(sim_room)

        sim = BuildingSimulator(
            rooms,
            scenario.weather,
            hp_mode=HeatPumpMode.COOLING,
            hp_max_power_w=building.hp_max_power_w,
        )

        ctrl = PumpAheadController(
            scenario.controller,
            [r.name for r in building.rooms],
            mode="cooling",
        )

        n_steps = 10080  # 7 days
        for _ in range(n_steps):
            all_meas = sim.get_all_measurements()
            actions = ctrl.step(all_meas)
            sim.step_all(actions)

        # No crash = success. Verify basic sanity.
        final_meas = sim.get_all_measurements()
        for name, meas in final_meas.items():
            assert 10.0 < meas.T_room < 50.0, (
                f"{name}: T_room={meas.T_room} out of sane range"
            )

    def test_cooling_split_never_heats(self) -> None:
        """In cooling mode, split NEVER enters HEATING mode (Axiom #3)."""
        scenario = dual_source_cooling_steady()
        building = scenario.building
        rooms: list[SimulatedRoom] = []
        for room_cfg in building.rooms:
            model = RCModel(room_cfg.params, ModelOrder.THREE, dt=60.0)
            sim_room = SimulatedRoom(
                room_cfg.name,
                model,
                ufh_max_power_w=room_cfg.ufh_max_power_w,
                ufh_cooling_max_power_w=room_cfg.ufh_cooling_max_power_w,
                split_power_w=room_cfg.split_power_w,
            )
            rooms.append(sim_room)

        sim = BuildingSimulator(
            rooms,
            scenario.weather,
            hp_mode=HeatPumpMode.COOLING,
            hp_max_power_w=building.hp_max_power_w,
        )

        ctrl = PumpAheadController(
            scenario.controller,
            [r.name for r in building.rooms],
            room_has_split={r.name: r.has_split for r in building.rooms},
            mode="cooling",
        )

        n_steps = 1440  # 1 day (shorter for unit test speed)
        for _ in range(n_steps):
            all_meas = sim.get_all_measurements()
            actions = ctrl.step(all_meas)
            # Axiom #3: no split should be HEATING
            for name, a in actions.items():
                assert a.split_mode != SplitMode.HEATING, (
                    f"{name}: split HEATING in COOLING — Axiom #3"
                )
            sim.step_all(actions)


# ---------------------------------------------------------------------------
# TestControllerConfigModeSwitch — ControllerConfig validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestControllerConfigModeSwitch:
    """Tests for mode-switch fields in ControllerConfig."""

    def test_default_thresholds(self) -> None:
        """Default thresholds are 18C and 22C."""
        cfg = ControllerConfig()
        assert cfg.mode_switch_heating_threshold == 18.0
        assert cfg.mode_switch_cooling_threshold == 22.0
        assert cfg.mode_switch_min_hold_minutes == 60

    def test_invalid_thresholds_raises(self) -> None:
        """heating >= cooling threshold raises ValueError."""
        with pytest.raises(ValueError, match="mode_switch_heating_threshold"):
            ControllerConfig(
                mode_switch_heating_threshold=25.0,
                mode_switch_cooling_threshold=20.0,
            )

    def test_negative_min_hold_raises(self) -> None:
        """Negative min_hold_minutes raises ValueError."""
        with pytest.raises(ValueError, match="mode_switch_min_hold_minutes"):
            ControllerConfig(mode_switch_min_hold_minutes=-1)

    def test_custom_thresholds(self) -> None:
        """Custom thresholds are stored correctly."""
        cfg = ControllerConfig(
            mode_switch_heating_threshold=15.0,
            mode_switch_cooling_threshold=25.0,
            mode_switch_min_hold_minutes=120,
        )
        assert cfg.mode_switch_heating_threshold == 15.0
        assert cfg.mode_switch_cooling_threshold == 25.0
        assert cfg.mode_switch_min_hold_minutes == 120


# ---------------------------------------------------------------------------
# TestGraduatedCoolingThrottle — condensation-safe valve throttling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGraduatedCoolingThrottle:
    """Tests for graduated cooling valve throttle in PumpAheadController."""

    def test_controller_throttles_valve_near_dew_point(self) -> None:
        """In cooling mode, valve is throttled when T_slab approaches T_dew.

        With T_room=25, humidity=80 -> T_dew ~ 21.3 (Magnus).
        T_slab=23.0 -> gap = 23.0 - 21.3 = 1.7 < margin(2.0) -> throttle=0.0.
        """
        config = ControllerConfig(kp=10.0, ki=0.0, setpoint=22.0)
        ctrl = PumpAheadController(config, ["room"], mode="cooling")
        meas = {
            "room": Measurements(
                T_room=25.0,
                T_slab=23.0,
                T_outdoor=32.0,
                valve_pos=0.0,
                hp_mode=HeatPumpMode.COOLING,
                humidity=80.0,
            )
        }
        actions = ctrl.step(meas)
        # PID would produce a positive valve (room is 3C above setpoint)
        # but throttle should reduce it to 0.0 since gap < margin
        assert actions["room"].valve_position == pytest.approx(0.0)

    def test_controller_no_throttle_when_floor_safe(self) -> None:
        """Valve is not throttled when T_slab is well above T_dew + margin.

        With T_room=25, humidity=40 -> T_dew ~ 10.5.
        T_slab=25.0 -> gap = 25 - 10.5 = 14.5 >> margin + ramp = 4.
        Throttle = 1.0 (no reduction).
        """
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=22.0)
        ctrl = PumpAheadController(config, ["room"], mode="cooling")
        meas = {
            "room": Measurements(
                T_room=25.0,
                T_slab=25.0,
                T_outdoor=32.0,
                valve_pos=0.0,
                hp_mode=HeatPumpMode.COOLING,
                humidity=40.0,
            )
        }
        actions = ctrl.step(meas)
        # Room is 3C above setpoint -> PID output = 5*3 = 15%
        # No throttle -> valve stays at PID output
        assert actions["room"].valve_position == pytest.approx(15.0)

    def test_controller_zero_valve_at_condensation_limit(self) -> None:
        """Valve forced to 0 when T_slab is at condensation limit.

        With T_room=25, humidity=90 -> T_dew ~ 23.3.
        T_slab=25.0 -> gap = 25 - 23.3 = 1.7 < margin(2.0) -> throttle=0.0.
        """
        config = ControllerConfig(kp=10.0, ki=0.0, setpoint=22.0)
        ctrl = PumpAheadController(config, ["room"], mode="cooling")
        meas = {
            "room": Measurements(
                T_room=25.0,
                T_slab=25.0,
                T_outdoor=32.0,
                valve_pos=0.0,
                hp_mode=HeatPumpMode.COOLING,
                humidity=90.0,
            )
        }
        actions = ctrl.step(meas)
        assert actions["room"].valve_position == pytest.approx(0.0)

    def test_throttle_only_in_cooling_mode(self) -> None:
        """Graduated throttle does NOT apply in heating mode.

        Same high humidity conditions but in heating mode — valve should
        not be throttled.
        """
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=22.0, valve_floor_pct=0.0)
        ctrl = PumpAheadController(config, ["room"], mode="heating")
        meas = {
            "room": Measurements(
                T_room=20.0,
                T_slab=20.0,
                T_outdoor=5.0,
                valve_pos=0.0,
                hp_mode=HeatPumpMode.HEATING,
                humidity=90.0,
            )
        }
        actions = ctrl.step(meas)
        # Room is 2C below setpoint -> error = 2 -> valve = 10%
        # No throttle in heating mode
        assert actions["room"].valve_position == pytest.approx(10.0)
