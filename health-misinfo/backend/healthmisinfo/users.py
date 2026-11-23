from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from healthmisinfo.db.models import ROLES, User
from healthmisinfo.security import hash_password, validate_password_strength

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+$")


class UserError(ValueError):
    pass


def create_user(db: Session, email: str, display_name: str, password: str, role: str) -> User:
    email = email.strip().lower()
    if not _EMAIL.match(email):
        raise UserError("Invalid email address")
    if role not in ROLES:
        raise UserError(f"role must be one of {ROLES}")
    try:
        validate_password_strength(password)
    except ValueError as e:
        raise UserError(str(e)) from e
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise UserError("A user with this email already exists")
    next_n = (db.scalar(select(func.max(User.id))) or 0) + 1
    u = User(
        email=email,
        display_name=display_name.strip(),
        reviewer_code=f"R-{next_n:04d}",
        password_hash=hash_password(password),
        role=role,
    )
    db.add(u)
    db.flush()
    return u
