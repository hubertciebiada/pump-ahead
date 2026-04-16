"""Unit tests for pumpahead.visualization."""

from __future__ import annotations

from pathlib import Path

import pytest

from pumpahead.simulation_log import SimRecord, SimulationLog
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.visualization import (
    _downsample,
    generate_plots,
    plot_dashboard,
    plot_energy,
    plot_room_temperatures,
    plot_splits,
    plot_valves,
    plot_weather,
)
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# Fixtures
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
                T_room=19.5 + t * 0.03,
                T_slab=20.5 + t * 0.015,
                valve_position=70.0,
            )
        )
    return SimulationLog(records)


@pytest.fixture()
def large_log() -> SimulationLog:
    """10 000-record single-room log for downsampling tests."""
    records = [_make_record(t, room_name="salon") for t in range(10_000)]
    return SimulationLog(records)


@pytest.fixture()
def empty_log() -> SimulationLog:
    """Empty simulation log."""
    return SimulationLog()


# ---------------------------------------------------------------------------
# TestDownsample
# ---------------------------------------------------------------------------


class TestDownsample:
    """Tests for the _downsample private helper."""

    @pytest.mark.unit
    def test_below_threshold_unchanged(self) -> None:
        """Data below max_points is returned unchanged."""
        data = [1, 2, 3, 4, 5]
        result = _downsample(data, max_points=10)
        assert result == data

    @pytest.mark.unit
    def test_at_threshold_unchanged(self) -> None:
        """Data exactly at max_points is returned unchanged."""
        data = list(range(100))
        result = _downsample(data, max_points=100)
        assert result == data

    @pytest.mark.unit
    def test_above_threshold_reduced(self) -> None:
        """Data above max_points is reduced to max_points."""
        data = list(range(10_000))
        result = _downsample(data, max_points=500)
        assert len(result) == 500

    @pytest.mark.unit
    def test_preserves_type(self) -> None:
        """Downsampled list preserves element type."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = _downsample(data, max_points=3)
        assert len(result) == 3
        assert all(isinstance(x, float) for x in result)

    @pytest.mark.unit
    def test_empty_list(self) -> None:
        """Empty list returns empty."""
        result = _downsample([], max_points=10)
        assert result == []


# ---------------------------------------------------------------------------
# TestPlotRoomTemperatures
# ---------------------------------------------------------------------------


class TestPlotRoomTemperatures:
    """Tests for the plot_room_temperatures function."""

    @pytest.mark.unit
    def test_returns_figure(self, sample_log: SimulationLog) -> None:
        """Function returns a matplotlib Figure."""
        import matplotlib.figure

        fig = plot_room_temperatures(sample_log, room_name="salon")
        assert isinstance(fig, matplotlib.figure.Figure)
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_setpoint_line_drawn(self, sample_log: SimulationLog) -> None:
        """Setpoint and comfort band are drawn when provided."""
        fig = plot_room_temperatures(sample_log, room_name="salon", setpoint=21.0)
        ax = fig.axes[0]
        # Should have lines for T_room, T_slab, setpoint
        assert len(ax.lines) >= 3
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_room_name_in_title(self, sample_log: SimulationLog) -> None:
        """Room name appears in figure title."""
        fig = plot_room_temperatures(sample_log, room_name="salon")
        ax = fig.axes[0]
        assert "salon" in ax.get_title()
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_default_room_name_in_title(self) -> None:
        """Empty room name shows 'default' in title."""
        log = SimulationLog([_make_record(t) for t in range(10)])
        fig = plot_room_temperatures(log, room_name="")
        ax = fig.axes[0]
        assert "default" in ax.get_title()
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_save_to_file(self, sample_log: SimulationLog, tmp_path: Path) -> None:
        """Figure can be saved as PNG."""
        save_path = tmp_path / "room_temp.png"
        fig = plot_room_temperatures(sample_log, room_name="salon", save_path=save_path)
        assert save_path.exists()
        assert save_path.stat().st_size > 0
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_empty_log_rejected(self, empty_log: SimulationLog) -> None:
        """Empty log raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            plot_room_temperatures(empty_log)


# ---------------------------------------------------------------------------
# TestPlotValves
# ---------------------------------------------------------------------------


