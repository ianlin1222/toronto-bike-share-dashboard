"""User-facing local launcher; only Python's standard library is required."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_COMPOSE = Path('/Applications/Docker.app/Contents/Resources/cli-plugins/docker-compose')


def run(command: list[str], *, capture: bool = False, check: bool = True,
        timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=capture, check=check,
                          timeout=timeout)


def require_build_space() -> None:
    free_gb = shutil.disk_usage(ROOT).free / 1_000_000_000
    if free_gb < 10:
        raise RuntimeError(
            f'Only {free_gb:.1f} GB is free. Free at least 10 GB (20 GB recommended) '
            'before building. Nothing was deleted or restarted. '
            'Do not delete the PostgreSQL volume or use Docker factory reset: they contain your history.'
        )


def compose_command() -> list[str]:
    docker = shutil.which('docker')
    if docker and run([docker, 'compose', 'version'], capture=True, check=False, timeout=10).returncode == 0:
        return [docker, 'compose']
    if DESKTOP_COMPOSE.is_file():
        return [str(DESKTOP_COMPOSE)]
    legacy = shutil.which('docker-compose')
    if legacy:
        return [legacy]
    raise RuntimeError('Docker Compose is missing. Install/open Docker Desktop, or run make demo for sample data.')


def read_env() -> dict[str, str]:
    path = ROOT / '.env'
    if not path.exists():
        return {}
    return {
        key.strip(): value.strip().strip('\"\'')
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith('#') and '=' in line
        for key, value in [line.split('=', 1)]
    }


def free_port(port: int) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            return False
    return True


def configure() -> dict[str, str]:
    """Fill only missing/template values; never rotate an existing credential."""
    path = ROOT / '.env'
    values = read_env()
    template = (ROOT / '.env.example').read_text()
    text = path.read_text() if path.exists() else template
    defaults = {
        key: value for line in template.splitlines()
        if line and not line.startswith('#') and '=' in line
        for key, value in [line.split('=', 1)]
    }
    changed: dict[str, str] = {}
    for key, default in defaults.items():
        if key not in values:
            values[key] = default
            changed[key] = default
    for key in ('POSTGRES_PASSWORD', 'BIKESHARE_INGEST_PASSWORD', 'BIKESHARE_API_PASSWORD', 'BIKESHARE_REPORTER_PASSWORD'):
        if not values[key] or values[key].startswith('replace-with-'):
            values[key] = secrets.token_hex(24)
            changed[key] = values[key]
    from urllib.parse import quote

    roles = (
        ('MIGRATION', values['POSTGRES_USER'], 'POSTGRES_PASSWORD'),
        ('INGEST', 'bikeshare_ingest', 'BIKESHARE_INGEST_PASSWORD'),
        ('API', 'bikeshare_api', 'BIKESHARE_API_PASSWORD'),
        ('REPORTING', 'bikeshare_reporter', 'BIKESHARE_REPORTER_PASSWORD'),
    )
    for name, user, password_key in roles:
        key = f'BIKESHARE_{name}_DATABASE_URL'
        if not values.get(key) or 'replace-with-' in values[key]:
            values[key] = f'postgresql+psycopg://{quote(user, safe="")}:{quote(values[password_key], safe="")}@db:5432/{quote(values["POSTGRES_DB"], safe="")}'
            changed[key] = values[key]
    if values['BIKESHARE_SOURCE_CONTACT'].startswith('replace-with-'):
        values['BIKESHARE_SOURCE_CONTACT'] = 'local educational project; no public deployment'
        changed['BIKESHARE_SOURCE_CONTACT'] = values['BIKESHARE_SOURCE_CONTACT']
    existing_keys: set[str] = set()
    lines: list[str] = []
    for line in text.splitlines():
        key = line.split('=', 1)[0] if '=' in line and not line.startswith('#') else ''
        existing_keys.add(key)
        lines.append(f'{key}={changed[key]}' if key in changed else line)
    lines.extend(f'{key}={value}' for key, value in changed.items() if key not in existing_keys)
    if changed or not path.exists():
        with open(path, 'w', opener=lambda name, flags: os.open(name, flags, 0o600)) as handle:
            handle.write('\n'.join(lines) + '\n')
        path.chmod(0o600)
        print('Local configuration is ready. Passwords are stored only in .env.', flush=True)
    return values


def require_engine() -> None:
    docker = shutil.which('docker')
    if not docker:
        raise RuntimeError('Docker is not installed. Install Docker Desktop, or run make demo.')
    if run([docker, 'info', '--format', '{{.ServerVersion}}'], capture=True, check=False, timeout=10).returncode == 0:
        return
    if sys.platform == 'darwin' and Path('/Applications/Docker.app').exists():
        print('Opening Docker Desktop. Complete any first-run prompts in its window…', flush=True)
        run(['open', '-a', 'Docker'])
        for _ in range(60):
            if run([docker, 'info', '--format', '{{.ServerVersion}}'], capture=True, check=False, timeout=10).returncode == 0:
                return
            time.sleep(2)
    raise RuntimeError('Docker is not running. Open Docker Desktop, wait for the engine, then run make start again.')


def health(url: str) -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(url + '/readyz', timeout=3) as response:
            result = json.load(response)
        return result if isinstance(result, dict) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def start(*, open_browser: bool) -> None:
    require_build_space()
    command = compose_command()
    require_engine()
    values = configure()
    port = int(values['BIKESHARE_API_PORT'])
    url = f'http://127.0.0.1:{port}'
    existing = run([*command, 'ps', '--status', 'running', '-q', 'api'], capture=True).stdout.strip()
    if not existing and not free_port(port):
        raise RuntimeError(f'Port {port} is in use. Set BIKESHARE_API_PORT=8081 in .env and retry. The other application has been left running.')
    existing_db = run([*command, 'ps', '--status', 'running', '-q', 'db'], capture=True).stdout.strip()
    database_port = int(values['POSTGRES_PORT'])
    if not existing_db and not free_port(database_port):
        raise RuntimeError(f'Database port {database_port} is in use. Change POSTGRES_PORT in .env to an unused port such as 5434, then retry. Do not change the internal database URLs.')
    run([*command, 'config', '--quiet'])
    print('Building and starting the live application. The first build downloads dependencies.', flush=True)
    run([*command, 'up', '--build', '-d', 'db', 'migrate', 'collector', 'api'])
    print('Waiting for the first usable live station update…', flush=True)
    for _ in range(90):
        result = health(url)
        if result and result.get('ready') and result.get('mode') == 'live_baseline':
            print(f'\nLive dashboard is ready: {url}/dashboard\nDock finder: {url}/demo\nStop: make stop   Logs: make logs', flush=True)
            if open_browser:
                webbrowser.open(url + '/dashboard')
            return
        time.sleep(2)
    raise RuntimeError(f'The services started but live data is not ready yet. Open {url}/demo for status, then run make logs. No sample data was substituted.')


def demo() -> None:
    uv = shutil.which('uv')
    if not uv:
        raise RuntimeError('uv is required for the sample demo. Install uv or use make start with Docker Desktop.')
    port = next((candidate for candidate in range(8081, 8091) if free_port(candidate)), None)
    if port is None:
        raise RuntimeError('Ports 8081-8090 are busy. Stop an unused local demo and retry.')
    environment = os.environ | {
        'UV_CACHE_DIR': str(ROOT / '.uv-cache'),
        'BIKESHARE_APP_MODE': 'fixture_demo',
        'BIKESHARE_BIND_HOST': '127.0.0.1',
        'BIKESHARE_BIND_PORT': str(port),
    }
    print(f'Sample-data dashboard: http://127.0.0.1:{port}/dashboard — press Ctrl+C to stop.', flush=True)
    subprocess.run([uv, 'run', '--locked', 'bikeshare', 'serve'], cwd=ROOT, env=environment, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description='Start and manage the local Bike Share application.')
    parser.add_argument('action', choices=('start', 'setup', 'doctor', 'stop', 'status', 'logs', 'demo', 'compose'))
    parser.add_argument('--open', action='store_true', dest='open_browser')
    args, extra = parser.parse_known_args()
    try:
        if args.action == 'start':
            start(open_browser=args.open_browser)
        elif args.action == 'setup':
            configure()
        elif args.action == 'demo':
            demo()
        elif args.action == 'doctor':
            print(f'Project: {ROOT}\nPython: {sys.version.split()[0]}\nFree disk: {shutil.disk_usage(ROOT).free/1_000_000_000:.1f} GB')
            command = compose_command()
            print('Compose: ' + run([*command, 'version'], capture=True).stdout.strip())
            require_engine()
            print('Docker engine: running')
            values = read_env()
            print('Configuration: ' + ('present' if values else 'will be created by make start'))
            url = f'http://127.0.0.1:{values.get("BIKESHARE_API_PORT", "8080")}'
            print('Application: ' + json.dumps(health(url) or {'ready': False}))
        else:
            command = compose_command()
            actions = {'stop': ['stop'], 'status': ['ps'], 'logs': ['logs', '--tail', '80', 'collector', 'api', 'migrate'], 'compose': extra}
            run([*command, *actions[args.action]])
    except subprocess.TimeoutExpired:
        print('\nDocker did not respond in time. Check free disk space and restart Docker Desktop. '
              'Do not use factory reset or delete the database volume.', file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f'\nCould not finish: {error}', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nStopped.')


if __name__ == '__main__':
    main()
