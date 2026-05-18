import requests


class RequestUtil:
    def __init__(self, base_url=None, timeout=30):
        self.base_url = base_url
        self.timeout = timeout

    def get(self, url, **kwargs):
        if self.base_url and not url.startswith("http"):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        return requests.get(url, timeout=self.timeout, **kwargs)

    def post(self, url, **kwargs):
        if self.base_url and not url.startswith("http"):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        return requests.post(url, timeout=self.timeout, **kwargs)