class TestPlotValves:
    """Tests for the plot_valves function."""

    @pytest.mark.unit
    def test_returns_figure(self, sample_log: SimulationLog) -> None:
        """Function returns a matplotlib Figure."""
        import matplotlib.figure

        fig = plot_valves(sample_log)
        assert isinstance(fig, matplotlib.figure.Figure)
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_multi_room_lines(self, multi_room_log: SimulationLog) -> None:
        """Multi-room log produces multiple lines."""
        fig = plot_valves(multi_room_log)
        ax = fig.axes[0]
        # Should have at least 2 lines (one per room)
        assert len(ax.lines) >= 2
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_save_to_file(self, sample_log: SimulationLog, tmp_path: Path) -> None:
        """Figure can be saved as PNG."""
        save_path = tmp_path / "valves.png"
        fig = plot_valves(sample_log, save_path=save_path)
        assert save_path.exists()
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_empty_log_rejected(self, empty_log: SimulationLog) -> None:
        """Empty log raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            plot_valves(empty_log)


# ---------------------------------------------------------------------------
# TestPlotSplits
# ---------------------------------------------------------------------------


class TestPlotSplits:
    """Tests for the plot_splits function."""

    @pytest.mark.unit
    def test_returns_figure(self, sample_log: SimulationLog) -> None:
        """Function returns a matplotlib Figure."""
        import matplotlib.figure

        fig = plot_splits(sample_log)
        assert isinstance(fig, matplotlib.figure.Figure)
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_save_to_file(self, sample_log: SimulationLog, tmp_path: Path) -> None:
        """Figure can be saved as PNG."""
        save_path = tmp_path / "splits.png"
        fig = plot_splits(sample_log, save_path=save_path)
        assert save_path.exists()
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_empty_log_rejected(self, empty_log: SimulationLog) -> None:
        """Empty log raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            plot_splits(empty_log)


# ---------------------------------------------------------------------------
# TestPlotWeather
# ---------------------------------------------------------------------------


class TestPlotWeather:
    """Tests for the plot_weather function."""

    @pytest.mark.unit
    def test_returns_figure(self, sample_log: SimulationLog) -> None:
        """Function returns a matplotlib Figure."""
        import matplotlib.figure

        fig = plot_weather(sample_log)
        assert isinstance(fig, matplotlib.figure.Figure)
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_two_subplots(self, sample_log: SimulationLog) -> None:
        """Weather plot has 2 subplots (T_outdoor and GHI)."""
        fig = plot_weather(sample_log)
        assert len(fig.axes) == 2
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_save_to_file(self, sample_log: SimulationLog, tmp_path: Path) -> None:
        """Figure can be saved as PNG."""
        save_path = tmp_path / "weather.png"
        fig = plot_weather(sample_log, save_path=save_path)
        assert save_path.exists()
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_empty_log_rejected(self, empty_log: SimulationLog) -> None:
        """Empty log raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            plot_weather(empty_log)


# ---------------------------------------------------------------------------
# TestPlotEnergy
# ---------------------------------------------------------------------------


class TestPlotEnergy:
    """Tests for the plot_energy function."""

    @pytest.mark.unit
    def test_returns_figure(self, sample_log: SimulationLog) -> None:
        """Function returns a matplotlib Figure."""
        import matplotlib.figure

        fig = plot_energy(sample_log, ufh_nominal_power_w=5000.0)
        assert isinstance(fig, matplotlib.figure.Figure)
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_save_to_file(self, sample_log: SimulationLog, tmp_path: Path) -> None:
        """Figure can be saved as PNG."""
        save_path = tmp_path / "energy.png"
        fig = plot_energy(
            sample_log,
            ufh_nominal_power_w=5000.0,
            split_power_w=2500.0,
            save_path=save_path,
        )
        assert save_path.exists()
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_empty_log_rejected(self, empty_log: SimulationLog) -> None:
        """Empty log raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            plot_energy(empty_log, ufh_nominal_power_w=5000.0)


# ---------------------------------------------------------------------------
# TestPlotDashboard
# ---------------------------------------------------------------------------


