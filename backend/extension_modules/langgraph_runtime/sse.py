from __future__ import annotations

import json
import time
from typing import Any
import queue


def make_send_delta(out_q: "queue.Queue[str]", model_name: str) -> Any:
    stream_id = f"chatcmpl-{int(time.time())}"

    def _send(text: str) -> None:
        if not text:
            return
        chunk = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name,
            "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
        }
        out_q.put(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n")

    return _send


def send_done(out_q: "queue.Queue[str]") -> None:
    out_q.put("data: [DONE]\n\n")


