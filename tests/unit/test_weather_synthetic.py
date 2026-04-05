"""Unit tests for pumpahead.weather — WeatherSource protocol + SyntheticWeather."""

from __future__ import annotations

import math

import pytest

from pumpahead.weather import (
    ChannelProfile,
    ProfileKind,
    SyntheticWeather,
    WeatherPoint,
    WeatherSource,
)

# ---------------------------------------------------------------------------
# TestWeatherPoint — frozen dataclass, field access
# ---------------------------------------------------------------------------


class TestWeatherPoint:
    """Tests for the WeatherPoint frozen dataclass."""

    @pytest.mark.unit
    def test_field_access(self) -> None:
        """All four fields must be accessible by name."""
        wp = WeatherPoint(T_out=-5.0, GHI=200.0, wind_speed=3.5, humidity=65.0)
        assert wp.T_out == -5.0
        assert wp.GHI == 200.0
        assert wp.wind_speed == 3.5
        assert wp.humidity == 65.0

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """Assigning to a field on a frozen dataclass must raise."""
        wp = WeatherPoint(T_out=0.0, GHI=0.0, wind_speed=0.0, humidity=50.0)
        with pytest.raises(AttributeError):
            wp.T_out = 10.0  # type: ignore[misc]

    @pytest.mark.unit
    def test_equality(self) -> None:
        """Two WeatherPoints with the same values must be equal."""
        a = WeatherPoint(T_out=1.0, GHI=2.0, wind_speed=3.0, humidity=4.0)
        b = WeatherPoint(T_out=1.0, GHI=2.0, wind_speed=3.0, humidity=4.0)
        assert a == b


# ---------------------------------------------------------------------------
# TestChannelProfile — evaluate() for each ProfileKind
# ---------------------------------------------------------------------------


