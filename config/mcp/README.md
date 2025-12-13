# MCP 서버 설정 가이드

Model Context Protocol (MCP) 서버를 통해 Claude Desktop, Cursor 등에서 트렌드 분석 에이전트를 도구로 사용할 수 있습니다.

## 🎯 MCP란?

MCP (Model Context Protocol)는 AI 애플리케이션이 외부 도구와 데이터 소스에 연결할 수 있도록 하는 개방형 프로토콜입니다.

- **공식 문서**: [modelcontextprotocol.io](https://modelcontextprotocol.io/)
- **GitHub**: [github.com/modelcontextprotocol](https://github.com/modelcontextprotocol)

## 🚀 빠른 시작 (5분)

### 1단계: MCP 서버 실행

```bash
# MCP 서버 실행
python automation/mcp/mcp_server.py

# 또는 백그라운드 실행
python automation/mcp/mcp_server.py &
```

**출력 예시**:
```
🤖 MCP Server for Social Trend Agent
✅ Server started successfully
📡 Listening on: stdio
🔧 Available tools: 3
```

### 2단계: Claude Desktop 설정

#### macOS

```bash
# Claude Desktop 설정 파일 편집
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

#### Windows

```bash
# Claude Desktop 설정 파일 편집
notepad %APPDATA%\Claude\claude_desktop_config.json
```

### 3단계: 설정 파일 작성

`claude_desktop_config.json`에 다음 내용 추가:

```json
{
  "mcpServers": {
    "social-trend-agent": {
      "command": "python",
      "args": [
        "/absolute/path/to/social-trend-agent/automation/mcp/mcp_server.py"
      ],
      "env": {
        "OPENAI_API_KEY": "your-openai-api-key"
      }
    }
  }
}
```

**⚠️ 중요**:
- 절대 경로를 사용하세요
- API 키를 직접 입력하거나 `.env` 파일 경로 설정

### 4단계: Claude Desktop 재시작

Claude Desktop을 완전히 종료 후 재실행하세요.

### 5단계: 도구 확인

Claude Desktop에서 다음과 같이 물어보세요:

```
"어떤 도구들을 사용할 수 있나요?"
```

응답에 다음 도구들이 나타나야 합니다:
- `analyze_news_trend`
- `analyze_viral_video`
- `search_web`

## 🔧 제공되는 도구

### 1. analyze_news_trend

뉴스 트렌드를 분석합니다.

**파라미터**:
```json
{
  "query": "검색 키워드",
  "timeWindow": "7d",  // 24h, 7d, 30d
  "language": "ko",    // ko, en
  "maxResults": 20
}
```

**사용 예시** (Claude Desktop):
```
"AI에 대한 최근 7일간 뉴스 트렌드를 분석해줘"
```

### 2. analyze_viral_video

바이럴 비디오를 분석합니다.

**파라미터**:
```json
{
  "query": "검색 키워드",
  "market": "KR",      // KR, US, JP, GB, DE
  "platforms": ["youtube"],
  "timeWindow": "24h"
}
```

**사용 예시** (Claude Desktop):
```
"K-pop 관련 최근 급상승 YouTube 영상을 분석해줘"
```

### 3. search_web (선택)

Brave Search API를 사용한 웹 검색 (API 키 필요).

**파라미터**:
```json
{
  "query": "검색어",
  "count": 10
}
```

## 📝 고급 설정

### .env 파일 사용

API 키를 설정 파일에 직접 넣지 않고 `.env` 파일 사용:

```json
{
  "mcpServers": {
    "social-trend-agent": {
      "command": "python",
      "args": [
        "/path/to/social-trend-agent/automation/mcp/mcp_server.py"
      ],
      "cwd": "/path/to/social-trend-agent",
      "env": {
        "PYTHONPATH": "/path/to/social-trend-agent"
      }
    }
  }
}
```

`.env` 파일:
```bash
OPENAI_API_KEY=sk-your-key                  # OpenAI 사용 시
ANTHROPIC_API_KEY=sk-ant-your-key          # Anthropic 사용 시
NEWS_API_KEY=your-news-api-key
BRAVE_API_KEY=your-brave-api-key  # 선택
```

## 🔍 Cursor IDE 설정

Cursor에서도 동일한 방식으로 MCP 서버를 사용할 수 있습니다.

```json
// .cursor/mcp_config.json
{
  "mcpServers": {
    "social-trend-agent": {
      "command": "python",
      "args": ["/path/to/automation/mcp/mcp_server.py"]
    }
  }
}
```

## 🧪 테스트

### MCP 서버 직접 테스트

```bash
# MCP 서버 실행
python automation/mcp/mcp_server.py

# 다른 터미널에서
echo '{"method":"tools/list"}' | python automation/mcp/mcp_server.py
```

### 도구 실행 테스트

```python
# test_mcp.py
import subprocess
import json

request = {
    "method": "tools/call",
    "params": {
        "name": "analyze_news_trend",
        "arguments": {
            "query": "AI",
            "timeWindow": "7d"
        }
    }
}

result = subprocess.run(
    ["python", "automation/mcp/mcp_server.py"],
    input=json.dumps(request),
    capture_output=True,
    text=True
)

print(result.stdout)
```

## 🐛 트러블슈팅

### 1. "도구를 찾을 수 없습니다"

**원인**: MCP 서버가 제대로 시작되지 않음

**해결**:
```bash
# 수동 실행하여 에러 확인
python automation/mcp/mcp_server.py

# 로그 확인
tail -f logs/agent.log
```

### 2. "API 키 에러"

**원인**: 환경 변수가 제대로 전달되지 않음

**해결**:
- `claude_desktop_config.json`에 `env` 섹션 확인
- 절대 경로 사용 확인
- `.env` 파일 위치 확인

### 3. "Python 모듈을 찾을 수 없습니다"

**원인**: PYTHONPATH 설정 누락

**해결**:
```json
{
  "env": {
    "PYTHONPATH": "/absolute/path/to/social-trend-agent"
  }
}
```

### 4. Claude Desktop 재시작 안됨

**원인**: 백그라운드 프로세스 남아있음

**해결**:
```bash
# macOS
killall "Claude"

# Windows
taskkill /F /IM Claude.exe
```

## 📊 로그 확인

```bash
# MCP 서버 로그
tail -f logs/mcp_server.log

# 에이전트 로그
tail -f logs/agent.log
```

## 🔒 보안

### API 키 보호

1. **절대로** Git에 API 키 커밋하지 마세요
2. `.env` 파일 사용 권장
3. 설정 파일 권한 확인:
```bash
chmod 600 ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

### 환경 변수 암호화

```bash
# macOS Keychain 사용 (고급)
security add-generic-password -a "mcp" -s "openai-key" -w "sk-your-key"
```

## 📚 추가 자료

### MCP 공식 문서
- [MCP 스펙](https://spec.modelcontextprotocol.io/)
- [Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [예제](https://github.com/modelcontextprotocol/servers)

### 프로젝트 문서
- [메인 README](../../README.md)
- [FastAPI 가이드](../../agents/api/README.md)

## 🎯 사용 사례

### 1. 일일 트렌드 브리핑

Claude Desktop에서:
```
"오늘 AI 관련 뉴스 트렌드를 분석하고
주요 인사이트 3가지만 간단히 요약해줘"
```

### 2. 경쟁사 모니터링

```
"Tesla의 최근 30일 뉴스 감성 분석 결과를
경쟁사와 비교해서 보여줘"
```

### 3. 콘텐츠 아이디어

```
"K-pop 관련 최근 바이럴 영상들의
공통 패턴을 분석해서 콘텐츠 아이디어 제안해줘"
```

## 💡 팁

1. **쿼리 최적화**: 구체적인 키워드 사용
2. **기간 설정**: 최근 데이터가 더 정확
3. **결과 활용**: Claude가 결과를 해석하고 추가 인사이트 제공
4. **자동화**: n8n과 연동하여 정기 실행 가능

---

**⚠️ 주의**: MCP는 아직 베타 기능입니다. Claude Desktop 최신 버전 사용을 권장합니다.
