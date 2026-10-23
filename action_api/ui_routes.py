"""Mount with app.include_router(ui_router); imports of the hands service are lazy."""
from ui.api import ControlRoom, make_router

router = make_router(ControlRoom(real=True))
