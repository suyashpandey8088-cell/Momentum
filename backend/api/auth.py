from datetime import timedelta
from uuid import uuid4
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, delete
from core.config import get_settings
from core.security import *
from models.entities import *
from schemas.contracts import *
from services.common import serialize, audit, utc
from services.email import send_email
from database.seeds.demo import seed_workspace

router = APIRouter(prefix='/api/auth', tags=['authentication'])

def user_data(db: Session, user: User, session: UserSession | None = None):
    org = db.get(Organization, session.organization_id) if session and session.organization_id else None
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == org.id)) if org else None
    return {**serialize(user, {'password_hash'}), 'organization': serialize(org) if org else None, 'role': membership.role if membership else None}

def account_token(db: Session, user: User, kind: str):
    token = new_token()
    db.add(VerificationToken(id=hash_token(token), user_id=user.id, kind=kind, expires_at=now()+timedelta(hours=1 if kind == 'reset' else 24)))
    path = 'reset-password' if kind == 'reset' else 'verify-email'
    link = f'{get_settings().frontend_url.rstrip("/")}/{path}?token={token}'
    subject = 'Reset your MOMENTUM password' if kind == 'reset' else 'Verify your email for MOMENTUM'
    body = f'Hi {user.name},\n\nUse this single-use link within {"one hour" if kind == "reset" else "24 hours"}:\n{link}\n\nIf you did not request this, ignore this email.\n\nMOMENTUM — From conversation to completion.'
    email_id = send_email(db, user.email, subject, body)
    return email_id, link

@router.post('/signup')
def signup(body: Signup, request: Request, response: Response, db: DB):
    rate_limit(request, 'signup', 8, 3600)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(409, 'An account with this email already exists. Sign in or reset your password.')
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    db.add(user); db.flush()
    email_id, link = account_token(db, user, 'verify')
    create_session(db, response, user)
    db.commit()
    return {'user': user_data(db, user), 'next': '/onboarding', 'email_delivery': 'smtp' if get_settings().smtp_host else 'local_outbox', 'development_link': link if not get_settings().is_production and not get_settings().smtp_host else None}

@router.post('/login')
def login(body: Login, request: Request, response: Response, db: DB):
    rate_limit(request, 'login', 12, 300)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not verify_password(body.password, user.password_hash if user else None) or not user or user.is_demo: raise HTTPException(401, 'The email or password is incorrect.')
    token = create_session(db, response, user)
    session = db.get(UserSession, hash_token(token))
    db.commit()
    return {'user': user_data(db, user, session), 'next': '/app' if user.onboarded else '/onboarding'}

@router.post('/logout')
def logout(request: Request, response: Response, db: DB):
    clear_session(db, request, response); db.commit()
    return {'ok': True}

@router.get('/me')
def me(auth: Auth, db: DB):
    user, session = auth
    return {'user': user_data(db, user, session)}

@router.post('/demo')
def demo(request: Request, response: Response, db: DB):
    if not get_settings().enable_demo: raise HTTPException(404, 'The demo is disabled on this deployment.')
    rate_limit(request, 'demo', 10, 3600)
    existing = request.cookies.get(COOKIE)
    session = db.get(UserSession, hash_token(existing)) if existing else None
    if session:
        existing_user = db.get(User, session.user_id)
        if existing_user and existing_user.is_demo and utc(session.expires_at) > now(): return {'next': '/app', 'user': user_data(db, existing_user, session)}
    identifier = uuid4().hex[:12]
    user = User(email=f'demo-{identifier}@demo.local', name='Alex Morgan', is_demo=True, email_verified=True, onboarded=True)
    db.add(user); db.flush()
    org = Organization(name='Orbit Studio', is_demo=True, created_by=user.id)
    db.add(org); db.flush()
    db.add(Membership(organization_id=org.id, user_id=user.id, role='admin')); db.flush()
    seed_workspace(db, org, user)
    create_session(db, response, user, org.id)
    audit(db, org.id, user.id, 'Private demo workspace created')
    db.commit()
    return {'next': '/app', 'demo': True}

@router.post('/onboarding')
def onboard(body: Onboarding, auth: Auth, response: Response, db: DB):
    user, session = auth
    if user.is_demo: raise HTTPException(403, 'Create an account to set up your own workspace.')
    if user.onboarded: raise HTTPException(409, 'Onboarding has already been completed.')
    org = Organization(name=body.organization if body.account_type == 'team' else f'{body.name.split()[0]}’s workspace', created_by=user.id)
    db.add(org); db.flush()
    db.add(Membership(organization_id=org.id, user_id=user.id, role='admin'))
    user.name = body.name; user.onboarded = True
    session.organization_id = org.id
    if body.sample_data: seed_workspace(db, org, user)
    audit(db, org.id, user.id, 'Workspace created', 'organization', org.id, {'account_type': body.account_type, 'role': body.role, 'team_size': body.team_size, 'use_case': body.use_case, 'preferred_integrations': body.integrations})
    db.commit()
    return {'user': user_data(db, user, session), 'next': '/app'}

@router.post('/forgot-password')
def forgot_password(body: EmailRequest, request: Request, db: DB):
    rate_limit(request, 'forgot', 5, 3600)
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.is_demo == False))
    link = None
    if user:
        _, url = account_token(db, user, 'reset')
        if not get_settings().is_production and not get_settings().smtp_host: link = url
    db.commit()
    return {'message': 'If an account exists, a reset link has been prepared. Check your inbox.', 'delivery': 'smtp' if get_settings().smtp_host else 'local_outbox', 'development_link': link}

