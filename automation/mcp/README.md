# MCP (Model Context Protocol) 연동 가이드

> Claude Desktop 및 다른 LLM 클라이언트가 트렌드 분석 에이전트를 도구로 사용할 수 있도록 MCP 서버 설정

---

## 📌 MCP란?

**Model Context Protocol (MCP)**는 LLM이 외부 도구, 데이터 소스, 서비스와 상호작용할 수 있게 해주는 오픈 프로토콜입니다.

### 주요 기능
- 🔧 **도구 제공**: LLM이 파일 읽기, 검색, API 호출 등을 수행
- 📊 **데이터 접근**: 로컬 파일, 데이터베이스, 외부 API에 접근
- 🔄 **실시간 연동**: 최신 정보를 LLM에 실시간 제공

---

## 🎯 이 프로젝트의 MCP 활용

### 사용 사례

1. **Claude Desktop에서 트렌드 분석 요청**
   ```
   User: "최근 7일간 전기차 관련 뉴스 트렌드를 분석해줘"
   Claude: [MCP로 news_trend_agent 실행]
   Claude: "분석 결과: 긍정 67%, 주요 키워드: 전기차, 배터리, 충전..."
   ```

2. **파일 시스템 접근**
   ```
   User: "어제 생성된 트렌드 리포트를 보여줘"
   Claude: [MCP로 artifacts/ 디렉토리 읽기]
   Claude: "2024-10-18 리포트 내용..."
   ```

3. **실시간 웹 검색**
   ```
   User: "지금 유튜브에서 급상승 중인 비디오는?"
   Claude: [MCP로 viral_video_agent 실행]
   Claude: "Top 3 급상승 비디오: ..."
   ```

---

## 🚀 설치 및 설정

### 1. Claude Desktop 설치

https://claude.ai/download 에서 다운로드

### 2. MCP 서버 설정 파일 생성

**macOS/Linux:**
```bash
mkdir -p ~/Library/Application\ Support/Claude/
touch ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```powershell
mkdir "$env:APPDATA\Claude\"
New-Item "$env:APPDATA\Claude\claude_desktop_config.json"
```

### 3. 설정 파일 편집

`claude_desktop_config.json` 에 다음 내용 추가:

```json
{
  "mcpServers": {
    "trend-analysis": {
      "command": "python",
      "args": [
        "/absolute/path/to/Automatic-Consumer-Trend-Analysis-Agent/automation/mcp/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/absolute/path/to/Automatic-Consumer-Trend-Analysis-Agent"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/absolute/path/to/Automatic-Consumer-Trend-Analysis-Agent/artifacts"
      ]
    }
  }
}
```

**⚠️ 주의**: `/absolute/path/to/...`를 실제 프로젝트 경로로 변경하세요!

---

## 🔧 MCP 서버 구현

### mcp_server.py 생성

`automation/mcp/mcp_server.py`:

```python
#!/usr/bin/env python3
"""
MCP Server for Trend Analysis Agents

Provides tools for Claude Desktop to run trend analysis agents.
"""
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.news_trend_agent.graph import run_agent as run_news_agent
from agents.viral_video_agent.graph import run_agent as run_viral_agent


