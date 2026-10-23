"""FastAPI app factory. Bind it to 127.0.0.1: `uvicorn api.main:app --host 127.0.0.1`."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.controller import RunController
from api.routes import router
from api.settings import Settings

VITE_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


def _mount_web(app: FastAPI, dist: Path) -> None:
    """Serve the built web app from the API's own origin (`npm run build` in web/).

    Only `dist/assets` is exposed as files; every other non-API path returns `index.html` so React
    Router deep links survive a refresh. Nothing outside `dist` is ever read.
    """
    index = dist / "index.html"
    if not index.is_file():
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        return FileResponse(index)


def create_app(settings: Settings | None = None, web_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="Groww Weekly Review Pulse API", docs_url=None, redoc_url=None)
    app.state.settings = settings or Settings.load()
    app.state.controller = RunController(app.state.settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=VITE_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    _mount_web(app, WEB_DIST if web_dist is None else web_dist)
    return app


def __getattr__(name: str) -> FastAPI:
    # `uvicorn api.main:app` builds the app lazily so importing this module has no side effects.
    if name == "app":
        return create_app()
    raise AttributeError(name)