@router.post('/reset-password')
def reset_password(body: ResetPassword, request: Request, response: Response, db: DB):
    rate_limit(request, 'reset', 10, 3600)
    token = db.get(VerificationToken, hash_token(body.token))
    if not token or token.used or token.kind != 'reset' or utc(token.expires_at) < now(): raise HTTPException(400, 'This reset link is invalid or expired. Request a new one.')
    user = db.get(User, token.user_id)
    user.password_hash = hash_password(body.password)
    token.used = True
    for session in db.scalars(select(Session).where(Session.user_id == user.id)): db.delete(session)
    db.commit()
    return {'message': 'Password updated. Sign in with your new password.'}

@router.post('/verify-email')
def verify_email(body: TokenRequest, db: DB):
    token = db.get(VerificationToken, hash_token(body.token))
    if not token or token.used or token.kind != 'verify' or utc(token.expires_at) < now(): raise HTTPException(400, 'This verification link is invalid or expired.')
    user = db.get(User, token.user_id)
    user.email_verified = True; token.used = True; db.commit()
    return {'message': 'Your email is verified.'}

@router.post('/resend-verification')
def resend_verification(auth: Auth, request: Request, db: DB):
    rate_limit(request, 'verify-resend', 3, 3600)
    user, _ = auth
    if user.email_verified: return {'message': 'Your email is already verified.'}
    _, link = account_token(db, user, 'verify'); db.commit()
    return {'message': 'Verification email prepared.', 'delivery': 'smtp' if get_settings().smtp_host else 'local_outbox', 'development_link': link if not get_settings().is_production and not get_settings().smtp_host else None}

@router.get('/outbox')
def development_outbox(email: str, db: DB):
    if get_settings().is_production or get_settings().smtp_host: raise HTTPException(404, 'Not available.')
    item = db.scalar(select(EmailOutbox).where(EmailOutbox.recipient == email.lower()).order_by(EmailOutbox.created_at.desc()).limit(1))
    if not item: raise HTTPException(404, 'No local email yet.')
    return serialize(item)

@router.patch('/preferences')
def preferences(body: Preferences, auth: Auth, db: DB):
    user, _ = auth
    if body.theme is not None: user.theme = body.theme
    if body.motion is not None: user.motion = body.motion
    if body.notification_preferences is not None: user.notification_preferences = {**user.notification_preferences, **body.notification_preferences}
    db.commit()
    return serialize(user, {'password_hash'})

@router.get('/google')
def google_login(request: Request, db: DB):
    import base64, hashlib
    from urllib.parse import urlencode
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret: raise HTTPException(409, 'Google sign-in is not configured on this server. Use email and password.')
    rate_limit(request, 'google-auth', 20, 3600)
    state = new_token(); verifier = new_token()
    db.add(OAuthState(id=hash_token(state), provider='google_login', code_verifier=verifier, expires_at=now()+timedelta(minutes=10))); db.commit()
    params = {'client_id': settings.google_client_id, 'redirect_uri': settings.api_public_url.rstrip('/')+'/api/auth/google/callback', 'response_type': 'code', 'scope': 'openid email profile', 'state': state, 'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(), 'code_challenge_method': 'S256', 'prompt': 'select_account'}
    response = RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params))
    response.set_cookie('momentum_oauth_state', state, httponly=True, secure=settings.cookie_secure, samesite='lax', max_age=600, path='/')
    return response

@router.get('/google/callback')
def google_callback(code: str, state: str, request: Request, db: DB):
    import httpx
    settings = get_settings()
    saved = db.get(OAuthState, hash_token(state))
    cookie_state = request.cookies.get('momentum_oauth_state', '')
    if not saved or saved.provider != 'google_login' or not hmac.compare_digest(cookie_state, state) or utc(saved.expires_at) < now(): raise HTTPException(400, 'Google sign-in expired. Please try again.')
    db.delete(saved); db.commit()
    try:
        with httpx.Client(timeout=25) as client:
            token_response = client.post('https://oauth2.googleapis.com/token', data={'client_id': settings.google_client_id, 'client_secret': settings.google_client_secret, 'code': code, 'grant_type': 'authorization_code', 'redirect_uri': settings.api_public_url.rstrip('/')+'/api/auth/google/callback', 'code_verifier': saved.code_verifier})
            token_response.raise_for_status()
            info_response = client.get('https://openidconnect.googleapis.com/v1/userinfo', headers={'Authorization': 'Bearer '+token_response.json()['access_token']})
            info_response.raise_for_status(); info = info_response.json()
    except (httpx.HTTPError, ValueError): raise HTTPException(502, 'Google sign-in could not be verified. Please try again.')
    if not info.get('email_verified') or not info.get('email'): raise HTTPException(403, 'Google did not return a verified email address.')
    email = info['email'].lower()
    user = db.scalar(select(User).where(User.email == email))
    if user and not user.email_verified: raise HTTPException(409, 'Verify your existing email account before using Google sign-in.')
    if not user:
        user = User(email=email, name=str(info.get('name') or email.split('@')[0])[:120], email_verified=True); db.add(user); db.flush()
    response = RedirectResponse(settings.frontend_url.rstrip('/')+('/app' if user.onboarded else '/onboarding'))
    create_session(db, response, user); db.commit()
    response.delete_cookie('momentum_oauth_state', path='/')
    return response