def run_news_trend_analysis(query: str, time_window: str = "7d", language: str = "ko") -> dict:
    """Run news trend analysis"""
    try:
        state = run_news_agent(
            query=query,
            time_window=time_window,
            language=language,
            max_results=20
        )

        return {
            "success": True,
            "report": state.report_md,
            "metrics": state.metrics,
            "summary": state.analysis.get("summary", ""),
            "sentiment": state.analysis.get("sentiment", {}),
            "keywords": state.analysis.get("keywords", {}).get("top_keywords", [])[:5]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def run_viral_video_analysis(query: str, market: str = "KR", platforms: list = None, time_window: str = "7d") -> dict:
    """Run viral video analysis"""
    if platforms is None:
        platforms = ["youtube"]

    try:
        state = run_viral_agent(
            query=query,
            market=market,
            platforms=platforms,
            time_window=time_window
        )

        return {
            "success": True,
            "report": state.report_md,
            "metrics": state.metrics,
            "spikes_detected": state.analysis.get("viral", {}).get("total_spikes", 0),
            "avg_growth_rate": state.analysis.get("viral", {}).get("avg_growth_rate", 0),
            "top_videos": state.normalized[:3] if state.normalized else []
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# MCP Tool Definitions
TOOLS = [
    {
        "name": "analyze_news_trend",
        "description": "Analyze news trends for a given query. Returns sentiment analysis, keywords, and insights.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query or topic to analyze"
                },
                "time_window": {
                    "type": "string",
                    "description": "Time window (e.g., '24h', '7d', '30d')",
                    "default": "7d"
                },
                "language": {
                    "type": "string",
                    "description": "Language code ('ko' or 'en')",
                    "default": "ko"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_viral_videos",
        "description": "Analyze viral videos and detect spike patterns. Returns top trending videos and success factors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query or topic"
                },
                "market": {
                    "type": "string",
                    "description": "Market code (KR, US, JP, etc.)",
                    "default": "KR"
                },
                "platforms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Platforms to analyze (youtube, tiktok, instagram)",
                    "default": ["youtube"]
                },
                "time_window": {
                    "type": "string",
                    "description": "Time window (e.g., '24h', '7d')",
                    "default": "7d"
                }
            },
            "required": ["query"]
        }
    }
]


def handle_call_tool(tool_name: str, arguments: dict) -> dict:
    """Handle tool calls from MCP"""
    if tool_name == "analyze_news_trend":
        return run_news_trend_analysis(**arguments)
    elif tool_name == "analyze_viral_videos":
        return run_viral_video_analysis(**arguments)
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def main():
    """MCP Server main loop"""
    print("MCP Trend Analysis Server started", file=sys.stderr)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line)
            method = request.get("method")

            if method == "tools/list":
                response = {
                    "tools": TOOLS
                }
            elif method == "tools/call":
                tool_name = request["params"]["name"]
                arguments = request["params"].get("arguments", {})
                response = handle_call_tool(tool_name, arguments)
            else:
                response = {"error": f"Unknown method: {method}"}

            # Send response
            print(json.dumps(response), flush=True)

        except Exception as e:
            error_response = {"error": str(e)}
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
```

### 실행 권한 부여

```bash
chmod +x automation/mcp/mcp_server.py
```

---

## 🧪 테스트

### 1. MCP 서버 수동 실행

```bash
python automation/mcp/mcp_server.py
```

표준 입력으로 JSON 전송:
```json
{"method": "tools/list"}
```

예상 출력:
```json
{"tools": [{"name": "analyze_news_trend", ...}]}
```

### 2. Claude Desktop에서 테스트

1. Claude Desktop 재시작
2. 새 대화 시작
3. 다음과 같이 요청:

```
최근 7일간 "전기차" 관련 뉴스 트렌드를 분석해줘
```

Claude가 `analyze_news_trend` 도구를 사용하여 분석을 수행합니다.

---

## 📊 사용 예시

### 예시 1: 뉴스 트렌드 분석

**User:**
```
"비건 식품" 트렌드를 분석해줘. 최근 30일 데이터로.
```

**Claude (MCP 호출):**
```python
analyze_news_trend(
    query="비건 식품",
    time_window="30d",
    language="ko"
)
```

**결과:**
```
비건 식품에 대한 최근 30일 트렌드 분석 결과:

감성: 긍정 72%, 중립 23%, 부정 5%
주요 키워드: 비건, 채식, 건강, 환경, 대체육

주요 인사이트:
- 건강과 환경에 대한 관심 증가로 긍정적 반응
- "대체육" 관련 뉴스가 급증
- 주요 브랜드: 풀무원, 동원F&B, 농심

