from contextlib import asynccontextmanager

from env_manager import get_config, init_config
from fastapi import FastAPI

from src.adapters.mock_chatwoot_adapter import MockChatwootAdapter
from src.adapters.mock_db_adapter import MockDBAdapter
from src.dependencies import set_chatwoot_adapter, set_db_adapter
from src.routers import health, inbound
from src.workers.outbound_worker import OutboundWorker

init_config("config/config_vars.yaml")

CHATWOOT_API_KEY = get_config("CHATWOOT_API_KEY")
CHATWOOT_ACCOUNT_ID = get_config("CHATWOOT_ACCOUNT_ID")
CHATWOOT_BASE_URL = get_config("CHATWOOT_BASE_URL")
PORT = get_config("PORT")

print(f"[Config] Loaded Chatwoot account={CHATWOOT_ACCOUNT_ID}, base_url={CHATWOOT_BASE_URL}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_adapter = MockDBAdapter()
    chatwoot_adapter = MockChatwootAdapter()
    worker = OutboundWorker(db_adapter, chatwoot_adapter)

    set_db_adapter(db_adapter)
    set_chatwoot_adapter(chatwoot_adapter)

    await worker.start()
    app.state.outbound_worker = worker
    try:
        yield
    finally:
        await worker.stop()
        app.state.outbound_worker = None


app = FastAPI(title="Chatwoot Processor (Mock)", lifespan=lifespan)

app.include_router(health.router)
app.include_router(inbound.router)
