"""Vercel entry point for the FastAPI app.

Vercel runs this file as one serverless function; ``app`` is the ASGI callable.
``vercel.json`` rewrites every path (``/``, ``/static/...``, ``/api/...``) to
this function, so FastAPI keeps serving the dashboard, the static assets and the
API exactly as it does locally.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import app  # noqa: E402  (import after sys.path is fixed)

__all__ = ["app"]
