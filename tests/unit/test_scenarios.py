"""Tests for the simulation scenario library.

Validates that all scenarios in ``pumpahead.scenarios`` construct valid
``SimScenario`` instances with correct weather, building, and controller
configurations.  Tests cover construction, determinism, mode coverage,
parametric sweeps, the new ``description`` field, and module exports.
"""

import pytest

from pumpahead.building_profiles import (
    well_insulated,
)
from pumpahead.config import (
    BuildingParams,
    ControllerConfig,
    SimScenario,
)
from pumpahead.scenarios import (
    PARAMETRIC_SWEEPS,
    SCENARIO_LIBRARY,
    bathroom_heater,
    bathroom_heater_cooling,
    cold_snap,
    cwu_heavy,
    dew_point_stress,
    extreme_cold,
    full_year_2025,
    hot_july,
    insulation_sweep,
    rapid_warming,
    screed_sweep,
    solar_overshoot,
    steady_state,
)
from pumpahead.weather import SyntheticWeather, WeatherSource

# ---------------------------------------------------------------------------
# TestScenarioConstruction — library-wide construction tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestScenarioConstruction:
    """Tests for basic construction properties of all scenarios."""

    def test_library_has_at_least_8_entries(self) -> None:
        """SCENARIO_LIBRARY contains at least 8 single scenarios."""
        assert len(SCENARIO_LIBRARY) >= 8

    def test_exactly_18_single_scenarios(self) -> None:
        """SCENARIO_LIBRARY has exactly 18 entries."""
        assert len(SCENARIO_LIBRARY) == 18

    def test_exactly_2_parametric_sweeps(self) -> None:
        """PARAMETRIC_SWEEPS has exactly 2 entries."""
        assert len(PARAMETRIC_SWEEPS) == 2

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_construction_valid(self, name: str) -> None:
        """Every scenario in SCENARIO_LIBRARY constructs without error."""
        factory = SCENARIO_LIBRARY[name]
        scenario = factory()
        assert isinstance(scenario, SimScenario)

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_deterministic(self, name: str) -> None:
        """Every scenario is deterministic — two calls produce identical output."""
        factory = SCENARIO_LIBRARY[name]
        a = factory()
        b = factory()
        # Compare all non-weather fields (frozen dataclass equality)
        assert a.name == b.name
        assert a.building == b.building
        assert a.controller == b.controller
        assert a.duration_minutes == b.duration_minutes
        assert a.mode == b.mode
        assert a.dt_seconds == b.dt_seconds
        assert a.cwu_schedule == b.cwu_schedule
        assert a.sensor_noise_std == b.sensor_noise_std
        assert a.description == b.description
        # Compare weather output at multiple time points
        for t in [0.0, 100.0, 500.0]:
            pa = a.weather.get(t)
            pb = b.weather.get(t)
            assert pa == pb, f"Weather mismatch at t={t}"

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_name_matches_key(self, name: str) -> None:
        """Scenario name matches the registry key."""
        scenario = SCENARIO_LIBRARY[name]()
        assert scenario.name == name

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_has_nonempty_description(self, name: str) -> None:
        """Every scenario has a non-empty description."""
        scenario = SCENARIO_LIBRARY[name]()
        assert scenario.description != ""
        assert len(scenario.description) > 10

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_positive_duration(self, name: str) -> None:
        """Every scenario has a positive duration."""
        scenario = SCENARIO_LIBRARY[name]()
        assert scenario.duration_minutes > 0

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_weather_is_weather_source(self, name: str) -> None:
        """Every scenario's weather satisfies the WeatherSource protocol."""
        scenario = SCENARIO_LIBRARY[name]()
        assert isinstance(scenario.weather, WeatherSource)

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_weather_callable_at_t0(self, name: str) -> None:
        """Weather.get(0) returns valid values for every scenario."""
        scenario = SCENARIO_LIBRARY[name]()
        point = scenario.weather.get(0.0)
        assert isinstance(point.T_out, float)
        assert isinstance(point.GHI, float)
        assert isinstance(point.wind_speed, float)
        assert isinstance(point.humidity, float)

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_building_is_building_params(self, name: str) -> None:
        """Every scenario's building is a valid BuildingParams."""
        scenario = SCENARIO_LIBRARY[name]()
        assert isinstance(scenario.building, BuildingParams)

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_controller_is_controller_config(self, name: str) -> None:
        """Every scenario's controller is a valid ControllerConfig."""
        scenario = SCENARIO_LIBRARY[name]()
        assert isinstance(scenario.controller, ControllerConfig)


