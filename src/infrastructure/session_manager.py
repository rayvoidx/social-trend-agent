"""
Session Manager

CLI, Chatbot, API 모드에서 공통으로 사용하는 세션 관리
"""

import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """에이전트 세션"""

    session_id: str
    created_at: datetime
    last_accessed: datetime

    # 대화 히스토리 (챗봇 모드)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)

    # 컨텍스트 데이터 (모든 모드)
    context: Dict[str, Any] = field(default_factory=dict)

    # 세션 메타데이터
    mode: str = "cli"  # cli, chatbot, api
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str):
        """대화 메시지 추가 (챗봇 모드)"""
        self.conversation_history.append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )
        self.last_accessed = datetime.now()

    def get_conversation_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """대화 히스토리 조회"""
        if limit:
            return self.conversation_history[-limit:]
        return self.conversation_history

    def update_context(self, key: str, value: Any):
        """컨텍스트 업데이트"""
        self.context[key] = value
        self.last_accessed = datetime.now()

    def get_context(self, key: str, default: Any = None) -> Any:
        """컨텍스트 조회"""
        self.last_accessed = datetime.now()
        return self.context.get(key, default)

    def is_expired(self, ttl_minutes: int = 60) -> bool:
        """세션 만료 여부 확인"""
        expiry_time = self.last_accessed + timedelta(minutes=ttl_minutes)
        return datetime.now() > expiry_time


class SessionManager:
    """
    세션 관리자

    다양한 실행 모드에서 세션을 통합 관리:
    - CLI: 임시 세션 (일회성)
    - Chatbot: 영구 세션 (대화 맥락 유지)
    - API: 토큰 기반 세션
    """

    _instance = None

    def __new__(cls):
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """초기화"""
        if self._initialized:
            return

        self.sessions: Dict[str, Session] = {}
        self._initialized = True
        logger.info("SessionManager initialized")

    def create_session(
        self,
        session_id: Optional[str] = None,
        mode: str = "cli",
        user_id: Optional[str] = None,
        **metadata,
    ) -> Session:
        """
        새 세션 생성

        Args:
            session_id: 세션 ID (없으면 자동 생성)
            mode: 실행 모드 (cli, chatbot, api)
            user_id: 사용자 ID (선택사항)
            **metadata: 추가 메타데이터

        Returns:
            생성된 세션
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        session = Session(
            session_id=session_id,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            mode=mode,
            user_id=user_id,
            metadata=metadata,
        )

        self.sessions[session_id] = session
        logger.info(f"Created session: {session_id} (mode={mode})")

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        세션 조회

        Args:
            session_id: 세션 ID

        Returns:
            세션 객체 (없으면 None)
        """
        session = self.sessions.get(session_id)
        if session:
            session.last_accessed = datetime.now()
        return session

    def get_or_create_session(
        self, session_id: Optional[str] = None, mode: str = "cli", **kwargs
    ) -> Session:
        """
        세션 조회 또는 생성

        Args:
            session_id: 세션 ID
            mode: 실행 모드
            **kwargs: 추가 인자

        Returns:
            세션 객체
        """
        if session_id and session_id in self.sessions:
            return self.get_session(session_id)

        return self.create_session(session_id=session_id, mode=mode, **kwargs)

    def delete_session(self, session_id: str) -> bool:
        """
        세션 삭제

        Args:
            session_id: 세션 ID

        Returns:
            삭제 성공 여부
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    def cleanup_expired_sessions(self, ttl_minutes: int = 60):
        """
        만료된 세션 정리

        Args:
            ttl_minutes: 세션 TTL (분)
        """
        expired = []
        for session_id, session in self.sessions.items():
            if session.is_expired(ttl_minutes):
                expired.append(session_id)

        for session_id in expired:
            self.delete_session(session_id)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def get_active_sessions(self) -> List[Session]:
        """활성 세션 목록 조회"""
        return list(self.sessions.values())

    def get_session_count(self) -> int:
        """세션 수 조회"""
        return len(self.sessions)

    def get_sessions_by_mode(self, mode: str) -> List[Session]:
        """모드별 세션 조회"""
        return [s for s in self.sessions.values() if s.mode == mode]

    def get_sessions_by_user(self, user_id: str) -> List[Session]:
        """사용자별 세션 조회"""
        return [s for s in self.sessions.values() if s.user_id == user_id]


# 싱글톤 인스턴스 접근 함수
def get_session_manager() -> SessionManager:
    """SessionManager 싱글톤 인스턴스 반환"""
    return SessionManager()


# ============================================================================
# 모드별 헬퍼 함수
# ============================================================================


def create_cli_session(**kwargs) -> Session:
    """
    CLI 모드 세션 생성 (임시)

    Usage:
        session = create_cli_session()
        # 일회성 실행 후 자동 삭제
    """
    manager = get_session_manager()
    return manager.create_session(mode="cli", **kwargs)


def create_chatbot_session(user_id: str, **kwargs) -> Session:
    """
    챗봇 모드 세션 생성 (영구)

    Usage:
        session = create_chatbot_session(user_id="user123")
        session.add_message("user", "안녕하세요")
        session.add_message("assistant", "안녕하세요! 무엇을 도와드릴까요?")
    """
    manager = get_session_manager()
    return manager.create_session(mode="chatbot", user_id=user_id, **kwargs)


def create_api_session(api_key: str, **kwargs) -> Session:
    """
    API 모드 세션 생성 (토큰 기반)

    Usage:
        session = create_api_session(api_key="abc123")
    """
    manager = get_session_manager()
    return manager.create_session(
        mode="api", session_id=api_key, **kwargs  # API 키를 세션 ID로 사용
    )


# ============================================================================
# 컨텍스트 매니저 (with 문 지원)
# ============================================================================


class SessionContext:
    """
    세션 컨텍스트 매니저

    Usage:
        with SessionContext(mode="cli") as session:
            session.update_context("query", "AI")
            # 작업 수행
        # 자동으로 세션 정리 (CLI 모드)
    """

    def __init__(self, session_id: Optional[str] = None, mode: str = "cli", **kwargs):
        self.session_id = session_id
        self.mode = mode
        self.kwargs = kwargs
        self.session = None
        self.manager = get_session_manager()

    def __enter__(self) -> Session:
        """컨텍스트 진입"""
        self.session = self.manager.get_or_create_session(
            session_id=self.session_id, mode=self.mode, **self.kwargs
        )
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료"""
        # CLI 모드는 자동 삭제
        if self.mode == "cli" and self.session:
            self.manager.delete_session(self.session.session_id)
