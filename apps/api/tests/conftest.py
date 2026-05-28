import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages"))

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)
