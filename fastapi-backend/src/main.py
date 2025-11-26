# apps/cereon-demo-server/src/main.py
import logging
import os
from typing import List, Optional
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

import uvicorn
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException

from settings import get_settings
from cards import ALL_OVERVIEW_CARDS


settings = get_settings()

LOG_LEVEL = (settings.log_level or "INFO").upper()
HOST = settings.host
PORT = int(settings.port)

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Starting application...")
        try:
            for CardCls in ALL_OVERVIEW_CARDS:
                try:
                    CardCls(app).as_route(app=app)
                    logger.info(
                        "Registered card route: %s/%s", CardCls.route_prefix, CardCls.card_id
                    )
                except Exception as e:
                    logger.exception(
                        "Failed to register route for %s: %s",
                        getattr(CardCls, "card_id", repr(CardCls)),
                        e,
                    )
        except Exception:
            logger.exception("Unexpected error while registering overview card routes")

        logger.info("Application startup complete")
        yield
    finally:
        logger.info("Application shutdown complete")


app = FastAPI(
    title="Cereon Demo Server",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins or ["*"],
    allow_credentials=bool(settings.cors_allow_credentials),
    allow_methods=settings.cors_allow_methods or ["*"],
    allow_headers=settings.cors_allow_headers or ["*"],
)


@app.get("/", response_class=JSONResponse)
async def root():
    return JSONResponse({"ok": True, "service": "cereon-demo-server"})


@app.get("/health", response_class=JSONResponse)
async def health():
    """
    Lightweight health endpoint. For deeper health checks (DB, vectorstore, etc.)
    call into core.db.health_check() from your monitoring infra.
    """
    try:
        return JSONResponse({"ok": True})
    except Exception as exc:
        logger.exception("Health check failed: %s", exc)
        raise HTTPException(status_code=500, detail="health check failed")


if __name__ == "__main__":
    logger.info("Starting %s on %s:%d", app.title, HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL.lower())
