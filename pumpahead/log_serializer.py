"""JSON and pickle serialization for SimulationLog.

Provides lossless roundtrip save/load of simulation logs in two formats:

* **JSON** -- human-readable, versioned schema (``version: 1``), with
  optional pretty-print.  Streaming write keeps memory overhead low
  for large logs.
* **pickle** -- fast binary format using the highest available protocol.
  Suitable for local analysis workflows.  Only load trusted files --
  ``pickle.load`` can execute arbitrary code.

Error handling covers missing files, corrupted data, and version
mismatches with clear exception messages.

Typical usage::

    from pathlib import Path
    from pumpahead.log_serializer import save_json, load_json

    save_json(log, Path("results/cold_snap.json"), pretty=True)
    loaded = load_json(Path("results/cold_snap.json"))

Units:
    Temperatures: degC
    Powers: W
    Valve position: 0-100 %
    Time: minutes
"""

from __future__ import annotations

import json
import pickle
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pumpahead.simulation_log import SimRecord, SimulationLog
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Private helpers — dict <-> dataclass conversion
# ---------------------------------------------------------------------------


def _record_to_dict(record: SimRecord) -> dict[str, Any]:
    """Convert a ``SimRecord`` to a JSON-serialisable dictionary.

    ``dataclasses.asdict`` is used for recursive conversion, then any
    ``Enum`` values are replaced with their ``.value`` strings.

    Args:
        record: The record to convert.

    Returns:
        A plain dict with all values JSON-serialisable.
    """
    d = asdict(record)
    # Convert enum fields to their string values.
    d["measurements"]["hp_mode"] = record.measurements.hp_mode.value
    d["actions"]["split_mode"] = record.actions.split_mode.value
    return d


def _dict_to_record(d: dict[str, Any]) -> SimRecord:
    """Reconstruct a ``SimRecord`` from a dictionary.

    Enum fields are rebuilt from their string ``.value`` representations.

    Args:
        d: Dictionary as produced by ``_record_to_dict``.

    Returns:
        A frozen ``SimRecord`` instance.

    Raises:
        KeyError: If a required field is missing.
        ValueError: If an enum value string is invalid.
    """
    m = d["measurements"]
    measurements = Measurements(
        T_room=m["T_room"],
        T_slab=m["T_slab"],
        T_outdoor=m["T_outdoor"],
        valve_pos=m["valve_pos"],
        hp_mode=HeatPumpMode(m["hp_mode"]),
    )

    a = d["actions"]
    actions = Actions(
        valve_position=a["valve_position"],
        split_mode=SplitMode(a["split_mode"]),
        split_setpoint=a["split_setpoint"],
    )

    w = d["weather"]
    weather = WeatherPoint(
        T_out=w["T_out"],
        GHI=w["GHI"],
        wind_speed=w["wind_speed"],
        humidity=w["humidity"],
    )

    return SimRecord(
        t=d["t"],
        measurements=measurements,
        actions=actions,
        weather=weather,
        room_name=d["room_name"],
    )


# ---------------------------------------------------------------------------
# Public API — JSON
# ---------------------------------------------------------------------------


def save_json(
    log: SimulationLog,
    path: Path | str,
    *,
    pretty: bool = False,
) -> None:
    """Serialise a ``SimulationLog`` to a JSON file.

    Uses streaming writes to avoid building the entire serialised form
    in memory at once — important for full-year logs (525 600 records).

    The file format is::

        {
          "version": 1,
          "records": [ ... ]
        }

    Args:
        log: The simulation log to save.
        path: Destination file path (created or overwritten).
        pretty: If ``True``, write indented JSON for human readability.
            Compact (single-line per record) otherwise.
    """
    path = Path(path)
    indent = 2 if pretty else None
    with path.open("w", encoding="utf-8") as f:
        f.write('{"version": ')
        f.write(str(_SCHEMA_VERSION))
        f.write(', "records": [')
        first = True
        for record in log:
            if not first:
                f.write(",")
            if pretty:
                f.write("\n")
            record_json = json.dumps(_record_to_dict(record), indent=indent)
            if pretty:
                # Indent each line of the record JSON by 2 spaces
                indented = "\n".join("  " + line for line in record_json.splitlines())
                f.write(indented)
            else:
                f.write(record_json)
            first = False
        if pretty and len(log) > 0:
            f.write("\n")
        f.write("]}")
        if pretty:
            f.write("\n")


