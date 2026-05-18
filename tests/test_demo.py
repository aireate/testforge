import pytest
from common.request_util import RequestUtil


@pytest.fixture
def api():
    return RequestUtil()


def test_get_request(api):
    response = api.get("https://httpbin.org/get")
    assert response.status_code == 200
