import pytest
from common.request_util import RequestUtil
from common.log_util import info, error


@pytest.fixture(scope="session")
def api():
    return RequestUtil()


@pytest.fixture(scope="session")
def base_url():
    return "https://jsonplaceholder.typicode.com"
