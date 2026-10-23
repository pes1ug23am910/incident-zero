"""Localhost HTTP surface. Approval is collected in the server's terminal."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .service import ActionService, ALLOWLIST
from .safety import Blocked


def create_app(service=None, input_fn=input):
    app = FastAPI(title="Incident Zero Action API")
    # Lazy creation keeps importing the app free of Docker reads and mutations.
    boundary = service

    def api():
        nonlocal boundary
        if boundary is None:
            boundary = ActionService()
        return boundary

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            return JSONResponse({"decision": "BLOCK", "reason_codes": ["LOCAL_ONLY"]}, status_code=403)
        return await call_next(request)

    @app.exception_handler(Blocked)
    async def blocked(request, exc):
        return JSONResponse(exc.payload(), status_code=exc.status)

    @app.exception_handler(KeyError)
    async def malformed(request, exc):
        return JSONResponse({"decision": "BLOCK", "reason_codes": ["MALFORMED_REQUEST"]}, status_code=422)

    @app.get("/health")
    def health():
        api().log("health")
        return {"ok": True, "stopped": api().stop_path.exists()}

    @app.get("/actions")
    def actions():
        api().log("list_actions")
        return {"actions": ALLOWLIST, "scale_service": "not_available_on_compose"}

    @app.post("/actions/dry-run")
    def dry_run(body: dict):
        if body.get('alert'):
            api().bind_alert(body['report'], body['alert'])
        return api().dry_run(body, body["report"])

    @app.post("/approvals")
    def approvals(body: dict):
        # HTTP cannot request test bypass or submit a fake boolean human answer.
        return api().approve(body, body["report"], body["preview"], body["operator"], input_fn=input_fn,
                             policy_approval=body.get("policy_approval", False))

    @app.post("/actions/execute")
    def execute(body: dict):
        return api().execute(body, body["report"], body.get("approval_token", body.get("token")), body.get("idempotency_key"))

    @app.post("/actions/verify")
    def verify(body: dict):
        return api().verify(body["idempotency_key"])

    @app.post("/stop")
    def stop(body: dict):
        return api().stop(body.get("operator", "local operator"))

    @app.delete("/stop")
    def clear(body: dict):
        return api().clear_stop(body["confirmation"], body["operator"])

    return app


app = create_app()
