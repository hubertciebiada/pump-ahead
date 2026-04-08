"""Interactive Plotly Dash replay application for simulation logs.

Provides ``create_app()`` which returns a ``dash.Dash`` instance for
step-by-step replay of a ``SimulationLog``.  The app includes a timeline
slider, play/pause/step controls, synchronized per-room charts, weather
overlay, and per-room gauges.

Dash and Plotly are optional dependencies (``viz`` extra).  Importing
this package when they are not installed raises ``ImportError`` with
installation instructions.

Typical usage::

    from pumpahead.replay import create_app

    app = create_app(log)
    app.run(debug=True)

Or via the command line::

    python -m pumpahead.replay --log results/cold_snap.json --port 8050
"""

from pumpahead.replay.app import create_app

__all__ = ["create_app"]
