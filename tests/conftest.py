import os

import pytest

os.environ.setdefault("PECCA_TEST_SMALL", "1")


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PECCA_HOME", str(tmp_path / ".pecca"))
    monkeypatch.setenv("PECCA_TEST_SMALL", "1")
    monkeypatch.delenv("PECCA_WORKSPACE", raising=False)
    monkeypatch.delenv("PECCA_ALLOW_FORCE", raising=False)
    monkeypatch.chdir(tmp_path)
    from pecca.core import context

    context.reset()
    yield
    context.reset()
