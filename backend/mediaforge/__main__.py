from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ControlDeck Media Forge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9130)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error("G0 binds to loopback only")
    uvicorn.run("mediaforge.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
