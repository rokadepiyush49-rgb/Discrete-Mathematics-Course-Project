"""Command line entry point: `route-resilience build` and `route-resilience serve`."""

from __future__ import annotations

import argparse

from .pipeline import build


def main() -> None:
    parser = argparse.ArgumentParser(prog="route-resilience", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="run the full analysis and write artifacts/results.json")
    serve = commands.add_parser("serve", help="start the API and dashboard")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.command == "build":
        build()
    else:
        import uvicorn

        uvicorn.run("route_resilience.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
