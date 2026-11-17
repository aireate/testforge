"""失败归因评测：用标注样本量化规则/LLM 的分类效果。

评估指标：准确率、宏平均 F1、每类 precision/recall/F1、混淆矩阵。
这是「AI 测试」里最容易被追问的部分：不能只说接了 LLM，要能证明效果。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from ai.failure_triage import CATEGORY_LABELS, Failure, classify_failure


@dataclass(frozen=True)
class EvalSample:
    id: str
    message: str
    detail: str
    expected: str
    note: str = ""


@dataclass(frozen=True)
class ClassScore:
    label: str
    support: int
    precision: float
    recall: float
    f1: float


@dataclass
class EvalReport:
    predictor: str
    total: int
    correct: int
    accuracy: float
    macro_f1: float
    per_class: dict[str, ClassScore]
    confusion: dict[str, dict[str, int]]
    mismatches: list[dict[str, str]]
    elapsed: float


def load_samples(path: str | Path) -> list[EvalSample]:
    samples: list[EvalSample] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                samples.append(
                    EvalSample(
                        id=raw["id"],
                        message=raw["message"],
                        detail=raw.get("detail", ""),
                        expected=raw["expected"],
                        note=raw.get("note", ""),
                    )
                )
            except (KeyError, json.JSONDecodeError) as exc:
                raise ValueError(f"数据集第 {line_no} 行格式错误: {exc}") from exc
    if not samples:
        raise ValueError("数据集为空")
    unknown = {sample.expected for sample in samples} - set(CATEGORY_LABELS)
    if unknown:
        raise ValueError(f"存在未知分类: {sorted(unknown)}")
    return samples


def evaluate_predictions(
    samples: list[EvalSample],
    predictions: dict[str, str],
    predictor: str = "rules",
    elapsed: float = 0.0,
) -> EvalReport:
    labels = list(CATEGORY_LABELS)
    confusion = {expected: {predicted: 0 for predicted in labels} for expected in labels}
    correct = 0
    mismatches: list[dict[str, str]] = []

    for sample in samples:
        predicted = predictions.get(sample.id, "UNKNOWN")
        confusion[sample.expected][predicted] += 1
        if predicted == sample.expected:
            correct += 1
        else:
            mismatches.append(
                {
                    "id": sample.id,
                    "expected": CATEGORY_LABELS[sample.expected],
                    "predicted": CATEGORY_LABELS.get(predicted, predicted),
                    "note": sample.note,
                }
            )

    per_class: dict[str, ClassScore] = {}
    f1_scores: list[float] = []
    for label in labels:
        support = sum(confusion[label].values())
        tp = confusion[label][label]
        predicted_count = sum(row[label] for row in confusion.values())
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = ClassScore(label, support, precision, recall, f1)
        if support:
            f1_scores.append(f1)

    return EvalReport(
        predictor=predictor,
        total=len(samples),
        correct=correct,
        accuracy=correct / len(samples) if samples else 0.0,
        macro_f1=sum(f1_scores) / len(f1_scores) if f1_scores else 0.0,
        per_class=per_class,
        confusion=confusion,
        mismatches=mismatches,
        elapsed=round(elapsed, 3),
    )


def evaluate_rules(samples: list[EvalSample]) -> EvalReport:
    started = time.perf_counter()
    predictions = {
        sample.id: classify_failure(
            Failure(
                nodeid=sample.id,
                test_name=sample.id,
                message=sample.message,
                detail=sample.detail,
            )
        ).category
        for sample in samples
    }
    return evaluate_predictions(
        samples, predictions, predictor="rules", elapsed=time.perf_counter() - started
    )


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(report: EvalReport) -> str:
    lines = [
        "# 失败归因评测报告",
        "",
        f"- 预测器：{report.predictor}",
        f"- 样本数：{report.total}",
        f"- 准确率：{report.accuracy:.1%}（{report.correct}/{report.total}）",
        f"- 宏平均 F1：{report.macro_f1:.3f}",
        f"- 总耗时：{report.elapsed:.3f}s",
        "",
        "## 分类指标",
        "",
        "| 分类 | 支持数 | Precision | Recall | F1 |",
        "|:--|--:|--:|--:|--:|",
    ]
    for score in report.per_class.values():
        lines.append(
            f"| {CATEGORY_LABELS[score.label]} | {score.support} | "
            f"{score.precision:.3f} | {score.recall:.3f} | {score.f1:.3f} |"
        )

    lines.extend(["", "## 混淆矩阵（行=真实，列=预测）", ""])
    short = {label: label[:4] for label in CATEGORY_LABELS}
    header = "| 真实 \\ 预测 | " + " | ".join(short[label] for label in CATEGORY_LABELS) + " |"
    lines.append(header)
    lines.append("|:--|" + "|".join("--:" for _ in CATEGORY_LABELS) + "|")
    for expected in CATEGORY_LABELS:
        row = report.confusion[expected]
        lines.append(
            f"| {CATEGORY_LABELS[expected]} | "
            + " | ".join(str(row[predicted]) for predicted in CATEGORY_LABELS)
            + " |"
        )

    if report.mismatches:
        lines.extend(["", "## 错误样本", "", "| 样本 | 真实 | 预测 | 说明 |", "|:--|:--|:--|:--|"])
        for item in report.mismatches:
            lines.append(
                f"| {_cell(item['id'])} | {_cell(item['expected'])} | "
                f"{_cell(item['predicted'])} | {_cell(item['note'])} |"
            )

    lines.extend(
        [
            "",
            "> 说明：规则引擎为离线基线；接入 LLM 后，用同一数据集和指标做 A/B 对比，",
            "> 并以准确率相对基线下降不超过 5% 作为 prompt/模型变更的回归门槛。",
            "",
        ]
    )
    return "\n".join(lines)
