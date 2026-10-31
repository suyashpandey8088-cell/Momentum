import base64
import hashlib
from datetime import timedelta
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from models.entities import Integration, OAuthState, now
from core.security import new_token, hash_token, encrypt_token, decrypt_token
from core.config import get_settings
from .catalog import CATALOG, oauth_credentials, redirect_uri


def authorization_url(db: Session, provider: str, org_id: str, user_id: str):
    client_id, secret = oauth_credentials(provider)
    if not client_id or not secret: raise HTTPException(409, f'{CATALOG[provider]["name"]} needs OAuth credentials on the server. No connection has been simulated.')
    state = new_token(); verifier = new_token()
    db.add(OAuthState(id=hash_token(state), organization_id=org_id, user_id=user_id, provider=provider, code_verifier=verifier, expires_at=now()+timedelta(minutes=10)))
    family = CATALOG[provider]['oauth']
    params = {'client_id': client_id, 'redirect_uri': redirect_uri(provider), 'response_type': 'code', 'state': state}
    if family == 'google':
        url = 'https://accounts.google.com/o/oauth2/v2/auth'
        params.update({'scope': ' '.join(CATALOG[provider]['scopes']), 'access_type': 'offline', 'prompt': 'consent', 'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(), 'code_challenge_method': 'S256'})
    elif family == 'linear':
        url = 'https://linear.app/oauth/authorize'; params['scope'] = ','.join(CATALOG[provider]['scopes'])
    elif family == 'slack':
        url = 'https://slack.com/oauth/v2/authorize'; params['user_scope'] = ','.join(CATALOG[provider]['scopes'])
    else:
        url = 'https://api.notion.com/v1/oauth/authorize'; params['owner'] = 'user'
    return url + '?' + urlencode(params)

def exchange_code(db: Session, provider: str, code: str, state: str, org_id: str, user_id: str) -> Integration:
    saved = db.get(OAuthState, hash_token(state))
    if not saved or saved.provider != provider or saved.organization_id != org_id or saved.user_id != user_id or saved.expires_at.replace(tzinfo=None) < now().replace(tzinfo=None): raise HTTPException(400, 'The connection request is invalid or expired. Start again from Integrations.')
    db.delete(saved); db.flush()
    client_id, secret = oauth_credentials(provider)
    family = CATALOG[provider]['oauth']
    data = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri(provider), 'client_id': client_id}
    headers = {'Accept': 'application/json'}
    if family == 'google':
        url = 'https://oauth2.googleapis.com/token'; data['client_secret'] = secret; data['code_verifier'] = saved.code_verifier
    elif family == 'linear':
        url = 'https://api.linear.app/oauth/token'; data['client_secret'] = secret
    elif family == 'slack':
        url = 'https://slack.com/api/oauth.v2.access'; data['client_secret'] = secret
    else:
        url = 'https://api.notion.com/v1/oauth/token'
        headers['Authorization'] = 'Basic ' + base64.b64encode(f'{client_id}:{secret}'.encode()).decode()
    try:
        with httpx.Client(timeout=30) as client: response = client.post(url, data=data, headers=headers)
        response.raise_for_status(); payload = response.json()
    except (httpx.HTTPError, ValueError): raise HTTPException(502, 'The provider did not complete authorization. Please try connecting again.')
    if family == 'slack': payload = payload.get('authed_user', {})
    access = payload.get('access_token')
    if not access or payload.get('error'): raise HTTPException(400, 'Authorization was not granted.')
    integration = db.scalar(select(Integration).where(Integration.organization_id == org_id, Integration.provider == provider))
    if not integration:
        integration = Integration(organization_id=org_id, provider=provider); db.add(integration)
    integration.token_encrypted = encrypt_token(access)
    integration.refresh_encrypted = encrypt_token(payload.get('refresh_token', ''))
    integration.expires_at = now()+timedelta(seconds=payload['expires_in']) if payload.get('expires_in') else None
    integration.scopes = (payload.get('scope', '').replace(',', ' ').split())
    integration.status = 'connected'; integration.account_label = CATALOG[provider]['name'] + ' account'
    integration.updated_at = now()
    # Fetch an account label only when the granted scopes permit it.
    try:
        with httpx.Client(timeout=15) as client:
            if family == 'slack':
                info = client.post('https://slack.com/api/auth.test', headers={'Authorization': f'Bearer {access}'}).json()
                if info.get('ok'): integration.account_label = info.get('team', 'Slack workspace')
            elif family == 'linear':
                info = client.post('https://api.linear.app/graphql', headers={'Authorization': f'Bearer {access}'}, json={'query': '{ organization { name } }'}).json()
                integration.account_label = info.get('data', {}).get('organization', {}).get('name', 'Linear workspace')
            elif family == 'notion':
                info = client.get('https://api.notion.com/v1/users/me', headers={'Authorization': f'Bearer {access}', 'Notion-Version': '2022-06-28'}).json()
                integration.account_label = info.get('name') or 'Notion workspace'
    except httpx.HTTPError: pass
    db.flush()
    return integration

def access_token(db: Session, integration: Integration) -> str:
    expiry = integration.expires_at
    if expiry and expiry.replace(tzinfo=None) > now().replace(tzinfo=None)+timedelta(minutes=2): return decrypt_token(integration.token_encrypted)
    refresh = decrypt_token(integration.refresh_encrypted)
    family = CATALOG[integration.provider]['oauth']
    if not refresh or family not in {'google', 'linear', 'slack'}:
        if expiry: integration.status = 'error'; db.commit()
        raise HTTPException(409, 'This connection has expired. Reconnect the integration.')
    client_id, secret = oauth_credentials(integration.provider)
    data = {'grant_type': 'refresh_token', 'refresh_token': refresh, 'client_id': client_id, 'client_secret': secret}
    url = {'google': 'https://oauth2.googleapis.com/token', 'linear': 'https://api.linear.app/oauth/token', 'slack': 'https://slack.com/api/oauth.v2.access'}[family]
    try:
        with httpx.Client(timeout=20) as client: response = client.post(url, data=data)
        response.raise_for_status(); payload = response.json()
        if family == 'slack': payload = payload.get('authed_user', {})
        if not payload.get('access_token'): raise ValueError('No access token')
    except (httpx.HTTPError, ValueError):
        integration.status = 'error'; db.commit()
        raise HTTPException(409, 'The provider could not refresh this connection. Reconnect it in Integrations.')
    integration.token_encrypted = encrypt_token(payload['access_token'])
    if payload.get('refresh_token'): integration.refresh_encrypted = encrypt_token(payload['refresh_token'])
    integration.expires_at = now()+timedelta(seconds=payload['expires_in']) if payload.get('expires_in') else None
    integration.status = 'connected'; db.commit()
    return payload['access_token']
