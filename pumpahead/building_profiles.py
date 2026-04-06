"""Predefined building profiles for simulation.

Provides factory functions that return validated ``BuildingParams`` instances
with physically realistic RC parameters.  Profiles range from the author's
real house (``hubert_real``) to parametric variants for sweep studies
(``well_insulated``, ``leaky_old_house``, ``thin_screed``,
``heavy_construction``).

All RC parameters follow project conventions:
    R in K/W, C in J/K, T in degC, Q in W.

Usage::

    from pumpahead.building_profiles import hubert_real, BUILDING_PROFILES

    building = hubert_real()
    assert len(building.rooms) == 8

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
    "HUBERT_ROOMS",
    "heavy_construction",
    "hubert_real",
    "leaky_old_house",
    "thin_screed",
    "well_insulated",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_REF_AREA = 20.0  # Reference room area [m^2] for scaling


def _make_3r3c_params(
    *,
    area_m2: float,
    has_split: bool = False,
    C_air_ref: float = 60_000.0,
    C_slab_ref: float = 3_250_000.0,
    C_wall_ref: float = 1_500_000.0,
    R_sf_ref: float = 0.01,
    R_wi_ref: float = 0.02,
    R_wo_ref: float = 0.03,
    R_ve_ref: float = 0.03,
    R_ins_ref: float = 0.01,
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
# hubert_real — author's real house (8 rooms, 13 UFH loops, up to 5 splits)
# ---------------------------------------------------------------------------

# Location: Lubcza, Poland
_HUBERT_LAT = 50.69
_HUBERT_LON = 17.38

# HP: Panasonic Aquarea 9 kW (hardware-agnostic — only watts stored)
_HUBERT_HP_MAX_W = 9000.0

# Internal gains: occupancy + appliances (conservative estimate per room)
_Q_INT_LIVING = 150.0   # W — living room (TV, lights, people)
_Q_INT_KITCHEN = 200.0  # W — kitchen (fridge, cooking residual)
_Q_INT_BEDROOM = 50.0   # W — sleeping occupants
_Q_INT_OFFICE = 120.0   # W — computer + monitor
_Q_INT_CHILD = 80.0     # W — child room
_Q_INT_BATH = 30.0      # W — lights only
_Q_INT_CLOSET = 0.0     # W — unoccupied
_Q_INT_HALL = 20.0      # W — passage lights

HUBERT_ROOMS: tuple[RoomConfig, ...] = (
    # salon — 30 m^2, 2 loops, split, south + west windows
    RoomConfig(
        name="salon",
        area_m2=30.0,
        params=_make_3r3c_params(area_m2=30.0, has_split=True),
        windows=(
            WindowConfig(orientation=Orientation.SOUTH, area_m2=4.0, g_value=0.6),
            WindowConfig(orientation=Orientation.WEST, area_m2=2.5, g_value=0.6),
        ),
        has_split=True,
        split_power_w=3500.0,
        ufh_max_power_w=6000.0,
        ufh_loops=2,
        q_int_w=_Q_INT_LIVING,
    ),
    # kuchnia — 15 m^2, 2 loops, split, east window
    RoomConfig(
        name="kuchnia",
        area_m2=15.0,
        params=_make_3r3c_params(area_m2=15.0, has_split=True),
        windows=(
            WindowConfig(orientation=Orientation.EAST, area_m2=2.0, g_value=0.6),
        ),
        has_split=True,
        split_power_w=2500.0,
        ufh_max_power_w=3500.0,
        ufh_loops=2,
        q_int_w=_Q_INT_KITCHEN,
    ),
    # sypialnia — 18 m^2, 2 loops, split, south window
    RoomConfig(
        name="sypialnia",
        area_m2=18.0,
        params=_make_3r3c_params(area_m2=18.0, has_split=True),
        windows=(
            WindowConfig(orientation=Orientation.SOUTH, area_m2=2.5, g_value=0.6),
        ),
        has_split=True,
        split_power_w=2500.0,
        ufh_max_power_w=4000.0,
        ufh_loops=2,
        q_int_w=_Q_INT_BEDROOM,
    ),
    # gabinet — 12 m^2, 1 loop, split, north window
    RoomConfig(
        name="gabinet",
        area_m2=12.0,
        params=_make_3r3c_params(area_m2=12.0, has_split=True),
        windows=(
            WindowConfig(orientation=Orientation.NORTH, area_m2=1.5, g_value=0.6),
        ),
        has_split=True,
        split_power_w=2500.0,
        ufh_max_power_w=2800.0,
        ufh_loops=1,
        q_int_w=_Q_INT_OFFICE,
    ),
    # pokoj_dzieci — 14 m^2, 2 loops, split, east window
    RoomConfig(
        name="pokoj_dzieci",
        area_m2=14.0,
        params=_make_3r3c_params(area_m2=14.0, has_split=True),
        windows=(
            WindowConfig(orientation=Orientation.EAST, area_m2=2.0, g_value=0.6),
        ),
        has_split=True,
        split_power_w=2500.0,
        ufh_max_power_w=3200.0,
        ufh_loops=2,
        q_int_w=_Q_INT_CHILD,
    ),
    # lazienka — 8 m^2, 1 loop, no split, north window (small)
    RoomConfig(
        name="lazienka",
        area_m2=8.0,
        params=_make_3r3c_params(area_m2=8.0, has_split=False),
        windows=(
            WindowConfig(orientation=Orientation.NORTH, area_m2=0.5, g_value=0.6),
        ),
        has_split=False,
        split_power_w=0.0,
        ufh_max_power_w=2000.0,
        ufh_loops=1,
        q_int_w=_Q_INT_BATH,
    ),
    # garderoba — 5 m^2, 1 loop, no split, no windows
    RoomConfig(
        name="garderoba",
        area_m2=5.0,
        params=_make_3r3c_params(area_m2=5.0, has_split=False),
        windows=(),
        has_split=False,
        split_power_w=0.0,
        ufh_max_power_w=1200.0,
        ufh_loops=1,
        q_int_w=_Q_INT_CLOSET,
    ),
    # korytarz — 10 m^2, 2 loops, no split, no windows
    RoomConfig(
        name="korytarz",
        area_m2=10.0,
        params=_make_3r3c_params(area_m2=10.0, has_split=False),
        windows=(),
        has_split=False,
        split_power_w=0.0,
        ufh_max_power_w=2400.0,
        ufh_loops=2,
        q_int_w=_Q_INT_HALL,
    ),
)
"""All 8 rooms of Hubert's real house.

