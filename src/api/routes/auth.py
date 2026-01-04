"""
Authentication API routes.

인증 및 JWT 토큰 발급을 위한 FastAPI 기반 API입니다.

엔드포인트:
- POST /api/auth/login - 사용자 로그인 및 JWT 토큰 발급
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
import jwt
from jwt import PyJWTError


logger = logging.getLogger(__name__)

# JWT 설정 (실제 프로덕션에서는 환경변수로 관리)
SECRET_KEY = "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ============================================================================
# 요청/응답 모델 (Pydantic v2)
# ============================================================================


class LoginRequest(BaseModel):
    """로그인 요청 모델"""

    username: str = Field(..., description="사용자명", min_length=1, max_length=50)
    password: str = Field(..., description="비밀번호", min_length=1, max_length=100)

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "testuser",
                "password": "testpassword123"
            }
        }
    }


class TokenResponse(BaseModel):
    """토큰 응답 모델"""

    access_token: str = Field(..., description="JWT 액세스 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")
    expires_in: int = Field(..., description="토큰 만료 시간 (초)")
    user: Dict[str, Any] = Field(..., description="사용자 정보")

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "user": {
                    "username": "testuser",
                    "id": "user123"
                }
            }
        }
    }


class ErrorResponse(BaseModel):
    """에러 응답 모델"""

    error: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="에러 상세 정보")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "invalid_credentials",
                "message": "사용자명 또는 비밀번호가 올바르지 않습니다.",
                "detail": "Authentication failed"
            }
        }
    }


# ============================================================================
# JWT 토큰 생성 및 검증 유틸리티
# ============================================================================


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT 액세스 토큰 생성
    
    Args:
        data: 토큰에 포함할 데이터
        expires_delta: 토큰 만료 시간 (기본값: 30분)
        
    Returns:
        JWT 토큰 문자열
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    
    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create JWT token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="토큰 생성에 실패했습니다."
        )


def verify_token(token: str) -> Dict[str, Any]:
    """
    JWT 토큰 검증
    
    Args:
        token: JWT 토큰 문자열
        
    Returns:
        토큰 페이로드
        
    Raises:
        HTTPException: 토큰이 유효하지 않은 경우
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다."
        )
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다."
        )


# ============================================================================
# 인증 로직
# ============================================================================


async def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    사용자 인증
    
    실제 환경에서는 데이터베이스에서 사용자 정보를 조회하고 
    비밀번호 해시를 검증해야 합니다.
    
    Args:
        username: 사용자명
        password: 비밀번호
        
    Returns:
        인증 성공 시 사용자 정보, 실패 시 None
    """
    # 임시 사용자 데이터 (실제 환경에서는 데이터베이스 조회)
    # 보안상 실제 비밀번호 해시 비교가 필요함
    test_users = {
        "testuser": {
            "id": "user123",
            "username": "testuser",
            "password": "testpassword123",  # 실제로는 해시된 비밀번호
            "email": "test@example.com",
            "role": "user"
        },
        "admin": {
            "id": "admin001",
            "username": "admin",
            "password": "admin123",  # 실제로는 해시된 비밀번호
            "email": "admin@example.com",
            "role": "admin"
        }
    }
    
    user = test_users.get(username)
    if user and user["password"] == password:
        # 반환할 때 비밀번호는 제외
        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"]
        }
    
    return None


# ============================================================================
# API 엔드포인트
# ============================================================================


async def login(request: LoginRequest) -> TokenResponse:
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
    try:
        # 입력 데이터 검증 로깅
        logger.info(f"Login attempt for username: {request.username}")
        
        # 사용자 인증
        user = await authenticate_user(request.username, request.password)
        
        if not user:
            logger.warning(f"Authentication failed for username: {request.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="사용자명 또는 비밀번호가 올바르지 않습니다."
            )
        
        # JWT 토큰 생성
        token_data = {
            "sub": user["username"],  # subject (사용자 식별자)
            "user_id": user["id"],
            "role": user["role"]
        }
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data=token_data,
            expires_delta=access_token_expires
        )
        
        logger.info(f"Login successful for username: {request.username}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 초 단위
            user=user
        )
        
    except HTTPException:
        # HTTPException은 그대로 재발생
        raise
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그인 처리 중 오류가 발생했습니다."
        )