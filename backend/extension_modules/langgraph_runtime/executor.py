from __future__ import annotations

from typing import Any, Callable, List, Optional

from .parsing import ToolArgsBuffer, extract_tool_event
from .message_utils import to_langchain_messages


class LangGraphExecutor:
    def __init__(
        self,
        *,
        make_llm: Callable[[], Any],
        create_agent: Callable[[Any, List[Any]], Any],
        load_tools: Optional[Callable[[], List[Any]]] = None,
    ) -> None:
        self._make_llm = make_llm
        self._create_agent = create_agent
        self._load_tools = load_tools

    async def run_stream(
        self,
        *,
        messages: List[Any],
        on_content: Callable[[str], None],
        on_tool_event: Optional[Callable[[dict], None]] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Any]] = None,
    ) -> None:
        model = self._make_llm()

        if tools is None and self._load_tools is not None:
            tools = self._load_tools()
        tools = tools or []

        # Normalize messages into LangChain message objects
        lc_messages = messages
        if messages and isinstance(messages[0], dict):
            lc_messages = to_langchain_messages(messages, system_prompt=system_prompt)

        agent = self._create_agent(model, tools)

        buffers = ToolArgsBuffer()
        test = []
        async for event in agent.astream_log({"messages": lc_messages}):
            if hasattr(event, "ops") and event.ops:
                for op in event.ops:
                    test.append(op)
                    if op.get("op") == "add" and "value" in op:
                        val = op["value"]
                        # # 1) 우선 상태/툴 이벤트를 추출해 전송한다 (텍스트 스트림에 섞이지 않도록)
                        # tool_evt = extract_tool_event(val, buffers)
                        # if tool_evt and on_tool_event:
                        #     on_tool_event(tool_evt)
                        #     # 상태 이벤트인 경우 텍스트 스트림으로는 내보내지 않음
                        #     continue

                        # 2) 일반 텍스트 출력만 청크로 스트림
                        if getattr(val, "content", None):
                            text = str(val.content)
                            step = 200
                            for i in range(0, len(text), step):
                                on_content(text[i : i + step])
        for t in test:
            has_content = hasattr(t, "usage_metadata")
            if has_content:
                print(t.usage_metadata)


    async def run_once(
        self,
        *,
        messages: List[Any],
        system_prompt: Optional[str] = None,
    ) -> str:
        model = self._make_llm()
        tools: List[Any] = []
        if self._load_tools is not None:
            tools = self._load_tools()

        lc_messages = messages
        if messages and isinstance(messages[0], dict):
            lc_messages = to_langchain_messages(messages, system_prompt=system_prompt)

        agent = self._create_agent(model, tools)
        res = await agent.ainvoke({"messages": lc_messages})
        text = str(res)
        return text