출처: [링크1], [링크2], [링크3]
```

### 예시 2: 바이럴 비디오 분석

**User:**
```
유튜브와 틱톡에서 "K-pop" 관련 급상승 비디오를 찾아줘
```

**Claude (MCP 호출):**
```python
analyze_viral_videos(
    query="K-pop",
    market="KR",
    platforms=["youtube", "tiktok"],
    time_window="24h"
)
```

**결과:**
```
K-pop 관련 급상승 비디오 (최근 24시간):

급상승 감지: 5개
평균 증가율: 340%

Top 3:
1. [YouTube] 신인 걸그룹 데뷔 무대 - 조회수 3.2M (+340%)
2. [TikTok] 챌린지 커버댄스 - 조회수 2.1M (+285%)
3. [YouTube] 해외 프로듀서 리액션 - 조회수 1.9M (+250%)

성공 요인:
- 중독성 있는 후렴구
- 챌린지 트렌드 편승
- 글로벌 팬덤 형성
```

### 예시 3: 과거 리포트 조회

**User:**
```
어제 생성된 트렌드 리포트를 보여줘
```

**Claude (filesystem MCP 사용):**
```
artifacts/news_trend_agent/ 디렉토리에서 파일 검색...

최신 리포트: 2024-10-18_143000.md

[리포트 내용 표시]
```

---

## ⚙️ 고급 설정

### 환경 변수 전달

`claude_desktop_config.json`에서:
```json
{
  "mcpServers": {
    "trend-analysis": {
      "command": "python",
      "args": ["..."],
      "env": {
        "PYTHONPATH": "...",
        "NEWS_API_KEY": "your_key",
        "YOUTUBE_API_KEY": "your_key"
      }
    }
  }
}
```

### 복수 MCP 서버

```json
{
  "mcpServers": {
    "trend-analysis": {...},
    "filesystem": {...},
    "web-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "your_key"
      }
    }
  }
}
```

---

## 🐛 문제 해결

### 문제 1: MCP 서버가 시작되지 않음

**확인:**
- Python 경로가 올바른지 (`which python`)
- 프로젝트 경로가 절대 경로인지
- `mcp_server.py` 실행 권한 확인

**해결:**
```bash
# Python 경로 확인
which python3

# 설정 파일에 python3 사용
"command": "/usr/bin/python3"
```

### 문제 2: Claude가 도구를 찾지 못함

**확인:**
- Claude Desktop 재시작
- 설정 파일 JSON 문법 오류 (`jq . claude_desktop_config.json`)
- MCP 서버 로그 확인

**로그 확인:**
```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp*.log

# Windows
Get-Content "$env:APPDATA\Claude\Logs\mcp*.log" -Wait
```

### 문제 3: 도구 실행 실패

**확인:**
- 에이전트 코드에 버그가 없는지
- API 키가 설정되어 있는지 (또는 샘플 데이터 모드)
- Python 의존성 설치 확인

**해결:**
```bash
# 수동으로 에이전트 실행 테스트
python scripts/run_agent.py --agent news_trend_agent --query "test"

# 의존성 재설치
pip install -r backend/requirements.txt
```

---

## 📚 참고 자료

- [MCP 공식 문서](https://modelcontextprotocol.io/)
- [Claude Desktop MCP 가이드](https://claude.ai/docs/mcp)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Server 예제](https://github.com/modelcontextprotocol/servers)

---

## 🎯 다음 단계

1. **더 많은 도구 추가**
   - 경쟁사 비교 도구
   - 트렌드 예측 도구
   - 리포트 자동 요약 도구

2. **다른 LLM 클라이언트 연동**
   - VS Code Copilot
   - Continue.dev
   - Cursor

3. **실시간 스트리밍**
   - 분석 진행 상황 실시간 표시
   - 에이전트 실행 로그 스트리밍

---

**버전**: 1.0.0
**최종 업데이트**: 2024-10-19
**유지보수자**: Integration Team
