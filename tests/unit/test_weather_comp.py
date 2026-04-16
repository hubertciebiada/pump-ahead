"""Unit tests for weather-compensation curve module.

Tests cover:
- TestWeatherCompCurveFormula: heating curve formula, clamping, monotonicity
- TestCoolingCompCurveFormula: cooling curve formula, clamping, monotonicity
- TestWeatherCompValidation: validation for both curve types
- TestSerialization: to_dict / from_dict roundtrip for both curves
- TestSimScenarioBackwardCompatibility: SimScenario with/without curves
"""

from __future__ import annotations

import pytest

from pumpahead.config import (
    BuildingParams,
    ControllerConfig,
    RoomConfig,
    SimScenario,
)
from pumpahead.model import RCParams
from pumpahead.scenarios import SCENARIO_LIBRARY
from pumpahead.weather import SyntheticWeather
from pumpahead.weather_comp import CoolingCompCurve, WeatherCompCurve

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


def _make_room(name: str = "salon") -> RoomConfig:
    """Create a minimal valid RoomConfig."""
    return RoomConfig(name=name, area_m2=25.0, params=_siso_params())


def _make_building() -> BuildingParams:
    """Create a minimal valid BuildingParams."""
    return BuildingParams(
        rooms=(_make_room(),),
        hp_max_power_w=12_000.0,
        latitude=50.06,
        longitude=19.94,
    )


def _make_weather() -> SyntheticWeather:
    """Create a minimal constant SyntheticWeather source."""
    return SyntheticWeather.constant(T_out=-5.0)


def _typical_heating_curve() -> WeatherCompCurve:
    """Typical Aquarea-style heating curve.

    base=35, slope=1.0, neutral=15, max=55, min=20.
    """
    return WeatherCompCurve(
        t_supply_base=35.0,
        slope=1.0,
        t_neutral=15.0,
        t_supply_max=55.0,
        t_supply_min=20.0,
    )


def _typical_cooling_curve() -> CoolingCompCurve:
    """Typical cooling curve.

    base=10, slope=0.3, neutral=22, max=22, min=7.
    """
    return CoolingCompCurve(
        t_supply_base=10.0,
        slope=0.3,
        t_neutral=22.0,
        t_supply_max=22.0,
        t_supply_min=7.0,
    )


# ===========================================================================
# TestWeatherCompCurveFormula — heating curve
# ===========================================================================


