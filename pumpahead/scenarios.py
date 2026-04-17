"""Simulation scenario library for PumpAhead.

Central catalog of deterministic simulation scenarios covering heating,
cooling, auto mode, edge cases, and parametric sweeps.  Each factory
function returns a fully configured ``SimScenario`` ready for use with
``BuildingSimulator``.

All scenarios use ``SyntheticWeather`` profiles (no external data) so
that results are perfectly reproducible.

Structure mirrors ``pumpahead.building_profiles``:
    * Individual factory functions returning ``SimScenario`` instances.
    * ``SCENARIO_LIBRARY`` — registry mapping name to factory callable.
    * ``PARAMETRIC_SWEEPS`` — registry for sweep generators returning
      ``list[SimScenario]``.

Usage::

    from pumpahead.scenarios import steady_state, SCENARIO_LIBRARY

    scenario = steady_state()
    assert scenario.name == "steady_state"

    # Or via the lookup dict:
    factory = SCENARIO_LIBRARY["cold_snap"]
    scenario = factory()
"""

from __future__ import annotations

from collections.abc import Callable

from pumpahead.building_profiles import (
    heavy_construction,
    leaky_old_house,
    modern_bungalow,
    modern_bungalow_with_bathroom_heater,
    modern_bungalow_with_splits,
    thin_screed,
    well_insulated,
)
from pumpahead.config import (
    BuildingParams,
    ControllerConfig,
    RoomConfig,
    SimScenario,
)
from pumpahead.cwu_coordinator import CWU_HEAVY
from pumpahead.weather import ChannelProfile, ProfileKind, SyntheticWeather
from pumpahead.weather_comp import WeatherCompCurve

__all__ = [
    "PARAMETRIC_SWEEPS",
    "SCENARIO_LIBRARY",
    "bathroom_heater",
    "bathroom_heater_cooling",
    "cold_snap",
    "cold_snap_weather_comp",
    "cwu_heavy",
    "cwu_with_splits",
    "dew_point_stress",
    "dual_source_cold_snap",
    "dual_source_cooling_steady",
    "dual_source_steady_state",
    "extreme_cold",
    "full_year_2025",
    "hot_july",
    "insulation_sweep",
    "priority_inversion_stress",
    "rapid_warming",
    "screed_sweep",
    "solar_overshoot",
    "spring_transition",
    "steady_state",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _modern_bungalow_single_room() -> BuildingParams:
    """Extract the first room (salon) from modern_bungalow as a single-room building.

    The room is modified to have ``has_split=False`` and ``split_power_w=0.0``
    to keep parametric comparisons fair across single-room profiles.

    Returns:
        Validated ``BuildingParams`` with 1 room (salon, no split).
    """
    building = modern_bungalow()
    salon = next(r for r in building.rooms if r.name == "salon")
    # Rebuild RCParams without split capability
    from pumpahead.model import RCParams

    params_no_split = RCParams(
        C_air=salon.params.C_air,
        C_slab=salon.params.C_slab,
        C_wall=salon.params.C_wall,
        R_sf=salon.params.R_sf,
        R_wi=salon.params.R_wi,
        R_wo=salon.params.R_wo,
        R_ve=salon.params.R_ve,
        R_ins=salon.params.R_ins,
        f_conv=salon.params.f_conv,
        f_rad=salon.params.f_rad,
        T_ground=salon.params.T_ground,
        has_split=False,
    )
    salon_no_split = RoomConfig(
        name=salon.name,
        area_m2=salon.area_m2,
        params=params_no_split,
        windows=salon.windows,
        has_split=False,
        split_power_w=0.0,
        ufh_loops=salon.ufh_loops,
        pipe_length_m=salon.pipe_length_m,
        pipe_spacing_m=salon.pipe_spacing_m,
        pipe_diameter_outer_mm=salon.pipe_diameter_outer_mm,
        pipe_wall_thickness_mm=salon.pipe_wall_thickness_mm,
        q_int_w=salon.q_int_w,
    )
    return BuildingParams(
        rooms=(salon_no_split,),
        hp_max_power_w=7000.0,
        latitude=50.69,
        longitude=17.38,
    )


# ---------------------------------------------------------------------------
# Single-scenario factory functions
# ---------------------------------------------------------------------------


def steady_state() -> SimScenario:
    """Steady-state heating at constant outdoor temperature.

    Constant T_out=0C, no solar, no wind.  Tests that the controller
    stabilises room temperature around setpoint within +/-0.3C.

    Returns:
        ``SimScenario`` with ``well_insulated`` building, 48h duration.
    """
    weather = SyntheticWeather.constant(
        T_out=0.0,
        GHI=0.0,
        wind_speed=0.0,
        humidity=50.0,
    )
    return SimScenario(
        name="steady_state",
        building=well_insulated(),
        weather=weather,
        controller=ControllerConfig(setpoint=21.0),
        duration_minutes=2880,
        mode="heating",
        dt_seconds=60.0,
        description=(
            "Steady-state heating at T_out=0C, no solar. "
            "Tests temperature stabilization within +/-0.3C."
        ),
    )


def cold_snap() -> SimScenario:
    """Step drop from 0C to -15C after 24h.

    Multi-room scenario using ``modern_bungalow`` building.  Tests split
    entry/exit logic and UFH takeover under severe cold.

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 5-day duration.
    """
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
        name="cold_snap",
        building=modern_bungalow(),
        weather=weather,
        controller=ControllerConfig(setpoint=21.0),
        duration_minutes=7200,
        mode="heating",
        dt_seconds=60.0,
        description=(
            "Step drop from 0C to -15C after 24h. "
            "Tests split entry/exit and UFH takeover."
        ),
    )


