from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db.session import get_async_engine
from src.env_manager import init_config
from src.routers import health, monitor, outbound, webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialise configuration once and dispose the shared database engine on shutdown.
    """

    init_config("config/config_vars.yaml")
    try:
        yield
    finally:
        engine = get_async_engine()
        await engine.dispose()


app = FastAPI(title="Chatwoot Processor", lifespan=lifespan)

app.include_router(webhook.router)
app.include_router(outbound.router)
app.include_router(health.router)
app.include_router(monitor.router)