@pytest.mark.unit
class TestWeatherCompCurveFormula:
    """Tests for WeatherCompCurve.t_supply() formula correctness."""

    def test_neutral_point_returns_base(self) -> None:
        """At t_out == t_neutral, supply == t_supply_base."""
        curve = _typical_heating_curve()
        result = curve.t_supply(15.0)
        assert result == pytest.approx(35.0)

    def test_above_neutral_returns_base(self) -> None:
        """Above neutral, max(0, neutral - t_out) == 0 so supply == base."""
        curve = _typical_heating_curve()
        assert curve.t_supply(20.0) == pytest.approx(35.0)
        assert curve.t_supply(30.0) == pytest.approx(35.0)

    def test_below_neutral_increases_supply(self) -> None:
        """Below neutral, supply increases linearly.

        At t_out=5, delta=10, supply = 35 + 1.0*10 = 45.
        """
        curve = _typical_heating_curve()
        assert curve.t_supply(5.0) == pytest.approx(45.0)

    def test_well_below_neutral(self) -> None:
        """At t_out=-5, delta=20, supply = 35 + 1.0*20 = 55 (at max)."""
        curve = _typical_heating_curve()
        assert curve.t_supply(-5.0) == pytest.approx(55.0)

    def test_monotonically_decreasing_with_rising_t_out(self) -> None:
        """Supply temperature never increases as t_out increases."""
        curve = _typical_heating_curve()
        t_outs = list(range(-20, 30))
        supplies = [curve.t_supply(t) for t in t_outs]
        for i in range(1, len(supplies)):
            assert supplies[i] <= supplies[i - 1], (
                f"Monotonicity violated at t_out={t_outs[i]}: "
                f"{supplies[i]} > {supplies[i - 1]}"
            )

    def test_clamp_to_max(self) -> None:
        """Very cold outdoor temperature: supply clamped at t_supply_max."""
        curve = _typical_heating_curve()
        # t_out=-20, delta=35, raw=35+35=70 -> clamped to 55
        assert curve.t_supply(-20.0) == pytest.approx(55.0)

    def test_clamp_to_min(self) -> None:
        """Even far above neutral, supply stays at base (>= min)."""
        curve = _typical_heating_curve()
        # base is 35 which is above min of 20, so stays at 35
        assert curve.t_supply(40.0) == pytest.approx(35.0)

    def test_clamp_to_min_when_base_equals_min(self) -> None:
        """When base == min, supply never drops below min."""
        curve = WeatherCompCurve(
            t_supply_base=20.0,
            slope=1.5,
            t_neutral=10.0,
            t_supply_max=55.0,
            t_supply_min=20.0,
        )
        # Above neutral -> raw = 20, clamped to 20
        assert curve.t_supply(15.0) == pytest.approx(20.0)
        # Below neutral -> raw = 20 + 1.5*5 = 27.5
        assert curve.t_supply(5.0) == pytest.approx(27.5)

    def test_typical_aquarea_curve_intermediate_values(self) -> None:
        """Spot-check typical Aquarea curve at several outdoor temps.

        Curve: base=35, slope=1.0, neutral=15, max=55, min=20.
        """
        curve = _typical_heating_curve()
        # t_out=10: delta=5, supply=35+5=40
        assert curve.t_supply(10.0) == pytest.approx(40.0)
        # t_out=0: delta=15, supply=35+15=50
        assert curve.t_supply(0.0) == pytest.approx(50.0)
        # t_out=-10: delta=25, supply=35+25=60 -> clamped to 55
        assert curve.t_supply(-10.0) == pytest.approx(55.0)

    def test_zero_slope_flat_curve(self) -> None:
        """With slope=0, supply is always base regardless of t_out."""
        curve = WeatherCompCurve(
            t_supply_base=40.0,
            slope=0.0,
            t_neutral=15.0,
            t_supply_max=55.0,
            t_supply_min=20.0,
        )
        assert curve.t_supply(-20.0) == pytest.approx(40.0)
        assert curve.t_supply(0.0) == pytest.approx(40.0)
        assert curve.t_supply(15.0) == pytest.approx(40.0)
        assert curve.t_supply(30.0) == pytest.approx(40.0)

    def test_very_large_slope_extreme_cold(self) -> None:
        """Large slope + extreme cold: clamped to max."""
        curve = WeatherCompCurve(
            t_supply_base=30.0,
            slope=10.0,
            t_neutral=15.0,
            t_supply_max=55.0,
            t_supply_min=20.0,
        )
        # t_out=-15, delta=30, raw=30+300=330 -> clamped to 55
        assert curve.t_supply(-15.0) == pytest.approx(55.0)

    def test_base_equals_max_clamps_immediately(self) -> None:
        """When base == max, supply is always max (or less above neutral)."""
        curve = WeatherCompCurve(
            t_supply_base=55.0,
            slope=1.0,
            t_neutral=15.0,
            t_supply_max=55.0,
            t_supply_min=20.0,
        )
        assert curve.t_supply(-10.0) == pytest.approx(55.0)
        assert curve.t_supply(15.0) == pytest.approx(55.0)
        assert curve.t_supply(25.0) == pytest.approx(55.0)


# ===========================================================================
# TestCoolingCompCurveFormula — cooling curve
# ===========================================================================