class TestChannelProfile:
    """Tests for ChannelProfile.evaluate() across all profile kinds."""

    # -- CONSTANT --

    @pytest.mark.unit
    def test_constant_returns_baseline(self) -> None:
        """CONSTANT profile returns baseline at any time."""
        p = ChannelProfile(kind=ProfileKind.CONSTANT, baseline=42.0)
        assert p.evaluate(0.0) == 42.0
        assert p.evaluate(999.0) == 42.0
        assert p.evaluate(-10.0) == 42.0

    # -- STEP --

    @pytest.mark.unit
    def test_step_before_step_time(self) -> None:
        """STEP profile returns baseline before step_time_minutes."""
        p = ChannelProfile(
            kind=ProfileKind.STEP,
            baseline=10.0,
            amplitude=5.0,
            step_time_minutes=60.0,
        )
        assert p.evaluate(0.0) == 10.0
        assert p.evaluate(59.99) == 10.0

    @pytest.mark.unit
    def test_step_at_step_time(self) -> None:
        """STEP profile returns baseline + amplitude at exactly step_time."""
        p = ChannelProfile(
            kind=ProfileKind.STEP,
            baseline=10.0,
            amplitude=5.0,
            step_time_minutes=60.0,
        )
        assert p.evaluate(60.0) == 15.0

    @pytest.mark.unit
    def test_step_after_step_time(self) -> None:
        """STEP profile returns baseline + amplitude after step_time."""
        p = ChannelProfile(
            kind=ProfileKind.STEP,
            baseline=10.0,
            amplitude=5.0,
            step_time_minutes=60.0,
        )
        assert p.evaluate(120.0) == 15.0

    @pytest.mark.unit
    def test_step_negative_amplitude(self) -> None:
        """STEP with negative amplitude produces a drop."""
        p = ChannelProfile(
            kind=ProfileKind.STEP,
            baseline=20.0,
            amplitude=-10.0,
            step_time_minutes=30.0,
        )
        assert p.evaluate(0.0) == 20.0
        assert p.evaluate(30.0) == 10.0

    # -- RAMP --

    @pytest.mark.unit
    def test_ramp_at_start(self) -> None:
        """RAMP at t=0 returns baseline."""
        p = ChannelProfile(
            kind=ProfileKind.RAMP,
            baseline=0.0,
            amplitude=10.0,
            period_minutes=100.0,
        )
        assert p.evaluate(0.0) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_ramp_at_midpoint(self) -> None:
        """RAMP at t=period/2 returns baseline + amplitude/2."""
        p = ChannelProfile(
            kind=ProfileKind.RAMP,
            baseline=0.0,
            amplitude=10.0,
            period_minutes=100.0,
        )
        assert p.evaluate(50.0) == pytest.approx(5.0)

    @pytest.mark.unit
    def test_ramp_at_end(self) -> None:
        """RAMP at t=period returns baseline + amplitude."""
        p = ChannelProfile(
            kind=ProfileKind.RAMP,
            baseline=0.0,
            amplitude=10.0,
            period_minutes=100.0,
        )
        assert p.evaluate(100.0) == pytest.approx(10.0)

    @pytest.mark.unit
    def test_ramp_clamped_beyond_period(self) -> None:
        """RAMP beyond period clamps at baseline + amplitude."""
        p = ChannelProfile(
            kind=ProfileKind.RAMP,
            baseline=5.0,
            amplitude=20.0,
            period_minutes=60.0,
        )
        assert p.evaluate(120.0) == pytest.approx(25.0)

    @pytest.mark.unit
    def test_ramp_clamped_negative_time(self) -> None:
        """RAMP at negative time clamps progress to 0 (returns baseline)."""
        p = ChannelProfile(
            kind=ProfileKind.RAMP,
            baseline=5.0,
            amplitude=20.0,
            period_minutes=60.0,
        )
        assert p.evaluate(-10.0) == pytest.approx(5.0)

    # -- SINUSOIDAL --

    @pytest.mark.unit
    def test_sinusoidal_at_zero(self) -> None:
        """SINUSOIDAL at t=0 returns baseline (sin(0)=0)."""
        p = ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=10.0,
            amplitude=5.0,
            period_minutes=60.0,
        )
        assert p.evaluate(0.0) == pytest.approx(10.0)

    @pytest.mark.unit
    def test_sinusoidal_at_quarter_period(self) -> None:
        """SINUSOIDAL at t=period/4 returns baseline + amplitude (sin(pi/2)=1)."""
        p = ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=10.0,
            amplitude=5.0,
            period_minutes=60.0,
        )
        assert p.evaluate(15.0) == pytest.approx(15.0)

    @pytest.mark.unit
    def test_sinusoidal_at_half_period(self) -> None:
        """SINUSOIDAL at t=period/2 returns baseline (sin(pi)~0)."""
        p = ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=10.0,
            amplitude=5.0,
            period_minutes=60.0,
        )
        assert p.evaluate(30.0) == pytest.approx(10.0)

    @pytest.mark.unit
    def test_sinusoidal_at_three_quarter_period(self) -> None:
        """SINUSOIDAL at t=3*period/4 returns baseline - amplitude (sin(3pi/2)=-1)."""
        p = ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=10.0,
            amplitude=5.0,
            period_minutes=60.0,
        )
        assert p.evaluate(45.0) == pytest.approx(5.0)

    @pytest.mark.unit
    def test_sinusoidal_periodicity(self) -> None:
        """SINUSOIDAL is periodic: value at t equals value at t + period."""
        p = ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=0.0,
            amplitude=7.0,
            period_minutes=120.0,
        )
        t = 37.5
        assert p.evaluate(t) == pytest.approx(p.evaluate(t + 120.0))

    @pytest.mark.unit
    def test_sinusoidal_analytic_value(self) -> None:
        """SINUSOIDAL at arbitrary time matches analytic formula."""
        p = ChannelProfile(
            kind=ProfileKind.SINUSOIDAL,
            baseline=3.0,
            amplitude=2.0,
            period_minutes=100.0,
        )
        t = 25.0  # sin(2*pi*25/100) = sin(pi/2) = 1.0
        expected = 3.0 + 2.0 * math.sin(2.0 * math.pi * 25.0 / 100.0)
        assert p.evaluate(t) == pytest.approx(expected)

    # -- Validation --

    @pytest.mark.unit
    def test_sinusoidal_zero_period_rejected(self) -> None:
        """SINUSOIDAL with period_minutes=0 must raise ValueError."""
        with pytest.raises(ValueError, match="period_minutes must be > 0"):
            ChannelProfile(
                kind=ProfileKind.SINUSOIDAL,
                baseline=0.0,
                amplitude=1.0,
                period_minutes=0.0,
            )

    @pytest.mark.unit
    def test_sinusoidal_negative_period_rejected(self) -> None:
        """SINUSOIDAL with negative period_minutes must raise ValueError."""
        with pytest.raises(ValueError, match="period_minutes must be > 0"):
            ChannelProfile(
                kind=ProfileKind.SINUSOIDAL,
                baseline=0.0,
                amplitude=1.0,
                period_minutes=-10.0,
            )

    @pytest.mark.unit
    def test_ramp_zero_period_rejected(self) -> None:
        """RAMP with period_minutes=0 must raise ValueError."""
        with pytest.raises(ValueError, match="period_minutes must be > 0"):
            ChannelProfile(
                kind=ProfileKind.RAMP,
                baseline=0.0,
                amplitude=1.0,
                period_minutes=0.0,
            )

    @pytest.mark.unit
    def test_ramp_negative_period_rejected(self) -> None:
        """RAMP with negative period_minutes must raise ValueError."""
        with pytest.raises(ValueError, match="period_minutes must be > 0"):
            ChannelProfile(
                kind=ProfileKind.RAMP,
                baseline=0.0,
                amplitude=1.0,
                period_minutes=-5.0,
            )

    @pytest.mark.unit
    def test_constant_any_period_accepted(self) -> None:
        """CONSTANT ignores period_minutes (no validation)."""
        p = ChannelProfile(
            kind=ProfileKind.CONSTANT,
            baseline=5.0,
            period_minutes=0.0,
        )
        assert p.evaluate(0.0) == 5.0

    @pytest.mark.unit
    def test_step_any_period_accepted(self) -> None:
        """STEP ignores period_minutes (no validation)."""
        p = ChannelProfile(
            kind=ProfileKind.STEP,
            baseline=5.0,
            amplitude=3.0,
            step_time_minutes=10.0,
            period_minutes=0.0,
        )
        assert p.evaluate(10.0) == 8.0

    # -- Frozen --

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """ChannelProfile is frozen — attribute assignment must raise."""
        p = ChannelProfile(kind=ProfileKind.CONSTANT, baseline=1.0)
        with pytest.raises(AttributeError):
            p.baseline = 2.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestSyntheticWeatherConstant — factory and defaults
