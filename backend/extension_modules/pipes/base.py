from abc import ABC, abstractmethod
from typing import Union, Dict, Any, Generator, Iterator, List, Protocol, Awaitable, Optional, Callable
import asyncio
from langchain_openai import AzureChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from mcp import StdioServerParameters
import os
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent   
import time
import uuid
from open_webui.models.files import Files
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
import json
from extension_modules.tools.sscnt_quality import LawLibraryOutput, SpecLibraryOutput, InstLibraryOutputWithImage
from open_webui.retrieval.web.main import SearchResult, get_filtered_results
from open_webui.config import TAVILY_API_KEY,WEB_SEARCH_RESULT_COUNT,WEB_SEARCH_DOMAIN_FILTER_LIST
from langchain_core.tools import StructuredTool
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from open_webui.constants import TASKS
from open_webui.models.models import ModelsTable
from open_webui.main import generate_chat_completions
from open_webui.models.users import Users
from extension_modules.tools.base import CSToolBase, ToolList


# Cloud-neutral configuration
load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "azure_openai")
OPENAI_API_TYPE = os.getenv("OPENAI_API_TYPE", "azure")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "2024-02-15-preview")
OPENAI_DEPLOYMENT_NAME = os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-4")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4")

SLEEP_TIME = float(os.getenv("SLEEP_TIME", "0.05"))
DEFAULT_CUSTOM_MODEL_ID = os.getenv("DEFAULT_CUSTOM_MODEL_ID")

class WebSearchToolInput(BaseModel):
    query: str = Field(..., description="사용자의 질의나 추가적인 정보를 얻기 위한 웹검색용 쿼리를 제공하세요. 검색에 용이할 수 있는 문장으로 제공하세요.")


