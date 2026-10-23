"""Playwright-free HTTP smoke test against an already running Control Room."""
import argparse
import json
from urllib.request import urlopen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8788")
    args = parser.parse_args(argv)
    base = args.url.rstrip("/")

    def fetch(path):
        with urlopen(base + path, timeout=10) as response:
            assert response.status == 200, path
            return response.read().decode("utf-8")

    html, js, css = fetch("/"), fetch("/static/app.js"), fetch("/static/app.css")
    for view in ("war-room", "incidents", "services", "approvals", "safety"):
        assert f'id="{view}"' in html and f'data-view="{view}"' in html, view
    assert "pollEvents" in js and "approvalPanel" in js and "--bg" in css
    assert isinstance(json.loads(fetch("/api/incidents")), list)
    assert "stopped" in json.loads(fetch("/api/stop"))
    assert "pending" in json.loads(fetch("/api/approvals"))
    print("PASS: HTML, CSS, JS, five views, incidents, approvals and STOP reads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
