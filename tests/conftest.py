"""Build camera fixtures once so replay tests can run OpenCV on them."""

import pytest

from tests.fixtures.build_fixtures import build


@pytest.fixture(scope="session", autouse=True)
def camera_fixtures():
    build()