class ReactAgentBasePipe(ABC):
    def __init__(self,model: BaseChatModel | AzureChatOpenAI,tool: CSToolBase, valves: BaseModel,agent_start_message: str="에이전트를 시작 합니다", agent_end_message: str="모든 작업이 종료 되었습니다", agent_error_message: str="오류가 발생 했습니다 : "):
        self.model = model
        self.tool = tool
        self.valves = valves
        self.agent_start_message = agent_start_message
        self.agent_end_message = agent_end_message
        self.agent_error_message = agent_error_message

    @abstractmethod
    def pipe(self, body: dict, __event_emitter__=None) -> Union[str, Dict[str, Any], Generator, Iterator]:
        pass


    class SendCitationType(Protocol):
        def __call__(self, url: str, title: str, content: str) -> Awaitable[None]: ...


    class SendStatusType(Protocol):
        def __call__(self, status_message: str, done: bool) -> Awaitable[None]: ...
    
    EmitterType = Optional[Callable[[dict], Awaitable[None]]]

    @staticmethod
    def _get_send_citation(emitter: EmitterType):
        async def send_citation(url: str, title: str, content: str):
            if not emitter:
                return
            payload = {
                "type": "citation",
                "data": {
                    "document": [content],
                    "metadata": [{"source": url, "html": False}],
                    "source": {"name": title},
                },
            }
            if asyncio.iscoroutinefunction(emitter):
                await emitter(payload)
            else:
                emitter(payload)
        return send_citation

    @staticmethod
    def _get_send_status(emitter: EmitterType):
        async def send_status(msg: str, done: bool):
            if not emitter:
                return
            payload = {"type": "status", "data": {"description": msg, "done": done}}
            if asyncio.iscoroutinefunction(emitter):
                await emitter(payload)
            else:
                emitter(payload)
        return send_status

    @staticmethod
    def _get_model(model_type: str="azure", temperature: float=0.1):
        if model_type == "azure":
            model = AzureChatOpenAI(
                azure_endpoint=OPENAI_API_BASE,
                azure_deployment=OPENAI_DEPLOYMENT_NAME,
                api_version=OPENAI_API_VERSION,
                api_key=OPENAI_API_KEY,
                model_kwargs={"stream_options": {"include_usage": True}},
            )
            if temperature:
                if OPENAI_DEPLOYMENT_NAME[-5:] != "gpt-5":
                    model.model_kwargs["temperature"] = temperature
            return model
        else:
            raise ValueError(f"Invalid model type: {model_type}")

    def _get_mcp_session_params(mcp_command: str="npx", mcp_args: List[str]=["-y", "@azure/mcp@latest", "server", "start"]):
        return StdioServerParameters(
            command=mcp_command,
            args=mcp_args,
            env=os.environ.copy(),
        )

    def get_web_search_tool(self):
        web_search_tool = StructuredTool.from_function(
            # 비동기 함수 사용. 동기 함수 사용 시 coroutine이 아닌 func을 사용해야 함
            coroutine=self.search_tavily,
            name="web_search",
            description=f"""
                        웹 검색 결과를 반환 합니다
                        스키마 정보는 아래와 같습니다.
                        {PydanticOutputParser(pydantic_object=SearchResult).get_format_instructions()}
                    """,
            args_schema=WebSearchToolInput,
        )

        return ToolList(tools=web_search_tool, tool_start_message="웹 검색을 진행 중입니다...")

    async def search_tavily(
        self,        
        query: str,
    ) -> list[SearchResult]:
        """Async Tavily search with timeout, retries, and filtering."""
        import aiohttp

        api_key = getattr(self.valves, "TAVILY_API_KEY", None) or TAVILY_API_KEY.value
        count = getattr(self.valves, "WEB_SEARCH_RESULT_COUNT", None) or WEB_SEARCH_RESULT_COUNT.value
        filter_list = getattr(self.valves, "WEB_SEARCH_DOMAIN_FILTER_LIST", None) or WEB_SEARCH_DOMAIN_FILTER_LIST.value

        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        data = {"query": query, "max_results": count}

        timeout = aiohttp.ClientTimeout(total=10)

        async def _once(session):
            async with session.post(url, headers=headers, json=data) as resp:
                resp.raise_for_status()
                return await resp.json()

        # simple retry with backoff
        last_err = None
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            for attempt in range(3):
                try:
                    json_response = await _once(session)
                    results = json_response.get("results", [])
                    if filter_list:
                        results = get_filtered_results(results, filter_list)
                    return [
                        SearchResult(
                            link=result.get("url") or result.get("link", ""),
                            title=result.get("title", ""),
                            snippet=result.get("content") or result.get("snippet"),
                        )
                        for result in results
                        if (result.get("url") or result.get("link"))
                    ]
                except Exception as e:
                    last_err = e
                    await asyncio.sleep(min(1.5 * (attempt + 1), 5))

        # If all retries failed, raise last error
        raise last_err if last_err else RuntimeError("Tavily search failed")
        

    async def _pipe(self, body: Dict[str, Any], __user__: dict, __event_emitter__=None, __metadata__=None, __task__=None,__request__=None):
        if __task__ is not None and __task__ != TASKS.DEFAULT:
            user = Users.get_user_by_id(__user__["id"])
            response = await generate_chat_completions(
                __request__,
                {"model": DEFAULT_CUSTOM_MODEL_ID, "messages": body.get("messages"), "stream": False},
                user=user,
            )
            yield f"sample_pipe: {response['choices'][0]['message']['content']}"
            return

        messages = body.get("messages")
        if not messages:
            text = body.get("input") or body.get("text")
            messages = text

        features = []
        if __metadata__.get("features", {}).get("web_search"):
            features.append("web_search")

        tools = self.tool.get_tool()
        if "web_search" in features:
            tools.append(self.get_web_search_tool())

        url_buffer = ""
        send_citation = self._get_send_citation(__event_emitter__)
        send_status = self._get_send_status(__event_emitter__)  

        await send_status(self.agent_start_message, False)

        try:
            agent = create_react_agent(self.model, [t.tools for t in tools], prompt=self.valves.SYSTEM_PROMPT)
            
            in_url = False
            tools_list = []

            async for chunk in agent.astream_events({"messages": messages}, version="v2"):
                kind = chunk["event"]
                data = chunk["data"]
                if kind == "on_chat_model_stream":
                    if "chunk" in data:
                        ch = data["chunk"]
                        if hasattr(ch, 'content') and ch.content:
                            piece = ch.content
                            
                            # URL이 포함된 청크인지 확인
                            if "http" in piece or in_url:
                                url_buffer += piece
                                in_url = True
                                
                                # URL이 완성되었는지 확인 (공백, 개행, 마침표 등으로 끝나는 경우)
                                if any(char in piece for char in [' ', '\n', ')', ']', '>', '"', "'", "|"]):
                                    # 완성된 URL 출력
                                    print(f"Complete URL: {url_buffer.strip()}")
                                    yield url_buffer
                                    url_buffer = ""
                                    in_url = False
                            else:
                                # URL이 아닌 일반 텍스트는 바로 출력
                                yield piece
                            
                            await asyncio.sleep(SLEEP_TIME)

                elif kind == "on_tool_start":
                    for t in tools:
                        if t.tools.name == chunk['name']:
                            await send_status(t.tool_start_message, False)
                            break
                elif kind == "on_chat_model_end":
                    output = data.get("output")
                    # 스트림이 끝날 때 버퍼에 남은 URL이 있다면 출력
                    if url_buffer.strip():
                        print(f"Final URL: {url_buffer.strip()}")
                        yield url_buffer
                        url_buffer = ""
                        in_url = False
        except Exception as e:
            await send_status(f"{self.agent_error_message} {e}", True)
            raise e
        finally:
            if url_buffer.strip():
                print(f"Finally URL: {url_buffer.strip()}")
                yield url_buffer
            await send_status(self.agent_end_message, True)