@pytest.mark.unit
class TestCoolingCompCurveFormula:
    """Tests for CoolingCompCurve.t_supply() formula correctness."""

    def test_neutral_point_returns_base(self) -> None:
        """At t_out == t_neutral, supply == t_supply_base."""
        curve = _typical_cooling_curve()
        assert curve.t_supply(22.0) == pytest.approx(10.0)

    def test_below_neutral_returns_base(self) -> None:
        """Below neutral, max(0, t_out - neutral) == 0 so supply == base."""
        curve = _typical_cooling_curve()
        assert curve.t_supply(15.0) == pytest.approx(10.0)
        assert curve.t_supply(0.0) == pytest.approx(10.0)

    def test_above_neutral_increases_supply(self) -> None:
        """Above neutral, supply increases linearly.

        At t_out=32, delta=10, supply = 10 + 0.3*10 = 13.
        """
        curve = _typical_cooling_curve()
        assert curve.t_supply(32.0) == pytest.approx(13.0)

    def test_monotonically_non_decreasing_with_rising_t_out(self) -> None:
        """Supply temperature never decreases as t_out increases."""
        curve = _typical_cooling_curve()
        t_outs = list(range(10, 50))
        supplies = [curve.t_supply(t) for t in t_outs]
        for i in range(1, len(supplies)):
            assert supplies[i] >= supplies[i - 1], (
                f"Monotonicity violated at t_out={t_outs[i]}: "
                f"{supplies[i]} < {supplies[i - 1]}"
            )

    def test_clamp_to_max(self) -> None:
        """Very hot outdoor temperature: supply clamped at t_supply_max."""
        curve = _typical_cooling_curve()
        # t_out=62, delta=40, raw=10+0.3*40=22 (at max)
        assert curve.t_supply(62.0) == pytest.approx(22.0)
        # t_out=100, delta=78, raw=10+0.3*78=33.4 -> clamped to 22
        assert curve.t_supply(100.0) == pytest.approx(22.0)

    def test_clamp_to_min(self) -> None:
        """Supply never drops below min, even with base == min."""
        curve = CoolingCompCurve(
            t_supply_base=7.0,
            slope=0.3,
            t_neutral=22.0,
            t_supply_max=22.0,
            t_supply_min=7.0,
        )
        assert curve.t_supply(10.0) == pytest.approx(7.0)
        assert curve.t_supply(-10.0) == pytest.approx(7.0)

    def test_zero_slope_flat_curve(self) -> None:
        """With slope=0, supply is always base regardless of t_out."""
        curve = CoolingCompCurve(
            t_supply_base=12.0,
            slope=0.0,
            t_neutral=22.0,
            t_supply_max=22.0,
            t_supply_min=7.0,
        )
        assert curve.t_supply(0.0) == pytest.approx(12.0)
        assert curve.t_supply(22.0) == pytest.approx(12.0)
        assert curve.t_supply(40.0) == pytest.approx(12.0)

    def test_intermediate_values(self) -> None:
        """Spot-check at several outdoor temps.

        Curve: base=10, slope=0.3, neutral=22, max=22, min=7.
        """
        curve = _typical_cooling_curve()
        # t_out=25: delta=3, supply=10+0.3*3=10.9
        assert curve.t_supply(25.0) == pytest.approx(10.9)
        # t_out=30: delta=8, supply=10+0.3*8=12.4
        assert curve.t_supply(30.0) == pytest.approx(12.4)
        # t_out=40: delta=18, supply=10+0.3*18=15.4
        assert curve.t_supply(40.0) == pytest.approx(15.4)

    def test_base_equals_max_clamps_immediately(self) -> None:
        """When base == max, supply is always max (regardless of t_out)."""
        curve = CoolingCompCurve(
            t_supply_base=22.0,
            slope=0.3,
            t_neutral=22.0,
            t_supply_max=22.0,
            t_supply_min=7.0,
        )
        assert curve.t_supply(10.0) == pytest.approx(22.0)
        assert curve.t_supply(22.0) == pytest.approx(22.0)
        assert curve.t_supply(35.0) == pytest.approx(22.0)


# ===========================================================================
# TestWeatherCompValidation — validation for both curve types
# ===========================================================================


