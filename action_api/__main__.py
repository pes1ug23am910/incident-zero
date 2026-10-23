"""Run the localhost Action API, or latch/clear STOP from an operator terminal."""
import argparse
import json
from .service import ActionService


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "stop", "clear-stop"), nargs="?", default="serve")
    parser.add_argument("--operator", default="local operator")
    parser.add_argument("--confirmation")
    args = parser.parse_args(argv)
    if args.command == "serve":
        import uvicorn
        uvicorn.run("action_api.app:app", host="127.0.0.1", port=8787)
    elif args.command == "stop":
        print(json.dumps(ActionService().stop(args.operator)))
    else:
        phrase = args.confirmation or input("Type I confirm the incident is over: ")
        print(json.dumps(ActionService().clear_stop(phrase, args.operator)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
