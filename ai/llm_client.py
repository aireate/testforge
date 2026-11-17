"""可选的 LLM 归因增强。

只依赖 OpenAI 兼容的 /chat/completions 接口，通过环境变量启用：
    TF_LLM_BASE_URL  例如 https://api.openai.com/v1
    TF_LLM_API_KEY
    TF_LLM_MODEL     默认 gpt-4o-mini
未配置、超时或返回异常时返回 None，规则引擎结果不受影响。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests

from ai.failure_triage import TriageResult

_SYSTEM_PROMPT = (
    "你是资深测试工程师。根据失败的断言、状态码和堆栈，判断最可能的根因，"
    "并给出一条可执行的排查建议。只使用给出的信息，不要编造不存在的日志。"
    "输出 80 字以内的中文，格式：根因：...；建议：..."
)


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key: str
    model: str
    timeout: float = 20.0

    @classmethod
    def from_env(cls) -> "LlmConfig | None":
        base_url = os.getenv("TF_LLM_BASE_URL", "").strip()
        api_key = os.getenv("TF_LLM_API_KEY", "").strip()
        if not base_url or not api_key:
            return None
        return cls(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            model=os.getenv("TF_LLM_MODEL", "gpt-4o-mini"),
            timeout=float(os.getenv("TF_LLM_TIMEOUT", "20")),
        )

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"


def enrich(result: TriageResult, config: LlmConfig | None = None) -> str | None:
    config = config or LlmConfig.from_env()
    if config is None:
        return None

    user_prompt = (
        f"用例：{result.failure.nodeid}::{result.failure.test_name}\n"
        f"规则分类：{result.label}（{result.confidence}）\n"
        f"依据：{result.evidence}\n"
        f"堆栈：{result.failure.detail[:1500]}"
    )
    try:
        response = requests.post(
            config.endpoint,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=config.timeout,
        )
        if response.status_code != 200:
            return None
        content = response.json()["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None

    note = " ".join(str(content).split())
    return note[:300] or None
