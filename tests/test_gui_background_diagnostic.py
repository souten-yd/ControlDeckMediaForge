"""Native-tab diagnostics own their browser and never override visibility."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.mark.parametrize('fail', [False, True])
def test_native_browser_cleanup_and_no_default_overrides(monkeypatch: pytest.MonkeyPatch, fail: bool) -> None:
    script = Path(__file__).resolve().parents[1] / 'scripts/3ds_background_return_installed_e2e.py'
    spec = importlib.util.spec_from_file_location('background_diagnostic', script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls: list[Any] = []
    profile: list[Path] = []

    class Process:
        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            calls.append('terminate-owned')

        def wait(self, timeout: int) -> None:
            assert timeout == 15
            calls.append('wait-owned')

    def launch(argv: list[str], **kwargs: Any) -> Process:
        assert isinstance(argv, list) and 'shell' not in kwargs
        folder = Path(next(arg.split('=', 1)[1] for arg in argv if arg.startswith('--user-data-dir=')))
        profile.append(folder)
        (folder / 'DevToolsActivePort').write_text('12345\n/devtools/test\n')
        return Process()

    browser = SimpleNamespace(close=lambda: calls.append('close-browser'))

    def connect(endpoint: str, **kwargs: Any) -> Any:
        assert endpoint == 'http://127.0.0.1:12345'
        assert kwargs == {'no_defaults': True}
        return browser

    monkeypatch.setattr(module.subprocess, 'Popen', launch)
    playwright = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))
    try:
        with module.native_browser(playwright) as opened:
            assert opened is browser
            if fail:
                raise ValueError('diagnostic failed')
    except ValueError:
        assert fail
    assert calls == ['close-browser', 'terminate-owned', 'wait-owned']
    assert len(profile) == 1 and not profile[0].exists()