def cold_snap_weather_comp() -> SimScenario:
    """Step drop from 0C to -15C after 24h with a realistic HP heating curve.

    Mirrors the :func:`cold_snap` weather profile (baseline 0 C, amplitude
    -15 C, step at t=1440 min, constant GHI=0, wind=2, humidity=60) but
    exercises the weather-compensation curve introduced in #141 and wired
    in #143.  The curve uses ``t_supply_base=35`` C, ``slope=0.4``,
    ``t_neutral=0`` C, ``t_supply_max=55`` C, ``t_supply_min=25`` C, giving
    ~41 C supply at the -15 C cold peak (35 + 0.4 * 15).

    Uses the ``modern_bungalow`` building (7 kW HP, 8 rooms, salon has
    splits).  Duration is 48 h so the second 24 h exercises the peak
    supply temperature.

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 48 h duration,
        heating mode, and a configured ``WeatherCompCurve``.
    """
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
    curve = WeatherCompCurve(
        t_supply_base=35.0,
        slope=0.4,
        t_neutral=0.0,
        t_supply_max=55.0,
        t_supply_min=25.0,
    )
    return SimScenario(
        name="cold_snap_weather_comp",
        building=modern_bungalow(),
        weather=weather,
        controller=ControllerConfig(setpoint=21.0),
        duration_minutes=2880,
        mode="heating",
        dt_seconds=60.0,
        weather_comp=curve,
        description=(
            "Step drop from 0C to -15C after 24h with realistic HP "
            "heating curve (base=35C, slope=0.4, neutral=0C). "
            "Tests weather-compensation under severe cold."
        ),
    )


def hot_july() -> SimScenario:
    """Simulated hot July with daily temperature and solar cycles.

    Sinusoidal T_out (mean 30C, amplitude 5C) and GHI (mean 400, amplitude
    400) with a 24h period.  Tests cooling mode over a full month.

    Returns:
        ``SimScenario`` with ``well_insulated`` building, 31-day duration.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=30.0,
            amplitude=5.0,
            period_minutes=1440.0,
        ),
        ghi=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=400.0,
            amplitude=400.0,
            period_minutes=1440.0,
        ),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=1.0),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=50.0),
    )
    return SimScenario(
        name="hot_july",
        building=well_insulated(),
        weather=weather,
        controller=ControllerConfig(setpoint=25.0),
        duration_minutes=44640,
        mode="cooling",
        dt_seconds=60.0,
        description=(
            "Simulated hot July with daily temp cycle (25-35C) and solar "
            "gains. Tests cooling mode."
        ),
    )


def solar_overshoot() -> SimScenario:
    """March-like conditions with strong solar gains on south windows.

    Sinusoidal T_out (mean 5C, amplitude 8C) and GHI (mean 250,
    amplitude 250) with a 24h period.  Tests overshoot prevention
    in auto mode.

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 3-day duration.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=5.0,
            amplitude=8.0,
            period_minutes=1440.0,
        ),
        ghi=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=250.0,
            amplitude=250.0,
            period_minutes=1440.0,
        ),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=1.5),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=55.0),
    )
    return SimScenario(
        name="solar_overshoot",
        building=modern_bungalow(),
        weather=weather,
        controller=ControllerConfig(setpoint=22.0),
        duration_minutes=4320,
        mode="auto",
        dt_seconds=60.0,
        description=(
            "March-like conditions with strong solar gains on south "
            "windows. Tests overshoot prevention."
        ),
    )


