"""失败归因引擎。

设计原则：
1. 离线可用：规则引擎不依赖网络和密钥，CI 中始终生效；
2. LLM 可选：配置环境变量后才调用，失败时静默降级，不影响测试结果；
3. 输出可执行：每个分类给出排查动作，而不是只贴一段堆栈。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

CATEGORY_LABELS = {
    "ENVIRONMENT": "环境/连接",
    "SERVER_ERROR": "服务端 5xx",
    "VALIDATION": "参数校验",
    "AUTHENTICATION": "认证",
    "AUTHORIZATION": "权限",
    "CONFLICT": "业务冲突",
    "DATABASE": "数据库",
    "ASSERTION": "断言失败",
    "UNKNOWN": "未分类",
}

CATEGORY_ACTIONS = {
    "ENVIRONMENT": "检查 SUT 是否启动、端口与网络是否可达，确认 fixture 生命周期。",
    "SERVER_ERROR": "查看 SUT 日志与堆栈，按请求报文复现并定位服务端异常。",
    "VALIDATION": "核对请求体与接口 schema，确认是用例数据问题还是契约变更。",
    "AUTHENTICATION": "检查 Token 获取、过期时间与请求头注入是否正确。",
    "AUTHORIZATION": "确认账号角色与资源归属，区分越权预期与前置数据问题。",
    "CONFLICT": "检查库存/订单状态/幂等键等前置状态，确认冲突是否符合预期。",
    "DATABASE": "检查数据库文件、并发锁与事务提交，落库断言前确认写入已完成。",
    "ASSERTION": "对比期望值与实际响应，附上请求/响应报文定位差异字段。",
    "UNKNOWN": "人工复核堆栈，并把该失败模式补充为新的归因规则。",
}

# 顺序即优先级：先排除环境问题，再看显式状态码，最后才落到断言
_RULES: list[tuple[str, str, str]] = [
    (
        "ENVIRONMENT",
        r"Connection(Error|Refused|Reset|Aborted)|Max retries exceeded|timed out|Timeout|"
        r"ConnectTimeout|ReadTimeout|Name or service not known",
        "high",
    ),
    ("SERVER_ERROR", r"\b5\d{2}\b|Internal Server Error|HTTP_5\d{2}|Bad Gateway", "high"),
    ("VALIDATION", r"\b422\b|VALIDATION_ERROR|RequestValidationError|ResponseValidationError|validation error", "high"),
    (
        "AUTHENTICATION",
        r"\b401\b|UNAUTHORIZED|TOKEN_EXPIRED|TOKEN_INVALID|INVALID_CREDENTIALS|"
        r"Authentication failed|missing bearer token",
        "high",
    ),
    ("AUTHORIZATION", r"\b403\b|FORBIDDEN|PermissionDenied|not allowed to access|role .* cannot", "high"),
    (
        "CONFLICT",
        r"\b409\b|OUT_OF_STOCK|IDEMPOTENCY_CONFLICT|ORDER_STATE_INVALID|PRODUCT_IN_USE|STOCK_NEGATIVE|"
        r"Idempotency-Key reused|different payload",
        "high",
    ),
    ("DATABASE", r"sqlite3?\.|database is locked|no such table|IntegrityError|OperationalError", "medium"),
    ("ASSERTION", r"AssertionError|^assert |\bassert\b", "medium"),
]


@dataclass(frozen=True)
class Failure:
    nodeid: str
    test_name: str
    message: str = ""
    detail: str = ""
    duration: float = 0.0


@dataclass
class TriageResult:
    failure: Failure
    category: str
    confidence: str
    evidence: str
    action: str
    llm_note: str | None = None

    @property
    def label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)


def _find_evidence(failure: Failure, pattern: re.Pattern) -> str:
    lines = [
        line.strip()
        for line in f"{failure.message}\n{failure.detail}".splitlines()
        if line.strip()
    ]
    for line in lines:
        if pattern.search(line):
            return line[:220]
    return lines[0][:220] if lines else ""


def classify_failure(failure: Failure) -> TriageResult:
    haystack = f"{failure.message}\n{failure.detail}"
    for category, pattern, confidence in _RULES:
        compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        if compiled.search(haystack):
            return TriageResult(
                failure=failure,
                category=category,
                confidence=confidence,
                evidence=_find_evidence(failure, compiled),
                action=CATEGORY_ACTIONS[category],
            )
    return TriageResult(
        failure=failure,
        category="UNKNOWN",
        confidence="low",
        evidence=_find_evidence(failure, re.compile(r".")) or failure.message[:220],
        action=CATEGORY_ACTIONS["UNKNOWN"],
    )


def parse_junit(path: str | Path) -> list[Failure]:
    """从 JUnit XML 中提取失败/错误用例（pytest --junitxml 的产物）。"""
    tree = ET.parse(path)
    root = tree.getroot()
    failures: list[Failure] = []

    for case in root.iter("testcase"):
        node = case.find("failure")
        if node is None:
            node = case.find("error")
        if node is None:
            continue
        message = node.get("message") or ""
        detail = node.text or ""
        failures.append(
            Failure(
                nodeid=case.get("classname", ""),
                test_name=case.get("name", ""),
                message=message,
                detail=detail,
                duration=float(case.get("time") or 0.0),
            )
        )
    return failures


def triage_failures(failures: list[Failure], use_llm: bool = False) -> list[TriageResult]:
    from ai import llm_client

    results = [classify_failure(failure) for failure in failures]
    if use_llm and llm_client.LlmConfig.from_env() is not None:
        for result in results:
            result.llm_note = llm_client.enrich(result)
    return results


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(results: list[TriageResult]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    counts: dict[str, int] = {}
    for result in results:
        counts[result.category] = counts.get(result.category, 0) + 1

    lines = [
        "# 测试失败归因报告",
        "",
        f"- 生成时间：{now}",
        f"- 失败用例：{len(results)}",
        "- 分类分布："
        + ("、".join(f"{CATEGORY_LABELS.get(k, k)} {v}" for k, v in counts.items()) or "无"),
        "",
        "| 用例 | 分类 | 置信度 | 依据 | 建议动作 |",
        "|:--|:--|:--|:--|:--|",
    ]
    for result in results:
        name = result.failure.test_name or result.failure.nodeid or "unknown"
        lines.append(
            f"| {_cell(name)} | {result.label} | {result.confidence} | "
            f"{_cell(result.evidence)} | {_cell(result.action)} |"
        )

    details = [result for result in results if result.failure.detail]
    if details:
        lines.extend(["", "## 失败明细", ""])
        for result in details:
            lines.extend(
                [
                    f"### {result.failure.test_name or result.failure.nodeid}",
                    "",
                    f"- 分类：{result.label}（{result.confidence}）",
                    f"- 建议：{result.action}",
                ]
            )
            if result.llm_note:
                lines.append(f"- LLM 分析：{result.llm_note}")
            lines.extend(
                [
                    "",
                    "```text",
                    result.failure.detail.strip()[:1500],
                    "```",
                    "",
                ]
            )
    return "\n".join(lines) + "\n"
