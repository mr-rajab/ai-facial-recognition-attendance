"""FastAPI app: session middleware + portal (admin/student accounts, attendance)."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from portal_bootstrap import ensure_bootstrap_admin
from portal_router import build_router
from rate_limit import limiter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ENV_PRIMARY = os.path.join(ROOT, ".env")
_ENV_CWD = os.path.join(os.getcwd(), ".env")


def _merge_env_file(path: str) -> None:
    if not os.path.isfile(path):
        return
    try:
        from io import StringIO

        from dotenv import dotenv_values

        with open(path, encoding="utf-8-sig") as handle:
            pairs = dotenv_values(stream=StringIO(handle.read()))
        for key, val in pairs.items():
            if not key or val is None:
                continue
            val = str(val).strip()
            cur = str(os.environ.get(key, "")).strip()
            if cur == "":
                os.environ[key] = val
    except ImportError:
        with open(path, encoding="utf-8-sig") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and str(os.environ.get(k, "")).strip() == "":
                    os.environ[k] = v


def _load_dotenv_files() -> None:
    if os.path.isfile(_ENV_PRIMARY):
        _merge_env_file(_ENV_PRIMARY)
    elif os.path.isfile(_ENV_CWD) and os.path.abspath(_ENV_CWD) != os.path.abspath(_ENV_PRIMARY):
        _merge_env_file(_ENV_CWD)


_load_dotenv_files()

templates = Jinja2Templates(directory=os.path.join(ROOT, "templates"))
_log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    env_path = _ENV_PRIMARY if os.path.isfile(_ENV_PRIMARY) else (_ENV_CWD if os.path.isfile(_ENV_CWD) else "")
    ensure_bootstrap_admin()
    import sqlite3

    import init_db as _idb

    conn = sqlite3.connect(_idb.DB_PATH)
    nu = int(conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0])
    conn.close()
    _log.warning("web_app: ROOT=%s | .env=%s | users=%s", ROOT, env_path or "(none)", nu)
    _log.warning("web_app: quick attendance enabled — GET /quick-attendance (no login)")
    yield


app = FastAPI(title="Attendance System", version="2.0", lifespan=_lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", "change-me-set-SECRET_KEY-in-production"),
    https_only=False,
)
app.mount("/static", StaticFiles(directory=os.path.join(ROOT, "static")), name="static")

app.include_router(build_router(templates, ROOT))


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
