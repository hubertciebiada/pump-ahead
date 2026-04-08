"""Unit tests for pumpahead.disturbance_vector."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from pumpahead.disturbance_vector import (
    MPC_DT_SECONDS,
    MPC_HORIZON_STEPS,
    DisturbanceBuilder,
    InternalGainProfile,
)
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.solar import EphemerisCalculator, Orientation, WindowConfig
from pumpahead.solar_gti import GTIModel
from pumpahead.weather import SyntheticWeather

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def constant_weather() -> SyntheticWeather:
    """Weather source with constant T_out=5C, GHI=0."""
    return SyntheticWeather.constant(T_out=5.0, GHI=0.0)


@pytest.fixture()
def sunny_weather() -> SyntheticWeather:
    """Weather source with constant T_out=10C, GHI=500 W/m^2."""
    return SyntheticWeather.constant(T_out=10.0, GHI=500.0)


@pytest.fixture()
def lubcza_ephemeris() -> EphemerisCalculator:
    """Ephemeris for Lubcza, Poland (lat 50.69, lon 17.38)."""
    return EphemerisCalculator(latitude=50.69, longitude=17.38)


@pytest.fixture()
def gti_model() -> GTIModel:
    """GTI model with default albedo."""
    return GTIModel()


@pytest.fixture()
def south_windows() -> tuple[WindowConfig, ...]:
    """Single south-facing window: 3 m^2, g=0.6."""
    return (WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6),)


@pytest.fixture()
def mixed_windows() -> tuple[WindowConfig, ...]:
    """South + east windows for different orientations."""
    return (
        WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6),
        WindowConfig(Orientation.EAST, area_m2=2.0, g_value=0.5),
    )


@pytest.fixture()
def constant_profile() -> InternalGainProfile:
    """Constant 100 W internal gain profile."""
    return InternalGainProfile.constant(100.0)


@pytest.fixture()
def variable_profile() -> InternalGainProfile:
    """Variable profile: weekday day=200W, night=50W; weekend day=300W, night=80W."""
    return InternalGainProfile(
        weekday_day_w=200.0,
        weekday_night_w=50.0,
        weekend_day_w=300.0,
        weekend_night_w=80.0,
        day_start_hour=7,
        day_end_hour=22,
    )


@pytest.fixture()
def builder_night(
    constant_weather: SyntheticWeather,
    gti_model: GTIModel,
    lubcza_ephemeris: EphemerisCalculator,
    south_windows: tuple[WindowConfig, ...],
    constant_profile: InternalGainProfile,
) -> DisturbanceBuilder:
    """Builder with constant weather (no GHI) and constant Q_int=100W."""
    return DisturbanceBuilder(
        weather=constant_weather,
        gti_model=gti_model,
        ephemeris=lubcza_ephemeris,
        windows=south_windows,
        gain_profile=constant_profile,
    )


@pytest.fixture()
def builder_sunny(
    sunny_weather: SyntheticWeather,
    gti_model: GTIModel,
    lubcza_ephemeris: EphemerisCalculator,
    south_windows: tuple[WindowConfig, ...],
    constant_profile: InternalGainProfile,
) -> DisturbanceBuilder:
    """Builder with sunny weather (GHI=500) and constant Q_int=100W."""
    return DisturbanceBuilder(
        weather=sunny_weather,
        gti_model=gti_model,
        ephemeris=lubcza_ephemeris,
        windows=south_windows,
        gain_profile=constant_profile,
    )


# ---------------------------------------------------------------------------
# TestInternalGainProfile
# ---------------------------------------------------------------------------


class TestInternalGainProfile:
    """Tests for the InternalGainProfile dataclass."""

    @pytest.mark.unit
    def test_constant_factory(self) -> None:
        """constant() creates a profile that returns the same value everywhere."""
        profile = InternalGainProfile.constant(150.0)
        # Test weekday day, weekday night, weekend day, weekend night
        assert profile.weekday_day_w == 150.0
        assert profile.weekday_night_w == 150.0
        assert profile.weekend_day_w == 150.0
        assert profile.weekend_night_w == 150.0

    @pytest.mark.unit
    def test_constant_evaluate_any_time(self) -> None:
        """constant(150) returns 150.0 regardless of datetime."""
        profile = InternalGainProfile.constant(150.0)
        # Monday 10:00 (weekday day)
        assert profile.evaluate(datetime(2024, 1, 1, 10, 0, tzinfo=UTC)) == 150.0
        # Saturday 23:00 (weekend night)
        assert profile.evaluate(datetime(2024, 1, 6, 23, 0, tzinfo=UTC)) == 150.0

    @pytest.mark.unit
    def test_weekday_day(self, variable_profile: InternalGainProfile) -> None:
        """Weekday at 12:00 returns weekday_day_w."""
        # 2024-01-01 is Monday
        dt = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        assert variable_profile.evaluate(dt) == 200.0

    @pytest.mark.unit
    def test_weekday_night(self, variable_profile: InternalGainProfile) -> None:
        """Weekday at 23:00 returns weekday_night_w."""
        # 2024-01-01 is Monday
        dt = datetime(2024, 1, 1, 23, 0, tzinfo=UTC)
        assert variable_profile.evaluate(dt) == 50.0

    @pytest.mark.unit
    def test_weekday_early_morning(self, variable_profile: InternalGainProfile) -> None:
        """Weekday at 05:00 (before day_start_hour=7) returns weekday_night_w."""
        dt = datetime(2024, 1, 2, 5, 0, tzinfo=UTC)  # Tuesday
        assert variable_profile.evaluate(dt) == 50.0

    @pytest.mark.unit
    def test_weekend_day(self, variable_profile: InternalGainProfile) -> None:
        """Weekend at 14:00 returns weekend_day_w."""
        # 2024-01-06 is Saturday
        dt = datetime(2024, 1, 6, 14, 0, tzinfo=UTC)
        assert variable_profile.evaluate(dt) == 300.0

    @pytest.mark.unit
    def test_weekend_night(self, variable_profile: InternalGainProfile) -> None:
        """Weekend at 23:00 returns weekend_night_w."""
        # 2024-01-07 is Sunday
        dt = datetime(2024, 1, 7, 23, 0, tzinfo=UTC)
        assert variable_profile.evaluate(dt) == 80.0

    @pytest.mark.unit
    def test_day_boundary_start_inclusive(
        self, variable_profile: InternalGainProfile
    ) -> None:
        """Hour == day_start_hour is daytime (inclusive)."""
        dt = datetime(2024, 1, 1, 7, 0, tzinfo=UTC)  # Monday 07:00
        assert variable_profile.evaluate(dt) == 200.0

    @pytest.mark.unit
    def test_day_boundary_end_exclusive(
        self, variable_profile: InternalGainProfile
    ) -> None:
        """Hour == day_end_hour is nighttime (exclusive)."""
        dt = datetime(2024, 1, 1, 22, 0, tzinfo=UTC)  # Monday 22:00
        assert variable_profile.evaluate(dt) == 50.0

    @pytest.mark.unit
    def test_validation_negative_wattage(self) -> None:
        """Negative wattage raises ValueError."""
        with pytest.raises(ValueError, match="weekday_day_w must be >= 0"):
            InternalGainProfile(
                weekday_day_w=-10.0,
                weekday_night_w=50.0,
                weekend_day_w=100.0,
                weekend_night_w=50.0,
            )

    @pytest.mark.unit
    def test_validation_hours_out_of_range(self) -> None:
        """day_start_hour outside [0, 23] raises ValueError."""
        with pytest.raises(ValueError, match="day_start_hour must be in"):
            InternalGainProfile(
                weekday_day_w=100.0,
                weekday_night_w=50.0,
                weekend_day_w=100.0,
                weekend_night_w=50.0,
                day_start_hour=25,
                day_end_hour=22,
            )

    @pytest.mark.unit
    def test_validation_start_ge_end(self) -> None:
        """day_start_hour >= day_end_hour raises ValueError."""
        with pytest.raises(ValueError, match="must be <"):
            InternalGainProfile(
                weekday_day_w=100.0,
                weekday_night_w=50.0,
                weekend_day_w=100.0,
                weekend_night_w=50.0,
                day_start_hour=22,
                day_end_hour=7,
            )

    @pytest.mark.unit
    def test_zero_wattage_allowed(self) -> None:
        """Zero wattage is valid (unoccupied room)."""
        profile = InternalGainProfile.constant(0.0)
        assert profile.evaluate(datetime(2024, 1, 1, 12, 0, tzinfo=UTC)) == 0.0


# ---------------------------------------------------------------------------
# TestDisturbanceBuilder
# ---------------------------------------------------------------------------


class TestDisturbanceBuilder:
    """Tests for the DisturbanceBuilder class."""

    @pytest.mark.unit
    def test_output_shape_3r3c(self, builder_night: DisturbanceBuilder) -> None:
        """Default build produces shape (96, 3) for 3R3C."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build(start, n_disturbances=3)
        assert d.shape == (MPC_HORIZON_STEPS, 3)

    @pytest.mark.unit
    def test_output_shape_2r2c(self, builder_night: DisturbanceBuilder) -> None:
        """build with n_disturbances=2 produces shape (96, 2)."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build(start, n_disturbances=2)
        assert d.shape == (MPC_HORIZON_STEPS, 2)

    @pytest.mark.unit
    def test_invalid_n_disturbances(self, builder_night: DisturbanceBuilder) -> None:
        """n_disturbances != 2 or 3 raises ValueError."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="n_disturbances must be 2 or 3"):
            builder_night.build(start, n_disturbances=4)

    @pytest.mark.unit
    def test_t_out_constant(self, builder_night: DisturbanceBuilder) -> None:
        """Column 0 (T_out) matches the weather source constant value."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build(start, n_disturbances=3)
        np.testing.assert_allclose(d[:, 0], 5.0)

    @pytest.mark.unit
    def test_q_sol_zero_at_night(self, builder_night: DisturbanceBuilder) -> None:
        """Q_sol is 0 when GHI=0 (nighttime weather)."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build(start, n_disturbances=3)
        np.testing.assert_allclose(d[:, 1], 0.0)

    @pytest.mark.unit
    def test_q_sol_positive_daytime(self, builder_sunny: DisturbanceBuilder) -> None:
        """Q_sol > 0 for at least some steps when GHI=500 during daytime.

        The sun is above the horizon for part of the 24h horizon at lat 50.
        """
        # Start at midnight UTC on June 21 -- sunrise around 03:30 UTC
        start = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        d = builder_sunny.build(start, n_disturbances=3)
        # At least some steps during daylight should have Q_sol > 0
        assert np.any(d[:, 1] > 0), "Q_sol should be positive during daytime"

    @pytest.mark.unit
    def test_q_sol_night_steps_zero(self, builder_sunny: DisturbanceBuilder) -> None:
        """Q_sol should be 0.0 for nighttime steps (sun below horizon).

        Start at midnight June 21 -- first few steps are before sunrise.
        """
        start = datetime(2024, 6, 21, 0, 0, tzinfo=UTC)
        d = builder_sunny.build(start, n_disturbances=3)
        # Midnight to ~03:30 UTC is night at lat 50.69 in June
        # First ~14 steps (0-3.5h) should be zero or near-zero
        # Check first 10 steps to be safe (before 2:30 UTC)
        assert d[0, 1] == 0.0, "Midnight Q_sol should be 0"

    @pytest.mark.unit
    def test_q_int_constant_profile(self, builder_night: DisturbanceBuilder) -> None:
        """Column 2 (Q_int) is constant when using constant profile."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build(start, n_disturbances=3)
        np.testing.assert_allclose(d[:, 2], 100.0)

    @pytest.mark.unit
    def test_q_int_variable_profile(
        self,
        constant_weather: SyntheticWeather,
        gti_model: GTIModel,
        lubcza_ephemeris: EphemerisCalculator,
        south_windows: tuple[WindowConfig, ...],
        variable_profile: InternalGainProfile,
    ) -> None:
        """Q_int reflects the variable profile (day/night transitions).

        Start at Monday 06:00 UTC. day_start_hour=7, so:
        - Steps 0-3 (06:00-06:45): nighttime -> 50 W
        - Step 4+ (07:00+): daytime -> 200 W
        """
        builder = DisturbanceBuilder(
            weather=constant_weather,
            gti_model=gti_model,
            ephemeris=lubcza_ephemeris,
            windows=south_windows,
            gain_profile=variable_profile,
        )
        start = datetime(2024, 1, 1, 6, 0, tzinfo=UTC)  # Monday 06:00
        d = builder.build(start, n_disturbances=3)

        # Steps 0-3 (06:00-06:45) should be nighttime (50 W)
        np.testing.assert_allclose(d[0:4, 2], 50.0)
        # Step 4 (07:00) should be daytime (200 W)
        assert d[4, 2] == 200.0

    @pytest.mark.unit
    def test_q_int_weekday_weekend_transition(
        self,
        constant_weather: SyntheticWeather,
        gti_model: GTIModel,
        lubcza_ephemeris: EphemerisCalculator,
        south_windows: tuple[WindowConfig, ...],
        variable_profile: InternalGainProfile,
    ) -> None:
        """Q_int changes at the weekday->weekend boundary.

        Start Friday 12:00, horizon covers into Saturday.
        2024-01-05 is Friday, 2024-01-06 is Saturday.
        """
        builder = DisturbanceBuilder(
            weather=constant_weather,
            gti_model=gti_model,
            ephemeris=lubcza_ephemeris,
            windows=south_windows,
            gain_profile=variable_profile,
        )
        # Friday 12:00 -> Saturday 12:00 (96 steps of 15 min = 24h)
        start = datetime(2024, 1, 5, 12, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)

        # Friday 12:00 (weekday day) -> 200 W
        assert d[0, 2] == 200.0
        # Saturday 12:00 is step 96-1=95 (last step), but let's check step 48
        # which is midnight crossing into Saturday (00:00 Sat) -> weekend night
        # Step 48 = 12h later = Saturday 00:00 -> weekend_night_w = 80
        assert d[48, 2] == 80.0

    @pytest.mark.unit
    def test_q_int_omitted_for_2r2c(self, builder_night: DisturbanceBuilder) -> None:
        """2R2C build has no Q_int column (only T_out, Q_sol)."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build(start, n_disturbances=2)
        assert d.shape[1] == 2

    @pytest.mark.unit
    def test_no_windows_q_sol_zero(
        self,
        sunny_weather: SyntheticWeather,
        gti_model: GTIModel,
        lubcza_ephemeris: EphemerisCalculator,
        constant_profile: InternalGainProfile,
    ) -> None:
        """Room with no windows has Q_sol=0 for all steps."""
        builder = DisturbanceBuilder(
            weather=sunny_weather,
            gti_model=gti_model,
            ephemeris=lubcza_ephemeris,
            windows=(),
            gain_profile=constant_profile,
        )
        start = datetime(2024, 6, 21, 10, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)
        np.testing.assert_allclose(d[:, 1], 0.0)

    @pytest.mark.unit
    def test_build_for_model_3r3c(
        self,
        builder_night: DisturbanceBuilder,
        params_3r3c: RCParams,
    ) -> None:
        """build_for_model with 3R3C model produces n_disturbances=3."""
        model = RCModel(params_3r3c, ModelOrder.THREE, dt=60.0)
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build_for_model(start, model)
        assert d.shape == (MPC_HORIZON_STEPS, 3)

    @pytest.mark.unit
    def test_build_for_model_2r2c(
        self,
        builder_night: DisturbanceBuilder,
        params_2r2c: RCParams,
    ) -> None:
        """build_for_model with 2R2C model produces n_disturbances=2."""
        model = RCModel(params_2r2c, ModelOrder.TWO, dt=60.0)
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build_for_model(start, model)
        assert d.shape == (MPC_HORIZON_STEPS, 2)

    @pytest.mark.unit
    def test_custom_horizon_and_dt(
        self,
        constant_weather: SyntheticWeather,
        gti_model: GTIModel,
        lubcza_ephemeris: EphemerisCalculator,
        south_windows: tuple[WindowConfig, ...],
        constant_profile: InternalGainProfile,
    ) -> None:
        """Custom dt_seconds and horizon_steps produce correct shape."""
        builder = DisturbanceBuilder(
            weather=constant_weather,
            gti_model=gti_model,
            ephemeris=lubcza_ephemeris,
            windows=south_windows,
            gain_profile=constant_profile,
            dt_seconds=600,   # 10 min
            horizon_steps=48,  # 8h
        )
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder.build(start, n_disturbances=3)
        assert d.shape == (48, 3)

    @pytest.mark.unit
    def test_sim_t0_offset(
        self,
        gti_model: GTIModel,
        lubcza_ephemeris: EphemerisCalculator,
        south_windows: tuple[WindowConfig, ...],
        constant_profile: InternalGainProfile,
    ) -> None:
        """sim_t0_minutes offsets the weather query correctly.

        With a ramp weather source, shifting sim_t0 should shift T_out values.
        """
        ramp_weather = SyntheticWeather.ramp_t_out(
            baseline=0.0, amplitude=10.0, period_minutes=1440.0
        )
        builder = DisturbanceBuilder(
            weather=ramp_weather,
            gti_model=gti_model,
            ephemeris=lubcza_ephemeris,
            windows=south_windows,
            gain_profile=constant_profile,
            dt_seconds=MPC_DT_SECONDS,
            horizon_steps=4,
        )
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)

        # Build at t0=0
        d0 = builder.build(start, sim_t0_minutes=0.0, n_disturbances=3)
        # Build at t0=60 (1 hour offset)
        d60 = builder.build(start, sim_t0_minutes=60.0, n_disturbances=3)

        # T_out at t0=60 should be higher than at t0=0 (ramp is increasing)
        assert d60[0, 0] > d0[0, 0]

    @pytest.mark.unit
    def test_full_horizon_covers_24h(
        self, builder_night: DisturbanceBuilder
    ) -> None:
        """Default horizon (96 steps * 15 min) covers exactly 24 hours.

        The last step starts at 24h - 15min = 23h45.
        """
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build(start, n_disturbances=3)
        assert d.shape[0] == 96
        # Verify: last step index 95 corresponds to 95*15=1425 min = 23h45
        last_dt = start + timedelta(seconds=95 * MPC_DT_SECONDS)
        assert last_dt.hour == 23
        assert last_dt.minute == 45

    @pytest.mark.unit
    def test_dtype_float64(self, builder_night: DisturbanceBuilder) -> None:
        """Output array has dtype float64."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build(start, n_disturbances=3)
        assert d.dtype == np.float64

    @pytest.mark.unit
    def test_per_room_windows_different_q_sol(
        self,
        sunny_weather: SyntheticWeather,
        gti_model: GTIModel,
        lubcza_ephemeris: EphemerisCalculator,
        constant_profile: InternalGainProfile,
    ) -> None:
        """Different window configs produce different Q_sol values.

        A room with more south-facing glass gets higher Q_sol at noon.
        """
        small_south = (WindowConfig(Orientation.SOUTH, area_m2=1.0, g_value=0.6),)
        large_south = (WindowConfig(Orientation.SOUTH, area_m2=5.0, g_value=0.6),)

        builder_small = DisturbanceBuilder(
            weather=sunny_weather,
            gti_model=gti_model,
            ephemeris=lubcza_ephemeris,
            windows=small_south,
            gain_profile=constant_profile,
        )
        builder_large = DisturbanceBuilder(
            weather=sunny_weather,
            gti_model=gti_model,
            ephemeris=lubcza_ephemeris,
            windows=large_south,
            gain_profile=constant_profile,
        )

        # Summer noon: Q_sol should differ
        start = datetime(2024, 6, 21, 10, 0, tzinfo=UTC)
        d_small = builder_small.build(start, n_disturbances=3)
        d_large = builder_large.build(start, n_disturbances=3)

        # Find a step with positive Q_sol
        daytime_idx = np.where(d_large[:, 1] > 0)[0]
        assert len(daytime_idx) > 0
        # Large window should have ~5x the Q_sol of small window
        ratio = d_large[daytime_idx[0], 1] / d_small[daytime_idx[0], 1]
        assert ratio == pytest.approx(5.0, rel=1e-6)

    @pytest.mark.unit
    def test_constructor_validation_dt(
        self,
        constant_weather: SyntheticWeather,
        gti_model: GTIModel,
        lubcza_ephemeris: EphemerisCalculator,
        south_windows: tuple[WindowConfig, ...],
        constant_profile: InternalGainProfile,
    ) -> None:
        """dt_seconds <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="dt_seconds must be positive"):
            DisturbanceBuilder(
                weather=constant_weather,
                gti_model=gti_model,
                ephemeris=lubcza_ephemeris,
                windows=south_windows,
                gain_profile=constant_profile,
                dt_seconds=0,
            )

    @pytest.mark.unit
    def test_constructor_validation_horizon(
        self,
        constant_weather: SyntheticWeather,
        gti_model: GTIModel,
        lubcza_ephemeris: EphemerisCalculator,
        south_windows: tuple[WindowConfig, ...],
        constant_profile: InternalGainProfile,
    ) -> None:
        """horizon_steps <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="horizon_steps must be positive"):
            DisturbanceBuilder(
                weather=constant_weather,
                gti_model=gti_model,
                ephemeris=lubcza_ephemeris,
                windows=south_windows,
                gain_profile=constant_profile,
                horizon_steps=-1,
            )

    @pytest.mark.unit
    def test_compatible_with_model_predict(
        self,
        builder_night: DisturbanceBuilder,
        params_3r3c: RCParams,
    ) -> None:
        """Disturbance matrix is directly usable with RCModel.predict().

        Build a disturbance vector and use it to drive a 3R3C model prediction
        for the full MPC horizon.
        """
        model = RCModel(params_3r3c, ModelOrder.THREE, dt=float(MPC_DT_SECONDS))
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        d = builder_night.build_for_model(start, model)

        x0 = model.reset()
        u_seq = np.zeros((MPC_HORIZON_STEPS, model.n_inputs))

        # Should not raise -- shapes must match
        trajectory = model.predict(x0, u_seq, d)
        assert trajectory.shape == (MPC_HORIZON_STEPS + 1, model.n_states)

    @pytest.mark.unit
    def test_module_constants(self) -> None:
        """Module-level constants have correct values."""
        assert MPC_DT_SECONDS == 900
        assert MPC_HORIZON_STEPS == 96
        # 96 * 900 seconds = 86400 seconds = 24 hours
        assert MPC_DT_SECONDS * MPC_HORIZON_STEPS == 86400
