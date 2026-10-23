"""Control Room routes share the Action API's existing service boundary."""
from ui.api import ControlRoom, make_router


def create_room(service_factory, reports_dir=None, runs_dir=None):
    from ui.action_backend import ActionBackend
    room = ControlRoom(reports_dir, runs_dir, real=True)
    room._backend = ActionBackend(room, service_factory)
    return room


# Kept for callers that mount the router directly. The main app injects its own
# lazy service factory so both HTTP surfaces use the same policy and state.
router = make_router(ControlRoom(real=True))
