"""Optional private Supabase object storage; the service-role key never reaches the browser."""
import httpx
from core.config import get_settings


def configured() -> bool:
    s = get_settings()
    return bool(s.supabase_url and s.supabase_service_role_key)

def _request(method: str, path: str, **kwargs):
    s = get_settings()
    url = f'{s.supabase_url.rstrip("/")}/storage/v1/{path}'
    headers = {'Authorization': f'Bearer {s.supabase_service_role_key}', 'apikey': s.supabase_service_role_key}
    headers.update(kwargs.pop('headers', {}))
    with httpx.Client(timeout=60) as client:
        response = client.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response

def upload(key: str, path: str, content_type: str):
    if not configured(): return
    with open(path, 'rb') as file: _request('POST', f'object/{get_settings().supabase_storage_bucket}/{key}', content=file.read(), headers={'Content-Type': content_type, 'x-upsert': 'false'})

def remove(key: str):
    if not configured() or not key: return
    _request('DELETE', f'object/{get_settings().supabase_storage_bucket}', json={'prefixes': [key]})

def remote_signed_url(key: str) -> str | None:
    if not configured() or not key: return None
    data = _request('POST', f'object/sign/{get_settings().supabase_storage_bucket}/{key}', json={'expiresIn': 900}).json()
    return get_settings().supabase_url.rstrip('/') + '/storage/v1' + data['signedURL']

def download(key: str, destination: str):
    if not configured(): return
    response = _request('GET', f'object/{get_settings().supabase_storage_bucket}/{key}')
    with open(destination, 'wb') as file: file.write(response.content)