def full_year_2025() -> SimScenario:
    """Full-year simulation with annual temperature and solar cycles.

    Sinusoidal T_out (baseline 10C, amplitude 15C, period 365 days)
    and GHI (baseline 200, amplitude 200, same period).  Tests the
    controller across all seasonal transitions.

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 365-day duration.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=10.0,
            amplitude=15.0,
            period_minutes=525600.0,
        ),
        ghi=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=200.0,
            amplitude=200.0,
            period_minutes=525600.0,
        ),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=2.0),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=55.0),
    )
    return SimScenario(
        name="full_year_2025",
        building=modern_bungalow(),
        weather=weather,
        controller=ControllerConfig(setpoint=22.0),
        duration_minutes=525600,
        mode="auto",
        dt_seconds=60.0,
        description=(
            "Full-year simulation (365 days, 525600 steps). "
            "Annual temperature cycle -5C to 25C."
        ),
    )


def extreme_cold() -> SimScenario:
    """Extreme cold (-20C) with high wind on a leaky building.

    Constant T_out=-20C, wind 5 m/s, no solar.  Edge case that tests
    maximum heating demand on a poorly insulated building.

    Returns:
        ``SimScenario`` with ``leaky_old_house`` building, 3-day duration.
    """
    weather = SyntheticWeather.constant(
        T_out=-20.0,
        GHI=0.0,
        wind_speed=5.0,
        humidity=70.0,
    )
    return SimScenario(
        name="extreme_cold",
        building=leaky_old_house(),
        weather=weather,
        controller=ControllerConfig(setpoint=21.0),
        duration_minutes=4320,
        mode="heating",
        dt_seconds=60.0,
        description=(
            "Extreme cold (-20C) with high wind on a leaky building. "
            "Edge case for max heating demand."
        ),
    )


def rapid_warming() -> SimScenario:
    """Rapid outdoor temperature rise from -10C to +15C over 12h.

    Ramp T_out from -10C to +15C over 720 minutes, then constant.
    GHI ramps from 0 to 500 over the same period.  Tests mode
    transition from heating to off/cooling.

    Returns:
        ``SimScenario`` with ``well_insulated`` building, 48h duration.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.RAMP,
            baseline=-10.0,
            amplitude=25.0,
            period_minutes=720.0,
        ),
        ghi=ChannelProfile(
            kind=ProfileKind.RAMP,
            baseline=0.0,
            amplitude=500.0,
            period_minutes=720.0,
        ),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=1.0),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=50.0),
    )
    return SimScenario(
        name="rapid_warming",
        building=well_insulated(),
        weather=weather,
        controller=ControllerConfig(setpoint=22.0),
        duration_minutes=2880,
        mode="auto",
        dt_seconds=60.0,
        description=(
            "Rapid outdoor temp rise from -10C to +15C over 12h. "
            "Tests mode transition from heating to off/cooling."
        ),
    )


def cwu_heavy() -> SimScenario:
    """Heavy CWU schedule at -5C outdoor temperature.

    CWU cycle: 45 minutes every 3 hours starting at t=0.  Tests
    UFH recovery after repeated heat pump interruptions for
    domestic hot water production.

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 24h duration.
    """
    weather = SyntheticWeather.constant(
        T_out=-5.0,
        GHI=0.0,
        wind_speed=1.0,
        humidity=60.0,
    )
    return SimScenario(
        name="cwu_heavy",
        building=modern_bungalow(),
        weather=weather,
        controller=ControllerConfig(setpoint=21.0),
        duration_minutes=1440,
        mode="heating",
        dt_seconds=60.0,
        cwu_schedule=CWU_HEAVY,
        description=(
            "Heavy CWU schedule (45 min every 3h) at -5C. "
            "Tests UFH recovery after repeated HP interruptions."
        ),
    )


