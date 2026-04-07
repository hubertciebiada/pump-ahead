"""Unit tests for SimRecord and SimulationLog."""

import dataclasses

import pytest

from pumpahead.simulation_log import SimRecord, SimulationLog
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_measurements() -> Measurements:
    """Typical room measurement snapshot."""
    return Measurements(
        T_room=21.5,
        T_slab=23.0,
        T_outdoor=-5.0,
        valve_pos=60.0,
        hp_mode=HeatPumpMode.HEATING,
    )


@pytest.fixture()
def sample_actions() -> Actions:
    """Typical controller actions with split heating."""
    return Actions(
        valve_position=55.0,
        split_mode=SplitMode.HEATING,
        split_setpoint=22.0,
    )


@pytest.fixture()
def sample_weather() -> WeatherPoint:
    """Typical winter weather conditions."""
    return WeatherPoint(
        T_out=-4.5,
        GHI=120.0,
        wind_speed=3.5,
        humidity=65.0,
    )


@pytest.fixture()
def sample_record(
    sample_measurements: Measurements,
    sample_actions: Actions,
    sample_weather: WeatherPoint,
) -> SimRecord:
    """A single SimRecord for the salon at t=42."""
    return SimRecord(
        t=42,
        measurements=sample_measurements,
        actions=sample_actions,
        weather=sample_weather,
        room_name="salon",
    )


@pytest.fixture()
def populated_log(
    sample_measurements: Measurements,
    sample_actions: Actions,
    sample_weather: WeatherPoint,
) -> SimulationLog:
    """Log with 100 records: t=0..99, even=salon, odd=kitchen."""
    log = SimulationLog()
    for i in range(100):
        room = "salon" if i % 2 == 0 else "kitchen"
        log.append(
            SimRecord(
                t=i,
                measurements=sample_measurements,
                actions=sample_actions,
                weather=sample_weather,
                room_name=room,
            )
        )
    return log


# ---------------------------------------------------------------------------
# TestSimRecord
# ---------------------------------------------------------------------------


