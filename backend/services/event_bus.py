"""In-memory async event bus for SSE streaming with replay buffer."""

import asyncio
import json
import time
from collections import defaultdict
from typing import AsyncGenerator, Dict, List


class EventBus:
    """Pub/sub event bus that buffers events so late subscribers don't miss them."""

    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._buffers: Dict[str, List[dict]] = defaultdict(list)
        self._completed: Dict[str, float] = {}

    async def publish(self, job_id: str, event_type: str, data: dict):
        """Publish an event to all subscribers and buffer it for late joiners."""
        message = {"event": event_type, "data": data}
        self._buffers[job_id].append(message)
        for queue in self._subscribers.get(job_id, []):
            await queue.put(message)
        if event_type == "done":
            self._completed[job_id] = time.time()
            self._cleanup_old()

    async def subscribe(self, job_id: str) -> AsyncGenerator[dict, None]:
        """Subscribe to events for a job. Replays buffered events first.
        
        Yields raw dicts — sse-starlette handles the SSE formatting.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[job_id].append(queue)

        try:
            # Replay buffered events first
            for message in self._buffers.get(job_id, []):
                yield {"data": json.dumps(message)}
                if message["event"] == "done":
                    return

            # Then listen for new events
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=120.0)
                    yield {"data": json.dumps(message)}
                    if message["event"] == "done":
                        break
                except asyncio.TimeoutError:
                    yield {"data": json.dumps({"event": "ping", "data": {"message": "keepalive"}})}
        finally:
            if job_id in self._subscribers:
                try:
                    self._subscribers[job_id].remove(queue)
                except ValueError:
                    pass
                if not self._subscribers[job_id]:
                    del self._subscribers[job_id]

    def is_job_done(self, job_id: str) -> bool:
        return job_id in self._completed

    def get_buffer(self, job_id: str) -> list:
        return self._buffers.get(job_id, [])

    def _cleanup_old(self):
        now = time.time()
        expired = [jid for jid, ts in self._completed.items() if now - ts > 300]
        for jid in expired:
            self._completed.pop(jid, None)
            self._buffers.pop(jid, None)
            self._subscribers.pop(jid, None)


# Global singleton
event_bus = EventBus()
