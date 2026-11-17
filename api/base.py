from common.request_util import RequestUtil


class BaseApi:
    """服务层基类：只负责组织请求，不做断言，断言留在用例中。"""

    def __init__(self, client: RequestUtil) -> None:
        self.client = client
