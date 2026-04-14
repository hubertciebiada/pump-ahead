"""Unit tests for assertion functions in pumpahead.metrics."""

from __future__ import annotations

import pytest

from pumpahead.metrics import (
    assert_comfort,
    assert_energy_vs_baseline,
    assert_floor_temp_safe,
    assert_no_freezing,
    assert_no_opposing_action,
    assert_no_priority_inversion,
    assert_no_prolonged_cold,
)
from pumpahead.simulation_log import SimRecord, SimulationLog
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_record(
    *,
    t: int = 0,
    T_room: float = 21.0,
    T_slab: float = 23.0,
    T_outdoor: float = -5.0,
    valve_pos: float = 50.0,
    hp_mode: HeatPumpMode = HeatPumpMode.HEATING,
    valve_position: float = 50.0,
    split_mode: SplitMode = SplitMode.OFF,
    split_setpoint: float = 0.0,
    T_out: float = -5.0,
    GHI: float = 0.0,
    wind_speed: float = 2.0,
    humidity: float = 50.0,
    room_name: str = "",
) -> SimRecord:
    """Build a SimRecord with sensible defaults for testing."""
    return SimRecord(
        t=t,
        measurements=Measurements(
            T_room=T_room,
            T_slab=T_slab,
            T_outdoor=T_outdoor,
            valve_pos=valve_pos,
            hp_mode=hp_mode,
        ),
        actions=Actions(
            valve_position=valve_position,
            split_mode=split_mode,
            split_setpoint=split_setpoint,
        ),
        weather=WeatherPoint(
            T_out=T_out,
            GHI=GHI,
            wind_speed=wind_speed,
            humidity=humidity,
        ),
        room_name=room_name,
    )


def _make_log(records: list[SimRecord]) -> SimulationLog:
    """Wrap a list of SimRecords in a SimulationLog."""
    return SimulationLog(records)


# ---------------------------------------------------------------------------
# TestAssertComfort
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssertComfort:
    """Tests for assert_comfort."""

    def test_passes_when_above_threshold(self) -> None:
        """100% comfort passes the default 90% threshold."""
        log = _make_log([_make_record(t=i, T_room=21.0) for i in range(10)])
        assert_comfort(log, setpoint=21.0)  # should not raise

    def test_passes_at_exact_threshold(self) -> None:
        """Exactly 90% comfort passes the default 90% threshold."""
        # 9 comfortable, 1 outside -> 90%
        records = [_make_record(t=i, T_room=21.0) for i in range(9)]
        records.append(_make_record(t=9, T_room=25.0))
        log = _make_log(records)
        assert_comfort(log, setpoint=21.0)  # should not raise

    def test_raises_below_threshold(self) -> None:
        """Below 90% comfort raises AssertionError."""
        # 8 comfortable, 2 outside -> 80%
        records = [_make_record(t=i, T_room=21.0) for i in range(8)]
        records.append(_make_record(t=8, T_room=25.0))
        records.append(_make_record(t=9, T_room=25.0))
        log = _make_log(records)
        with pytest.raises(AssertionError, match="comfort 80.0%"):
            assert_comfort(log, setpoint=21.0)

    def test_raises_on_empty_log(self) -> None:
        """Empty log raises AssertionError, not ZeroDivisionError."""
        log = SimulationLog()
        with pytest.raises(AssertionError, match="empty log"):
            assert_comfort(log, setpoint=21.0)

    def test_custom_threshold(self) -> None:
        """Custom threshold=50.0 passes with 60% comfort."""
        # 6 comfortable, 4 outside -> 60%
        records = [_make_record(t=i, T_room=21.0) for i in range(6)]
        records.extend(_make_record(t=6 + i, T_room=25.0) for i in range(4))
        log = _make_log(records)
        assert_comfort(log, setpoint=21.0, threshold=50.0)  # should not raise

    def test_custom_comfort_band(self) -> None:
        """Wider comfort_band=1.0 allows more deviation."""
        # T_room=21.8, setpoint=21.0 -> |dev|=0.8 <= 1.0 -> comfortable
        log = _make_log([_make_record(t=i, T_room=21.8) for i in range(10)])
        assert_comfort(log, setpoint=21.0, comfort_band=1.0)  # should not raise

    def test_narrow_comfort_band_fails(self) -> None:
        """Narrow comfort_band=0.1 rejects deviation of 0.3."""
        log = _make_log([_make_record(t=i, T_room=21.3) for i in range(10)])
        with pytest.raises(AssertionError, match="comfort 0.0%"):
            assert_comfort(log, setpoint=21.0, comfort_band=0.1)

    def test_error_message_contains_diagnostics(self) -> None:
        """Error message includes percentages, setpoint, and counts."""
        records = [_make_record(t=i, T_room=25.0) for i in range(5)]
        log = _make_log(records)
        with pytest.raises(AssertionError, match="comfortable=0/5"):
            assert_comfort(log, setpoint=21.0)

    def test_boundary_inclusive(self) -> None:
        """Record exactly at band edge is comfortable."""
        log = _make_log([_make_record(t=0, T_room=21.5)])
        assert_comfort(
            log, setpoint=21.0, comfort_band=0.5, threshold=100.0
        )  # should not raise


