import requests


class RequestUtil:
    def __init__(self, base_url=None, timeout=30):
        self.base_url = base_url
        self.timeout = timeout

    def _build_url(self, url):
        if self.base_url and not url.startswith("http"):
            return f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        return url

    def get(self, url, **kwargs):
        return requests.get(self._build_url(url), timeout=self.timeout, **kwargs)

    def post(self, url, **kwargs):
        return requests.post(self._build_url(url), timeout=self.timeout, **kwargs)

    def put(self, url, **kwargs):
        return requests.put(self._build_url(url), timeout=self.timeout, **kwargs)

    def delete(self, url, **kwargs):
        return requests.delete(self._build_url(url), timeout=self.timeout, **kwargs)
