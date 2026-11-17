import hmac
import json
from hashlib import sha256
from typing import Any

from api.base import BaseApi
from config.settings import settings


class PaymentApi(BaseApi):
    def callback(
        self,
        payload: dict[str, Any],
        signature: str | None = None,
        raw_body: str | None = None,
    ):
        raw = raw_body if raw_body is not None else json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        )
        sign = signature
        if sign is None:
            sign = hmac.new(
                settings.pay_secret.encode(), raw.encode(), sha256
            ).hexdigest()
        return self.client.post(
            "/payments/callback",
            data=raw.encode(),
            headers={
                "Content-Type": "application/json",
                "X-Pay-Signature": sign,
            },
        )
