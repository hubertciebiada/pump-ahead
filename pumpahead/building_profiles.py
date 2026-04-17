"""Predefined building profiles for simulation.

Provides factory functions that return validated ``BuildingParams`` instances
with physically realistic RC parameters.  ``modern_bungalow`` is the
calibrated 13-room reference house; the remaining profiles
(``well_insulated``, ``leaky_old_house``, ``thin_screed``,
``heavy_construction``) are single-room parametric variants for sweep
studies and sanity checks.

All RC parameters follow project conventions:
    R in K/W, C in J/K, T in degC, Q in W.

Usage::

    from pumpahead.building_profiles import modern_bungalow, BUILDING_PROFILES

    building = modern_bungalow()
    assert len(building.rooms) == 13

    # Or via the lookup dict:
    factory = BUILDING_PROFILES["leaky_old_house"]
    building = factory()
"""

from __future__ import annotations

from collections.abc import Callable

from pumpahead.config import BuildingParams, RoomConfig
from pumpahead.model import RCParams
from pumpahead.solar import Orientation, WindowConfig

__all__ = [
    "BUILDING_PROFILES",
    "MODERN_BUNGALOW_ROOMS",
    "heavy_construction",
    "modern_bungalow",
    "modern_bungalow_with_bathroom_heater",
    "modern_bungalow_with_splits",
    "leaky_old_house",
    "thin_screed",
    "well_insulated",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_REF_AREA = 20.0  # Reference room area [m^2] for scaling

# Modern bungalow UFH pipe spacing [m].  The real salon loop is
# documented at 96 m of pipe in 36.28 m² ⇒ ~0.15 m centre-to-centre
# (standard residential practice).  Reused across all 13 rooms.
_MODERN_BUNGALOW_PIPE_SPACING_M: float = 0.15

# Fallback pipe spacing [m] for single-room parametric profiles
# (well_insulated, leaky_old_house, thin_screed, heavy_construction).
_SINGLE_ROOM_PIPE_SPACING_M: float = 0.20

# Defaults calibrated to a modern, heavily insulated single-storey house
# (30 cm mineral wool walls, 20 cm ceiling wool, 7 cm wet screed) so that a
# ~155 m^2 building loses ~4.5 kW at design ΔT=40 K (T_in=20, T_out=-20).


def _make_3r3c_params(
    *,
    area_m2: float,
    has_split: bool = False,
    C_air_ref: float = 60_000.0,
    C_slab_ref: float = 2_900_000.0,
    C_wall_ref: float = 1_500_000.0,
    R_sf_ref: float = 0.01,
    R_wi_ref: float = 0.04,
    R_wo_ref: float = 0.15,
    R_ve_ref: float = 0.20,
    R_ins_ref: float = 0.05,
    f_conv: float = 0.6,
    f_rad: float = 0.4,
    T_ground: float = 10.0,
) -> RCParams:
    """Build a 3R3C ``RCParams`` with area-based scaling.

    Capacitances scale proportionally to area (proxy for volume/mass).
    Resistances scale inversely (larger surfaces = lower resistance).

    Args:
        area_m2: Room floor area in m^2.
        has_split: Whether the room has a split/AC unit.
        C_air_ref: Air capacitance at ``_REF_AREA`` [J/K].
        C_slab_ref: Slab capacitance at ``_REF_AREA`` [J/K].
        C_wall_ref: Wall capacitance at ``_REF_AREA`` [J/K].
        R_sf_ref: Slab-floor resistance at ``_REF_AREA`` [K/W].
        R_wi_ref: Wall-interior resistance at ``_REF_AREA`` [K/W].
        R_wo_ref: Wall-outdoor resistance at ``_REF_AREA`` [K/W].
        R_ve_ref: Ventilation resistance at ``_REF_AREA`` [K/W].
        R_ins_ref: Insulation resistance at ``_REF_AREA`` [K/W].
        f_conv: Convective solar fraction [-].
        f_rad: Radiative solar fraction [-].
        T_ground: Ground temperature [degC].

    Returns:
        Validated ``RCParams`` instance.
    """
    scale = area_m2 / _REF_AREA
    inv_scale = _REF_AREA / area_m2
    return RCParams(
        C_air=C_air_ref * scale,
        C_slab=C_slab_ref * scale,
        C_wall=C_wall_ref * scale,
        R_sf=R_sf_ref * inv_scale,
        R_wi=R_wi_ref * inv_scale,
        R_wo=R_wo_ref * inv_scale,
        R_ve=R_ve_ref * inv_scale,
        R_ins=R_ins_ref * inv_scale,
        f_conv=f_conv,
        f_rad=f_rad,
        T_ground=T_ground,
        has_split=has_split,
    )


# ---------------------------------------------------------------------------
# modern_bungalow — single-storey reference house (13 rooms, 13 UFH loops)
# ---------------------------------------------------------------------------
#
# Calibrated against a real WT-2021-class single-storey house in southern
# Poland: ~165 m² total (~158 m² heated), 30 cm mineral-wool walls, 20 cm
# ceiling wool, 7 cm wet screed.  Heated by a 7 kW air-source heat pump
# with a 9 kW resistive backup handled by the safety layer.  No splits.
# 13 UFH loops via two distributors.  All rooms target 20 °C except the
# bathroom at 24 °C (controller-level override).
#
# Reference design heat loss: Q = 4.55 kW at design T_out = -20 °C.
# This profile is calibrated to that figure (within ~0.3 %).

_BUNGALOW_LAT = 50.69
_BUNGALOW_LON = 17.38

# Real HP rated thermal output (the 9 kW resistive backup is modelled
# separately in the safety layer, not aggregated here).
_BUNGALOW_HP_MAX_W = 7000.0

# Internal gains: 2 adults + 2 children = 4 occupants, ~80 W each, plus
# appliances allocated to the room where they live.
_Q_INT_SALON = 150.0
_Q_INT_KITCHEN = 200.0
_Q_INT_BEDROOM = 50.0
_Q_INT_CHILD = 80.0
_Q_INT_OFFICE = 120.0
_Q_INT_BATH = 30.0
_Q_INT_HALL = 20.0
_Q_INT_CLOSET = 0.0
_Q_INT_WC = 10.0
_Q_INT_ENTRY = 10.0


MODERN_BUNGALOW_ROOMS: tuple[RoomConfig, ...] = (
    # garderoba — 7.40 m^2, 1 loop, no windows
    RoomConfig(
        name="garderoba",
        area_m2=7.40,
        params=_make_3r3c_params(area_m2=7.40),
        windows=(),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_CLOSET,
    ),
    # sypialnia — 12.68 m^2, 1 loop, south window
    RoomConfig(
        name="sypialnia",
        area_m2=12.68,
        params=_make_3r3c_params(area_m2=12.68),
        windows=(
            WindowConfig(orientation=Orientation.SOUTH, area_m2=2.5, g_value=0.6),
        ),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_BEDROOM,
    ),
    # dlugi_korytarz — 12.12 m^2, 1 loop, no windows
    RoomConfig(
        name="dlugi_korytarz",
        area_m2=12.12,
        params=_make_3r3c_params(area_m2=12.12),
        windows=(),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_HALL,
    ),
    # lazienka — 8.90 m^2, 1 loop, small north window, target 24 °C
    # (controller setpoint override; structural model is the same)
    RoomConfig(
        name="lazienka",
        area_m2=8.90,
        params=_make_3r3c_params(area_m2=8.90),
        windows=(
            WindowConfig(orientation=Orientation.NORTH, area_m2=0.5, g_value=0.6),
        ),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_BATH,
    ),
    # pokoj_dziecka_1 — 14.33 m^2, 1 loop, east window
    RoomConfig(
        name="pokoj_dziecka_1",
        area_m2=14.33,
        params=_make_3r3c_params(area_m2=14.33),
        windows=(WindowConfig(orientation=Orientation.EAST, area_m2=2.0, g_value=0.6),),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_CHILD,
    ),
    # pokoj_dziecka_2 — 11.65 m^2, 1 loop, east window
    RoomConfig(
        name="pokoj_dziecka_2",
        area_m2=11.65,
        params=_make_3r3c_params(area_m2=11.65),
        windows=(WindowConfig(orientation=Orientation.EAST, area_m2=2.0, g_value=0.6),),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_CHILD,
    ),
    # korytarz_witryna — ~5 m^2, 1 loop, no windows
    RoomConfig(
        name="korytarz_witryna",
        area_m2=5.0,
        params=_make_3r3c_params(area_m2=5.0),
        windows=(),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_HALL,
    ),
    # wiatrolap — 5.05 m^2, 1 loop, north window (entry)
    RoomConfig(
        name="wiatrolap",
        area_m2=5.05,
        params=_make_3r3c_params(area_m2=5.05),
        windows=(
            WindowConfig(orientation=Orientation.NORTH, area_m2=1.0, g_value=0.6),
        ),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_ENTRY,
    ),
    # salon — 36.28 m^2, 1 loop (Obieg 1, 96 m of pipe), big S+W windows
    RoomConfig(
        name="salon",
        area_m2=36.28,
        params=_make_3r3c_params(area_m2=36.28),
        windows=(
            WindowConfig(orientation=Orientation.SOUTH, area_m2=5.0, g_value=0.6),
            WindowConfig(orientation=Orientation.WEST, area_m2=3.0, g_value=0.6),
        ),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_SALON,
    ),
    # kuchnia_jadalnia — 13.59 m^2, 1 loop (Obieg 17), east window
    RoomConfig(
        name="kuchnia_jadalnia",
        area_m2=13.59,
        params=_make_3r3c_params(area_m2=13.59),
        windows=(WindowConfig(orientation=Orientation.EAST, area_m2=2.0, g_value=0.6),),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_KITCHEN,
    ),
    # gabinet_1 — 13.0 m^2, 1 loop, north window
    RoomConfig(
        name="gabinet_1",
        area_m2=13.0,
        params=_make_3r3c_params(area_m2=13.0),
        windows=(
            WindowConfig(orientation=Orientation.NORTH, area_m2=1.5, g_value=0.6),
        ),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_OFFICE,
    ),
    # gabinet_2 — 12.62 m^2, 1 loop, north window
    RoomConfig(
        name="gabinet_2",
        area_m2=12.62,
        params=_make_3r3c_params(area_m2=12.62),
        windows=(
            WindowConfig(orientation=Orientation.NORTH, area_m2=1.5, g_value=0.6),
        ),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_OFFICE,
    ),
    # toaleta — 5.49 m^2, 1 loop (Obieg 11, tiny 4.6 m loop), no windows
    RoomConfig(
        name="toaleta",
        area_m2=5.49,
        params=_make_3r3c_params(area_m2=5.49),
        windows=(),
        pipe_spacing_m=_MODERN_BUNGALOW_PIPE_SPACING_M,
        ufh_loops=1,
        q_int_w=_Q_INT_WC,
    ),
)
"""All 13 heated rooms of the reference modern bungalow.

Total UFH loops: 13 (one per room).  No splits.
Total heated area: ~158 m² (vs ~165 m² total — 3 unheated utility rooms
not modelled).
"""


def modern_bungalow() -> BuildingParams:
    """Reference modern bungalow — 13 rooms, 13 UFH loops, no splits.

    Single-storey house calibrated to a real WT-2021-class building in
    southern Poland (lat=50.69, lon=17.38).  Heated by a 7 kW ASHP with
    9 kW resistive backup handled by the safety layer.  RC parameters
    reflect 30 cm mineral-wool walls, 20 cm ceiling wool, 7 cm wet screed.

    Returns:
        Validated ``BuildingParams`` with 13 rooms.
    """
    return BuildingParams(
        rooms=MODERN_BUNGALOW_ROOMS,
        hp_max_power_w=_BUNGALOW_HP_MAX_W,
        latitude=_BUNGALOW_LAT,
        longitude=_BUNGALOW_LON,
    )


# ---------------------------------------------------------------------------
# modern_bungalow_with_splits — fictitious dual-source variant of modern_bungalow
# ---------------------------------------------------------------------------
#
# The real house has no splits.  This profile is a parallel variant used
# only by simulation tests that exercise split coordination logic
# (Axiom #1 priority, anti-takeover, dew-point fallback to split, etc.).
# Five rooms get hypothetical splits — same names as `modern_bungalow` so
# tests can flip profiles without renaming.

_SPLIT_ROOM_NAMES_WITH_SPLITS = frozenset(
    {
        "salon",
        "sypialnia",
        "pokoj_dziecka_1",
        "pokoj_dziecka_2",
        "gabinet_1",
        "gabinet_2",
    }
)
_SPLIT_POWER_BY_ROOM = {
    "salon": 3500.0,
    "sypialnia": 2500.0,
    "pokoj_dziecka_1": 2500.0,
    "pokoj_dziecka_2": 2500.0,
    "gabinet_1": 2500.0,
    "gabinet_2": 2500.0,
}


def _add_split(room: RoomConfig) -> RoomConfig:
    """Return a copy of ``room`` with a hypothetical split installed."""
    if room.name not in _SPLIT_ROOM_NAMES_WITH_SPLITS:
        return room
    p = room.params
    params_with_split = RCParams(
        C_air=p.C_air,
        C_slab=p.C_slab,
        C_wall=p.C_wall,
        R_sf=p.R_sf,
        R_wi=p.R_wi,
        R_wo=p.R_wo,
        R_ve=p.R_ve,
        R_ins=p.R_ins,
        f_conv=p.f_conv,
        f_rad=p.f_rad,
        T_ground=p.T_ground,
        has_split=True,
    )
    return RoomConfig(
        name=room.name,
        area_m2=room.area_m2,
        params=params_with_split,
        windows=room.windows,
        has_split=True,
        split_power_w=_SPLIT_POWER_BY_ROOM[room.name],
        ufh_loops=room.ufh_loops,
        pipe_length_m=room.pipe_length_m,
        pipe_spacing_m=room.pipe_spacing_m,
        pipe_diameter_outer_mm=room.pipe_diameter_outer_mm,
        pipe_wall_thickness_mm=room.pipe_wall_thickness_mm,
        q_int_w=room.q_int_w,
    )


def modern_bungalow_with_splits() -> BuildingParams:
    """Test-only variant of ``modern_bungalow`` with hypothetical splits.

    Identical thermal envelope to ``modern_bungalow``, but six rooms (salon,
    sypialnia, both children's rooms, both offices) gain a hypothetical
    split unit.  Used exclusively by simulation scenarios that exercise
    split coordination logic; not representative of the real house.

    Returns:
        Validated ``BuildingParams`` with 13 rooms (6 with splits).
    """
    rooms = tuple(_add_split(r) for r in MODERN_BUNGALOW_ROOMS)
    return BuildingParams(
        rooms=rooms,
        hp_max_power_w=_BUNGALOW_HP_MAX_W,
        latitude=_BUNGALOW_LAT,
        longitude=_BUNGALOW_LON,
    )


# ---------------------------------------------------------------------------
# modern_bungalow_with_bathroom_heater — heating-only electric heater variant
# ---------------------------------------------------------------------------
#
# The real bathroom (lazienka) has a 300 W electric towel rail / resistive
# heater intended to cover peak heating demand when UFH alone is too slow
# to track the 24 °C setpoint against the 20 °C house-wide target.  This
# profile mirrors the real wiring: only ``lazienka`` is modified, gaining a
# ``has_split=True`` auxiliary that is actually a heating-only source
# (``auxiliary_type="heater"``).  All other rooms are identical to
# ``modern_bungalow``.


_BATHROOM_HEATER_POWER_W = 300.0


def _lazienka_with_heater(room: RoomConfig) -> RoomConfig:
    """Return a copy of ``room`` with a 300 W heating-only heater.

    Only the ``lazienka`` room is modified.  The new RoomConfig has
    ``has_split=True`` (to reuse the SplitCoordinator pipeline),
    ``split_power_w=300.0`` W, and ``auxiliary_type="heater"`` so the
    controller forces ``SplitMode.OFF`` in cooling mode (Axiom #3).
    The underlying ``RCParams`` is rebuilt with ``has_split=True``.

    Args:
        room: Source room configuration.

    Returns:
        Modified ``RoomConfig`` when ``room.name == "lazienka"``,
        otherwise returns the input unchanged.
    """
    if room.name != "lazienka":
        return room
    p = room.params
    params_with_split = RCParams(
        C_air=p.C_air,
        C_slab=p.C_slab,
        C_wall=p.C_wall,
        R_sf=p.R_sf,
        R_wi=p.R_wi,
        R_wo=p.R_wo,
        R_ve=p.R_ve,
        R_ins=p.R_ins,
        f_conv=p.f_conv,
        f_rad=p.f_rad,
        T_ground=p.T_ground,
        has_split=True,
    )
    return RoomConfig(
        name=room.name,
        area_m2=room.area_m2,
        params=params_with_split,
        windows=room.windows,
        has_split=True,
        split_power_w=_BATHROOM_HEATER_POWER_W,
        ufh_loops=room.ufh_loops,
        pipe_length_m=room.pipe_length_m,
        pipe_spacing_m=room.pipe_spacing_m,
        pipe_diameter_outer_mm=room.pipe_diameter_outer_mm,
        pipe_wall_thickness_mm=room.pipe_wall_thickness_mm,
        q_int_w=room.q_int_w,
        auxiliary_type="heater",
    )


def modern_bungalow_with_bathroom_heater() -> BuildingParams:
    """Modern bungalow variant with a 300 W electric heater in the bathroom.

    Identical thermal envelope to ``modern_bungalow``, except that
    ``lazienka`` gains a heating-only electric resistive heater
    (``auxiliary_type="heater"``, 300 W).  The heater reuses the
    ``SplitCoordinator`` pipeline but the controller forces
    ``SplitMode.OFF`` for heater rooms in cooling mode so the heater
    never opposes the HP mode (Axiom #3).

    All other 12 rooms are identical to ``modern_bungalow``.

    Returns:
        Validated ``BuildingParams`` with 13 rooms (lazienka with
        heating-only heater, all others UFH-only).
    """
    rooms = tuple(_lazienka_with_heater(r) for r in MODERN_BUNGALOW_ROOMS)
    return BuildingParams(
        rooms=rooms,
        hp_max_power_w=_BUNGALOW_HP_MAX_W,
        latitude=_BUNGALOW_LAT,
        longitude=_BUNGALOW_LON,
    )


# ---------------------------------------------------------------------------
# well_insulated — modern passive-house-like single room
# ---------------------------------------------------------------------------


def well_insulated() -> BuildingParams:
    """Well-insulated modern building — low heat loss.

    Thick walls, triple-glazed windows, mechanical ventilation with
    heat recovery.  High R values across the board.

    Returns:
        Validated ``BuildingParams`` with 1 room.
    """
    area = 20.0
    params = _make_3r3c_params(
        area_m2=area,
        has_split=False,
        C_air_ref=60_000.0,
        C_slab_ref=3_250_000.0,
        C_wall_ref=2_000_000.0,
        R_sf_ref=0.01,
        R_wi_ref=0.04,
        R_wo_ref=0.08,  # thick walls — high R
        R_ve_ref=0.10,  # MVHR — very high ventilation R
        R_ins_ref=0.02,  # thick sub-slab insulation
    )
    room = RoomConfig(
        name="main",
        area_m2=area,
        params=params,
        windows=(
            WindowConfig(orientation=Orientation.SOUTH, area_m2=3.0, g_value=0.5),
        ),
        has_split=False,
        split_power_w=0.0,
        pipe_spacing_m=_SINGLE_ROOM_PIPE_SPACING_M,
        ufh_loops=2,
        q_int_w=100.0,
    )
    return BuildingParams(
        rooms=(room,),
        hp_max_power_w=6000.0,
        latitude=50.0,
        longitude=20.0,
    )


# ---------------------------------------------------------------------------
# leaky_old_house — poorly insulated pre-1970s building
# ---------------------------------------------------------------------------


def leaky_old_house() -> BuildingParams:
    """Leaky, poorly insulated old house — high heat loss.

    Thin walls, single-glazed windows, natural ventilation with
    significant infiltration.  Low R values, especially R_wo and R_ve.

    Returns:
        Validated ``BuildingParams`` with 1 room.
    """
    area = 20.0
    params = _make_3r3c_params(
        area_m2=area,
        has_split=False,
        C_air_ref=60_000.0,
        C_slab_ref=3_250_000.0,
        C_wall_ref=1_200_000.0,
        R_sf_ref=0.01,
        R_wi_ref=0.015,
        R_wo_ref=0.012,  # thin uninsulated walls — low R
        R_ve_ref=0.008,  # leaky envelope — very low R
        R_ins_ref=0.005,  # minimal sub-slab insulation
    )
    room = RoomConfig(
        name="main",
        area_m2=area,
        params=params,
        windows=(
            WindowConfig(orientation=Orientation.SOUTH, area_m2=2.0, g_value=0.7),
            WindowConfig(orientation=Orientation.NORTH, area_m2=1.5, g_value=0.7),
        ),
        has_split=False,
        split_power_w=0.0,
        pipe_spacing_m=_SINGLE_ROOM_PIPE_SPACING_M,
        ufh_loops=2,
        q_int_w=100.0,
    )
    return BuildingParams(
        rooms=(room,),
        hp_max_power_w=12000.0,
        latitude=52.0,
        longitude=21.0,
    )


# ---------------------------------------------------------------------------
# thin_screed — low-mass floor system (e.g. 30 mm dry screed)
# ---------------------------------------------------------------------------


def thin_screed() -> BuildingParams:
    """Thin-screed building — fast thermal response, low slab mass.

    Floor system with ~30 mm dry screed instead of 80 mm wet screed.
    C_slab is roughly 40% of the standard value.  Faster to heat up
    but stores less energy.

    Returns:
        Validated ``BuildingParams`` with 1 room.
    """
    area = 20.0
    params = _make_3r3c_params(
        area_m2=area,
        has_split=False,
        C_air_ref=60_000.0,
        C_slab_ref=1_300_000.0,  # ~40% of standard 80 mm screed
        C_wall_ref=1_500_000.0,
        R_sf_ref=0.008,  # thinner slab — lower R
        R_wi_ref=0.02,
        R_wo_ref=0.03,
        R_ve_ref=0.03,
        R_ins_ref=0.01,
    )
    room = RoomConfig(
        name="main",
        area_m2=area,
        params=params,
        windows=(
            WindowConfig(orientation=Orientation.SOUTH, area_m2=2.5, g_value=0.6),
        ),
        has_split=False,
        split_power_w=0.0,
        pipe_spacing_m=_SINGLE_ROOM_PIPE_SPACING_M,
        ufh_loops=2,
        q_int_w=100.0,
    )
    return BuildingParams(
        rooms=(room,),
        hp_max_power_w=8000.0,
        latitude=50.0,
        longitude=20.0,
    )


# ---------------------------------------------------------------------------
# heavy_construction — high thermal mass (e.g. 120 mm screed + massive walls)
# ---------------------------------------------------------------------------


def heavy_construction() -> BuildingParams:
    """Heavy-construction building — high thermal mass throughout.

    Thick concrete screed (~120 mm) and massive brick/concrete walls.
    C_slab and C_wall are significantly higher than standard.  Slow
    thermal response but excellent energy storage.

    Returns:
        Validated ``BuildingParams`` with 1 room.
    """
    area = 20.0
    params = _make_3r3c_params(
        area_m2=area,
        has_split=False,
        C_air_ref=60_000.0,
        C_slab_ref=4_875_000.0,  # ~150% of standard 80 mm (120 mm screed)
        C_wall_ref=3_000_000.0,  # massive walls — double C
        R_sf_ref=0.012,  # thicker slab — slightly higher R
        R_wi_ref=0.02,
        R_wo_ref=0.035,
        R_ve_ref=0.03,
        R_ins_ref=0.012,
    )
    room = RoomConfig(
        name="main",
        area_m2=area,
        params=params,
        windows=(
            WindowConfig(orientation=Orientation.SOUTH, area_m2=2.5, g_value=0.6),
        ),
        has_split=False,
        split_power_w=0.0,
        pipe_spacing_m=_SINGLE_ROOM_PIPE_SPACING_M,
        ufh_loops=2,
        q_int_w=100.0,
    )
    return BuildingParams(
        rooms=(room,),
        hp_max_power_w=10000.0,
        latitude=50.0,
        longitude=20.0,
    )


# ---------------------------------------------------------------------------
# Profile registry
# ---------------------------------------------------------------------------

BUILDING_PROFILES: dict[str, Callable[[], BuildingParams]] = {
    "modern_bungalow": modern_bungalow,
    "modern_bungalow_with_splits": modern_bungalow_with_splits,
    "modern_bungalow_with_bathroom_heater": modern_bungalow_with_bathroom_heater,
    "well_insulated": well_insulated,
    "leaky_old_house": leaky_old_house,
    "thin_screed": thin_screed,
    "heavy_construction": heavy_construction,
}
"""Mapping of profile name to factory function."""
