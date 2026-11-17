"""失败归因评测入口：python tools/eval_triage.py"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.evaluation import evaluate_rules, load_samples, render_markdown  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="失败归因评测")
    parser.add_argument("--dataset", default=str(ROOT / "ai" / "eval_dataset.jsonl"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "triage_eval.md"))
    parser.add_argument("--min-accuracy", type=float, default=0.8)
    args = parser.parse_args()

    samples = load_samples(args.dataset)
    report = evaluate_rules(samples)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(report), encoding="utf-8")

    print(
        f"样本 {report.total}｜准确率 {report.accuracy:.1%}"
        f"（{report.correct}/{report.total}）｜宏平均 F1 {report.macro_f1:.3f}"
        f"｜耗时 {report.elapsed:.3f}s"
    )
    if report.mismatches:
        print("错误样本：")
        for item in report.mismatches:
            print(f"  - {item['id']}: 真实 {item['expected']} / 预测 {item['predicted']}")
    print(f"报告：{out}")

    if report.accuracy < args.min_accuracy:
        print(f"未达到门槛 {args.min_accuracy:.0%}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
