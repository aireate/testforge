import pytest
from common.request_util import RequestUtil


@pytest.fixture
def api():
    return RequestUtil()


def test_create_post(api):
    payload = {
        "title": "foo",
        "body": "bar",
        "userId": 1
    }

    response = api.post("https://jsonplaceholder.typicode.com/posts", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["title"] == payload["title"]
