from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from healthmisinfo.api.deps import get_current_user
from healthmisinfo.api.schemas import LoginIn, LoginOut, UserOut
from healthmisinfo.audit import audit
from healthmisinfo.config import get_settings
from healthmisinfo.db.models import User
from healthmisinfo.db.session import get_db
from healthmisinfo.ratelimit import client_ip, enforce
from healthmisinfo.security import create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut, summary="Sign in (sets an HttpOnly session cookie)")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    enforce(request, "login", s.rate_limit_login, s.rate_limit_window_seconds)
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        audit(db, "auth.login_failed", "user", None, details={"email_domain": body.email.split("@")[-1][:64]}, ip=client_ip(request))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    user.last_login_at = datetime.now(UTC)
    token = create_access_token(user.id, user.role)
    audit(db, "auth.login", "user", user.id, actor_id=user.id, ip=client_ip(request))
    db.commit()
    response.set_cookie(
        s.cookie_name,
        token,
        max_age=s.access_token_minutes * 60,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path="/",
    )
    return LoginOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/logout", summary="Clear the session cookie")
def logout(response: Response):
    response.delete_cookie(get_settings().cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
