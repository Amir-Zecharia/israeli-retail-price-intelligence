"""Run IRPI with a project-owned PostgreSQL cluster and a read-only dashboard.

Usage: .venv/bin/python scripts/local.py setup|start|ingest|test|backup|status|stop
Requires PostgreSQL 17 binaries and the project's requirements installed.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.local'
PGDATA = STATE / 'postgres'
SOCKET = STATE / 'socket'
SNAPSHOT = ROOT / 'data' / 'local_snapshot.sql'
PORT = 55432


def pg_bin():
    explicit = os.environ.get('PG_BIN')
    candidates = [Path(explicit)] if explicit else []
    found = shutil.which('initdb')
    if found:
        candidates.append(Path(found).parent)
    candidates += [Path('/opt/homebrew/opt/postgresql@17/bin'), Path('/usr/local/opt/postgresql@17/bin'), Path('/usr/lib/postgresql/17/bin')]
    for candidate in candidates:
        if (candidate / 'pg_ctl').is_file():
            return candidate
    raise SystemExit('PostgreSQL binaries not found. Install PostgreSQL 17 or set PG_BIN.')


def dsn(database='irpi_local', reader=False):
    user = 'irpi_dashboard@' if reader else ''
    return f'postgresql://{user}/{database}?host={quote(str(SOCKET),safe="")}&port={PORT}'


def command(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, cwd=ROOT, **kwargs)


def setup():
    import psycopg
    sys.path.insert(0, str(ROOT))
    from database.connection import migrate
    binaries = pg_bin()
    STATE.mkdir(mode=0o700, exist_ok=True)
    STATE.chmod(0o700)
    SOCKET.mkdir(mode=0o700, exist_ok=True)
    SOCKET.chmod(0o700)
    if not (PGDATA / 'PG_VERSION').exists():
        command([binaries / 'initdb', '-D', PGDATA, '--auth-local=trust', '--auth-host=reject', '--no-locale', '--encoding=UTF8'])
    running = subprocess.run([str(binaries / 'pg_ctl'), '-D', str(PGDATA), 'status'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not running:
        command([binaries / 'pg_ctl', '-D', PGDATA, '-l', STATE / 'postgres.log', '-o', f"-k '{SOCKET}' -p {PORT} -h ''", 'start'])
    with psycopg.connect(dsn('postgres'), autocommit=True) as conn:
        for role in ('irpi_reader', 'irpi_ingestor'):
            if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
                conn.execute(f'CREATE ROLE {role} NOLOGIN')
        for database in ('irpi_local', 'irpi_test'):
            if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,)).fetchone():
                command([binaries / 'createdb', '-h', SOCKET, '-p', PORT, database])
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='irpi_dashboard'").fetchone():
            conn.execute('CREATE ROLE irpi_dashboard LOGIN IN ROLE irpi_reader')
    with psycopg.connect(dsn()) as conn:
        fresh = conn.execute("SELECT to_regclass('public.schema_migrations') IS NULL").fetchone()[0]
    if fresh and SNAPSHOT.exists():
        command([binaries / 'psql', '-h', SOCKET, '-p', PORT, '-d', 'irpi_local', '-v', 'ON_ERROR_STOP=1', '--single-transaction', '-f', SNAPSHOT], stdout=subprocess.DEVNULL)
    migrate(dsn())
    return binaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('setup', 'start', 'ingest', 'test', 'backup', 'status', 'stop'))
    parser.add_argument('--port', type=int, default=8501, help='Local Streamlit port')
    args = parser.parse_args()
    if args.action == 'stop':
        command([pg_bin() / 'pg_ctl', '-D', PGDATA, 'stop', '-m', 'fast'])
        return
    binaries = setup()
    env = dict(os.environ, DATABASE_URL=dsn(), TEST_DATABASE_URL=dsn('irpi_test'), READ_DATABASE_URL=dsn(reader=True), DASHBOARD_TEST_DATABASE_URL=dsn(reader=True))
    if args.action == 'start':
        # Both supported connection variables are read-only in the dashboard process.
        env['DATABASE_URL'] = env['READ_DATABASE_URL']
        command([sys.executable, '-m', 'streamlit', 'run', ROOT / 'app' / 'main.py', '--server.address=127.0.0.1', f'--server.port={args.port}', '--server.headless=true'], env=env)
    elif args.action == 'ingest':
        command([sys.executable, '-m', 'pipeline.ingest'], env=env)
    elif args.action == 'test':
        command([sys.executable, '-m', 'pytest', '-q'], env=env)
    elif args.action == 'backup':
        SNAPSHOT.parent.mkdir(exist_ok=True)
        temporary = SNAPSHOT.with_suffix('.sql.tmp')
        command([binaries / 'pg_dump', '--dbname', dsn(), '--no-owner', '--file', temporary])
        temporary.chmod(0o600)
        temporary.replace(SNAPSHOT)
        print('Saved a local database snapshot; the data directory is excluded from Git.')
    elif args.action == 'status':
        import psycopg
        with psycopg.connect(dsn(reader=True)) as conn:
            rows, days = conn.execute('SELECT count(*),count(DISTINCT observation_date) FROM published_prices').fetchone()
        print(json.dumps({'published_observations': rows, 'observed_dates': days, 'read_only_dashboard': True}))
    else:
        print('Local PostgreSQL ready. Run start to open the dashboard, or ingest to collect genuine prices.')


if __name__ == '__main__':
    main()
