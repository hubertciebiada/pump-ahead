"""Matplotlib static plots for post-hoc simulation analysis.

Provides per-room temperature plots, valve plots, split activity plots,
weather overlay, energy breakdown, and a multi-room dashboard.  All plots
auto-save as PNG at 150 DPI with ``bbox_inches="tight"`` when a
``save_path`` is supplied.

Individual plot functions return a ``matplotlib.figure.Figure`` without
closing it, allowing callers to further customise.  The batch function
``generate_plots()`` saves all PNGs, closes figures after save, and
returns a list of saved file paths.

matplotlib is an optional dependency (``viz`` extra); plot functions
raise ``ImportError`` with installation instructions when it is not
available.

Typical usage::

    from pumpahead.visualization import generate_plots

    paths = generate_plots(
        log,
        output_dir=Path("plots"),
        scenario_name="cold_snap",
        setpoint=21.0,
    )

Units:
    Temperatures: degC
    Powers: W
    Energy: kWh
    Valve position: 0-100 %
    Time: minutes (input), hours (plot x-axis)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pumpahead.metrics import SimMetrics
from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import SplitMode

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _lazy_import_matplotlib() -> Any:
    """Lazy-import matplotlib.pyplot with Agg backend.

    Returns:
        The ``matplotlib.pyplot`` module.

    Raises:
        ImportError: If matplotlib is not installed.
    """
    try:
        import matplotlib
    except ImportError:
        msg = (
            "matplotlib is required for visualization plots. "
            "Install it with: pip install pumpahead[viz]"
        )
        raise ImportError(msg) from None

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _downsample[T](data: list[T], max_points: int = 5000) -> list[T]:
    """Reduce *data* to at most *max_points* via uniform stride selection.

    When ``len(data) <= max_points``, returns *data* unchanged.

    Args:
        data: Input sequence.
        max_points: Maximum number of elements in the result.

    Returns:
        A list with at most *max_points* elements, preserving order.
    """
    n = len(data)
    if n <= max_points:
        return data
    stride = n / max_points
    return [data[int(i * stride)] for i in range(max_points)]


def _extract_room_names(log: SimulationLog) -> list[str]:
    """Return sorted unique room names from *log*.

    Empty room names are replaced with ``"default"`` in the output.

    Args:
        log: Simulation log to scan.

    Returns:
        Sorted list of room names (with ``""`` mapped to ``"default"``).
    """
    raw = sorted({r.room_name for r in log})
    return [name if name else "default" for name in raw]


def _minutes_to_hours(minutes: list[int]) -> list[float]:
    """Convert a list of simulation times from minutes to hours.

    Args:
        minutes: Time values in minutes.

    Returns:
        Time values in hours.
    """
    return [m / 60.0 for m in minutes]


def _validate_non_empty(log: SimulationLog) -> None:
    """Raise ``ValueError`` if *log* is empty.

    Args:
        log: Simulation log to check.

    Raises:
        ValueError: When the log has zero records.
    """
    if len(log) == 0:
        msg = "Simulation log must not be empty"
        raise ValueError(msg)


def _safe_room_name(room_name: str) -> str:
    """Return a file-safe room name, replacing empty strings.

    Args:
        room_name: Raw room name from the simulation log.

    Returns:
        ``"default"`` when *room_name* is empty, otherwise *room_name*.
    """
    return room_name if room_name else "default"


# ---------------------------------------------------------------------------
# Individual plot functions
# ---------------------------------------------------------------------------


def plot_room_temperatures(
    log: SimulationLog,
    *,
    room_name: str = "",
    setpoint: float | None = None,
    comfort_band: float = 0.5,
    save_path: Path | None = None,
    max_points: int = 5000,
) -> Figure:
    """Plot per-room temperature traces: T_room, T_slab, setpoint, comfort band.

    Args:
        log: Simulation log (optionally pre-filtered to one room).
        room_name: Room name for filtering and title.  When empty, uses
            all records.
        setpoint: Target room temperature [degC].  When provided, a gray
            dashed line and a green comfort band are drawn.
        comfort_band: Half-width of the comfort band [degC].
        save_path: If provided, save the figure as PNG at this path.
        max_points: Maximum data points to plot (downsampled if exceeded).

    Returns:
        matplotlib Figure.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If the log is empty.
    """
    _validate_non_empty(log)
    plt = _lazy_import_matplotlib()

    records = list(log.get_room(room_name)) if room_name else list(log)
    if not records:
        records = list(log)
    records = _downsample(records, max_points)

    time_h = _minutes_to_hours([r.t for r in records])
    t_room = [r.T_room for r in records]
    t_slab = [r.T_slab for r in records]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(time_h, t_room, label="T_room", color="#2196F3", linewidth=1.0)
    ax.plot(time_h, t_slab, label="T_slab", color="#FF9800", linewidth=1.0)

    if setpoint is not None:
        ax.axhline(
            y=setpoint,
            color="gray",
            linewidth=1.0,
            linestyle="--",
            label=f"Setpoint ({setpoint} degC)",
        )
        ax.fill_between(
            time_h,
            setpoint - comfort_band,
            setpoint + comfort_band,
            alpha=0.15,
            color="#4CAF50",
            label=f"Comfort band (+/-{comfort_band} degC)",
        )

    display_name = _safe_room_name(room_name)
    ax.set_title(f"Room Temperatures — {display_name}")
    ax.set_xlabel("Time [hours]")
    ax.set_ylabel("Temperature [degC]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig  # type: ignore[no-any-return]


def plot_valves(
    log: SimulationLog,
    *,
    save_path: Path | None = None,
    max_points: int = 5000,
) -> Figure:
    """Plot valve position traces for all rooms.

    Args:
        log: Simulation log (may contain multiple rooms).
        save_path: If provided, save the figure as PNG at this path.
        max_points: Maximum data points per room (downsampled if exceeded).

    Returns:
        matplotlib Figure.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If the log is empty.
    """
    _validate_non_empty(log)
    plt = _lazy_import_matplotlib()

    room_names = _extract_room_names(log)

    fig, ax = plt.subplots(figsize=(12, 4))

    for display_name in room_names:
        raw_name = "" if display_name == "default" else display_name
        records = list(log.get_room(raw_name))
        records = _downsample(records, max_points)
        time_h = _minutes_to_hours([r.t for r in records])
        valve = [r.valve_position for r in records]
        ax.plot(time_h, valve, label=display_name, linewidth=1.0)

    ax.set_ylim(-5, 105)
    ax.set_title("Valve Positions")
    ax.set_xlabel("Time [hours]")
    ax.set_ylabel("Valve position [%]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig  # type: ignore[no-any-return]


def plot_splits(
    log: SimulationLog,
    *,
    save_path: Path | None = None,
    max_points: int = 5000,
) -> Figure:
    """Plot split activity for all rooms as step lines.

    Y-axis uses numeric encoding: OFF=0, HEATING=1, COOLING=-1.

    Args:
        log: Simulation log (may contain multiple rooms).
        save_path: If provided, save the figure as PNG at this path.
        max_points: Maximum data points per room (downsampled if exceeded).

    Returns:
        matplotlib Figure.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If the log is empty.
    """
    _validate_non_empty(log)
    plt = _lazy_import_matplotlib()

    room_names = _extract_room_names(log)

    split_mode_map = {
        SplitMode.OFF: 0,
        SplitMode.HEATING: 1,
        SplitMode.COOLING: -1,
    }

    fig, ax = plt.subplots(figsize=(12, 3))

    for display_name in room_names:
        raw_name = "" if display_name == "default" else display_name
        records = list(log.get_room(raw_name))
        records = _downsample(records, max_points)
        time_h = _minutes_to_hours([r.t for r in records])
        modes = [split_mode_map[r.split_mode] for r in records]
        ax.step(time_h, modes, label=display_name, where="post", linewidth=1.0)

    ax.set_yticks([-1, 0, 1])
    ax.set_yticklabels(["COOL", "OFF", "HEAT"])
    ax.set_ylim(-1.5, 1.5)
    ax.set_title("Split Activity")
    ax.set_xlabel("Time [hours]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig  # type: ignore[no-any-return]


def plot_weather(
    log: SimulationLog,
    *,
    save_path: Path | None = None,
    max_points: int = 5000,
) -> Figure:
    """Plot weather conditions: T_outdoor and GHI on two subplots.

    Args:
        log: Simulation log.
        save_path: If provided, save the figure as PNG at this path.
        max_points: Maximum data points to plot (downsampled if exceeded).

    Returns:
        matplotlib Figure.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If the log is empty.
    """
    _validate_non_empty(log)
    plt = _lazy_import_matplotlib()

    records = list(log)
    records = _downsample(records, max_points)
    time_h = _minutes_to_hours([r.t for r in records])
    t_out = [r.T_out for r in records]
    ghi = [r.GHI for r in records]

    fig, (ax_temp, ax_ghi) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    ax_temp.plot(time_h, t_out, color="#2196F3", linewidth=1.0)
    ax_temp.set_title("Outdoor Temperature")
    ax_temp.set_ylabel("T_outdoor [degC]")
    ax_temp.grid(True, alpha=0.3)

    ax_ghi.plot(time_h, ghi, color="#FF9800", linewidth=1.0)
    ax_ghi.set_title("Global Horizontal Irradiance")
    ax_ghi.set_xlabel("Time [hours]")
    ax_ghi.set_ylabel("GHI [W/m^2]")
    ax_ghi.grid(True, alpha=0.3)

    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig  # type: ignore[no-any-return]


def plot_energy(
    log: SimulationLog,
    *,
    ufh_nominal_power_w: float,
    split_power_w: float = 0.0,
    dt_minutes: int = 1,
    save_path: Path | None = None,
    max_points: int = 5000,
) -> Figure:
    """Plot cumulative energy breakdown: UFH and split stacked area.

    Args:
        log: Simulation log.
        ufh_nominal_power_w: Maximum UFH power [W].
        split_power_w: Maximum split power [W].
        dt_minutes: Simulation timestep [minutes].
        save_path: If provided, save the figure as PNG at this path.
        max_points: Maximum data points to plot (downsampled if exceeded).

    Returns:
        matplotlib Figure.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If the log is empty.
    """
    _validate_non_empty(log)
    plt = _lazy_import_matplotlib()

    records = list(log)
    records = _downsample(records, max_points)

    dt_hours = dt_minutes / 60.0
    cumulative_ufh: list[float] = []
    cumulative_split: list[float] = []
    time_h: list[float] = []
    ufh_acc = 0.0
    split_acc = 0.0

    for rec in records:
        ufh_power = (rec.valve_position / 100.0) * ufh_nominal_power_w
        split_power = split_power_w if rec.split_mode != SplitMode.OFF else 0.0
        # Convert W * hours to kWh
        ufh_acc += ufh_power * dt_hours / 1000.0
        split_acc += split_power * dt_hours / 1000.0
        cumulative_ufh.append(ufh_acc)
        cumulative_split.append(split_acc)
        time_h.append(rec.t / 60.0)

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.fill_between(
        time_h,
        0,
        cumulative_ufh,
        alpha=0.6,
        color="#2196F3",
        label="UFH",
    )
    total = [u + s for u, s in zip(cumulative_ufh, cumulative_split, strict=True)]
    ax.fill_between(
        time_h,
        cumulative_ufh,
        total,
        alpha=0.6,
        color="#FF5722",
        label="Split",
    )

    ax.set_title("Cumulative Energy Consumption")
    ax.set_xlabel("Time [hours]")
    ax.set_ylabel("Energy [kWh]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig  # type: ignore[no-any-return]


def plot_dashboard(
    log: SimulationLog,
    *,
    setpoint: float,
    comfort_band: float = 0.5,
    ufh_nominal_power_w: float | None = None,
    split_power_w: float | None = None,
    dt_minutes: int = 1,
    save_path: Path | None = None,
    max_points: int = 5000,
) -> Figure:
    """Plot a multi-room dashboard with temperature, valve, and metrics.

    For each room creates two subplot rows: temperature overlay and valve
    position.  A final text panel shows ``SimMetrics`` summaries.

    Args:
        log: Simulation log (may contain multiple rooms).
        setpoint: Target room temperature [degC].
        comfort_band: Half-width of the comfort band [degC].
        ufh_nominal_power_w: Maximum UFH power [W] (for metrics).
        split_power_w: Maximum split power [W] (for metrics).
        dt_minutes: Simulation timestep [minutes].
        save_path: If provided, save the figure as PNG at this path.
        max_points: Maximum data points per room (downsampled if exceeded).

    Returns:
        matplotlib Figure.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If the log is empty.
    """
    _validate_non_empty(log)
    plt = _lazy_import_matplotlib()

    room_names = _extract_room_names(log)
    n_rooms = len(room_names)
    # 2 rows per room (temp + valve) + 1 row for metrics text
    n_rows = n_rooms * 2 + 1

    fig, axes = plt.subplots(
        n_rows,
        1,
        figsize=(14, 3 * n_rows),
        squeeze=False,
    )

    for i, display_name in enumerate(room_names):
        raw_name = "" if display_name == "default" else display_name
        records = list(log.get_room(raw_name))
        records = _downsample(records, max_points)
        time_h = _minutes_to_hours([r.t for r in records])

        # Temperature subplot
        ax_temp = axes[i * 2, 0]
        t_room = [r.T_room for r in records]
        t_slab = [r.T_slab for r in records]
        ax_temp.plot(time_h, t_room, label="T_room", color="#2196F3", linewidth=1.0)
        ax_temp.plot(time_h, t_slab, label="T_slab", color="#FF9800", linewidth=1.0)
        ax_temp.axhline(
            y=setpoint, color="gray", linewidth=1.0, linestyle="--", alpha=0.7
        )
        ax_temp.fill_between(
            time_h,
            setpoint - comfort_band,
            setpoint + comfort_band,
            alpha=0.1,
            color="#4CAF50",
        )
        ax_temp.set_title(f"{display_name} — Temperature")
        ax_temp.set_ylabel("T [degC]")
        ax_temp.legend(loc="upper right", fontsize="small")
        ax_temp.grid(True, alpha=0.3)

        # Valve subplot
        ax_valve = axes[i * 2 + 1, 0]
        valve = [r.valve_position for r in records]
        ax_valve.plot(time_h, valve, color="#9C27B0", linewidth=1.0)
        ax_valve.set_ylim(-5, 105)
        ax_valve.set_title(f"{display_name} — Valve Position")
        ax_valve.set_ylabel("Valve [%]")
        ax_valve.grid(True, alpha=0.3)

    # Metrics text panel
    ax_text = axes[-1, 0]
    ax_text.axis("off")
    metrics_lines: list[str] = []
    for display_name in room_names:
        raw_name = "" if display_name == "default" else display_name
        room_log = log.get_room(raw_name)
        if len(room_log) == 0:
            continue
        m = SimMetrics.from_log(
            room_log,
            setpoint=setpoint,
            comfort_band=comfort_band,
            ufh_nominal_power_w=ufh_nominal_power_w,
            split_power_w=split_power_w,
            dt_minutes=dt_minutes,
        )
        energy_str = f"{m.energy_kwh:.1f} kWh" if m.energy_kwh is not None else "N/A"
        metrics_lines.append(
            f"{display_name}: "
            f"comfort={m.comfort_pct:.1f}%, "
            f"max_over={m.max_overshoot:.2f} degC, "
            f"max_under={m.max_undershoot:.2f} degC, "
            f"energy={energy_str}"
        )

    ax_text.text(
        0.05,
        0.95,
        "Metrics Summary\n" + "\n".join(metrics_lines),
        transform=ax_text.transAxes,
        verticalalignment="top",
        fontfamily="monospace",
        fontsize=10,
    )

    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Batch function
# ---------------------------------------------------------------------------


def generate_plots(
    log: SimulationLog,
    output_dir: Path,
    *,
    scenario_name: str = "sim",
    setpoint: float = 21.0,
    comfort_band: float = 0.5,
    ufh_nominal_power_w: float | None = None,
    split_power_w: float | None = None,
    dt_minutes: int = 1,
    max_points: int = 5000,
) -> list[Path]:
    """Generate all standard plots and save as PNG files.

    Creates *output_dir* if it does not exist.  All figures are closed
    after saving to avoid memory accumulation.

    Naming convention:
        - Global plots: ``{scenario_name}_{plot_type}.png``
        - Per-room plots: ``{scenario_name}_{room_name}_{plot_type}.png``

    Args:
        log: Simulation log.
        output_dir: Directory to write PNG files into.
        scenario_name: Prefix for filenames.
        setpoint: Target room temperature [degC].
        comfort_band: Half-width of the comfort band [degC].
        ufh_nominal_power_w: Maximum UFH power [W].  When ``None``, the energy
            plot is skipped.
        split_power_w: Maximum split power [W].  When ``None``, the energy
            plot is skipped.
        dt_minutes: Simulation timestep [minutes].
        max_points: Maximum data points per plot (downsampled if exceeded).

    Returns:
        List of paths to saved PNG files.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If the log is empty.
    """
    _validate_non_empty(log)
    plt = _lazy_import_matplotlib()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    room_names = _extract_room_names(log)

    # -- Per-room temperature plots -------------------------------------------
    for display_name in room_names:
        raw_name = "" if display_name == "default" else display_name
        path = output_dir / f"{scenario_name}_{display_name}_temperatures.png"
        fig = plot_room_temperatures(
            log,
            room_name=raw_name,
            setpoint=setpoint,
            comfort_band=comfort_band,
            save_path=path,
            max_points=max_points,
        )
        plt.close(fig)
        saved.append(path)

    # -- Valves ---------------------------------------------------------------
    path = output_dir / f"{scenario_name}_valves.png"
    fig = plot_valves(log, save_path=path, max_points=max_points)
    plt.close(fig)
    saved.append(path)

    # -- Splits ---------------------------------------------------------------
    path = output_dir / f"{scenario_name}_splits.png"
    fig = plot_splits(log, save_path=path, max_points=max_points)
    plt.close(fig)
    saved.append(path)

    # -- Weather --------------------------------------------------------------
    path = output_dir / f"{scenario_name}_weather.png"
    fig = plot_weather(log, save_path=path, max_points=max_points)
    plt.close(fig)
    saved.append(path)

    # -- Energy (only when power parameters provided) -------------------------
    if ufh_nominal_power_w is not None and split_power_w is not None:
        path = output_dir / f"{scenario_name}_energy.png"
        fig = plot_energy(
            log,
            ufh_nominal_power_w=ufh_nominal_power_w,
            split_power_w=split_power_w,
            dt_minutes=dt_minutes,
            save_path=path,
            max_points=max_points,
        )
        plt.close(fig)
        saved.append(path)

    # -- Dashboard ------------------------------------------------------------
    path = output_dir / f"{scenario_name}_dashboard.png"
    fig = plot_dashboard(
        log,
        setpoint=setpoint,
        comfort_band=comfort_band,
        ufh_nominal_power_w=ufh_nominal_power_w,
        split_power_w=split_power_w,
        dt_minutes=dt_minutes,
        save_path=path,
        max_points=max_points,
    )
    plt.close(fig)
    saved.append(path)

    return saved