# ---------------------------------------------------------------------------


class TestSyntheticWeatherConstant:
    """Tests for SyntheticWeather.constant() factory."""

    @pytest.mark.unit
    def test_constant_defaults(self) -> None:
        """Default constant weather: T_out=0, GHI=0, wind=0, humidity=50."""
        w = SyntheticWeather.constant()
        p = w.get(0.0)
        assert p.T_out == 0.0
        assert p.GHI == 0.0
        assert p.wind_speed == 0.0
        assert p.humidity == 50.0

    @pytest.mark.unit
    def test_constant_custom_values(self) -> None:
        """Custom constant values are returned at any time."""
        w = SyntheticWeather.constant(
            T_out=-15.0,
            GHI=300.0,
            wind_speed=5.0,
            humidity=80.0,
        )
        for t in [0.0, 60.0, 1440.0, -10.0]:
            p = w.get(t)
            assert p.T_out == -15.0
            assert p.GHI == 300.0
            assert p.wind_speed == 5.0
            assert p.humidity == 80.0

    @pytest.mark.unit
    def test_constant_time_invariant(self) -> None:
        """Constant weather gives the same point at different times."""
        w = SyntheticWeather.constant(T_out=5.0)
        assert w.get(0.0) == w.get(999.0)


# ---------------------------------------------------------------------------
# TestSyntheticWeatherStep — step on T_out, others constant
# ---------------------------------------------------------------------------


class TestSyntheticWeatherStep:
    """Tests for SyntheticWeather.step_t_out() factory."""

    @pytest.mark.unit
    def test_step_before_step_time(self) -> None:
        """T_out is baseline before step_time."""
        w = SyntheticWeather.step_t_out(
            baseline=-5.0,
            amplitude=15.0,
            step_time_minutes=120.0,
        )
        p = w.get(60.0)
        assert p.T_out == -5.0

    @pytest.mark.unit
    def test_step_at_step_time(self) -> None:
        """T_out is baseline + amplitude at step_time."""
        w = SyntheticWeather.step_t_out(
            baseline=-5.0,
            amplitude=15.0,
            step_time_minutes=120.0,
        )
        p = w.get(120.0)
        assert p.T_out == 10.0

    @pytest.mark.unit
    def test_step_after_step_time(self) -> None:
        """T_out is baseline + amplitude after step_time."""
        w = SyntheticWeather.step_t_out(
            baseline=-5.0,
            amplitude=15.0,
            step_time_minutes=120.0,
        )
        p = w.get(240.0)
        assert p.T_out == 10.0

    @pytest.mark.unit
    def test_step_other_channels_constant(self) -> None:
        """GHI, wind_speed, humidity remain constant during step."""
        w = SyntheticWeather.step_t_out(
            baseline=0.0,
            amplitude=10.0,
            step_time_minutes=60.0,
            GHI=100.0,
            wind_speed=2.0,
            humidity=70.0,
        )
        for t in [0.0, 30.0, 60.0, 120.0]:
            p = w.get(t)
            assert p.GHI == 100.0
            assert p.wind_speed == 2.0
            assert p.humidity == 70.0