@pytest.mark.unit
class TestWeatherCompValidation:
    """Tests for __post_init__ validation of WeatherCompCurve and CoolingCompCurve."""

    def test_heating_negative_slope_raises(self) -> None:
        """WeatherCompCurve rejects negative slope."""
        with pytest.raises(ValueError, match="slope must be >= 0"):
            WeatherCompCurve(
                t_supply_base=35.0,
                slope=-0.5,
                t_neutral=15.0,
                t_supply_max=55.0,
                t_supply_min=20.0,
            )

    def test_heating_min_greater_than_max_raises(self) -> None:
        """WeatherCompCurve rejects t_supply_min > t_supply_max."""
        with pytest.raises(ValueError, match="t_supply_max.*must be >.*t_supply_min"):
            WeatherCompCurve(
                t_supply_base=35.0,
                slope=1.0,
                t_neutral=15.0,
                t_supply_max=10.0,
                t_supply_min=20.0,
            )

    def test_heating_min_equals_max_raises(self) -> None:
        """WeatherCompCurve rejects t_supply_min == t_supply_max."""
        with pytest.raises(ValueError, match="t_supply_max.*must be >.*t_supply_min"):
            WeatherCompCurve(
                t_supply_base=35.0,
                slope=1.0,
                t_neutral=15.0,
                t_supply_max=20.0,
                t_supply_min=20.0,
            )

    def test_heating_base_below_min_raises(self) -> None:
        """WeatherCompCurve rejects t_supply_base < t_supply_min."""
        with pytest.raises(ValueError, match="t_supply_base.*must be >=.*t_supply_min"):
            WeatherCompCurve(
                t_supply_base=15.0,
                slope=1.0,
                t_neutral=15.0,
                t_supply_max=55.0,
                t_supply_min=20.0,
            )

    def test_heating_base_above_max_raises(self) -> None:
        """WeatherCompCurve rejects t_supply_base > t_supply_max."""
        with pytest.raises(ValueError, match="t_supply_base.*must be <=.*t_supply_max"):
            WeatherCompCurve(
                t_supply_base=60.0,
                slope=1.0,
                t_neutral=15.0,
                t_supply_max=55.0,
                t_supply_min=20.0,
            )

    def test_heating_non_positive_min_raises(self) -> None:
        """WeatherCompCurve rejects t_supply_min <= 0."""
        with pytest.raises(ValueError, match="t_supply_min must be > 0"):
            WeatherCompCurve(
                t_supply_base=5.0,
                slope=1.0,
                t_neutral=15.0,
                t_supply_max=55.0,
                t_supply_min=0.0,
            )

    def test_heating_negative_min_raises(self) -> None:
        """WeatherCompCurve rejects t_supply_min < 0."""
        with pytest.raises(ValueError, match="t_supply_min must be > 0"):
            WeatherCompCurve(
                t_supply_base=5.0,
                slope=1.0,
                t_neutral=15.0,
                t_supply_max=55.0,
                t_supply_min=-5.0,
            )

    def test_cooling_negative_slope_raises(self) -> None:
        """CoolingCompCurve rejects negative slope."""
        with pytest.raises(ValueError, match="slope must be >= 0"):
            CoolingCompCurve(
                t_supply_base=10.0,
                slope=-0.3,
                t_neutral=22.0,
                t_supply_max=22.0,
                t_supply_min=7.0,
            )

    def test_cooling_min_greater_than_max_raises(self) -> None:
        """CoolingCompCurve rejects t_supply_min > t_supply_max."""
        with pytest.raises(ValueError, match="t_supply_max.*must be >.*t_supply_min"):
            CoolingCompCurve(
                t_supply_base=10.0,
                slope=0.3,
                t_neutral=22.0,
                t_supply_max=5.0,
                t_supply_min=7.0,
            )

    def test_cooling_base_below_min_raises(self) -> None:
        """CoolingCompCurve rejects t_supply_base < t_supply_min."""
        with pytest.raises(ValueError, match="t_supply_base.*must be >=.*t_supply_min"):
            CoolingCompCurve(
                t_supply_base=5.0,
                slope=0.3,
                t_neutral=22.0,
                t_supply_max=22.0,
                t_supply_min=7.0,
            )

    def test_cooling_base_above_max_raises(self) -> None:
        """CoolingCompCurve rejects t_supply_base > t_supply_max."""
        with pytest.raises(ValueError, match="t_supply_base.*must be <=.*t_supply_max"):
            CoolingCompCurve(
                t_supply_base=25.0,
                slope=0.3,
                t_neutral=22.0,
                t_supply_max=22.0,
                t_supply_min=7.0,
            )

    def test_cooling_non_positive_min_raises(self) -> None:
        """CoolingCompCurve rejects t_supply_min <= 0."""
        with pytest.raises(ValueError, match="t_supply_min must be > 0"):
            CoolingCompCurve(
                t_supply_base=5.0,
                slope=0.3,
                t_neutral=22.0,
                t_supply_max=22.0,
                t_supply_min=0.0,
            )

    @pytest.mark.parametrize(
        ("cls", "kwargs"),
        [
            pytest.param(
                WeatherCompCurve,
                {
                    "t_supply_base": 35.0,
                    "slope": -1.0,
                    "t_neutral": 15.0,
                    "t_supply_max": 55.0,
                    "t_supply_min": 20.0,
                },
                id="heating-negative-slope",
            ),
            pytest.param(
                CoolingCompCurve,
                {
                    "t_supply_base": 10.0,
                    "slope": -0.5,
                    "t_neutral": 22.0,
                    "t_supply_max": 22.0,
                    "t_supply_min": 7.0,
                },
                id="cooling-negative-slope",
            ),
        ],
    )
    def test_parametrized_negative_slope_raises(
        self, cls: type, kwargs: dict[str, float]
    ) -> None:
        """Both curve types reject negative slopes (parametrized)."""
        with pytest.raises(ValueError, match="slope must be >= 0"):
            cls(**kwargs)

    @pytest.mark.parametrize(
        ("cls", "kwargs"),
        [
            pytest.param(
                WeatherCompCurve,
                {
                    "t_supply_base": 35.0,
                    "slope": 1.0,
                    "t_neutral": 15.0,
                    "t_supply_max": 55.0,
                    "t_supply_min": 0.0,
                },
                id="heating-zero-min",
            ),
            pytest.param(
                CoolingCompCurve,
                {
                    "t_supply_base": 10.0,
                    "slope": 0.3,
                    "t_neutral": 22.0,
                    "t_supply_max": 22.0,
                    "t_supply_min": -1.0,
                },
                id="cooling-negative-min",
            ),
        ],
    )
    def test_parametrized_non_positive_min_raises(
        self, cls: type, kwargs: dict[str, float]
    ) -> None:
        """Both curve types reject non-positive t_supply_min (parametrized)."""
        with pytest.raises(ValueError, match="t_supply_min must be > 0"):
            cls(**kwargs)


