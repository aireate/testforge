"""AI 辅助测试能力：失败归因（规则引擎 + 可选 LLM）与报告生成。"""

from ai.failure_triage import Failure, TriageResult, classify_failure, parse_junit, render_markdown

__all__ = [
    "Failure",
    "TriageResult",
    "classify_failure",
    "parse_junit",
    "render_markdown",
]
