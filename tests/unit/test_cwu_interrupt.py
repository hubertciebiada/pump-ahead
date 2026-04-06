"""Unit tests for CWU (domestic hot water) interrupt modeling.

Tests cover the ``CWUCycle`` dataclass validation and the
``BuildingSimulator`` integration: Q_floor is forced to 0 during an
active CWU cycle, splits are unaffected, and normal operation resumes
after the cycle ends.
"""

from __future__ import annotations

import dataclasses

import pytest

from pumpahead.config import CWUCycle
from pumpahead.model import ModelOrder, RCModel
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulator import (
    Actions,
    BuildingSimulator,
    SplitMode,
)
from pumpahead.weather import SyntheticWeather

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def siso_room(model_3r3c: RCModel) -> SimulatedRoom:
    """SISO simulated room with 5000 W UFH capacity."""
    return SimulatedRoom("cwu_test", model_3r3c, ufh_max_power_w=5000.0)


@pytest.fixture()
def mimo_room(model_3r3c_mimo: RCModel) -> SimulatedRoom:
    """MIMO simulated room with 5000 W UFH and 2500 W split."""
    return SimulatedRoom(
        "cwu_test_mimo",
        model_3r3c_mimo,
        ufh_max_power_w=5000.0,
        split_power_w=2500.0,
    )


@pytest.fixture()
def constant_weather() -> SyntheticWeather:
    """Constant weather: T_out=-5 degC, no solar."""
    return SyntheticWeather.constant(T_out=-5.0, GHI=0.0)


# ---------------------------------------------------------------------------
# TestCWUCycle
# ---------------------------------------------------------------------------


class TestCWUCycle:
    """Tests for the CWUCycle frozen dataclass."""

    @pytest.mark.unit
    def test_valid_repeating_cycle(self) -> None:
        """A valid repeating CWU cycle is created without error."""
        cycle = CWUCycle(start_minute=60, duration_minutes=30, interval_minutes=480)
        assert cycle.start_minute == 60
        assert cycle.duration_minutes == 30
        assert cycle.interval_minutes == 480

    @pytest.mark.unit
    def test_valid_single_shot_cycle(self) -> None:
        """A single-shot CWU cycle (interval=0) is valid."""
        cycle = CWUCycle(start_minute=120, duration_minutes=45, interval_minutes=0)
        assert cycle.interval_minutes == 0

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """CWUCycle is immutable (frozen=True)."""
        cycle = CWUCycle(start_minute=0, duration_minutes=30, interval_minutes=480)
        with pytest.raises(dataclasses.FrozenInstanceError):
            cycle.start_minute = 10  # type: ignore[misc]

    @pytest.mark.unit
    def test_negative_start_minute_raises(self) -> None:
        """Negative start_minute is rejected."""
        with pytest.raises(ValueError, match="start_minute must be >= 0"):
            CWUCycle(start_minute=-1, duration_minutes=30, interval_minutes=480)

    @pytest.mark.unit
    def test_zero_duration_raises(self) -> None:
        """Zero duration_minutes is rejected."""
        with pytest.raises(ValueError, match="duration_minutes must be > 0"):
            CWUCycle(start_minute=0, duration_minutes=0, interval_minutes=480)

    @pytest.mark.unit
    def test_negative_duration_raises(self) -> None:
        """Negative duration_minutes is rejected."""
        with pytest.raises(ValueError, match="duration_minutes must be > 0"):
            CWUCycle(start_minute=0, duration_minutes=-10, interval_minutes=480)

    @pytest.mark.unit
    def test_negative_interval_raises(self) -> None:
        """Negative interval_minutes is rejected."""
        with pytest.raises(ValueError, match="interval_minutes must be >= 0"):
            CWUCycle(start_minute=0, duration_minutes=30, interval_minutes=-1)

    @pytest.mark.unit
    def test_interval_less_than_duration_raises(self) -> None:
        """interval_minutes <= duration_minutes is rejected when repeating."""
        with pytest.raises(ValueError, match="interval_minutes.*must be >.*duration"):
            CWUCycle(start_minute=0, duration_minutes=30, interval_minutes=30)

    @pytest.mark.unit
    def test_interval_equal_to_duration_raises(self) -> None:
        """interval_minutes == duration_minutes is rejected."""
        with pytest.raises(ValueError, match="interval_minutes.*must be >.*duration"):
            CWUCycle(start_minute=0, duration_minutes=60, interval_minutes=60)

    @pytest.mark.unit
    def test_start_minute_zero_valid(self) -> None:
        """start_minute=0 is a valid configuration."""
        cycle = CWUCycle(start_minute=0, duration_minutes=30, interval_minutes=480)
        assert cycle.start_minute == 0