Total UFH loops: 2+2+2+1+2+1+1+2 = 13.
Rooms with split: salon, kuchnia, sypialnia, gabinet, pokoj_dzieci (5 of 8).
"""


def hubert_real() -> BuildingParams:
    """Hubert's real house — 8-room, 13-loop, 5-split building.

    Located in Lubcza, Poland (lat=50.69, lon=17.38).  Heated by a 9 kW
    air-source heat pump.  RC parameters use 80 mm screed, modern insulation.

    Returns:
        Validated ``BuildingParams`` with 8 rooms.
    """
    return BuildingParams(
        rooms=HUBERT_ROOMS,
        hp_max_power_w=_HUBERT_HP_MAX_W,
        latitude=_HUBERT_LAT,
        longitude=_HUBERT_LON,
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
        R_wo_ref=0.08,   # thick walls — high R
        R_ve_ref=0.10,   # MVHR — very high ventilation R
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
        ufh_max_power_w=4000.0,
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
        R_ins_ref=0.005, # minimal sub-slab insulation
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
        ufh_max_power_w=6000.0,
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
        R_sf_ref=0.008,          # thinner slab — lower R
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
        ufh_max_power_w=4000.0,
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
        R_sf_ref=0.012,          # thicker slab — slightly higher R
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
        ufh_max_power_w=5000.0,
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
    "hubert_real": hubert_real,
    "well_insulated": well_insulated,
    "leaky_old_house": leaky_old_house,
    "thin_screed": thin_screed,
    "heavy_construction": heavy_construction,
}
"""Mapping of profile name to factory function.

All five profiles construct valid ``BuildingParams`` instances.
"""
