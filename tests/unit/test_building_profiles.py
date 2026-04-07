"""Tests for building profile factory functions.

Validates that all profiles in ``pumpahead.building_profiles`` construct
valid ``BuildingParams`` instances with physically sensible RC parameters.
"""

import pytest

from pumpahead.building_profiles import (
    BUILDING_PROFILES,
    HUBERT_ROOMS,
    heavy_construction,
    hubert_real,
    leaky_old_house,
    thin_screed,
    well_insulated,
)
from pumpahead.config import BuildingParams

# ---------------------------------------------------------------------------
# TestHubertReal — author's real house
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHubertReal:
    """Tests specific to the ``hubert_real`` profile."""

    def test_returns_building_params(self) -> None:
        """Factory returns a BuildingParams instance."""
        building = hubert_real()
        assert isinstance(building, BuildingParams)

    def test_exactly_8_rooms(self) -> None:
        """Hubert's house has exactly 8 rooms."""
        building = hubert_real()
        assert len(building.rooms) == 8

    def test_room_names_are_unique(self) -> None:
        """All room names are unique."""
        building = hubert_real()
        names = [r.name for r in building.rooms]
        assert len(names) == len(set(names))

    def test_expected_room_names(self) -> None:
        """Room names match the known layout."""
        building = hubert_real()
        names = sorted(r.name for r in building.rooms)
        expected = sorted(
            [
                "salon",
                "kuchnia",
                "sypialnia",
                "gabinet",
                "pokoj_dzieci",
                "lazienka",
                "garderoba",
                "korytarz",
            ]
        )
        assert names == expected

    def test_total_ufh_loops_is_13(self) -> None:
        """Total UFH loops across all rooms sum to 13."""
        building = hubert_real()
        total = sum(r.ufh_loops for r in building.rooms)
        assert total == 13

    def test_at_least_5_rooms_with_split(self) -> None:
        """At least 5 rooms have split/AC units."""
        building = hubert_real()
        split_count = sum(1 for r in building.rooms if r.has_split)
        assert split_count >= 5

    def test_exactly_5_rooms_with_split(self) -> None:
        """Exactly 5 rooms have split/AC units."""
        building = hubert_real()
        split_rooms = [r.name for r in building.rooms if r.has_split]
        assert len(split_rooms) == 5
        assert set(split_rooms) == {
            "salon",
            "kuchnia",
            "sypialnia",
            "gabinet",
            "pokoj_dzieci",
        }

    def test_location_lubcza_poland(self) -> None:
        """Coordinates match Lubcza, Poland."""
        building = hubert_real()
        assert building.latitude == pytest.approx(50.69)
        assert building.longitude == pytest.approx(17.38)

    def test_hp_power_positive(self) -> None:
        """Heat pump max power is positive."""
        building = hubert_real()
        assert building.hp_max_power_w > 0

    def test_deterministic(self) -> None:
        """Calling factory twice returns equal results."""
        a = hubert_real()
        b = hubert_real()
        assert a == b

    def test_hubert_rooms_matches_factory(self) -> None:
        """HUBERT_ROOMS constant matches hubert_real().rooms."""
        building = hubert_real()
        assert building.rooms == HUBERT_ROOMS

    def test_validation_passes(self) -> None:
        """BuildingParams validation does not raise."""
        # If construction fails, this test fails with ValueError
        building = hubert_real()
        assert building is not None

    def test_garderoba_has_no_windows(self) -> None:
        """Garderoba (closet) has no windows."""
        building = hubert_real()
        garderoba = next(r for r in building.rooms if r.name == "garderoba")
        assert len(garderoba.windows) == 0

    def test_korytarz_has_no_windows(self) -> None:
        """Korytarz (hallway) has no windows."""
        building = hubert_real()
        korytarz = next(r for r in building.rooms if r.name == "korytarz")
        assert len(korytarz.windows) == 0

    def test_salon_has_south_and_west_windows(self) -> None:
        """Salon has south and west-facing windows."""
        from pumpahead.solar import Orientation

        building = hubert_real()
        salon = next(r for r in building.rooms if r.name == "salon")
        orientations = {w.orientation for w in salon.windows}
        assert Orientation.SOUTH in orientations
        assert Orientation.WEST in orientations

    def test_split_rooms_have_positive_split_power(self) -> None:
        """Rooms with splits have positive split power."""
        building = hubert_real()
        for room in building.rooms:
            if room.has_split:
                assert room.split_power_w > 0, f"{room.name}: split_power_w <= 0"

    def test_no_split_rooms_have_zero_split_power(self) -> None:
        """Rooms without splits have zero split power."""
        building = hubert_real()
        for room in building.rooms:
            if not room.has_split:
                assert room.split_power_w == 0.0, f"{room.name}: split_power_w != 0"


