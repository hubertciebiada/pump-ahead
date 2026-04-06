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
    hubert_real,
    leaky_old_house,
    thin_screed,
    well_insulated,
)
from pumpahead.config import (
    BuildingParams,
    ControllerConfig,
    CWUCycle,
    RoomConfig,
    SimScenario,
)
from pumpahead.weather import ChannelProfile, ProfileKind, SyntheticWeather

__all__ = [
    "PARAMETRIC_SWEEPS",
    "SCENARIO_LIBRARY",
    "cold_snap",
    "cwu_heavy",
    "extreme_cold",
    "full_year_2025",
    "hot_july",
    "insulation_sweep",
    "rapid_warming",
    "screed_sweep",
    "solar_overshoot",
    "steady_state",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hubert_single_room() -> BuildingParams:
    """Extract the first room (salon) from hubert_real as a single-room building.

    The room is modified to have ``has_split=False`` and ``split_power_w=0.0``
    to keep parametric comparisons fair across single-room profiles.

    Returns:
        Validated ``BuildingParams`` with 1 room (salon, no split).
    """
    building = hubert_real()
    salon = building.rooms[0]
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
        ufh_max_power_w=salon.ufh_max_power_w,
        ufh_loops=salon.ufh_loops,
        q_int_w=salon.q_int_w,
    )
    return BuildingParams(
        rooms=(salon_no_split,),
        hp_max_power_w=9000.0,
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

    Multi-room scenario using ``hubert_real`` building.  Tests split
    entry/exit logic and UFH takeover under severe cold.

    Returns:
        ``SimScenario`` with ``hubert_real`` building, 5-day duration.
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
        building=hubert_real(),
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
        ``SimScenario`` with ``hubert_real`` building, 3-day duration.
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
        building=hubert_real(),
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
        ``SimScenario`` with ``hubert_real`` building, 365-day duration.
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
        building=hubert_real(),
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
        ``SimScenario`` with ``hubert_real`` building, 24h duration.
    """
    weather = SyntheticWeather.constant(
        T_out=-5.0,
        GHI=0.0,
        wind_speed=1.0,
        humidity=60.0,
    )
    return SimScenario(
        name="cwu_heavy",
        building=hubert_real(),
        weather=weather,
        controller=ControllerConfig(setpoint=21.0),
        duration_minutes=1440,
        mode="heating",
        dt_seconds=60.0,
        cwu_schedule=(
            CWUCycle(
                start_minute=0,
                duration_minutes=45,
                interval_minutes=180,
            ),
        ),
        description=(
            "Heavy CWU schedule (45 min every 3h) at -5C. "
            "Tests UFH recovery after repeated HP interruptions."
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
        2. ``hubert_real`` salon (single room) — moderate insulation
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
        ("hubert_salon", _hubert_single_room()),
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
        2. ``hubert_real`` salon (single room) — ~80 mm wet screed
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
        ("hubert_salon", _hubert_single_room()),
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
    "hot_july": hot_july,
    "solar_overshoot": solar_overshoot,
    "full_year_2025": full_year_2025,
    "extreme_cold": extreme_cold,
    "rapid_warming": rapid_warming,
    "cwu_heavy": cwu_heavy,
}
"""Mapping of scenario name to factory function (single scenarios)."""

PARAMETRIC_SWEEPS: dict[str, Callable[[], list[SimScenario]]] = {
    "insulation_sweep": insulation_sweep,
    "screed_sweep": screed_sweep,
}
"""Mapping of sweep name to generator function (returns list of scenarios)."""
