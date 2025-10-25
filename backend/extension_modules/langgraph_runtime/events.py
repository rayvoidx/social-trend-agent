from __future__ import annotations

import asyncio
from typing import Any, Optional


async def emit_status(
    event_emitter: Optional[Any],
    description: str,
    *,
    done: bool = False,
    hidden: bool = False,
) -> None:
    if not event_emitter:
        return
    payload = {
        "type": "status",
        "data": {"description": description.strip(), "done": done, "hidden": hidden},
    }
    try:
        if asyncio.iscoroutinefunction(event_emitter):
            await event_emitter(payload)
        else:
            # Fall back to sync callable if provided
            event_emitter(payload)
    except Exception:
        # Swallow emitter errors to avoid breaking the main flow
        return


async def emit_message(
    event_emitter: Optional[Any],
    content: str,
    *,
    role: str = "assistant",
    meta: Optional[dict] = None,
) -> None:
    if not event_emitter:
        return
    data = {"role": role, "content": content}
    if meta:
        data.update(meta)
    payload = {"type": "message", "data": data}
    try:
        if asyncio.iscoroutinefunction(event_emitter):
            await event_emitter(payload)
        else:
            event_emitter(payload)
    except Exception:
        return


