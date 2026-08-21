from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("doctor", "serve"))
    args = parser.parse_args()
    if args.operation == "doctor":
        from mediaforge import __version__
        from mediaforge.app import create_app

        create_app
        print(json.dumps({"status": "ok", "version": __version__, "packaged": bool(getattr(sys, "frozen", False))}))
        return 0

    import uvicorn

    from mediaforge.app import create_app

    port = int(os.environ.get("MEDIA_FORGE_PORT", "9130"))
    uvicorn.run(create_app(), host="127.0.0.1", port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