# ---------------------------------------------------------------------------
# TestAllProfiles — common properties across all profiles
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAllProfiles:
    """Tests that apply to every profile in BUILDING_PROFILES."""

    def test_five_profiles_exist(self) -> None:
        """At least 5 profiles are registered."""
        assert len(BUILDING_PROFILES) >= 5

    def test_expected_profile_names(self) -> None:
        """All required profile names are present."""
        expected = {
            "hubert_real",
            "well_insulated",
            "leaky_old_house",
            "thin_screed",
            "heavy_construction",
        }
        assert expected.issubset(set(BUILDING_PROFILES.keys()))

    @pytest.mark.parametrize("name", list(BUILDING_PROFILES.keys()))
    def test_construction_valid(self, name: str) -> None:
        """Every profile constructs without raising ValueError."""
        factory = BUILDING_PROFILES[name]
        building = factory()
        assert isinstance(building, BuildingParams)

    @pytest.mark.parametrize("name", list(BUILDING_PROFILES.keys()))
    def test_deterministic(self, name: str) -> None:
        """Every profile is deterministic (two calls return equal)."""
        factory = BUILDING_PROFILES[name]
        a = factory()
        b = factory()
        assert a == b

    @pytest.mark.parametrize("name", list(BUILDING_PROFILES.keys()))
    def test_at_least_one_room(self, name: str) -> None:
        """Every profile has at least one room."""
        building = BUILDING_PROFILES[name]()
        assert len(building.rooms) >= 1

    @pytest.mark.parametrize("name", list(BUILDING_PROFILES.keys()))
    def test_positive_r_values(self, name: str) -> None:
        """All R values in every room are positive."""
        building = BUILDING_PROFILES[name]()
        for room in building.rooms:
            p = room.params
            assert p.R_sf > 0, f"{name}/{room.name}: R_sf <= 0"
            # 3R3C parameters
            if p.R_wi is not None:
                assert p.R_wi > 0, f"{name}/{room.name}: R_wi <= 0"
            if p.R_wo is not None:
                assert p.R_wo > 0, f"{name}/{room.name}: R_wo <= 0"
            if p.R_ve is not None:
                assert p.R_ve > 0, f"{name}/{room.name}: R_ve <= 0"
            if p.R_ins is not None:
                assert p.R_ins > 0, f"{name}/{room.name}: R_ins <= 0"

    @pytest.mark.parametrize("name", list(BUILDING_PROFILES.keys()))
    def test_positive_c_values(self, name: str) -> None:
        """All C values in every room are positive."""
        building = BUILDING_PROFILES[name]()
        for room in building.rooms:
            p = room.params
            assert p.C_air > 0, f"{name}/{room.name}: C_air <= 0"
            assert p.C_slab > 0, f"{name}/{room.name}: C_slab <= 0"
            if p.C_wall is not None:
                assert p.C_wall > 0, f"{name}/{room.name}: C_wall <= 0"

    @pytest.mark.parametrize("name", list(BUILDING_PROFILES.keys()))
    def test_solar_fractions_valid(self, name: str) -> None:
        """Solar fractions f_conv, f_rad are in [0, 1] and sum <= 1."""
        building = BUILDING_PROFILES[name]()
        for room in building.rooms:
            p = room.params
            assert 0.0 <= p.f_conv <= 1.0, f"{name}/{room.name}: f_conv={p.f_conv}"
            assert 0.0 <= p.f_rad <= 1.0, f"{name}/{room.name}: f_rad={p.f_rad}"
            assert p.f_conv + p.f_rad <= 1.0, (
                f"{name}/{room.name}: f_conv+f_rad={p.f_conv + p.f_rad}"
            )

    @pytest.mark.parametrize("name", list(BUILDING_PROFILES.keys()))
    def test_has_split_consistency(self, name: str) -> None:
        """RoomConfig.has_split matches RCParams.has_split in every room."""
        building = BUILDING_PROFILES[name]()
        for room in building.rooms:
            assert room.has_split == room.params.has_split, (
                f"{name}/{room.name}: has_split mismatch"
            )


