"""Unit tests for SimMetrics dataclass and from_log() computation."""

from __future__ import annotations

import pytest

from pumpahead.metrics import SimMetrics, _dew_point
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def comfort_log() -> SimulationLog:
    """Log with 10 records: 8 within comfort band, 2 outside.

    Setpoint: 21.0, comfort_band: 0.5
    Records at T_room: [21.0, 21.2, 20.8, 21.5, 20.5, 20.0, 22.0, 21.3,
                         20.6, 21.1]
    Within band (|dev| <= 0.5): 21.0, 21.2, 20.8, 21.5, 20.5, 21.3, 20.6, 21.1 = 8
    Outside: 20.0 (dev=-1.0), 22.0 (dev=+1.0)
    """
    temps = [21.0, 21.2, 20.8, 21.5, 20.5, 20.0, 22.0, 21.3, 20.6, 21.1]
    return _make_log([_make_record(t=i, T_room=temp) for i, temp in enumerate(temps)])


@pytest.fixture()
def mixed_split_log() -> SimulationLog:
    """Log with 10 records: 4 with split HEATING, 6 with split OFF."""
    records = []
    for i in range(10):
        mode = SplitMode.HEATING if i < 4 else SplitMode.OFF
        records.append(_make_record(t=i, split_mode=mode, split_setpoint=22.0))
    return _make_log(records)


@pytest.fixture()
def condensation_log() -> SimulationLog:
    """Log with 5 records: 2 have condensation risk.

    Condensation occurs when T_floor < T_dew + 2.
    With humidity=80%, T_room=21.0: T_dew ~ 17.42 (Magnus formula)
    Threshold = 17.42 + 2.0 = 19.42
    Records with T_slab=18.0 (< 19.42) trigger condensation.
    """
    records = [
        _make_record(t=0, T_slab=23.0, humidity=80.0),  # safe
        _make_record(t=1, T_slab=18.0, humidity=80.0),  # condensation!
        _make_record(t=2, T_slab=25.0, humidity=80.0),  # safe
        _make_record(t=3, T_slab=18.0, humidity=80.0),  # condensation!
        _make_record(t=4, T_slab=20.0, humidity=80.0),  # safe (20 >= 19)
    ]
    return _make_log(records)


@pytest.fixture()
def mode_switch_log() -> SimulationLog:
    """Log with mode transitions: HEATING -> OFF -> HEATING -> COOLING.

    That's 3 transitions (mode_switches = 3).
    """
    modes = [
        HeatPumpMode.HEATING,
        HeatPumpMode.HEATING,
        HeatPumpMode.OFF,
        HeatPumpMode.OFF,
        HeatPumpMode.HEATING,
        HeatPumpMode.COOLING,
    ]
    return _make_log([_make_record(t=i, hp_mode=m) for i, m in enumerate(modes)])