# ---------------------------------------------------------------------------
# TestModesCovered — verify heating, cooling, auto modes are represented
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestModesCovered:
    """Tests that the scenario library covers all three operating modes."""

    def test_heating_mode_exists(self) -> None:
        """At least one scenario uses heating mode."""
        modes = {SCENARIO_LIBRARY[n]().mode for n in SCENARIO_LIBRARY}
        assert "heating" in modes

    def test_cooling_mode_exists(self) -> None:
        """At least one scenario uses cooling mode."""
        modes = {SCENARIO_LIBRARY[n]().mode for n in SCENARIO_LIBRARY}
        assert "cooling" in modes

    def test_auto_mode_exists(self) -> None:
        """At least one scenario uses auto mode."""
        modes = {SCENARIO_LIBRARY[n]().mode for n in SCENARIO_LIBRARY}
        assert "auto" in modes

    def test_at_least_three_heating_scenarios(self) -> None:
        """At least 3 scenarios use heating mode."""
        heating = [
            n for n in SCENARIO_LIBRARY if SCENARIO_LIBRARY[n]().mode == "heating"
        ]
        assert len(heating) >= 3

    def test_all_modes_covered(self) -> None:
        """All three modes appear across all scenarios (single + sweep)."""
        modes: set[str] = set()
        for factory in SCENARIO_LIBRARY.values():
            modes.add(factory().mode)
        for gen in PARAMETRIC_SWEEPS.values():
            for s in gen():
                modes.add(s.mode)
        assert modes == {"heating", "cooling", "auto"}


