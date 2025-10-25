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


def tool_event_to_status_desc(tool_evt: dict) -> str:
    name = tool_evt.get("name") or "툴 실행"
    args_preview = tool_evt.get("args_preview")
    complete = bool(tool_evt.get("complete", False))

    # 인자가 아직 완성되지 않았으면 조각 텍스트 대신 진행 메시지로 표시
    if not complete or args_preview is None:
        return f"툴 실행: {name} | 인자 수신 중..."

    # 완성된 JSON이면 간결 요약으로 표시
    try:
        data = json.loads(args_preview)

        def _short(v):
            if isinstance(v, (int, float)):
                return str(v)
            if isinstance(v, str):
                return (v[:48] + "...") if len(v) > 48 else v
            if isinstance(v, list):
                return f"[{len(v)}]"
            if isinstance(v, dict):
                return "{...}"
            return str(v)

        summary = None
        if isinstance(data, dict):
            items = list(data.items())[:3]
            summary = ", ".join([f"{k}: {_short(v)}" for k, v in items])
        elif isinstance(data, list):
            summary = f"목록 {len(data)}개"
        else:
            summary = _short(data)

        return f"툴 실행: {name} | 인자: {summary}"
    except Exception:
        # JSON 파싱이 안 되면 안전하게 잘라서 표시
        text = str(args_preview)
        text = text.replace("\n", " ").replace("\r", " ")
        if len(text) > 160:
            text = text[:160] + "..."
        return f"툴 실행: {name} | 인자: {text}"


