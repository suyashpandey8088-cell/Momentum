from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from core.security import Admin, Workspace, DB, rate_limit
from core.config import get_settings
from models.entities import *
from schemas.contracts import IntegrationConfig
from services.common import serialize, audit
from integrations.catalog import CATALOG, oauth_credentials
from integrations.oauth import authorization_url, exchange_code

router = APIRouter(prefix='/api/integrations', tags=['integrations'])
EXCLUDE = {'token_encrypted', 'refresh_encrypted'}

@router.get('')
def list_integrations(workspace: Workspace, db: DB):
    _, org, membership = workspace
    connected = {item.provider: item for item in db.scalars(select(Integration).where(Integration.organization_id == org.id))}
    result = []
    for key, entry in CATALOG.items():
        item = connected.get(key)
        client_id, secret = oauth_credentials(key) if entry['implemented'] else ('', '')
        result.append({'provider': key, **entry, 'configured': bool(client_id and secret), 'status': item.status if item else 'disconnected', 'id': item.id if item else None, 'account_label': item.account_label if item else '', 'config': item.config if item and membership.role == 'admin' else {}, 'can_manage': membership.role == 'admin' and not org.is_demo})
    return result

@router.get('/{provider}/connect')
def connect(provider: str, request: Request, workspace: Admin, db: DB):
    user, org, _ = workspace
    if org.is_demo: raise HTTPException(403, 'Create your own workspace before connecting external accounts. Demo connections are never simulated.')
    if provider not in CATALOG or not CATALOG[provider]['implemented']: raise HTTPException(404, 'This integration is planned, not connected.')
    rate_limit(request, 'oauth-connect', 20, 3600)
    url = authorization_url(db, provider, org.id, user.id); db.commit()
    return RedirectResponse(url)

@router.get('/{provider}/callback')
def callback(provider: str, code: str, state: str, workspace: Admin, db: DB):
    user, org, _ = workspace
    if org.is_demo or provider not in CATALOG or not CATALOG[provider]['implemented']: raise HTTPException(400, 'Invalid integration callback.')
    try:
        exchange_code(db, provider, code, state, org.id, user.id)
        audit(db, org.id, user.id, 'Integration connected', 'integration', provider)
        db.commit()
    except Exception:
        db.rollback(); raise
    return RedirectResponse(get_settings().frontend_url.rstrip('/')+'/app/integrations?connected='+provider)

@router.patch('/{provider}/config')
def configure(provider: str, body: IntegrationConfig, workspace: Admin, db: DB):
    user, org, _ = workspace
    item = db.scalar(select(Integration).where(Integration.organization_id == org.id, Integration.provider == provider))
    if not item or item.status != 'connected': raise HTTPException(409, 'Connect the integration first.')
    allowed = {'linear': {'team_id'}, 'notion': {'database_id', 'title_property'}, 'slack': {'channel'}}.get(provider, set())
    if set(body.config) - allowed: raise HTTPException(422, 'Unsupported integration setting.')
    if any(not isinstance(value, str) or len(value) > 200 for value in body.config.values()): raise HTTPException(422, 'Settings must be short strings.')
    item.config = {**item.config, **body.config}; item.updated_at = now()
    audit(db, org.id, user.id, 'Integration configuration updated', 'integration', provider); db.commit()
    return serialize(item, EXCLUDE)

@router.delete('/{provider}')
def disconnect(provider: str, workspace: Admin, db: DB):
    user, org, _ = workspace
    item = db.scalar(select(Integration).where(Integration.organization_id == org.id, Integration.provider == provider))
    if item:
        item.token_encrypted = ''; item.refresh_encrypted = ''; item.status = 'disconnected'; item.account_label = ''; item.scopes = []; item.config = {}; item.updated_at = now()
    audit(db, org.id, user.id, 'Integration disconnected; stored tokens removed', 'integration', provider); db.commit()
    return {'ok': True, 'note': 'Local tokens removed. Revoke app access at the provider to invalidate previously issued tokens.'}