def load_json(path: Path | str) -> SimulationLog:
    """Load a ``SimulationLog`` from a JSON file.

    Args:
        path: Path to the JSON file produced by :func:`save_json`.

    Returns:
        A ``SimulationLog`` with all records restored.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the JSON is malformed, the schema version is
            unsupported, or required fields are missing.
    """
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in {path}: {exc}"
        raise ValueError(msg) from exc

    try:
        version = data["version"]
    except KeyError:
        msg = f"Malformed log file {path}: missing key 'version'"
        raise ValueError(msg) from None

    if version != _SCHEMA_VERSION:
        msg = f"Unsupported log version: {version}, expected {_SCHEMA_VERSION}"
        raise ValueError(msg)

    try:
        raw_records = data["records"]
    except KeyError:
        msg = f"Malformed log file {path}: missing key 'records'"
        raise ValueError(msg) from None

    try:
        records = [_dict_to_record(d) for d in raw_records]
    except KeyError as exc:
        msg = f"Malformed log file {path}: missing key {exc}"
        raise ValueError(msg) from exc

    return SimulationLog(records)


def load_json_string(text: str) -> SimulationLog:
    """Load a ``SimulationLog`` from a JSON string.

    This is the in-memory counterpart of :func:`load_json`.  It is useful
    when the JSON data is already available as a string (e.g. from a file
    upload callback) and does not need to be read from disk.

    Args:
        text: JSON string produced by :func:`save_json` (or equivalent).

    Returns:
        A ``SimulationLog`` with all records restored.

    Raises:
        ValueError: If the string is not valid JSON, the schema version is
            unsupported, or required fields are missing.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON string: {exc}"
        raise ValueError(msg) from exc

    try:
        version = data["version"]
    except KeyError:
        msg = "Malformed log data: missing key 'version'"
        raise ValueError(msg) from None

    if version != _SCHEMA_VERSION:
        msg = f"Unsupported log version: {version}, expected {_SCHEMA_VERSION}"
        raise ValueError(msg)

    try:
        raw_records = data["records"]
    except KeyError:
        msg = "Malformed log data: missing key 'records'"
        raise ValueError(msg) from None

    try:
        records = [_dict_to_record(d) for d in raw_records]
    except KeyError as exc:
        msg = f"Malformed log data: missing key {exc}"
        raise ValueError(msg) from exc

    return SimulationLog(records)


# ---------------------------------------------------------------------------
# Public API — pickle
# ---------------------------------------------------------------------------


def save_pickle(log: SimulationLog, path: Path | str) -> None:
    """Serialise a ``SimulationLog`` to a pickle file.

    Uses the highest available pickle protocol for performance.

    Args:
        log: The simulation log to save.
        path: Destination file path (created or overwritten).
    """
    path = Path(path)
    with path.open("wb") as f:
        pickle.dump(log, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_pickle(path: Path | str) -> SimulationLog:
    """Load a ``SimulationLog`` from a pickle file.

    Only load files you trust — ``pickle.load`` can execute arbitrary
    code from untrusted data.

    Args:
        path: Path to the pickle file produced by :func:`save_pickle`.

    Returns:
        A ``SimulationLog`` with all records restored.

    Raises:
        FileNotFoundError: If *path* does not exist.
        TypeError: If the unpickled object is not a ``SimulationLog``.
    """
    path = Path(path)
    with path.open("rb") as f:
        result = pickle.load(f)  # noqa: S301
    if not isinstance(result, SimulationLog):
        msg = f"Expected SimulationLog, got {type(result).__name__}"
        raise TypeError(msg)
    return result
