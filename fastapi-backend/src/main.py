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

# Optional generator import (deferred import so dependencies are optional)
try:
    from generators.generate_neo4j_mock import generate_neo4j_mock_data  # type: ignore
except Exception:
    generate_neo4j_mock_data = None

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

        # Optionally run the neo4j mock data generator in background on startup.
        # Controlled via env var: NEO4J_MOCK_RUN=true
        try:
            run_mock = os.environ.get("NEO4J_MOCK_RUN", "false").lower() in ("1", "true", "yes")
            if run_mock:
                if generate_neo4j_mock_data is None:
                    logger.error(
                        "Generator not available: ensure requirements (faker, neo4j driver) are installed"
                    )
                else:
                    # read optional env overrides
                    seed = int(os.environ.get("NEO4J_MOCK_SEED", "42"))
                    n_instruments = int(os.environ.get("NEO4J_MOCK_N_INSTRUMENTS", "20000"))
                    n_issuers = int(os.environ.get("NEO4J_MOCK_N_ISSUERS", "2000"))
                    n_counterparties = int(os.environ.get("NEO4J_MOCK_N_COUNTERPARTIES", "2000"))
                    n_trades = int(os.environ.get("NEO4J_MOCK_N_TRADES", "200000"))
                    n_signals = int(os.environ.get("NEO4J_MOCK_N_SIGNALS", "50000"))
                    n_events = int(os.environ.get("NEO4J_MOCK_N_EVENTS", "50000"))
                    corr_top_k = int(os.environ.get("NEO4J_MOCK_CORR_TOP_K", "10"))

                    gen_args = {
                        "seed": seed * 2,
                        "n_instruments": n_instruments * 2,
                        "n_issuers": n_issuers * 2,
                        "n_counterparties": n_counterparties * 2,
                        "n_trades": n_trades * 2,
                        "n_signals": n_signals * 2,
                        "n_events": n_events * 2,
                        "corr_top_k": corr_top_k * 2,
                        "mode": "csv",
                        "batch_size": 2000 * 2,
                    }

                    logger.info(
                        "Scheduling neo4j mock generator in background with args: %s", gen_args
                    )

                    def run_generator():
                        try:
                            generate_neo4j_mock_data(gen_args)
                            logger.info("Neo4j mock generation finished")
                        except Exception:
                            logger.exception("Neo4j mock generation failed")

                    # Run in a background thread so startup is not blocked.
                    executor = ThreadPoolExecutor(max_workers=1)
                    executor.submit(run_generator)
        except Exception:
            logger.exception("Failed to schedule neo4j mock generator")

        logger.info("Application startup complete")
        yield
    finally:
        logger.info("Application shutdown complete")


app = FastAPI(
    title="Cereon LinkedIn Analyzer Server",
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