def cwu_with_splits() -> SimScenario:
    """Heavy CWU schedule with split-equipped rooms at -5C.

    Combines the ``modern_bungalow`` multi-room building (which has
    split-equipped rooms) with a heavy CWU schedule.  Primary test
    scenario for verifying anti-panic logic: splits should NOT
    activate during CWU cycles when T_room is close to setpoint.

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 24h duration,
        CWU_HEAVY schedule.
    """
    weather = SyntheticWeather.constant(
        T_out=-5.0,
        GHI=0.0,
        wind_speed=1.0,
        humidity=60.0,
    )
    return SimScenario(
        name="cwu_with_splits",
        building=modern_bungalow_with_splits(),
        weather=weather,
        controller=ControllerConfig(
            kp=5.0,
            ki=0.01,
            setpoint=21.0,
            split_deadband=1.0,
            valve_floor_pct=15.0,
        ),
        duration_minutes=1440,
        mode="heating",
        dt_seconds=60.0,
        cwu_schedule=CWU_HEAVY,
        description=(
            "Heavy CWU schedule (45 min every 3h) at -5C with splits. "
            "Tests anti-panic logic: no false-alarm split activations "
            "during CWU when T_room > setpoint - 1.0 degC."
        ),
    )


# ---------------------------------------------------------------------------
# Dual-source (UFH + split) scenario factory functions
# ---------------------------------------------------------------------------


def dual_source_steady_state() -> SimScenario:
    """Steady-state dual-source heating at constant T_out=0C.

    Uses ``modern_bungalow`` building (5 rooms with splits, 3 without).
    Constant outdoor temperature, no solar.  Tests that split runtime
    stays below 15% in the second half (after warmup) and UFH-only
    rooms are unaffected.

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 72h duration.
    """
    weather = SyntheticWeather.constant(
        T_out=0.0,
        GHI=0.0,
        wind_speed=0.0,
        humidity=50.0,
    )
    return SimScenario(
        name="dual_source_steady_state",
        building=modern_bungalow_with_splits(),
        weather=weather,
        controller=ControllerConfig(
            kp=5.0,
            ki=0.01,
            setpoint=21.0,
            split_deadband=1.5,
            valve_floor_pct=15.0,
        ),
        duration_minutes=4320,
        mode="heating",
        dt_seconds=60.0,
        description=(
            "Steady-state dual-source heating at T_out=0C. "
            "Tests split runtime < 15% and no regression in UFH-only rooms."
        ),
    )


def dual_source_cold_snap() -> SimScenario:
    """Step drop from 0C to -15C at t=1440 for dual-source rooms.

    Uses ``modern_bungalow_with_splits`` with HP intentionally undersized
    to ~3.5 kW so the heat pump cannot fully cover the design load on its
    own and splits must contribute during the cold snap.  This exercises
    the split-entry branch of the coordinator.

    Returns:
        ``SimScenario`` with undersized-HP building, 5-day duration.
    """
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
    base = modern_bungalow_with_splits()
    building = BuildingParams(
        rooms=base.rooms,
        hp_max_power_w=3500.0,
        latitude=base.latitude,
        longitude=base.longitude,
    )
    return SimScenario(
        name="dual_source_cold_snap",
        building=building,
        weather=weather,
        controller=ControllerConfig(
            kp=5.0,
            ki=0.01,
            setpoint=21.0,
            split_deadband=1.0,
        ),
        duration_minutes=7200,
        mode="heating",
        dt_seconds=60.0,
        description=(
            "Step drop from 0C to -15C at t=1440 min with undersized HP. "
            "Tests split entry during cold snap and UFH takeover."
        ),
    )