# ---------------------------------------------------------------------------
# TestSpecificScenarios — weather / building correctness per scenario
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSpecificScenarios:
    """Tests validating specific weather and building details."""

    # -- steady_state -------------------------------------------------------

    def test_steady_state_constant_weather(self) -> None:
        """steady_state has constant T_out=0, GHI=0."""
        s = steady_state()
        p0 = s.weather.get(0.0)
        p1000 = s.weather.get(1000.0)
        assert p0.T_out == pytest.approx(0.0)
        assert pytest.approx(0.0) == p0.GHI
        assert p1000.T_out == pytest.approx(0.0)
        assert pytest.approx(0.0) == p1000.GHI

    def test_steady_state_duration_48h(self) -> None:
        """steady_state lasts 48 hours (2880 minutes)."""
        assert steady_state().duration_minutes == 2880

    def test_steady_state_well_insulated_building(self) -> None:
        """steady_state uses well_insulated building (1 room)."""
        s = steady_state()
        assert len(s.building.rooms) == 1

    def test_steady_state_heating_mode(self) -> None:
        """steady_state uses heating mode."""
        assert steady_state().mode == "heating"

    # -- cold_snap ----------------------------------------------------------

    def test_cold_snap_step_weather(self) -> None:
        """cold_snap has T_out step from 0 to -15 at t=1440."""
        s = cold_snap()
        before = s.weather.get(1439.0)
        after = s.weather.get(1441.0)
        assert before.T_out == pytest.approx(0.0)
        assert after.T_out == pytest.approx(-15.0)

    def test_cold_snap_multi_room(self) -> None:
        """cold_snap uses modern_bungalow (13 rooms)."""
        s = cold_snap()
        assert len(s.building.rooms) == 13

    def test_cold_snap_duration_5_days(self) -> None:
        """cold_snap lasts 5 days (7200 minutes)."""
        assert cold_snap().duration_minutes == 7200

    # -- hot_july -----------------------------------------------------------

    def test_hot_july_sinusoidal_t_out(self) -> None:
        """hot_july has sinusoidal T_out with mean=30, amplitude=5."""
        s = hot_july()
        p0 = s.weather.get(0.0)
        # At t=0, sin(0) = 0, so T_out = 30.0
        assert p0.T_out == pytest.approx(30.0)
        # At t=360 (quarter period), sin(pi/2) = 1, so T_out = 35.0
        p360 = s.weather.get(360.0)
        assert p360.T_out == pytest.approx(35.0)

    def test_hot_july_cooling_mode(self) -> None:
        """hot_july uses cooling mode."""
        assert hot_july().mode == "cooling"

    def test_hot_july_duration_31_days(self) -> None:
        """hot_july lasts 31 days (44640 minutes)."""
        assert hot_july().duration_minutes == 44640

    def test_hot_july_setpoint_25(self) -> None:
        """hot_july setpoint is 25C."""
        assert hot_july().controller.setpoint == pytest.approx(25.0)

    # -- solar_overshoot ----------------------------------------------------

    def test_solar_overshoot_auto_mode(self) -> None:
        """solar_overshoot uses auto mode."""
        assert solar_overshoot().mode == "auto"

    def test_solar_overshoot_sinusoidal_ghi(self) -> None:
        """solar_overshoot has sinusoidal GHI with mean=250, amplitude=250."""
        s = solar_overshoot()
        # At t=0, sin(0) = 0, so GHI = 250
        p0 = s.weather.get(0.0)
        assert pytest.approx(250.0) == p0.GHI
        # At quarter period (360 min), sin(pi/2) = 1, GHI = 500
        p360 = s.weather.get(360.0)
        assert pytest.approx(500.0) == p360.GHI

    def test_solar_overshoot_modern_bungalow_building(self) -> None:
        """solar_overshoot uses modern_bungalow (13 rooms)."""
        s = solar_overshoot()
        assert len(s.building.rooms) == 13

    # -- full_year_2025 -----------------------------------------------------

    def test_full_year_duration_525600(self) -> None:
        """full_year_2025 lasts exactly 525600 minutes (365 days)."""
        assert full_year_2025().duration_minutes == 525600

    def test_full_year_auto_mode(self) -> None:
        """full_year_2025 uses auto mode."""
        assert full_year_2025().mode == "auto"

    def test_full_year_temperature_range(self) -> None:
        """full_year_2025 T_out ranges from -5 to +25 over the year."""
        s = full_year_2025()
        # At t=0, sin(0) = 0, T_out = 10
        p0 = s.weather.get(0.0)
        assert p0.T_out == pytest.approx(10.0)
        # At quarter period (525600/4), sin(pi/2)=1, T_out = 25
        p_quarter = s.weather.get(525600.0 / 4)
        assert p_quarter.T_out == pytest.approx(25.0)
        # At three-quarter period, sin(3*pi/2) = -1, T_out = -5
        p_3quarter = s.weather.get(3 * 525600.0 / 4)
        assert p_3quarter.T_out == pytest.approx(-5.0)

    # -- extreme_cold -------------------------------------------------------

    def test_extreme_cold_constant_minus_20(self) -> None:
        """extreme_cold has constant T_out=-20C."""
        s = extreme_cold()
        p0 = s.weather.get(0.0)
        p2000 = s.weather.get(2000.0)
        assert p0.T_out == pytest.approx(-20.0)
        assert p2000.T_out == pytest.approx(-20.0)

    def test_extreme_cold_leaky_building(self) -> None:
        """extreme_cold uses leaky_old_house building."""
        s = extreme_cold()
        # leaky_old_house is single-room
        assert len(s.building.rooms) == 1

    def test_extreme_cold_high_wind(self) -> None:
        """extreme_cold has wind_speed=5.0 m/s."""
        s = extreme_cold()
        p = s.weather.get(0.0)
        assert p.wind_speed == pytest.approx(5.0)

    # -- rapid_warming ------------------------------------------------------

    def test_rapid_warming_ramp_weather(self) -> None:
        """rapid_warming has T_out ramp from -10 to +15 over 720 min."""
        s = rapid_warming()
        p0 = s.weather.get(0.0)
        assert p0.T_out == pytest.approx(-10.0)
        # After the ramp completes (720+ min), T_out = -10 + 25 = 15
        p1000 = s.weather.get(1000.0)
        assert p1000.T_out == pytest.approx(15.0)
        # Midpoint of the ramp (360 min): T_out = -10 + 25*0.5 = 2.5
        p360 = s.weather.get(360.0)
        assert p360.T_out == pytest.approx(2.5)

    def test_rapid_warming_auto_mode(self) -> None:
        """rapid_warming uses auto mode."""
        assert rapid_warming().mode == "auto"

    # -- cwu_heavy ----------------------------------------------------------

    def test_cwu_heavy_has_cwu_schedule(self) -> None:
        """cwu_heavy has a CWU schedule with at least one cycle."""
        s = cwu_heavy()
        assert len(s.cwu_schedule) >= 1

    def test_cwu_heavy_cycle_parameters(self) -> None:
        """cwu_heavy CWU cycle: 45 min duration, 180 min interval."""
        s = cwu_heavy()
        cycle = s.cwu_schedule[0]
        assert cycle.start_minute == 0
        assert cycle.duration_minutes == 45
        assert cycle.interval_minutes == 180

    def test_cwu_heavy_constant_weather(self) -> None:
        """cwu_heavy has constant T_out=-5C."""
        s = cwu_heavy()
        p0 = s.weather.get(0.0)
        p500 = s.weather.get(500.0)
        assert p0.T_out == pytest.approx(-5.0)
        assert p500.T_out == pytest.approx(-5.0)

    def test_cwu_heavy_duration_24h(self) -> None:
        """cwu_heavy lasts 24h (1440 minutes)."""
        assert cwu_heavy().duration_minutes == 1440

    # -- dew_point_stress ------------------------------------------------------

    def test_dew_point_stress_name(self) -> None:
        """dew_point_stress scenario name is correct."""
        assert dew_point_stress().name == "dew_point_stress"

    def test_dew_point_stress_cooling_mode(self) -> None:
        """dew_point_stress uses cooling mode."""
        assert dew_point_stress().mode == "cooling"

    def test_dew_point_stress_duration_48h(self) -> None:
        """dew_point_stress lasts 48h (2880 minutes)."""
        assert dew_point_stress().duration_minutes == 2880

    def test_dew_point_stress_moderate_humidity(self) -> None:
        """dew_point_stress has constant RH=50%."""
        s = dew_point_stress()
        p0 = s.weather.get(0.0)
        p500 = s.weather.get(500.0)
        assert p0.humidity == pytest.approx(50.0)
        assert p500.humidity == pytest.approx(50.0)

    def test_dew_point_stress_t_out_around_35(self) -> None:
        """dew_point_stress has T_out baseline=35C."""
        s = dew_point_stress()
        p0 = s.weather.get(0.0)
        assert p0.T_out == pytest.approx(35.0)

    def test_dew_point_stress_in_scenario_library(self) -> None:
        """dew_point_stress is registered in SCENARIO_LIBRARY."""
        assert "dew_point_stress" in SCENARIO_LIBRARY

    def test_dew_point_stress_modern_bungalow_building(self) -> None:
        """dew_point_stress uses modern_bungalow_with_splits building (13 rooms)."""
        s = dew_point_stress()
        assert len(s.building.rooms) == 13

    def test_dew_point_stress_setpoint_25(self) -> None:
        """dew_point_stress setpoint is 25C."""
        assert dew_point_stress().controller.setpoint == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# TestParametricSweeps — sweep construction and consistency
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParametricSweeps:
    """Tests for parametric sweep generators."""

    def test_insulation_sweep_returns_3_scenarios(self) -> None:
        """insulation_sweep returns exactly 3 scenarios."""
        scenarios = insulation_sweep()
        assert len(scenarios) == 3

    def test_screed_sweep_returns_3_scenarios(self) -> None:
        """screed_sweep returns exactly 3 scenarios."""
        scenarios = screed_sweep()
        assert len(scenarios) == 3

    @pytest.mark.parametrize("sweep_name", list(PARAMETRIC_SWEEPS.keys()))
    def test_sweep_all_valid(self, sweep_name: str) -> None:
        """Every scenario in every sweep is a valid SimScenario."""
        scenarios = PARAMETRIC_SWEEPS[sweep_name]()
        for s in scenarios:
            assert isinstance(s, SimScenario)

    @pytest.mark.parametrize("sweep_name", list(PARAMETRIC_SWEEPS.keys()))
    def test_sweep_deterministic(self, sweep_name: str) -> None:
        """Parametric sweeps are deterministic."""
        a = PARAMETRIC_SWEEPS[sweep_name]()
        b = PARAMETRIC_SWEEPS[sweep_name]()
        assert len(a) == len(b)
        for sa, sb in zip(a, b, strict=False):
            assert sa.name == sb.name
            assert sa.building == sb.building
            assert sa.controller == sb.controller
            assert sa.duration_minutes == sb.duration_minutes
            assert sa.mode == sb.mode
            assert sa.description == sb.description
            # Compare weather output at multiple time points
            for t in [0.0, 100.0, 500.0]:
                pa = sa.weather.get(t)
                pb = sb.weather.get(t)
                assert pa == pb, f"Weather mismatch at t={t} in {sa.name}"

    @pytest.mark.parametrize("sweep_name", list(PARAMETRIC_SWEEPS.keys()))
    def test_sweep_unique_names(self, sweep_name: str) -> None:
        """All scenarios in a sweep have unique names."""
        scenarios = PARAMETRIC_SWEEPS[sweep_name]()
        names = [s.name for s in scenarios]
        assert len(names) == len(set(names))

    @pytest.mark.parametrize("sweep_name", list(PARAMETRIC_SWEEPS.keys()))
    def test_sweep_has_descriptions(self, sweep_name: str) -> None:
        """All scenarios in sweeps have non-empty descriptions."""
        scenarios = PARAMETRIC_SWEEPS[sweep_name]()
        for s in scenarios:
            assert s.description != ""

    def test_insulation_sweep_same_weather(self) -> None:
        """All insulation_sweep scenarios share the same weather output."""
        scenarios = insulation_sweep()
        ref = scenarios[0].weather.get(0.0)
        for s in scenarios[1:]:
            p = s.weather.get(0.0)
            assert p.T_out == pytest.approx(ref.T_out)
            assert pytest.approx(ref.GHI) == p.GHI
            assert p.wind_speed == pytest.approx(ref.wind_speed)
            assert p.humidity == pytest.approx(ref.humidity)

    def test_screed_sweep_same_weather(self) -> None:
        """All screed_sweep scenarios share the same weather output."""
        scenarios = screed_sweep()
        for t_min in [0.0, 500.0, 1000.0]:
            ref = scenarios[0].weather.get(t_min)
            for s in scenarios[1:]:
                p = s.weather.get(t_min)
                assert p.T_out == pytest.approx(ref.T_out)
                assert pytest.approx(ref.GHI) == p.GHI

    def test_insulation_sweep_different_buildings(self) -> None:
        """Insulation sweep scenarios have different building R values."""
        scenarios = insulation_sweep()
        r_wo_values = []
        for s in scenarios:
            room = s.building.rooms[0]
            r_wo = room.params.R_wo
            assert r_wo is not None
            r_wo_values.append(r_wo)
        # All three should be distinct
        assert len(set(r_wo_values)) == 3

    def test_screed_sweep_different_buildings(self) -> None:
        """Screed sweep scenarios have different building configurations."""
        scenarios = screed_sweep()
        # Compare full building params — all three should be distinct
        buildings = [s.building for s in scenarios]
        assert buildings[0] != buildings[1]
        assert buildings[1] != buildings[2]
        assert buildings[0] != buildings[2]

    def test_insulation_sweep_all_heating_mode(self) -> None:
        """All insulation_sweep scenarios use heating mode."""
        for s in insulation_sweep():
            assert s.mode == "heating"

    def test_screed_sweep_all_heating_mode(self) -> None:
        """All screed_sweep scenarios use heating mode."""
        for s in screed_sweep():
            assert s.mode == "heating"

    def test_insulation_sweep_bungalow_salon_no_split(self) -> None:
        """Insulation sweep bungalow_salon variant has no split."""
        scenarios = insulation_sweep()
        bungalow_scenarios = [s for s in scenarios if "bungalow_salon" in s.name]
        assert len(bungalow_scenarios) == 1
        room = bungalow_scenarios[0].building.rooms[0]
        assert room.has_split is False
        assert room.split_power_w == 0.0

    def test_screed_sweep_bungalow_salon_no_split(self) -> None:
        """Screed sweep bungalow_salon variant has no split."""
        scenarios = screed_sweep()
        bungalow_scenarios = [s for s in scenarios if "bungalow_salon" in s.name]
        assert len(bungalow_scenarios) == 1
        room = bungalow_scenarios[0].building.rooms[0]
        assert room.has_split is False
        assert room.split_power_w == 0.0

    def test_total_scenario_count_at_least_10(self) -> None:
        """Total scenario count (single + sweep) is at least 10."""
        total = len(SCENARIO_LIBRARY)
        for gen in PARAMETRIC_SWEEPS.values():
            total += len(gen())
        assert total >= 10

    def test_bathroom_heater_registered(self) -> None:
        """bathroom_heater and bathroom_heater_cooling are in the library."""
        assert "bathroom_heater" in SCENARIO_LIBRARY
        assert "bathroom_heater_cooling" in SCENARIO_LIBRARY
        heating = bathroom_heater()
        assert heating.name == "bathroom_heater"
        assert heating.mode == "heating"
        assert heating.duration_minutes == 2880
        assert "lazienka" in heating.room_overrides
        assert heating.room_overrides["lazienka"].setpoint == 24.0
        lazienka = next(r for r in heating.building.rooms if r.name == "lazienka")
        assert lazienka.auxiliary_type == "heater"
        assert lazienka.has_split is True
        assert lazienka.split_power_w == 300.0

        cooling = bathroom_heater_cooling()
        assert cooling.mode == "cooling"
        assert "lazienka" in cooling.room_overrides