# ---------------------------------------------------------------------------
# TestSyntheticWeatherRamp — ramp on T_out
# ---------------------------------------------------------------------------


class TestSyntheticWeatherRamp:
    """Tests for SyntheticWeather.ramp_t_out() factory."""

    @pytest.mark.unit
    def test_ramp_at_start(self) -> None:
        """T_out at t=0 is baseline."""
        w = SyntheticWeather.ramp_t_out(
            baseline=-10.0,
            amplitude=20.0,
            period_minutes=100.0,
        )
        assert w.get(0.0).T_out == pytest.approx(-10.0)

    @pytest.mark.unit
    def test_ramp_at_midpoint(self) -> None:
        """T_out at t=period/2 is baseline + amplitude/2."""
        w = SyntheticWeather.ramp_t_out(
            baseline=-10.0,
            amplitude=20.0,
            period_minutes=100.0,
        )
        assert w.get(50.0).T_out == pytest.approx(0.0)

    @pytest.mark.unit
    def test_ramp_at_end(self) -> None:
        """T_out at t=period is baseline + amplitude."""
        w = SyntheticWeather.ramp_t_out(
            baseline=-10.0,
            amplitude=20.0,
            period_minutes=100.0,
        )
        assert w.get(100.0).T_out == pytest.approx(10.0)

    @pytest.mark.unit
    def test_ramp_clamped_beyond(self) -> None:
        """T_out beyond period stays at baseline + amplitude."""
        w = SyntheticWeather.ramp_t_out(
            baseline=-10.0,
            amplitude=20.0,
            period_minutes=100.0,
        )
        assert w.get(200.0).T_out == pytest.approx(10.0)

    @pytest.mark.unit
    def test_ramp_other_channels_constant(self) -> None:
        """Non-T_out channels remain constant during ramp."""
        w = SyntheticWeather.ramp_t_out(
            baseline=0.0,
            amplitude=10.0,
            period_minutes=60.0,
            GHI=50.0,
            wind_speed=1.0,
            humidity=40.0,
        )
        p = w.get(30.0)
        assert p.GHI == 50.0
        assert p.wind_speed == 1.0
        assert p.humidity == 40.0


# ---------------------------------------------------------------------------
# TestSyntheticWeatherSinusoidal — sinusoidal T_out
# ---------------------------------------------------------------------------


class TestSyntheticWeatherSinusoidal:
    """Tests for SyntheticWeather.sinusoidal_t_out() factory."""

    @pytest.mark.unit
    def test_sinusoidal_at_zero(self) -> None:
        """T_out at t=0 equals baseline (sin(0) = 0)."""
        w = SyntheticWeather.sinusoidal_t_out(
            baseline=5.0,
            amplitude=10.0,
            period_minutes=1440.0,
        )
        assert w.get(0.0).T_out == pytest.approx(5.0)

    @pytest.mark.unit
    def test_sinusoidal_at_quarter_period(self) -> None:
        """T_out at t=period/4 equals baseline + amplitude."""
        w = SyntheticWeather.sinusoidal_t_out(
            baseline=5.0,
            amplitude=10.0,
            period_minutes=1440.0,
        )
        assert w.get(360.0).T_out == pytest.approx(15.0)

    @pytest.mark.unit
    def test_sinusoidal_at_half_period(self) -> None:
        """T_out at t=period/2 returns back to baseline."""
        w = SyntheticWeather.sinusoidal_t_out(
            baseline=5.0,
            amplitude=10.0,
            period_minutes=1440.0,
        )
        assert w.get(720.0).T_out == pytest.approx(5.0)

    @pytest.mark.unit
    def test_sinusoidal_at_three_quarter_period(self) -> None:
        """T_out at t=3*period/4 equals baseline - amplitude."""
        w = SyntheticWeather.sinusoidal_t_out(
            baseline=5.0,
            amplitude=10.0,
            period_minutes=1440.0,
        )
        assert w.get(1080.0).T_out == pytest.approx(-5.0)

    @pytest.mark.unit
    def test_sinusoidal_periodicity(self) -> None:
        """Value at t must equal value at t + period."""
        w = SyntheticWeather.sinusoidal_t_out(
            baseline=0.0,
            amplitude=8.0,
            period_minutes=120.0,
        )
        t = 37.0
        assert w.get(t).T_out == pytest.approx(w.get(t + 120.0).T_out)

    @pytest.mark.unit
    def test_sinusoidal_default_period(self) -> None:
        """Default period is 1440 minutes (one day)."""
        w = SyntheticWeather.sinusoidal_t_out(baseline=0.0, amplitude=5.0)
        # At t=360 (quarter of 1440), T_out = 0 + 5*sin(pi/2) = 5
        assert w.get(360.0).T_out == pytest.approx(5.0)

    @pytest.mark.unit
    def test_sinusoidal_other_channels_constant(self) -> None:
        """Non-T_out channels remain constant during sinusoidal variation."""
        w = SyntheticWeather.sinusoidal_t_out(
            baseline=0.0,
            amplitude=10.0,
            period_minutes=60.0,
            GHI=200.0,
            wind_speed=4.0,
            humidity=55.0,
        )
        for t in [0.0, 15.0, 30.0, 45.0]:
            p = w.get(t)
            assert p.GHI == 200.0
            assert p.wind_speed == 4.0
            assert p.humidity == 55.0


