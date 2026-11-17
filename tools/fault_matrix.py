"""缺陷注入矩阵：逐个启用 SUT 缺陷，验证接口用例能否发现。

用法：
    python tools/fault_matrix.py
    python run.py faults

输出：控制台汇总 + reports/fault_matrix.md
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.failure_triage import parse_junit  # noqa: E402
from sut.faults import FAULT_SPECS  # noqa: E402


@dataclass
class FaultRun:
    fault_id: str
    title: str
    area: str
    detected: bool
    failures: int
    duration: float
    examples: list[str] = field(default_factory=list)


def _run_pytest(junit_path: Path, faults: str | None = None) -> tuple[int, float]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "TESTFORGE_RETRIES": "0",
        }
    )
    if faults:
        env["TESTFORGE_FAULTS"] = faults
    else:
        env.pop("TESTFORGE_FAULTS", None)

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "not ui",
        "-q",
        "--tb=no",
        "--maxfail=3",
        "-p",
        "no:cacheprovider",
        "-n",
        "4",
        f"--junitxml={junit_path}",
    ]
    started = time.time()
    process = subprocess.run(
        command, cwd=ROOT, env=env, capture_output=True, text=True
    )
    return process.returncode, round(time.time() - started, 1)


def _collect(junit_path: Path) -> list[str]:
    try:
        failures = parse_junit(junit_path)
    except (FileNotFoundError, ValueError):
        return []
    return [f"{failure.nodeid}::{failure.test_name}" for failure in failures]


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="testforge-faults-"))

    print("基线检查（不注入缺陷）...")
    baseline_xml = workdir / "baseline.xml"
    baseline_code, baseline_time = _run_pytest(baseline_xml)
    baseline_failures = _collect(baseline_xml)
    if baseline_code != 0:
        print(f"基线未通过（{len(baseline_failures)} 个失败），请先修复：")
        for name in baseline_failures[:5]:
            print(f"  - {name}")
        return 2
    print(f"基线通过，用时 {baseline_time}s\n")

    runs: list[FaultRun] = []
    for spec in FAULT_SPECS:
        print(f"注入 {spec.id}（{spec.area}：{spec.title}）...", end=" ", flush=True)
        junit = workdir / f"{spec.id}.xml"
        code, duration = _run_pytest(junit, faults=spec.id)
        failures = _collect(junit)
        detected = code != 0 or bool(failures)
        run = FaultRun(
            fault_id=spec.id,
            title=spec.title,
            area=spec.area,
            detected=detected,
            failures=len(failures),
            duration=duration,
            examples=failures[:3],
        )
        runs.append(run)
        print(f"{'检出' if detected else '未检出'}（{len(failures)} 个失败，{duration}s）")

    detected = sum(1 for run in runs if run.detected)
    rate = detected / len(runs) * 100 if runs else 0.0

    lines = [
        "# 缺陷注入检出率",
        "",
        f"- 基线：接口用例全部通过（{baseline_time}s）",
        f"- 注入缺陷：{len(runs)} 个",
        f"- 检出：{detected}/{len(runs)}（{rate:.0f}%）",
        "",
        "| 缺陷 | 模块 | 说明 | 结果 | 失败用例数 | 示例 |",
        "|:--|:--|:--|:--|--:|:--|",
    ]
    for run in runs:
        example = run.examples[0] if run.examples else "-"
        result = "检出" if run.detected else "**未检出**"
        lines.append(
            f"| `{run.fault_id}` | {run.area} | {run.title} | {result} | "
            f"{run.failures} | {example} |"
        )

    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    report = out_dir / "fault_matrix.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n检出 {detected}/{len(runs)}（{rate:.0f}%），报告：{report}")
    if detected < len(runs):
        print("存在未检出缺陷，说明对应用例覆盖不足：")
        for run in runs:
            if not run.detected:
                print(f"  - {run.fault_id}: {run.title}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