# ===========================================================================
# TestSerialization — to_dict / from_dict roundtrip
# ===========================================================================


@pytest.mark.unit
class TestSerialization:
    """Tests for to_dict() / from_dict() serialisation roundtrip."""

    def test_heating_roundtrip(self) -> None:
        """WeatherCompCurve survives to_dict -> from_dict."""
        original = _typical_heating_curve()
        data = original.to_dict()
        restored = WeatherCompCurve.from_dict(data)
        assert restored == original

    def test_cooling_roundtrip(self) -> None:
        """CoolingCompCurve survives to_dict -> from_dict."""
        original = _typical_cooling_curve()
        data = original.to_dict()
        restored = CoolingCompCurve.from_dict(data)
        assert restored == original

    def test_heating_to_dict_returns_plain_dict(self) -> None:
        """to_dict() returns a plain dict with float values."""
        curve = _typical_heating_curve()
        data = curve.to_dict()
        assert isinstance(data, dict)
        assert set(data.keys()) == {
            "t_supply_base",
            "slope",
            "t_neutral",
            "t_supply_max",
            "t_supply_min",
        }
        for v in data.values():
            assert isinstance(v, int | float)

    def test_cooling_to_dict_returns_plain_dict(self) -> None:
        """to_dict() returns a plain dict with float values."""
        curve = _typical_cooling_curve()
        data = curve.to_dict()
        assert isinstance(data, dict)
        assert set(data.keys()) == {
            "t_supply_base",
            "slope",
            "t_neutral",
            "t_supply_max",
            "t_supply_min",
        }

    def test_from_dict_validates(self) -> None:
        """from_dict triggers __post_init__ validation."""
        bad_data = {
            "t_supply_base": 35.0,
            "slope": -1.0,
            "t_neutral": 15.0,
            "t_supply_max": 55.0,
            "t_supply_min": 20.0,
        }
        with pytest.raises(ValueError, match="slope must be >= 0"):
            WeatherCompCurve.from_dict(bad_data)

    def test_from_dict_missing_key_raises_type_error(self) -> None:
        """from_dict with missing keys raises TypeError."""
        incomplete = {
            "t_supply_base": 35.0,
            "slope": 1.0,
        }
        with pytest.raises(TypeError):
            WeatherCompCurve.from_dict(incomplete)

    def test_heating_roundtrip_preserves_custom_min(self) -> None:
        """Custom t_supply_min survives roundtrip."""
        original = WeatherCompCurve(
            t_supply_base=30.0,
            slope=0.8,
            t_neutral=12.0,
            t_supply_max=50.0,
            t_supply_min=25.0,
        )
        restored = WeatherCompCurve.from_dict(original.to_dict())
        assert restored == original
        assert restored.t_supply_min == pytest.approx(25.0)