def priority_inversion_stress() -> SimScenario:
    """Extreme cold stress test for anti-takeover logic.

    Uses ``modern_bungalow`` building with aggressive controller gains
    and intentionally low valve floor.  Step T_out from 0C to -20C
    at t=720 min.  Tests that even under stress, priority inversion
    does not occur.

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 3-day duration.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.STEP,
            baseline=0.0,
            amplitude=-20.0,
            step_time_minutes=720.0,
        ),
        ghi=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=0.0),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=3.0),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=60.0),
    )
    return SimScenario(
        name="priority_inversion_stress",
        building=modern_bungalow_with_splits(),
        weather=weather,
        controller=ControllerConfig(
            kp=10.0,
            ki=0.005,
            setpoint=21.0,
            valve_floor_pct=5.0,
            split_deadband=1.0,
        ),
        duration_minutes=4320,
        mode="heating",
        dt_seconds=60.0,
        description=(
            "Extreme cold stress (-20C step at t=720) with low valve "
            "floor. Tests anti-takeover prevents priority inversion."
        ),
    )


def dual_source_cooling_steady() -> SimScenario:
    """Steady-state cooling with dual-source rooms at T_out=32C.

    Uses ``modern_bungalow`` building (5 rooms with splits, 3 without).
    Constant high outdoor temperature, moderate solar gains.  Tests
    that cooling mode produces negative Q_floor, splits cool correctly,
    and splits NEVER heat in cooling mode (Axiom #3).

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 7-day duration.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=32.0,
            amplitude=4.0,
            period_minutes=1440.0,
        ),
        ghi=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=350.0,
            amplitude=350.0,
            period_minutes=1440.0,
        ),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=1.0),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=50.0),
    )
    return SimScenario(
        name="dual_source_cooling_steady",
        building=modern_bungalow_with_splits(),
        weather=weather,
        controller=ControllerConfig(
            kp=5.0,
            ki=0.01,
            setpoint=25.0,
            split_deadband=1.0,
        ),
        duration_minutes=10080,
        mode="cooling",
        dt_seconds=60.0,
        description=(
            "Steady-state dual-source cooling at T_out~32C with solar. "
            "Tests negative Q_floor and Axiom #3 compliance."
        ),
    )


def dew_point_stress() -> SimScenario:
    """Dew point stress test with hot outdoor and moderate humidity.

    Constant RH=50%, T_out~35C (sinusoidal, amplitude 5C), strong solar.
    At T_air~24C and RH=50%, Magnus gives T_dew=12.9C, so the
    condensation safety margin (T_dew + 2 = 14.9C) is tight against
    floor equilibrium (~16-17C) which is pulled down by T_ground=10C.

    The scenario stresses the cooling throttle by combining extreme
    outdoor heat (up to 40C) with enough humidity to keep T_dew + 2
    within 2-3C of the floor equilibrium.  The controller must
    throttle cooling to prevent floor overcooling.

    Uses ``modern_bungalow`` building (5 rooms with splits, 3 without).

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 48h duration,
        cooling mode.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=35.0,
            amplitude=5.0,
            period_minutes=1440.0,
        ),
        ghi=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=400.0,
            amplitude=400.0,
            period_minutes=1440.0,
        ),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=1.0),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=50.0),
    )
    return SimScenario(
        name="dew_point_stress",
        building=modern_bungalow_with_splits(),
        weather=weather,
        controller=ControllerConfig(setpoint=25.0, split_deadband=0.5),
        duration_minutes=2880,
        mode="cooling",
        dt_seconds=60.0,
        description=(
            "Dew point stress: RH=50%, T_out~35C (amp=5C), setpoint=25C. "
            "Tests condensation protection with tight dew-point margins "
            "under extreme outdoor heat."
        ),
    )


def spring_transition() -> SimScenario:
    """Spring transition scenario with auto mode switching.

    Ramp T_out from 5C to 28C over 5 days.  Tests the ModeController's
    hysteresis: system should switch from HEATING to COOLING once the
    outdoor temperature crosses the cooling threshold and the minimum
    hold time is satisfied.

    Returns:
        ``SimScenario`` with ``modern_bungalow`` building, 7-day duration.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.RAMP,
            baseline=5.0,
            amplitude=23.0,
            period_minutes=7200.0,
        ),
        ghi=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=200.0,
            amplitude=200.0,
            period_minutes=1440.0,
        ),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=1.5),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=55.0),
    )
    return SimScenario(
        name="spring_transition",
        building=modern_bungalow(),
        weather=weather,
        controller=ControllerConfig(
            kp=5.0,
            ki=0.01,
            setpoint=22.0,
        ),
        duration_minutes=10080,
        mode="auto",
        dt_seconds=60.0,
        description=(
            "Spring transition: ramp T_out 5C->28C over 5 days. "
            "Tests auto mode switching with hysteresis."
        ),
    )


