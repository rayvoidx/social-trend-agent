from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


def to_langchain_messages(
    messages: List[Dict[str, Any]],
    *,
    system_prompt: Optional[str] = None,
) -> List[Any]:
    out: List[Any] = []
    if system_prompt:
        out.append(SystemMessage(content=system_prompt))

    for m in messages or []:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, (list, dict)):
            try:
                content = json.dumps(content, ensure_ascii=False)
            except Exception:
                content = str(content)

        if not content:
            continue

        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))

    return out


