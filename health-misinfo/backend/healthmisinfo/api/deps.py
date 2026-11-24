"""Authentication / authorization dependencies."""

from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from healthmisinfo.config import get_settings
from healthmisinfo.db.models import AppSetting, User
from healthmisinfo.db.session import get_db
from healthmisinfo.security import decode_access_token

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _token_from_request(request: Request) -> tuple[str | None, str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip(), "bearer"
    cookie = request.cookies.get(get_settings().cookie_name)
    return (cookie, "cookie") if cookie else (None, "none")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token, kind = _token_from_request(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    if kind == "cookie" and request.method not in SAFE_METHODS and not request.headers.get("x-requested-with"):
        # CSRF defence for cookie sessions: browsers cannot add custom headers cross-site without CORS.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing X-Requested-With header")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}) from None
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive or not found")
    return user


class Guest:
    """Anonymous visitor in public mode. Never persisted; owns no records."""

    id = None
    role = "guest"
    reviewer_code = "guest"
    is_guest = True


GUEST = Guest()


def is_guest(user) -> bool:
    return getattr(user, "is_guest", False)


def get_viewer(request: Request, db: Session = Depends(get_db)) -> User | Guest:
    """Signed-in user if a valid session is present; otherwise a Guest when public mode is on."""
    token, _ = _token_from_request(request)
    if token or not get_settings().public_mode:
        try:
            return get_current_user(request, db)
        except HTTPException as e:
            if not get_settings().public_mode or e.status_code == status.HTTP_403_FORBIDDEN:
                raise
    return GUEST


def require_roles(*roles: str) -> Callable[..., User]:
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return user

    return dep


require_admin = require_roles("admin")
require_reviewer = require_roles("admin", "reviewer")
require_researcher = require_roles("admin", "researcher")

DEFAULT_APP_SETTINGS = {
    "auto_queue_abstained": True,
    "auto_queue_needs_review": True,
}


def app_setting(db: Session, key: str):
    row = db.get(AppSetting, key)
    if row is not None:
        return row.value
    s = get_settings()
    if key == "reviews_required":
        return s.reviews_required
    if key == "store_analysis_text":
        return s.store_analysis_text
    return DEFAULT_APP_SETTINGS.get(key)