# ---------------------------------------------------------------------------
# TestWeatherSourceProtocol — isinstance check
# ---------------------------------------------------------------------------


class TestWeatherSourceProtocol:
    """Tests for WeatherSource protocol compliance."""

    @pytest.mark.unit
    def test_synthetic_weather_is_weather_source(self) -> None:
        """SyntheticWeather.constant() must satisfy isinstance(x, WeatherSource)."""
        w = SyntheticWeather.constant()
        assert isinstance(w, WeatherSource)

    @pytest.mark.unit
    def test_arbitrary_class_with_get_is_weather_source(self) -> None:
        """Any class with a matching get() signature satisfies the protocol."""

        class MyWeather:
            def get(self, t_minutes: float) -> WeatherPoint:
                return WeatherPoint(T_out=0.0, GHI=0.0, wind_speed=0.0, humidity=0.0)

        assert isinstance(MyWeather(), WeatherSource)

    @pytest.mark.unit
    def test_class_without_get_is_not_weather_source(self) -> None:
        """A class without get() does not satisfy the protocol."""

        class NotWeather:
            pass

        assert not isinstance(NotWeather(), WeatherSource)


# ---------------------------------------------------------------------------
# TestSyntheticWeatherDirectInit — direct constructor usage
# ---------------------------------------------------------------------------


class TestSyntheticWeatherDirectInit:
    """Tests for direct SyntheticWeather construction with ChannelProfiles."""

    @pytest.mark.unit
    def test_all_channels_sinusoidal(self) -> None:
        """All four channels can be sinusoidal independently."""
        w = SyntheticWeather(
            t_out=ChannelProfile(
                kind=ProfileKind.SINUSOIDAL,
                baseline=0.0,
                amplitude=10.0,
                period_minutes=60.0,
            ),
            ghi=ChannelProfile(
                kind=ProfileKind.SINUSOIDAL,
                baseline=500.0,
                amplitude=500.0,
                period_minutes=1440.0,
            ),
            wind_speed=ChannelProfile(
                kind=ProfileKind.RAMP,
                baseline=0.0,
                amplitude=10.0,
                period_minutes=120.0,
            ),
            humidity=ChannelProfile(
                kind=ProfileKind.STEP,
                baseline=50.0,
                amplitude=20.0,
                step_time_minutes=30.0,
            ),
        )
        # At t=15 (quarter of 60 for T_out), T_out = 0 + 10*sin(pi/2) = 10
        p = w.get(15.0)
        assert p.T_out == pytest.approx(10.0)
        # wind_speed ramp at t=15: progress=15/120=0.125 -> 0+10*0.125=1.25
        assert p.wind_speed == pytest.approx(1.25)
        # humidity step: t=15 < 30 -> 50
        assert p.humidity == pytest.approx(50.0)

    @pytest.mark.unit
    def test_zero_amplitude_all_profiles(self) -> None:
        """Zero amplitude returns baseline for any profile kind."""
        for kind in ProfileKind:
            kwargs: dict[str, object] = {
                "kind": kind,
                "baseline": 42.0,
                "amplitude": 0.0,
            }
            if kind in (ProfileKind.SINUSOIDAL, ProfileKind.RAMP):
                kwargs["period_minutes"] = 60.0
            p = ChannelProfile(**kwargs)  # type: ignore[arg-type]
            assert p.evaluate(0.0) == pytest.approx(42.0)
            assert p.evaluate(30.0) == pytest.approx(42.0)