# ---------------------------------------------------------------------------
# TestSimScenarioDescription — description field on dataclass
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimScenarioDescription:
    """Tests for the SimScenario.description field."""

    def test_description_default_is_empty_string(self) -> None:
        """SimScenario description defaults to empty string."""
        weather = SyntheticWeather.constant(T_out=0.0)
        s = SimScenario(
            name="test",
            building=well_insulated(),
            weather=weather,
            controller=ControllerConfig(),
            duration_minutes=60,
        )
        assert s.description == ""

    def test_description_can_be_set(self) -> None:
        """SimScenario accepts a custom description."""
        weather = SyntheticWeather.constant(T_out=0.0)
        s = SimScenario(
            name="test",
            building=well_insulated(),
            weather=weather,
            controller=ControllerConfig(),
            duration_minutes=60,
            description="My test scenario",
        )
        assert s.description == "My test scenario"

    def test_description_is_frozen(self) -> None:
        """SimScenario.description cannot be reassigned (frozen)."""
        weather = SyntheticWeather.constant(T_out=0.0)
        s = SimScenario(
            name="test",
            building=well_insulated(),
            weather=weather,
            controller=ControllerConfig(),
            duration_minutes=60,
            description="original",
        )
        with pytest.raises(AttributeError):
            s.description = "changed"  # type: ignore[misc]

    def test_backward_compatibility_without_description(self) -> None:
        """Existing code that omits description still works."""
        weather = SyntheticWeather.constant(T_out=0.0)
        # This should not raise
        s = SimScenario(
            name="legacy",
            building=well_insulated(),
            weather=weather,
            controller=ControllerConfig(),
            duration_minutes=120,
            mode="heating",
            dt_seconds=60.0,
            cwu_schedule=(),
            sensor_noise_std=0.0,
        )
        assert s.description == ""


