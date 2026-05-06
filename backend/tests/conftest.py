from __future__ import annotations

import pytest

from backend.app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(database_path=tmp_path / "test.db")


@pytest.fixture
def client(app):
    return app.test_client()
