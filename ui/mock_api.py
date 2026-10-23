"""Run with python -m ui.mock_api; all decisions are in memory."""
from fastapi import FastAPI
from ui.api import ControlRoom, make_router


def create_app(reports_dir=None, runs_dir=None):
    app = FastAPI(title="Incident Zero Control Room (mock)")
    app.state.control_room = ControlRoom(reports_dir, runs_dir)
    app.include_router(make_router(app.state.control_room))
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8788)
