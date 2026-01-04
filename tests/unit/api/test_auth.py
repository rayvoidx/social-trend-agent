"""
Tests for authentication API.
"""

import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone, timedelta
import jwt

from src.api.routes.auth import (
    LoginRequest,
    TokenResponse,
    create_access_token,
    verify_token,
    authenticate_user,
    login,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from fastapi import HTTPException


class TestAuthModels:
    """Test Pydantic models."""
    
    def test_login_request_valid(self):
        """Test valid login request."""
        request = LoginRequest(username="testuser", password="password123")
        assert request.username == "testuser"
        assert request.password == "password123"
    
    def test_login_request_validation_error(self):
        """Test login request validation errors."""
        with pytest.raises(ValueError):
            LoginRequest(username="", password="password123")
        
        with pytest.raises(ValueError):
            LoginRequest(username="testuser", password="")
    
    def test_token_response_valid(self):
        """Test valid token response."""
        user_data = {"id": "user123", "username": "testuser"}
        response = TokenResponse(
            access_token="token123",
            token_type="bearer",
            expires_in=1800,
            user=user_data
        )
        assert response.access_token == "token123"
        assert response.token_type == "bearer"
        assert response.expires_in == 1800
        assert response.user == user_data


class TestJWTUtilities:
    """Test JWT token utilities."""
    
    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "testuser", "user_id": "123"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        
        # Decode and verify token
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
        assert decoded["user_id"] == "123"
        assert "exp" in decoded
        assert "iat" in decoded
    
    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=60)
        token = create_access_token(data, expires_delta)
        
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = datetime.fromtimestamp(decoded["exp"], timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Should expire in approximately 60 minutes
        delta = exp_time - now
        assert 3500 < delta.total_seconds() < 3700  # Allow some tolerance
    
    def test_verify_token_valid(self):
        """Test valid token verification."""
        data = {"sub": "testuser", "user_id": "123"}
        token = create_access_token(data)
        
        payload = verify_token(token)
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == "123"
    
    def test_verify_token_invalid(self):
        """Test invalid token verification."""
        with pytest.raises(HTTPException) as exc_info:
            verify_token("invalid_token")
        
        assert exc_info.value.status_code == 401
        assert "유효하지 않은 토큰입니다" in exc_info.value.detail
    
    def test_verify_token_expired(self):
        """Test expired token verification."""
        # Create token that expires immediately
        data = {"sub": "testuser"}
        expired_delta = timedelta(seconds=-1)
        token = create_access_token(data, expired_delta)
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)
        
        assert exc_info.value.status_code == 401
        assert "토큰이 만료되었습니다" in exc_info.value.detail


class TestAuthentication:
    """Test authentication logic."""
    
    @pytest.mark.asyncio
    async def test_authenticate_user_valid(self):
        """Test valid user authentication."""
        user = await authenticate_user("testuser", "testpassword123")
        
        assert user is not None
        assert user["username"] == "testuser"
        assert user["id"] == "user123"
        assert user["email"] == "test@example.com"
        assert user["role"] == "user"
        assert "password" not in user  # Password should not be returned
    
    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_username(self):
        """Test authentication with invalid username."""
        user = await authenticate_user("nonexistent", "password123")
        assert user is None
    
    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_password(self):
        """Test authentication with invalid password."""
        user = await authenticate_user("testuser", "wrongpassword")
        assert user is None
    
    @pytest.mark.asyncio
    async def test_authenticate_admin_user(self):
        """Test admin user authentication."""
        user = await authenticate_user("admin", "admin123")
        
        assert user is not None
        assert user["username"] == "admin"
        assert user["role"] == "admin"


class TestLoginEndpoint:
    """Test login endpoint."""
    
    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login."""
        request = LoginRequest(username="testuser", password="testpassword123")
        response = await login(request)
        
        assert isinstance(response, TokenResponse)
        assert response.token_type == "bearer"
        assert response.expires_in == ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert response.user["username"] == "testuser"
        assert response.user["id"] == "user123"
        
        # Verify token is valid
        payload = verify_token(response.access_token)
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == "user123"
        assert payload["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        request = LoginRequest(username="testuser", password="wrongpassword")
        
        with pytest.raises(HTTPException) as exc_info:
            await login(request)
        
        assert exc_info.value.status_code == 401
        assert "사용자명 또는 비밀번호가 올바르지 않습니다" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_login_admin_success(self):
        """Test admin login success."""
        request = LoginRequest(username="admin", password="admin123")
        response = await login(request)
        
        assert response.user["role"] == "admin"
        
        # Verify token contains admin role
        payload = verify_token(response.access_token)
        assert payload["role"] == "admin"
    
    @pytest.mark.asyncio
    async def test_login_server_error(self):
        """Test login with server error."""
        request = LoginRequest(username="testuser", password="testpassword123")
        
        # Mock create_access_token to raise exception
        with patch("src.api.routes.auth.create_access_token") as mock_create:
            mock_create.side_effect = Exception("Token creation failed")
            
            with pytest.raises(HTTPException) as exc_info:
                await login(request)
            
            assert exc_info.value.status_code == 500
            assert "로그인 처리 중 오류가 발생했습니다" in exc_info.value.detail