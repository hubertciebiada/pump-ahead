"""Integration tests for Epic #5 -- Metrics, assertions, and test framework.

Verifies end-to-end wiring between the three sub-issue modules:
    #38 SimMetrics (metrics.py)
    #39 Assertion functions (metrics.py)
    #40 Pytest integration (conftest.py fixtures, markers, parametrized scenarios)

Tests exercise the full pipeline:
    SimulationLog -> SimMetrics.from_log() -> assertions
    SimulationLog -> get_room() / time_range() -> SimMetrics
    Two controller logs -> SimMetrics.compare()

All tests are fast (<1s total), deterministic, and use the
``@pytest.mark.unit`` marker.
"""

from __future__ import annotations

import ast
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

from pumpahead.config import SimScenario
from pumpahead.metrics import (
    SimMetrics,
    assert_comfort,
    assert_energy_vs_baseline,
    assert_floor_temp_safe,
    assert_no_opposing_action,
    assert_no_priority_inversion,
)
from pumpahead.scenarios import SCENARIO_LIBRARY
from pumpahead.simulation_log import SimRecord, SimulationLog
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.weather import WeatherPoint

_REPO_ROOT = Path(__file__).resolve().parents[2]

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
# TestEpic05Integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEpic05Integration:
    """Integration tests verifying SimMetrics, assertions, and test framework
    modules work together end-to-end."""

    # -- (a) SimulationLog -> SimMetrics pipeline ----------------------------

    def test_simulation_log_feeds_sim_metrics(self) -> None:
        """100-record clean log produces expected metrics via from_log().

        Constructs a log where every record is at setpoint (21.0 degC),
        T_slab=23.0, valve=50%, split OFF, humidity=50%, hp_mode=HEATING.
        Verifies comfort is 100%, no overshoot/undershoot, energy > 0,
        no condensation, no mode switches, split runtime 0%.
        """
        records = [
            _make_record(
                t=i,
                T_room=21.0,
                T_slab=23.0,
                valve_position=50.0,
                split_mode=SplitMode.OFF,
                humidity=50.0,
                hp_mode=HeatPumpMode.HEATING,
            )
            for i in range(100)
        ]
        log = _make_log(records)

        m = SimMetrics.from_log(
            log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )

        assert m.comfort_pct == pytest.approx(100.0)
        assert m.max_overshoot == pytest.approx(0.0)
        assert m.max_undershoot == pytest.approx(0.0)
        assert m.energy_kwh is not None
        assert m.energy_kwh > 0.0
        assert m.condensation_events == 0
        assert m.mode_switches == 0
        assert m.split_runtime_pct == pytest.approx(0.0)

    # -- (b) Room filtering then metrics ------------------------------------

    def test_room_filtering_then_metrics(self) -> None:
        """Multi-room log filtered by get_room() produces per-room metrics.

        Creates interleaved records for "salon" and "kitchen" with
        different T_room values. Filters for "salon" and verifies the
        metrics reflect only the salon records.
        """
        records: list[SimRecord] = []
        for i in range(20):
            # salon: T_room=21.0 (at setpoint)
            records.append(_make_record(t=i, T_room=21.0, room_name="salon"))
            # kitchen: T_room=25.0 (far from setpoint)
            records.append(_make_record(t=i, T_room=25.0, room_name="kitchen"))

        log = _make_log(records)
        salon_log = log.get_room("salon")

        assert len(salon_log) == 20

        m = SimMetrics.from_log(salon_log, setpoint=21.0)
        assert m.comfort_pct == pytest.approx(100.0)

        # Kitchen metrics should show 0% comfort at default band
        kitchen_log = log.get_room("kitchen")
        m_kitchen = SimMetrics.from_log(kitchen_log, setpoint=21.0)
        assert m_kitchen.comfort_pct == pytest.approx(0.0)

    # -- (c) All assertions accept clean log --------------------------------

    def test_assertions_accept_clean_log(self) -> None:
        """All four assertion functions pass on a safe, comfortable log.

        The log has: T_room at setpoint, T_slab well within limits,
        no split usage, consistent HP mode.
        """
        records = [
            _make_record(
                t=i,
                T_room=21.0,
                T_slab=23.0,
                valve_position=50.0,
                split_mode=SplitMode.OFF,
                hp_mode=HeatPumpMode.HEATING,
                humidity=50.0,
            )
            for i in range(20)
        ]
        log = _make_log(records)

        # None of these should raise
        assert_comfort(log, setpoint=21.0)
        assert_floor_temp_safe(log)
        assert_no_priority_inversion(log)
        assert_no_opposing_action(log)

    # -- (d) Assertions detect violations -----------------------------------

    def test_assertions_detect_floor_temp_violation(self) -> None:
        """assert_floor_temp_safe raises on T_slab > 34.0 degC."""
        log = _make_log([_make_record(t=0, T_slab=36.0, humidity=50.0)])
        with pytest.raises(AssertionError, match="exceeds max 34.00"):
            assert_floor_temp_safe(log)

    def test_assertions_detect_priority_inversion(self) -> None:
        """assert_no_priority_inversion raises when split runs > 50%.

        8/10 records with split HEATING = 80% > 50% threshold.
        """
        records = [_make_record(t=i, split_mode=SplitMode.HEATING) for i in range(8)]
        records.extend(
            _make_record(t=8 + i, split_mode=SplitMode.OFF) for i in range(2)
        )
        log = _make_log(records)
        with pytest.raises(AssertionError, match="split runtime 80.0%"):
            assert_no_priority_inversion(log)

    def test_assertions_detect_opposing_action(self) -> None:
        """assert_no_opposing_action raises when split COOLING in HEATING mode."""
        log = _make_log(
            [
                _make_record(
                    t=0,
                    hp_mode=HeatPumpMode.HEATING,
                    split_mode=SplitMode.COOLING,
                ),
            ]
        )
        with pytest.raises(AssertionError, match="split COOLING while HP HEATING"):
            assert_no_opposing_action(log)

    def test_assertions_detect_comfort_violation(self) -> None:
        """assert_comfort raises when all records are far from setpoint.

        T_room=25.0 with setpoint=21.0, default band=0.5 -> 0% comfort.
        """
        records = [_make_record(t=i, T_room=25.0) for i in range(10)]
        log = _make_log(records)
        with pytest.raises(AssertionError, match="comfort 0.0%"):
            assert_comfort(log, setpoint=21.0)

    # -- (e) Metrics compare two controllers --------------------------------

    def test_metrics_compare_two_controllers(self) -> None:
        """SimMetrics.compare() returns deltas for all fields.

        Builds two logs with different controller behaviour and verifies
        the diff dict contains all SimMetrics field names as keys.
        """
        # "good" controller: at setpoint, low valve, split OFF
        good_records = [
            _make_record(
                t=i,
                T_room=21.0,
                valve_position=30.0,
                split_mode=SplitMode.OFF,
                hp_mode=HeatPumpMode.HEATING,
            )
            for i in range(20)
        ]
        # "bad" controller: high overshoot, high valve, split always on
        bad_records = [
            _make_record(
                t=i,
                T_room=23.0,
                valve_position=80.0,
                split_mode=SplitMode.HEATING,
                hp_mode=HeatPumpMode.HEATING,
            )
            for i in range(20)
        ]

        m_good = SimMetrics.from_log(
            _make_log(good_records),
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        m_bad = SimMetrics.from_log(
            _make_log(bad_records),
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )

        diff = m_good.compare(m_bad)

        # All 13 SimMetrics fields should be present as keys
        expected_keys = {f.name for f in dc_fields(SimMetrics)}
        assert set(diff.keys()) == expected_keys

        # Good controller has 100% comfort, bad has 0% -> delta = +100
        assert diff["comfort_pct"] is not None
        assert diff["comfort_pct"] == pytest.approx(100.0)

        # Good uses less energy than bad
        assert diff["energy_kwh"] is not None
        assert diff["energy_kwh"] < 0.0

        # Good has 0% split runtime, bad has 100% -> delta = -100
        assert diff["split_runtime_pct"] is not None
        assert diff["split_runtime_pct"] == pytest.approx(-100.0)

    # -- (f) Energy vs baseline integration ---------------------------------

    def test_energy_vs_baseline_integration(self) -> None:
        """assert_energy_vs_baseline passes for same-energy logs, fails for excess.

        Verifies the full chain: two logs -> SimMetrics.from_log() -> comparison.
        """
        baseline_records = [
            _make_record(t=i, valve_position=50.0, split_mode=SplitMode.OFF)
            for i in range(10)
        ]
        baseline_log = _make_log(baseline_records)

        # Same energy: should pass
        test_log_same = _make_log(baseline_records)
        assert_energy_vs_baseline(
            test_log_same,
            baseline_log,
            setpoint=21.0,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )

        # Excess energy: valve=100% vs baseline valve=50% -> 100% increase
        excess_records = [
            _make_record(t=i, valve_position=100.0, split_mode=SplitMode.OFF)
            for i in range(10)
        ]
        excess_log = _make_log(excess_records)
        with pytest.raises(AssertionError, match="exceeds baseline"):
            assert_energy_vs_baseline(
                excess_log,
                baseline_log,
                setpoint=21.0,
                ufh_max_power_w=5000.0,
                split_power_w=2500.0,
            )

    # -- (g) Time range filtering preserves metrics consistency -------------

    def test_time_range_filtering_preserves_metrics_consistency(self) -> None:
        """Metrics on a time_range() subset are consistent with the subset data.

        Creates a 200-record log, filters to t=[50, 100], and verifies
        the metrics reflect only the filtered records.
        """
        records: list[SimRecord] = []
        for i in range(200):
            # Records 0-99: T_room=21.0 (at setpoint)
            # Records 100-199: T_room=25.0 (far from setpoint)
            t_room = 21.0 if i < 100 else 25.0
            records.append(_make_record(t=i, T_room=t_room, humidity=50.0))

        log = _make_log(records)

        # Subset within the "at setpoint" range
        subset_good = log.time_range(50, 99)
        m_good = SimMetrics.from_log(subset_good, setpoint=21.0)
        assert m_good.comfort_pct == pytest.approx(100.0)
        assert len(subset_good) == 50

        # Subset within the "far from setpoint" range
        subset_bad = log.time_range(150, 199)
        m_bad = SimMetrics.from_log(subset_bad, setpoint=21.0)
        assert m_bad.comfort_pct == pytest.approx(0.0)
        assert len(subset_bad) == 50

        # Subset spanning both ranges
        subset_mixed = log.time_range(80, 119)
        m_mixed = SimMetrics.from_log(subset_mixed, setpoint=21.0)
        # 80-99 = 20 comfortable, 100-119 = 20 uncomfortable -> 50%
        assert m_mixed.comfort_pct == pytest.approx(50.0)

    # -- (h) Public API exports all Epic 05 types ---------------------------

    def test_sim_metrics_exported_from_package(self) -> None:
        """All Epic 05 public types are importable from the pumpahead package."""
        import pumpahead

        # Core types
        assert hasattr(pumpahead, "SimMetrics")
        assert hasattr(pumpahead, "SimRecord")
        assert hasattr(pumpahead, "SimulationLog")

        # Assertion functions
        assert hasattr(pumpahead, "assert_comfort")
        assert hasattr(pumpahead, "assert_floor_temp_safe")
        assert hasattr(pumpahead, "assert_no_priority_inversion")
        assert hasattr(pumpahead, "assert_no_opposing_action")
        assert hasattr(pumpahead, "assert_energy_vs_baseline")

        # Verify they are the correct objects (not stubs)
        assert pumpahead.SimMetrics is SimMetrics
        assert pumpahead.assert_comfort is assert_comfort
        assert pumpahead.assert_floor_temp_safe is assert_floor_temp_safe
        assert pumpahead.assert_no_priority_inversion is assert_no_priority_inversion
        assert pumpahead.assert_no_opposing_action is assert_no_opposing_action
        assert pumpahead.assert_energy_vs_baseline is assert_energy_vs_baseline

    # -- (i) Scenario library produces valid SimScenario instances -----------

    def test_scenario_library_produces_valid_sim_scenarios(self) -> None:
        """Every entry in SCENARIO_LIBRARY produces a valid SimScenario."""
        assert len(SCENARIO_LIBRARY) > 0, "SCENARIO_LIBRARY must not be empty"

        for name, factory in SCENARIO_LIBRARY.items():
            scenario = factory()
            assert isinstance(scenario, SimScenario), (
                f"SCENARIO_LIBRARY[{name!r}]() did not produce a SimScenario"
            )
            assert scenario.name == name, (
                f"Scenario name mismatch: expected {name!r}, got {scenario.name!r}"
            )
            assert len(scenario.building.rooms) > 0, (
                f"SCENARIO_LIBRARY[{name!r}] has no rooms"
            )
            assert scenario.dt_seconds > 0, (
                f"SCENARIO_LIBRARY[{name!r}] has non-positive dt_seconds"
            )

    # -- (j) No homeassistant imports in core (architectural drift guard) ---

    def test_no_homeassistant_imports_in_core(self) -> None:
        """No .py file in pumpahead/ must import homeassistant.

        Parses every Python file in the core library using AST to detect
        any import of homeassistant modules. This is the key architectural
        invariant: pumpahead/ is testable standalone without HA installed.
        """
        core_dir = _REPO_ROOT / "pumpahead"
        violations: list[str] = []

        for py_file in sorted(core_dir.glob("*.py")):
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("homeassistant"):
                            violations.append(
                                f"{py_file.name}: import {alias.name} "
                                f"at line {node.lineno}"
                            )
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.module is not None
                    and node.module.startswith("homeassistant")
                ):
                    violations.append(
                        f"{py_file.name}: from {node.module} "
                        f"import ... at line {node.lineno}"
                    )

        assert violations == [], (
            "Core library has homeassistant imports:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
