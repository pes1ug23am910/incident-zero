"""Start the Control Room without a frontend build step."""
import argparse
import os
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("mock", "real"), default="mock")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reports-dir", type=Path)
    parser.add_argument("--runs-dir", type=Path)
    args = parser.parse_args(argv)
    if args.reports_dir:
        os.environ["INCIDENT_ZERO_REPORTS_DIR"] = str(args.reports_dir.resolve())
    if args.runs_dir:
        os.environ["INCIDENT_ZERO_RUNS_DIR"] = str(args.runs_dir.resolve())
    import uvicorn
    from fastapi import FastAPI
    from ui.api import ControlRoom, make_router
    room = ControlRoom(real=args.mode == "real")
    app = FastAPI(title="Incident Zero Control Room")
    app.state.control_room = room
    app.include_router(make_router(room))
    port = args.port or (8788 if args.mode == "mock" else 8787)
    print(f"Control Room: http://127.0.0.1:{port} · {room.mode()} · reports: {room.reports}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