# ---------------------------------------------------------------------------
# Bathroom heater (heating-only auxiliary) scenarios
# ---------------------------------------------------------------------------


def bathroom_heater() -> SimScenario:
    """Bathroom with a 300 W electric heater tracking 24 °C in heating mode.

    Uses ``modern_bungalow_with_bathroom_heater`` — identical envelope to
    ``modern_bungalow`` but ``lazienka`` gains a heating-only 300 W
    resistive heater (``auxiliary_type="heater"``).  The rest of the house
    targets 20 °C while ``lazienka`` gets a per-room override setpoint of
    24 °C.  Tests:

    * The bathroom reaches its 24 °C setpoint within a comfort band of
      0.7 °C in the second 24 h.
    * The heater activates (``split_runtime > 0``) but stays well below
      the anti-takeover threshold.
    * No priority inversion, no opposing action, floor temperature safe.

    Returns:
        ``SimScenario`` with ``modern_bungalow_with_bathroom_heater``
        building, 48 h heating duration at T_out=-5 °C.
    """
    weather = SyntheticWeather.constant(
        T_out=-5.0,
        GHI=0.0,
        wind_speed=1.0,
        humidity=60.0,
    )
    base_controller = ControllerConfig(
        kp=5.0,
        ki=0.01,
        setpoint=20.0,
        split_deadband=0.5,
    )
    bathroom_override = ControllerConfig(
        kp=5.0,
        ki=0.01,
        setpoint=24.0,
        split_deadband=0.5,
    )
    return SimScenario(
        name="bathroom_heater",
        building=modern_bungalow_with_bathroom_heater(),
        weather=weather,
        controller=base_controller,
        duration_minutes=2880,
        mode="heating",
        dt_seconds=60.0,
        room_overrides={"lazienka": bathroom_override},
        description=(
            "Bathroom with 300 W electric heater tracking 24 C at "
            "T_out=-5 C. Other rooms at 20 C.  Tests heater activation "
            "in heating mode and Axiom #3 compliance."
        ),
    )


