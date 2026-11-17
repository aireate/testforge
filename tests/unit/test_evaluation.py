from pathlib import Path

import pytest

from ai.evaluation import EvalSample, evaluate_predictions, evaluate_rules, load_samples
from ai.failure_triage import CATEGORY_LABELS

DATASET = Path(__file__).resolve().parents[2] / "ai" / "eval_dataset.jsonl"


def test_load_dataset() -> None:
    samples = load_samples(DATASET)
    assert len(samples) == 60
    assert {sample.expected for sample in samples} == set(CATEGORY_LABELS)
    assert len({sample.id for sample in samples}) == len(samples)


def test_perfect_predictions() -> None:
    samples = [
        EvalSample("1", "m", "", "AUTHENTICATION"),
        EvalSample("2", "m", "", "CONFLICT"),
    ]
    report = evaluate_predictions(
        samples, {"1": "AUTHENTICATION", "2": "CONFLICT"}, predictor="test"
    )
    assert report.accuracy == 1.0
    assert report.macro_f1 == pytest.approx(1.0)
    assert report.mismatches == []


def test_accuracy_and_confusion() -> None:
    samples = [
        EvalSample("1", "m", "", "AUTHENTICATION"),
        EvalSample("2", "m", "", "AUTHENTICATION"),
        EvalSample("3", "m", "", "VALIDATION"),
    ]
    report = evaluate_predictions(
        samples,
        {"1": "AUTHENTICATION", "2": "VALIDATION", "3": "VALIDATION"},
        predictor="test",
    )
    assert report.correct == 2
    assert report.accuracy == pytest.approx(2 / 3)
    assert report.confusion["AUTHENTICATION"]["AUTHENTICATION"] == 1
    assert report.confusion["AUTHENTICATION"]["VALIDATION"] == 1
    assert len(report.mismatches) == 1


def test_rule_report_consistency() -> None:
    samples = load_samples(DATASET)
    report = evaluate_rules(samples)
    assert report.total == 60
    assert report.correct + len(report.mismatches) == 60
    assert 0.8 <= report.accuracy < 1.0
