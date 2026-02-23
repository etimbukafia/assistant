"""Playground FastAPI app."""

import logging
import os
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.db import init_db  # noqa: E402
from app.routes.context_entries import router as context_router  # noqa: E402
from app.routes.contacts import router as contacts_router  # noqa: E402
from app.routes.entity_references import router as entity_refs_router  # noqa: E402
from app.routes.chat import router as chat_router  # noqa: E402
from app.routes.admin_context import router as admin_context_router  # noqa: E402
from app.routes.hot_cache import router as hot_cache_router  # noqa: E402
from app.routes.warm_cache import router as warm_cache_router  # noqa: E402
from app.routes.inbox import router as inbox_router  # noqa: E402
from app.routes.calendar import router as calendar_router  # noqa: E402
from app.routes.action_tools import router as action_tools_router  # noqa: E402
from app.routes.v1.chat import router as v1_chat_router  # noqa: E402


log_level = os.getenv("LOG_LEVEL", "INFO").upper()
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, log_level, logging.INFO))
if not root_logger.handlers:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

app = FastAPI(title="Playground API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(context_router, prefix="/api")
app.include_router(contacts_router, prefix="/api")
app.include_router(entity_refs_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(admin_context_router, prefix="/api")
app.include_router(hot_cache_router, prefix="/api")
app.include_router(warm_cache_router, prefix="/api")
app.include_router(inbox_router, prefix="/api")
app.include_router(calendar_router, prefix="/api")
app.include_router(action_tools_router, prefix="/api")
app.include_router(v1_chat_router, prefix="/v1")
