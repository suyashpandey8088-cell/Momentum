"""Apply versioned PostgreSQL migrations once, in a transaction."""
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'backend'),str(Path(__file__).resolve().parents[1])]
from sqlalchemy import text
from core.database import engine
from core.config import get_settings
if engine.dialect.name != 'postgresql':
    raise SystemExit('Versioned migrations target PostgreSQL. SQLite development bootstraps automatically.')
with engine.begin() as connection:
    connection.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())'))
    for path in sorted((Path(__file__).parent/'migrations').glob('*.sql')):
        if connection.execute(text('SELECT 1 FROM schema_migrations WHERE version=:v'),{'v':path.name}).first():
            print(f'Already applied: {path.name}');continue
        connection.execute(text(path.read_text()))
        connection.execute(text('INSERT INTO schema_migrations(version) VALUES (:v)'),{'v':path.name})
        print(f'Applied: {path.name}')
