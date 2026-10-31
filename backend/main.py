import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from core.config import get_settings
from core.database import engine
from models.entities import Base
from api import auth, workspace, meetings, actions, integrations, insights
from workers.runner import worker_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('momentum')
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.is_production: Base.metadata.create_all(engine)
    worker = asyncio.create_task(worker_loop()) if settings.embedded_worker else None
    logger.info('MOMENTUM API ready · %s mode', settings.app_env)
    yield
    if worker:
        worker.cancel()
        try: await worker
        except asyncio.CancelledError: pass
    engine.dispose()

app = FastAPI(title='MOMENTUM API', description='From conversation to completion. Private, approval-first meeting execution.', version='1.0.0', lifespan=lifespan, docs_url='/api/docs' if not settings.is_production else None, redoc_url=None, openapi_url='/api/openapi.json' if not settings.is_production else None)

@app.middleware('http')
async def security_middleware(request: Request, call_next):
    if request.method in {'POST', 'PATCH', 'PUT', 'DELETE'}:
        if request.headers.get('x-momentum-client') != 'web' or request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'This mutation requires the MOMENTUM web client.'}, status_code=403)
        length = request.headers.get('content-length')
        if length and length.isdigit() and int(length) > (settings.max_upload_mb+2)*1024*1024:
            return JSONResponse({'detail': 'Request is too large.'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Request-ID'] = str(uuid4())
    if request.url.path.startswith('/api/') and not request.url.path.startswith('/api/docs'): response.headers['Cache-Control'] = 'no-store'
    return response

@app.exception_handler(Exception)
async def unhandled_exception(request: Request, error: Exception):
    request_id = str(uuid4())
    logger.error('Unhandled API error %s: %s', request_id, type(error).__name__)
    return JSONResponse({'detail': 'Something went wrong. Your data was not confirmed as changed. Please try again.', 'request_id': request_id}, status_code=500)

@app.get('/api/health')
def health():
    from sqlalchemy import text
    with engine.connect() as connection: connection.execute(text('SELECT 1'))
    return {'status': 'ok', 'service': 'momentum', 'environment': settings.app_env}

@app.get('/api/health/ready')
def readiness():
    from sqlalchemy import text
    with engine.connect() as connection: connection.execute(text('SELECT 1'))
    return {'status': 'ready', 'database': 'ok', 'embedded_worker': settings.embedded_worker}

for router in [auth.router, workspace.router, meetings.router, actions.router, integrations.router, insights.router]: app.include_router(router)