def bathroom_heater_cooling() -> SimScenario:
    """Bathroom heater must be passive in cooling mode.

    Same building as ``bathroom_heater`` but with a hot sinusoidal
    outdoor profile (T_out baseline 30 °C, amplitude 5 °C, 24 h period)
    and the system in cooling mode.  The bathroom keeps its 24 °C
    override setpoint (below the 25 °C house-wide target) so an
    unconstrained coordinator would try to cool it — but the heater
    has no cooling capability, so the controller must force
    ``SplitMode.OFF`` (enforced via ``auxiliary_type="heater"``).
    Tests:

    * ``split_mode`` is ``OFF`` at every step for ``lazienka``.
    * ``assert_no_opposing_action`` passes (heater never cools).

    Returns:
        ``SimScenario`` with ``modern_bungalow_with_bathroom_heater``
        building, 48 h cooling duration.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=30.0,
            amplitude=5.0,
            period_minutes=1440.0,
        ),
        ghi=ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=300.0,
            amplitude=300.0,
            period_minutes=1440.0,
        ),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=1.0),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=50.0),
    )
    base_controller = ControllerConfig(
        kp=5.0,
        ki=0.01,
        setpoint=25.0,
        split_deadband=0.5,
    )
    bathroom_override = ControllerConfig(
        kp=5.0,
        ki=0.01,
        setpoint=24.0,
        split_deadband=0.5,
    )
    return SimScenario(
        name="bathroom_heater_cooling",
        building=modern_bungalow_with_bathroom_heater(),
        weather=weather,
        controller=base_controller,
        duration_minutes=2880,
        mode="cooling",
        dt_seconds=60.0,
        room_overrides={"lazienka": bathroom_override},
        description=(
            "Bathroom heater in cooling mode (T_out~30 C).  Tests that "
            "the controller forces SplitMode.OFF for heater rooms "
            "regardless of error (Axiom #3)."
        ),
    )


# ---------------------------------------------------------------------------
# Parametric sweep functions
# ---------------------------------------------------------------------------


def insulation_sweep() -> list[SimScenario]:
    """Parametric sweep across insulation levels.

    Three scenarios with identical weather (constant T_out=-10C) and
    heating mode, but different buildings:
        1. ``well_insulated`` — modern passive-house-like
        2. ``modern_bungalow`` salon (single room) — moderate insulation
        3. ``leaky_old_house`` — poorly insulated pre-1970s

    Returns:
        List of 3 ``SimScenario`` instances for cross-comparison.
    """
    weather = SyntheticWeather.constant(
        T_out=-10.0,
        GHI=0.0,
        wind_speed=2.0,
        humidity=60.0,
    )
    controller = ControllerConfig(setpoint=21.0)
    duration = 2880  # 48h

    profiles: list[tuple[str, BuildingParams]] = [
        ("well_insulated", well_insulated()),
        ("bungalow_salon", _modern_bungalow_single_room()),
        ("leaky_old_house", leaky_old_house()),
    ]

    return [
        SimScenario(
            name=f"insulation_sweep_{label}",
            building=building,
            weather=weather,
            controller=controller,
            duration_minutes=duration,
            mode="heating",
            dt_seconds=60.0,
            description=(
                f"Insulation sweep: {label} at T_out=-10C. "
                "Compares heating performance across insulation levels."
            ),
        )
        for label, building in profiles
    ]


def screed_sweep() -> list[SimScenario]:
    """Parametric sweep across screed thicknesses.

    Three scenarios with identical weather (step T_out from 0 to -15C
    at t=720 min) and heating mode, but different slab mass:
        1. ``thin_screed`` — ~30 mm dry screed
        2. ``modern_bungalow`` salon (single room) — ~80 mm wet screed
        3. ``heavy_construction`` — ~120 mm concrete screed

    Returns:
        List of 3 ``SimScenario`` instances for cross-comparison.
    """
    weather = SyntheticWeather(
        t_out=ChannelProfile(
            kind=ProfileKind.STEP,
            baseline=0.0,
            amplitude=-15.0,
            step_time_minutes=720.0,
        ),
        ghi=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=0.0),
        wind_speed=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=0.0),
        humidity=ChannelProfile(kind=ProfileKind.CONSTANT, baseline=50.0),
    )
    controller = ControllerConfig(setpoint=21.0)
    duration = 4320  # 3 days

    profiles: list[tuple[str, BuildingParams]] = [
        ("thin_screed", thin_screed()),
        ("bungalow_salon", _modern_bungalow_single_room()),
        ("heavy_construction", heavy_construction()),
    ]

    return [
        SimScenario(
            name=f"screed_sweep_{label}",
            building=building,
            weather=weather,
            controller=controller,
            duration_minutes=duration,
            mode="heating",
            dt_seconds=60.0,
            description=(
                f"Screed sweep: {label} with step cold at t=720min. "
                "Compares thermal response across slab masses."
            ),
        )
        for label, building in profiles
    ]


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

SCENARIO_LIBRARY: dict[str, Callable[[], SimScenario]] = {
    "steady_state": steady_state,
    "cold_snap": cold_snap,
    "cold_snap_weather_comp": cold_snap_weather_comp,
    "hot_july": hot_july,
    "solar_overshoot": solar_overshoot,
    "full_year_2025": full_year_2025,
    "extreme_cold": extreme_cold,
    "rapid_warming": rapid_warming,
    "cwu_heavy": cwu_heavy,
    "cwu_with_splits": cwu_with_splits,
    "dual_source_steady_state": dual_source_steady_state,
    "dual_source_cold_snap": dual_source_cold_snap,
    "priority_inversion_stress": priority_inversion_stress,
    "dual_source_cooling_steady": dual_source_cooling_steady,
    "spring_transition": spring_transition,
    "dew_point_stress": dew_point_stress,
    "bathroom_heater": bathroom_heater,
    "bathroom_heater_cooling": bathroom_heater_cooling,
}
"""Mapping of scenario name to factory function (single scenarios)."""

PARAMETRIC_SWEEPS: dict[str, Callable[[], list[SimScenario]]] = {
    "insulation_sweep": insulation_sweep,
    "screed_sweep": screed_sweep,
}
"""Mapping of sweep name to generator function (returns list of scenarios)."""