# ---------------------------------------------------------------------------
# TestAssertFloorTempSafe
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssertFloorTempSafe:
    """Tests for assert_floor_temp_safe."""

    def test_passes_safe_temperatures(self) -> None:
        """Temperatures well within limits pass."""
        log = _make_log(
            [
                _make_record(t=0, T_slab=25.0, humidity=50.0),
                _make_record(t=1, T_slab=30.0, humidity=50.0),
            ]
        )
        assert_floor_temp_safe(log)  # should not raise

    def test_raises_on_high_floor_temp(self) -> None:
        """T_floor > 34.0 raises AssertionError."""
        log = _make_log(
            [
                _make_record(t=0, T_slab=25.0),
                _make_record(t=1, T_slab=35.0),
            ]
        )
        with pytest.raises(AssertionError, match="exceeds max 34.00"):
            assert_floor_temp_safe(log)

    def test_exact_max_temp_passes(self) -> None:
        """T_floor exactly 34.0 passes (check is >, not >=)."""
        log = _make_log([_make_record(t=0, T_slab=34.0, humidity=50.0)])
        assert_floor_temp_safe(log)  # should not raise

    def test_raises_on_condensation_risk(self) -> None:
        """T_floor < T_dew + 2 raises AssertionError.

        Magnus: T_dew ~ 17.42 at T_room=21, RH=80.
        Threshold ~ 17.42 + 2.0 = 19.42.
        T_slab=18.0 < 19.42 -> condensation risk.
        """
        log = _make_log(
            [
                _make_record(t=5, T_slab=18.0, humidity=80.0),
            ]
        )
        with pytest.raises(AssertionError, match="condensation risk"):
            assert_floor_temp_safe(log)

    def test_exact_dew_margin_passes(self) -> None:
        """T_floor at T_dew + 2.0 passes (check is <, not <=).

        Magnus: T_dew ~ 17.42 at T_room=21, RH=80, threshold ~ 19.42.
        T_slab=19.5 is NOT < 19.42 -> passes.
        """
        log = _make_log([_make_record(t=0, T_slab=19.5, humidity=80.0)])
        assert_floor_temp_safe(log)  # should not raise

    def test_empty_log_passes_silently(self) -> None:
        """Empty log passes without error."""
        log = SimulationLog()
        assert_floor_temp_safe(log)  # should not raise

    def test_error_message_includes_timestep(self) -> None:
        """Error message includes the violating timestep."""
        log = _make_log([_make_record(t=42, T_slab=36.0)])
        with pytest.raises(AssertionError, match="t=42"):
            assert_floor_temp_safe(log)

    def test_error_message_includes_temperatures(self) -> None:
        """Error message includes the violating temperature values."""
        log = _make_log([_make_record(t=0, T_slab=35.5)])
        with pytest.raises(AssertionError, match="T_floor=35.50"):
            assert_floor_temp_safe(log)

    def test_custom_max_temp(self) -> None:
        """Custom max_temp=30.0 rejects T_floor=31.0."""
        log = _make_log([_make_record(t=0, T_slab=31.0, humidity=50.0)])
        with pytest.raises(AssertionError, match="exceeds max 30.00"):
            assert_floor_temp_safe(log, max_temp=30.0)

    def test_detects_first_violation_only(self) -> None:
        """Raises on the first violation, not later ones."""
        log = _make_log(
            [
                _make_record(t=0, T_slab=25.0, humidity=50.0),  # safe
                _make_record(t=1, T_slab=35.0, humidity=50.0),  # violation
                _make_record(t=2, T_slab=36.0, humidity=50.0),  # also violation
            ]
        )
        with pytest.raises(AssertionError, match="t=1"):
            assert_floor_temp_safe(log)

    def test_checks_every_timestep(self) -> None:
        """Violation at the last timestep is still caught."""
        records = [_make_record(t=i, T_slab=25.0, humidity=50.0) for i in range(9)]
        records.append(_make_record(t=9, T_slab=35.0, humidity=50.0))
        log = _make_log(records)
        with pytest.raises(AssertionError, match="t=9"):
            assert_floor_temp_safe(log)


