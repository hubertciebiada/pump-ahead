"""Integration tests for Epic #6 -- Visualization, serialization, and replay.

Verifies end-to-end wiring between the three sub-issue modules:
    #41 matplotlib static plots (visualization.py)
    #42 SimulationLog serialization (log_serializer.py)
    #43 Plotly Dash replay (replay/)

Tests exercise cross-module workflows:
    serialize -> load -> generate_plots()
    serialize -> load -> create_app()
    CLI __main__.py with JSON file on disk

All tests are fast, deterministic, and use the
``@pytest.mark.unit`` marker.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from pumpahead.log_serializer import (
    load_json,
    load_json_string,
    load_pickle,
    save_json,
    save_pickle,
)
from pumpahead.simulation_log import SimRecord, SimulationLog
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_record(
    *,
    t: int = 0,
    T_room: float = 21.0,
    T_slab: float = 23.0,
    T_outdoor: float = -5.0,
    valve_pos: float = 50.0,
    hp_mode: HeatPumpMode = HeatPumpMode.HEATING,
    valve_position: float = 50.0,
    split_mode: SplitMode = SplitMode.OFF,
    split_setpoint: float = 0.0,
    T_out: float = -5.0,
    GHI: float = 0.0,
    wind_speed: float = 2.0,
    humidity: float = 50.0,
    room_name: str = "",
) -> SimRecord:
    """Build a SimRecord with sensible defaults for testing."""
    return SimRecord(
        t=t,
        measurements=Measurements(
            T_room=T_room,
            T_slab=T_slab,
            T_outdoor=T_outdoor,
            valve_pos=valve_pos,
            hp_mode=hp_mode,
        ),
        actions=Actions(
            valve_position=valve_position,
            split_mode=split_mode,
            split_setpoint=split_setpoint,
        ),
        weather=WeatherPoint(
            T_out=T_out,
            GHI=GHI,
            wind_speed=wind_speed,
            humidity=humidity,
        ),
        room_name=room_name,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_log() -> SimulationLog:
    """50-record, single-room log with varying data."""
    return SimulationLog(
        [
            _make_record(
                t=i,
                T_room=20.0 + i * 0.02,
                T_slab=22.0 + i * 0.01,
                T_out=-5.0 + i * 0.05,
                GHI=max(0.0, 100.0 * (i - 10) / 40.0) if i > 10 else 0.0,
                valve_position=40.0 + i * 0.2,
                valve_pos=40.0 + i * 0.2,
                room_name="salon",
            )
            for i in range(50)
        ]
    )


@pytest.fixture()
def multi_room_log() -> SimulationLog:
    """100-record, two-room log (salon + kitchen, 50 each)."""
    records: list[SimRecord] = []
    for i in range(50):
        records.append(
            _make_record(
                t=i,
                T_room=20.0 + i * 0.02,
                T_slab=22.0 + i * 0.01,
                valve_position=50.0,
                valve_pos=50.0,
                room_name="salon",
            )
        )
        records.append(
            _make_record(
                t=i,
                T_room=19.0 + i * 0.03,
                T_slab=21.0 + i * 0.015,
                valve_position=60.0,
                valve_pos=60.0,
                room_name="kitchen",
            )
        )
    return SimulationLog(records)


# ---------------------------------------------------------------------------
# TestSerializeThenVisualize
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSerializeThenVisualize:
    """Cross-module tests: serialize a log, load it, then visualize."""

    def test_json_roundtrip_then_generate_plots(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        """JSON roundtrip followed by generate_plots produces non-empty PNGs."""
        from pumpahead.visualization import generate_plots

        json_path = tmp_path / "log.json"
        save_json(sample_log, json_path)
        loaded = load_json(json_path)

        output_dir = tmp_path / "plots"
        paths = generate_plots(loaded, output_dir, scenario_name="test")

        assert len(paths) > 0
        for p in paths:
            assert p.exists()
            assert p.stat().st_size > 0

        # Close all matplotlib figures to avoid resource leak
        import matplotlib.pyplot as plt

        plt.close("all")

    def test_pickle_roundtrip_then_generate_plots(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        """Pickle roundtrip followed by generate_plots produces non-empty PNGs."""
        from pumpahead.visualization import generate_plots

        pkl_path = tmp_path / "log.pkl"
        save_pickle(sample_log, pkl_path)
        loaded = load_pickle(pkl_path)

        output_dir = tmp_path / "plots"
        paths = generate_plots(loaded, output_dir, scenario_name="test_pkl")

        assert len(paths) > 0
        for p in paths:
            assert p.exists()
            assert p.stat().st_size > 0

        import matplotlib.pyplot as plt

        plt.close("all")

    def test_json_roundtrip_then_dashboard_with_metrics(
        self,
        multi_room_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        """JSON roundtrip then plot_dashboard with power params for SimMetrics path."""
        from pumpahead.visualization import plot_dashboard

        json_path = tmp_path / "multi.json"
        save_json(multi_room_log, json_path)
        loaded = load_json(json_path)

        fig = plot_dashboard(
            loaded,
            setpoint=21.0,
            comfort_band=0.5,
            ufh_max_power_w=5000.0,
            split_power_w=2500.0,
        )
        assert fig is not None

        import matplotlib.pyplot as plt

        plt.close(fig)


# ---------------------------------------------------------------------------
# TestSerializeThenReplay
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSerializeThenReplay:
    """Cross-module tests: serialize a log, load it, then create replay app."""

    def test_json_roundtrip_then_create_app(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        """JSON roundtrip followed by create_app returns a working Dash app."""
        from pumpahead.replay import create_app

        json_path = tmp_path / "log.json"
        save_json(sample_log, json_path)
        loaded = load_json(json_path)

        app = create_app(log=loaded)
        assert app is not None
        assert hasattr(app, "layout")
        assert app.layout is not None

    def test_pickle_roundtrip_then_create_app(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        """Pickle roundtrip followed by create_app returns a working Dash app."""
        from pumpahead.replay import create_app

        pkl_path = tmp_path / "log.pkl"
        save_pickle(sample_log, pkl_path)
        loaded = load_pickle(pkl_path)

        app = create_app(log=loaded)
        assert app is not None
        assert hasattr(app, "layout")
        assert app.layout is not None

    def test_load_json_string_then_create_app(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        """load_json_string followed by create_app verifies the new public API."""
        from pumpahead.replay import create_app

        json_path = tmp_path / "log.json"
        save_json(sample_log, json_path)
        text = json_path.read_text(encoding="utf-8")
        loaded = load_json_string(text)

        app = create_app(log=loaded)
        assert app is not None
        assert app.layout is not None


# ---------------------------------------------------------------------------
# TestCliIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCliIntegration:
    """Tests for the __main__.py CLI entry point."""

    def test_main_loads_json_file(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        """CLI main() loads a JSON file and creates the app without error."""
        from pumpahead.replay.__main__ import main

        json_path = tmp_path / "cli_test.json"
        save_json(sample_log, json_path)

        with (
            mock.patch("sys.argv", ["prog", "--log", str(json_path)]),
            mock.patch("pumpahead.replay.app.create_app") as mock_create_app,
        ):
            # Mock create_app to return a mock app that won't start a server
            mock_app = mock.MagicMock()
            mock_create_app.return_value = mock_app

            main()

            mock_create_app.assert_called_once()
            mock_app.run.assert_called_once()