class TestSimRecord:
    """Tests for the SimRecord frozen dataclass."""

    @pytest.mark.unit
    def test_fields_accessible(self, sample_record: SimRecord) -> None:
        """All top-level fields are accessible with correct types."""
        assert sample_record.t == 42
        assert isinstance(sample_record.measurements, Measurements)
        assert isinstance(sample_record.actions, Actions)
        assert isinstance(sample_record.weather, WeatherPoint)
        assert sample_record.room_name == "salon"

    @pytest.mark.unit
    def test_frozen(self, sample_record: SimRecord) -> None:
        """Assigning to any field raises FrozenInstanceError."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_record.t = 99  # type: ignore[misc]

    @pytest.mark.unit
    def test_convenience_properties(self, sample_record: SimRecord) -> None:
        """Convenience properties delegate to contained dataclasses."""
        # Measurements
        assert sample_record.T_room == 21.5
        assert sample_record.T_slab == 23.0
        assert sample_record.T_outdoor == -5.0
        assert sample_record.valve_pos == 60.0
        assert sample_record.hp_mode == HeatPumpMode.HEATING

        # Actions
        assert sample_record.valve_position == 55.0
        assert sample_record.split_mode == SplitMode.HEATING
        assert sample_record.split_setpoint == 22.0

        # Weather
        assert sample_record.T_out == -4.5
        assert sample_record.GHI == 120.0
        assert sample_record.wind_speed == 3.5
        assert sample_record.humidity == 65.0

    @pytest.mark.unit
    def test_t_floor_equals_t_slab(self, sample_record: SimRecord) -> None:
        """T_floor is an alias for T_slab."""
        assert sample_record.T_floor == sample_record.T_slab

    @pytest.mark.unit
    def test_default_room_name(
        self,
        sample_measurements: Measurements,
        sample_actions: Actions,
        sample_weather: WeatherPoint,
    ) -> None:
        """room_name defaults to empty string."""
        record = SimRecord(
            t=0,
            measurements=sample_measurements,
            actions=sample_actions,
            weather=sample_weather,
        )
        assert record.room_name == ""


# ---------------------------------------------------------------------------
# TestSimulationLog
# ---------------------------------------------------------------------------


class TestSimulationLog:
    """Tests for the SimulationLog container."""

    @pytest.mark.unit
    def test_empty_log_len_zero(self) -> None:
        """Empty log has length 0."""
        log = SimulationLog()
        assert len(log) == 0

    @pytest.mark.unit
    def test_append_increments_len(self, sample_record: SimRecord) -> None:
        """Appending a record increments the length."""
        log = SimulationLog()
        log.append(sample_record)
        assert len(log) == 1
        log.append(sample_record)
        assert len(log) == 2

    @pytest.mark.unit
    def test_append_from_step(
        self,
        sample_measurements: Measurements,
        sample_actions: Actions,
        sample_weather: WeatherPoint,
    ) -> None:
        """append_from_step constructs a SimRecord and appends it."""
        log = SimulationLog()
        log.append_from_step(
            t=10,
            measurements=sample_measurements,
            actions=sample_actions,
            weather=sample_weather,
            room_name="bedroom",
        )
        assert len(log) == 1
        assert log[0].t == 10
        assert log[0].room_name == "bedroom"
        assert log[0].T_room == sample_measurements.T_room

    @pytest.mark.unit
    def test_getitem_single(self, populated_log: SimulationLog) -> None:
        """Integer index returns a single SimRecord."""
        record = populated_log[0]
        assert isinstance(record, SimRecord)
        assert record.t == 0

    @pytest.mark.unit
    def test_getitem_negative_index(self, populated_log: SimulationLog) -> None:
        """Negative index returns from the end."""
        record = populated_log[-1]
        assert isinstance(record, SimRecord)
        assert record.t == 99

    @pytest.mark.unit
    def test_getitem_index_error(self, populated_log: SimulationLog) -> None:
        """Out-of-range index raises IndexError."""
        with pytest.raises(IndexError):
            populated_log[200]

    @pytest.mark.unit
    def test_getitem_slice_returns_simulation_log(
        self, populated_log: SimulationLog
    ) -> None:
        """Slicing returns a new SimulationLog instance."""
        sliced = populated_log[10:20]
        assert isinstance(sliced, SimulationLog)

    @pytest.mark.unit
    def test_getitem_slice_content(self, populated_log: SimulationLog) -> None:
        """Sliced log contains the expected records."""
        sliced = populated_log[10:20]
        assert len(sliced) == 10
        assert sliced[0].t == 10
        assert sliced[-1].t == 19

    @pytest.mark.unit
    def test_getitem_slice_with_step(self, populated_log: SimulationLog) -> None:
        """Slicing with step works correctly."""
        sliced = populated_log[::2]
        assert len(sliced) == 50
        # All even-indexed records -> all salon
        for r in sliced:
            assert r.room_name == "salon"

    @pytest.mark.unit
    def test_iter(self, populated_log: SimulationLog) -> None:
        """Iteration yields all records in order."""
        records = list(populated_log)
        assert len(records) == 100
        assert records[0].t == 0
        assert records[99].t == 99

    @pytest.mark.unit
    def test_get_room_filters_correctly(self, populated_log: SimulationLog) -> None:
        """get_room returns only records for the specified room."""
        salon = populated_log.get_room("salon")
        assert isinstance(salon, SimulationLog)
        assert len(salon) == 50
        for r in salon:
            assert r.room_name == "salon"

    @pytest.mark.unit
    def test_get_room_empty_result(self, populated_log: SimulationLog) -> None:
        """get_room for a non-existent room returns an empty log."""
        result = populated_log.get_room("bathroom")
        assert isinstance(result, SimulationLog)
        assert len(result) == 0

    @pytest.mark.unit
    def test_time_range_filters_correctly(self, populated_log: SimulationLog) -> None:
        """time_range returns records within the inclusive bounds."""
        subset = populated_log.time_range(10, 19)
        assert isinstance(subset, SimulationLog)
        assert len(subset) == 10
        for r in subset:
            assert 10 <= r.t <= 19

    @pytest.mark.unit
    def test_time_range_empty_result(self, populated_log: SimulationLog) -> None:
        """time_range outside data range returns an empty log."""
        result = populated_log.time_range(200, 300)
        assert isinstance(result, SimulationLog)
        assert len(result) == 0

    @pytest.mark.unit
    def test_chaining_get_room_and_time_range(
        self, populated_log: SimulationLog
    ) -> None:
        """get_room and time_range can be chained."""
        result = populated_log.get_room("salon").time_range(0, 9)
        # salon records in t=0..9 are t=0,2,4,6,8
        assert len(result) == 5
        for r in result:
            assert r.room_name == "salon"
            assert 0 <= r.t <= 9

    @pytest.mark.unit
    def test_init_with_records(self, sample_record: SimRecord) -> None:
        """SimulationLog can be initialized with a list of records."""
        records = [sample_record, sample_record]
        log = SimulationLog(records)
        assert len(log) == 2

    @pytest.mark.unit
    def test_init_copies_list(self, sample_record: SimRecord) -> None:
        """Constructor copies the input list to prevent aliasing."""
        records = [sample_record]
        log = SimulationLog(records)
        records.append(sample_record)
        # External mutation should not affect the log
        assert len(log) == 1


# ---------------------------------------------------------------------------
# TestSimulationLogDataFrame
# ---------------------------------------------------------------------------


class TestSimulationLogDataFrame:
    """Tests for SimulationLog.to_dataframe() with pandas."""

    @pytest.mark.unit
    def test_to_dataframe_columns(self, populated_log: SimulationLog) -> None:
        """DataFrame has all expected columns."""
        pytest.importorskip("pandas")
        df = populated_log.to_dataframe()
        expected_columns = {
            "t",
            "T_room",
            "T_slab",
            "T_outdoor",
            "valve_pos",
            "hp_mode",
            "valve_position",
            "split_mode",
            "split_setpoint",
            "T_out",
            "GHI",
            "wind_speed",
            "humidity",
            "room_name",
        }
        assert set(df.columns) == expected_columns

    @pytest.mark.unit
    def test_to_dataframe_row_count(self, populated_log: SimulationLog) -> None:
        """DataFrame has the same number of rows as the log."""
        pytest.importorskip("pandas")
        df = populated_log.to_dataframe()
        assert len(df) == 100

    @pytest.mark.unit
    def test_to_dataframe_values(self, sample_record: SimRecord) -> None:
        """DataFrame values match the record's convenience properties."""
        pytest.importorskip("pandas")
        log = SimulationLog([sample_record])
        df = log.to_dataframe()
        row = df.iloc[0]

        assert row["t"] == 42
        assert row["T_room"] == 21.5
        assert row["T_slab"] == 23.0
        assert row["T_outdoor"] == -5.0
        assert row["valve_pos"] == 60.0
        assert row["hp_mode"] == "heating"
        assert row["valve_position"] == 55.0
        assert row["split_mode"] == "heating"
        assert row["split_setpoint"] == 22.0
        assert row["T_out"] == -4.5
        assert row["GHI"] == 120.0
        assert row["wind_speed"] == 3.5
        assert row["humidity"] == 65.0
        assert row["room_name"] == "salon"

    @pytest.mark.unit
    def test_to_dataframe_empty_log(self) -> None:
        """to_dataframe on an empty log returns an empty DataFrame."""
        pytest.importorskip("pandas")
        log = SimulationLog()
        df = log.to_dataframe()
        assert len(df) == 0

    @pytest.mark.unit
    def test_to_dataframe_enum_as_string(self, sample_record: SimRecord) -> None:
        """Enum fields are stored as string values, not enum objects."""
        pytest.importorskip("pandas")
        log = SimulationLog([sample_record])
        df = log.to_dataframe()
        assert isinstance(df["hp_mode"].iloc[0], str)
        assert isinstance(df["split_mode"].iloc[0], str)


# ---------------------------------------------------------------------------
# TestSimulationLogMemory
# ---------------------------------------------------------------------------


class TestSimulationLogMemory:
    """Memory usage tests for large SimulationLog instances."""

    @pytest.mark.unit
    def test_full_year_log_memory(self) -> None:
        """525,600 records (full year at 1-min resolution) fit in memory.

        This test verifies that a full-year log can be created and has
        the correct length.  Actual memory usage is well under 1 GB.
        """
        meas = Measurements(
            T_room=20.0,
            T_slab=22.0,
            T_outdoor=-5.0,
            valve_pos=50.0,
            hp_mode=HeatPumpMode.HEATING,
        )
        actions = Actions(valve_position=50.0)
        weather = WeatherPoint(T_out=-5.0, GHI=0.0, wind_speed=0.0, humidity=50.0)

        log = SimulationLog()
        for t in range(525_600):
            log.append(
                SimRecord(
                    t=t,
                    measurements=meas,
                    actions=actions,
                    weather=weather,
                    room_name="salon",
                )
            )

        assert len(log) == 525_600