# ===========================================================================
# TestSimScenarioBackwardCompatibility — SimScenario integration
# ===========================================================================


@pytest.mark.unit
class TestSimScenarioBackwardCompatibility:
    """Tests that SimScenario accepts weather_comp/cooling_comp optionally."""

    def test_scenario_without_curves(self) -> None:
        """Existing scenario construction still works (no curves)."""
        scenario = SimScenario(
            name="test_no_curves",
            building=_make_building(),
            weather=_make_weather(),
            controller=ControllerConfig(),
            duration_minutes=1440,
        )
        assert scenario.weather_comp is None
        assert scenario.cooling_comp is None

    def test_scenario_with_weather_comp(self) -> None:
        """Scenario with only weather_comp works."""
        curve = _typical_heating_curve()
        scenario = SimScenario(
            name="test_heating_curve",
            building=_make_building(),
            weather=_make_weather(),
            controller=ControllerConfig(),
            duration_minutes=1440,
            weather_comp=curve,
        )
        assert scenario.weather_comp is curve
        assert scenario.cooling_comp is None

    def test_scenario_with_cooling_comp(self) -> None:
        """Scenario with only cooling_comp works."""
        curve = _typical_cooling_curve()
        scenario = SimScenario(
            name="test_cooling_curve",
            building=_make_building(),
            weather=_make_weather(),
            controller=ControllerConfig(),
            duration_minutes=1440,
            mode="cooling",
            cooling_comp=curve,
        )
        assert scenario.cooling_comp is curve
        assert scenario.weather_comp is None

    def test_scenario_with_both_curves(self) -> None:
        """Scenario with both curves works (e.g. auto mode)."""
        heating = _typical_heating_curve()
        cooling = _typical_cooling_curve()
        scenario = SimScenario(
            name="test_both_curves",
            building=_make_building(),
            weather=_make_weather(),
            controller=ControllerConfig(),
            duration_minutes=1440,
            mode="auto",
            weather_comp=heating,
            cooling_comp=cooling,
        )
        assert scenario.weather_comp is heating
        assert scenario.cooling_comp is cooling

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_all_library_scenarios_still_construct(self, name: str) -> None:
        """Every scenario in SCENARIO_LIBRARY constructs without error.

        This verifies backward compatibility — existing scenarios that do
        not provide weather_comp / cooling_comp default to None.
        """
        factory = SCENARIO_LIBRARY[name]
        scenario = factory()
        assert isinstance(scenario, SimScenario)
        assert scenario.weather_comp is None
        assert scenario.cooling_comp is None


# ===========================================================================
# TestTopLevelImport — importable from pumpahead top-level
# ===========================================================================


@pytest.mark.unit
class TestTopLevelImport:
    """Tests that both curve classes are importable from pumpahead."""

    def test_weather_comp_curve_importable(self) -> None:
        """WeatherCompCurve is in pumpahead.__all__."""
        import pumpahead

        assert hasattr(pumpahead, "WeatherCompCurve")
        assert pumpahead.WeatherCompCurve is WeatherCompCurve

    def test_cooling_comp_curve_importable(self) -> None:
        """CoolingCompCurve is in pumpahead.__all__."""
        import pumpahead

        assert hasattr(pumpahead, "CoolingCompCurve")
        assert pumpahead.CoolingCompCurve is CoolingCompCurve
