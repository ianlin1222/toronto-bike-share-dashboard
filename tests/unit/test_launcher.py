from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('launcher', Path(__file__).parents[2] / 'scripts/manage.py')
assert spec is not None and spec.loader is not None
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.mark.parametrize('free_gb', [0.1, 5, 9.9])
def test_low_disk_stops_before_any_docker_operation(monkeypatch, free_gb):
    monkeypatch.setattr(launcher.shutil, 'disk_usage', lambda _: SimpleNamespace(free=free_gb*1_000_000_000))
    monkeypatch.setattr(launcher, 'compose_command', lambda: pytest.fail('Must not contact Docker'))
    with pytest.raises(RuntimeError, match='Free at least 10 GB'):
        launcher.start(open_browser=False)


def test_sufficient_build_space_passes(monkeypatch):
    monkeypatch.setattr(launcher.shutil, 'disk_usage', lambda _: SimpleNamespace(free=20*1024**3))
    launcher.require_build_space()


def test_configuration_fills_templates_once_without_rotating_passwords(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).parents[2]
    (tmp_path / '.env.example').write_text((root / '.env.example').read_text())
    monkeypatch.setattr(launcher, 'ROOT', tmp_path)
    first = launcher.configure()
    contents = (tmp_path / '.env').read_text()
    second = launcher.configure()
    assert first == second
    assert contents == (tmp_path / '.env').read_text()
    assert 'replace-with-' not in contents
    assert first['BIKESHARE_API_PASSWORD'] in first['BIKESHARE_API_DATABASE_URL']
    assert first['BIKESHARE_API_PASSWORD'] != first['POSTGRES_PASSWORD']
    assert (tmp_path / '.env').stat().st_mode & 0o777 == 0o600
