#!/usr/bin/env python
from __future__ import annotations

import argparse

import uvicorn


def main(host: str, port: int, reload: bool, workers: int) -> None:
    """Run FastAPI app."""
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Glupper backend")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_false", dest="reload")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    main(host=args.host, port=args.port, reload=args.reload, workers=args.workers)
