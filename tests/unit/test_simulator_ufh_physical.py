"""Unit tests for the physical UFH power distribution in BuildingSimulator.

Covers ``BuildingSimulator._distribute_hp_power`` after the rewrite for
issue #143 and the clean-break field removal in issue #144 — now driven
exclusively by ``pumpahead.ufh_loop.loop_power`` with a
weather-compensation-derived ``T_supply``.  The legacy proportional
fallback shim was deleted by #144, so every room must carry
``loop_geometry``.

Two test classes:

* ``TestPhysicalDistribution`` — rooms with explicit ``loop_geometry``.
* ``TestDiagnostics`` — ``last_step_info`` surface exposes ``T_supply``
  and per-room ``Q_floor`` correctly.
"""

from __future__ import annotations

import numpy as np
import pytest

from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulator import (
    Actions,
    BuildingSimulator,
    HeatPumpMode,
)
from pumpahead.ufh_loop import LoopGeometry
from pumpahead.weather import SyntheticWeather
from pumpahead.weather_comp import CoolingCompCurve, WeatherCompCurve

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _standard_params() -> RCParams:
    """Return a 3R3C SISO RCParams instance used throughout the tests."""
    return RCParams(
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


def _standard_geometry(area_m2: float = 20.0) -> LoopGeometry:
    """Return a standard UFH loop geometry used throughout the tests."""
    return LoopGeometry(
        effective_pipe_length_m=130.0,
        pipe_spacing_m=0.15,
        pipe_diameter_outer_mm=16.0,
        pipe_wall_thickness_mm=2.0,
        area_m2=area_m2,
    )


def _make_room(
    name: str,
    *,
    loop_geometry: LoopGeometry | None = None,
) -> SimulatedRoom:
    """Create a ``SimulatedRoom`` suitable for distributor tests."""
    model = RCModel(_standard_params(), ModelOrder.THREE, dt=60.0)
    if loop_geometry is None:
        loop_geometry = _standard_geometry()
    return SimulatedRoom(
        name,
        model,
        loop_geometry=loop_geometry,
    )


def _set_room_slab(room: SimulatedRoom, t_slab: float, t_air: float = 20.0) -> None:
    """Set a room's thermal state so ``T_slab`` has a known value."""
    room.set_initial_state(np.array([t_air, t_slab, t_air], dtype=np.float64))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cold_weather() -> SyntheticWeather:
    """Constant weather: T_out=-10 C."""
    return SyntheticWeather.constant(T_out=-10.0, GHI=0.0)


@pytest.fixture()
def mild_weather() -> SyntheticWeather:
    """Constant weather: T_out=+5 C."""
    return SyntheticWeather.constant(T_out=5.0, GHI=0.0)


@pytest.fixture()
def hot_weather() -> SyntheticWeather:
    """Constant weather: T_out=+32 C."""
    return SyntheticWeather.constant(T_out=32.0, GHI=0.0)


@pytest.fixture()
def heating_curve() -> WeatherCompCurve:
    """Heating curve: 30 C at t_out>=10 C, rising to 45 C at t_out<=-10 C."""
    return WeatherCompCurve(
        t_supply_base=30.0,
        slope=0.75,
        t_neutral=10.0,
        t_supply_max=45.0,
        t_supply_min=25.0,
    )


@pytest.fixture()
def cooling_curve() -> CoolingCompCurve:
    """Cooling curve: T_supply=12 C at mild, rising as t_out rises."""
    return CoolingCompCurve(
        t_supply_base=12.0,
        slope=0.3,
        t_neutral=25.0,
        t_supply_max=22.0,
        t_supply_min=8.0,
    )


# ---------------------------------------------------------------------------
# TestPhysicalDistribution — rooms WITH geometry
# ---------------------------------------------------------------------------


class TestPhysicalDistribution:
    """Tests for the physical loop_power path (rooms with geometry)."""

    @pytest.mark.unit
    def test_valve_zero_returns_zero_per_room(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """valve=0 -> allocated power is 0 regardless of T_supply."""
        geometry = _standard_geometry()
        rooms = [
            _make_room("r0", loop_geometry=geometry),
            _make_room("r1", loop_geometry=geometry),
        ]
        for r in rooms:
            _set_room_slab(r, t_slab=22.0)

        sim = BuildingSimulator(
            rooms,
            cold_weather,
            hp_mode=HeatPumpMode.HEATING,
            hp_max_power_w=10_000.0,
        )

        actions = {r.name: Actions(valve_position=0.0) for r in rooms}
        allocated = sim._distribute_hp_power(actions)

        assert allocated["r0"] == 0.0
        assert allocated["r1"] == 0.0

    @pytest.mark.unit
    def test_valve_one_high_supply_high_power(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """valve=100% with a high T_supply yields strictly positive power."""
        geometry = _standard_geometry()
        room = _make_room("r0", loop_geometry=geometry)
        _set_room_slab(room, t_slab=22.0)

        # No weather_comp -> fallback 35 C in heating.
        sim = BuildingSimulator(
            [room],
            cold_weather,
            hp_mode=HeatPumpMode.HEATING,
            hp_max_power_w=10_000.0,
        )

        allocated = sim._distribute_hp_power(
            {"r0": Actions(valve_position=100.0)},
        )

        assert allocated["r0"] > 0.0

    @pytest.mark.unit
    def test_higher_supply_higher_power(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """A higher T_supply (via heating curve) gives strictly more power."""
        geometry = _standard_geometry()

        # Curve A: moderate supply.
        curve_low = WeatherCompCurve(
            t_supply_base=28.0,
            slope=0.0,
            t_neutral=10.0,
            t_supply_max=40.0,
            t_supply_min=25.0,
        )
        # Curve B: aggressive supply.
        curve_high = WeatherCompCurve(
            t_supply_base=40.0,
            slope=0.0,
            t_neutral=10.0,
            t_supply_max=45.0,
            t_supply_min=25.0,
        )

        def _allocate(curve: WeatherCompCurve) -> float:
            room = _make_room("r0", loop_geometry=geometry)
            _set_room_slab(room, t_slab=22.0)
            sim = BuildingSimulator(
                [room],
                cold_weather,
                hp_mode=HeatPumpMode.HEATING,
                hp_max_power_w=100_000.0,  # unconstrained
                weather_comp=curve,
            )
            allocated = sim._distribute_hp_power(
                {"r0": Actions(valve_position=100.0)},
            )
            return allocated["r0"]

        q_low = _allocate(curve_low)
        q_high = _allocate(curve_high)

        assert q_high > q_low
        assert q_low > 0.0

    @pytest.mark.unit
    def test_cold_outdoor_raises_supply_via_curve(
        self,
        heating_curve: WeatherCompCurve,
    ) -> None:
        """Colder outdoor -> curve raises T_supply -> more floor power."""
        geometry = _standard_geometry()

        def _allocate(t_out: float) -> float:
            weather = SyntheticWeather.constant(T_out=t_out, GHI=0.0)
            room = _make_room("r0", loop_geometry=geometry)
            _set_room_slab(room, t_slab=22.0)
            sim = BuildingSimulator(
                [room],
                weather,
                hp_mode=HeatPumpMode.HEATING,
                hp_max_power_w=100_000.0,  # unconstrained
                weather_comp=heating_curve,
            )
            return sim._distribute_hp_power(
                {"r0": Actions(valve_position=100.0)},
            )["r0"]

        q_mild = _allocate(5.0)
        q_cold = _allocate(-15.0)

        assert q_cold > q_mild
        assert q_mild > 0.0

    @pytest.mark.unit
    def test_hp_capacity_limit_scales_proportionally(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """Total physical demand above HP capacity -> proportional scale."""
        geometry = _standard_geometry()
        rooms = [_make_room(f"r{i}", loop_geometry=geometry) for i in range(4)]
        for r in rooms:
            _set_room_slab(r, t_slab=22.0)

        # Unconstrained run to measure raw demand.
        sim_unlimited = BuildingSimulator(
            [_make_room(f"r{i}", loop_geometry=geometry) for i in range(4)],
            cold_weather,
            hp_mode=HeatPumpMode.HEATING,
        )
        for r in sim_unlimited._rooms:
            _set_room_slab(r, t_slab=22.0)

        actions = {f"r{i}": Actions(valve_position=100.0) for i in range(4)}
        raw = sim_unlimited._distribute_hp_power(actions)
        raw_total = sum(raw.values())
        assert raw_total > 0.0

        # Now run with HP capped well below the raw total.
        cap = raw_total / 2.0
        sim = BuildingSimulator(
            rooms,
            cold_weather,
            hp_mode=HeatPumpMode.HEATING,
            hp_max_power_w=cap,
        )
        allocated = sim._distribute_hp_power(actions)

        assert sum(allocated.values()) == pytest.approx(cap)
        # Ratios of the allocated values must match ratios of raw demands.
        for i in range(4):
            expected = raw[f"r{i}"] * cap / raw_total
            assert allocated[f"r{i}"] == pytest.approx(expected, rel=1e-9)

    @pytest.mark.unit
    def test_cooling_returns_negative_values(
        self,
        hot_weather: SyntheticWeather,
    ) -> None:
        """Cooling mode with a warm slab returns negative Q_floor."""
        geometry = _standard_geometry()
        room = _make_room("r0", loop_geometry=geometry)
        _set_room_slab(room, t_slab=24.0)

        sim = BuildingSimulator(
            [room],
            hot_weather,
            hp_mode=HeatPumpMode.COOLING,
            hp_max_power_w=10_000.0,
        )

        allocated = sim._distribute_hp_power(
            {"r0": Actions(valve_position=100.0)},
        )
        assert allocated["r0"] < 0.0

    @pytest.mark.unit
    def test_cooling_hp_capacity_limit(
        self,
        hot_weather: SyntheticWeather,
        cooling_curve: CoolingCompCurve,
    ) -> None:
        """In cooling mode the absolute total respects hp_max_power_w."""
        geometry = _standard_geometry()
        rooms = [_make_room(f"r{i}", loop_geometry=geometry) for i in range(4)]
        for r in rooms:
            _set_room_slab(r, t_slab=24.0)

        actions = {f"r{i}": Actions(valve_position=100.0) for i in range(4)}

        # Raw demand (unconstrained).
        sim_unlimited = BuildingSimulator(
            [_make_room(f"r{i}", loop_geometry=geometry) for i in range(4)],
            hot_weather,
            hp_mode=HeatPumpMode.COOLING,
            cooling_comp=cooling_curve,
        )
        for r in sim_unlimited._rooms:
            _set_room_slab(r, t_slab=24.0)
        raw = sim_unlimited._distribute_hp_power(actions)
        raw_abs_total = sum(abs(d) for d in raw.values())
        assert raw_abs_total > 0.0

        cap = raw_abs_total / 2.0
        sim = BuildingSimulator(
            rooms,
            hot_weather,
            hp_mode=HeatPumpMode.COOLING,
            hp_max_power_w=cap,
            cooling_comp=cooling_curve,
        )
        allocated = sim._distribute_hp_power(actions)

        assert sum(abs(d) for d in allocated.values()) == pytest.approx(cap)
        # All entries must remain non-positive (cooling sign convention).
        for name in allocated:
            assert allocated[name] <= 0.0

    @pytest.mark.unit
    def test_hp_off_returns_zero_and_no_supply(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """HP OFF short-circuits to zero and clears ``t_supply_c``."""
        geometry = _standard_geometry()
        rooms = [_make_room(f"r{i}", loop_geometry=geometry) for i in range(3)]
        sim = BuildingSimulator(
            rooms,
            cold_weather,
            hp_mode=HeatPumpMode.OFF,
            hp_max_power_w=10_000.0,
        )

        allocated = sim._distribute_hp_power(
            {r.name: Actions(valve_position=100.0) for r in rooms},
        )

        for name, v in allocated.items():
            assert v == 0.0, f"{name} should be 0 when HP is OFF"
        assert sim.last_step_info["t_supply_c"] is None

    @pytest.mark.unit
    def test_axiom_3_wrong_direction_returns_zero(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """HEATING with T_slab >= T_supply -> loop_power=0 (Axiom #3)."""
        geometry = _standard_geometry()
        room = _make_room("r0", loop_geometry=geometry)
        # T_slab at 40 C is hotter than the fallback 35 C supply.
        _set_room_slab(room, t_slab=40.0)

        sim = BuildingSimulator(
            [room],
            cold_weather,
            hp_mode=HeatPumpMode.HEATING,
            hp_max_power_w=10_000.0,
        )

        allocated = sim._distribute_hp_power(
            {"r0": Actions(valve_position=100.0)},
        )

        assert allocated["r0"] == 0.0

    @pytest.mark.unit
    def test_compute_t_supply_off_returns_zero(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """_compute_t_supply returns 0.0 when HP is OFF (defensive path)."""
        geometry = _standard_geometry()
        room = _make_room("r0", loop_geometry=geometry)
        sim = BuildingSimulator(
            [room],
            cold_weather,
            hp_mode=HeatPumpMode.OFF,
        )
        # Directly exercise the defensive branch — callers of
        # _distribute_hp_power short-circuit OFF before calling this,
        # but the helper still has to return a finite value.
        assert sim._compute_t_supply(-5.0) == 0.0


# ---------------------------------------------------------------------------
# TestGeometryRequired — every room must carry loop_geometry (#144)
# ---------------------------------------------------------------------------


class TestGeometryRequired:
    """Issue #144 removes the legacy shim — geometry is now mandatory."""

    @pytest.mark.unit
    def test_missing_geometry_raises(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """BuildingSimulator refuses rooms without loop_geometry."""
        model = RCModel(_standard_params(), ModelOrder.THREE, dt=60.0)
        room_no_geom = SimulatedRoom("r0", model, loop_geometry=None)
        with pytest.raises(ValueError, match="loop_geometry"):
            BuildingSimulator(
                [room_no_geom],
                cold_weather,
                hp_mode=HeatPumpMode.HEATING,
            )


# ---------------------------------------------------------------------------
# TestDiagnostics — last_step_info surface
# ---------------------------------------------------------------------------


class TestDiagnostics:
    """Tests for BuildingSimulator.last_step_info."""

    @pytest.mark.unit
    def test_initial_state_is_empty(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """Before any step, diagnostics are empty / None."""
        rooms = [
            _make_room("r0", loop_geometry=_standard_geometry()),
        ]
        sim = BuildingSimulator(
            rooms,
            cold_weather,
            hp_mode=HeatPumpMode.HEATING,
        )

        info = sim.last_step_info
        assert info["t_supply_c"] is None
        assert info["q_floor_w"] == {}
        assert info["hp_mode"] == HeatPumpMode.HEATING

    @pytest.mark.unit
    def test_populated_after_step_all(
        self,
        cold_weather: SyntheticWeather,
        heating_curve: WeatherCompCurve,
    ) -> None:
        """After step_all, diagnostics reflect the last distribution."""
        geometry = _standard_geometry()
        rooms = [_make_room(f"r{i}", loop_geometry=geometry) for i in range(2)]
        for r in rooms:
            _set_room_slab(r, t_slab=22.0)

        sim = BuildingSimulator(
            rooms,
            cold_weather,
            hp_mode=HeatPumpMode.HEATING,
            hp_max_power_w=100_000.0,
            weather_comp=heating_curve,
        )

        actions = {r.name: Actions(valve_position=100.0) for r in rooms}
        sim.step_all(actions)

        info = sim.last_step_info

        # T_supply matches the curve at T_out=-10 C.
        expected = heating_curve.t_supply(-10.0)
        assert info["t_supply_c"] == pytest.approx(expected)

        q = info["q_floor_w"]
        assert isinstance(q, dict)
        assert set(q.keys()) == {"r0", "r1"}
        for name in q:
            assert q[name] > 0.0

        assert info["hp_mode"] == HeatPumpMode.HEATING

    @pytest.mark.unit
    def test_last_step_info_is_defensive_copy(
        self,
        cold_weather: SyntheticWeather,
    ) -> None:
        """Mutating q_floor_w in the returned dict does not affect state."""
        geometry = _standard_geometry()
        rooms = [_make_room("r0", loop_geometry=geometry)]
        _set_room_slab(rooms[0], t_slab=22.0)

        sim = BuildingSimulator(
            rooms,
            cold_weather,
            hp_mode=HeatPumpMode.HEATING,
            hp_max_power_w=10_000.0,
        )
        sim.step_all({"r0": Actions(valve_position=100.0)})

        info1 = sim.last_step_info
        q1 = info1["q_floor_w"]
        assert isinstance(q1, dict)
        original = q1["r0"]

        # Mutate the returned dict.
        q1["r0"] = -999.0
        q1["injected"] = 42.0

        info2 = sim.last_step_info
        q2 = info2["q_floor_w"]
        assert isinstance(q2, dict)
        assert q2["r0"] == pytest.approx(original)
        assert "injected" not in q2
