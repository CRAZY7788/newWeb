"""Pytest fixtures — sets an isolated SQLite DB before importing app (seed runs once)."""
import os
import sys
import uuid
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
NEW_APP_DIR = TESTS_DIR.parent
if str(NEW_APP_DIR) not in sys.path:
    sys.path.insert(0, str(NEW_APP_DIR))

TEST_DB = TESTS_DIR / f"pytest_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

import pytest  # noqa: E402

from app import (  # noqa: E402
    app,
    db,
    User,
    Folder,
    File,
    FILE_STATUS_ACCEPTED,
    FILE_STATUS_CHECKED_OUT,
    FILE_STATUS_DRAFT,
    FILE_STATUS_PENDING,
    FILE_STATUS_VOID,
)


@pytest.fixture(scope="session")
def flask_app():
    app.config["TESTING"] = True
    with app.app_context():
        yield app
    if TEST_DB.exists():
        TEST_DB.unlink(missing_ok=True)


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture
def app_ctx(flask_app):
    with flask_app.app_context():
        yield


@pytest.fixture
def login(client, app_ctx):
    def _login(username="admin"):
        user = User.query.filter_by(username=username).first()
        assert user is not None, f"seed user {username!r} missing"
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["username"] = user.username
            sess["role"] = user.role
        return client

    return _login


@pytest.fixture
def any_folder(app_ctx):
    folder = Folder.query.first()
    assert folder is not None, "no folder in seed data"
    return folder


def unique_name(prefix="doc"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
