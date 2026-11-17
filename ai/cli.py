"""失败归因命令行入口。

用法：
    python -m ai.cli --junit reports/junit.xml
    python -m ai.cli --junit reports/junit.xml --out reports/triage.md --llm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai.failure_triage import parse_junit, render_markdown, triage_failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TestForge 失败归因报告")
    parser.add_argument("--junit", default="reports/junit.xml", help="pytest JUnit XML 路径")
    parser.add_argument("--out", default="reports/triage.md", help="Markdown 输出路径")
    parser.add_argument("--llm", action="store_true", help="启用 LLM 增强（需 TF_LLM_* 环境变量）")
    args = parser.parse_args(argv)

    junit_path = Path(args.junit)
    if not junit_path.exists():
        print(f"未找到 JUnit 报告：{junit_path}", file=sys.stderr)
        print("请先执行：python -m pytest --junitxml=reports/junit.xml", file=sys.stderr)
        return 2

    failures = parse_junit(junit_path)
    results = triage_failures(failures, use_llm=args.llm)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(results), encoding="utf-8")

    print(f"失败用例：{len(results)}")
    if results:
        summary: dict[str, int] = {}
        for result in results:
            summary[result.label] = summary.get(result.label, 0) + 1
        print("分类：" + "，".join(f"{k} {v}" for k, v in summary.items()))
    print(f"报告已写入：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