# ---------------------------------------------------------------------------
# TestExports — importability from pumpahead
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExports:
    """Tests for module-level exports and __init__.py re-exports."""

    def test_scenario_library_importable_from_init(self) -> None:
        """SCENARIO_LIBRARY is importable from pumpahead."""
        from pumpahead import SCENARIO_LIBRARY as sl

        assert len(sl) >= 8

    def test_parametric_sweeps_importable_from_init(self) -> None:
        """PARAMETRIC_SWEEPS is importable from pumpahead."""
        from pumpahead import PARAMETRIC_SWEEPS as ps

        assert len(ps) >= 2

    def test_factory_functions_importable_from_init(self) -> None:
        """All scenario factory functions are importable from pumpahead."""
        from pumpahead import (
            cold_snap as cs,
        )
        from pumpahead import (
            cwu_heavy as ch,
        )
        from pumpahead import (
            dew_point_stress as dps,
        )
        from pumpahead import (
            extreme_cold as ec,
        )
        from pumpahead import (
            full_year_2025 as fy,
        )
        from pumpahead import (
            hot_july as hj,
        )
        from pumpahead import (
            insulation_sweep as isw,
        )
        from pumpahead import (
            rapid_warming as rw,
        )
        from pumpahead import (
            screed_sweep as ssw,
        )
        from pumpahead import (
            solar_overshoot as so,
        )
        from pumpahead import (
            steady_state as ss,
        )

        # Verify all are callable
        for fn in [ss, cs, hj, so, fy, ec, rw, ch, isw, ssw, dps]:
            assert callable(fn)

    def test_all_symbols_in_init_all(self) -> None:
        """All new symbols appear in pumpahead.__all__."""
        import pumpahead

        expected = [
            "SCENARIO_LIBRARY",
            "PARAMETRIC_SWEEPS",
            "steady_state",
            "cold_snap",
            "hot_july",
            "solar_overshoot",
            "full_year_2025",
            "extreme_cold",
            "rapid_warming",
            "cwu_heavy",
            "insulation_sweep",
            "screed_sweep",
            "dew_point_stress",
        ]
        for sym in expected:
            assert sym in pumpahead.__all__, f"{sym} missing from __all__"

    def test_scenarios_importable_from_scenarios_module(self) -> None:
        """All symbols are importable directly from pumpahead.scenarios."""
        from pumpahead.scenarios import (  # noqa: F401
            PARAMETRIC_SWEEPS,
            SCENARIO_LIBRARY,
            cold_snap,
            cwu_heavy,
            dew_point_stress,
            extreme_cold,
            full_year_2025,
            hot_july,
            insulation_sweep,
            rapid_warming,
            screed_sweep,
            solar_overshoot,
            steady_state,
        )
