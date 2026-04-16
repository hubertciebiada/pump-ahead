"""Tests for RoomConfig pipe geometry fields and effective_pipe_length_m.

Validates the four new pipe geometry fields (``pipe_length_m``,
``pipe_spacing_m``, ``pipe_diameter_outer_mm``, ``pipe_wall_thickness_mm``),
their XOR validator, range constraints, and the computed
``effective_pipe_length_m`` property.
"""

import pytest

from pumpahead.config import _PIPE_BEND_SAFETY_FACTOR, RoomConfig
from pumpahead.model import RCParams

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _siso_params() -> RCParams:
    """Standard 3R3C SISO (UFH-only) parameters."""
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


def _make_room(**kwargs: object) -> RoomConfig:
    """Create a valid RoomConfig with sensible defaults."""
    defaults: dict[str, object] = {
        "name": "living_room",
        "area_m2": 25.0,
        "params": _siso_params(),
    }
    defaults.update(kwargs)
    return RoomConfig(**defaults)  # type: ignore[arg-type]


# ===========================================================================
# XOR validator — pipe_length_m vs pipe_spacing_m
# ===========================================================================


class TestPipeGeometryXOR:
    """Tests for the mutually-exclusive pipe_length_m / pipe_spacing_m rule."""

    def test_both_none_valid(self) -> None:
        """Both None (legacy mode, no geometry) is valid."""
        room = _make_room()
        assert room.pipe_length_m is None
        assert room.pipe_spacing_m is None

    def test_only_pipe_length_valid(self) -> None:
        """Providing only pipe_length_m is valid."""
        room = _make_room(pipe_length_m=120.0)
        assert room.pipe_length_m == 120.0
        assert room.pipe_spacing_m is None

    def test_only_pipe_spacing_valid(self) -> None:
        """Providing only pipe_spacing_m is valid."""
        room = _make_room(pipe_spacing_m=0.15)
        assert room.pipe_spacing_m == 0.15
        assert room.pipe_length_m is None

    def test_both_provided_raises(self) -> None:
        """Providing both pipe_length_m and pipe_spacing_m raises ValueError."""
        with pytest.raises(ValueError, match="exactly one of pipe_length_m"):
            _make_room(pipe_length_m=120.0, pipe_spacing_m=0.15)

    def test_pipe_length_zero_raises(self) -> None:
        """Zero pipe_length_m raises ValueError."""
        with pytest.raises(ValueError, match="pipe_length_m must be > 0"):
            _make_room(pipe_length_m=0.0)

    def test_pipe_length_negative_raises(self) -> None:
        """Negative pipe_length_m raises ValueError."""
        with pytest.raises(ValueError, match="pipe_length_m must be > 0"):
            _make_room(pipe_length_m=-50.0)

    def test_pipe_spacing_zero_raises(self) -> None:
        """Zero pipe_spacing_m raises ValueError."""
        with pytest.raises(ValueError, match="pipe_spacing_m must be > 0"):
            _make_room(pipe_spacing_m=0.0)

    def test_pipe_spacing_negative_raises(self) -> None:
        """Negative pipe_spacing_m raises ValueError."""
        with pytest.raises(ValueError, match="pipe_spacing_m must be > 0"):
            _make_room(pipe_spacing_m=-0.1)


# ===========================================================================
# Default dimension fields — pipe_diameter_outer_mm / pipe_wall_thickness_mm
# ===========================================================================


class TestPipeDimensions:
    """Tests for pipe diameter and wall thickness defaults and validation."""

    def test_default_diameter(self) -> None:
        """Default outer diameter is 16.0 mm (standard PEX)."""
        room = _make_room()
        assert room.pipe_diameter_outer_mm == 16.0

    def test_default_wall_thickness(self) -> None:
        """Default wall thickness is 2.0 mm."""
        room = _make_room()
        assert room.pipe_wall_thickness_mm == 2.0

    def test_custom_diameter(self) -> None:
        """Custom outer diameter is accepted."""
        room = _make_room(pipe_diameter_outer_mm=20.0)
        assert room.pipe_diameter_outer_mm == 20.0

    def test_custom_wall_thickness(self) -> None:
        """Custom wall thickness is accepted."""
        room = _make_room(pipe_wall_thickness_mm=1.8)
        assert room.pipe_wall_thickness_mm == 1.8

    def test_diameter_zero_raises(self) -> None:
        """Zero outer diameter raises ValueError."""
        with pytest.raises(ValueError, match="pipe_diameter_outer_mm must be > 0"):
            _make_room(pipe_diameter_outer_mm=0.0)

    def test_diameter_negative_raises(self) -> None:
        """Negative outer diameter raises ValueError."""
        with pytest.raises(ValueError, match="pipe_diameter_outer_mm must be > 0"):
            _make_room(pipe_diameter_outer_mm=-5.0)

    def test_wall_thickness_zero_raises(self) -> None:
        """Zero wall thickness raises ValueError."""
        with pytest.raises(ValueError, match="pipe_wall_thickness_mm must be > 0"):
            _make_room(pipe_wall_thickness_mm=0.0)

    def test_wall_thickness_negative_raises(self) -> None:
        """Negative wall thickness raises ValueError."""
        with pytest.raises(ValueError, match="pipe_wall_thickness_mm must be > 0"):
            _make_room(pipe_wall_thickness_mm=-1.0)

    def test_wall_too_large_raises(self) -> None:
        """Wall thickness > diameter / 2 raises ValueError (negative bore)."""
        with pytest.raises(ValueError, match="pipe_wall_thickness_mm.*must be"):
            _make_room(pipe_diameter_outer_mm=16.0, pipe_wall_thickness_mm=9.0)

    def test_wall_at_boundary_raises(self) -> None:
        """Wall thickness == diameter / 2 raises ValueError (zero bore)."""
        with pytest.raises(ValueError, match="pipe_wall_thickness_mm.*must be"):
            _make_room(pipe_diameter_outer_mm=16.0, pipe_wall_thickness_mm=8.0)


# ===========================================================================
# effective_pipe_length_m property
# ===========================================================================


class TestEffectivePipeLength:
    """Tests for the effective_pipe_length_m computed property."""

    def test_from_pipe_length(self) -> None:
        """Returns pipe_length_m directly when set."""
        room = _make_room(pipe_length_m=120.0)
        assert room.effective_pipe_length_m == 120.0

    def test_from_spacing(self) -> None:
        """Computes area / spacing * safety factor when pipe_spacing_m is set."""
        room = _make_room(area_m2=25.0, pipe_spacing_m=0.15)
        expected = 25.0 / 0.15 * _PIPE_BEND_SAFETY_FACTOR
        assert room.effective_pipe_length_m == pytest.approx(expected)

    def test_from_spacing_small_room(self) -> None:
        """Computed length scales with room area."""
        room = _make_room(area_m2=9.0, pipe_spacing_m=0.20)
        expected = 9.0 / 0.20 * _PIPE_BEND_SAFETY_FACTOR
        assert room.effective_pipe_length_m == pytest.approx(expected)

    def test_no_geometry_raises(self) -> None:
        """Raises ValueError when neither field is set (legacy mode)."""
        room = _make_room()
        with pytest.raises(ValueError, match="pipe geometry not configured"):
            _ = room.effective_pipe_length_m
