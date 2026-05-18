import pytest
from common.request_util import RequestUtil


@pytest.fixture
def api():
    return RequestUtil()


def test_get_user(api):
    response = api.get("https://jsonplaceholder.typicode.com/users/1")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == 1
    assert "username" in data
    assert "email" in data
