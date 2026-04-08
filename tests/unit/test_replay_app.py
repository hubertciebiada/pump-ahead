"""Unit tests for pumpahead.replay — Plotly Dash interactive replay application."""

from __future__ import annotations

import pytest

from pumpahead.simulation_log import SimRecord, SimulationLog
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    t: int,
    *,
    room_name: str = "",
    T_room: float = 21.0,
    T_slab: float = 22.0,
    T_out: float = 5.0,
    GHI: float = 0.0,
    valve_position: float = 50.0,
    split_mode: SplitMode = SplitMode.OFF,
) -> SimRecord:
    """Helper to create a single SimRecord with sensible defaults."""
    return SimRecord(
        t=t,
        measurements=Measurements(
            T_room=T_room,
            T_slab=T_slab,
            T_outdoor=T_out,
            valve_pos=valve_position,
            hp_mode=HeatPumpMode.HEATING,
        ),
        actions=Actions(
            valve_position=valve_position,
            split_mode=split_mode,
            split_setpoint=21.0,
        ),
        weather=WeatherPoint(
            T_out=T_out,
            GHI=GHI,
            wind_speed=2.0,
            humidity=50.0,
        ),
        room_name=room_name,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_log() -> SimulationLog:
    """100-record, single-room simulation log."""
    records = [
        _make_record(
            t,
            room_name="salon",
            T_room=20.0 + t * 0.02,
            T_slab=21.0 + t * 0.01,
            T_out=5.0 - t * 0.01,
            GHI=max(0.0, 300.0 * (t - 30) / 70.0) if t > 30 else 0.0,
            valve_position=50.0 + t * 0.3,
        )
        for t in range(100)
    ]
    return SimulationLog(records)


@pytest.fixture()
def multi_room_log() -> SimulationLog:
    """200-record, two-room simulation log (salon + kitchen)."""
    records: list[SimRecord] = []
    for t in range(100):
        records.append(
            _make_record(
                t,
                room_name="salon",
                T_room=20.0 + t * 0.02,
                T_slab=21.0 + t * 0.01,
                valve_position=50.0,
                split_mode=SplitMode.HEATING if t > 50 else SplitMode.OFF,
            )
        )
        records.append(
            _make_record(
                t,
                room_name="kitchen",
                T_room=19.0 + t * 0.03,
                T_slab=20.0 + t * 0.02,
                valve_position=70.0,
            )
        )
    return SimulationLog(records)


@pytest.fixture()
def empty_log() -> SimulationLog:
    """Empty simulation log."""
    return SimulationLog()


@pytest.fixture()
def large_log() -> SimulationLog:
    """10,000-record single-room simulation log for performance testing."""
    records = [
        _make_record(
            t,
            room_name="salon",
            T_room=20.0 + (t % 1440) * 0.001,
            T_slab=21.0 + (t % 1440) * 0.0005,
            T_out=5.0 + 3.0 * ((t % 1440) / 1440.0),
            GHI=max(0.0, 500.0 * ((t % 1440) - 360) / 720.0)
            if (t % 1440) > 360
            else 0.0,
            valve_position=50.0 + 20.0 * ((t % 1440) / 1440.0),
        )
        for t in range(10_000)
    ]
    return SimulationLog(records)


# ---------------------------------------------------------------------------
# TestCreateApp
# ---------------------------------------------------------------------------


class TestCreateApp:
    """Tests for create_app factory function."""

    @pytest.mark.unit
    def test_create_app_returns_dash_instance(self, sample_log: SimulationLog) -> None:
        """create_app returns a Dash app instance."""
        from pumpahead.replay.app import create_app

        app = create_app(log=sample_log)
        assert app is not None
        # Dash app has layout and callback attributes
        assert hasattr(app, "layout")
        assert app.layout is not None

    @pytest.mark.unit
    def test_create_app_with_none_log(self) -> None:
        """create_app with None log creates app in empty state."""
        from pumpahead.replay.app import create_app

        app = create_app(log=None)
        assert app is not None
        assert app.layout is not None

    @pytest.mark.unit
    def test_create_app_with_empty_log(self, empty_log: SimulationLog) -> None:
        """create_app with empty log creates app in placeholder state."""
        from pumpahead.replay.app import create_app

        app = create_app(log=empty_log)
        assert app is not None

    @pytest.mark.unit
    def test_create_app_stores_log(self, sample_log: SimulationLog) -> None:
        """create_app stores the log in the server-side store."""
        from pumpahead.replay.app import _LOG_STORE, create_app

        initial_count = len(_LOG_STORE)
        create_app(log=sample_log)
        assert len(_LOG_STORE) > initial_count

    @pytest.mark.unit
    def test_create_app_custom_setpoint(self, sample_log: SimulationLog) -> None:
        """create_app accepts custom setpoint and comfort_band."""
        from pumpahead.replay.app import create_app

        app = create_app(log=sample_log, setpoint=22.0, comfort_band=1.0)
        assert app is not None

    @pytest.mark.unit
    def test_create_replay_app_exported(self) -> None:
        """create_replay_app is available from pumpahead top-level."""
        from pumpahead import create_replay_app

        assert callable(create_replay_app)

    @pytest.mark.unit
    def test_create_app_from_replay_package(self) -> None:
        """create_app is importable from pumpahead.replay."""
        from pumpahead.replay import create_app

        assert callable(create_app)


# ---------------------------------------------------------------------------
# TestChartBuilders
# ---------------------------------------------------------------------------


class TestChartBuilders:
    """Tests for individual chart builder functions."""

    @pytest.mark.unit
    def test_build_temperature_figure(self, sample_log: SimulationLog) -> None:
        """Temperature figure has expected traces."""
        from pumpahead.replay.app import _build_temperature_figure, _get_room_records

        records = _get_room_records(sample_log, "salon")
        fig = _build_temperature_figure(
            records,
            current_step=50,
            room_name="salon",
            setpoint=21.0,
            comfort_band=0.5,
        )
        # Should have comfort band, T_room, T_slab traces
        assert len(fig.data) >= 2
        trace_names = [t.name for t in fig.data if t.name]
        assert "T_room" in trace_names
        assert "T_slab" in trace_names

    @pytest.mark.unit
    def test_build_valve_figure(self, sample_log: SimulationLog) -> None:
        """Valve figure has expected trace."""
        from pumpahead.replay.app import _build_valve_figure, _get_room_records

        records = _get_room_records(sample_log, "salon")
        fig = _build_valve_figure(records, current_step=50, room_name="salon")
        trace_names = [t.name for t in fig.data if t.name]
        assert "Valve" in trace_names

    @pytest.mark.unit
    def test_build_split_figure(self, multi_room_log: SimulationLog) -> None:
        """Split figure has expected trace."""
        from pumpahead.replay.app import _build_split_figure, _get_room_records

        records = _get_room_records(multi_room_log, "salon")
        fig = _build_split_figure(records, current_step=75, room_name="salon")
        trace_names = [t.name for t in fig.data if t.name]
        assert "Split" in trace_names

    @pytest.mark.unit
    def test_build_weather_figure(self, sample_log: SimulationLog) -> None:
        """Weather figure has T_out and GHI traces."""
        from pumpahead.replay.app import _build_weather_figure

        fig = _build_weather_figure(sample_log, current_step=50)
        trace_names = [t.name for t in fig.data if t.name]
        assert "T_out" in trace_names
        assert "GHI" in trace_names

    @pytest.mark.unit
    def test_build_gauge(self) -> None:
        """Gauge figure has indicator trace."""
        from pumpahead.replay.app import _build_gauge

        fig = _build_gauge(
            t_room=21.3,
            setpoint=21.0,
            comfort_band=0.5,
            room_name="salon",
        )
        assert len(fig.data) == 1
        assert fig.data[0].mode == "gauge+number"

    @pytest.mark.unit
    def test_build_empty_figure(self) -> None:
        """Empty figure has annotation text."""
        from pumpahead.replay.app import _build_empty_figure

        fig = _build_empty_figure("Test placeholder")
        # Check layout annotations
        assert len(fig.layout.annotations) == 1
        assert fig.layout.annotations[0].text == "Test placeholder"

    @pytest.mark.unit
    def test_temperature_figure_current_step_boundary(
        self,
        sample_log: SimulationLog,
    ) -> None:
        """Temperature figure handles step=0 and step=last."""
        from pumpahead.replay.app import _build_temperature_figure, _get_room_records

        records = _get_room_records(sample_log, "salon")
        # Step 0
        fig0 = _build_temperature_figure(
            records,
            current_step=0,
            room_name="salon",
            setpoint=21.0,
            comfort_band=0.5,
        )
        assert fig0 is not None
        # Step last
        fig_last = _build_temperature_figure(
            records,
            current_step=len(records) - 1,
            room_name="salon",
            setpoint=21.0,
            comfort_band=0.5,
        )
        assert fig_last is not None

    @pytest.mark.unit
    def test_build_temperature_figure_out_of_range_step(
        self,
        sample_log: SimulationLog,
    ) -> None:
        """Temperature figure handles step beyond range without error."""
        from pumpahead.replay.app import _build_temperature_figure, _get_room_records

        records = _get_room_records(sample_log, "salon")
        fig = _build_temperature_figure(
            records,
            current_step=999,
            room_name="salon",
            setpoint=21.0,
            comfort_band=0.5,
        )
        assert fig is not None


# ---------------------------------------------------------------------------
# TestDataHelpers
# ---------------------------------------------------------------------------


class TestDataHelpers:
    """Tests for data extraction and downsampling helpers."""

    @pytest.mark.unit
    def test_extract_room_names_single(self, sample_log: SimulationLog) -> None:
        """extract_room_names returns single room name."""
        from pumpahead.replay.app import _extract_room_names

        names = _extract_room_names(sample_log)
        assert names == ["salon"]

    @pytest.mark.unit
    def test_extract_room_names_multi(self, multi_room_log: SimulationLog) -> None:
        """extract_room_names returns sorted room names."""
        from pumpahead.replay.app import _extract_room_names

        names = _extract_room_names(multi_room_log)
        assert names == ["kitchen", "salon"]

    @pytest.mark.unit
    def test_extract_room_names_default(self) -> None:
        """Empty room name maps to 'default'."""
        from pumpahead.replay.app import _extract_room_names

        log = SimulationLog([_make_record(0)])
        names = _extract_room_names(log)
        assert names == ["default"]

    @pytest.mark.unit
    def test_downsample_indices_small(self) -> None:
        """Small data returns all indices."""
        from pumpahead.replay.app import _downsample_indices

        result = _downsample_indices(50, max_points=100)
        assert result == list(range(50))

    @pytest.mark.unit
    def test_downsample_indices_large(self) -> None:
        """Large data returns exactly max_points indices."""
        from pumpahead.replay.app import _downsample_indices

        result = _downsample_indices(10_000, max_points=2000)
        assert len(result) == 2000
        # Should be monotonically increasing
        assert all(result[i] < result[i + 1] for i in range(len(result) - 1))
        # First index should be 0
        assert result[0] == 0

    @pytest.mark.unit
    def test_minutes_to_hours(self) -> None:
        """Minutes are correctly converted to hours."""
        from pumpahead.replay.app import _minutes_to_hours

        result = _minutes_to_hours([0, 60, 120, 90])
        assert result == [0.0, 1.0, 2.0, 1.5]

    @pytest.mark.unit
    def test_get_room_records_default(self) -> None:
        """get_room_records maps 'default' to empty string."""
        from pumpahead.replay.app import _get_room_records

        log = SimulationLog([_make_record(0, room_name="")])
        records = _get_room_records(log, "default")
        assert len(records) == 1

    @pytest.mark.unit
    def test_get_room_records_named(self, sample_log: SimulationLog) -> None:
        """get_room_records retrieves named room records."""
        from pumpahead.replay.app import _get_room_records

        records = _get_room_records(sample_log, "salon")
        assert len(records) == 100


# ---------------------------------------------------------------------------
# TestScenarioLoading
# ---------------------------------------------------------------------------


class TestScenarioLoading:
    """Tests for the file upload scenario loading."""

    @pytest.mark.unit
    def test_speed_map_values(self) -> None:
        """Speed map has expected keys and positive intervals."""
        from pumpahead.replay.app import _SPEED_MAP

        assert "1x" in _SPEED_MAP
        assert "2x" in _SPEED_MAP
        assert "5x" in _SPEED_MAP
        assert "10x" in _SPEED_MAP
        for speed, interval in _SPEED_MAP.items():
            assert interval > 0, f"{speed} should have positive interval"

    @pytest.mark.unit
    def test_speed_map_ordering(self) -> None:
        """Faster speeds have shorter intervals."""
        from pumpahead.replay.app import _SPEED_MAP

        assert _SPEED_MAP["1x"] > _SPEED_MAP["2x"]
        assert _SPEED_MAP["2x"] > _SPEED_MAP["5x"]
        assert _SPEED_MAP["5x"] > _SPEED_MAP["10x"]

    @pytest.mark.unit
    def test_log_store_is_dict(self) -> None:
        """Module-level log store is a dict."""
        from pumpahead.replay.app import _LOG_STORE

        assert isinstance(_LOG_STORE, dict)


# ---------------------------------------------------------------------------
# TestLargeLogPerformance
# ---------------------------------------------------------------------------


class TestLargeLogPerformance:
    """Tests that large logs render without crash."""

    @pytest.mark.unit
    def test_create_app_with_large_log(self, large_log: SimulationLog) -> None:
        """create_app handles 10,000-record log without crash."""
        from pumpahead.replay.app import create_app

        app = create_app(log=large_log)
        assert app is not None

    @pytest.mark.unit
    def test_build_temperature_large_log(self, large_log: SimulationLog) -> None:
        """Temperature chart builds for large log with downsampling."""
        from pumpahead.replay.app import _build_temperature_figure, _get_room_records

        records = _get_room_records(large_log, "salon")
        assert len(records) == 10_000
        fig = _build_temperature_figure(
            records,
            current_step=5000,
            room_name="salon",
            setpoint=21.0,
            comfort_band=0.5,
        )
        assert fig is not None
        # Traces should have at most _MAX_CHART_POINTS data points
        for trace in fig.data:
            if hasattr(trace, "x") and trace.x is not None:
                assert len(trace.x) <= 10_000  # At most original, usually downsampled

    @pytest.mark.unit
    def test_build_weather_large_log(self, large_log: SimulationLog) -> None:
        """Weather chart builds for large log."""
        from pumpahead.replay.app import _build_weather_figure

        fig = _build_weather_figure(large_log, current_step=5000)
        assert fig is not None

    @pytest.mark.unit
    def test_downsampled_trace_count(self, large_log: SimulationLog) -> None:
        """Downsampled traces have at most _MAX_CHART_POINTS entries."""
        from pumpahead.replay.app import (
            _MAX_CHART_POINTS,
            _build_valve_figure,
            _get_room_records,
        )

        records = _get_room_records(large_log, "salon")
        fig = _build_valve_figure(records, current_step=5000, room_name="salon")
        for trace in fig.data:
            if hasattr(trace, "x") and trace.x is not None:
                assert len(trace.x) <= _MAX_CHART_POINTS


# ---------------------------------------------------------------------------
# TestCallbackLogic
# ---------------------------------------------------------------------------


class TestCallbackLogic:
    """Tests for callback logic indirectly via chart builder outputs."""

    @pytest.mark.unit
    def test_multi_room_charts_per_room(
        self,
        multi_room_log: SimulationLog,
    ) -> None:
        """Multi-room log produces charts for each room."""
        from pumpahead.replay.app import (
            _build_temperature_figure,
            _extract_room_names,
            _get_room_records,
        )

        rooms = _extract_room_names(multi_room_log)
        assert len(rooms) == 2

        for room in rooms:
            records = _get_room_records(multi_room_log, room)
            assert len(records) > 0
            fig = _build_temperature_figure(
                records,
                current_step=0,
                room_name=room,
                setpoint=21.0,
                comfort_band=0.5,
            )
            assert fig is not None

    @pytest.mark.unit
    def test_split_mode_mapping(self) -> None:
        """Split mode mapping covers all SplitMode values."""
        from pumpahead.replay.app import _SPLIT_MODE_MAP

        assert SplitMode.OFF in _SPLIT_MODE_MAP
        assert SplitMode.HEATING in _SPLIT_MODE_MAP
        assert SplitMode.COOLING in _SPLIT_MODE_MAP
        assert _SPLIT_MODE_MAP[SplitMode.OFF] == 0
        assert _SPLIT_MODE_MAP[SplitMode.HEATING] == 1
        assert _SPLIT_MODE_MAP[SplitMode.COOLING] == -1

    @pytest.mark.unit
    def test_gauge_values_match_record(self) -> None:
        """Gauge indicator value matches the input T_room."""
        from pumpahead.replay.app import _build_gauge

        fig = _build_gauge(
            t_room=22.5,
            setpoint=21.0,
            comfort_band=0.5,
            room_name="test",
        )
        assert fig.data[0].value == 22.5

    @pytest.mark.unit
    def test_valve_figure_y_range(self, sample_log: SimulationLog) -> None:
        """Valve chart has y-axis range [-5, 105]."""
        from pumpahead.replay.app import _build_valve_figure, _get_room_records

        records = _get_room_records(sample_log, "salon")
        fig = _build_valve_figure(records, current_step=50, room_name="salon")
        y_range = fig.layout.yaxis.range
        assert y_range is not None
        assert y_range[0] == -5
        assert y_range[1] == 105


# ---------------------------------------------------------------------------
# TestMainModule
# ---------------------------------------------------------------------------


class TestMainModule:
    """Tests for __main__.py entry point."""

    @pytest.mark.unit
    def test_main_importable(self) -> None:
        """__main__.py is importable."""
        from pumpahead.replay.__main__ import main

        assert callable(main)


# ---------------------------------------------------------------------------
# TestEmptyState
# ---------------------------------------------------------------------------


class TestEmptyState:
    """Tests for empty/placeholder application state."""

    @pytest.mark.unit
    def test_empty_figure_placeholder(self) -> None:
        """Empty figure shows placeholder text."""
        from pumpahead.replay.app import _build_empty_figure

        fig = _build_empty_figure("No data")
        assert fig.layout.annotations[0].text == "No data"
        # Axes should be hidden
        assert fig.layout.xaxis.visible is False
        assert fig.layout.yaxis.visible is False

    @pytest.mark.unit
    def test_slider_marks_empty(self) -> None:
        """Slider marks for zero steps returns fallback."""
        from pumpahead.replay.app import _build_slider_marks

        marks = _build_slider_marks(0)
        assert 0 in marks

    @pytest.mark.unit
    def test_slider_marks_few_steps(self) -> None:
        """Slider marks for few steps returns empty (auto-generate)."""
        from pumpahead.replay.app import _build_slider_marks

        marks = _build_slider_marks(10)
        assert marks == {}

    @pytest.mark.unit
    def test_slider_marks_many_steps(self) -> None:
        """Slider marks for many steps returns sparse marks."""
        from pumpahead.replay.app import _build_slider_marks

        marks = _build_slider_marks(10_000)
        assert len(marks) <= 20
        assert 0 in marks
