---
description: LangGraph 에이전트 그래프 및 데이터 파이프라인 최적화
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: [agent name or pipeline component]
---

# Data & AI Pipeline Agent

$ARGUMENTS에 대한 LangGraph 에이전트 또는 데이터 파이프라인을 분석하고 최적화합니다.

## Tasks

1. 관련 에이전트 그래프 구조 파악 (src/agents/)
2. 상태 스키마 및 노드 흐름 분석
3. MCP 도구 연동 확인
4. PartialResult 패턴 적용 확인
5. 최적화 또는 수정 구현

## Key Areas

- LangGraph StateGraph (nodes, edges, conditional)
- MCP 서버 통합 (Brave Search, Supadata)
- LLM 클라이언트 및 model_roles
- Pinecone RAG 파이프라인
- Self-refinement 엔진
