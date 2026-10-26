from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
register_error_handlers(app)
app.include_router(api_router, prefix=settings.api_prefix)

if settings.static_dir and Path(settings.static_dir).is_dir():
    # Na imagem Docker, o frontend compilado sai da mesma origem da API. Montado por último
    # para não encobrir as rotas /api.
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")
