from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_HTML = (Path(__file__).parent.parent.parent / "static" / "index.html").read_text()


@router.get("/", response_class=HTMLResponse)
async def index():
    return _HTML
