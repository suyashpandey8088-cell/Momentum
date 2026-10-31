import base64
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Annotated
from fastapi import Request, Response, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from .config import get_settings
from .database import get_db
from models.entities import User, Session as UserSession, Membership, Organization, now

COOKIE = 'momentum_session'
_rate_buckets: dict[str, deque] = defaultdict(deque)

def hash_token(value: str) -> str: return hashlib.sha256(value.encode()).hexdigest()
def new_token() -> str: return secrets.token_urlsafe(32)

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600_000)
    return f'pbkdf2_sha256$600000${salt.hex()}${digest.hex()}'

def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        hash_password(password)
        return False
    try:
        algorithm, rounds, salt, expected = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or int(rounds) != 600_000: return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError): return False

def rate_limit(request: Request, scope: str, limit: int = 15, seconds: int = 60):
    key = f'{scope}:{request.client.host if request.client else "unknown"}'
    bucket = _rate_buckets[key]
    current = time.monotonic()
    while bucket and bucket[0] < current - seconds: bucket.popleft()
    if len(bucket) >= limit: raise HTTPException(429, 'Too many requests. Please wait a minute and try again.')
    bucket.append(current)
    if len(_rate_buckets) > 10000:
        for k in list(_rate_buckets):
            if not _rate_buckets[k] or _rate_buckets[k][-1] < current - 3600: del _rate_buckets[k]

def create_session(db: Session, response: Response, user: User, org_id: str | None = None) -> str:
    token = new_token()
    if org_id is None:
        membership = db.scalar(select(Membership).where(Membership.user_id == user.id).limit(1))
        org_id = membership.organization_id if membership else None
    db.add(UserSession(id=hash_token(token), user_id=user.id, organization_id=org_id, expires_at=now() + timedelta(days=get_settings().session_days)))
    db.flush()
    response.set_cookie(COOKIE, token, httponly=True, secure=get_settings().cookie_secure, samesite='lax', max_age=get_settings().session_days * 86400, path='/')
    return token

def clear_session(db: Session, request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        session = db.get(UserSession, hash_token(token))
        if session: db.delete(session)
    response.delete_cookie(COOKIE, path='/', httponly=True, secure=get_settings().cookie_secure, samesite='lax')

def get_auth(request: Request, db: Annotated[Session, Depends(get_db)]) -> tuple[User, UserSession]:
    token = request.cookies.get(COOKIE)
    if not token: raise HTTPException(401, 'Sign in to access your workspace.')
    session = db.get(UserSession, hash_token(token))
    if not session or session.expires_at.replace(tzinfo=None) < now().replace(tzinfo=None): raise HTTPException(401, 'Your session has expired. Please sign in again.')
    user = db.get(User, session.user_id)
    if not user: raise HTTPException(401, 'Account not found.')
    return user, session

Auth = Annotated[tuple[User, UserSession], Depends(get_auth)]
DB = Annotated[Session, Depends(get_db)]

def get_workspace(auth: Auth, db: DB) -> tuple[User, Organization, Membership]:
    user, session = auth
    if not session.organization_id: raise HTTPException(428, 'Complete onboarding to create your workspace.')
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == session.organization_id))
    org = db.get(Organization, session.organization_id)
    if not membership or not org: raise HTTPException(403, 'You do not have access to this workspace.')
    return user, org, membership

Workspace = Annotated[tuple[User, Organization, Membership], Depends(get_workspace)]

def require_writer(workspace: Workspace):
    user, org, membership = workspace
    if membership.role == 'viewer': raise HTTPException(403, 'This workspace is read-only for your role.')
    return user, org, membership

Writer = Annotated[tuple[User, Organization, Membership], Depends(require_writer)]

def require_admin(workspace: Workspace):
    user, org, membership = workspace
    if membership.role != 'admin': raise HTTPException(403, 'A workspace administrator is required.')
    return user, org, membership

Admin = Annotated[tuple[User, Organization, Membership], Depends(require_admin)]

def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        if get_settings().is_production: raise RuntimeError('Token encryption is not configured.')
        key = base64.urlsafe_b64encode(hashlib.sha256(b'momentum-development-only').digest()).decode()
    return Fernet(key.encode())

def encrypt_token(value: str) -> str: return _fernet().encrypt(value.encode()).decode() if value else ''
def decrypt_token(value: str) -> str: return _fernet().decrypt(value.encode()).decode() if value else ''
