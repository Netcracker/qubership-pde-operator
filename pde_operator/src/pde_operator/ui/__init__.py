from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

UI_DIR = Path(__file__).resolve().parent / "standalone"


def mount_ui(app: FastAPI) -> None:
    """Serve the shared React SPA at /ui with History API deep-link fallback."""

    @app.get("/")
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/", status_code=307)

    @app.get("/ui")
    @app.get("/ui/")
    async def ui_root() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")

    @app.get("/ui/{resource_path:path}")
    async def ui_spa(resource_path: str) -> FileResponse:
        # Serve any real file under standalone/ (app.js, styles.css, fontawesome/...)
        candidate = (UI_DIR / resource_path).resolve()
        try:
            candidate.relative_to(UI_DIR.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(UI_DIR / "index.html")
