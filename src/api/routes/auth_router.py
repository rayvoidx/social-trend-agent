"""
Authentication router for FastAPI.

인증 관련 API 엔드포인트를 위한 FastAPI 라우터입니다.
"""

from fastapi import APIRouter
from .auth import login, LoginRequest, TokenResponse

# Create auth router
router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(request: LoginRequest):
    """
    사용자 로그인 및 JWT 토큰 발급

    사용자명과 비밀번호를 검증하고 유효한 경우 JWT 토큰을 발급합니다.

    Args:
        request: 로그인 요청 데이터

    Returns:
        JWT 토큰과 사용자 정보

    Raises:
        HTTPException: 인증 실패 시
    """
    return await login(request)
