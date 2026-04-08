"""Command-line entry point: ``python -m pumpahead.replay``.

Supports optional arguments:

    --log PATH   Path to a JSON or pickle SimulationLog file.
    --port PORT  Port for the Dash server (default 8050).
    --debug      Enable Dash debug mode with hot reloading.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    """Parse CLI arguments and launch the Dash replay application."""
    parser = argparse.ArgumentParser(
        description="PumpAhead interactive simulation replay (Plotly Dash)",
    )
    parser.add_argument(
        "--log",
        type=str,
        default=None,
        help="Path to a SimulationLog file (JSON or pickle).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port for the Dash server (default: 8050).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable Dash debug mode.",
    )

    args = parser.parse_args()

    # Load log if path provided
    from pumpahead.simulation_log import SimulationLog

    log: SimulationLog | None = None
    if args.log is not None:
        log_path = Path(args.log)
        if not log_path.exists():
            print(f"Error: log file not found: {log_path}", file=sys.stderr)
            sys.exit(1)

        suffix = log_path.suffix.lower()
        if suffix == ".json":
            from pumpahead.log_serializer import load_json

            log = load_json(log_path)
        elif suffix in {".pkl", ".pickle"}:
            from pumpahead.log_serializer import load_pickle

            log = load_pickle(log_path)
        else:
            print(
                f"Error: unsupported file format '{suffix}'. "
                "Use .json or .pkl/.pickle.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Loaded log with {len(log)} records from {log_path}")

    from pumpahead.replay.app import create_app

    app = create_app(log=log)
    app.run(port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