# ---------------------------------------------------------------------------
# TestPhysicalSensibility — cross-profile physical comparisons
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPhysicalSensibility:
    """Tests for physically sensible relationships between profiles."""

    def test_thin_screed_lower_c_slab_than_heavy(self) -> None:
        """thin_screed has lower C_slab than heavy_construction."""
        ts = thin_screed()
        hc = heavy_construction()
        # Both single-room profiles — compare the single room
        assert ts.rooms[0].params.C_slab < hc.rooms[0].params.C_slab

    def test_leaky_lower_r_wo_than_well_insulated(self) -> None:
        """leaky_old_house has lower R_wo than well_insulated."""
        leaky = leaky_old_house()
        good = well_insulated()
        r_wo_leaky = leaky.rooms[0].params.R_wo
        r_wo_good = good.rooms[0].params.R_wo
        assert r_wo_leaky is not None
        assert r_wo_good is not None
        assert r_wo_leaky < r_wo_good

    def test_leaky_lower_r_ve_than_well_insulated(self) -> None:
        """leaky_old_house has lower R_ve than well_insulated."""
        leaky = leaky_old_house()
        good = well_insulated()
        r_ve_leaky = leaky.rooms[0].params.R_ve
        r_ve_good = good.rooms[0].params.R_ve
        assert r_ve_leaky is not None
        assert r_ve_good is not None
        assert r_ve_leaky < r_ve_good

    def test_c_slab_to_c_air_ratio_reasonable(self) -> None:
        """C_slab/C_air ratio is in a physically plausible range (10-200)."""
        for name, factory in BUILDING_PROFILES.items():
            building = factory()
            for room in building.rooms:
                ratio = room.params.C_slab / room.params.C_air
                assert 10 <= ratio <= 200, (
                    f"{name}/{room.name}: C_slab/C_air={ratio:.1f}"
                )

    def test_r_sf_in_plausible_range(self) -> None:
        """R_sf (slab-floor) is in a plausible range for all rooms.

        For 20 m^2: 0.005-0.05 K/W. Scaled rooms differ proportionally.
        We check a generous range of 0.001-0.1 K/W.
        """
        for name, factory in BUILDING_PROFILES.items():
            building = factory()
            for room in building.rooms:
                assert 0.001 <= room.params.R_sf <= 0.1, (
                    f"{name}/{room.name}: R_sf={room.params.R_sf}"
                )

    def test_c_air_scales_with_area(self) -> None:
        """C_air roughly scales with room area in hubert_real.

        Larger rooms should have proportionally larger C_air.  We check
        that salon (30 m^2) has higher C_air than garderoba (5 m^2).
        """
        building = hubert_real()
        salon = next(r for r in building.rooms if r.name == "salon")
        garderoba = next(r for r in building.rooms if r.name == "garderoba")
        assert salon.params.C_air > garderoba.params.C_air

    def test_ufh_max_power_reasonable(self) -> None:
        """UFH max power is in a reasonable range (500-10000 W)."""
        for name, factory in BUILDING_PROFILES.items():
            building = factory()
            for room in building.rooms:
                assert 500 <= room.ufh_max_power_w <= 10_000, (
                    f"{name}/{room.name}: ufh_max_power_w={room.ufh_max_power_w}"
                )

    def test_heavy_construction_higher_c_wall(self) -> None:
        """heavy_construction has higher C_wall than thin_screed."""
        hc = heavy_construction()
        ts = thin_screed()
        c_wall_hc = hc.rooms[0].params.C_wall
        c_wall_ts = ts.rooms[0].params.C_wall
        assert c_wall_hc is not None
        assert c_wall_ts is not None
        assert c_wall_hc > c_wall_ts


# ---------------------------------------------------------------------------
# TestExports — module-level exports
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExports:
    """Tests for module-level exports and __init__.py re-exports."""

    def test_building_profiles_importable_from_init(self) -> None:
        """BUILDING_PROFILES is importable from pumpahead."""
        from pumpahead import BUILDING_PROFILES as bp

        assert len(bp) >= 5

    def test_hubert_rooms_importable_from_init(self) -> None:
        """HUBERT_ROOMS is importable from pumpahead."""
        from pumpahead import HUBERT_ROOMS as hr

        assert len(hr) == 8

    def test_factory_functions_importable_from_init(self) -> None:
        """All factory functions are importable from pumpahead."""
        from pumpahead import (
            heavy_construction as hc,
        )
        from pumpahead import (
            hubert_real as hr,
        )
        from pumpahead import (
            leaky_old_house as lo,
        )
        from pumpahead import (
            thin_screed as ts,
        )
        from pumpahead import (
            well_insulated as wi,
        )

        # Just verify they are callable
        assert callable(hr)
        assert callable(wi)
        assert callable(lo)
        assert callable(ts)
        assert callable(hc)

    def test_all_symbols_in_init_all(self) -> None:
        """All new symbols appear in pumpahead.__all__."""
        import pumpahead

        expected = [
            "BUILDING_PROFILES",
            "HUBERT_ROOMS",
            "hubert_real",
            "well_insulated",
            "leaky_old_house",
            "thin_screed",
            "heavy_construction",
        ]
        for sym in expected:
            assert sym in pumpahead.__all__, f"{sym} missing from __all__"