# ---------------------------------------------------------------------------
# TestAssertNoPriorityInversion
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssertNoPriorityInversion:
    """Tests for assert_no_priority_inversion."""

    def test_passes_low_split_runtime(self) -> None:
        """30% split runtime passes the default 50% threshold."""
        # 3 split ON, 7 OFF -> 30%
        records = [_make_record(t=i, split_mode=SplitMode.HEATING) for i in range(3)]
        records.extend(
            _make_record(t=3 + i, split_mode=SplitMode.OFF) for i in range(7)
        )
        log = _make_log(records)
        assert_no_priority_inversion(log)  # should not raise

    def test_passes_at_exact_threshold(self) -> None:
        """Exactly 50% split runtime passes (check is >, not >=)."""
        # 5 ON, 5 OFF -> 50%
        records = [_make_record(t=i, split_mode=SplitMode.HEATING) for i in range(5)]
        records.extend(
            _make_record(t=5 + i, split_mode=SplitMode.OFF) for i in range(5)
        )
        log = _make_log(records)
        assert_no_priority_inversion(log)  # should not raise

    def test_raises_above_threshold(self) -> None:
        """60% split runtime raises with default 50% threshold."""
        # 6 ON, 4 OFF -> 60%
        records = [_make_record(t=i, split_mode=SplitMode.HEATING) for i in range(6)]
        records.extend(
            _make_record(t=6 + i, split_mode=SplitMode.OFF) for i in range(4)
        )
        log = _make_log(records)
        with pytest.raises(AssertionError, match="split runtime 60.0%"):
            assert_no_priority_inversion(log)

    def test_raises_on_empty_log(self) -> None:
        """Empty log raises AssertionError, not ZeroDivisionError."""
        log = SimulationLog()
        with pytest.raises(AssertionError, match="empty log"):
            assert_no_priority_inversion(log)

    def test_cooling_counts_as_split_on(self) -> None:
        """SplitMode.COOLING counts as split ON."""
        records = [_make_record(t=i, split_mode=SplitMode.COOLING) for i in range(10)]
        log = _make_log(records)
        with pytest.raises(AssertionError, match="split runtime 100.0%"):
            assert_no_priority_inversion(log)

    def test_custom_threshold(self) -> None:
        """Custom max_split_pct=30.0 rejects 40% runtime."""
        # 4 ON, 6 OFF -> 40%
        records = [_make_record(t=i, split_mode=SplitMode.HEATING) for i in range(4)]
        records.extend(
            _make_record(t=4 + i, split_mode=SplitMode.OFF) for i in range(6)
        )
        log = _make_log(records)
        with pytest.raises(AssertionError, match="split runtime 40.0%"):
            assert_no_priority_inversion(log, max_split_pct=30.0)

    def test_error_message_contains_diagnostics(self) -> None:
        """Error message includes percentages and counts."""
        records = [_make_record(t=i, split_mode=SplitMode.HEATING) for i in range(8)]
        records.extend(
            _make_record(t=8 + i, split_mode=SplitMode.OFF) for i in range(2)
        )
        log = _make_log(records)
        with pytest.raises(AssertionError, match="split_on=8/10"):
            assert_no_priority_inversion(log)

    def test_all_split_off_passes(self) -> None:
        """All split OFF -> 0% runtime, passes any threshold."""
        log = _make_log(
            [_make_record(t=i, split_mode=SplitMode.OFF) for i in range(10)]
        )
        assert_no_priority_inversion(log)  # should not raise