class TestPlotDashboard:
    """Tests for the plot_dashboard function."""

    @pytest.mark.unit
    def test_returns_figure(self, sample_log: SimulationLog) -> None:
        """Function returns a matplotlib Figure."""
        import matplotlib.figure

        fig = plot_dashboard(sample_log, setpoint=21.0)
        assert isinstance(fig, matplotlib.figure.Figure)
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_multi_room(self, multi_room_log: SimulationLog) -> None:
        """Multi-room dashboard creates subplots for each room."""
        fig = plot_dashboard(multi_room_log, setpoint=21.0)
        # 2 rooms * 2 rows (temp + valve) + 1 metrics = 5 axes
        assert len(fig.axes) == 5
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_save_to_file(self, sample_log: SimulationLog, tmp_path: Path) -> None:
        """Figure can be saved as PNG."""
        save_path = tmp_path / "dashboard.png"
        fig = plot_dashboard(sample_log, setpoint=21.0, save_path=save_path)
        assert save_path.exists()
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.unit
    def test_empty_log_rejected(self, empty_log: SimulationLog) -> None:
        """Empty log raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            plot_dashboard(empty_log, setpoint=21.0)


# ---------------------------------------------------------------------------
# TestGeneratePlots
# ---------------------------------------------------------------------------


class TestGeneratePlots:
    """Tests for the generate_plots batch function."""

    @pytest.mark.unit
    def test_all_pngs_generated(
        self, sample_log: SimulationLog, tmp_path: Path
    ) -> None:
        """All expected PNG files are generated with energy params."""
        paths = generate_plots(
            sample_log,
            tmp_path,
            scenario_name="test",
            setpoint=21.0,
            ufh_nominal_power_w=5000.0,
            split_power_w=2500.0,
        )
        # 1 room temp + valves + splits + weather + energy + dashboard = 6
        assert len(paths) == 6
        for p in paths:
            assert p.exists()
            assert p.suffix == ".png"
            assert p.stat().st_size > 0

    @pytest.mark.unit
    def test_without_energy_params(
        self, sample_log: SimulationLog, tmp_path: Path
    ) -> None:
        """Energy plot is skipped when power params are None."""
        paths = generate_plots(
            sample_log,
            tmp_path,
            scenario_name="noeng",
        )
        # 1 room temp + valves + splits + weather + dashboard = 5 (no energy)
        assert len(paths) == 5
        names = [p.name for p in paths]
        assert not any("energy" in n for n in names)

    @pytest.mark.unit
    def test_multi_room(self, multi_room_log: SimulationLog, tmp_path: Path) -> None:
        """Multi-room log generates per-room temperature plots."""
        paths = generate_plots(
            multi_room_log,
            tmp_path,
            scenario_name="multi",
            setpoint=21.0,
            ufh_nominal_power_w=5000.0,
            split_power_w=2500.0,
        )
        names = [p.name for p in paths]
        # 2 room temps + valves + splits + weather + energy + dashboard = 7
        assert len(paths) == 7
        assert "multi_salon_temperatures.png" in names
        assert "multi_kitchen_temperatures.png" in names

    @pytest.mark.unit
    def test_creates_output_dir(
        self, sample_log: SimulationLog, tmp_path: Path
    ) -> None:
        """Output directory is created if it doesn't exist."""
        output_dir = tmp_path / "nested" / "output"
        assert not output_dir.exists()
        generate_plots(sample_log, output_dir, scenario_name="test")
        assert output_dir.exists()

    @pytest.mark.unit
    def test_empty_log_rejected(self, empty_log: SimulationLog, tmp_path: Path) -> None:
        """Empty log raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            generate_plots(empty_log, tmp_path)

    @pytest.mark.unit
    def test_returns_paths(self, sample_log: SimulationLog, tmp_path: Path) -> None:
        """generate_plots returns a list of Path objects."""
        paths = generate_plots(sample_log, tmp_path, scenario_name="ret")
        assert isinstance(paths, list)
        assert all(isinstance(p, Path) for p in paths)

    @pytest.mark.unit
    def test_naming_convention(self, sample_log: SimulationLog, tmp_path: Path) -> None:
        """PNG files follow {scenario}_{plot_type}.png naming."""
        paths = generate_plots(
            sample_log,
            tmp_path,
            scenario_name="cold_snap",
            setpoint=21.0,
            ufh_nominal_power_w=5000.0,
            split_power_w=2500.0,
        )
        names = [p.name for p in paths]
        assert "cold_snap_salon_temperatures.png" in names
        assert "cold_snap_valves.png" in names
        assert "cold_snap_splits.png" in names
        assert "cold_snap_weather.png" in names
        assert "cold_snap_energy.png" in names
        assert "cold_snap_dashboard.png" in names

    @pytest.mark.unit
    def test_large_log_downsampled(
        self, large_log: SimulationLog, tmp_path: Path
    ) -> None:
        """Large log is plotted successfully (downsampling applied)."""
        paths = generate_plots(
            large_log,
            tmp_path,
            scenario_name="large",
            max_points=500,
        )
        assert len(paths) > 0
        for p in paths:
            assert p.exists()

    @pytest.mark.unit
    def test_default_room_name_in_filename(self, tmp_path: Path) -> None:
        """Records with empty room_name use 'default' in filenames."""
        log = SimulationLog([_make_record(t) for t in range(10)])
        paths = generate_plots(log, tmp_path, scenario_name="def")
        names = [p.name for p in paths]
        assert "def_default_temperatures.png" in names
