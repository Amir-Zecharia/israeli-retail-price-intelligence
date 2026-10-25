"""Small psycopg connection and transactional migration helpers."""
import argparse
import hashlib
import os
from pathlib import Path
import psycopg

MIGRATIONS = Path(__file__).parent / 'migrations'

def connect(dsn=None, **kwargs):
    """Return a UTC connection. Callers own transaction and connection lifetime."""
    target = dsn or os.environ.get('DATABASE_URL')
    if not target:
        raise ValueError('DATABASE_URL is required')
    return psycopg.connect(target, options='-c timezone=UTC', **kwargs)


def migrate(dsn=None):
    """Apply checked, ordered migrations once under a transaction-scoped lock."""
    with connect(dsn) as conn:
        conn.execute('SELECT pg_advisory_xact_lock(718291001)')
        conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())')
        for path in sorted(MIGRATIONS.glob('*.sql')):
            payload = path.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            old = conn.execute('SELECT sha256 FROM schema_migrations WHERE name=%s',(path.name,)).fetchone()
            if old:
                if old[0] != digest:
                    raise ValueError(f'Applied migration checksum mismatch: {path.name}')
                continue
            conn.execute(payload.decode('utf8'))
            conn.execute('INSERT INTO schema_migrations(name,sha256) VALUES (%s,%s)',(path.name,digest))

if __name__ == '__main__':
    argparse.ArgumentParser(description='Apply IRPI PostgreSQL migrations using DATABASE_URL').parse_args()
    migrate()
    print('Migrations applied')