# ---------------------------------------------------------------------------
# TestAssertNoOpposingAction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssertNoOpposingAction:
    """Tests for assert_no_opposing_action."""

    def test_passes_consistent_heating(self) -> None:
        """Split HEATING in HEATING mode passes."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    hp_mode=HeatPumpMode.HEATING,
                    split_mode=SplitMode.HEATING,
                ),
            ]
        )
        assert_no_opposing_action(log)  # should not raise

    def test_passes_consistent_cooling(self) -> None:
        """Split COOLING in COOLING mode passes."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    hp_mode=HeatPumpMode.COOLING,
                    split_mode=SplitMode.COOLING,
                ),
            ]
        )
        assert_no_opposing_action(log)  # should not raise

    def test_passes_split_off_in_heating(self) -> None:
        """Split OFF in any HP mode passes."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    hp_mode=HeatPumpMode.HEATING,
                    split_mode=SplitMode.OFF,
                ),
            ]
        )
        assert_no_opposing_action(log)  # should not raise

    def test_passes_hp_off_with_split_heating(self) -> None:
        """HP OFF with any split mode passes (Axiom #3 only applies when HP active)."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    hp_mode=HeatPumpMode.OFF,
                    split_mode=SplitMode.HEATING,
                ),
            ]
        )
        assert_no_opposing_action(log)  # should not raise

    def test_passes_hp_off_with_split_cooling(self) -> None:
        """HP OFF with split COOLING passes."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    hp_mode=HeatPumpMode.OFF,
                    split_mode=SplitMode.COOLING,
                ),
            ]
        )
        assert_no_opposing_action(log)  # should not raise

    def test_raises_cooling_in_heating_mode(self) -> None:
        """Split COOLING while HP HEATING raises AssertionError."""
        log = _make_log(
            [
                _make_record(
                    t=3,
                    hp_mode=HeatPumpMode.HEATING,
                    split_mode=SplitMode.COOLING,
                ),
            ]
        )
        with pytest.raises(AssertionError, match="split COOLING while HP HEATING"):
            assert_no_opposing_action(log)

    def test_raises_heating_in_cooling_mode(self) -> None:
        """Split HEATING while HP COOLING raises AssertionError."""
        log = _make_log(
            [
                _make_record(
                    t=7,
                    hp_mode=HeatPumpMode.COOLING,
                    split_mode=SplitMode.HEATING,
                ),
            ]
        )
        with pytest.raises(AssertionError, match="split HEATING while HP COOLING"):
            assert_no_opposing_action(log)

    def test_empty_log_passes_silently(self) -> None:
        """Empty log passes without error."""
        log = SimulationLog()
        assert_no_opposing_action(log)  # should not raise

    def test_error_message_includes_timestep(self) -> None:
        """Error message includes the violating timestep."""
        log = _make_log(
            [
                _make_record(
                    t=99,
                    hp_mode=HeatPumpMode.HEATING,
                    split_mode=SplitMode.COOLING,
                ),
            ]
        )
        with pytest.raises(AssertionError, match="t=99"):
            assert_no_opposing_action(log)

    def test_detects_first_violation(self) -> None:
        """Raises on the first opposing action, not later ones."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    hp_mode=HeatPumpMode.HEATING,
                    split_mode=SplitMode.OFF,
                ),
                _make_record(
                    t=1,
                    hp_mode=HeatPumpMode.HEATING,
                    split_mode=SplitMode.COOLING,
                ),
                _make_record(
                    t=2,
                    hp_mode=HeatPumpMode.COOLING,
                    split_mode=SplitMode.HEATING,
                ),
            ]
        )
        with pytest.raises(AssertionError, match="t=1"):
            assert_no_opposing_action(log)

    def test_mixed_valid_records_pass(self) -> None:
        """Mix of valid modes (OFF, consistent) passes."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    hp_mode=HeatPumpMode.HEATING,
                    split_mode=SplitMode.HEATING,
                ),
                _make_record(
                    t=1,
                    hp_mode=HeatPumpMode.OFF,
                    split_mode=SplitMode.COOLING,
                ),
                _make_record(
                    t=2,
                    hp_mode=HeatPumpMode.COOLING,
                    split_mode=SplitMode.OFF,
                ),
                _make_record(
                    t=3,
                    hp_mode=HeatPumpMode.COOLING,
                    split_mode=SplitMode.COOLING,
                ),
            ]
        )
        assert_no_opposing_action(log)  # should not raise


# ---------------------------------------------------------------------------
# TestAssertEnergyVsBaseline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssertEnergyVsBaseline:
    """Tests for assert_energy_vs_baseline."""

    # Common energy parameters for all tests in this class.
    _SETPOINT = 21.0
    _UFH_MAX_POWER_W = 5000.0
    _SPLIT_POWER_W = 2500.0
    _DT_MINUTES = 1

    def _assert_energy(
        self,
        log: SimulationLog,
        baseline_log: SimulationLog,
        *,
        max_increase: float = 0.1,
    ) -> None:
        """Call assert_energy_vs_baseline with standard energy params."""
        assert_energy_vs_baseline(
            log,
            baseline_log,
            max_increase=max_increase,
            setpoint=self._SETPOINT,
            ufh_max_power_w=self._UFH_MAX_POWER_W,
            split_power_w=self._SPLIT_POWER_W,
            dt_minutes=self._DT_MINUTES,
        )

    def test_passes_same_energy(self) -> None:
        """Identical logs pass (0% increase)."""
        log = _make_log(
            [
                _make_record(t=0, valve_position=50.0, split_mode=SplitMode.OFF),
            ]
        )
        self._assert_energy(log, log)  # should not raise

    def test_passes_lower_energy(self) -> None:
        """Test log with less energy than baseline passes."""
        baseline = _make_log(
            [
                _make_record(
                    t=0,
                    valve_position=100.0,
                    split_mode=SplitMode.HEATING,
                ),
            ]
        )
        test = _make_log(
            [
                _make_record(t=0, valve_position=50.0, split_mode=SplitMode.OFF),
            ]
        )
        self._assert_energy(test, baseline)  # should not raise

    def test_passes_within_max_increase(self) -> None:
        """Energy slightly above baseline but within 10% passes."""
        # baseline: valve=50% -> 2500W floor, split OFF -> 0W
        # test: valve=54% -> 2700W floor, split OFF -> 0W
        # increase = (2700 - 2500) / 2500 = 8% < 10%
        baseline = _make_log(
            [
                _make_record(t=0, valve_position=50.0, split_mode=SplitMode.OFF),
            ]
        )
        test = _make_log(
            [
                _make_record(t=0, valve_position=54.0, split_mode=SplitMode.OFF),
            ]
        )
        self._assert_energy(test, baseline)  # should not raise

    def test_raises_exceeds_max_increase(self) -> None:
        """Energy >10% above baseline raises AssertionError."""
        # baseline: valve=50% -> 2500W
        # test: valve=100% -> 5000W, increase = 100% > 10%
        baseline = _make_log(
            [
                _make_record(t=0, valve_position=50.0, split_mode=SplitMode.OFF),
            ]
        )
        test = _make_log(
            [
                _make_record(t=0, valve_position=100.0, split_mode=SplitMode.OFF),
            ]
        )
        with pytest.raises(AssertionError, match="exceeds baseline"):
            self._assert_energy(test, baseline)

    def test_raises_nonzero_vs_zero_baseline(self) -> None:
        """Non-zero test energy with zero baseline raises."""
        baseline = _make_log(
            [
                _make_record(t=0, valve_position=0.0, split_mode=SplitMode.OFF),
            ]
        )
        test = _make_log(
            [
                _make_record(t=0, valve_position=50.0, split_mode=SplitMode.OFF),
            ]
        )
        with pytest.raises(AssertionError, match="zero baseline"):
            self._assert_energy(test, baseline)

    def test_passes_both_zero_energy(self) -> None:
        """Both logs with zero energy passes."""
        log = _make_log(
            [
                _make_record(t=0, valve_position=0.0, split_mode=SplitMode.OFF),
            ]
        )
        self._assert_energy(log, log)  # should not raise

    def test_custom_max_increase(self) -> None:
        """Custom max_increase=0.5 allows 50% increase."""
        # baseline: valve=50% -> 2500W
        # test: valve=70% -> 3500W, increase = 40% < 50%
        baseline = _make_log(
            [
                _make_record(t=0, valve_position=50.0, split_mode=SplitMode.OFF),
            ]
        )
        test = _make_log(
            [
                _make_record(t=0, valve_position=70.0, split_mode=SplitMode.OFF),
            ]
        )
        self._assert_energy(test, baseline, max_increase=0.5)  # should not raise

    def test_error_message_contains_diagnostics(self) -> None:
        """Error message includes energy values and percentage."""
        baseline = _make_log(
            [
                _make_record(t=0, valve_position=50.0, split_mode=SplitMode.OFF),
            ]
        )
        test = _make_log(
            [
                _make_record(t=0, valve_position=100.0, split_mode=SplitMode.OFF),
            ]
        )
        with pytest.raises(AssertionError, match="kWh"):
            self._assert_energy(test, baseline)

    def test_multi_step_logs(self) -> None:
        """Works correctly with multi-step logs."""
        baseline_records = [
            _make_record(t=i, valve_position=50.0, split_mode=SplitMode.OFF)
            for i in range(10)
        ]
        test_records = [
            _make_record(t=i, valve_position=50.0, split_mode=SplitMode.OFF)
            for i in range(10)
        ]
        baseline = _make_log(baseline_records)
        test = _make_log(test_records)
        self._assert_energy(test, baseline)  # should not raise


# ---------------------------------------------------------------------------
# TestAssertNoFreezing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssertNoFreezing:
    """Tests for assert_no_freezing."""

    def test_passes_when_all_above_min(self) -> None:
        """All records above hard_min pass without raising."""
        log = _make_log(
            [_make_record(t=i, T_room=20.0, room_name="salon") for i in range(10)]
        )
        assert_no_freezing(log)  # should not raise

    def test_passes_at_exact_threshold(self) -> None:
        """Records exactly at hard_min pass (check is strict <)."""
        log = _make_log(
            [_make_record(t=i, T_room=16.0, room_name="salon") for i in range(10)]
        )
        assert_no_freezing(log)  # should not raise

    def test_raises_on_freezing_room(self) -> None:
        """Single freezing record raises with full diagnostics."""
        log = _make_log(
            [
                _make_record(t=42, T_room=15.5, room_name="salon"),
            ]
        )
        with pytest.raises(AssertionError) as exc_info:
            assert_no_freezing(log)
        message = str(exc_info.value)
        assert "salon" in message
        assert "t=42" in message
        assert "15.50" in message

    def test_raises_on_first_violation_only(self) -> None:
        """Raises on the first violating record, not later ones."""
        records = [
            _make_record(t=0, T_room=20.0, room_name="salon"),
            _make_record(t=1, T_room=20.0, room_name="salon"),
            _make_record(t=2, T_room=20.0, room_name="salon"),
            _make_record(t=3, T_room=15.0, room_name="salon"),  # first violation
            _make_record(t=4, T_room=20.0, room_name="salon"),
            _make_record(t=5, T_room=20.0, room_name="salon"),
            _make_record(t=6, T_room=20.0, room_name="salon"),
            _make_record(t=7, T_room=14.0, room_name="salon"),  # later violation
        ]
        log = _make_log(records)
        with pytest.raises(AssertionError, match="t=3"):
            assert_no_freezing(log)

    def test_multi_room_detects_correct_room(self) -> None:
        """Interleaved multi-room log detects the correct freezing room."""
        records = [
            _make_record(t=0, T_room=20.0, room_name="salon"),
            _make_record(t=0, T_room=20.0, room_name="sypialnia"),
            _make_record(t=1, T_room=20.0, room_name="salon"),
            _make_record(t=1, T_room=14.0, room_name="sypialnia"),  # violation
            _make_record(t=2, T_room=20.0, room_name="salon"),
            _make_record(t=2, T_room=20.0, room_name="sypialnia"),
        ]
        log = _make_log(records)
        with pytest.raises(AssertionError) as exc_info:
            assert_no_freezing(log)
        message = str(exc_info.value)
        assert "sypialnia" in message
        assert "salon" not in message

    def test_empty_log_passes(self) -> None:
        """Empty log passes silently."""
        log = SimulationLog()
        assert_no_freezing(log)  # should not raise

    def test_custom_hard_min(self) -> None:
        """Custom hard_min=10.0 accepts T=12.0 but rejects T=9.0."""
        ok_log = _make_log(
            [_make_record(t=i, T_room=12.0, room_name="salon") for i in range(5)]
        )
        assert_no_freezing(ok_log, hard_min=10.0)  # should not raise

        bad_log = _make_log([_make_record(t=0, T_room=9.0, room_name="salon")])
        with pytest.raises(AssertionError, match="hard_min=10.00"):
            assert_no_freezing(bad_log, hard_min=10.0)

    def test_unnamed_room_renders_placeholder(self) -> None:
        """Records with empty room_name render as '<unnamed>' in diagnostics."""
        log = _make_log([_make_record(t=0, T_room=15.0, room_name="")])
        with pytest.raises(AssertionError, match="<unnamed>"):
            assert_no_freezing(log)


# ---------------------------------------------------------------------------
# TestAssertNoProlongedCold
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssertNoProlongedCold:
    """Tests for assert_no_prolonged_cold."""

    def test_passes_when_above_threshold(self) -> None:
        """All records above threshold pass without raising."""
        log = _make_log(
            [_make_record(t=i, T_room=21.0, room_name="salon") for i in range(100)]
        )
        assert_no_prolonged_cold(log)  # should not raise

    def test_passes_short_dip(self) -> None:
        """Cold dip shorter than max duration does not raise."""
        # 60-minute dip, well under default 1440-minute max
        records = [_make_record(t=i, T_room=17.0, room_name="salon") for i in range(60)]
        records.append(_make_record(t=60, T_room=20.0, room_name="salon"))
        log = _make_log(records)
        assert_no_prolonged_cold(log)  # should not raise

    def test_raises_on_prolonged_cold_run(self) -> None:
        """Cold run longer than 1440 min raises with full diagnostics."""
        # Cold run: t=0..1500, 1501 minutes total span -> duration 1500 > 1440
        records = [
            _make_record(t=i, T_room=17.0, room_name="kitchen") for i in range(0, 1501)
        ]
        log = _make_log(records)
        with pytest.raises(AssertionError) as exc_info:
            assert_no_prolonged_cold(log)
        message = str(exc_info.value)
        assert "kitchen" in message
        assert "starting at t=0" in message
        assert "17.00" in message

    def test_run_resets_on_warm_record(self) -> None:
        """Two short cold runs separated by a warm record do not raise."""
        # First cold run 0..600 (601 min, duration 600), warm at 700, second cold
        # run 701..1300 (duration 599). Neither exceeds 1440.
        records = []
        for t in range(0, 601):
            records.append(_make_record(t=t, T_room=17.0, room_name="salon"))
        records.append(_make_record(t=700, T_room=20.0, room_name="salon"))
        for t in range(701, 1301):
            records.append(_make_record(t=t, T_room=17.0, room_name="salon"))
        log = _make_log(records)
        assert_no_prolonged_cold(log)  # should not raise

    def test_multi_room_independent_runs(self) -> None:
        """Cold run in one room raises while another stays warm."""
        records: list[SimRecord] = []
        for t in range(0, 1501):
            records.append(_make_record(t=t, T_room=21.0, room_name="salon"))
            records.append(_make_record(t=t, T_room=17.0, room_name="sypialnia"))
        log = _make_log(records)
        with pytest.raises(AssertionError) as exc_info:
            assert_no_prolonged_cold(log)
        message = str(exc_info.value)
        assert "sypialnia" in message

    def test_empty_log_passes(self) -> None:
        """Empty log passes silently."""
        log = SimulationLog()
        assert_no_prolonged_cold(log)  # should not raise

    def test_exact_threshold_passes(self) -> None:
        """Cold run of exactly max_duration_minutes does NOT raise (strict >)."""
        # t=0..1440 inclusive -> duration = 1440, equal to max. Strict > => pass.
        records = [
            _make_record(t=t, T_room=17.0, room_name="salon") for t in range(0, 1441)
        ]
        log = _make_log(records)
        assert_no_prolonged_cold(log)  # should not raise

    def test_custom_threshold_and_duration(self) -> None:
        """Custom threshold=19.0 with max_duration_minutes=60 catches a short dip."""
        # Cold run: t=0..100, duration=100 > 60
        records = [
            _make_record(t=t, T_room=18.5, room_name="salon") for t in range(0, 101)
        ]
        log = _make_log(records)
        with pytest.raises(AssertionError, match="60 min"):
            assert_no_prolonged_cold(
                log,
                threshold=19.0,
                max_duration_minutes=60,
            )

    def test_min_temp_reported_correctly(self) -> None:
        """Diagnostic message reports the minimum temperature in the run."""
        # Cold run from t=0..1500 with min temp 14.5
        records: list[SimRecord] = []
        for t in range(0, 1501):
            T = 17.0 if t != 750 else 14.5
            records.append(_make_record(t=t, T_room=T, room_name="salon"))
        log = _make_log(records)
        with pytest.raises(AssertionError, match="14.50"):
            assert_no_prolonged_cold(log)

    def test_unnamed_room_renders_placeholder(self) -> None:
        """Records with empty room_name render as '<unnamed>' in diagnostics."""
        records = [_make_record(t=t, T_room=17.0, room_name="") for t in range(0, 1501)]
        log = _make_log(records)
        with pytest.raises(AssertionError, match="<unnamed>"):
            assert_no_prolonged_cold(log)
