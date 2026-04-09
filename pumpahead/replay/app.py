"""Plotly Dash replay application for interactive SimulationLog playback.

Contains the ``create_app`` factory function that builds a fully wired
Dash application with timeline slider, play/pause/step controls,
synchronized per-room charts, weather overlay, and per-room gauges.

Dash and Plotly are lazily imported so that ``pumpahead`` remains usable
without the ``viz`` extra installed.

Large logs (>5000 points) are automatically downsampled for background
chart traces while the current-step marker remains at full resolution.
The ``SimulationLog`` is stored server-side (module-level dict) to avoid
pushing large payloads to the browser.

Units:
    Temperatures: degC
    Powers: W
    Valve position: 0-100 %
    Time: minutes (data), hours (chart x-axis)
"""

from __future__ import annotations

import base64
import pickle
import uuid
from typing import Any

from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import SplitMode

# ---------------------------------------------------------------------------
# Lazy import helpers
# ---------------------------------------------------------------------------


def _lazy_import_dash() -> tuple[Any, Any, Any, Any]:
    """Lazy-import Dash modules.

    Returns:
        Tuple of (dash, dcc, html, callback helpers).

    Raises:
        ImportError: If dash is not installed.
    """
    try:
        import dash as _dash
        from dash import Input, Output, State, callback_context, dcc, html
    except ImportError:
        msg = (
            "dash is required for the replay application. "
            "Install it with: pip install pumpahead[viz]"
        )
        raise ImportError(msg) from None
    return _dash, dcc, html, (Input, Output, State, callback_context)


def _lazy_import_plotly() -> Any:
    """Lazy-import plotly.graph_objects.

    Returns:
        The ``plotly.graph_objects`` module.

    Raises:
        ImportError: If plotly is not installed.
    """
    try:
        import plotly.graph_objects as _go
    except ImportError:
        msg = (
            "plotly is required for the replay application. "
            "Install it with: pip install pumpahead[viz]"
        )
        raise ImportError(msg) from None
    return _go


# ---------------------------------------------------------------------------
# Server-side log storage
# ---------------------------------------------------------------------------

