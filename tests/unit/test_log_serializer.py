"""Unit tests for pumpahead.log_serializer."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import pytest

from pumpahead.log_serializer import (
    load_json,
    load_pickle,
    save_json,
    save_pickle,
)
from pumpahead.simulation_log import SimRecord, SimulationLog
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(t: int, *, room_name: str = "salon") -> SimRecord:
    """Create a deterministic ``SimRecord`` with values derived from *t*.

    Values vary with *t* so that roundtrip tests can detect corruption
    or data loss (records at different timesteps are never identical).
    """
    return SimRecord(
        t=t,
        measurements=Measurements(
            T_room=20.0 + t * 0.01,
            T_slab=21.0 + t * 0.005,
            T_outdoor=-5.0 + t * 0.02,
            valve_pos=50.0 + t * 0.1,
            hp_mode=HeatPumpMode.HEATING,
        ),
        actions=Actions(
            valve_position=45.0 + t * 0.15,
            split_mode=SplitMode.OFF,
            split_setpoint=22.0,
        ),
        weather=WeatherPoint(
            T_out=-5.0 + t * 0.02,
            GHI=max(0.0, 100.0 * (t - 20) / 80.0) if t > 20 else 0.0,
            wind_speed=3.0 + t * 0.01,
            humidity=55.0 - t * 0.05,
        ),
        room_name=room_name,
    )


def _logs_equal(a: SimulationLog, b: SimulationLog) -> bool:
    """Return whether two logs contain identical records."""
    if len(a) != len(b):
        return False
    return all(ra == rb for ra, rb in zip(a, b, strict=True))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_log() -> SimulationLog:
    """100-record, single-room log with varying data."""
    return SimulationLog([_make_record(t, room_name="salon") for t in range(100)])


@pytest.fixture()
def multi_room_log() -> SimulationLog:
    """200-record, two-room log (salon + kitchen, 100 each)."""
    records = [_make_record(t, room_name="salon") for t in range(100)]
    records += [_make_record(t, room_name="kitchen") for t in range(100)]
    return SimulationLog(records)


@pytest.fixture()
def empty_log() -> SimulationLog:
    """Empty simulation log."""
    return SimulationLog()


# ---------------------------------------------------------------------------
# JSON roundtrip tests
# ---------------------------------------------------------------------------


class TestSaveLoadJson:
    """Tests for ``save_json`` and ``load_json``."""

    @pytest.mark.unit()
    def test_roundtrip_preserves_data(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "log.json"
        save_json(sample_log, fp)
        loaded = load_json(fp)
        assert _logs_equal(sample_log, loaded)

    @pytest.mark.unit()
    def test_roundtrip_multi_room(
        self,
        multi_room_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "multi.json"
        save_json(multi_room_log, fp)
        loaded = load_json(fp)
        assert _logs_equal(multi_room_log, loaded)

    @pytest.mark.unit()
    def test_roundtrip_empty_log(
        self,
        empty_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "empty.json"
        save_json(empty_log, fp)
        loaded = load_json(fp)
        assert len(loaded) == 0

    @pytest.mark.unit()
    def test_pretty_print_readable(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "pretty.json"
        save_json(sample_log, fp, pretty=True)
        text = fp.read_text(encoding="utf-8")
        # Pretty output should have multiple lines and indentation
        assert text.count("\n") > 10
        assert "  " in text

    @pytest.mark.unit()
    def test_compact_smaller_than_pretty(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        compact_fp = tmp_path / "compact.json"
        pretty_fp = tmp_path / "pretty.json"
        save_json(sample_log, compact_fp, pretty=False)
        save_json(sample_log, pretty_fp, pretty=True)
        assert compact_fp.stat().st_size < pretty_fp.stat().st_size

    @pytest.mark.unit()
    def test_json_human_readable(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "readable.json"
        save_json(sample_log, fp, pretty=True)
        data = json.loads(fp.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert isinstance(data["records"], list)
        first = data["records"][0]
        assert "t" in first
        assert "measurements" in first
        assert "actions" in first
        assert "weather" in first
        assert "room_name" in first

    @pytest.mark.unit()
    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_json(tmp_path / "nonexistent.json")

    @pytest.mark.unit()
    def test_corrupted_json_raises(self, tmp_path: Path) -> None:
        fp = tmp_path / "bad.json"
        fp.write_text("this is not json {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_json(fp)

    @pytest.mark.unit()
    def test_wrong_version_raises(self, tmp_path: Path) -> None:
        fp = tmp_path / "future.json"
        fp.write_text(
            json.dumps({"version": 999, "records": []}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="version"):
            load_json(fp)

    @pytest.mark.unit()
    def test_missing_records_key_raises(self, tmp_path: Path) -> None:
        fp = tmp_path / "no_records.json"
        fp.write_text(json.dumps({"version": 1}), encoding="utf-8")
        with pytest.raises(ValueError, match="missing key"):
            load_json(fp)

    @pytest.mark.unit()
    def test_enum_values_as_strings(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "enums.json"
        save_json(sample_log, fp)
        data = json.loads(fp.read_text(encoding="utf-8"))
        first = data["records"][0]
        assert first["measurements"]["hp_mode"] == "heating"
        assert first["actions"]["split_mode"] == "off"

    @pytest.mark.unit()
    def test_all_fields_present(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "fields.json"
        save_json(sample_log, fp)
        data = json.loads(fp.read_text(encoding="utf-8"))
        first = data["records"][0]
        expected_keys = {"t", "room_name", "measurements", "actions", "weather"}
        assert set(first.keys()) == expected_keys
        assert set(first["measurements"].keys()) == {
            "T_room",
            "T_slab",
            "T_outdoor",
            "valve_pos",
            "hp_mode",
        }
        assert set(first["actions"].keys()) == {
            "valve_position",
            "split_mode",
            "split_setpoint",
        }
        assert set(first["weather"].keys()) == {
            "T_out",
            "GHI",
            "wind_speed",
            "humidity",
        }

    @pytest.mark.unit()
    def test_str_path_accepted(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        """Both ``save_json`` and ``load_json`` accept str paths."""
        fp = str(tmp_path / "str_path.json")
        save_json(sample_log, fp)
        loaded = load_json(fp)
        assert _logs_equal(sample_log, loaded)

    @pytest.mark.unit()
    def test_float_precision_roundtrip(self, tmp_path: Path) -> None:
        """Floating-point values survive JSON roundtrip without drift."""
        record = _make_record(17, room_name="precision_room")
        log = SimulationLog([record])
        fp = tmp_path / "precision.json"
        save_json(log, fp)
        loaded = load_json(fp)
        assert loaded[0] == record

    @pytest.mark.unit()
    def test_missing_version_key_raises(self, tmp_path: Path) -> None:
        fp = tmp_path / "no_version.json"
        fp.write_text(json.dumps({"records": []}), encoding="utf-8")
        with pytest.raises(ValueError, match="missing key"):
            load_json(fp)


# ---------------------------------------------------------------------------
# Pickle roundtrip tests
# ---------------------------------------------------------------------------


class TestSaveLoadPickle:
    """Tests for ``save_pickle`` and ``load_pickle``."""

    @pytest.mark.unit()
    def test_roundtrip_preserves_data(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "log.pkl"
        save_pickle(sample_log, fp)
        loaded = load_pickle(fp)
        assert _logs_equal(sample_log, loaded)

    @pytest.mark.unit()
    def test_roundtrip_multi_room(
        self,
        multi_room_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "multi.pkl"
        save_pickle(multi_room_log, fp)
        loaded = load_pickle(fp)
        assert _logs_equal(multi_room_log, loaded)

    @pytest.mark.unit()
    def test_roundtrip_empty_log(
        self,
        empty_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        fp = tmp_path / "empty.pkl"
        save_pickle(empty_log, fp)
        loaded = load_pickle(fp)
        assert len(loaded) == 0

    @pytest.mark.unit()
    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_pickle(tmp_path / "nonexistent.pkl")

    @pytest.mark.unit()
    def test_corrupted_pickle_raises(self, tmp_path: Path) -> None:
        fp = tmp_path / "bad.pkl"
        fp.write_bytes(b"this is not a pickle file\x00\x01\x02")
        with pytest.raises(Exception):  # noqa: B017, PT011
            load_pickle(fp)

    @pytest.mark.unit()
    def test_wrong_type_raises(self, tmp_path: Path) -> None:
        fp = tmp_path / "dict.pkl"
        with fp.open("wb") as f:
            pickle.dump({"not": "a simulation log"}, f)
        with pytest.raises(TypeError, match="Expected SimulationLog"):
            load_pickle(fp)

    @pytest.mark.unit()
    def test_str_path_accepted(
        self,
        sample_log: SimulationLog,
        tmp_path: Path,
    ) -> None:
        """Both ``save_pickle`` and ``load_pickle`` accept str paths."""
        fp = str(tmp_path / "str_path.pkl")
        save_pickle(sample_log, fp)
        loaded = load_pickle(fp)
        assert _logs_equal(sample_log, loaded)


# ---------------------------------------------------------------------------
# Large log tests
# ---------------------------------------------------------------------------


class TestLargeLog:
    """Performance tests with larger logs (10 000 records)."""

    @pytest.mark.unit()
    def test_json_roundtrip_large(self, tmp_path: Path) -> None:
        log = SimulationLog(
            [_make_record(t, room_name="large_room") for t in range(10_000)]
        )
        fp = tmp_path / "large.json"
        save_json(log, fp)
        loaded = load_json(fp)
        assert _logs_equal(log, loaded)

    @pytest.mark.unit()
    def test_pickle_roundtrip_large(self, tmp_path: Path) -> None:
        log = SimulationLog(
            [_make_record(t, room_name="large_room") for t in range(10_000)]
        )
        fp = tmp_path / "large.pkl"
        save_pickle(log, fp)
        loaded = load_pickle(fp)
        assert _logs_equal(log, loaded)