# ---------------------------------------------------------------------------
# TestCWUInterruptSimulation
# ---------------------------------------------------------------------------


class TestCWUInterruptSimulation:
    """Tests for CWU interrupt behavior in BuildingSimulator."""

    @pytest.mark.unit
    def test_q_floor_zero_during_cwu(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """During a CWU cycle, Q_floor is forced to 0 (valve closed)."""
        # CWU active from minute 0 to minute 30
        cycle = CWUCycle(start_minute=0, duration_minutes=30, interval_minutes=0)
        sim = BuildingSimulator(siso_room, constant_weather, cwu_schedule=[cycle])

        # Reference simulator without CWU (valve=0)
        params = siso_room._model.params
        model_ref = RCModel(params, ModelOrder.THREE, dt=60.0)
        room_ref = SimulatedRoom("ref", model_ref, ufh_max_power_w=5000.0)
        sim_ref = BuildingSimulator(room_ref, constant_weather)

        # Both run with valve=100 command, but CWU sim should behave like valve=0
        for _ in range(30):
            sim.step(Actions(valve_position=100.0))
            sim_ref.step(Actions(valve_position=0.0))

        # CWU simulator should match the zero-valve reference
        assert siso_room.T_slab == pytest.approx(room_ref.T_slab, abs=1e-10)
        assert siso_room.T_air == pytest.approx(room_ref.T_air, abs=1e-10)

    @pytest.mark.unit
    def test_floor_resumes_after_cwu(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """After CWU ends, floor loops resume normal operation."""
        # CWU active from minute 0 to minute 10
        cycle = CWUCycle(start_minute=0, duration_minutes=10, interval_minutes=0)
        sim = BuildingSimulator(siso_room, constant_weather, cwu_schedule=[cycle])

        # Run through the CWU period
        for _ in range(10):
            sim.step(Actions(valve_position=100.0))

        t_slab_after_cwu = siso_room.T_slab

        # Run 100 more steps with valve=100 (CWU is over)
        for _ in range(100):
            sim.step(Actions(valve_position=100.0))

        # Slab should warm up now that floor heating is active
        assert siso_room.T_slab > t_slab_after_cwu

    @pytest.mark.unit
    def test_repeating_cwu_cycles(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Repeating CWU cycles interrupt floor heating periodically."""
        # CWU: 10-min duration, repeats every 60 minutes, starts at minute 0
        cycle = CWUCycle(start_minute=0, duration_minutes=10, interval_minutes=60)
        sim = BuildingSimulator(siso_room, constant_weather, cwu_schedule=[cycle])

        # Minute 0-9: CWU active
        for t in range(10):
            assert sim.is_cwu_active, f"CWU should be active at minute {t}"
            sim.step(Actions(valve_position=100.0))

        # Minute 10-59: CWU inactive
        for t in range(10, 60):
            assert not sim.is_cwu_active, f"CWU should be inactive at minute {t}"
            sim.step(Actions(valve_position=100.0))

        # Minute 60-69: CWU active again (second cycle)
        for t in range(60, 70):
            assert sim.is_cwu_active, f"CWU should be active at minute {t}"
            sim.step(Actions(valve_position=100.0))

        # Minute 70+: CWU inactive again
        assert not sim.is_cwu_active

    @pytest.mark.unit
    def test_split_unaffected_by_cwu(
        self,
        mimo_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """CWU interrupt forces Q_floor=0 but splits continue operating."""
        # CWU active for the entire run
        cycle = CWUCycle(start_minute=0, duration_minutes=100, interval_minutes=0)
        sim = BuildingSimulator(
            mimo_room, constant_weather, cwu_schedule=[cycle]
        )

        # Reference: same room type, no CWU, valve=0, split heating
        params_mimo = mimo_room._model.params
        model_ref = RCModel(params_mimo, ModelOrder.THREE, dt=60.0)
        room_ref = SimulatedRoom(
            "ref_mimo", model_ref, ufh_max_power_w=5000.0, split_power_w=2500.0
        )
        sim_ref = BuildingSimulator(room_ref, constant_weather)

        # CWU sim: valve=100 (overridden to 0), split=HEATING
        # Ref sim: valve=0, split=HEATING
        for _ in range(50):
            sim.step(
                Actions(
                    valve_position=100.0,
                    split_mode=SplitMode.HEATING,
                    split_setpoint=22.0,
                )
            )
            sim_ref.step(
                Actions(
                    valve_position=0.0,
                    split_mode=SplitMode.HEATING,
                    split_setpoint=22.0,
                )
            )

        # Both rooms should have identical state: splits were active in both
        assert mimo_room.T_air == pytest.approx(room_ref.T_air, abs=1e-10)
        assert mimo_room.T_slab == pytest.approx(room_ref.T_slab, abs=1e-10)

    @pytest.mark.unit
    def test_is_cwu_active_property(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """is_cwu_active property reflects the current CWU state."""
        cycle = CWUCycle(start_minute=5, duration_minutes=10, interval_minutes=0)
        sim = BuildingSimulator(siso_room, constant_weather, cwu_schedule=[cycle])

        # Before CWU starts (minute 0-4)
        for _ in range(5):
            assert not sim.is_cwu_active
            sim.step(Actions(valve_position=50.0))

        # During CWU (minute 5-14)
        for _ in range(10):
            assert sim.is_cwu_active
            sim.step(Actions(valve_position=50.0))

        # After CWU (minute 15+)
        assert not sim.is_cwu_active

    @pytest.mark.unit
    def test_no_cwu_schedule_no_effect(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Without a CWU schedule, simulator behaves normally."""
        sim = BuildingSimulator(siso_room, constant_weather)

        assert not sim.is_cwu_active

        # Run with valve=100 for 100 steps
        for _ in range(100):
            sim.step(Actions(valve_position=100.0))

        # Slab should be warmer than initial (heating active)
        assert siso_room.T_slab > 20.0

    @pytest.mark.unit
    def test_cwu_before_start_minute_inactive(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """CWU cycle is inactive before start_minute even with repeating."""
        cycle = CWUCycle(
            start_minute=100, duration_minutes=10, interval_minutes=60
        )
        sim = BuildingSimulator(siso_room, constant_weather, cwu_schedule=[cycle])

        # Minutes 0-99: should be inactive
        for _ in range(100):
            assert not sim.is_cwu_active
            sim.step(Actions(valve_position=50.0))

        # Minute 100: should be active
        assert sim.is_cwu_active

    @pytest.mark.unit
    def test_multiple_cwu_cycles_in_schedule(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Multiple CWU cycles in the schedule are checked independently."""
        cycle_a = CWUCycle(start_minute=0, duration_minutes=5, interval_minutes=0)
        cycle_b = CWUCycle(start_minute=10, duration_minutes=5, interval_minutes=0)
        sim = BuildingSimulator(
            siso_room, constant_weather, cwu_schedule=[cycle_a, cycle_b]
        )

        # Minute 0-4: cycle_a active
        for _ in range(5):
            assert sim.is_cwu_active
            sim.step(Actions(valve_position=50.0))

        # Minute 5-9: neither active
        for _ in range(5):
            assert not sim.is_cwu_active
            sim.step(Actions(valve_position=50.0))

        # Minute 10-14: cycle_b active
        for _ in range(5):
            assert sim.is_cwu_active
            sim.step(Actions(valve_position=50.0))

        # Minute 15+: neither active
        assert not sim.is_cwu_active
