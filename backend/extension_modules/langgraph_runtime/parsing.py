from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple


class ToolArgsBuffer:
    def __init__(self) -> None:
        self._buffers: Dict[str, str] = {}

    def append(self, call_id: str, piece: str) -> Tuple[Optional[dict], bool]:
        buf = self._buffers.get(call_id, "") + str(piece)
        self._buffers[call_id] = buf
        try:
            parsed = json.loads(buf)
            return parsed, True
        except json.JSONDecodeError:
            return None, False


def _from_additional_kwargs(val: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    tool_name: Optional[str] = None
    tool_args_str: Optional[str] = None
    tool_call_id: Optional[str] = None

    additional_kwargs = getattr(val, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict):
        tool_calls = additional_kwargs.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            item = tool_calls[0] or {}
            fn = item.get("function", {}) or {}
            tool_name = fn.get("name")
            tool_args_str = fn.get("arguments")
            tool_call_id = item.get("id")

    return tool_name, tool_args_str, tool_call_id


def _from_tool_calls(val: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    tool_name: Optional[str] = None
    tool_args_str: Optional[str] = None
    tool_call_id: Optional[str] = None

    tool_calls = getattr(val, "tool_calls", None)
    if isinstance(tool_calls, list) and tool_calls:
        item = tool_calls[0] or {}
        tool_name = item.get("name")
        args = item.get("args")
        if args not in (None, {}):
            tool_args_str = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
        tool_call_id = item.get("id")

    return tool_name, tool_args_str, tool_call_id


def _from_tool_call_chunks(val: Any, buffers: ToolArgsBuffer, fallback_id: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[dict], bool, Optional[str]]:
    chunks = getattr(val, "tool_call_chunks", None)
    if not chunks:
        return None, None, None, False, None

    item = (chunks[0] or {})
    call_id = item.get("id") or fallback_id or "__default__"
    tool_name = item.get("name")
    args_piece = item.get("args")

    parsed_args: Optional[dict] = None
    is_complete = False
    preview_str: Optional[str] = None

    if args_piece:
        parsed_args, is_complete = buffers.append(call_id, str(args_piece))
        if is_complete and parsed_args is not None:
            preview_str = json.dumps(parsed_args, ensure_ascii=False)

    return tool_name, preview_str, parsed_args, is_complete, call_id


def extract_tool_event(val: Any, buffers: ToolArgsBuffer) -> Optional[Dict[str, Any]]:
    """
    Normalize tool-call signals from LangGraph/OpenAI message chunks.
    Returns a dict with keys: name, args_preview, complete
    or None if no tool signal is present.
    """
    name_ak, args_ak, id_ak = _from_additional_kwargs(val)
    name_tc, args_tc, id_tc = _from_tool_calls(val)

    name = name_ak or name_tc
    args_preview = args_ak or args_tc
    call_id = id_ak or id_tc

    # Handle streaming chunks for arguments
    ch_name, ch_args_preview, ch_args_full, ch_complete, ch_id = _from_tool_call_chunks(val, buffers, call_id)
    if ch_name:
        name = name or ch_name
    if ch_args_preview:
        args_preview = ch_args_preview
    if ch_id:
        call_id = ch_id

    if not name and not args_preview:
        return None

    complete = False
    if args_preview is not None:
        try:
            json.loads(args_preview)
            complete = True
        except Exception:
            # could be partial string; rely on chunk completion path
            complete = ch_complete

    return {
        "name": name,
        "args_preview": args_preview,
        "complete": bool(complete),
        "call_id": call_id,
    }


