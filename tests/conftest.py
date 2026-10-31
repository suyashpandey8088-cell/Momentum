import os
import sys
import tempfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT)]
TMP=tempfile.TemporaryDirectory(prefix='momentum-tests-')
os.environ.update(DATABASE_URL=f'sqlite:///{TMP.name}/test.db',STORAGE_DIR=f'{TMP.name}/uploads',APP_ENV='test',EMBEDDED_WORKER='false',ENABLE_DEMO='true',COOKIE_SECURE='false',OPENAI_API_KEY='',SPEECH_API_KEY='',EMBEDDING_API_KEY='',SUPABASE_URL='',SUPABASE_SERVICE_ROLE_KEY='',TOKEN_ENCRYPTION_KEY='',SMTP_HOST='')
from fastapi.testclient import TestClient
from core.database import engine
from models.entities import Base
from main import app
from core.security import _rate_buckets

@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);_rate_buckets.clear()
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def client():
    with TestClient(app) as client:
        client.headers['X-Momentum-Client']='web'
        yield client

@pytest.fixture
def demo(client):
    response=client.post('/api/auth/demo');assert response.status_code==200
    return client

@pytest.fixture
def account(client):
    response=client.post('/api/auth/signup',json={'name':'Test Owner','email':'owner@example.com','password':'a-secure-test-password'})
    assert response.status_code==200
    response=client.post('/api/auth/onboarding',json={'name':'Test Owner','account_type':'team','organization':'Test Studio','role':'Product lead','team_size':'2–10','use_case':'Product development','integrations':[],'sample_data':False})
    assert response.status_code==200
    return client
