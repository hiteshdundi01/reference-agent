"""Serving the dashboard's build, when it has been built: its files at their own
paths, and index.html for every other path outside /api, so the dashboard's own
routes load."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.status import HTTP_404_NOT_FOUND
from starlette.types import Scope


class DashboardFiles(StaticFiles):
    """The build's files, falling back to index.html for the dashboard's routes."""

    async def get_response(self, path: str, scope: Scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != HTTP_404_NOT_FOUND or path.startswith("api/"):
                raise
            return FileResponse(Path(str(self.directory)) / "index.html")


def serve_dashboard(app: FastAPI, build: Path) -> None:
    """Serve the build at / when it exists; with no build, the app is the API alone."""
    if build.is_dir():
        app.mount("/", DashboardFiles(directory=build, html=True), name="dashboard")
