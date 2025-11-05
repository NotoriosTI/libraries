from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.adapters.chatwoot_real import ChatwootRESTAdapter
from src.adapters.sqlite_db_adapter import SQLiteDBAdapter
from src.dependencies import set_chatwoot_adapter, set_db_adapter
from src.routers import health, monitor, outbound, webhook
from src.workers.outbound_worker import OutboundWorker
from src.env_manager import get_config, init_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_config("config/config_vars.yaml")

    settings = {
        "chatwoot_account_id": get_config("CHATWOOT_ACCOUNT_ID"),
        "chatwoot_base_url": get_config("CHATWOOT_BASE_URL"),
        "chatwoot_api_key": get_config("CHATWOOT_API_KEY"),
        "port": get_config("PORT"),
    }

    print(
        "[Config] Loaded Chatwoot account="
        f"{settings['chatwoot_account_id']}, base_url={settings['chatwoot_base_url']}"
    )

    db_adapter = SQLiteDBAdapter()
    await db_adapter.init_db()
    print("[DB] SQLite initialized.")
    chatwoot_adapter = ChatwootRESTAdapter(
        settings["chatwoot_base_url"],
        settings["chatwoot_api_key"],
        str(settings["chatwoot_account_id"]),
    )
    worker = OutboundWorker(db_adapter, chatwoot_adapter)

    set_db_adapter(db_adapter)
    set_chatwoot_adapter(chatwoot_adapter)

    app.state.db_adapter = db_adapter
    app.state.chatwoot_adapter = chatwoot_adapter
    app.state.settings = settings

    await worker.start()
    app.state.outbound_worker = worker
    try:
        yield
    finally:
        await worker.stop()
        app.state.outbound_worker = None


app = FastAPI(title="Chatwoot Processor", lifespan=lifespan)

app.include_router(webhook.router)
app.include_router(outbound.router)
app.include_router(health.router)
app.include_router(monitor.router)
