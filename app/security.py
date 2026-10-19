import secrets
from typing import Optional, List
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, APIKeyHeader
from app.config import settings
from app.schemas.common import UserRole

# Security schemes
security_basic = HTTPBasic(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class AuthenticatedUser:
    def __init__(self, username: str, role: UserRole):
        self.username = username
        self.role = role

    def __repr__(self):
        return f"<User(username={self.username}, role={self.role})>"

def get_current_user(
    credentials: Optional[HTTPBasicCredentials] = Security(security_basic),
    api_key: Optional[str] = Security(api_key_header),
) -> AuthenticatedUser:
    """
    Authenticates requests via either API Key (X-API-Key) or HTTP Basic Authentication.
    If AUTH_ENABLED is False, defaults to an internal admin user.
    """
    if not settings.AUTH_ENABLED:
        return AuthenticatedUser(username="dev_admin", role=UserRole.ADMIN)

    # 1. Check API Key Header
    if api_key:
        if secrets.compare_digest(api_key, settings.API_KEY_ADMIN):
            return AuthenticatedUser(username="admin_apikey_user", role=UserRole.ADMIN)
        elif secrets.compare_digest(api_key, settings.API_KEY_ENGINEER):
            return AuthenticatedUser(username="engineer_apikey_user", role=UserRole.ENGINEER)
        elif secrets.compare_digest(api_key, settings.API_KEY_VIEWER):
            return AuthenticatedUser(username="viewer_apikey_user", role=UserRole.VIEWER)

    # 2. Check HTTP Basic Auth Credentials
    if credentials:
        users = settings.get_basic_auth_dict()
        user_info = users.get(credentials.username)
        if user_info and secrets.compare_digest(credentials.password, user_info["password"]):
            role_str = user_info["role"]
            role = UserRole(role_str) if role_str in UserRole._value2member_map_ else UserRole.VIEWER
            return AuthenticatedUser(username=credentials.username, role=role)

    # Unauthenticated
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials. Use HTTP Basic Auth or X-API-Key header.",
        headers={"WWW-Authenticate": "Basic realm='Incident Platform'"},
    )

def require_role(allowed_roles: List[UserRole]):
    """
    Role-Based Access Control (RBAC) dependency factory.
    Verifies that the authenticated user possesses one of the allowed roles.
    """
    def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        # Admin has access to all roles
        if user.role == UserRole.ADMIN:
            return user
        if user.role in allowed_roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation not permitted. Required roles: {[r.value for r in allowed_roles]}. Current role: {user.role.value}"
        )
    return role_checker
