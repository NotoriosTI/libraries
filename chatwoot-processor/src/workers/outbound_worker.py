import asyncio
from contextlib import suppress

from src.adapters.mock_chatwoot_adapter import MockChatwootAdapter
from src.adapters.mock_db_adapter import MockDBAdapter


class OutboundWorker:
    """
    Async background worker that flushes queued outbound messages to Chatwoot.
    """

    def __init__(
        self,
        db: MockDBAdapter,
        chatwoot: MockChatwootAdapter,
        poll_interval: float = 3.0,
    ) -> None:
        self.db = db
        self.chatwoot = chatwoot
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def run(self) -> None:
        if self._running:
            return
        self._running = True
        print("[Worker] Outbound worker started")
        try:
            while self._running:
                await self._process_outbound_messages()
                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            print("[Worker] Outbound worker cancelled")
            raise
        finally:
            self._running = False

    async def _process_outbound_messages(self) -> None:
        queued = await self.db.fetch_queued_outbound()
        if not queued:
            return

        for message in queued:
            success = await self.chatwoot.send_message(message)
            new_status = "sent" if success else "failed"
            await self.db.update_status(message.id, new_status)

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            print("[Worker] Outbound worker stopped")