# ---------------------------------------------------------------------------
# TestSimMetricsComfort
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsComfort:
    """Tests for comfort metrics: comfort_pct, overshoot, undershoot, mean_deviation."""

    def test_comfort_pct_typical(self, comfort_log: SimulationLog) -> None:
        """8/10 records within band -> 80.0%."""
        m = SimMetrics.from_log(comfort_log, setpoint=21.0, comfort_band=0.5)
        assert m.comfort_pct == pytest.approx(80.0)

    def test_comfort_pct_all_comfortable(self) -> None:
        """All records exactly at setpoint -> 100.0%."""
        log = _make_log([_make_record(t=i, T_room=21.0) for i in range(5)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.comfort_pct == pytest.approx(100.0)

    def test_comfort_pct_none_comfortable(self) -> None:
        """All records 2 degC above setpoint -> 0.0%."""
        log = _make_log([_make_record(t=i, T_room=23.0) for i in range(5)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.comfort_pct == pytest.approx(0.0)

    def test_comfort_band_zero(self) -> None:
        """comfort_band=0.0 only counts exact matches."""
        log = _make_log(
            [
                _make_record(t=0, T_room=21.0),
                _make_record(t=1, T_room=21.0),
                _make_record(t=2, T_room=21.1),
            ]
        )
        m = SimMetrics.from_log(log, setpoint=21.0, comfort_band=0.0)
        assert m.comfort_pct == pytest.approx(200.0 / 3.0)

    def test_comfort_band_boundary_inclusive(self) -> None:
        """Record exactly at band edge is comfortable (<=, not <)."""
        log = _make_log([_make_record(t=0, T_room=21.5)])
        m = SimMetrics.from_log(log, setpoint=21.0, comfort_band=0.5)
        assert m.comfort_pct == pytest.approx(100.0)

    def test_max_overshoot(self, comfort_log: SimulationLog) -> None:
        """Max overshoot is 22.0 - 21.0 = 1.0 degC."""
        m = SimMetrics.from_log(comfort_log, setpoint=21.0)
        assert m.max_overshoot == pytest.approx(1.0)

    def test_max_undershoot(self, comfort_log: SimulationLog) -> None:
        """Max undershoot is 21.0 - 20.0 = 1.0 degC."""
        m = SimMetrics.from_log(comfort_log, setpoint=21.0)
        assert m.max_undershoot == pytest.approx(1.0)

    def test_mean_deviation(self) -> None:
        """Mean absolute deviation with known values."""
        # Deviations from 21.0: |0|, |1|, |-1| -> mean = 2/3
        log = _make_log(
            [
                _make_record(t=0, T_room=21.0),
                _make_record(t=1, T_room=22.0),
                _make_record(t=2, T_room=20.0),
            ]
        )
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.mean_deviation == pytest.approx(2.0 / 3.0)


# ---------------------------------------------------------------------------
# TestSimMetricsSplit
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsSplit:
    """Tests for split runtime percentage."""

    def test_split_runtime_typical(self, mixed_split_log: SimulationLog) -> None:
        """4/10 records with split on -> 40.0%."""
        m = SimMetrics.from_log(mixed_split_log, setpoint=21.0)
        assert m.split_runtime_pct == pytest.approx(40.0)

    def test_split_runtime_all_off(self) -> None:
        """All split OFF -> 0.0%."""
        log = _make_log([_make_record(t=i, split_mode=SplitMode.OFF) for i in range(5)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.split_runtime_pct == pytest.approx(0.0)

    def test_split_runtime_cooling_counts(self) -> None:
        """Cooling mode also counts as split ON."""
        log = _make_log(
            [_make_record(t=i, split_mode=SplitMode.COOLING) for i in range(5)]
        )
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.split_runtime_pct == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# TestSimMetricsSafety
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsSafety:
    """Tests for safety metrics: condensation events, floor temperature bounds."""

    def test_condensation_events(self, condensation_log: SimulationLog) -> None:
        """2 records have T_floor < T_dew + 2."""
        m = SimMetrics.from_log(condensation_log, setpoint=21.0)
        assert m.condensation_events == 2

    def test_no_condensation_dry_air(self) -> None:
        """With low humidity (20%), dew point is low -> no condensation."""
        # T_dew ~ -0.28 (Magnus) at T_air=21, RH=20
        # Threshold = -0.28 + 2.0 = 1.72, T_slab=23.0 >> 1.72
        log = _make_log([_make_record(t=0, T_slab=23.0, humidity=20.0)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.condensation_events == 0

    def test_max_floor_temp(self) -> None:
        """Maximum floor temperature across records."""
        log = _make_log(
            [
                _make_record(t=0, T_slab=22.0),
                _make_record(t=1, T_slab=30.0),
                _make_record(t=2, T_slab=25.0),
            ]
        )
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.max_floor_temp == pytest.approx(30.0)

    def test_min_floor_temp(self) -> None:
        """Minimum floor temperature across records."""
        log = _make_log(
            [
                _make_record(t=0, T_slab=22.0),
                _make_record(t=1, T_slab=18.0),
                _make_record(t=2, T_slab=25.0),
            ]
        )
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.min_floor_temp == pytest.approx(18.0)


# ---------------------------------------------------------------------------
# TestSimMetricsModeSwitches
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsModeSwitches:
    """Tests for heat-pump mode switch counting."""

    def test_mode_switches_typical(self, mode_switch_log: SimulationLog) -> None:
        """HEATING->OFF->HEATING->COOLING = 3 switches."""
        m = SimMetrics.from_log(mode_switch_log, setpoint=21.0)
        assert m.mode_switches == 3

    def test_mode_switches_no_change(self) -> None:
        """All same mode -> 0 switches."""
        log = _make_log(
            [_make_record(t=i, hp_mode=HeatPumpMode.HEATING) for i in range(5)]
        )
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.mode_switches == 0

    def test_mode_switches_every_step(self) -> None:
        """Alternating modes -> n-1 switches."""
        modes = [HeatPumpMode.HEATING, HeatPumpMode.OFF] * 3
        log = _make_log([_make_record(t=i, hp_mode=m) for i, m in enumerate(modes)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.mode_switches == 5


# ---------------------------------------------------------------------------
# TestSimMetricsEnergy
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsEnergy:
    """Tests for energy metrics: energy_kwh, peak_power_w, floor_energy_pct."""

    def test_energy_none_without_power_params(self) -> None:
        """Energy fields are None when power params not provided."""
        log = _make_log([_make_record(t=0)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.energy_kwh is None
        assert m.peak_power_w is None
        assert m.floor_energy_pct is None

    def test_energy_with_power_params(self) -> None:
        """Energy computed correctly with ufh_max=5000, split=2500.

        Record: valve_position=50% -> floor_power=2500W, split OFF -> 0W.
        1 step at dt=1min -> energy = 2500 * 60 / 3_600_000 kWh.
        """
        log = _make_log(
            [_make_record(t=0, valve_position=50.0, split_mode=SplitMode.OFF)]
        )
        m = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
            dt_minutes=1,
        )
        expected_kwh = 2500.0 * 60.0 / 3_600_000.0
        assert m.energy_kwh == pytest.approx(expected_kwh)

    def test_peak_power(self) -> None:
        """Peak power is max of floor + split at any timestep."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    valve_position=100.0,
                    split_mode=SplitMode.HEATING,
                ),
                _make_record(t=1, valve_position=50.0, split_mode=SplitMode.OFF),
            ]
        )
        m = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        # Step 0: 5000 + 2500 = 7500W (peak)
        # Step 1: 2500 + 0 = 2500W
        assert m.peak_power_w == pytest.approx(7500.0)

    def test_floor_energy_pct_ufh_only(self) -> None:
        """100% floor energy when split is always OFF."""
        log = _make_log(
            [_make_record(t=0, valve_position=50.0, split_mode=SplitMode.OFF)]
        )
        m = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        assert m.floor_energy_pct == pytest.approx(100.0)

    def test_floor_energy_pct_mixed(self) -> None:
        """Floor energy percentage with mixed UFH + split."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    valve_position=50.0,
                    split_mode=SplitMode.HEATING,
                ),
            ]
        )
        m = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        # floor: 2500W, split: 2500W -> floor_pct = 50%
        assert m.floor_energy_pct == pytest.approx(50.0)

    def test_zero_energy_floor_pct_zero(self) -> None:
        """When valve=0 and split=OFF, floor_energy_pct=0.0 (not NaN)."""
        log = _make_log(
            [_make_record(t=0, valve_position=0.0, split_mode=SplitMode.OFF)]
        )
        m = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        assert m.energy_kwh == pytest.approx(0.0)
        assert m.floor_energy_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestSimMetricsEmptyLog
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsEmptyLog:
    """Tests for empty log handling — no crash, zeroed metrics."""

    def test_empty_log_no_crash(self) -> None:
        """Empty log produces metrics without raising."""
        log = SimulationLog()
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.comfort_pct == pytest.approx(0.0)
        assert m.max_overshoot == pytest.approx(0.0)
        assert m.max_undershoot == pytest.approx(0.0)
        assert m.mean_deviation == pytest.approx(0.0)
        assert m.condensation_events == 0
        assert m.mode_switches == 0

    def test_empty_log_energy_none(self) -> None:
        """Empty log without power params -> energy fields are None."""
        log = SimulationLog()
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.energy_kwh is None
        assert m.peak_power_w is None
        assert m.floor_energy_pct is None

    def test_empty_log_energy_with_params(self) -> None:
        """Empty log with power params -> energy fields are 0.0."""
        log = SimulationLog()
        m = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        assert m.energy_kwh == pytest.approx(0.0)
        assert m.peak_power_w == pytest.approx(0.0)
        assert m.floor_energy_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestSimMetricsSingleRecord
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsSingleRecord:
    """Tests for single-record logs."""

    def test_single_record_at_setpoint(self) -> None:
        """Single record at setpoint: comfort=100%, deviation=0."""
        log = _make_log([_make_record(t=0, T_room=21.0)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.comfort_pct == pytest.approx(100.0)
        assert m.mean_deviation == pytest.approx(0.0)
        assert m.max_overshoot == pytest.approx(0.0)
        assert m.max_undershoot == pytest.approx(0.0)

    def test_single_record_mode_switches_zero(self) -> None:
        """Single record cannot have mode switches."""
        log = _make_log([_make_record(t=0)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.mode_switches == 0

    def test_single_record_floor_temps(self) -> None:
        """Single record: max and min floor temp are the same."""
        log = _make_log([_make_record(t=0, T_slab=25.0)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        assert m.max_floor_temp == pytest.approx(25.0)
        assert m.min_floor_temp == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# TestSimMetricsCompare
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsCompare:
    """Tests for the compare() method."""

    def test_compare_identical(self) -> None:
        """Comparing identical metrics yields all-zero deltas."""
        log = _make_log([_make_record(t=i, T_room=21.0) for i in range(5)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        diff = m.compare(m)
        for key, val in diff.items():
            if val is not None:
                assert val == pytest.approx(0.0), f"{key} should be 0.0"

    def test_compare_comfort_delta(self) -> None:
        """Better controller has higher comfort_pct -> positive delta."""
        good_log = _make_log([_make_record(t=i, T_room=21.0) for i in range(10)])
        bad_log = _make_log([_make_record(t=i, T_room=23.0) for i in range(10)])
        good = SimMetrics.from_log(good_log, setpoint=21.0)
        bad = SimMetrics.from_log(bad_log, setpoint=21.0)
        diff = good.compare(bad)
        assert diff["comfort_pct"] is not None
        assert diff["comfort_pct"] == pytest.approx(100.0)

    def test_compare_energy_none_when_missing(self) -> None:
        """Delta is None when either side has None energy fields."""
        log = _make_log([_make_record(t=0)])
        m_no_energy = SimMetrics.from_log(log, setpoint=21.0)
        m_with_energy = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        diff = m_no_energy.compare(m_with_energy)
        assert diff["energy_kwh"] is None
        assert diff["peak_power_w"] is None
        assert diff["floor_energy_pct"] is None

    def test_compare_returns_all_fields(self) -> None:
        """compare() returns a key for every SimMetrics field."""
        log = _make_log([_make_record(t=0)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        diff = m.compare(m)
        from dataclasses import fields as dc_fields

        expected_keys = {f.name for f in dc_fields(SimMetrics)}
        assert set(diff.keys()) == expected_keys

    def test_compare_negative_delta(self) -> None:
        """Lower comfort_pct produces negative delta."""
        good_log = _make_log([_make_record(t=i, T_room=21.0) for i in range(10)])
        bad_log = _make_log([_make_record(t=i, T_room=23.0) for i in range(10)])
        good = SimMetrics.from_log(good_log, setpoint=21.0)
        bad = SimMetrics.from_log(bad_log, setpoint=21.0)
        diff = bad.compare(good)
        assert diff["comfort_pct"] is not None
        assert diff["comfort_pct"] == pytest.approx(-100.0)

    def test_compare_mode_switches_int_delta(self) -> None:
        """mode_switches delta is numeric (int field)."""
        log1 = _make_log(
            [
                _make_record(t=0, hp_mode=HeatPumpMode.HEATING),
                _make_record(t=1, hp_mode=HeatPumpMode.OFF),
            ]
        )
        log2 = _make_log(
            [
                _make_record(t=0, hp_mode=HeatPumpMode.HEATING),
                _make_record(t=1, hp_mode=HeatPumpMode.HEATING),
            ]
        )
        m1 = SimMetrics.from_log(log1, setpoint=21.0)
        m2 = SimMetrics.from_log(log2, setpoint=21.0)
        diff = m1.compare(m2)
        assert diff["mode_switches"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TestSimMetricsDeterminism
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsDeterminism:
    """Verify that the same log always produces the same metrics."""

    def test_deterministic_output(self) -> None:
        """Two calls with the same log and params yield identical metrics."""
        records = [
            _make_record(
                t=i,
                T_room=20.0 + i * 0.3,
                T_slab=22.0 + i * 0.1,
                valve_position=float(i * 10),
                split_mode=SplitMode.HEATING if i % 3 == 0 else SplitMode.OFF,
                hp_mode=(HeatPumpMode.HEATING if i < 5 else HeatPumpMode.COOLING),
                humidity=50.0 + i * 2.0,
            )
            for i in range(10)
        ]
        log = _make_log(records)
        m1 = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        m2 = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        assert m1 == m2


# ---------------------------------------------------------------------------
# TestSimMetricsFrozen
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimMetricsFrozen:
    """Verify that SimMetrics is immutable."""

    def test_cannot_mutate(self) -> None:
        """Assigning to a field raises FrozenInstanceError."""
        log = _make_log([_make_record(t=0)])
        m = SimMetrics.from_log(log, setpoint=21.0)
        with pytest.raises(AttributeError):
            m.comfort_pct = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestDewPoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDewPoint:
    """Tests for the _dew_point helper (now uses Magnus formula)."""

    def test_typical_value(self) -> None:
        """T_dew at 21C, 50% RH ~ 10.17 (Magnus formula)."""
        assert _dew_point(21.0, 50.0) == pytest.approx(10.17, abs=0.1)

    def test_saturated_air(self) -> None:
        """At 100% RH, T_dew = T_air."""
        assert _dew_point(21.0, 100.0) == pytest.approx(21.0)

    def test_dry_air(self) -> None:
        """At 0% RH, T_dew = -273.15 (absolute zero guard)."""
        assert _dew_point(21.0, 0.0) == pytest.approx(-273.15)