_LOG_STORE: dict[str, SimulationLog] = {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SPEED_MAP: dict[str, int] = {
    "1x": 1000,
    "2x": 500,
    "5x": 200,
    "10x": 100,
}

_MAX_CHART_POINTS = 2000
"""Maximum number of points for background chart traces."""

_SPLIT_MODE_MAP: dict[SplitMode, int] = {
    SplitMode.OFF: 0,
    SplitMode.HEATING: 1,
    SplitMode.COOLING: -1,
}

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


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
    """Convert simulation times from minutes to hours.

    Args:
        minutes: Time values in minutes.

    Returns:
        Time values in hours.
    """
    return [m / 60.0 for m in minutes]


def _downsample_indices(n: int, max_points: int = _MAX_CHART_POINTS) -> list[int]:
    """Return uniformly-spaced indices for downsampling.

    When ``n <= max_points``, returns ``list(range(n))``.

    Args:
        n: Total number of data points.
        max_points: Maximum number of indices to return.

    Returns:
        List of integer indices.
    """
    if n <= max_points:
        return list(range(n))
    stride = n / max_points
    return [int(i * stride) for i in range(max_points)]


def _get_room_records(log: SimulationLog, display_name: str) -> list[Any]:
    """Get records for a room, mapping ``"default"`` back to ``""``."""
    raw_name = "" if display_name == "default" else display_name
    return list(log.get_room(raw_name))


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------


def _build_temperature_figure(
    records: list[Any],
    current_step: int,
    room_name: str,
    setpoint: float,
    comfort_band: float,
) -> Any:
    """Build a temperature chart for a single room.

    Shows T_room and T_slab traces with setpoint/comfort band and a
    vertical marker at the current timestep.

    Args:
        records: List of ``SimRecord`` for this room.
        current_step: Index into *records* for the vertical marker.
        room_name: Display name for the chart title.
        setpoint: Target temperature [degC].
        comfort_band: Half-width of comfort band [degC].

    Returns:
        A Plotly Figure.
    """
    go_mod = _lazy_import_plotly()

    n = len(records)
    indices = _downsample_indices(n)
    time_h = [records[i].t / 60.0 for i in indices]
    t_room = [records[i].T_room for i in indices]
    t_slab = [records[i].T_slab for i in indices]

    fig = go_mod.Figure()

    # Comfort band
    fig.add_trace(
        go_mod.Scatter(
            x=time_h + time_h[::-1],
            y=[setpoint + comfort_band] * len(time_h)
            + [setpoint - comfort_band] * len(time_h),
            fill="toself",
            fillcolor="rgba(76, 175, 80, 0.1)",
            line={"color": "rgba(0,0,0,0)"},
            showlegend=False,
            hoverinfo="skip",
            name="Comfort band",
        )
    )

    # Setpoint line
    fig.add_hline(
        y=setpoint,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Setpoint {setpoint} degC",
        annotation_position="top left",
    )

    # T_room trace
    fig.add_trace(
        go_mod.Scatter(
            x=time_h,
            y=t_room,
            name="T_room",
            line={"color": "#2196F3", "width": 1.5},
            mode="lines",
        )
    )

    # T_slab trace
    fig.add_trace(
        go_mod.Scatter(
            x=time_h,
            y=t_slab,
            name="T_slab",
            line={"color": "#FF9800", "width": 1.5},
            mode="lines",
        )
    )

    # Current step marker
    if 0 <= current_step < n:
        marker_time = records[current_step].t / 60.0
        fig.add_vline(
            x=marker_time,
            line_dash="solid",
            line_color="red",
            line_width=1.5,
        )

    fig.update_layout(
        title=f"Temperature - {room_name}",
        xaxis_title="Time [hours]",
        yaxis_title="Temperature [degC]",
        margin={"l": 50, "r": 20, "t": 40, "b": 40},
        height=300,
        legend={"orientation": "h", "y": -0.2},
        template="plotly_white",
    )

    return fig


def _build_valve_figure(
    records: list[Any],
    current_step: int,
    room_name: str,
) -> Any:
    """Build a valve position chart for a single room.

    Args:
        records: List of ``SimRecord`` for this room.
        current_step: Index into *records* for the vertical marker.
        room_name: Display name for the chart title.

    Returns:
        A Plotly Figure.
    """
    go_mod = _lazy_import_plotly()

    n = len(records)
    indices = _downsample_indices(n)
    time_h = [records[i].t / 60.0 for i in indices]
    valve = [records[i].valve_position for i in indices]

    fig = go_mod.Figure()

    fig.add_trace(
        go_mod.Scatter(
            x=time_h,
            y=valve,
            name="Valve",
            line={"color": "#9C27B0", "width": 1.5},
            fill="tozeroy",
            fillcolor="rgba(156, 39, 176, 0.1)",
            mode="lines",
        )
    )

    # Current step marker
    if 0 <= current_step < n:
        marker_time = records[current_step].t / 60.0
        fig.add_vline(
            x=marker_time,
            line_dash="solid",
            line_color="red",
            line_width=1.5,
        )

    fig.update_layout(
        title=f"Valve Position - {room_name}",
        xaxis_title="Time [hours]",
        yaxis_title="Valve [%]",
        yaxis_range=[-5, 105],
        margin={"l": 50, "r": 20, "t": 40, "b": 40},
        height=250,
        template="plotly_white",
    )

    return fig


def _build_split_figure(
    records: list[Any],
    current_step: int,
    room_name: str,
) -> Any:
    """Build a split activity chart for a single room.

    Y-axis: OFF=0, HEATING=1, COOLING=-1.

    Args:
        records: List of ``SimRecord`` for this room.
        current_step: Index into *records* for the vertical marker.
        room_name: Display name for the chart title.

    Returns:
        A Plotly Figure.
    """
    go_mod = _lazy_import_plotly()

    n = len(records)
    indices = _downsample_indices(n)
    time_h = [records[i].t / 60.0 for i in indices]
    modes = [_SPLIT_MODE_MAP[records[i].split_mode] for i in indices]

    fig = go_mod.Figure()

    fig.add_trace(
        go_mod.Scatter(
            x=time_h,
            y=modes,
            name="Split",
            line={"color": "#FF5722", "width": 1.5, "shape": "hv"},
            mode="lines",
        )
    )

    # Current step marker
    if 0 <= current_step < n:
        marker_time = records[current_step].t / 60.0
        fig.add_vline(
            x=marker_time,
            line_dash="solid",
            line_color="red",
            line_width=1.5,
        )

    fig.update_layout(
        title=f"Split Activity - {room_name}",
        xaxis_title="Time [hours]",
        yaxis_title="Mode",
        yaxis={"tickvals": [-1, 0, 1], "ticktext": ["COOL", "OFF", "HEAT"]},
        yaxis_range=[-1.5, 1.5],
        margin={"l": 50, "r": 20, "t": 40, "b": 40},
        height=200,
        template="plotly_white",
    )

    return fig


def _build_weather_figure(
    log: SimulationLog,
    current_step: int,
) -> Any:
    """Build a weather chart with T_out and GHI.

    Args:
        log: Full simulation log (weather is global, not per-room).
        current_step: Index into *log* for the vertical marker.

    Returns:
        A Plotly Figure with two y-axes.
    """
    go_mod = _lazy_import_plotly()
    from plotly.subplots import make_subplots

    records = list(log)
    n = len(records)
    indices = _downsample_indices(n)
    time_h = [records[i].t / 60.0 for i in indices]
    t_out = [records[i].T_out for i in indices]
    ghi = [records[i].GHI for i in indices]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Outdoor Temperature", "GHI"),
    )

    fig.add_trace(
        go_mod.Scatter(
            x=time_h,
            y=t_out,
            name="T_out",
            line={"color": "#2196F3", "width": 1.5},
            mode="lines",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go_mod.Scatter(
            x=time_h,
            y=ghi,
            name="GHI",
            line={"color": "#FF9800", "width": 1.5},
            mode="lines",
        ),
        row=2,
        col=1,
    )

    # Current step marker
    if 0 <= current_step < n:
        marker_time = records[current_step].t / 60.0
        fig.add_vline(
            x=marker_time,
            line_dash="solid",
            line_color="red",
            line_width=1.5,
        )

    fig.update_yaxes(title_text="T_out [degC]", row=1, col=1)
    fig.update_yaxes(title_text="GHI [W/m^2]", row=2, col=1)
    fig.update_xaxes(title_text="Time [hours]", row=2, col=1)

    fig.update_layout(
        height=400,
        margin={"l": 50, "r": 20, "t": 40, "b": 40},
        template="plotly_white",
        legend={"orientation": "h", "y": -0.15},
    )

    return fig


def _build_gauge(
    t_room: float,
    setpoint: float,
    comfort_band: float,
    room_name: str,
) -> Any:
    """Build a gauge indicator for a single room.

    Shows current T_room with color zones: blue (cold), green (comfort),
    red (hot).

    Args:
        t_room: Current air temperature [degC].
        setpoint: Target temperature [degC].
        comfort_band: Half-width of comfort band [degC].
        room_name: Display name.

    Returns:
        A Plotly Figure with a single Indicator trace.
    """
    go_mod = _lazy_import_plotly()

    # Define gauge range around setpoint
    gauge_min = setpoint - 5.0
    gauge_max = setpoint + 5.0

    fig = go_mod.Figure(
        go_mod.Indicator(
            mode="gauge+number",
            value=t_room,
            title={"text": room_name},
            gauge={
                "axis": {"range": [gauge_min, gauge_max]},
                "bar": {"color": "#2196F3"},
                "steps": [
                    {
                        "range": [gauge_min, setpoint - comfort_band],
                        "color": "rgba(33, 150, 243, 0.2)",
                    },
                    {
                        "range": [setpoint - comfort_band, setpoint + comfort_band],
                        "color": "rgba(76, 175, 80, 0.2)",
                    },
                    {
                        "range": [setpoint + comfort_band, gauge_max],
                        "color": "rgba(244, 67, 54, 0.2)",
                    },
                ],
                "threshold": {
                    "line": {"color": "gray", "width": 2},
                    "thickness": 0.75,
                    "value": setpoint,
                },
            },
            number={"suffix": " degC", "valueformat": ".1f"},
        )
    )

    fig.update_layout(
        height=200,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )

    return fig


def _build_empty_figure(title: str = "No data loaded") -> Any:
    """Build a placeholder figure for empty/missing data.

    Args:
        title: Annotation text.

    Returns:
        A Plotly Figure with a centred text annotation.
    """
    go_mod = _lazy_import_plotly()
    fig = go_mod.Figure()
    fig.add_annotation(
        text=title,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"size": 16, "color": "gray"},
    )
    fig.update_layout(
        height=250,
        template="plotly_white",
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return fig


# ---------------------------------------------------------------------------
# Slider helpers
# ---------------------------------------------------------------------------


def _build_slider_marks(n_steps: int, max_marks: int = 20) -> dict[int, str]:
    """Build slider marks at evenly-spaced indices.

    Each mark label shows the time in hours.

    Args:
        n_steps: Total number of timesteps.
        max_marks: Maximum number of marks to display.

    Returns:
        Dict mapping step index -> label string.
    """
    if n_steps <= 0:
        return {0: "0h"}
    if n_steps <= max_marks:
        # Use every step if few enough -- but still show in hours
        # We need the log to convert, so show step indices
        return {}  # Let Dash auto-generate
    stride = max(1, n_steps // max_marks)
    return {i: "" for i in range(0, n_steps, stride)}


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app(
    log: SimulationLog | None = None,
    *,
    setpoint: float = 21.0,
    comfort_band: float = 0.5,
) -> Any:
    """Create a Dash replay application.

    Args:
        log: Initial simulation log to display.  ``None`` starts the app
            in an empty state with file upload enabled.
        setpoint: Default target temperature [degC].
        comfort_band: Half-width of the comfort band [degC].

    Returns:
        A configured ``dash.Dash`` instance ready to be started with
        ``.run()``.
    """
    _dash, dcc, html, (Input, Output, State, callback_context) = _lazy_import_dash()
    from dash.exceptions import PreventUpdate

    # Store the initial log
    initial_log_id = ""
    n_steps = 0
    room_names: list[str] = []

    if log is not None and len(log) > 0:
        initial_log_id = str(uuid.uuid4())
        _LOG_STORE[initial_log_id] = log
        n_steps = len(log)
        room_names = _extract_room_names(log)

    # -- Layout ---------------------------------------------------------------

    app = _dash.Dash(
        __name__,
        title="PumpAhead Replay",
        suppress_callback_exceptions=True,
    )

    app.layout = html.Div(
        [
            # Hidden stores
            dcc.Store(id="log-id", data=initial_log_id),
            dcc.Store(id="n-steps", data=n_steps),
            dcc.Store(id="room-names", data=room_names),
            dcc.Store(id="setpoint", data=setpoint),
            dcc.Store(id="comfort-band", data=comfort_band),
            dcc.Store(id="current-step", data=0),
            dcc.Store(id="playing", data=False),
            dcc.Interval(
                id="playback-interval",
                interval=_SPEED_MAP["1x"],
                disabled=True,
            ),
            # Header
            html.H1(
                "PumpAhead Simulation Replay",
                style={
                    "textAlign": "center",
                    "fontFamily": "sans-serif",
                    "marginBottom": "10px",
                },
            ),
            # Scenario selector
            html.Div(
                [
                    html.Label(
                        "Load simulation log (JSON or pickle):",
                        style={"fontWeight": "bold", "marginRight": "10px"},
                    ),
                    dcc.Upload(
                        id="upload-log",
                        children=html.Div(
                            [
                                "Drag and drop or ",
                                html.A("click to select a file"),
                            ]
                        ),
                        style={
                            "width": "100%",
                            "height": "50px",
                            "lineHeight": "50px",
                            "borderWidth": "1px",
                            "borderStyle": "dashed",
                            "borderRadius": "5px",
                            "textAlign": "center",
                            "marginBottom": "10px",
                        },
                        multiple=False,
                    ),
                    html.Div(id="upload-status", style={"color": "gray"}),
                ],
                style={"marginBottom": "15px", "padding": "0 20px"},
            ),
            # Playback controls
            html.Div(
                [
                    html.Button(
                        "Step Back",
                        id="btn-step-back",
                        n_clicks=0,
                        style={"marginRight": "5px"},
                    ),
                    html.Button(
                        "Play",
                        id="btn-play-pause",
                        n_clicks=0,
                        style={"marginRight": "5px"},
                    ),
                    html.Button(
                        "Step Forward",
                        id="btn-step-fwd",
                        n_clicks=0,
                        style={"marginRight": "5px"},
                    ),
                    html.Label(
                        "Speed: ",
                        style={"marginLeft": "20px", "marginRight": "5px"},
                    ),
                    dcc.Dropdown(
                        id="speed-selector",
                        options=[{"label": s, "value": s} for s in _SPEED_MAP],
                        value="1x",
                        clearable=False,
                        style={"width": "80px", "display": "inline-block"},
                    ),
                    html.Span(
                        id="step-display",
                        children="Step: 0 / 0",
                        style={"marginLeft": "20px", "fontFamily": "monospace"},
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "0 20px",
                    "marginBottom": "10px",
                },
            ),
            # Timeline slider
            html.Div(
                [
                    dcc.Slider(
                        id="timeline-slider",
                        min=0,
                        max=max(0, n_steps - 1),
                        step=1,
                        value=0,
                        tooltip={"placement": "bottom", "always_visible": False},
                        updatemode="mouseup",
                    ),
                ],
                style={"padding": "0 20px", "marginBottom": "20px"},
            ),
            # Gauges row
            html.Div(
                id="gauges-container",
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "justifyContent": "center",
                    "padding": "0 20px",
                },
            ),
            # Per-room charts container
            html.Div(id="charts-container", style={"padding": "0 20px"}),
            # Weather chart
            html.Div(
                [dcc.Graph(id="weather-chart")],
                style={"padding": "0 20px", "marginTop": "10px"},
            ),
        ],
        style={"maxWidth": "1400px", "margin": "0 auto"},
    )

    # -- Callbacks ------------------------------------------------------------

    @app.callback(  # type: ignore
        Output("log-id", "data"),
        Output("n-steps", "data"),
        Output("room-names", "data"),
        Output("current-step", "data"),
        Output("upload-status", "children"),
        Output("timeline-slider", "max"),
        Output("timeline-slider", "value"),
        Input("upload-log", "contents"),
        State("upload-log", "filename"),
        prevent_initial_call=True,
    )
    def load_scenario(
        contents: str | None, filename: str | None
    ) -> tuple[str, int, list[str], int, str, int, int]:
        """Load an uploaded SimulationLog file."""
        if contents is None or filename is None:
            raise PreventUpdate

        try:
            # Parse the base64-encoded file
            _content_type, content_string = contents.split(",", 1)
            decoded = base64.b64decode(content_string)

            suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

            if suffix == "json":
                from pumpahead.log_serializer import load_json_string

                loaded_log = load_json_string(decoded.decode("utf-8"))
            elif suffix in {"pkl", "pickle"}:
                loaded_log = pickle.loads(decoded)  # noqa: S301
                if not isinstance(loaded_log, SimulationLog):
                    return ("", 0, [], 0, "File does not contain a SimulationLog", 0, 0)
            else:
                return ("", 0, [], 0, f"Unsupported format: .{suffix}", 0, 0)

            new_id = str(uuid.uuid4())
            _LOG_STORE[new_id] = loaded_log
            new_n = len(loaded_log)
            new_rooms = _extract_room_names(loaded_log)

            return (
                new_id,
                new_n,
                new_rooms,
                0,
                f"Loaded {filename}: {new_n} records, {len(new_rooms)} room(s)",
                max(0, new_n - 1),
                0,
            )

        except Exception as exc:
            return ("", 0, [], 0, f"Error loading file: {exc}", 0, 0)

    @app.callback(  # type: ignore
        Output("playing", "data"),
        Output("btn-play-pause", "children"),
        Output("playback-interval", "disabled"),
        Input("btn-play-pause", "n_clicks"),
        State("playing", "data"),
        State("n-steps", "data"),
        prevent_initial_call=True,
    )
    def toggle_playback(
        _n_clicks: int, playing: bool, n_steps_val: int
    ) -> tuple[bool, str, bool]:
        """Toggle play/pause state."""
        if n_steps_val <= 0:
            return (False, "Play", True)
        new_playing = not playing
        label = "Pause" if new_playing else "Play"
        return (new_playing, label, not new_playing)

    @app.callback(  # type: ignore
        Output("playback-interval", "interval"),
        Input("speed-selector", "value"),
    )
    def update_speed(speed: str) -> int:
        """Update the playback interval based on speed selection."""
        return _SPEED_MAP.get(speed, 1000)

    @app.callback(  # type: ignore
        Output("current-step", "data", allow_duplicate=True),
        Output("playing", "data", allow_duplicate=True),
        Output("btn-play-pause", "children", allow_duplicate=True),
        Output("playback-interval", "disabled", allow_duplicate=True),
        Input("playback-interval", "n_intervals"),
        State("current-step", "data"),
        State("n-steps", "data"),
        State("playing", "data"),
        prevent_initial_call=True,
    )
    def advance_step(
        _n_intervals: int, step: int, n_steps_val: int, playing: bool
    ) -> tuple[int, bool, str, bool]:
        """Advance one step during playback."""
        if not playing or n_steps_val <= 0:
            raise PreventUpdate
        new_step = step + 1
        if new_step >= n_steps_val:
            # Stop at end
            return (n_steps_val - 1, False, "Play", True)
        return (new_step, True, "Pause", False)

    @app.callback(  # type: ignore
        Output("current-step", "data", allow_duplicate=True),
        Input("btn-step-fwd", "n_clicks"),
        State("current-step", "data"),
        State("n-steps", "data"),
        prevent_initial_call=True,
    )
    def step_forward(_n_clicks: int, step: int, n_steps_val: int) -> int:
        """Increment step by 1."""
        if n_steps_val <= 0:
            raise PreventUpdate
        return min(step + 1, n_steps_val - 1)

    @app.callback(  # type: ignore
        Output("current-step", "data", allow_duplicate=True),
        Input("btn-step-back", "n_clicks"),
        State("current-step", "data"),
        State("n-steps", "data"),
        prevent_initial_call=True,
    )
    def step_backward(_n_clicks: int, step: int, n_steps_val: int) -> int:
        """Decrement step by 1."""
        if n_steps_val <= 0:
            raise PreventUpdate
        return max(step - 1, 0)

    @app.callback(  # type: ignore
        Output("current-step", "data", allow_duplicate=True),
        Input("timeline-slider", "value"),
        prevent_initial_call=True,
    )
    def sync_slider(value: int) -> int:
        """Sync current step from slider position."""
        return value

    @app.callback(  # type: ignore
        Output("timeline-slider", "value", allow_duplicate=True),
        Output("step-display", "children"),
        Input("current-step", "data"),
        State("n-steps", "data"),
        prevent_initial_call=True,
    )
    def update_slider_from_step(step: int, n_steps_val: int) -> tuple[int, str]:
        """Keep slider in sync with current step."""
        display = f"Step: {step} / {max(0, n_steps_val - 1)}"
        return (step, display)

    @app.callback(  # type: ignore
        Output("gauges-container", "children"),
        Output("charts-container", "children"),
        Output("weather-chart", "figure"),
        Input("current-step", "data"),
        Input("log-id", "data"),
        State("n-steps", "data"),
        State("room-names", "data"),
        State("setpoint", "data"),
        State("comfort-band", "data"),
    )
    def update_charts(
        step: int,
        log_id: str,
        n_steps_val: int,
        room_names_val: list[str],
        setpoint_val: float,
        comfort_band_val: float,
    ) -> tuple[list[Any], list[Any], Any]:
        """Rebuild all charts and gauges for the current step."""
        dcc_mod = __import__("dash", fromlist=["dcc"]).dcc
        html_mod = __import__("dash", fromlist=["html"]).html

        if not log_id or log_id not in _LOG_STORE or n_steps_val <= 0:
            empty = _build_empty_figure("No simulation data loaded")
            return (
                [
                    html_mod.Div(
                        "No data loaded",
                        style={"color": "gray", "textAlign": "center"},
                    )
                ],
                [dcc_mod.Graph(figure=empty)],
                empty,
            )

        current_log = _LOG_STORE[log_id]
        step = max(0, min(step, n_steps_val - 1))

        gauges: list[Any] = []
        charts: list[Any] = []

        for room_name in room_names_val:
            records = _get_room_records(current_log, room_name)
            if not records:
                continue

            # Find the record closest to the current step for this room
            # The log may interleave rooms, so we use the step index
            # relative to the room's own records
            room_step = min(step, len(records) - 1)

            # Gauge
            current_record = records[room_step]
            gauge_fig = _build_gauge(
                t_room=current_record.T_room,
                setpoint=setpoint_val,
                comfort_band=comfort_band_val,
                room_name=room_name,
            )
            gauges.append(
                html_mod.Div(
                    dcc_mod.Graph(figure=gauge_fig, config={"displayModeBar": False}),
                    style={"width": "250px", "display": "inline-block"},
                )
            )

            # Temperature chart
            temp_fig = _build_temperature_figure(
                records,
                room_step,
                room_name,
                setpoint_val,
                comfort_band_val,
            )
            charts.append(dcc_mod.Graph(figure=temp_fig))

            # Valve chart
            valve_fig = _build_valve_figure(records, room_step, room_name)
            charts.append(dcc_mod.Graph(figure=valve_fig))

            # Split chart
            split_fig = _build_split_figure(records, room_step, room_name)
            charts.append(dcc_mod.Graph(figure=split_fig))

        # Weather chart (uses the full log, step mapped to overall index)
        weather_step = max(0, min(step, len(current_log) - 1))
        weather_fig = _build_weather_figure(current_log, weather_step)

        return (gauges, charts, weather_fig)

    return app
